package io.cleanyourtv.ui;

import android.app.Activity;
import android.os.Bundle;

/** Explicit shell entry point only: no Home lifecycle or menu integration. */
public final class TvProviderDiagnosticActivity extends Activity {
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        boolean rawValues = getIntent().getBooleanExtra("raw_values", false);
        android.content.Context app = getApplicationContext();
        new Thread(() -> {
            try {
                TvProviderDiagnostic.run(app, rawValues);
            } finally {
                runOnUiThread(this::finish);
            }
        }, "tv-provider-diagnostic").start();
    }
}
