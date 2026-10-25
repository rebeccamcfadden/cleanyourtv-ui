package io.cleanyourtv.ui;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.graphics.Shader;

/** Original procedural artwork and explicitly fictional progress for the opt-in Home layout preview. */
final class HomePreview {
    static final int COUNT = 4, TOP_COUNT = 8;
    static final float APPS_TOP = 1092, UTILITIES_TOP = 1470, WEATHER_TOP = 1735;
    static final float APPS_SCROLL = 650, UTILITIES_SCROLL = 1050;
    private static final String[] TITLES = {"Severance", "Dune: Part Two", "The Bear", "Sh\u014dgun"};
    private static final String[] EPISODES = {"S1 E4", "", "S2 E6", "S1 E3"};
    private static final String[] PROVIDERS = {"Apple TV+", "Max", "Hulu", "Disney+"};
    private static final int[] PROGRESS = {57, 56, 51, 68};
    private static final int[][] COLORS = {
        {0xFF397887, 0xFF0B2537}, {0xFFBD9667, 0xFF3D2A26},
        {0xFF987D65, 0xFF252B36}, {0xFF68837B, 0xFF182D32}
    };

    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint border = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint heading = Ui.text(Ui.medium, 32, 0xFFEDF1F5);
    private final Paint text = Ui.text(Ui.medium, 25, 0xFFEDF1F5);
    private final Paint dim = Ui.text(Ui.regular, 21, 0xFFA8B7C6);
    private final Paint clock = Ui.numbers(Ui.light, 84, 0xFFEDF1F5);
    private final Paint greeting = Ui.text(Ui.regular, 43, 0xFFEDF1F5);
    private final Path path = new Path();
    private final RectF box = new RectF();
    private final Shader sky = new LinearGradient(0, 0, 0, 1080, 0xFF233B4B, 0xFF060D17, Shader.TileMode.CLAMP);
    private final Shader shade = new LinearGradient(0, 360, 0, 1080, 0x00060C14, 0xF5060C14, Shader.TileMode.CLAMP);
    private final Shader[] art = new Shader[COUNT];

    HomePreview() {
        border.setStyle(Paint.Style.STROKE);
        for (int i = 0; i < COUNT; i++) {
            art[i] = new LinearGradient(0, 660, 0, 876, COLORS[i][0], COLORS[i][1], Shader.TileMode.CLAMP);
        }
    }

    static String demo() { return Ui.tr("Demonstração", "Demo"); }
    static String title(int index) { return TITLES[index]; }
    static String placeholderMessage() {
        return Ui.tr("Apenas demonstração. A reprodução ainda não está conectada.",
                "Demo only. Playback is not connected.");
    }

    static String topLabel(int index) {
        switch (index) {
            case 0: return Ui.tr("Início", "Home");
            case 1: return Ui.tr("Filmes", "Movies");
            case 2: return Ui.tr("Séries", "Shows");
            case 3: return Ui.tr("Música", "Music");
            case 4: return Ui.tr("Buscar", "Search");
            case 5: return "Wi-Fi";
            case 6: return Ui.tr("Entradas HDMI", "HDMI Inputs");
            default: return Ui.tr("Configurações", "Settings");
        }
    }

    static void layoutTop(RectF[] rects, float k) {
        float[] left = {96, 240, 420, 610, 806, 1536, 1624, 1712};
        float[] width = {134, 170, 180, 176, 68, 68, 68, 68};
        for (int i = 0; i < TOP_COUNT; i++) {
            rects[i].set(left[i] * k, 62 * k, (left[i] + width[i]) * k, 130 * k);
        }
    }

    static void layoutCards(RectF[] rects, float k) {
        float width = (1728 - 3 * 22) / 4f;
        for (int i = 0; i < COUNT; i++) {
            float left = 96 + i * (width + 22);
            rects[i].set(left * k, 660 * k, (left + width) * k, 876 * k);
        }
    }

    void background(Canvas c, float k) {
        c.save();
        c.scale(k, k);
        fill.setAlpha(255);
        fill.setShader(sky);
        c.drawRect(0, 0, 1920, 1080, fill);
        fill.setShader(null);
        ridge(c, 0xFF344C5A, 480, 0);
        ridge(c, 0xFF1C3543, 625, 70);
        ridge(c, 0xFF102735, 745, 140);
        fill.setShader(shade);
        c.drawRect(0, 0, 1920, 1080, fill);
        fill.setShader(null);
        c.restore();
    }

    private void ridge(Canvas c, int color, float base, float offset) {
        path.reset();
        path.moveTo(-180, 1080);
        path.lineTo(-180, base);
        for (int i = 0; i < 11; i++) {
            float y = base - (i % 3 == 0 ? 190 : i % 3 == 1 ? 45 : 110);
            path.lineTo(i * 210 - offset, y);
        }
        path.lineTo(2100, 1080);
        path.close();
        fill.setColor(color);
        c.drawPath(path, fill);
    }

    void header(Canvas c, Context context, float k, RectF[] rects, Spring[] focus, float scroll) {
        c.save();
        c.scale(k, k);
        if (scroll > 0) {
            fill.setColor(Ui.alpha(0xFF0B1722, Math.min(1, scroll / 250)));
            c.drawRect(0, 0, 1920, 178, fill);
        }
        for (int i = 0; i < TOP_COUNT; i++) {
            RectF r = rects[i];
            box.set(r.left / k, r.top / k, r.right / k, r.bottom / k);
            float f = Ui.clamp(focus[i].value);
            fill.setColor(i == 0 ? 0xFFECF0F3 : Ui.alpha(0xFFEAF1F7, f));
            if (i == 0 || f > 0.01f) c.drawRoundRect(box, 34, 34, fill);
            int ink = i == 0 || f > 0.5f ? 0xFF152230 : 0xFFBBC8D5;
            if (i < 4) {
                text.setColor(ink);
                fitted(c, topLabel(i), box, 25, text);
            } else {
                String symbol = i == 4 ? "search" : i == 5 ? "wifi" : i == 6 ? "hdmi" : "settings";
                Symbols.draw(context, c, symbol, box.centerX(), box.centerY(), 27, ink);
            }
            if (f > 0.01f) {
                border.setColor(Ui.alpha(0xFFC0DDF5, f));
                border.setStrokeWidth(3);
                c.drawRoundRect(box, 34, 34, border);
            }
        }
        c.restore();
    }

    void hero(Canvas c, float k, String hello, String date, String time, String weather,
            RectF[] rects, Spring[] focus) {
        c.save();
        c.scale(k, k);
        c.drawText(hello, 96, 445, greeting);
        c.drawText(date, 96, 491, dim);
        c.drawText(time, 1824 - clock.measureText(time), 454, clock);
        c.drawText(weather, 1824 - dim.measureText(weather), 505, dim);
        c.drawText(Ui.tr("Continuar assistindo", "Continue Watching"), 96, 622, heading);
        String notice = demo() + "  /  " + Ui.tr("Dados de exemplo", "Sample data");
        c.drawText(notice, 1824 - dim.measureText(notice), 622, dim);
        for (int i = 0; i < COUNT; i++) {
            RectF r = rects[i];
            box.set(r.left / k, r.top / k, r.right / k, r.bottom / k);
            drawArt(c, i);
            border.setColor(focus[i].value > 0.1f ? 0xFFC0DDF5 : 0x35FFFFFF);
            border.setStrokeWidth(focus[i].value > 0.1f ? 4 : 1);
            c.drawRoundRect(box, 16, 16, border);
            text.setColor(0xFFEDF1F5);
            text.setTextSize(26);
            c.drawText(TITLES[i], box.left, 918, text);
            String episode = EPISODES[i].isEmpty() ? Ui.tr("Filme", "Movie") : EPISODES[i];
            c.drawText(episode + "  /  " + PROVIDERS[i], box.left, 954, dim);
        }
        c.restore();
    }

    private void drawArt(Canvas c, int index) {
        c.save();
        path.reset();
        path.addRoundRect(box, 16, 16, Path.Direction.CW);
        c.clipPath(path);
        fill.setAlpha(255);
        fill.setShader(art[index]);
        c.drawRect(box, fill);
        fill.setShader(null);
        // Abstract, locally drawn scenery, not copied programme artwork.
        fill.setColor(0x35DDEDF3);
        for (int j = 0; j < 6; j++) {
            float x = box.left + 30 + j * 77;
            if (index == 0 || index == 2) c.drawRect(x, box.top + j * 10, x + 26, box.bottom, fill);
            else c.drawOval(x - 110, box.top + 50 + j * 18, x + 230, box.bottom + 100, fill);
        }
        fill.setColor(0x5905111D);
        c.drawRect(box.left, box.bottom - 80, box.right, box.bottom, fill);
        text.setTextSize(19);
        text.setColor(0xFFDAE9F5);
        c.drawText(demo(), box.left + 18, box.top + 34, text);
        c.drawText(Ui.tr("Progresso de exemplo", "Sample progress") + "  " + PROGRESS[index] + "%",
                box.left + 18, box.bottom - 30, text);
        fill.setColor(0x55FFFFFF);
        c.drawRoundRect(box.left + 18, box.bottom - 15, box.right - 18, box.bottom - 10, 3, 3, fill);
        fill.setColor(0xFFE1EDF6);
        c.drawRoundRect(box.left + 18, box.bottom - 15,
                box.left + 18 + (box.width() - 36) * PROGRESS[index] / 100f, box.bottom - 10, 3, 3, fill);
        c.restore();
    }

    void appsHeading(Canvas c, float k) {
        c.save();
        c.scale(k, k);
        c.drawText(Ui.tr("Seus aplicativos", "Your apps"), 96, 1038, heading);
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
}
