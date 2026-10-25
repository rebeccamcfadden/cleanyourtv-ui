package io.cleanyourtv.ui;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Shader;

/** Shared Figma background treatment; all content is drawn after these three layers. */
final class LandscapeBackground {
    private final Bitmap image;
    private final int tint;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
    private final RectF cover = new RectF();
    private Shader fade;
    private float fadeHeight;

    LandscapeBackground(Bitmap image, boolean catalog) {
        this.image = image;
        tint = catalog ? 0xD9090E15 : 0x99090E15;
    }

    void draw(Canvas canvas, float width, float height) {
        float scale = Math.max(width / image.getWidth(), height / image.getHeight());
        float w = image.getWidth() * scale, h = image.getHeight() * scale;
        cover.set((width - w) / 2, (height - h) / 2, (width + w) / 2, (height + h) / 2);
        canvas.save();
        canvas.clipRect(0, 0, width, height);
        paint.setShader(null);
        paint.setColor(0xFFFFFFFF);
        canvas.drawBitmap(image, null, cover, paint);
        paint.setColor(tint);
        canvas.drawRect(0, 0, width, height, paint);
        if (fade == null || fadeHeight != height) {
            fadeHeight = height;
            fade = new LinearGradient(0, 0, 0, height,
                    new int[] {0x10090E15, 0x40090E15, 0xF5090E15, 0xFF090E15},
                    new float[] {0, 0.45f, 0.82f, 1}, Shader.TileMode.CLAMP);
        }
        paint.setColor(0xFFFFFFFF);
        paint.setShader(fade);
        canvas.drawRect(0, 0, width, height, paint);
        paint.setShader(null);
        canvas.restore();
    }
}
