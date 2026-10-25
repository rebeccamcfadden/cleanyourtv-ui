package io.cleanyourtv.ui;

import android.content.Context;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.media.tv.TvContract;
import android.os.Looper;

import java.util.ArrayList;
import java.util.List;

/** Reads Watch Next only. Preview channels are discovery data, never a fallback for Continue Watching. */
final class TvProviderWatchNextSource implements ContinueWatchingSource {
    private final Context context;
    private final ContinueWatchingPlayback playback;

    TvProviderWatchNextSource(Context context) {
        this.context = context.getApplicationContext();
        this.playback = new ContinueWatchingPlayback(context.getPackageManager());
    }

    @Override public Result load() {
        if (Looper.myLooper() == Looper.getMainLooper()) {
            throw new IllegalStateException("Watch Next must be loaded off the main thread");
        }
        if (context.checkSelfPermission("android.permission.READ_TV_LISTINGS") != PackageManager.PERMISSION_GRANTED) {
            AppLog.w("Continue Watching: READ_TV_LISTINGS denied");
            return Result.empty(Status.PERMISSION_DENIED);
        }
        List<ContinueWatchingItem> items = new ArrayList<>();
        // A null projection tolerates OEM columns; an unprivileged reader must not supply SQL selection.
        try (Cursor cursor = context.getContentResolver().query(
                TvContract.WatchNextPrograms.CONTENT_URI, null, null, null, null)) {
            if (cursor == null) {
                AppLog.w("Continue Watching: Watch Next returned a null cursor");
                return Result.empty(Status.UNAVAILABLE);
            }
            while (cursor.moveToNext()) {
                Row row = new Row(cursor);
                Long id = row.number("_id");
                String title = row.text("title"), pkg = row.text("package_name");
                if (id == null || id <= 0 || title == null || title.trim().isEmpty()
                        || !ContinueWatchingPlayback.validPackage(pkg)) {
                    AppLog.w("Continue Watching: skipped row with invalid identity, title or package");
                    continue;
                }
                Boolean browsable = row.flag("browsable"), live = row.flag("live"), searchable = row.flag("searchable");
                if (row.invalidFlags) {
                    AppLog.w("Continue Watching: skipped row with malformed visibility/live flags");
                    continue;
                }
                Integer kind = row.integer("watch_next_type");
                ContinueWatchingItem.ContinuationKind continuation = kind != null
                        && kind == TvContract.WatchNextPrograms.WATCH_NEXT_TYPE_CONTINUE
                        ? ContinueWatchingItem.ContinuationKind.CONTINUE
                        : kind != null && kind == TvContract.WatchNextPrograms.WATCH_NEXT_TYPE_NEXT
                        ? ContinueWatchingItem.ContinuationKind.NEXT : ContinueWatchingItem.ContinuationKind.NONE;
                String original = row.text("intent_uri");
                String description = row.text("short_description");
                if (description == null || description.trim().isEmpty()) description = row.text("long_description");
                items.add(new ContinueWatchingItem(id, title, description, pkg, original, row.text("poster_art_uri"),
                        row.text("thumbnail_uri"), row.number("last_playback_position_millis"), row.number("duration_millis"),
                        row.number("last_engagement_time_utc_millis"), row.text("season_display_number"),
                        row.text("episode_display_number"), row.text("episode_title"), row.integer("type"), continuation,
                        playback.capability(original, pkg), browsable, live, searchable));
            }
        } catch (SecurityException e) {
            AppLog.w("Continue Watching: Watch Next permission denied (SecurityException)");
            return Result.empty(Status.PERMISSION_DENIED);
        } catch (IllegalArgumentException | UnsupportedOperationException e) {
            AppLog.w("Continue Watching: Watch Next unavailable (" + e.getClass().getSimpleName() + ")");
            return Result.empty(Status.UNAVAILABLE);
        } catch (RuntimeException e) {
            // Provider/OEM cursor implementations can fail on query, iteration or close. Never publish a partial list.
            AppLog.w("Continue Watching: Watch Next failed (" + e.getClass().getSimpleName() + ")");
            return Result.empty(Status.ERROR);
        }
        return new Result(Status.OK, items);
    }

    private static final class Row {
        private final Cursor cursor;
        boolean invalidFlags;

        Row(Cursor cursor) { this.cursor = cursor; }

        String text(String name) {
            int index = cursor.getColumnIndex(name);
            if (index < 0 || cursor.isNull(index)) return null;
            int type = cursor.getType(index);
            if (type == Cursor.FIELD_TYPE_STRING || type == Cursor.FIELD_TYPE_INTEGER) return cursor.getString(index);
            malformed(name);
            return null;
        }

        Long number(String name) {
            int index = cursor.getColumnIndex(name);
            if (index < 0 || cursor.isNull(index)) return null;
            if (cursor.getType(index) == Cursor.FIELD_TYPE_INTEGER) return cursor.getLong(index);
            if (cursor.getType(index) == Cursor.FIELD_TYPE_STRING) {
                try {
                    return Long.valueOf(cursor.getString(index).trim());
                } catch (NumberFormatException e) {
                    malformed(name);
                    return null;
                }
            }
            malformed(name);
            return null;
        }

        Integer integer(String name) {
            Long value = number(name);
            if (value == null) return null;
            if (value < Integer.MIN_VALUE || value > Integer.MAX_VALUE) {
                malformed(name);
                return null;
            }
            return value.intValue();
        }

        Boolean flag(String name) {
            int index = cursor.getColumnIndex(name);
            if (index < 0 || cursor.isNull(index)) return null;
            Long value = number(name);
            if (value != null && (value == 0 || value == 1)) return value == 1;
            invalidFlags = true;
            malformed(name);
            return null;
        }

        private static void malformed(String column) {
            AppLog.w("Continue Watching: malformed Watch Next column " + column);
        }
    }
}
