package io.cleanyourtv.ui;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

interface ContinueWatchingSource {
    enum Status { NOT_LOADED, OK, PERMISSION_DENIED, UNAVAILABLE, ERROR }

    final class Result {
        final Status status;
        final List<ContinueWatchingItem> items;

        Result(Status status, List<ContinueWatchingItem> items) {
            this.status = status;
            this.items = Collections.unmodifiableList(new ArrayList<>(items));
        }

        static Result empty(Status status) { return new Result(status, Collections.emptyList()); }
    }

    /** Blocking; the repository calls this on its IO executor, never from Home drawing or input handling. */
    Result load();
}
