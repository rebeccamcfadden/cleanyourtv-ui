package io.cleanyourtv.ui;

import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.database.Cursor;
import android.database.SQLException;
import android.media.tv.TvContract;
import android.net.Uri;
import android.os.Build;
import android.os.OperationCanceledException;
import android.os.SystemClock;
import android.util.Base64;
import android.util.Log;

import org.json.JSONObject;

import java.util.Arrays;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;
import java.util.TreeSet;

/** Temporary, read-only schema probe. No filtering, sorting, deduplication, network or playback. */
final class TvProviderDiagnostic {
    static final String TAG = "CYTV-TvProvider";
    private static final String READ = "android.permission.READ_TV_LISTINGS";
    private static final int CHUNK = 1000;

    private TvProviderDiagnostic() {}

    static void run(Context context, boolean rawValues) {
        String run = Long.toString(SystemClock.elapsedRealtimeNanos());
        info(run, "BEGIN package=" + context.getPackageName() + " uid=" + android.os.Process.myUid()
                + " sdk=" + Build.VERSION.SDK_INT + " raw_values=" + rawValues);
        info(run, "READ_TV_LISTINGS=" + permission(context, READ)
                + " ACCESS_ALL_EPG_DATA=" + permission(context,
                "com.android.providers.tv.permission.ACCESS_ALL_EPG_DATA"));
        info(run, rawValues ? "WARNING raw viewing history, URLs, intent extras and provider data: keep logs private."
                : "Sensitive columns are redacted. Explicit --ez raw_values true includes their original values.");
        boolean inventoryOk = inventory(context, run);
        ContentResolver resolver = context.getContentResolver();
        int complete = 0;
        if (table(resolver, run, "WATCH_NEXT", TvContract.WatchNextPrograms.CONTENT_URI, rawValues)) complete++;
        if (table(resolver, run, "PREVIEW_PROGRAM", TvContract.PreviewPrograms.CONTENT_URI, rawValues)) complete++;
        if (table(resolver, run, "CHANNEL", TvContract.Channels.CONTENT_URI, rawValues)) complete++;
        info(run, "END status=" + (complete == 3 && inventoryOk ? "COMPLETE" : "COMPLETED_WITH_ERRORS")
                + " complete_sources=" + complete + "/3 inventory_ok=" + inventoryOk);
    }

    private static String permission(Context context, String name) {
        return context.checkSelfPermission(name) == PackageManager.PERMISSION_GRANTED ? "GRANTED" : "DENIED";
    }

    private static boolean inventory(Context context, String run) {
        try {
            TreeSet<String> packages = new TreeSet<>();
            Intent intent = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LEANBACK_LAUNCHER);
            for (ResolveInfo app : context.getPackageManager().queryIntentActivities(intent, 0)) {
                if (app.activityInfo != null) packages.add(app.activityInfo.packageName);
            }
            for (String pkg : packages) value(run, "VISIBLE_LEANBACK_APP package=", JSONObject.quote(pkg));
            info(run, "VISIBLE_LEANBACK_APPS count=" + packages.size()
                    + " (visible enabled TV apps, not evidence that an app publishes records)");
            return true;
        } catch (SecurityException | IllegalStateException e) {
            failure(run, "APP_INVENTORY", e);
            return false;
        }
    }

    private static boolean table(ContentResolver resolver, String run, String source, Uri uri, boolean rawValues) {
        int rows = 0, fieldErrors = 0;
        boolean complete = false;
        String status = "ERROR";
        Map<String, Integer> publishers = new TreeMap<>();
        info(run, source + " BEGIN uri=" + uri + " projection=null selection=null sort=null");
        // No SQL selection for unprivileged readers; also avoid schema-dependent sort columns.
        try (Cursor cursor = resolver.query(uri, null, null, null, null)) {
            if (cursor == null) {
                status = "NULL_CURSOR";
                Log.e(TAG, "run=" + run + " " + source + " NULL_CURSOR; not an empty result");
            } else {
                String[] columns = cursor.getColumnNames();
                value(run, source + " columns=", Arrays.toString(columns));
                while (cursor.moveToNext()) {
                    rows++;
                    info(run, source + " ROW_BEGIN row=" + rows);
                    String publisher = "<missing package_name>";
                    for (int column = 0; column < columns.length; column++) {
                        String prefix = source + " row=" + rows + " column=" + JSONObject.quote(columns[column]);
                        try {
                            int type = cursor.getType(column);
                            value(run, prefix + " type=" + type + " value=",
                                    read(cursor, column, columns[column], type, rawValues));
                            if ("package_name".equals(columns[column])) {
                                publisher = type == Cursor.FIELD_TYPE_NULL ? "<null package_name>" : cursor.getString(column);
                            }
                        } catch (SecurityException | SQLException | IllegalArgumentException
                                | IllegalStateException | UnsupportedOperationException | OperationCanceledException e) {
                            fieldErrors++;
                            failure(run, prefix + " FIELD_ERROR", e);
                        }
                    }
                    publishers.put(publisher, publishers.containsKey(publisher) ? publishers.get(publisher) + 1 : 1);
                    info(run, source + " ROW_END row=" + rows);
                }
                complete = fieldErrors == 0;
                status = complete ? "OK" : "FIELD_ERRORS";
            }
        } catch (SecurityException e) {
            status = "SECURITY_EXCEPTION";
            failure(run, source, e);
        } catch (UnsupportedOperationException e) {
            status = "UNSUPPORTED";
            failure(run, source, e);
        } catch (IllegalArgumentException e) {
            status = "UNAVAILABLE_OR_INVALID_QUERY";
            failure(run, source, e);
        } catch (SQLException | IllegalStateException | OperationCanceledException e) {
            status = "QUERY_OR_CURSOR_ERROR";
            failure(run, source, e);
        }
        // A close() failure must also invalidate an otherwise fully read cursor.
        complete = complete && "OK".equals(status);
        for (Map.Entry<String, Integer> publisher : publishers.entrySet()) {
            value(run, source + " PUBLISHER rows=" + publisher.getValue() + " package=",
                    JSONObject.quote(publisher.getKey()));
        }
        info(run, source + " END status=" + status + " rows_visited=" + rows
                + " field_errors=" + fieldErrors + " complete=" + complete);
        return complete;
    }

    private static String read(Cursor cursor, int column, String name, int type, boolean rawValues) {
        switch (type) {
            case Cursor.FIELD_TYPE_NULL: return "null";
            case Cursor.FIELD_TYPE_INTEGER: return Long.toString(cursor.getLong(column));
            case Cursor.FIELD_TYPE_FLOAT: return Double.toString(cursor.getDouble(column));
            case Cursor.FIELD_TYPE_STRING:
                String text = cursor.getString(column);
                if (!rawValues && sensitive(name)) {
                    return "<REDACTED chars=" + text.length() + "; use raw_values=true>";
                }
                return JSONObject.quote(text);
            case Cursor.FIELD_TYPE_BLOB:
                byte[] bytes = cursor.getBlob(column);
                return rawValues ? "base64:" + Base64.encodeToString(bytes, Base64.NO_WRAP)
                        : "<BLOB bytes=" + bytes.length + "; use raw_values=true>";
            default: throw new IllegalArgumentException("Unknown cursor field type " + type);
        }
    }

    private static boolean sensitive(String column) {
        String name = column.toLowerCase(Locale.ROOT);
        return name.contains("uri") || name.contains("url") || name.contains("intent")
                || name.contains("internal_provider") || name.contains("token") || name.contains("secret")
                || name.contains("password") || name.contains("cookie") || name.contains("auth")
                || name.contains("extras") || name.contains("header");
    }

    private static void failure(String run, String source, Exception error) {
        value(run, source + " FAILURE " + error.getClass().getSimpleName() + " message=",
                JSONObject.quote(error.getMessage()));
        Log.e(TAG, "run=" + run + " " + source + " stacktrace", error);
    }

    private static void info(String run, String text) {
        value(run, "", text);
    }

    private static void value(String run, String prefix, String text) {
        int offset = 0;
        do {
            int end = Math.min(offset + CHUNK, text.length());
            if (end < text.length() && Character.isHighSurrogate(text.charAt(end - 1))
                    && Character.isLowSurrogate(text.charAt(end))) end--;
            String part = text.length() > CHUNK ? " chunk=" + offset + ".." + end + "/" + text.length() : "";
            Log.i(TAG, "run=" + run + " " + prefix + part + " " + text.substring(offset, end));
            // Older TVs drop rapid bursts even with a live logcat reader.
            SystemClock.sleep(2);
            offset = end;
        } while (offset < text.length());
    }
}
