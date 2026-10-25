package io.cleanyourtv.ui;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Bitmap;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.graphics.Shader;

/** Canvas renderer for the opt-in Home layout, including native Continue Watching cards. */
final class HomePreview {
    static final int TOP_COUNT = 8;
    static final float APPS_TOP = 1092, UTILITIES_TOP = 1470, WEATHER_TOP = 1735;
    static final float APPS_SCROLL = 420, UTILITIES_SCROLL = 1050;

    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint border = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint heading = Ui.text(Ui.medium, 32, 0xFFEDF1F5);
    private final Paint text = Ui.text(Ui.medium, 25, 0xFFEDF1F5);
    private final Paint dim = Ui.text(Ui.regular, 21, 0xFFA8B7C6);
    private final Paint clock = Ui.numbers(Ui.light, 84, 0xFFEDF1F5);
    private final Paint greeting = Ui.text(Ui.regular, 43, 0xFFEDF1F5);
    private final Paint small = Ui.text(Ui.regular, 17, 0xFF9FABB9);
    private final Paint period = Ui.text(Ui.light, 28, 0xFFACB8C4);
    private final java.util.Map<String, String> sourceLabels = new java.util.HashMap<>();
    private final Path path = new Path();
    private final RectF box = new RectF();
    private final RectF labelBox = new RectF();
    private final LandscapeBackground landscape;
    private final Shader cardShade = new LinearGradient(0, 720, 0, 876, 0x00020910, 0xD9020910, Shader.TileMode.CLAMP);

    HomePreview(Bitmap image) {
        landscape = new LandscapeBackground(image, false);
        border.setStyle(Paint.Style.STROKE);
    }

    void sourceLabel(String pkg, String label) {
        sourceLabels.put(pkg, label);
    }

    static String topLabel(int index) {
        switch (index) {
            case 0: return Ui.tr("Início", "Home");
            case 1: return Ui.tr("Filmes", "Movies");
            case 2: return Ui.tr("Séries", "TV Shows");
            case 3: return Ui.tr("Música", "Music");
            case 4: return Ui.tr("Buscar", "Search");
            case 5: return "Wi-Fi";
            case 6: return Ui.tr("Entradas HDMI", "HDMI Inputs");
            default: return Ui.tr("Configurações", "Settings");
        }
    }

    static void layoutTop(RectF[] rects, float k) {
        float[] left = {102, 240, 408, 592, 778, 1624, 1691, 1758};
        float[] width = {134, 158, 174, 144, 62, 62, 62, 62};
        for (int i = 0; i < TOP_COUNT; i++) {
            rects[i].set(left[i] * k, 62 * k, (left[i] + width[i]) * k, 130 * k);
        }
    }

    static void layoutCards(RectF[] rects, float k) {
        float width = (1728 - 3 * 22) / 4f;
        for (int i = 0; i < rects.length; i++) {
            float left = 96 + i * (width + 22);
            rects[i].set(left * k, 660 * k, (left + width) * k, 876 * k);
        }
    }

    void background(Canvas c, float width, float height) {
        landscape.draw(c, width, height);
    }

    void header(Canvas c, Context context, float k, RectF[] rects, Spring[] focus, int selectedTab) {
        c.save();
        c.scale(k, k);
        fill.setColor(0x12C0D4E5);
        box.set(96, 62, 746, 134);
        c.drawRoundRect(box, 36, 36, fill);
        border.setColor(0x14FFFFFF);
        border.setStrokeWidth(1);
        c.drawRoundRect(box, 36, 36, border);
        box.set(1608, 62, 1824, 134);
        c.drawRoundRect(box, 36, 36, fill);
        c.drawRoundRect(box, 36, 36, border);
        for (int i = 0; i < TOP_COUNT; i++) {
            RectF r = rects[i];
            box.set(r.left / k, r.top / k, r.right / k, r.bottom / k);
            float f = Ui.clamp(focus[i].value);
            boolean selected = i == selectedTab;
            fill.setColor(selected ? 0xFFECF0F3 : Ui.alpha(0xFFEAF1F7, f));
            if (selected || (i >= 4 && f > 0.01f)) c.drawRoundRect(box, 34, 34, fill);
            int ink = selected || (i >= 4 && f > 0.5f) ? 0xFF152230 : 0xFFBBC8D5;
            if (i < 4) {
                text.setColor(ink);
                fitted(c, topLabel(i), box, 25, text);
            } else {
                String symbol = i == 4 ? "search" : i == 5 ? "wifi" : i == 6 ? "inputs_outline" : "settings";
                Symbols.draw(context, c, symbol, box.centerX(), box.centerY(), 27, ink);
            }
            if (f > 0.01f && (selected || i >= 4)) {
                border.setColor(Ui.alpha(0xFFC0DDF5, f));
                border.setStrokeWidth(3);
                c.drawRoundRect(box, 34, 34, border);
            }
        }
        c.restore();
    }

    void hero(Canvas c, float k, String hello, String date, String time, String weather,
            RectF[] rects, Spring[] focus, HomeContinueWatching row, Bitmap[] artwork) {
        c.save();
        c.scale(k, k);
        c.drawText(hello, 96, 445, greeting);
        c.drawText(date, 96, 491, dim);
        int split = time.lastIndexOf(' ');
        String digits = split < 0 ? time : time.substring(0, split);
        String suffix = split < 0 ? "" : time.substring(split + 1);
        float periodWidth = suffix.isEmpty() ? 0 : period.measureText(suffix) + 18;
        c.drawText(digits, 1824 - periodWidth - clock.measureText(digits), 454, clock);
        if (!suffix.isEmpty()) c.drawText(suffix, 1824 - period.measureText(suffix), 454, period);
        c.drawText(weather, 1824 - dim.measureText(weather), 505, dim);
        if (!row.isEmpty()) {
            c.drawText(Ui.tr("Continuar assistindo", "Continue Watching"), 96, 632, heading);
            String count = row.items().size() + Ui.tr(" em andamento", " in progress");
            c.drawText(count, 1824 - dim.measureText(count), 632, dim);
        }
        for (int i = 0; i < row.visibleCount(); i++) {
            ContinueWatchingItem item = row.items().get(row.first() + i);
            RectF r = rects[i];
            box.set(r.left / k, r.top / k, r.right / k, r.bottom / k);
            drawArt(c, item, artwork[i]);
            border.setColor(focus[i].value > 0.1f ? 0xFFC0DDF5 : 0x35FFFFFF);
            border.setStrokeWidth(focus[i].value > 0.1f ? 4 : 1);
            c.drawRoundRect(box, 16, 16, border);
            if (focus[i].value > 0.1f) {
                String badge = item.continuationKind == ContinueWatchingItem.ContinuationKind.NEXT
                        ? Ui.tr("Próximo", "Play next") : Ui.tr("Retomar", "Resume");
                small.setTextSize(19);
                small.setColor(0xFF243544);
                float width = small.measureText(badge) + 48;
                fill.setColor(0xFFD4EAFA);
                c.drawRoundRect(box.left + 18, box.top + 18, box.left + 18 + width, box.top + 58, 20, 20, fill);
                c.drawText(badge, box.left + 42, box.top + 45, small);
            }
            text.setColor(0xFFEDF1F5);
            String source = sourceLabels.get(item.providerPackage);
            float sourceWidth = 0;
            if (source != null) {
                small.setTextSize(17);
                small.setColor(0xFF9FABB9);
                sourceWidth = Math.min(box.width() * 0.3f, small.measureText(source));
                label(c, source, box.right - sourceWidth, 918, sourceWidth, 17, small);
            }
            label(c, item.title, box.left, 918, box.width() - (sourceWidth > 0 ? sourceWidth + 14 : 0), 27, text);
            label(c, HomeContinueWatching.secondary(item), box.left, 954, box.width(), 21, dim);
        }
        c.restore();
    }

    private void drawArt(Canvas c, ContinueWatchingItem item, Bitmap artwork) {
        c.save();
        path.reset();
        path.addRoundRect(box, 16, 16, Path.Direction.CW);
        c.clipPath(path);
        fill.setColor(0xFF203D4D);
        c.drawRect(box, fill);
        if (artwork != null) {
            float scale = Math.max(box.width() / artwork.getWidth(), box.height() / artwork.getHeight());
            float width = artwork.getWidth() * scale, height = artwork.getHeight() * scale;
            labelBox.set(box.centerX() - width / 2, box.centerY() - height / 2,
                    box.centerX() + width / 2, box.centerY() + height / 2);
            fill.setColor(0xFFFFFFFF);
            fill.setFilterBitmap(true);
            c.drawBitmap(artwork, null, labelBox, fill);
        }
        fill.setShader(cardShade);
        c.drawRect(box, fill);
        fill.setShader(null);
        Double progress = item.progress();
        if (progress == null) { c.restore(); return; }
        text.setTextSize(19);
        text.setColor(0xFFDAE9F5);
        c.drawText(HomeContinueWatching.remainingText(item),
                box.left + 18, box.bottom - 30, text);
        fill.setColor(0x55FFFFFF);
        c.drawRoundRect(box.left + 18, box.bottom - 15, box.right - 18, box.bottom - 10, 3, 3, fill);
        fill.setColor(0xFFE1EDF6);
        c.drawRoundRect(box.left + 18, box.bottom - 15,
                box.left + 18 + (box.width() - 36) * progress.floatValue(), box.bottom - 10, 3, 3, fill);
        c.restore();
    }

    void appsHeading(Canvas c, float k, int count, boolean appsFocused) {
        c.save();
        c.scale(k, k);
        c.drawText(Ui.tr("Seus serviços", "Your services"), 96, 1038, heading);
        String hint = appsFocused ? count + Ui.tr(" serviços", " services")
                : Ui.tr("Desça para abrir seus apps", "Scroll down to open your apps");
        c.drawText(hint, 1824 - dim.measureText(hint), 1038, dim);
        c.restore();
    }

    void appTile(Canvas c, RectF rect, float k, float focus, String label) {
        fill.setColor(0x261D3547);
        c.drawRoundRect(rect, 22 * k, 22 * k, fill);
        border.setColor(focus > 0.1f ? 0xFFC0DDF5 : 0x25FFFFFF);
        border.setStrokeWidth((focus > 0.1f ? 3 : 1) * k);
        c.drawRoundRect(rect, 22 * k, 22 * k, border);
        text.setColor(focus > 0.1f ? 0xFFEDF1F5 : 0xFFADBBC9);
        box.set(rect.left, rect.bottom + 20 * k, rect.right, rect.bottom + 62 * k);
        fitted(c, label, box, 22 * k, text);
    }

    private static void fitted(Canvas c, String label, RectF rect, float size, Paint paint) {
        paint.setTextSize(size);
        float width = paint.measureText(label);
        if (width > rect.width() - 18) paint.setTextSize(size * Math.max(1, rect.width() - 18) / width);
        c.drawText(label, rect.centerX() - paint.measureText(label) / 2, rect.centerY() + Ui.halfCap(paint), paint);
    }

    private static void label(Canvas c, String value, float x, float y, float width, float size, Paint paint) {
        paint.setTextSize(size);
        int count = paint.breakText(value, true, width, null);
        if (count < value.length()) {
            count = paint.breakText(value, true, Math.max(0, width - paint.measureText("...")), null);
            value = value.substring(0, count) + "...";
        }
        c.drawText(value, x, y, paint);
    }
}
