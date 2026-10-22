package io.ankidesk;

import android.database.Cursor;
import android.database.MatrixCursor;
import android.os.CancellationSignal;
import android.os.ParcelFileDescriptor;
import android.provider.DocumentsContract.Document;
import android.provider.DocumentsContract.Root;
import android.provider.DocumentsProvider;
import android.webkit.MimeTypeMap;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;

/**
 * Exposes the runtime's home directory (Anki profiles, media, backups, add-ons)
 * in Android's Files app and in any app's file picker, so no file manager has
 * to be bundled.
 */
public class HomeDocumentsProvider extends DocumentsProvider {
    private static final String[] ROOT_COLUMNS = {
            Root.COLUMN_ROOT_ID, Root.COLUMN_FLAGS, Root.COLUMN_TITLE, Root.COLUMN_SUMMARY,
            Root.COLUMN_DOCUMENT_ID, Root.COLUMN_ICON, Root.COLUMN_AVAILABLE_BYTES,
    };
    private static final String[] DOC_COLUMNS = {
            Document.COLUMN_DOCUMENT_ID, Document.COLUMN_DISPLAY_NAME, Document.COLUMN_MIME_TYPE,
            Document.COLUMN_LAST_MODIFIED, Document.COLUMN_FLAGS, Document.COLUMN_SIZE,
    };

    private File home;

    @Override
    public boolean onCreate() {
        home = new Prefix(getContext()).home;
        return true;
    }

    @Override
    public Cursor queryRoots(String[] projection) {
        MatrixCursor c = new MatrixCursor(projection != null ? projection : ROOT_COLUMNS);
        home.mkdirs();
        c.newRow()
                .add(Root.COLUMN_ROOT_ID, "home")
                .add(Root.COLUMN_FLAGS, Root.FLAG_SUPPORTS_CREATE | Root.FLAG_SUPPORTS_IS_CHILD | Root.FLAG_LOCAL_ONLY)
                .add(Root.COLUMN_TITLE, getContext().getString(R.string.app_name))
                .add(Root.COLUMN_SUMMARY, "Anki profiles, media and backups")
                .add(Root.COLUMN_DOCUMENT_ID, docId(home))
                .add(Root.COLUMN_ICON, R.mipmap.ic_launcher)
                .add(Root.COLUMN_AVAILABLE_BYTES, home.getFreeSpace());
        return c;
    }

    @Override
    public Cursor queryDocument(String documentId, String[] projection) throws FileNotFoundException {
        MatrixCursor c = new MatrixCursor(projection != null ? projection : DOC_COLUMNS);
        addRow(c, file(documentId));
        return c;
    }

    @Override
    public Cursor queryChildDocuments(String parentId, String[] projection, String sortOrder) throws FileNotFoundException {
        MatrixCursor c = new MatrixCursor(projection != null ? projection : DOC_COLUMNS);
        File[] children = file(parentId).listFiles();
        if (children != null)
            for (File f : children)
                // ~/storage/* link to the phone's own storage, which the Files
                // app already shows and file() refuses (outside of home).
                if (!Prefix.isSharedStorage(f))
                    addRow(c, f);
        return c;
    }

    @Override
    public ParcelFileDescriptor openDocument(String documentId, String mode, CancellationSignal signal) throws FileNotFoundException {
        return ParcelFileDescriptor.open(file(documentId), ParcelFileDescriptor.parseMode(mode));
    }

    @Override
    public String createDocument(String parentId, String mimeType, String displayName) throws FileNotFoundException {
        File parent = file(parentId);
        File f = new File(parent, displayName);
        for (int i = 2; f.exists(); i++)
            f = new File(parent, displayName + " (" + i + ")");
        try {
            boolean ok = Document.MIME_TYPE_DIR.equals(mimeType) ? f.mkdir() : f.createNewFile();
            if (!ok)
                throw new IOException("create failed");
        } catch (IOException e) {
            throw new FileNotFoundException("Cannot create " + f + ": " + e.getMessage());
        }
        return docId(f);
    }

    @Override
    public void deleteDocument(String documentId) throws FileNotFoundException {
        File f = file(documentId);
        if (f.equals(home))
            throw new FileNotFoundException("Cannot delete the root");
        Prefix.deleteRecursive(f);
    }

    @Override
    public String renameDocument(String documentId, String displayName) throws FileNotFoundException {
        File f = file(documentId);
        File to = new File(f.getParentFile(), displayName);
        if (!f.renameTo(to))
            throw new FileNotFoundException("Cannot rename " + f);
        return docId(to);
    }

    @Override
    public boolean isChildDocument(String parentId, String documentId) {
        return documentId.startsWith(parentId + "/") || documentId.equals(parentId);
    }

    @Override
    public String getDocumentType(String documentId) throws FileNotFoundException {
        return mimeType(file(documentId));
    }

    private static String docId(File f) {
        return f.getAbsolutePath();
    }

    private File file(String docId) throws FileNotFoundException {
        File f = new File(docId);
        try {
            String canonical = f.getCanonicalPath();
            String root = home.getCanonicalPath();
            if (!canonical.equals(root) && !canonical.startsWith(root + "/"))
                throw new FileNotFoundException("Outside of home: " + docId);
        } catch (IOException e) {
            throw new FileNotFoundException(e.getMessage());
        }
        if (!f.exists())
            throw new FileNotFoundException(docId);
        return f;
    }

    private static String mimeType(File f) {
        if (f.isDirectory())
            return Document.MIME_TYPE_DIR;
        String name = f.getName();
        int dot = name.lastIndexOf('.');
        if (dot >= 0) {
            String ext = name.substring(dot + 1).toLowerCase();
            switch (ext) {
                case "apkg": case "colpkg": case "ankiaddon":
                    return "application/zip";
                default:
                    String t = MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext);
                    if (t != null)
                        return t;
            }
        }
        return "application/octet-stream";
    }

    private void addRow(MatrixCursor c, File f) {
        int flags = 0;
        if (f.canWrite()) {
            flags |= f.isDirectory() ? Document.FLAG_DIR_SUPPORTS_CREATE : Document.FLAG_SUPPORTS_WRITE;
            if (!f.equals(home))
                flags |= Document.FLAG_SUPPORTS_DELETE | Document.FLAG_SUPPORTS_RENAME;
        }
        c.newRow()
                .add(Document.COLUMN_DOCUMENT_ID, docId(f))
                .add(Document.COLUMN_DISPLAY_NAME, f.equals(home) ? getContext().getString(R.string.app_name) : f.getName())
                .add(Document.COLUMN_MIME_TYPE, mimeType(f))
                .add(Document.COLUMN_LAST_MODIFIED, f.lastModified())
                .add(Document.COLUMN_FLAGS, flags)
                .add(Document.COLUMN_SIZE, f.length());
    }
}
