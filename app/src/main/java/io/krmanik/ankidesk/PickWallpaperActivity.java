package io.krmanik.ankidesk;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;

/**
 * Android's picture picker for the desktop wallpaper ({@code ankidesk:pick-wallpaper}).
 * The picked picture is copied to ~/.config/kioku/picked-wallpaper, where the
 * desktop shell picks it up, crops it to the screen and applies it.
 */
public class PickWallpaperActivity extends Activity {
    private static final String TAG = "PickWallpaper";
    private static final int PICK = 1;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (savedInstanceState != null)
            return;
        Intent pick = new Intent(Intent.ACTION_GET_CONTENT).setType("image/*").addCategory(Intent.CATEGORY_OPENABLE);
        try {
            startActivityForResult(Intent.createChooser(pick, null), PICK);
        } catch (ActivityNotFoundException e) {
            Log.w(TAG, "No picture picker", e);
            finish();
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        Uri uri = data != null ? data.getData() : null;
        if (requestCode == PICK && resultCode == RESULT_OK && uri != null) {
            File dir = new File(new Prefix(this).home, ".config/kioku");
            File tmp = new File(dir, ".picked-wallpaper");
            //noinspection ResultOfMethodCallIgnored
            dir.mkdirs();
            try (InputStream in = getContentResolver().openInputStream(uri);
                 OutputStream out = new FileOutputStream(tmp)) {
                byte[] buf = new byte[1 << 16];
                for (int n; in != null && (n = in.read(buf)) > 0; )
                    out.write(buf, 0, n);
            } catch (Exception e) {
                Log.w(TAG, "Could not copy " + uri, e);
            }
            // Renamed only when complete, so the shell never reads half a file.
            if (!tmp.renameTo(new File(dir, "picked-wallpaper")))
                Log.w(TAG, "Could not save the picked picture");
        }
        finish();
    }
}
