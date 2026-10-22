// _kioku_android: the bridge between Kioku's Python code and its Java side
// (io.ankidesk.kioku.KiokuBridge).
//
//   call(method: str, args_json: str) -> str   KiokuBridge.call(), any thread
//   view_handle(id: int) -> int                a global ref to the web view's
//                                              View, for QWindow.fromWinId()
//   set_handler(callable)                      receives KiokuBridge events (a
//                                              JSON string) on Qt's main thread

#include <Python.h>

#include <QCoreApplication>
#include <QJniEnvironment>
#include <QJniObject>
#include <QMetaObject>
#include <QString>

#include <android/log.h>

static const char *BRIDGE = "io/ankidesk/kioku/KiokuBridge";
static PyObject *event_handler = nullptr;

static void native_event(JNIEnv *env, jclass, jstring json) {
    const char *utf8 = env->GetStringUTFChars(json, nullptr);
    QByteArray copy(utf8);
    env->ReleaseStringUTFChars(json, utf8);
    QCoreApplication *app = QCoreApplication::instance();
    if (!app) {
        __android_log_print(ANDROID_LOG_WARN, "Kioku", "event before the app exists");
        return;
    }
    QMetaObject::invokeMethod(app, [copy]() {
        PyGILState_STATE gil = PyGILState_Ensure();
        if (event_handler) {
            PyObject *result = PyObject_CallFunction(event_handler, "s", copy.constData());
            if (!result) {
                PyErr_Print();
            }
            Py_XDECREF(result);
        }
        PyGILState_Release(gil);
    }, Qt::QueuedConnection);
}

static PyObject *py_call(PyObject *, PyObject *args) {
    const char *method;
    const char *json;
    if (!PyArg_ParseTuple(args, "ss", &method, &json)) {
        return nullptr;
    }
    QString result;
    // the Java side may wait for Android's UI thread
    Py_BEGIN_ALLOW_THREADS
    QJniObject r = QJniObject::callStaticMethod<jstring>(
        BRIDGE, "call", "(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;",
        QJniObject::fromString(QString::fromUtf8(method)).object<jstring>(),
        QJniObject::fromString(QString::fromUtf8(json)).object<jstring>());
    result = r.toString();
    Py_END_ALLOW_THREADS
    QByteArray utf8 = result.toUtf8();
    return PyUnicode_FromStringAndSize(utf8.constData(), utf8.size());
}

static PyObject *py_view_handle(PyObject *, PyObject *args) {
    int id;
    if (!PyArg_ParseTuple(args, "i", &id)) {
        return nullptr;
    }
    QJniObject view = QJniObject::callStaticObjectMethod(
        BRIDGE, "getView", "(I)Landroid/view/View;", jint(id));
    if (!view.isValid()) {
        Py_RETURN_NONE;
    }
    QJniEnvironment env;
    jobject global = env->NewGlobalRef(view.object());
    return PyLong_FromVoidPtr(global);
}

static PyObject *py_set_handler(PyObject *, PyObject *args) {
    PyObject *handler;
    if (!PyArg_ParseTuple(args, "O", &handler)) {
        return nullptr;
    }
    Py_XINCREF(handler);
    Py_XSETREF(event_handler, handler);
    Py_RETURN_NONE;
}

static PyMethodDef methods[] = {
    {"call", py_call, METH_VARARGS, "Call KiokuBridge.call(method, args_json)."},
    {"view_handle", py_view_handle, METH_VARARGS, "Global ref to a web view's View."},
    {"set_handler", py_set_handler, METH_VARARGS, "Set the event callback."},
    {nullptr, nullptr, 0, nullptr},
};

static PyModuleDef module = {
    PyModuleDef_HEAD_INIT, "_kioku_android", nullptr, -1, methods,
};

extern "C" PyObject *PyInit__kioku_android(void) {
    QJniEnvironment env;
    const JNINativeMethod natives[] = {
        {"nativeEvent", "(Ljava/lang/String;)V", reinterpret_cast<void *>(native_event)},
    };
    if (!env.registerNativeMethods(BRIDGE, natives, 1)) {
        PyErr_SetString(PyExc_ImportError, "cannot register KiokuBridge.nativeEvent");
        return nullptr;
    }
    return PyModule_Create(&module);
}
