package io.cleanyourtv.ui;

/** Native playback metadata, independent of TMDB IDs and any Home presentation. */
final class ContinueWatchingItem {
    enum Source { WATCH_NEXT }
    enum ContinuationKind { CONTINUE, NEXT, NONE }
    enum PlaybackCapability { VALID_PLAYBACK, INVALID }

    final String stableId;
    final long providerRowId;
    final Source source = Source.WATCH_NEXT;
    final String title, description, providerPackage, originalPlaybackIntent, posterUri, thumbnailUri;
    final String seasonDisplayNumber, episodeDisplayNumber, episodeTitle;
    final Integer type;
    final ContinuationKind continuationKind;
    final PlaybackCapability playbackCapability;
    final Long playbackPositionMillis, durationMillis, lastEngagementTimeMillis;
    final Boolean browsable, live, searchable;

    ContinueWatchingItem(long rowId, String title, String description, String providerPackage,
            String originalPlaybackIntent, String posterUri, String thumbnailUri, Long position, Long duration,
            Long engagement, String season, String episode, String episodeTitle, Integer type,
            ContinuationKind continuationKind, PlaybackCapability playbackCapability,
            Boolean browsable, Boolean live, Boolean searchable) {
        this.providerRowId = rowId;
        this.stableId = "tvprovider:watch_next:" + providerPackage + ":" + rowId;
        this.title = title;
        this.description = description;
        this.providerPackage = providerPackage;
        this.originalPlaybackIntent = originalPlaybackIntent;
        this.posterUri = posterUri;
        this.thumbnailUri = thumbnailUri;
        this.playbackPositionMillis = position;
        this.durationMillis = duration;
        this.lastEngagementTimeMillis = engagement;
        this.seasonDisplayNumber = season;
        this.episodeDisplayNumber = episode;
        this.episodeTitle = episodeTitle;
        this.type = type;
        this.continuationKind = continuationKind;
        this.playbackCapability = playbackCapability;
        this.browsable = browsable;
        this.live = live;
        this.searchable = searchable;
    }

    /** Null means unknown. Provider values remain unchanged, including negative or over-duration positions. */
    Double progress() {
        if (playbackPositionMillis == null || playbackPositionMillis < 0 || durationMillis == null || durationMillis <= 0) {
            return null;
        }
        return Math.max(0d, Math.min(1d, playbackPositionMillis.doubleValue() / durationMillis.doubleValue()));
    }

    boolean canContinue() {
        return providerRowId > 0 && title != null && !title.trim().isEmpty()
                && providerPackage != null && !providerPackage.trim().isEmpty()
                && !Boolean.FALSE.equals(browsable) && !Boolean.TRUE.equals(live)
                && continuationKind == ContinuationKind.CONTINUE
                && playbackCapability == PlaybackCapability.VALID_PLAYBACK;
    }
}
