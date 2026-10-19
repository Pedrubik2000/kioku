package io.ankidesk;

import android.app.Activity;
import android.app.Application;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;

import com.termux.x11.LorieApp;
import com.termux.x11.MainActivity;

/**
 * Termux:X11's Application (it routes the X server's start broadcast to the
 * display), plus one safety net: if the display is opened while no session is
 * running, e.g. from Recents after Android killed the app, go through the
 * launcher so Anki gets started instead of showing an empty screen.
 */
public class AnkiApp extends LorieApp {
    /** Held here: SharedPreferences keeps its listeners only weakly. */
    private SharedPreferences.OnSharedPreferenceChangeListener touchModeListener;

    @Override
    public void onCreate() {
        applyDisplayDefaults();
        super.onCreate();
        // The touch mode can also be changed in the display settings; keep the
        // desktop's Settings page in step.
        touchModeListener = (prefs, key) -> {
            if ("touchMode".equals(key))
                AndroidBridge.writeTouchMode(this, prefs.getString(key, "2"));
        };
        getSharedPreferences(getPackageName() + "_preferences", MODE_PRIVATE)
                .registerOnSharedPreferenceChangeListener(touchModeListener);
        registerActivityLifecycleCallbacks(new Application.ActivityLifecycleCallbacks() {
            @Override
            public void onActivityResumed(Activity activity) {
                if (activity instanceof MainActivity && !Session.isAlive()) {
                    activity.startActivity(new Intent(activity, LauncherActivity.class));
                    activity.finish();
                }
            }

            @Override public void onActivityCreated(Activity a, Bundle b) {}
            @Override public void onActivityStarted(Activity a) {}
            @Override public void onActivityPaused(Activity a) {}
            @Override public void onActivityStopped(Activity a) {}
            @Override public void onActivitySaveInstanceState(Activity a, Bundle b) {}
            @Override public void onActivityDestroyed(Activity a) {}
        });
    }

    /**
     * Termux:X11 defaults suit a desktop-in-a-phone power user (trackpad mode,
     * extra keys bar). Anki on a phone works better as a touch app, so set
     * these once; the user can still change them in the display settings.
     */
    private void applyDisplayDefaults() {
        SharedPreferences prefs = getSharedPreferences(getPackageName() + "_preferences", MODE_PRIVATE);
        if (prefs.getBoolean("ankidesk_defaults_applied", false))
            return;
        prefs.edit()
                .putString("touchMode", "2") // simulated touchscreen: a tap is a click where the finger is
                .putBoolean("fullscreen", true)
                .putBoolean("showAdditionalKbd", false)
                .putBoolean("ankidesk_defaults_applied", true)
                .apply();
    }
}
