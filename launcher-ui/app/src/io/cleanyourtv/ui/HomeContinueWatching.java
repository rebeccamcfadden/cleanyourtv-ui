package io.cleanyourtv.ui;

import android.content.Context;

import java.util.Collections;
import java.util.List;

/** Selection and display-only values for the existing Home carousel. */
final class HomeContinueWatching {
    static final int VISIBLE = 4;
    private List<ContinueWatchingItem> items = Collections.emptyList();
    private int selected, first;

    List<ContinueWatchingItem> items() { return items; }
    boolean isEmpty() { return items.isEmpty(); }
    int selected() { return selected; }
    int first() { return first; }
    int visibleCount() { return Math.min(VISIBLE, items.size() - first); }
    ContinueWatchingItem current() { return isEmpty() ? null : items.get(selected); }

    void update(List<ContinueWatchingItem> next) {
        String identity = current() == null ? null : current().stableId;
        int nextIndex = Math.min(selected, Math.max(0, next.size() - 1));
        for (int i = 0; i < next.size(); i++) {
            if (next.get(i).stableId.equals(identity)) { nextIndex = i; break; }
        }
        items = next;
        select(nextIndex);
    }

    void select(int index) {
        selected = Math.max(0, Math.min(items.size() - 1, index));
        first = Math.max(0, Math.min(first, Math.max(0, items.size() - VISIBLE)));
        if (selected < first) first = selected;
        if (selected >= first + VISIBLE) first = selected - VISIBLE + 1;
    }

    ContinueWatchingPlayback.LaunchResult launch(Context context) {
        ContinueWatchingItem item = current();
        return item == null ? ContinueWatchingPlayback.LaunchResult.UNAVAILABLE
                : new ContinueWatchingPlayback(context.getPackageManager()).launch(context, item);
    }

    static String secondary(ContinueWatchingItem item) {
        String season = clean(item.seasonDisplayNumber), episode = clean(item.episodeDisplayNumber);
        String title = clean(item.episodeTitle);
        String numbers = (season.isEmpty() ? "" : "S" + season)
                + (episode.isEmpty() ? "" : (season.isEmpty() ? "" : " ") + "E" + episode);
        return numbers.isEmpty() ? title : title.isEmpty() ? numbers : numbers + " / " + title;
    }

    private static String clean(String value) { return value == null ? "" : value.trim(); }

    static String progressText(ContinueWatchingItem item) {
        Double progress = item.progress();
        return progress == null ? "" : (int) (progress * 100) + "%";
    }
}
