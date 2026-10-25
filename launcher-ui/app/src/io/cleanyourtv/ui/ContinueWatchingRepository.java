package io.cleanyourtv.ui;

import android.content.Context;
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

/** Screen-owned, foreground-driven data. No timers, UI objects, TMDB calls or persistent viewing-history cache. */
final class ContinueWatchingRepository implements AutoCloseable {
    interface Listener { void onContinueWatching(); }

    private final ContinueWatchingSource source;
    private final ExecutorService io;
    private final Executor main;
    private final Thread owner = Thread.currentThread();
    private final List<Listener> listeners = new ArrayList<>();
    private ContinueWatchingSource.Result result = ContinueWatchingSource.Result.empty(ContinueWatchingSource.Status.NOT_LOADED);
    private Future<?> pending;
    private long generation;
    private boolean foreground, closed;

    ContinueWatchingRepository(Context context) {
        this(new TvProviderWatchNextSource(context), Executors.newSingleThreadExecutor(), mainExecutor());
    }

    ContinueWatchingRepository(ContinueWatchingSource source, ExecutorService io, Executor main) {
        this.source = source;
        this.io = io;
        this.main = main;
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

    void onForeground() {
        checkOwner();
        if (closed) throw new IllegalStateException("Continue Watching repository is closed");
        if (foreground) return;
        foreground = true;
        refresh();
    }

    void onBackground() {
        checkOwner();
        foreground = false;
        invalidate();
    }

    void refresh() {
        checkOwner();
        if (!foreground || closed) return;
        invalidate();
        long request = generation;
        pending = io.submit(() -> {
            ContinueWatchingSource.Result loaded;
            try {
                loaded = qualify(source.load());
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
        if (pending != null) pending.cancel(true);
        pending = null;
    }

    private static ContinueWatchingSource.Result qualify(ContinueWatchingSource.Result loaded) {
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
        for (ContinueWatchingItem item : items) if (seen.add(item.stableId)) unique.add(item);
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
        invalidate();
        listeners.clear();
        result = ContinueWatchingSource.Result.empty(ContinueWatchingSource.Status.NOT_LOADED);
        io.shutdownNow();
    }

    private void checkOwner() {
        if (Thread.currentThread() != owner) throw new IllegalStateException("Use the repository on its owning UI thread");
    }
}
