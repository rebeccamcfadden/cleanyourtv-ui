package io.cleanyourtv.ui;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Handler;
import android.os.Looper;
import android.net.Uri;
import android.util.LruCache;
import android.widget.ImageView;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Posters, backdrops and logos for Explore and the title page: loaded in the background, kept in memory and on disk
 * (the app's cache folder, up to DISK_MAX, each file for TTL), so a row seen before shows at once without the network.
 */
final class Images {
    private Images() {}

    private static final long TTL = 7L * 24 * 3600_000, DISK_MAX = 160L * 1024 * 1024;
    /** An eighth of what the process may use, at most 24 MB: the TV has little memory and the disk holds the rest. */
    private static final LruCache<String, Bitmap> CACHE = new LruCache<String, Bitmap>(
            (int) Math.min(24L * 1024 * 1024, Runtime.getRuntime().maxMemory() / 8)) {
        @Override protected int sizeOf(String key, Bitmap b) { return b.getByteCount(); }
    };
    private static final ExecutorService POOL = Executors.newFixedThreadPool(4);
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static final Map<String, List<ImageView>> WAITING = new HashMap<>();
    private static File dir;
    private static Bitmap landscape;

    static synchronized Bitmap landscape(Context context) {
        if (landscape != null) return landscape;
        try (InputStream stream = context.getAssets().open("home-landscape.png")) {
            landscape = BitmapFactory.decodeStream(stream);
            if (landscape == null) throw new IOException("Invalid Home landscape");
            return landscape;
        } catch (IOException e) {
            AppLog.w("Home landscape could not be loaded: " + e.getMessage());
            throw new IllegalStateException("Bundled Home landscape is missing or invalid", e);
        }
    }

    interface ArtworkCallback { void loaded(Bitmap bitmap); }

    /** Native Home artwork shares the existing worker pool and HTTP/disk cache. Never called while drawing. */
    static void loadArtwork(Context context, String poster, String thumbnail, ArtworkCallback callback) {
        init(context);
        Context app = context.getApplicationContext();
        POOL.execute(() -> {
            Bitmap bitmap = artwork(app, poster);
            if (bitmap == null && thumbnail != null && !thumbnail.equals(poster)) bitmap = artwork(app, thumbnail);
            Bitmap ready = bitmap;
            MAIN.post(() -> callback.loaded(ready));
        });
    }

    private static Bitmap artwork(Context context, String value) {
        if (value == null || value.trim().isEmpty()) return null;
        String key = "watch-next:" + value;
        Bitmap hit = CACHE.get(key);
        if (hit != null) return hit;
        try {
            Uri uri = Uri.parse(value);
            String scheme = uri.getScheme();
            Bitmap bitmap;
            if ("https".equalsIgnoreCase(scheme)) {
                bitmap = fetch(value);
                if (bitmap != null && (bitmap.getWidth() > 1024 || bitmap.getHeight() > 576)) {
                    float scale = Math.min(1024f / bitmap.getWidth(), 576f / bitmap.getHeight());
                    bitmap = Bitmap.createScaledBitmap(bitmap, Math.max(1, Math.round(bitmap.getWidth() * scale)),
                            Math.max(1, Math.round(bitmap.getHeight() * scale)), true);
                }
            } else if ("content".equalsIgnoreCase(scheme) || "android.resource".equalsIgnoreCase(scheme)) {
                BitmapFactory.Options options = new BitmapFactory.Options();
                options.inJustDecodeBounds = true;
                try (InputStream stream = context.getContentResolver().openInputStream(uri)) {
                    if (stream == null) throw new IOException("No artwork stream");
                    BitmapFactory.decodeStream(stream, null, options);
                }
                if (options.outWidth <= 0 || options.outHeight <= 0) throw new IOException("Invalid artwork dimensions");
                options.inSampleSize = 1;
                while (options.outWidth / options.inSampleSize > 1024 || options.outHeight / options.inSampleSize > 576) {
                    options.inSampleSize *= 2;
                }
                options.inJustDecodeBounds = false;
                options.inPreferredConfig = Bitmap.Config.RGB_565;
                try (InputStream stream = context.getContentResolver().openInputStream(uri)) {
                    if (stream == null) throw new IOException("No artwork stream");
                    bitmap = BitmapFactory.decodeStream(stream, null, options);
                }
            } else {
                AppLog.w("Continue Watching: unsupported artwork scheme");
                return null;
            }
            if (bitmap == null) AppLog.w("Continue Watching: artwork could not be decoded");
            else CACHE.put(key, bitmap);
            return bitmap;
        } catch (IOException | SecurityException | IllegalArgumentException | IllegalStateException
                | android.content.res.Resources.NotFoundException e) {
            AppLog.w("Continue Watching: artwork unavailable (" + e.getClass().getSimpleName() + ")");
            return null;
        }
    }

    /** The disk cache's folder; old files are dropped once per start. */
    static synchronized void init(Context c) {
        if (dir != null) return;
        dir = new File(c.getApplicationContext().getCacheDir(), "img");
        //noinspection ResultOfMethodCallIgnored
        dir.mkdirs();
        POOL.execute(Images::prune);
    }

    /** Shows the image in the view once it arrives; a view reused for another image in the meantime is left alone. */
    static void load(ImageView view, String url) {
        if (dir == null) init(view.getContext());
        view.setTag(url);
        if (url == null || url.isEmpty()) {
            view.setImageDrawable(null);
            return;
        }
        Bitmap hit = CACHE.get(url);
        if (hit != null) {
            view.setImageBitmap(hit);
            return;
        }
        view.setImageDrawable(null);
        synchronized (WAITING) {
            List<ImageView> views = WAITING.get(url);
            if (views != null) {   // already on its way: this view gets it too
                views.add(view);
                return;
            }
            views = new ArrayList<>();
            views.add(view);
            WAITING.put(url, views);
        }
        POOL.execute(() -> {
            Bitmap b = fetch(url);
            if (b != null) CACHE.put(url, b);
            List<ImageView> views;
            synchronized (WAITING) { views = WAITING.remove(url); }
            if (b == null || views == null) return;
            MAIN.post(() -> {
                for (ImageView v : views) if (url.equals(v.getTag())) v.setImageBitmap(b);
            });
        });
    }

    /** From the disk cache when fresh, otherwise downloaded and saved. */
    static Bitmap fetch(String url) {
        File f = dir == null ? null : new File(dir, Integer.toHexString(url.hashCode()) + "-" + url.length());
        if (f != null && f.isFile() && System.currentTimeMillis() - f.lastModified() < TTL) {
            Bitmap b = decode(f, url);
            if (b != null) return b;
        }
        try {
            HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
            c.setConnectTimeout(8000);
            c.setReadTimeout(15000);
            byte[] bytes;
            try (InputStream in = c.getInputStream()) {
                bytes = Tmdb.readBytes(in);
            } finally {
                c.disconnect();
            }
            if (f != null) {
                try (FileOutputStream out = new FileOutputStream(f)) { out.write(bytes); } catch (Exception ignored) {}
            }
            return BitmapFactory.decodeByteArray(bytes, 0, bytes.length, options(url));
        } catch (Exception e) {
            return f != null && f.isFile() ? decode(f, url) : null;   // offline: an old copy beats nothing
        }
    }

    private static Bitmap decode(File f, String url) {
        return BitmapFactory.decodeFile(f.getAbsolutePath(), options(url));
    }

    /** Photos in half the memory; PNGs (title logos) keep their transparency. */
    private static BitmapFactory.Options options(String url) {
        BitmapFactory.Options o = new BitmapFactory.Options();
        o.inPreferredConfig = url.endsWith(".png") ? Bitmap.Config.ARGB_8888 : Bitmap.Config.RGB_565;
        return o;
    }

    /** Drops files well past their TTL, then the oldest until the folder fits in DISK_MAX. */
    private static void prune() {
        File[] files = dir.listFiles();
        if (files == null) return;
        long now = System.currentTimeMillis(), total = 0;
        List<File> kept = new ArrayList<>();
        for (File f : files) {
            //noinspection ResultOfMethodCallIgnored
            if (now - f.lastModified() > 2 * TTL) f.delete();
            else {
                kept.add(f);
                total += f.length();
            }
        }
        if (total <= DISK_MAX) return;
        File[] byAge = kept.toArray(new File[0]);
        Arrays.sort(byAge, (a, b) -> Long.compare(a.lastModified(), b.lastModified()));
        for (File f : byAge) {
            if (total <= DISK_MAX * 3 / 4) break;
            total -= f.length();
            //noinspection ResultOfMethodCallIgnored
            f.delete();
        }
    }

    static void trim() { CACHE.evictAll(); }
}
