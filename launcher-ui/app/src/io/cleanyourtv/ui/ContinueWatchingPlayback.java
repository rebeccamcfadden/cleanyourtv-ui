package io.cleanyourtv.ui;

import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;

import java.net.URISyntaxException;
import java.util.Locale;

/** Validates a copy for execution; never rewrites the stored provider URI or substitutes another destination. */
final class ContinueWatchingPlayback {
    enum LaunchResult { STARTED, INVALID_INTENT, UNAVAILABLE, FAILED }

    private final PackageManager packages;

    ContinueWatchingPlayback(PackageManager packages) { this.packages = packages; }

    static boolean validPackage(String pkg) {
        return pkg != null && pkg.matches("[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)*");
    }

    Intent prepare(String original, String pkg) {
        if (!validPackage(pkg) || original == null || original.trim().isEmpty()) return invalid();
        try {
            Intent intent = Intent.parseUri(original, Intent.URI_INTENT_SCHEME);
            if (intent.getSelector() != null
                    || intent.getComponent() != null && !pkg.equals(intent.getComponent().getPackageName())
                    || intent.getPackage() != null && !pkg.equals(intent.getPackage())) return invalid();
            String scheme = intent.getData() == null ? null : intent.getData().getScheme();
            if (intent.getData() != null && scheme == null) return invalid();
            if (scheme != null) {
                scheme = scheme.toLowerCase(Locale.ROOT);
                if (scheme.equals("file") || scheme.equals("javascript") || scheme.equals("data")) return invalid();
            }
            if (intent.getComponent() == null && intent.getData() == null) return invalid();
            intent.setClipData(null);
            intent.removeExtra("browser_fallback_url");
            intent.setPackage(pkg);
            // Discard provider task/forwarding and URI-grant flags; application Context needs NEW_TASK only.
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            return intent;
        } catch (URISyntaxException | IllegalArgumentException | SecurityException e) {
            AppLog.w("Continue Watching: invalid playback intent (" + e.getClass().getSimpleName() + ")");
            return null;
        }
    }

    private static Intent invalid() {
        AppLog.w("Continue Watching: rejected playback intent");
        return null;
    }

    boolean resolves(Intent intent, String pkg) {
        if (intent == null) return false;
        try {
            ResolveInfo resolved = packages.resolveActivity(intent, PackageManager.MATCH_DEFAULT_ONLY);
            boolean usable = resolved != null && resolved.activityInfo != null && resolved.activityInfo.enabled
                    && resolved.activityInfo.exported && pkg.equals(resolved.activityInfo.packageName);
            if (!usable) AppLog.w("Continue Watching: original playback destination unavailable");
            return usable;
        } catch (SecurityException | IllegalArgumentException | IllegalStateException e) {
            AppLog.w("Continue Watching: playback resolution failed (" + e.getClass().getSimpleName() + ")");
            return false;
        }
    }

    ContinueWatchingItem.PlaybackCapability capability(String original, String pkg) {
        return resolves(prepare(original, pkg), pkg) ? ContinueWatchingItem.PlaybackCapability.VALID_PLAYBACK
                : ContinueWatchingItem.PlaybackCapability.INVALID;
    }

    LaunchResult launch(Context context, ContinueWatchingItem item) {
        Intent intent = prepare(item.originalPlaybackIntent, item.providerPackage);
        if (intent == null) return LaunchResult.INVALID_INTENT;
        if (!resolves(intent, item.providerPackage)) return LaunchResult.UNAVAILABLE;
        try {
            context.startActivity(intent);
            return LaunchResult.STARTED;
        } catch (ActivityNotFoundException e) {
            AppLog.w("Continue Watching: playback destination disappeared");
            return LaunchResult.UNAVAILABLE;
        } catch (SecurityException | IllegalArgumentException | IllegalStateException e) {
            AppLog.w("Continue Watching: playback launch failed (" + e.getClass().getSimpleName() + ")");
            return LaunchResult.FAILED;
        }
    }
}
