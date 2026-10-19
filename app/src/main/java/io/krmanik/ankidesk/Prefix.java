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

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
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
        // session reinstalls them (ankidesk_pkg.py restore).
        File apps = new File(prefix, "var/lib/ankidesk/installed.json");
        if (apps.exists() && !apps.renameTo(new File(files, "apps-to-restore.json")))
            Log.w(TAG, "Could not keep the list of installed apps");
        deleteRecursive(prefix);
        if (!staging.renameTo(prefix))
            throw new IOException("Cannot move " + staging + " to " + prefix);
        home.mkdirs();
        Log.i(TAG, "Installed bootstrap into " + prefix);
    }

    /** Forget the installed runtime so the next start unpacks it again. User data is kept. */
    void reset() {
        deleteRecursive(prefix);
        deleteRecursive(new File(files, "usr-staging"));
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

    static void deleteRecursive(File f) {
        if (!f.exists() && !isSymlink(f))
            return;
        if (f.isDirectory() && !isSymlink(f)) {
            File[] children = f.listFiles();
            if (children != null)
                for (File c : children)
                    deleteRecursive(c);
        }
        //noinspection ResultOfMethodCallIgnored
        f.delete();
    }

    private static boolean isSymlink(File f) {
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
