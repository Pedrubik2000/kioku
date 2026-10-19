package io.ankidesk;

import android.os.Handler;
import android.os.Looper;

import java.util.concurrent.CopyOnWriteArrayList;

/** State of the Anki session, shared between {@link AnkiService} and the activities. */
final class Session {
    enum State {
        /** Nothing running. */
        IDLE,
        /** Unpacking the runtime. {@link #progress} is set. */
        INSTALLING,
        /** X server or Anki starting. */
        STARTING,
        /** Anki's main window is up. */
        READY,
        /** Gave up; {@link #message} and {@link #log} say why. */
        FAILED,
    }

    interface Listener {
        void onSessionChanged();
    }

    static volatile State state = State.IDLE;
    static volatile String message = "";
    static volatile String log = "";
    static volatile Prefix.Progress progress;

    private static final CopyOnWriteArrayList<Listener> listeners = new CopyOnWriteArrayList<>();
    private static final Handler main = new Handler(Looper.getMainLooper());

    private Session() {
    }

    static void set(State s, String msg) {
        state = s;
        message = msg == null ? "" : msg;
        if (s != State.INSTALLING)
            progress = null;
        notifyListeners();
    }

    static void fail(String msg, String logTail) {
        log = logTail == null ? "" : logTail;
        set(State.FAILED, msg);
    }

    static void installing(Prefix.Progress p) {
        progress = p;
        state = State.INSTALLING;
        notifyListeners();
    }

    static boolean isAlive() {
        return state == State.INSTALLING || state == State.STARTING || state == State.READY;
    }

    static void addListener(Listener l) {
        listeners.add(l);
    }

    static void removeListener(Listener l) {
        listeners.remove(l);
    }

    private static void notifyListeners() {
        main.post(() -> {
            for (Listener l : listeners)
                l.onSessionChanged();
        });
    }
}
