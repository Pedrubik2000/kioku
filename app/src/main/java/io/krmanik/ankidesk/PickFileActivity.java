package io.krmanik.ankidesk;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.util.Log;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

/**
 * Brings files from the phone into the desktop; no UI of its own.
 *
 * <ul>
 * <li>{@code ankidesk:pick-wallpaper}: Android's picture picker. The picture is
 * copied to ~/.config/kioku/picked-wallpaper, where the desktop crops and applies it.</li>
 * <li>{@code ankidesk:pick-deck}: Android's file picker. The file is copied to
 * ~/Imports and its path written to ~/.config/kioku/picked-deck; the desktop
 * then hands it to Anki, which imports it.</li>
 * <li>"Open with" / "Share" of a deck from another app (Files, browser,
 * messengers): same as pick-deck, then Kioku is brought up.</li>
 * </ul>
 */
public class PickFileActivity extends Activity {
    static final String EXTRA_KIND = "kind";
    static final String KIND_WALLPAPER = "wallpaper";
    static final String KIND_DECK = "deck";

    private static final String TAG = "PickFile";
    private static final int PICK = 1;
    private String kind;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (savedInstanceState != null) {
            kind = savedInstanceState.getString(EXTRA_KIND);
            return;
        }
        Intent intent = getIntent();
        Uri shared = sharedUri(intent);
        if (shared != null) {
            // From another app: import into Anki, starting Kioku if needed.
            kind = KIND_DECK;
            copyInBackground(shared, true);
            return;
        }
        kind = intent.getStringExtra(EXTRA_KIND);
        if (kind == null)
            kind = KIND_WALLPAPER;
        Intent pick = new Intent(KIND_DECK.equals(kind) ? Intent.ACTION_OPEN_DOCUMENT : Intent.ACTION_GET_CONTENT)
                .addCategory(Intent.CATEGORY_OPENABLE)
                // Deck files have no registered MIME type, so offer every file.
                .setType(KIND_DECK.equals(kind) ? "*/*" : "image/*");
        try {
            startActivityForResult(pick, PICK);
        } catch (ActivityNotFoundException e) {
            Log.w(TAG, "No file picker", e);
            finish();
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        out.putString(EXTRA_KIND, kind);
    }

    private static Uri sharedUri(Intent intent) {
        if (Intent.ACTION_VIEW.equals(intent.getAction()))
            return intent.getData();
        if (Intent.ACTION_SEND.equals(intent.getAction())) {
            if (Build.VERSION.SDK_INT >= 33)
                return intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri.class);
            //noinspection deprecation
            return intent.getParcelableExtra(Intent.EXTRA_STREAM);
        }
        return null;
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        Uri uri = data != null ? data.getData() : null;
        if (requestCode == PICK && resultCode == RESULT_OK && uri != null)
            copyInBackground(uri, false);
        else
            finish();
    }

    /** Copies off the main thread: a collection package can be hundreds of MB. */
    private void copyInBackground(Uri uri, boolean openKioku) {
        if (KIND_DECK.equals(kind))
            Toast.makeText(this, "Importing " + displayName(uri) + " into Anki…", Toast.LENGTH_SHORT).show();
        Prefix prefix = new Prefix(this);
        new Thread(() -> {
            try {
                if (KIND_DECK.equals(kind))
                    importDeck(prefix, uri);
                else
                    copy(uri, configDir(prefix), "picked-wallpaper");
            } catch (IOException | SecurityException e) {
                Log.w(TAG, "Could not copy " + uri, e);
                runOnUiThread(() -> Toast.makeText(this, "Could not read the file: " + e.getMessage(),
                        Toast.LENGTH_LONG).show());
            }
            runOnUiThread(() -> {
                if (openKioku)
                    startActivity(new Intent(this, LauncherActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
                finish();
            });
        }, "pick-file").start();
    }

    private static File configDir(Prefix prefix) {
        return new File(prefix.home, ".config/kioku");
    }

    private void importDeck(Prefix prefix, Uri uri) throws IOException {
        File imports = new File(prefix.home, "Imports");
        //noinspection ResultOfMethodCallIgnored
        imports.mkdirs();
        String name = displayName(uri).replace('/', '_');
        File dest = new File(imports, name);
        int dot = name.lastIndexOf('.');
        for (int i = 2; dest.exists(); i++)
            dest = new File(imports, dot > 0 ? name.substring(0, dot) + " (" + i + ")" + name.substring(dot) : name + " " + i);
        copy(uri, imports, dest.getName());
        // The desktop watches the config directory and passes the file to Anki.
        writeAtomically(configDir(prefix), "picked-deck", dest.getPath());
    }

    private String displayName(Uri uri) {
        String name = null;
        try (Cursor c = getContentResolver().query(uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (c != null && c.moveToFirst())
                name = c.getString(0);
        } catch (Exception e) {
            Log.w(TAG, "No display name for " + uri, e);
        }
        if (name == null || name.isEmpty())
            name = uri.getLastPathSegment();
        return name == null || name.isEmpty() ? "deck.apkg" : name;
    }

    /** Copies to dir/name through a temporary file, so readers never see half a file. */
    private void copy(Uri uri, File dir, String name) throws IOException {
        //noinspection ResultOfMethodCallIgnored
        dir.mkdirs();
        File tmp = new File(dir, "." + name + ".part");
        try (InputStream in = getContentResolver().openInputStream(uri);
             OutputStream out = new FileOutputStream(tmp)) {
            if (in == null)
                throw new IOException("no data");
            byte[] buf = new byte[1 << 16];
            for (int n; (n = in.read(buf)) > 0; )
                out.write(buf, 0, n);
        }
        if (!tmp.renameTo(new File(dir, name)))
            throw new IOException("cannot save " + name);
    }

    static void writeAtomically(File dir, String name, String text) throws IOException {
        //noinspection ResultOfMethodCallIgnored
        dir.mkdirs();
        File tmp = new File(dir, "." + name + ".tmp");
        try (OutputStream out = new FileOutputStream(tmp)) {
            out.write(text.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        }
        if (!tmp.renameTo(new File(dir, name)))
            throw new IOException("cannot save " + name);
    }
}
