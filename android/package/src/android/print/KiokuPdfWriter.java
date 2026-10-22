package android.print;

import android.os.CancellationSignal;
import android.os.ParcelFileDescriptor;

import java.io.File;
import java.io.IOException;

/**
 * Writes a web view's print document to a PDF file without the system print
 * dialog (Statistics' Save PDF). Lives in android.print because the layout
 * and write callbacks have package-private constructors.
 */
public class KiokuPdfWriter {
    public interface Done {
        void done(boolean ok);
    }

    public static void write(PrintDocumentAdapter adapter, File file, Done done) {
        PrintAttributes attributes = new PrintAttributes.Builder()
                .setMediaSize(PrintAttributes.MediaSize.ISO_A4)
                .setResolution(new PrintAttributes.Resolution("pdf", "pdf", 300, 300))
                .setMinMargins(PrintAttributes.Margins.NO_MARGINS)
                .build();
        adapter.onStart();
        adapter.onLayout(null, attributes, null, new PrintDocumentAdapter.LayoutResultCallback() {
            @Override
            public void onLayoutFinished(PrintDocumentInfo info, boolean changed) {
                ParcelFileDescriptor fd;
                try {
                    fd = ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_CREATE
                            | ParcelFileDescriptor.MODE_TRUNCATE | ParcelFileDescriptor.MODE_READ_WRITE);
                } catch (IOException e) {
                    finish(adapter, null, done, false);
                    return;
                }
                adapter.onWrite(new PageRange[] {PageRange.ALL_PAGES}, fd, new CancellationSignal(),
                        new PrintDocumentAdapter.WriteResultCallback() {
                            @Override
                            public void onWriteFinished(PageRange[] pages) {
                                finish(adapter, fd, done, true);
                            }

                            @Override
                            public void onWriteFailed(CharSequence error) {
                                finish(adapter, fd, done, false);
                            }

                            @Override
                            public void onWriteCancelled() {
                                finish(adapter, fd, done, false);
                            }
                        });
            }

            @Override
            public void onLayoutFailed(CharSequence error) {
                finish(adapter, null, done, false);
            }

            @Override
            public void onLayoutCancelled() {
                finish(adapter, null, done, false);
            }
        }, null);
    }

    private static void finish(PrintDocumentAdapter adapter, ParcelFileDescriptor fd, Done done, boolean ok) {
        if (fd != null) {
            try {
                fd.close();
            } catch (IOException ignored) {
            }
        }
        adapter.onFinish();
        done.done(ok);
    }
}
