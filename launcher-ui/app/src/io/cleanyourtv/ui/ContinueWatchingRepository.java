package io.cleanyourtv.ui;

import android.content.Context;
import android.content.ContentResolver;
import android.database.ContentObserver;
import android.media.tv.TvContract;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.Executor;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.function.LongSupplier;

/** Screen-owned, foreground-driven data. No timers, UI objects, TMDB calls or persistent viewing-history cache. */
final class ContinueWatchingRepository implements AutoCloseable {
    interface Listener { void onContinueWatching(); }
    private static final long RECENT_WINDOW_MILLIS = 30L * 24 * 60 * 60 * 1000;

    private final ContinueWatchingSource source;
    private final ExecutorService io;
    private final Executor main;
    private final LongSupplier clock;
    private final ContentResolver resolver;
    private final ContentObserver observer;
    private final Thread owner = Thread.currentThread();
    private final List<Listener> listeners = new ArrayList<>();
    private ContinueWatchingSource.Result result = ContinueWatchingSource.Result.empty(ContinueWatchingSource.Status.NOT_LOADED);
    private Future<?> pending;
    private long generation;
    private boolean foreground, closed;
    private boolean recentOnly, hideFinished;
    private boolean observing, changeQueued;

    ContinueWatchingRepository(Context context) {
        this(new TvProviderWatchNextSource(context), Executors.newSingleThreadExecutor(), mainExecutor(),
                System::currentTimeMillis, context.getApplicationContext().getContentResolver());
    }

    ContinueWatchingRepository(ContinueWatchingSource source, ExecutorService io, Executor main) {
        this(source, io, main, System::currentTimeMillis);
    }

    ContinueWatchingRepository(ContinueWatchingSource source, ExecutorService io, Executor main, LongSupplier clock) {
        this(source, io, main, clock, null);
    }

    ContinueWatchingRepository(ContinueWatchingSource source, ExecutorService io, Executor main, LongSupplier clock,
            ContentResolver resolver) {
        this.source = source;
        this.io = io;
        this.main = main;
        this.clock = clock;
        this.resolver = resolver;
        observer = resolver == null ? null : new ContentObserver(new Handler(Looper.getMainLooper())) {
            @Override public void onChange(boolean selfChange) { providerChanged(); }
            @Override public void onChange(boolean selfChange, Uri uri) { providerChanged(); }
        };
    }

    private static Executor mainExecutor() {
        Handler handler = new Handler(Looper.getMainLooper());
        return command -> handler.post(command);
    }

    void addListener(Listener listener) {
        checkOwner();
        if (!listeners.contains(listener)) listeners.add(listener);
    }

    void removeListener(Listener listener) { checkOwner(); listeners.remove(listener); }

    ContinueWatchingSource.Result current() { checkOwner(); return result; }

    void setFilters(boolean recentOnly, boolean hideFinished) {
        checkOwner();
        if (closed) throw new IllegalStateException("Continue Watching repository is closed");
        if (this.recentOnly == recentOnly && this.hideFinished == hideFinished) return;
        this.recentOnly = recentOnly;
        this.hideFinished = hideFinished;
        refresh();
    }

    void onForeground() {
        checkOwner();
        if (closed) throw new IllegalStateException("Continue Watching repository is closed");
        if (foreground) return;
        foreground = true;
        if (resolver != null) {
            try {
                resolver.registerContentObserver(TvContract.WatchNextPrograms.CONTENT_URI, true, observer);
                observing = true;
            } catch (SecurityException | IllegalArgumentException | UnsupportedOperationException e) {
                AppLog.w("Continue Watching: change notifications unavailable (" + e.getClass().getSimpleName() + ")");
            }
        }
        refresh();
    }

    void onBackground() {
        checkOwner();
        foreground = false;
        stopObserving();
        invalidate();
    }

    private void providerChanged() {
        checkOwner();
        if (!foreground || closed || changeQueued) return;
        // Invalidate immediately so an older, already-posted response cannot win this notification.
        invalidate();
        changeQueued = true;
        long request = generation;
        main.execute(() -> {
            checkOwner();
            if (!foreground || closed || generation != request) return;
            changeQueued = false;
            refresh();
        });
    }

    private void stopObserving() {
        if (!observing) return;
        observing = false;
        try {
            resolver.unregisterContentObserver(observer);
        } catch (SecurityException | IllegalArgumentException | IllegalStateException e) {
            AppLog.w("Continue Watching: could not unregister change notifications (" + e.getClass().getSimpleName() + ")");
        }
    }

    void refresh() {
        checkOwner();
        if (!foreground || closed) return;
        invalidate();
        long request = generation;
        boolean filterRecent = recentOnly, filterFinished = hideFinished;
        long now = clock.getAsLong();
        pending = io.submit(() -> {
            ContinueWatchingSource.Result loaded;
            try {
                loaded = qualify(source.load(), filterRecent, filterFinished, now);
            } catch (RuntimeException e) {
                AppLog.w("Continue Watching: source failed (" + e.getClass().getSimpleName() + ")");
                loaded = ContinueWatchingSource.Result.empty(ContinueWatchingSource.Status.ERROR);
            }
            ContinueWatchingSource.Result next = loaded;
            main.execute(() -> {
                checkOwner();
                if (closed || !foreground || generation != request) return;
                result = next;
                for (Listener listener : new ArrayList<>(listeners)) listener.onContinueWatching();
            });
        });
    }

    private void invalidate() {
        generation++;
        changeQueued = false;
        if (pending != null) pending.cancel(true);
        pending = null;
    }

    private static ContinueWatchingSource.Result qualify(ContinueWatchingSource.Result loaded,
            boolean recentOnly, boolean hideFinished, long now) {
        if (loaded.status != ContinueWatchingSource.Status.OK) {
            return ContinueWatchingSource.Result.empty(loaded.status);
        }
        List<ContinueWatchingItem> items = new ArrayList<>();
        for (ContinueWatchingItem item : loaded.items) if (item.canContinue()) items.add(item);
        // Unknown/nonpositive engagement sorts last; identity breaks ties without relying on provider row order.
        items.sort(Comparator.comparingLong(ContinueWatchingRepository::engagement).reversed()
                .thenComparing(item -> item.stableId));
        Set<String> seen = new HashSet<>();
        List<ContinueWatchingItem> unique = new ArrayList<>();
        for (ContinueWatchingItem item : items) {
            if (!seen.add(item.stableId)) continue;
            long engaged = engagement(item);
            if (recentOnly && engaged > 0 && engaged < now - RECENT_WINDOW_MILLIS) continue;
            Double progress = item.progress();
            if (hideFinished && progress != null && progress > 0.95d) continue;
            unique.add(item);
        }
        return new ContinueWatchingSource.Result(loaded.status, unique);
    }

    private static long engagement(ContinueWatchingItem item) {
        return item.lastEngagementTimeMillis == null ? 0 : Math.max(0, item.lastEngagementTimeMillis);
    }

    @Override public void close() {
        checkOwner();
        if (closed) return;
        closed = true;
        foreground = false;
        stopObserving();
        invalidate();
        listeners.clear();
        result = ContinueWatchingSource.Result.empty(ContinueWatchingSource.Status.NOT_LOADED);
        io.shutdownNow();
    }

    private void checkOwner() {
        if (Thread.currentThread() != owner) throw new IllegalStateException("Use the repository on its owning UI thread");
    }
}
