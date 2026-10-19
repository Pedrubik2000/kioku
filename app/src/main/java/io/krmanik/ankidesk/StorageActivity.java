package io.krmanik.ankidesk;

import android.Manifest;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.Settings;
import android.system.ErrnoException;
import android.system.Os;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

/**
 * {@code ankidesk:storage}, the counterpart of termux-setup-storage: asks for
 * access to the phone's shared storage and links its folders into
 * ~/storage (shared, downloads, dcim, pictures, ...), so the Files app and
 * Anki's file dialogs can reach the user's files. The result is written to
 * ~/.config/kioku/storage ("granted" or "denied") for the desktop.
 */
public class StorageActivity extends Activity {
    private static final String TAG = "Storage";
    private static final String[][] LINKS = {
            {"shared", ""},
            {"downloads", Environment.DIRECTORY_DOWNLOADS},
            {"documents", Environment.DIRECTORY_DOCUMENTS},
            {"dcim", Environment.DIRECTORY_DCIM},
            {"pictures", Environment.DIRECTORY_PICTURES},
            {"music", Environment.DIRECTORY_MUSIC},
            {"movies", Environment.DIRECTORY_MOVIES},
    };
    private boolean asked;

    @Override
    protected void onResume() {
        super.onResume();
        // Called again when the user comes back from the permission screen.
        if (granted(this)) {
            link(new Prefix(this));
            finish();
        } else if (!asked) {
            asked = true;
            request();
        } else {
            writeState(new Prefix(this), "denied");
            finish();
        }
    }

    static boolean granted(Activity a) {
        if (Build.VERSION.SDK_INT >= 30)
            return Environment.isExternalStorageManager();
        return a.checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED;
    }

    private void request() {
        if (Build.VERSION.SDK_INT >= 30) {
            try {
                startActivity(new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                        Uri.fromParts("package", getPackageName(), null)));
            } catch (ActivityNotFoundException e) {
                startActivity(new Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION));
            }
        } else {
            requestPermissions(new String[]{Manifest.permission.READ_EXTERNAL_STORAGE,
                    Manifest.permission.WRITE_EXTERNAL_STORAGE}, 1);
        }
    }

    /** ~/storage/* links to the shared storage folders, plus bookmarks for file managers. */
    static void link(Prefix prefix) {
        File storage = new File(prefix.home, "storage");
        //noinspection ResultOfMethodCallIgnored
        storage.mkdirs();
        File shared = Environment.getExternalStorageDirectory();
        StringBuilder bookmarks = new StringBuilder();
        for (String[] l : LINKS) {
            File link = new File(storage, l[0]);
            File target = l[1].isEmpty() ? shared : new File(shared, l[1]);
            try {
                // Only our own links are replaced; a real folder there is the user's.
                if (Prefix.isSymlink(link))
                    Os.remove(link.getPath());
                else if (link.exists())
                    continue;
                Os.symlink(target.getPath(), link.getPath());
            } catch (ErrnoException e) {
                Log.w(TAG, "Cannot link " + link, e);
            }
            String label = l[0].equals("shared") ? "Phone" : l[0].equals("dcim") ? "Camera"
                    : Character.toUpperCase(l[0].charAt(0)) + l[0].substring(1);
            bookmarks.append(Uri.fromFile(link)).append(' ').append(label).append('\n');
        }
        // GTK-format bookmarks, read by PCManFM-Qt (libfm-qt) and GTK file dialogs.
        File gtk = new File(prefix.home, ".config/gtk-3.0/bookmarks");
        try {
            String old = gtk.exists() ? Prefix.readFile(gtk) : "";
            if (!old.contains("/storage/shared")) {
                //noinspection ResultOfMethodCallIgnored
                gtk.getParentFile().mkdirs();
                try (OutputStream out = new FileOutputStream(gtk, true)) {
                    out.write(bookmarks.toString().getBytes(StandardCharsets.UTF_8));
                }
            }
        } catch (IOException e) {
            Log.w(TAG, "Cannot write bookmarks", e);
        }
        writeState(prefix, "granted");
    }

    /**
     * Turns phone storage off: removes the ~/storage links (only links, so
     * nothing on the phone is touched). Done before the runtime or packages
     * are removed or replaced, so no deletion can ever reach the user's files;
     * Settings turns it on again.
     */
    static void unlink(Prefix prefix) {
        File storage = new File(prefix.home, "storage");
        File[] links = storage.listFiles();
        boolean had = false;
        if (links != null) {
            for (File link : links) {
                if (Prefix.isSymlink(link)) {
                    had = true;
                    //noinspection ResultOfMethodCallIgnored
                    link.delete();
                }
            }
        }
        //noinspection ResultOfMethodCallIgnored
        storage.delete();  // only if now empty
        if (had)
            writeState(prefix, "off");
    }

    private static void writeState(Prefix prefix, String state) {
        try {
            PickFileActivity.writeAtomically(new File(prefix.home, ".config/kioku"), "storage", state);
        } catch (IOException e) {
            Log.w(TAG, "Cannot save storage state", e);
        }
    }
}
