"""Execute the UI diagnostic against fake Android cursors; no TV or Android runtime required."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "launcher-ui/app/src/io/cleanyourtv/ui/TvProviderDiagnostic.java"
ANDROID = "{http://schemas.android.com/apk/res/android}"

STUBS = {
    "android/content/Context.java": """
package android.content;
public abstract class Context {
    public abstract ContentResolver getContentResolver();
    public abstract android.content.pm.PackageManager getPackageManager();
    public abstract int checkSelfPermission(String permission);
    public String getPackageName() { return "io.cleanyourtv.ui"; }
}
""",
    "android/content/ContentResolver.java": """
package android.content;
public abstract class ContentResolver {
    public abstract android.database.Cursor query(android.net.Uri uri, String[] projection,
        String selection, String[] args, String sort);
}
""",
    "android/content/Intent.java": """
package android.content;
public class Intent {
    public static final String ACTION_MAIN = "android.intent.action.MAIN";
    public static final String CATEGORY_LEANBACK_LAUNCHER = "android.intent.category.LEANBACK_LAUNCHER";
    public Intent(String action) {}
    public Intent addCategory(String category) { return this; }
}
""",
    "android/content/pm/PackageManager.java": """
package android.content.pm;
public abstract class PackageManager {
    public static final int PERMISSION_GRANTED = 0;
    public abstract java.util.List<ResolveInfo> queryIntentActivities(android.content.Intent intent, int flags);
}
""",
    "android/content/pm/ResolveInfo.java": """
package android.content.pm;
public class ResolveInfo { public ActivityInfo activityInfo; }
""",
    "android/content/pm/ActivityInfo.java": """
package android.content.pm;
public class ActivityInfo { public String packageName; }
""",
    "android/database/Cursor.java": """
package android.database;
public interface Cursor extends AutoCloseable {
    int FIELD_TYPE_NULL = 0, FIELD_TYPE_INTEGER = 1, FIELD_TYPE_FLOAT = 2,
        FIELD_TYPE_STRING = 3, FIELD_TYPE_BLOB = 4;
    String[] getColumnNames();
    boolean moveToNext();
    int getType(int column);
    String getString(int column);
    long getLong(int column);
    double getDouble(int column);
    byte[] getBlob(int column);
    void close();
}
""",
    "android/database/SQLException.java": """
package android.database;
public class SQLException extends RuntimeException {
    public SQLException(String message) { super(message); }
}
""",
    "android/net/Uri.java": """
package android.net;
public final class Uri {
    private final String value;
    private Uri(String value) { this.value = value; }
    public static Uri parse(String value) { return new Uri(value); }
    public String toString() { return value; }
}
""",
    "android/media/tv/TvContract.java": """
package android.media.tv;
public final class TvContract {
    public static class WatchNextPrograms {
        public static final android.net.Uri CONTENT_URI =
            android.net.Uri.parse("content://android.media.tv/watch_next_program");
    }
    public static class PreviewPrograms {
        public static final android.net.Uri CONTENT_URI =
            android.net.Uri.parse("content://android.media.tv/preview_program");
    }
    public static class Channels {
        public static final android.net.Uri CONTENT_URI =
            android.net.Uri.parse("content://android.media.tv/channel");
    }
}
""",
    "android/os/Build.java": """
package android.os;
public class Build { public static class VERSION { public static final int SDK_INT = 28; } }
""",
    "android/os/Process.java": """
package android.os;
public class Process { public static int myUid() { return 10123; } }
""",
    "android/os/SystemClock.java": """
package android.os;
public class SystemClock {
    public static long elapsedRealtimeNanos() { return 123L; }
    public static void sleep(long millis) {
        if (millis != 2) throw new AssertionError("Expected diagnostic log pacing");
    }
}
""",
    "android/os/OperationCanceledException.java": """
package android.os;
public class OperationCanceledException extends RuntimeException {}
""",
    "android/util/Base64.java": """
package android.util;
public class Base64 {
    public static final int NO_WRAP = 2;
    public static String encodeToString(byte[] bytes, int flags) {
        return java.util.Base64.getEncoder().encodeToString(bytes);
    }
}
""",
    "android/util/Log.java": """
package android.util;
public class Log {
    public static final java.util.List<String> entries = new java.util.ArrayList<>();
    public static int i(String tag, String text) { entries.add(text); return 0; }
    public static int e(String tag, String text) { entries.add(text); return 0; }
    public static int e(String tag, String text, Throwable e) {
        entries.add(text + " " + e.getClass().getSimpleName() + ": " + e.getMessage()); return 0;
    }
}
""",
    "org/json/JSONObject.java": r'''
package org.json;
public class JSONObject {
    public static String quote(String text) {
        if (text == null) return "\"\"";
        StringBuilder out = new StringBuilder("\"");
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (c == '"' || c == '\\') out.append('\\').append(c);
            else if (c < 32) out.append(String.format("\\u%04x", (int)c));
            else out.append(c);
        }
        return out.append('"').toString();
    }
}
''',
}

HARNESS = r'''
package io.cleanyourtv.ui;

import android.content.*;
import android.content.pm.*;
import android.database.*;
import android.net.Uri;
import android.util.Log;
import java.nio.charset.StandardCharsets;
import java.util.*;

public final class DiagnosticTest {
    static final Object BAD = new Object();

    static final class Rows implements Cursor {
        final String[] columns;
        final Object[][] rows;
        int at = -1;
        boolean closed, failClose, failMove;
        Rows(String[] columns, Object[][] rows) { this.columns = columns; this.rows = rows; }
        public String[] getColumnNames() { return columns; }
        public boolean moveToNext() {
            if (failMove && at == 0) throw new SQLException("cursor fixture failure");
            return ++at < rows.length;
        }
        public int getType(int c) {
            Object v = rows[at][c];
            if (v == BAD) throw new SQLException("field fixture failure");
            return v == null ? 0 : v instanceof byte[] ? 4 : v instanceof String ? 3
                : v instanceof Double ? 2 : 1;
        }
        public String getString(int c) { return rows[at][c] == null ? null : rows[at][c].toString(); }
        public long getLong(int c) { return ((Number)rows[at][c]).longValue(); }
        public double getDouble(int c) { return ((Number)rows[at][c]).doubleValue(); }
        public byte[] getBlob(int c) { return (byte[])rows[at][c]; }
        public void close() {
            closed = true;
            if (failClose) throw new IllegalStateException("close fixture failure");
        }
    }

    static final class Resolver extends ContentResolver {
        final Map<String, Object> results = new HashMap<>();
        final List<String> queried = new ArrayList<>();
        public Cursor query(Uri uri, String[] projection, String selection, String[] args, String sort) {
            check(projection == null && selection == null && args == null && sort == null, "unconstrained queries");
            String name = uri.toString().substring(uri.toString().lastIndexOf('/') + 1);
            queried.add(name);
            Object result = results.get(name);
            if (result instanceof RuntimeException) throw (RuntimeException)result;
            return (Cursor)result;
        }
    }

    static final class App extends Context {
        final Resolver resolver = new Resolver();
        boolean readGranted = true, inventoryDenied;
        App() {
            for (String table : Arrays.asList("watch_next_program", "preview_program", "channel"))
                resolver.results.put(table, new Rows(new String[]{"_id"}, new Object[0][]));
        }
        public ContentResolver getContentResolver() { return resolver; }
        public PackageManager getPackageManager() {
            return new PackageManager() {
                public List<ResolveInfo> queryIntentActivities(Intent intent, int flags) {
                    if (inventoryDenied) throw new SecurityException("inventory fixture denied");
                    List<ResolveInfo> apps = new ArrayList<>();
                    for (int i = 0; i < 2; i++) {
                        ResolveInfo app = new ResolveInfo();
                        app.activityInfo = new ActivityInfo();
                        app.activityInfo.packageName = "com.example.player";
                        apps.add(app);
                    }
                    return apps;
                }
            };
        }
        public int checkSelfPermission(String p) {
            return readGranted && p.equals("android.permission.READ_TV_LISTINGS") ? 0 : -1;
        }
    }

    static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message + "\n" + String.join("\n", Log.entries));
    }
    static boolean has(String text) {
        for (String entry : Log.entries) if (entry.contains(text)) return true;
        return false;
    }
    static void run(App app, boolean raw) {
        Log.entries.clear();
        app.resolver.queried.clear();
        for (Object result : app.resolver.results.values()) {
            if (result instanceof Rows) {
                ((Rows)result).at = -1;
                ((Rows)result).closed = false;
            }
        }
        TvProviderDiagnostic.run(app, raw);
        check(app.resolver.queried.size() == 3, "all three sources attempted");
        for (Object result : app.resolver.results.values())
            if (result instanceof Rows) check(((Rows)result).closed, "cursor closed");
    }

    static void metadata() {
        App app = new App();
        Object[][] rows = new Object[30][];
        for (int i = 0; i < rows.length; i++) rows[i] = new Object[]{
            100L + i, "com.example.other", "Same title", null, 0L, 2400000L,
            "2", "4", 1700000000000L, "https://example.invalid/poster", 0.5d, 1L, "fixture-id"};
        app.resolver.results.put("watch_next_program", new Rows(new String[]{
            "_id", "package_name", "title", "short_description", "last_playback_position_millis",
            "duration_millis", "season_display_number", "episode_display_number",
            "last_engagement_time_utc_millis", "poster_art_uri", "vendor_rating", "searchable",
            "content_id"}, rows));
        run(app, true);
        check(has("READ_TV_LISTINGS=GRANTED ACCESS_ALL_EPG_DATA=DENIED"), "permission report");
        check(has("WATCH_NEXT END status=OK rows_visited=30"), "no row limit or title deduplication");
        check(has("WATCH_NEXT PUBLISHER rows=30 package= \"com.example.other\""), "no app allowlist");
        check(has("column=\"short_description\" type=0 value= null"), "null preserved");
        check(has("column=\"last_playback_position_millis\" type=1 value= 0"), "zero preserved");
        check(has("column=\"vendor_rating\" type=2 value= 0.5"), "unknown float column preserved");
        check(has("column=\"content_id\" type=3 value= \"fixture-id\""), "content identifier");
        check(has("VISIBLE_LEANBACK_APPS count=1"), "app inventory deduplicated only");
        check(has("END status=COMPLETE complete_sources=3/3"), "complete run");
    }

    static void privacy() {
        App app = new App();
        app.resolver.results.put("preview_program", new Rows(
            new String[]{"intent_uri", "poster_art_uri", "vendor_auth", "internal_provider_data", "title"},
            new Object[][]{{"intent://fixture#Intent;S.token=fixture-token;end",
                "https://example.invalid/?token=fixture-token", "fixture-token",
                new byte[]{1,2,3}, "Title\ninjected"}}));
        run(app, false);
        check(!has("fixture-token"), "URLs, intents and known secret columns redacted by default");
        check(has("REDACTED") && has("<BLOB bytes=3"), "redaction explicitly identified");
        for (String entry : Log.entries) check(!entry.contains("\n"), "single-line records");
        run(app, true);
        check(has("fixture-token") && has("base64:AQID"), "explicit raw mode preserves original values");
        check(has("WARNING raw viewing history"), "raw mode warning");
    }

    static void failures() {
        App app = new App();
        app.readGranted = false;
        app.resolver.results.put("watch_next_program", new SecurityException("permission fixture denied"));
        app.resolver.results.put("preview_program", new UnsupportedOperationException("table fixture unsupported"));
        app.resolver.results.put("channel", null);
        run(app, false);
        check(has("READ_TV_LISTINGS=DENIED"), "denied permission reported");
        check(has("WATCH_NEXT END status=SECURITY_EXCEPTION"), "denial not empty success");
        check(has("PREVIEW_PROGRAM END status=UNSUPPORTED"), "unsupported table reported");
        check(has("CHANNEL END status=NULL_CURSOR"), "null cursor not empty success");
        check(has("END status=COMPLETED_WITH_ERRORS complete_sources=0/3"), "failures summarized");
    }

    static void partial() {
        App app = new App();
        Rows fields = new Rows(new String[]{"bad", "title"}, new Object[][]{{BAD, "Still readable"}});
        app.resolver.results.put("watch_next_program", fields);
        run(app, true);
        check(has("FIELD_ERROR") && has("Still readable"), "field failure does not hide other fields");
        check(has("WATCH_NEXT END status=FIELD_ERRORS rows_visited=1 field_errors=1 complete=false"), "partial fields");
        Rows closing = new Rows(new String[]{"title"}, new Object[][]{{"Read before close"}});
        closing.failClose = true;
        app.resolver.results.put("watch_next_program", closing);
        run(app, true);
        check(has("WATCH_NEXT END status=QUERY_OR_CURSOR_ERROR rows_visited=1"), "close failure invalidates source");
        check(has("complete_sources=2/3"), "close error affects overall result");
        Rows moving = new Rows(new String[]{"title"}, new Object[][]{{"Partial read"}});
        moving.failMove = true;
        app.resolver.results.put("watch_next_program", moving);
        run(app, true);
        check(has("QUERY_OR_CURSOR_ERROR") && has("Partial read"), "cursor iteration error preserves earlier rows");
        app.resolver.results.put("watch_next_program", new IllegalArgumentException("unknown fixture URI"));
        app.inventoryDenied = true;
        run(app, false);
        check(has("UNAVAILABLE_OR_INVALID_QUERY"), "unknown URI reported");
        check(has("APP_INVENTORY FAILURE SecurityException") && has("inventory_ok=false"), "inventory failure explicit");
    }

    static void chunks() {
        App app = new App();
        StringBuilder text = new StringBuilder();
        for (int i = 0; i < 1500; i++) text.append('\u6f22').append("\ud83d\ude00");
        app.resolver.results.put("watch_next_program",
            new Rows(new String[]{"intent_uri"}, new Object[][]{{text.toString()}}));
        run(app, true);
        StringBuilder joined = new StringBuilder();
        int parts = 0;
        for (String entry : Log.entries) {
            check(entry.getBytes(StandardCharsets.UTF_8).length < 4000, "logcat payload under byte limit");
            if (!entry.contains("column=\"intent_uri\"")) continue;
            int start = entry.indexOf(" chunk=");
            check(start >= 0, "long values marked with chunk ranges");
            String part = entry.substring(entry.indexOf(' ', start + 1) + 1);
            check(!Character.isHighSurrogate(part.charAt(part.length() - 1)), "no broken trailing surrogate");
            check(!Character.isLowSurrogate(part.charAt(0)), "no broken leading surrogate");
            joined.append(part);
            parts++;
        }
        check(parts > 1 && joined.toString().equals(org.json.JSONObject.quote(text.toString())),
            "complete raw value reconstructed without truncation");
    }

    public static void main(String[] args) {
        switch (args[0]) {
            case "metadata": metadata(); break;
            case "privacy": privacy(); break;
            case "failures": failures(); break;
            case "partial": partial(); break;
            case "chunks": chunks(); break;
            default: throw new AssertionError("Unknown test");
        }
    }
}
'''


class TvProviderDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        home = os.environ.get("JAVA_HOME")
        javac = str(Path(home) / "bin/javac") if home else shutil.which("javac")
        cls.java = str(Path(home) / "bin/java") if home else shutil.which("java")
        if not javac or not cls.java:
            raise unittest.SkipTest("JDK required for the diagnostic's fake-cursor tests")
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name)
        sources = [str(SOURCE)]
        for name, text in {**STUBS, "io/cleanyourtv/ui/DiagnosticTest.java": HARNESS}.items():
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
            [self.java, "-cp", str(self.directory), "io.cleanyourtv.ui.DiagnosticTest", name],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_raw_metadata_and_all_publishers(self):
        self.scenario("metadata")

    def test_sensitive_values_require_opt_in(self):
        self.scenario("privacy")

    def test_inaccessible_sources_are_not_empty_successes(self):
        self.scenario("failures")

    def test_partial_results_and_cursor_failures(self):
        self.scenario("partial")

    def test_long_unicode_values_are_lossless_and_fit_logcat(self):
        self.scenario("chunks")

    def test_entrypoint_is_shell_protected_and_read_only(self):
        manifest = ET.parse(ROOT / "launcher-ui/app/AndroidManifest.xml").getroot()
        entry = manifest.find("application/activity[@%sname='.TvProviderDiagnosticActivity']" % ANDROID)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.get(ANDROID + "exported"), "true")
        self.assertEqual(entry.get(ANDROID + "permission"), "android.permission.DUMP")
        self.assertEqual(entry.findall("intent-filter"), [])
        permissions = {node.get(ANDROID + "name") for node in manifest.findall("uses-permission")}
        self.assertIn("android.permission.READ_TV_LISTINGS", permissions)
        self.assertNotIn("android.permission.DUMP", permissions)
        self.assertFalse(any("EPG" in name or "WATCHED" in name for name in permissions))


if __name__ == "__main__":
    unittest.main()
