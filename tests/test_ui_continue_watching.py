"""Run the Phase 2 Java boundary with fake framework services, without a TV or network."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_ui_tv_provider_diagnostic import STUBS as DIAGNOSTIC_STUBS


ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / "launcher-ui/app/src/io/cleanyourtv/ui"

STUBS = {
    **DIAGNOSTIC_STUBS,
    "android/content/Context.java": """
package android.content;
public abstract class Context {
    public abstract ContentResolver getContentResolver();
    public abstract android.content.pm.PackageManager getPackageManager();
    public abstract int checkSelfPermission(String permission);
    public Context getApplicationContext() { return this; }
    public abstract void startActivity(Intent intent);
}
""",
    "android/content/ComponentName.java": """
package android.content;
public class ComponentName {
    private final String pkg;
    public ComponentName(String pkg) { this.pkg = pkg; }
    public String getPackageName() { return pkg; }
}
""",
    "android/content/ActivityNotFoundException.java": """
package android.content;
public class ActivityNotFoundException extends RuntimeException {}
""",
    "android/content/pm/ActivityInfo.java": """
package android.content.pm;
public class ActivityInfo {
    public String packageName;
    public boolean enabled = true, exported = true;
}
""",
    "android/content/pm/PackageManager.java": """
package android.content.pm;
public abstract class PackageManager {
    public static final int PERMISSION_GRANTED = 0, MATCH_DEFAULT_ONLY = 65536;
    public abstract ResolveInfo resolveActivity(android.content.Intent intent, int flags);
}
""",
    "android/content/Intent.java": r'''
package android.content;
import android.net.Uri;
import java.net.URISyntaxException;
import java.util.*;

/** Minimal fixture parser only. Android itself supplies parsing in the built APK. */
public class Intent {
    public static final int URI_INTENT_SCHEME = 1, FLAG_ACTIVITY_NEW_TASK = 0x10000000;
    private String pkg;
    private ComponentName component;
    private Intent selector;
    private Uri data;
    private int flags;
    private Object clip = new Object();
    public final Map<String,String> extras = new HashMap<>();
    public static Intent parseUri(String original, int mode) throws URISyntaxException {
        Intent out = new Intent();
        if (original.contains("#Intent;")) {
            if (!original.endsWith(";end")) throw new URISyntaxException(original, "fixture invalid");
            String scheme = null;
            for (String field : original.substring(original.indexOf("#Intent;") + 8).split(";")) {
                if (field.startsWith("scheme=")) scheme = field.substring(7);
                else if (field.startsWith("package=")) out.pkg = field.substring(8);
                else if (field.startsWith("component=")) {
                    String value = field.substring(10);
                    out.component = new ComponentName(value.substring(0, value.indexOf('/')));
                }
                else if (field.equals("SEL")) out.selector = new Intent();
                else if (field.startsWith("launchFlags=")) out.flags = Integer.decode(field.substring(12));
                else if (field.startsWith("S.")) {
                    int equals = field.indexOf('=');
                    out.extras.put(field.substring(2, equals), field.substring(equals+1));
                }
            }
            String base = original.substring(0, original.indexOf("#Intent;"));
            if (base.startsWith("intent:") && scheme != null) base = scheme + base.substring(6);
            if (!base.equals("intent:")) out.data = Uri.parse(base);
        } else {
            new java.net.URI(original);
            out.data = Uri.parse(original);
        }
        return out;
    }
    public Intent getSelector() { return selector; }
    public ComponentName getComponent() { return component; }
    public String getPackage() { return pkg; }
    public Uri getData() { return data; }
    public void setClipData(Object clip) { this.clip = clip; }
    public Object getClipData() { return clip; }
    public void removeExtra(String name) { extras.remove(name); }
    public Intent setPackage(String pkg) { this.pkg = pkg; return this; }
    public Intent setFlags(int flags) { this.flags = flags; return this; }
    public int getFlags() { return flags; }
}
''',
    "android/net/Uri.java": """
package android.net;
public class Uri {
    private final String text;
    private Uri(String text) { this.text = text; }
    public static Uri parse(String text) { return new Uri(text); }
    public String getScheme() { int at = text.indexOf(':'); return at < 0 ? null : text.substring(0,at); }
    public String toString() { return text; }
}
""",
    "android/database/Cursor.java": """
package android.database;
public interface Cursor extends AutoCloseable {
    int FIELD_TYPE_NULL = 0, FIELD_TYPE_INTEGER = 1, FIELD_TYPE_FLOAT = 2,
        FIELD_TYPE_STRING = 3, FIELD_TYPE_BLOB = 4;
    int getColumnIndex(String name);
    boolean isNull(int index);
    int getType(int index);
    String getString(int index);
    long getLong(int index);
    void close();
    boolean moveToNext();
}
""",
    "android/database/ContentObserver.java": """
package android.database;
public abstract class ContentObserver {
    public ContentObserver(android.os.Handler handler) {}
    public void onChange(boolean selfChange) {}
    public void onChange(boolean selfChange, android.net.Uri uri) { onChange(selfChange); }
}
""",
    "android/content/ContentResolver.java": """
package android.content;
public abstract class ContentResolver {
    public abstract android.database.Cursor query(android.net.Uri uri, String[] projection,
        String selection, String[] args, String sort);
    public void registerContentObserver(android.net.Uri uri, boolean descendants, android.database.ContentObserver observer) {
        throw new UnsupportedOperationException();
    }
    public void unregisterContentObserver(android.database.ContentObserver observer) {
        throw new UnsupportedOperationException();
    }
}
""",
    "android/media/tv/TvContract.java": """
package android.media.tv;
public class TvContract {
    public static class WatchNextPrograms {
        public static final android.net.Uri CONTENT_URI =
            android.net.Uri.parse("content://android.media.tv/watch_next_program");
        public static final int WATCH_NEXT_TYPE_CONTINUE = 0, WATCH_NEXT_TYPE_NEXT = 1;
    }
}
""",
    "android/os/Looper.java": """
package android.os;
public class Looper {
    public static final Thread UI = Thread.currentThread();
    private static final Looper MAIN = new Looper();
    public static Looper getMainLooper() { return MAIN; }
    public static Looper myLooper() { return Thread.currentThread() == UI ? MAIN : null; }
}
""",
    "android/os/Handler.java": """
package android.os;
public class Handler {
    public Handler(Looper looper) {}
    public boolean post(Runnable command) { throw new AssertionError("Use injected callback executor in tests"); }
}
""",
}

HARNESS = r'''
package io.cleanyourtv.ui;

import android.content.*;
import android.content.pm.*;
import android.database.Cursor;
import android.database.SQLException;
import android.net.Uri;
import android.util.Log;
import java.util.*;
import java.util.concurrent.*;

public final class ContinueWatchingTest {
    static final String PKG = "com.example.player";
    static final String ORIGINAL = "intent://resume/42#Intent;scheme=player;package=" + PKG
        + ";launchFlags=0x140000c3;S.playback_token=private-fixture;S.browser_fallback_url=browser-fixture;end";

    static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
    static boolean logged(String part) {
        for (String line : Log.entries) if (line.contains(part)) return true;
        return false;
    }
    static Map<String,Object> row(long id) {
        Map<String,Object> fields = new LinkedHashMap<>();
        fields.put("_id", id); fields.put("package_name", PKG); fields.put("title", "Same show");
        fields.put("watch_next_type", 0L); fields.put("intent_uri", ORIGINAL);
        return fields;
    }
    static Map<String,Object> with(Map<String,Object> fields, String key, Object value) {
        fields.put(key,value); return fields;
    }
    static final class Rows implements Cursor {
        final List<Map<String,Object>> rows;
        final List<String> columns = new ArrayList<>();
        int index = -1;
        boolean closed, failMove, failClose;
        Rows(List<Map<String,Object>> rows) {
            this.rows = rows;
            Set<String> names = new LinkedHashSet<>();
            for (Map<String,Object> row : rows) names.addAll(row.keySet());
            columns.addAll(names);
        }
        Object value(int i) { return rows.get(index).get(columns.get(i)); }
        public int getColumnIndex(String name) { return columns.indexOf(name); }
        public boolean isNull(int i) { return value(i) == null; }
        public int getType(int i) {
            Object value = value(i);
            return value == null ? 0 : value instanceof String ? 3 : value instanceof byte[] ? 4
                : value instanceof Double ? 2 : 1;
        }
        public String getString(int i) { return String.valueOf(value(i)); }
        public long getLong(int i) { return ((Number)value(i)).longValue(); }
        public boolean moveToNext() {
            if (failMove && index == 0) throw new SQLException("private-fixture");
            return ++index < rows.size();
        }
        public void close() {
            closed = true;
            if (failClose) throw new IllegalStateException("private-fixture");
        }
    }
    static final class Packages extends PackageManager {
        boolean available = true, enabled = true, exported = true;
        String resolvedPackage = PKG;
        int calls;
        RuntimeException failure;
        public ResolveInfo resolveActivity(Intent intent, int flags) {
            calls++;
            if (failure != null) throw failure;
            check(flags == MATCH_DEFAULT_ONLY, "normal activity resolution");
            if (!available) return null;
            ResolveInfo resolved = new ResolveInfo();
            resolved.activityInfo = new ActivityInfo();
            resolved.activityInfo.packageName = resolvedPackage;
            resolved.activityInfo.enabled = enabled;
            resolved.activityInfo.exported = exported;
            return resolved;
        }
    }
    static class App extends Context {
        final Packages packages = new Packages();
        Rows rows;
        boolean granted = true;
        int queries, launches;
        RuntimeException queryFailure, launchFailure;
        Intent launched;
        App(List<Map<String,Object>> fields) { rows = fields == null ? null : new Rows(fields); }
        public Context getApplicationContext() { return this; }
        public PackageManager getPackageManager() { return packages; }
        public int checkSelfPermission(String permission) { return granted ? 0 : -1; }
        public ContentResolver getContentResolver() {
            return new ContentResolver() {
                public Cursor query(Uri uri, String[] projection, String selection, String[] args, String sort) {
                    queries++;
                    check(uri.toString().equals("content://android.media.tv/watch_next_program"), "only Watch Next");
                    check(projection == null && selection == null && args == null && sort == null, "no SQL filters");
                    check(Thread.currentThread() != android.os.Looper.UI, "query off UI thread");
                    if (queryFailure != null) throw queryFailure;
                    if (rows != null) { rows.index = -1; rows.closed = false; }
                    return rows;
                }
            };
        }
        public void startActivity(Intent intent) {
            if (launchFailure != null) throw launchFailure;
            launches++; launched = intent;
        }
    }
    static ContinueWatchingSource.Result load(App app) throws Exception {
        ExecutorService worker = Executors.newSingleThreadExecutor();
        try {
            ContinueWatchingSource.Result result = worker.submit(() -> new TvProviderWatchNextSource(app).load()).get();
            if (app.queries > 0 && app.rows != null && app.queryFailure == null) check(app.rows.closed, "cursor closed");
            return result;
        } finally { worker.shutdownNow(); }
    }

    static void metadata() throws Exception {
        Map<String,Object> fields = row(42);
        fields.put("package_name","com.google.android.youtube.tv");
        fields.put("intent_uri","https://example.invalid/play/42");
        fields.put("last_playback_position_millis",808000L);
        fields.put("duration_millis",1429000L);
        fields.put("last_engagement_time_utc_millis",123456789L);
        fields.put("poster_art_uri","https://example.invalid/poster.jpg");
        fields.put("browsable",1L); fields.put("searchable",1L); fields.put("live",0L);
        App app = new App(Collections.singletonList(fields));
        app.packages.resolvedPackage = "com.google.android.youtube.tv";
        ContinueWatchingSource.Result result = load(app);
        check(result.status == ContinueWatchingSource.Status.OK && result.items.size() == 1, "actual TV fixture");
        ContinueWatchingItem item = result.items.get(0);
        check(item.canContinue(), "YouTube qualifies without content ID, episode or TMDB ID");
        check(Math.abs(item.progress() * 100 - 56.54303708887334) < 0.0001, "actual progress 56.5%");
        check(item.playbackPositionMillis == 808000L && item.durationMillis == 1429000L, "raw times");
        check(item.lastEngagementTimeMillis == 123456789L && item.seasonDisplayNumber == null, "engagement/absence");
        check(item.stableId.equals("tvprovider:watch_next:com.google.android.youtube.tv:42"), "namespaced identity");
        check(item.originalPlaybackIntent.equals(fields.get("intent_uri")), "exact original intent");
        check(app.launches == 0, "data loading never starts playback");
        try { result.items.clear(); throw new AssertionError("mutable result"); }
        catch (UnsupportedOperationException expected) {}
        boolean blocked = false;
        try { new TvProviderWatchNextSource(app).load(); }
        catch (IllegalStateException expected) { blocked = true; }
        check(blocked, "source rejects UI-thread access");
    }

    static ContinueWatchingItem item(Long position, Long duration) {
        return new ContinueWatchingItem(42,"Show",null,PKG,ORIGINAL,null,null,position,duration,null,
            null,null,null,null,ContinueWatchingItem.ContinuationKind.CONTINUE,
            ContinueWatchingItem.PlaybackCapability.VALID_PLAYBACK,null,null,null);
    }
    static void progress() {
        check(item(null,100L).progress() == null && item(10L,null).progress() == null, "missing unknown");
        check(item(-1L,100L).progress() == null && item(0L,0L).progress() == null
            && item(1L,-100L).progress() == null, "invalid unknown");
        check(item(0L,100L).progress() == 0d, "known zero");
        check(item(100L,100L).progress() == 1d && item(200L,100L).progress() == 1d, "clamped completion");
        check(item(Long.MAX_VALUE,1L).progress() == 1d, "no overflow");
        check(item(200L,100L).playbackPositionMillis == 200L, "raw position not clamped");
    }

    static void malformed() throws Exception {
        List<Map<String,Object>> fields = new ArrayList<>();
        fields.add(row(1)); // No optional columns is valid.
        Map<String,Object> optional = row(2);
        optional.put("season_display_number","Specials"); optional.put("episode_display_number","Finale A");
        optional.put("poster_art_uri","content://provider/poster/2");
        optional.put("thumbnail_uri","android.resource://com.example.player/drawable/thumb");
        optional.put("last_playback_position_millis","bad-private-fixture");
        optional.put("duration_millis","999999999999999999999999999");
        optional.put("last_engagement_time_utc_millis","12000");
        optional.put("short_description",""); optional.put("long_description","Synopsis");
        fields.add(optional);
        fields.add(with(row(3),"last_playback_position_millis",3.5d));
        fields.add(with(row(4),"type",Long.MAX_VALUE));
        fields.add(with(row(5),"browsable","not-a-boolean"));
        fields.add(with(row(6),"live",2L));
        fields.add(with(row(7),"searchable","bad"));
        fields.add(with(row(0),"title","Show"));
        fields.add(with(row(-1),"title","Show"));
        fields.add(with(row(8),"_id","broken"));
        fields.add(with(row(9),"title"," \t "));
        fields.add(with(row(10),"package_name"," "));
        ContinueWatchingSource.Result result = load(new App(fields));
        check(result.items.size() == 4, "invalid required data and malformed flags skipped");
        check(result.items.get(0).canContinue(), "missing optional fields accepted");
        ContinueWatchingItem value = result.items.get(1);
        check(value.progress() == null && value.playbackPositionMillis == null && value.durationMillis == null,
            "malformed progress becomes unknown");
        check(value.lastEngagementTimeMillis == 12000L, "numeric-string timestamp");
        check(value.seasonDisplayNumber.equals("Specials") && value.episodeDisplayNumber.equals("Finale A"),
            "provider display strings not forced to integers");
        check(value.posterUri.startsWith("content://") && value.thumbnailUri.startsWith("android.resource://"),
            "native artwork retained");
        check(value.description.equals("Synopsis"), "description fallback");
        check(result.items.get(2).progress() == null && result.items.get(3).type == null, "float/overflow not truncated");
        check(logged("malformed Watch Next column"), "malformed metadata visible");
        check(!logged("bad-private-fixture"), "malformed values not logged");
    }

    static void failures() throws Exception {
        App app = new App(Collections.singletonList(row(1)));
        app.granted = false;
        check(load(app).status == ContinueWatchingSource.Status.PERMISSION_DENIED && app.queries == 0, "preflight denial");
        app.granted = true;
        RuntimeException[] errors = {new SecurityException("private-fixture"),
            new UnsupportedOperationException("private-fixture"), new IllegalArgumentException("private-fixture"),
            new SQLException("private-fixture"), new IllegalStateException("private-fixture")};
        ContinueWatchingSource.Status[] statuses = {ContinueWatchingSource.Status.PERMISSION_DENIED,
            ContinueWatchingSource.Status.UNAVAILABLE,ContinueWatchingSource.Status.UNAVAILABLE,
            ContinueWatchingSource.Status.ERROR,ContinueWatchingSource.Status.ERROR};
        for (int i=0;i<errors.length;i++) {
            app.queryFailure = errors[i];
            ContinueWatchingSource.Result result = load(app);
            check(result.status == statuses[i] && result.items.isEmpty(), "explicit recoverable query error");
        }
        app.queryFailure = null; app.rows.failMove = true;
        check(load(app).status == ContinueWatchingSource.Status.ERROR, "no partial iteration success");
        app.rows.failMove = false; app.rows.failClose = true;
        check(load(app).items.isEmpty(), "no partial close success");
        app = new App(null);
        check(load(app).status == ContinueWatchingSource.Status.UNAVAILABLE, "null not empty success");
        check(!logged("private-fixture"), "no exception messages/tokens");
    }

    static void playback() throws Exception {
        Packages packages = new Packages();
        ContinueWatchingPlayback player = new ContinueWatchingPlayback(packages);
        Intent safe = player.prepare(ORIGINAL,PKG);
        check(safe != null && safe.getPackage().equals(PKG), "pinned original package");
        check(safe.getFlags() == Intent.FLAG_ACTIVITY_NEW_TASK, "all URI grants and task flags stripped");
        check(safe.getClipData() == null && !safe.extras.containsKey("browser_fallback_url"), "clip/fallback stripped");
        check(safe.extras.get("playback_token").equals("private-fixture"), "resume extras retained");
        String[] invalid = {
            "intent://x#Intent;package=com.other.player;end",
            "intent://x#Intent;component=com.other.player/.Play;end",
            "intent://x#Intent;SEL;package=com.example.player;end",
            "file:///private", "javascript:alert(1)", "data:text/html,fixture",
            "intent://x#Intent;scheme=FILE;end",
            "intent://x#Intent;broken", "http://[broken", "intent:#Intent;end", "relative/path", ""};
        for (String uri : invalid) check(player.prepare(uri,PKG) == null, "unsafe URI rejected");
        check(player.prepare(ORIGINAL,"bad:package") == null, "invalid package");
        check(player.prepare("intent:#Intent;component="+PKG+"/.Play;end",PKG) != null,
            "same-package explicit activity allowed");
        check(player.resolves(safe,PKG), "resolvable");
        packages.resolvedPackage = "com.other.player";
        check(!player.resolves(safe,PKG), "resolution package checked");
        packages.resolvedPackage = PKG; packages.exported = false;
        check(!player.resolves(safe,PKG), "unexported not usable");
        packages.exported = true; packages.enabled = false;
        check(!player.resolves(safe,PKG), "disabled not usable");
        App app = new App(Collections.emptyList());
        player = new ContinueWatchingPlayback(app.packages);
        check(player.launch(app,item(1L,2L)) == ContinueWatchingPlayback.LaunchResult.STARTED
            && app.launches == 1, "launch original only");
        app.packages.available = false;
        check(player.launch(app,item(1L,2L)) == ContinueWatchingPlayback.LaunchResult.UNAVAILABLE
            && app.launches == 1, "no browser/app-home success fallback");
        app.packages.available = true; app.launchFailure = new ActivityNotFoundException();
        check(player.launch(app,item(1L,2L)) == ContinueWatchingPlayback.LaunchResult.UNAVAILABLE, "launch race");
        app.launchFailure = new SecurityException("private-fixture");
        check(player.launch(app,item(1L,2L)) == ContinueWatchingPlayback.LaunchResult.FAILED, "launch denial");
        app.packages.failure = new SecurityException("private-fixture");
        check(!player.resolves(safe,PKG), "resolution denial");
        check(!logged("private-fixture") && !logged("browser-fixture"), "never log URI/extras/messages");
    }

    static final class ManualIo extends AbstractExecutorService {
        final Deque<Runnable> tasks = new ArrayDeque<>();
        boolean stopped;
        public void execute(Runnable work) { tasks.add(work); }
        public void shutdown() { stopped = true; }
        public List<Runnable> shutdownNow() { stopped = true; tasks.clear(); return Collections.emptyList(); }
        public boolean isShutdown() { return stopped; }
        public boolean isTerminated() { return stopped; }
        public boolean awaitTermination(long timeout, TimeUnit unit) { return stopped; }
        void next() throws Exception {
            Runnable task = tasks.removeFirst();
            Thread worker = new Thread(task, "fixture-io");
            worker.start(); worker.join();
        }
    }
    static final class MainQueue implements Executor {
        final Deque<Runnable> tasks = new ArrayDeque<>();
        public void execute(Runnable work) { tasks.add(work); }
        void next() { tasks.removeFirst().run(); }
        void newest() { tasks.removeLast().run(); }
    }

    static void repository() throws Exception {
        List<Map<String,Object>> fields = new ArrayList<>();
        fields.add(with(row(1),"last_engagement_time_utc_millis",10L));
        fields.add(with(row(2),"last_engagement_time_utc_millis",20L));
        fields.add(with(row(2),"last_engagement_time_utc_millis",20L)); // Same identity only.
        fields.add(with(with(with(row(2),"package_name","com.other.player"),
            "intent_uri",ORIGINAL.replace(PKG,"com.other.player")),"last_engagement_time_utc_millis",30L));
        fields.add(with(with(row(3),"watch_next_type",1L),"last_engagement_time_utc_millis",25L));
        fields.add(with(row(4),"watch_next_type",2L));
        fields.add(with(row(5),"watch_next_type",3L));
        fields.add(with(row(6),"watch_next_type",null));
        fields.add(with(row(7),"live",1L));
        fields.add(with(row(8),"browsable",0L));
        fields.add(with(row(9),"intent_uri","file:///fixture"));
        fields.add(with(row(10),"intent_uri","intent://x#Intent;package=com.other.player;end"));
        fields.add(row(11)); // Unknown recency/progress still qualifies.
        fields.add(with(row(12),"last_engagement_time_utc_millis",20L)); // Deterministic tie.
        fields.add(with(with(row(13),"watch_next_type",1L),"live",1L));
        fields.add(with(with(row(14),"watch_next_type",1L),"browsable",0L));
        fields.add(with(with(row(15),"watch_next_type",1L),"intent_uri",null));
        fields.add(with(row(16),"watch_next_type",99L));
        // Resolve each pinned package without an application allowlist.
        App app = new App(fields) {
            @Override public PackageManager getPackageManager() {
                return new PackageManager() {
                    public ResolveInfo resolveActivity(Intent intent, int flags) {
                        ResolveInfo info = new ResolveInfo();
                        info.activityInfo = new ActivityInfo();
                        info.activityInfo.packageName = intent.getPackage();
                        return info;
                    }
                };
            }
        };
        ContinueWatchingSource.Result nativeRows = load(app);
        check(nativeRows.items.stream().anyMatch(i -> i.continuationKind == ContinueWatchingItem.ContinuationKind.NEXT),
            "NEXT preserved by source");
        ManualIo io = new ManualIo(); MainQueue main = new MainQueue();
        ContinueWatchingRepository repository = new ContinueWatchingRepository(() -> nativeRows,io,main);
        int[] changes = {0};
        ContinueWatchingRepository.Listener listener = () -> changes[0]++;
        repository.addListener(listener); repository.addListener(listener);
        check(repository.current().status == ContinueWatchingSource.Status.NOT_LOADED, "explicit initial state");
        repository.refresh(); check(io.tasks.isEmpty(), "no loading in background");
        repository.onForeground(); repository.onForeground(); check(io.tasks.size()==1, "one foreground refresh");
        io.next(); main.next();
        List<ContinueWatchingItem> items = repository.current().items;
        check(items.size()==6, "qualified CONTINUE and NEXT identities retained; other kinds and invalid rows excluded");
        check(items.get(0).providerPackage.equals("com.other.player"), "same title/row, other package survives");
        check(items.get(1).providerRowId==3
            && items.get(1).continuationKind==ContinueWatchingItem.ContinuationKind.NEXT, "NEXT ordered by engagement");
        check(items.get(2).providerRowId==12 && items.get(3).providerRowId==2, "stable tie by identity");
        check(items.get(4).providerRowId==1 && items.get(5).providerRowId==11, "recency descending; unknown last");
        check(changes[0]==1, "deduplicated listener");
        repository.onBackground(); repository.onForeground(); io.next(); main.next();
        check(changes[0]==2, "foreground refresh rather than polling");
        repository.removeListener(listener); repository.close();
        check(io.isShutdown() && repository.current().items.isEmpty(), "screen teardown releases work/state");
    }

    static final class ObservedResolver extends ContentResolver {
        android.database.ContentObserver observer;
        int registrations, removals;
        RuntimeException registerFailure, removeFailure;
        public Cursor query(Uri uri, String[] projection, String selection, String[] args, String sort) {
            throw new AssertionError("Repository must use the source, not query the resolver itself");
        }
        public void registerContentObserver(Uri uri, boolean descendants, android.database.ContentObserver observer) {
            registrations++;
            check(uri.toString().equals("content://android.media.tv/watch_next_program") && descendants,
                "observe Watch Next and row changes only");
            if (registerFailure != null) throw registerFailure;
            this.observer = observer;
        }
        public void unregisterContentObserver(android.database.ContentObserver observer) {
            removals++;
            check(this.observer == observer,"unregister exact observer");
            if (removeFailure != null) throw removeFailure;
        }
    }

    static void notifications() throws Exception {
        ManualIo io = new ManualIo(); MainQueue main = new MainQueue();
        ObservedResolver resolver = new ObservedResolver();
        ContinueWatchingSource.Result[] answer = {new ContinueWatchingSource.Result(
            ContinueWatchingSource.Status.OK,Collections.singletonList(item(1L,2L)))};
        ContinueWatchingRepository repository = new ContinueWatchingRepository(() -> answer[0],io,main,() -> 1L,resolver);
        check(resolver.registrations==0,"no observation before foreground");
        repository.onForeground(); repository.onForeground();
        check(resolver.registrations==1 && io.tasks.size()==1,"one observer and initial foreground load");
        io.next(); // Old result is waiting on main when the provider changes.
        answer[0] = new ContinueWatchingSource.Result(ContinueWatchingSource.Status.OK,
            Collections.singletonList(item(3L,4L)));
        resolver.observer.onChange(false);
        resolver.observer.onChange(false,Uri.parse("content://android.media.tv/watch_next_program/42"));
        resolver.observer.onChange(false);
        check(main.tasks.size()==2,"notification burst queues one reload, alongside the old response");
        main.next();
        check(repository.current().status==ContinueWatchingSource.Status.NOT_LOADED,"notification invalidates posted old result immediately");
        main.next();
        check(io.tasks.size()==1,"one background reload for burst");
        io.next(); main.next();
        check(repository.current().items.get(0).playbackPositionMillis==3L,"changed provider data delivered");
        resolver.observer.onChange(false);
        repository.onBackground();
        check(resolver.removals==1,"observer removed on pause");
        main.next();
        resolver.observer.onChange(false);
        check(io.tasks.isEmpty() && main.tasks.isEmpty(),"queued or late notifications cannot load while backgrounded");
        answer[0] = ContinueWatchingSource.Result.empty(ContinueWatchingSource.Status.OK);
        repository.onForeground(); io.next(); main.next();
        check(resolver.registrations==2 && repository.current().items.isEmpty(),"resume registers again and picks up removals");
        resolver.observer.onChange(false);
        repository.close(); repository.close();
        main.next();
        resolver.observer.onChange(false);
        check(resolver.removals==2 && io.isShutdown() && main.tasks.isEmpty(),"close unregisters once and ignores pending/late changes");
    }

    static void notificationFailures() throws Exception {
        ManualIo io = new ManualIo(); MainQueue main = new MainQueue();
        ObservedResolver resolver = new ObservedResolver();
        resolver.registerFailure = new SecurityException("private-fixture");
        ContinueWatchingRepository repository = new ContinueWatchingRepository(
            () -> ContinueWatchingSource.Result.empty(ContinueWatchingSource.Status.OK),io,main,() -> 1L,resolver);
        repository.onForeground(); io.next(); main.next();
        check(repository.current().status==ContinueWatchingSource.Status.OK,"observer denial does not break foreground query");
        check(logged("change notifications unavailable (SecurityException)"),"observer failure explicit");
        repository.onBackground();
        check(resolver.removals==0,"failed registration is not unregistered");
        resolver.registerFailure = null;
        repository.onForeground(); io.next(); main.next();
        check(resolver.registrations==2,"registration can recover on next foreground");
        resolver.removeFailure = new IllegalStateException("private-fixture");
        repository.onBackground();
        check(logged("could not unregister change notifications (IllegalStateException)"),"unregister failure explicit");
        resolver.observer.onChange(false);
        check(io.tasks.isEmpty() && main.tasks.isEmpty(),"late notification after failed unregister cannot reload");
        repository.close();
        check(!logged("private-fixture"),"observer failures never log exception details or provider data");
    }

    static void filters() throws Exception {
        long day = 24L * 60 * 60 * 1000, window = 30 * day;
        long[] now = {1800000000000L};
        Long[][] values = {
            {now[0],0L,100L},
            {now[0]-window,95L,100L},
            {now[0]-window-1,null,100L},
            {now[0],96L,100L},
            {null,null,null},
            {0L,20L,100L},
            {-1L,20L,100L},
            {now[0],20L,0L},
            {now[0],null,100L},
            {now[0],98L,100L},
            {now[0],200L,100L},
            {now[0],-1L,100L},
            {now[0],99L,null},
            {now[0]+day,50L,100L}
        };
        List<Map<String,Object>> fields = new ArrayList<>();
        for (int i=0;i<values.length;i++) {
            Map<String,Object> field = row(i+1);
            field.put("last_engagement_time_utc_millis",values[i][0]);
            field.put("last_playback_position_millis",values[i][1]);
            field.put("duration_millis",values[i][2]);
            if (i==8 || i==9) field.put("watch_next_type",1L);
            fields.add(field);
        }
        fields.add(with(with(with(row(4),"last_engagement_time_utc_millis",now[0]-1000),
            "last_playback_position_millis",80L),"duration_millis",100L));
        ContinueWatchingSource.Result nativeRows = load(new App(fields));
        ManualIo io = new ManualIo(); MainQueue main = new MainQueue();
        ContinueWatchingRepository repository = new ContinueWatchingRepository(() -> nativeRows,io,main,() -> now[0]);
        repository.onForeground(); io.next(); main.next();
        check(repository.current().items.size()==14,"filters default off");
        repository.setFilters(true,true); io.next(); main.next();
        Set<Long> ids = new HashSet<>();
        for (ContinueWatchingItem item : repository.current().items) ids.add(item.providerRowId);
        check(ids.equals(new HashSet<>(Arrays.asList(1L,2L,5L,6L,7L,8L,9L,12L,13L,14L))),
            "strict boundaries; unknowns and NEXT kept; completed newest record cannot revive an older duplicate");
        check(nativeRows.items.get(10).playbackPositionMillis==200L,"filter leaves raw provider progress unchanged");
        repository.setFilters(true,false); io.next(); main.next();
        check(repository.current().items.size()==13,"age filter independent; excludes old even with unknown progress");
        repository.setFilters(false,true); io.next(); main.next();
        check(repository.current().items.size()==11,"completion filter independent; includes old items when age filter off");
        repository.setFilters(false,false); io.next(); main.next();
        check(repository.current().items.size()==14,"disabling filters restores source items");
        repository.onBackground();
        repository.setFilters(true,true);
        check(io.tasks.isEmpty(),"filter changes do not query in background");
        now[0]+=day;
        repository.onForeground(); io.next(); main.next();
        check(repository.current().items.size()==9,"clock reevaluated on return; former cutoff item expires");
        repository.setFilters(true,true);
        check(io.tasks.isEmpty(),"unchanged options do not trigger another query");
        repository.setFilters(false,false); io.next();
        repository.setFilters(true,true); io.next();
        main.newest(); main.next();
        check(repository.current().items.size()==9,"stale responses from previous filter options cannot replace new results");
        repository.close();
    }

    static void stale() throws Exception {
        ManualIo io = new ManualIo(); MainQueue main = new MainQueue();
        ContinueWatchingSource.Result[] answer = {new ContinueWatchingSource.Result(
            ContinueWatchingSource.Status.OK,Collections.singletonList(item(1L,2L)))};
        ContinueWatchingRepository repository = new ContinueWatchingRepository(() -> answer[0],io,main);
        int[] changes = {0}; repository.addListener(() -> changes[0]++);
        repository.onForeground(); io.next(); // Old result waits on main.
        answer[0] = ContinueWatchingSource.Result.empty(ContinueWatchingSource.Status.PERMISSION_DENIED);
        repository.refresh(); io.next();
        main.newest(); main.next();
        check(repository.current().status == ContinueWatchingSource.Status.PERMISSION_DENIED
            && repository.current().items.isEmpty() && changes[0]==1, "old result cannot replace latest failure");
        repository.refresh(); io.next(); repository.onBackground(); main.next();
        check(changes[0]==1, "backgrounded response ignored");
        repository.onForeground(); io.next(); repository.close(); main.next();
        check(changes[0]==1, "closed response ignored");
        io = new ManualIo(); main = new MainQueue();
        repository = new ContinueWatchingRepository(() -> {throw new IllegalStateException("private-fixture");},io,main);
        repository.onForeground(); io.next(); main.next();
        check(repository.current().status == ContinueWatchingSource.Status.ERROR
            && repository.current().items.isEmpty(), "source failure explicitly recoverable");
        repository.close();
        check(!logged("private-fixture"), "source exception message withheld");
    }

    public static void main(String[] args) throws Exception {
        android.os.Looper.getMainLooper(); // Establish fixture UI thread before a worker accesses Looper.
        switch(args[0]) {
            case "metadata": metadata(); break;
            case "progress": progress(); break;
            case "malformed": malformed(); break;
            case "failures": failures(); break;
            case "playback": playback(); break;
            case "repository": repository(); break;
            case "filters": filters(); break;
            case "notifications": notifications(); break;
            case "notificationFailures": notificationFailures(); break;
            case "stale": stale(); break;
            default: throw new AssertionError("Unknown test");
        }
    }
}
'''


class ContinueWatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        home = os.environ.get("JAVA_HOME")
        javac = str(Path(home) / "bin/javac") if home else shutil.which("javac")
        cls.java = str(Path(home) / "bin/java") if home else shutil.which("java")
        if not javac or not cls.java:
            raise unittest.SkipTest("JDK required for Continue Watching Java tests")
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name)
        sources = [str(JAVA / name) for name in (
            "ContinueWatchingItem.java", "ContinueWatchingSource.java", "ContinueWatchingPlayback.java",
            "TvProviderWatchNextSource.java", "ContinueWatchingRepository.java", "AppLog.java",
        )]
        for name, text in {**STUBS, "io/cleanyourtv/ui/ContinueWatchingTest.java": HARNESS}.items():
            path = cls.directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            sources.append(str(path))
        result = subprocess.run(
            [javac, "--release", "8", "-encoding", "UTF-8", "-d", str(cls.directory), *sources],
            capture_output=True, text=True,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def scenario(self, name):
        result = subprocess.run(
            [self.java, "-cp", str(self.directory), "io.cleanyourtv.ui.ContinueWatchingTest", name],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_actual_tv_metadata_and_thread_boundary(self):
        self.scenario("metadata")

    def test_raw_and_derived_progress(self):
        self.scenario("progress")

    def test_missing_malformed_metadata_and_native_artwork(self):
        self.scenario("malformed")

    def test_recoverable_provider_failures(self):
        self.scenario("failures")

    def test_original_intent_validation_and_launch_outcomes(self):
        self.scenario("playback")

    def test_qualification_recency_identity_and_foreground_refresh(self):
        self.scenario("repository")

    def test_stale_and_background_results_cannot_replace_current_state(self):
        self.scenario("stale")

    def test_optional_age_and_completion_filters_boundaries_unknowns_and_refresh(self):
        self.scenario("filters")

    def test_foreground_change_notifications_coalescing_stale_results_and_cleanup(self):
        self.scenario("notifications")

    def test_change_observer_failures_preserve_foreground_loading_and_recover(self):
        self.scenario("notificationFailures")


if __name__ == "__main__":
    unittest.main()
