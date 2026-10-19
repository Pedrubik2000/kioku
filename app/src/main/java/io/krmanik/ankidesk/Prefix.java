package io.krmanik.ankidesk;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.SystemClock;
import android.system.ErrnoException;
import android.system.Os;
import android.system.OsConstants;
import android.util.Log;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;
import java.util.Properties;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/** The bundled Termux prefix: where it lives, whether it is intact, and its installation. */
final class Prefix {
    private static final String TAG = "AnkiPrefix";
    static final String BOOTSTRAP_ASSET = "bootstrap-aarch64.zip";

    /** Files whose absence means the runtime is damaged and must be unpacked again. */
    private static final String[] ESSENTIAL = {
            "bin/dash", "bin/python", "bin/jwm", "lib/libtermux-exec.so",
            "libexec/ankidx/session.sh", "share/ankidx/launch_anki.py",
            "lib/qt6/QtWebEngineProcess", "share/qt6/resources/qtwebengine_resources.pak",
    };

    final File files;
    final File prefix;
    final File home;
    final File tmp;

    Prefix(Context ctx) {
        // Must match the prefix baked into the bundled binaries.
        files = new File("/data/data/" + ctx.getPackageName() + "/files");
        prefix = new File(files, "usr");
        home = new File(files, "home");
        tmp = new File(prefix, "tmp");
    }

    /** Progress of {@link #install}. */
    static final class Progress {
        String stage;
        long bytesDone, bytesTotal;
        int filesDone, filesTotal;
        long etaMillis = -1;
    }

    interface ProgressListener {
        void onProgress(Progress p);
    }

    private static String apkVersion(Context ctx) {
        try {
            PackageInfo pi = ctx.getPackageManager().getPackageInfo(ctx.getPackageName(), 0);
            return pi.versionName + "/" + pi.lastUpdateTime;
        } catch (PackageManager.NameNotFoundException e) {
            throw new IllegalStateException(e);
        }
    }

    /** True when this APK's runtime is fully unpacked and nothing essential is missing. */
    boolean isInstalled(Context ctx) {
        File marker = new File(prefix, ".bootstrap-version");
        if (!marker.exists())
            return false;
        try {
            if (!apkVersion(ctx).equals(readFile(marker).trim()))
                return false;
        } catch (IOException e) {
            return false;
        }
        for (String rel : ESSENTIAL) {
            if (!new File(prefix, rel).exists()) {
                Log.w(TAG, "Runtime damaged, missing " + rel);
                return false;
            }
        }
        return true;
    }

    /**
     * Unpack the bootstrap into a staging directory and swap it in. The user's
     * home directory (collections, media, add-ons) is never touched.
     */
    void install(Context ctx, ProgressListener listener) throws IOException {
        if (!"arm64-v8a".equals(Build.SUPPORTED_ABIS[0]))
            throw new IOException("This device is " + Build.SUPPORTED_ABIS[0] + "; only 64-bit ARM (arm64-v8a) is supported.");

        Progress p = new Progress();
        p.stage = "Checking bootstrap";
        listener.onProgress(p);

        Properties manifest = readManifest(ctx);
        String pkg = manifest.getProperty("package", "");
        if (!pkg.equals(ctx.getPackageName()))
            throw new IOException("This build's runtime was made for '" + pkg + "' but the app is '" + ctx.getPackageName() + "'.");
        p.bytesTotal = Long.parseLong(manifest.getProperty("bytes", "0"));
        p.filesTotal = Integer.parseInt(manifest.getProperty("files", "0"));

        // getFilesDir() creates the directory; free space of a missing path reads as 0.
        ctx.getFilesDir();
        // Room for the unpacked runtime plus the copy being replaced on upgrade.
        long needed = p.bytesTotal + 64L * 1024 * 1024;
        long free = files.getUsableSpace();
        if (free < needed)
            throw new IOException(String.format("Not enough storage: %d MB free, %d MB needed.", free >> 20, needed >> 20));

        File staging = new File(files, "usr-staging");
        deleteRecursive(staging);
        if (!staging.mkdirs())
            throw new IOException("Cannot create " + staging);

        Map<String, String> symlinks = new HashMap<>();
        String executables = "";
        byte[] buf = new byte[1 << 16];
        long start = SystemClock.elapsedRealtime(), lastReport = 0;
        p.stage = "Unpacking";

        try (ZipInputStream zip = new ZipInputStream(ctx.getAssets().open(BOOTSTRAP_ASSET))) {
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                String name = entry.getName();
                if (name.equals("MANIFEST.txt"))
                    continue;
                if (name.equals("SYMLINKS.txt")) {
                    for (String line : readAll(zip, buf).split("\n")) {
                        String[] parts = line.split("←");
                        if (parts.length == 2)
                            symlinks.put(parts[1], parts[0]);
                    }
                    continue;
                }
                if (name.equals("EXECUTABLES.txt")) {
                    executables = readAll(zip, buf);
                    continue;
                }
                File out = new File(staging, name);
                if (!out.getCanonicalPath().startsWith(staging.getCanonicalPath() + File.separator))
                    throw new IOException("Bad entry " + name);
                if (entry.isDirectory()) {
                    out.mkdirs();
                    continue;
                }
                File parent = out.getParentFile();
                if (parent != null)
                    parent.mkdirs();
                try (OutputStream os = new FileOutputStream(out)) {
                    int n;
                    while ((n = zip.read(buf)) > 0) {
                        os.write(buf, 0, n);
                        p.bytesDone += n;
                    }
                }
                p.filesDone++;
                long now = SystemClock.elapsedRealtime();
                if (now - lastReport > 100) {
                    long elapsed = now - start;
                    if (p.bytesDone > 0 && elapsed > 1500)
                        p.etaMillis = elapsed * (p.bytesTotal - p.bytesDone) / p.bytesDone;
                    listener.onProgress(p);
                    lastReport = now;
                }
            }
        }

        p.stage = "Linking";
        p.etaMillis = -1;
        listener.onProgress(p);
        try {
            for (Map.Entry<String, String> e : symlinks.entrySet()) {
                File link = new File(staging, e.getKey());
                File parent = link.getParentFile();
                if (parent != null)
                    parent.mkdirs();
                Os.symlink(e.getValue(), link.getPath());
            }
            for (String rel : executables.split("\n")) {
                if (!rel.isEmpty())
                    Os.chmod(new File(staging, rel).getPath(), 0700);
            }
        } catch (ErrnoException e) {
            throw new IOException(e);
        }

        p.stage = "Finishing";
        listener.onProgress(p);
        new File(staging, "tmp").mkdirs();
        try (OutputStream os = new FileOutputStream(new File(staging, ".bootstrap-version"))) {
            os.write((apkVersion(ctx) + "\n").getBytes(StandardCharsets.UTF_8));
        }
        // Apps the user installed live inside the prefix; remember them so the
        // session reinstalls them (ankidesk_pkg.py restore). Merged with a list
        // left by an earlier update whose restore has not finished yet.
        keepInstalledApps();
        // Nothing removed below may reach the phone's files.
        StorageActivity.unlink(this);
        // Swap the runtimes with renames: until the new one is in place the old
        // one stays whole, so an interruption never leaves no runtime at all.
        // User data (decks, media, add-ons, settings) is in home/, which is
        // never touched here.
        File old = new File(files, "usr-old");
        deleteRecursive(old);
        if (prefix.exists() && !prefix.renameTo(old))
            throw new IOException("Cannot move " + prefix + " aside");
        if (!staging.renameTo(prefix)) {
            //noinspection ResultOfMethodCallIgnored
            old.renameTo(prefix);
            throw new IOException("Cannot move " + staging + " to " + prefix);
        }
        deleteRecursive(old);
        home.mkdirs();
        Log.i(TAG, "Installed bootstrap into " + prefix);
    }

    private void keepInstalledApps() {
        File apps = new File(prefix, "var/lib/ankidesk/installed.json");
        File restore = new File(files, "apps-to-restore.json");
        if (!apps.exists())
            return;
        try {
            JSONObject pending = new JSONObject(restore.exists() ? readFile(restore) : "{}");
            JSONObject current = new JSONObject(readFile(apps));
            for (Iterator<String> it = current.keys(); it.hasNext(); ) {
                String name = it.next();
                pending.put(name, current.get(name));
            }
            try (OutputStream os = new FileOutputStream(restore)) {
                os.write(pending.toString().getBytes(StandardCharsets.UTF_8));
            }
        } catch (IOException | JSONException e) {
            Log.w(TAG, "Could not keep the list of installed apps", e);
        }
    }

    /** Forget the installed runtime so the next start unpacks it again. User data is kept. */
    void reset() {
        keepInstalledApps();
        StorageActivity.unlink(this);
        deleteRecursive(prefix);
        deleteRecursive(new File(files, "usr-staging"));
        deleteRecursive(new File(files, "usr-old"));
    }

    private static Properties readManifest(Context ctx) throws IOException {
        try (ZipInputStream zip = new ZipInputStream(ctx.getAssets().open(BOOTSTRAP_ASSET))) {
            ZipEntry first = zip.getNextEntry();
            if (first == null || !first.getName().equals("MANIFEST.txt"))
                throw new IOException("Bootstrap has no MANIFEST.txt; rebuild it with tools/build_rootfs.py.");
            Properties props = new Properties();
            props.load(zip);
            return props;
        }
    }

    /** Environment shared by every process started inside the prefix. */
    Map<String, String> environment() {
        Map<String, String> env = new HashMap<>();
        String p = prefix.getPath();
        env.put("PREFIX", p);
        env.put("HOME", home.getPath());
        env.put("TMPDIR", tmp.getPath());
        env.put("TMP", tmp.getPath());
        env.put("PATH", p + "/bin:/system/bin");
        env.put("LANG", "en_US.UTF-8");
        env.put("DISPLAY", ":0");
        env.put("XKB_CONFIG_ROOT", p + "/share/xkeyboard-config-2");
        return env;
    }

    /**
     * Deletes f and, for a real directory, everything in it. Symbolic links are
     * removed, never followed, and nothing on the phone's shared storage is
     * touched even when reached through a link in the path (~/storage/...).
     */
    static void deleteRecursive(File f) {
        if (isSymlink(f)) {
            //noinspection ResultOfMethodCallIgnored
            f.delete();
            return;
        }
        if (!f.exists() || isSharedStorage(f))
            return;
        if (f.isDirectory()) {
            File[] children = f.listFiles();
            if (children != null)
                for (File c : children)
                    deleteRecursive(c);
        }
        //noinspection ResultOfMethodCallIgnored
        f.delete();
    }

    /** True for paths on the phone's shared storage (/storage, /sdcard, /mnt). */
    static boolean isSharedStorage(File f) {
        try {
            String c = f.getCanonicalPath();
            return c.startsWith("/storage/") || c.startsWith("/sdcard") || c.startsWith("/mnt/");
        } catch (IOException e) {
            return true;  // unknown: leave it alone
        }
    }

    static boolean isSymlink(File f) {
        try {
            return OsConstants.S_ISLNK(Os.lstat(f.getPath()).st_mode);
        } catch (ErrnoException e) {
            return false;
        }
    }

    static String readFile(File f) throws IOException {
        try (InputStream in = new FileInputStream(f)) {
            return readAll(in, new byte[8192]);
        }
    }

    /** Last {@code maxLines} lines of a log file, or a note if it does not exist. */
    static String tail(File f, int maxLines) {
        try {
            String[] lines = readFile(f).split("\n");
            StringBuilder sb = new StringBuilder();
            for (int i = Math.max(0, lines.length - maxLines); i < lines.length; i++)
                sb.append(lines[i]).append('\n');
            return sb.toString();
        } catch (IOException e) {
            return "(no " + f.getName() + ")\n";
        }
    }

    private static String readAll(InputStream in, byte[] buf) throws IOException {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        int n;
        while ((n = in.read(buf)) > 0)
            bos.write(buf, 0, n);
        return bos.toString("UTF-8");
    }
}
