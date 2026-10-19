package io.krmanik.ankidesk;

import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.provider.DocumentsContract;
import android.provider.Settings;
import android.util.Log;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.inputmethod.InputMethodManager;

import com.termux.x11.LoriePreferences;
import com.termux.x11.MainActivity;

/**
 * Commands sent from inside the prefix as {@code ankidesk:<command>} (through
 * xdg-open's request directory). They let the desktop use Android for things
 * that would otherwise need bundled apps: files, browser, settings, keyboard.
 */
final class AndroidBridge {
    private static final String TAG = "AndroidBridge";
    private static final Handler main = new Handler(Looper.getMainLooper());

    private AndroidBridge() {
    }

    static void handle(Context ctx, String request) {
        String cmd = request.substring("ankidesk:".length());
        Log.i(TAG, cmd);
        main.post(() -> {
            try {
                switch (cmd) {
                    case "keyboard/show":
                        setKeyboardVisible(true);
                        break;
                    case "keyboard/hide":
                        setKeyboardVisible(false);
                        break;
                    case "keyboard/toggle": {
                        MainActivity a = MainActivity.getFocusedOrAnyInstance();
                        if (a != null)
                            a.toggleKeyboardVisibility();
                        break;
                    }
                    case "input/touch":
                        // A tap clicks where the finger is.
                        setTouchMode(ctx, "2");
                        break;
                    case "input/trackpad":
                        // The screen acts as a laptop touchpad moving a cursor.
                        setTouchMode(ctx, "1");
                        break;
                    case "files":
                        openFiles(ctx);
                        break;
                    case "browser":
                        start(ctx, Intent.makeMainSelectorActivity(Intent.ACTION_MAIN, Intent.CATEGORY_APP_BROWSER));
                        break;
                    case "display-settings":
                        start(ctx, new Intent(ctx, LoriePreferences.class).setAction(Intent.ACTION_MAIN));
                        break;
                    case "app-settings":
                        start(ctx, new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                Uri.fromParts("package", ctx.getPackageName(), null)));
                        break;
                    case "phone-apps":
                        start(ctx, new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME));
                        break;
                    default:
                        Log.w(TAG, "Unknown request " + request);
                }
            } catch (Exception e) {
                Log.w(TAG, "Failed to handle " + request, e);
            }
        });
    }

    private static void setKeyboardVisible(boolean show) {
        MainActivity a = MainActivity.getFocusedOrAnyInstance();
        if (a == null)
            return;
        View v = a.getLorieView();
        if (show)
            v.requestFocus();
        if (Build.VERSION.SDK_INT >= 30) {
            // Unlike InputMethodManager, this also hides a keyboard that was
            // shown with SHOW_FORCED (Termux:X11's own keyboard toggle).
            WindowInsetsController c = a.getWindow().getInsetsController();
            if (c != null) {
                if (show)
                    c.show(WindowInsets.Type.ime());
                else
                    c.hide(WindowInsets.Type.ime());
                return;
            }
        }
        InputMethodManager imm = (InputMethodManager) a.getSystemService(Context.INPUT_METHOD_SERVICE);
        if (show)
            imm.showSoftInput(v, InputMethodManager.SHOW_IMPLICIT);
        else
            imm.hideSoftInputFromWindow(v.getWindowToken(), 0);
    }

    /** Same values as Termux:X11's "Touchscreen input mode" setting. */
    static void setTouchMode(Context ctx, String mode) {
        ctx.sendBroadcast(new Intent("com.termux.x11.CHANGE_PREFERENCE")
                .setPackage(ctx.getPackageName())
                .putExtra("touchMode", mode));
    }

    /** Android's Files app, opened at this app's home directory (HomeDocumentsProvider). */
    private static void openFiles(Context ctx) {
        String authority = ctx.getPackageName() + ".documents";
        Uri root = DocumentsContract.buildRootUri(authority, "home");
        try {
            start(ctx, new Intent(Intent.ACTION_VIEW).setDataAndType(root, DocumentsContract.Root.MIME_TYPE_ITEM));
        } catch (ActivityNotFoundException e) {
            Uri dir = DocumentsContract.buildDocumentUri(authority, new Prefix(ctx).home.getAbsolutePath());
            start(ctx, new Intent(Intent.ACTION_VIEW).setDataAndType(dir, DocumentsContract.Document.MIME_TYPE_DIR));
        }
    }

    private static void start(Context ctx, Intent i) {
        ctx.startActivity(i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
    }
}
