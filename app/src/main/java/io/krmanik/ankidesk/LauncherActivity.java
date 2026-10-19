package io.krmanik.ankidesk;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Build;
import android.os.Bundle;
import android.text.format.Formatter;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;

import com.termux.x11.MainActivity;

/**
 * The only launcher entry: one tap starts (or resumes) Anki. Shows unpack and
 * start-up progress, then hands over to the X11 display. If something fails it
 * stays up with the reason, the log tail and ways to recover.
 */
public class LauncherActivity extends Activity implements Session.Listener {
    private TextView status;
    private TextView detail;
    private ProgressBar bar;
    private View errorPanel;
    private TextView errorLog;
    private boolean displayOpened;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 0);
        buildUi();
    }

    @Override
    protected void onResume() {
        super.onResume();
        displayOpened = false;
        Session.addListener(this);
        if (Session.state == Session.State.READY) {
            openDisplay();
        } else if (Session.state == Session.State.FAILED) {
            onSessionChanged();
        } else {
            start(false, false);
        }
    }

    @Override
    protected void onPause() {
        Session.removeListener(this);
        super.onPause();
    }

    private void start(boolean safeMode, boolean reset) {
        if (!Session.isAlive())
            Session.set(Session.State.STARTING, "Starting…");
        Intent service = new Intent(this, AnkiService.class)
                .setAction(AnkiService.ACTION_START)
                .putExtra(AnkiService.EXTRA_SAFE_MODE, safeMode)
                .putExtra(AnkiService.EXTRA_RESET, reset);
        startForegroundService(service);
        onSessionChanged();
    }

    @Override
    public void onSessionChanged() {
        Session.State s = Session.state;
        errorPanel.setVisibility(s == Session.State.FAILED ? View.VISIBLE : View.GONE);
        switch (s) {
            case INSTALLING: {
                Prefix.Progress p = Session.progress;
                status.setText(p == null || p.stage == null ? "Preparing…" : p.stage + (p != null && "Unpacking".equals(p.stage) ? " Anki (first launch only)" : ""));
                if (p != null && p.bytesTotal > 0) {
                    int pct = (int) (p.bytesDone * 100 / p.bytesTotal);
                    bar.setIndeterminate(false);
                    bar.setProgress(pct);
                    String eta = p.etaMillis >= 0 ? " · about " + Math.max(1, (p.etaMillis + 999) / 1000) + " s left" : "";
                    detail.setText(pct + "%  ·  " + Formatter.formatShortFileSize(this, p.bytesDone) + " of "
                            + Formatter.formatShortFileSize(this, p.bytesTotal) + "  ·  "
                            + p.filesDone + " / " + p.filesTotal + " files" + eta);
                } else {
                    bar.setIndeterminate(true);
                    detail.setText("");
                }
                break;
            }
            case STARTING:
            case IDLE:
                bar.setIndeterminate(true);
                status.setText(Session.message.isEmpty() ? "Starting Kioku…" : Session.message);
                detail.setText("");
                break;
            case READY:
                openDisplay();
                break;
            case FAILED:
                bar.setIndeterminate(false);
                bar.setProgress(0);
                status.setText(Session.message);
                detail.setText("");
                errorLog.setText(Session.log);
                break;
        }
    }

    private void openDisplay() {
        if (displayOpened)
            return;
        displayOpened = true;
        startActivity(new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
        finish();
    }

    private void shareLog() {
        Intent send = new Intent(Intent.ACTION_SEND)
                .setType("text/plain")
                .putExtra(Intent.EXTRA_SUBJECT, getString(R.string.app_name) + " log")
                .putExtra(Intent.EXTRA_TEXT, Session.message + "\n\n" + Session.log);
        startActivity(Intent.createChooser(send, "Share log"));
    }

    private void buildUi() {
        float dp = getResources().getDisplayMetrics().density;
        int pad = (int) (24 * dp);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        root.setPadding(pad, pad * 3, pad, pad);
        root.setBackgroundColor(Color.parseColor("#1B2430"));

        ImageView icon = new ImageView(this);
        icon.setImageResource(R.mipmap.ic_launcher);
        root.addView(icon, new LinearLayout.LayoutParams((int) (96 * dp), (int) (96 * dp)));

        TextView title = text(getString(R.string.app_name), 24, Color.WHITE);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setPadding(0, pad, 0, pad / 2);
        root.addView(title);

        status = text("", 16, Color.parseColor("#DDE6F0"));
        root.addView(status);

        bar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        bar.setMax(100);
        bar.setIndeterminate(true);
        LinearLayout.LayoutParams barLp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        barLp.topMargin = pad / 2;
        root.addView(bar, barLp);

        detail = text("", 13, Color.parseColor("#9FB0C3"));
        root.addView(detail);

        LinearLayout err = new LinearLayout(this);
        err.setOrientation(LinearLayout.VERTICAL);
        err.setPadding(0, pad, 0, 0);
        errorPanel = err;

        LinearLayout row1 = new LinearLayout(this);
        row1.addView(button("Retry", v -> start(false, false)), weight());
        row1.addView(button("Safe mode", v -> start(true, false)), weight());
        err.addView(row1);
        LinearLayout row2 = new LinearLayout(this);
        row2.addView(button("Repair runtime", v -> start(false, true)), weight());
        row2.addView(button("Share log", v -> shareLog()), weight());
        err.addView(row2);

        TextView hint = text("Safe mode starts Anki without add-ons. Repair unpacks the runtime again; your decks are kept.", 12, Color.parseColor("#9FB0C3"));
        hint.setPadding(0, pad / 2, 0, pad / 2);
        err.addView(hint);

        errorLog = text("", 11, Color.parseColor("#C8D3DF"));
        errorLog.setGravity(Gravity.START);
        errorLog.setTypeface(Typeface.MONOSPACE);
        errorLog.setTextIsSelectable(true);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(errorLog);
        err.addView(scroll, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        root.addView(err, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        err.setVisibility(View.GONE);

        setContentView(root);
    }

    private TextView text(String s, int sp, int color) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(sp);
        t.setTextColor(color);
        t.setGravity(Gravity.CENTER);
        return t;
    }

    private Button button(String label, View.OnClickListener l) {
        Button b = new Button(this);
        b.setText(label);
        b.setAllCaps(false);
        b.setOnClickListener(l);
        return b;
    }

    private static LinearLayout.LayoutParams weight() {
        return new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1);
    }
}
