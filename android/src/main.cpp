// Kioku for Android: Qt's activity runs this main() on Qt's thread. It starts
// an embedded CPython that runs the unmodified Anki desktop app (aqt). PyQt6,
// sip, the Rust extension modules and the Java bridge (_kioku_android) are
// linked into this library and registered as built-in modules; the standard
// library and Python code were unpacked by KiokuActivity.

#include <Python.h>

#include <QtGlobal>

#include <android/log.h>
#include <cstdlib>
#include <string>

extern "C" {
PyObject *PyInit_sip(void);
PyObject *PyInit_QtCore(void);
PyObject *PyInit_QtGui(void);
PyObject *PyInit_QtWidgets(void);
PyObject *PyInit_QtNetwork(void);
PyObject *PyInit_QtSvg(void);
PyObject *PyInit__rsbridge(void);
PyObject *PyInit_orjson(void);
PyObject *PyInit_rpds(void);
PyObject *PyInit__kioku_android(void);
}

static void fail(const char *what, PyStatus status) {
    __android_log_print(ANDROID_LOG_ERROR, "Kioku", "%s failed: %s", what,
                        status.err_msg ? status.err_msg : "?");
    std::exit(1);
}

static void append_path(PyConfig *config, const std::string &path) {
    wchar_t *w = Py_DecodeLocale(path.c_str(), nullptr);
    PyStatus status = PyWideStringList_Append(&config->module_search_paths, w);
    PyMem_RawFree(w);
    if (PyStatus_Exception(status)) fail("module path", status);
}

int main(int argc, char *argv[]) {
    const char *home_env = std::getenv("KIOKU_PYTHON_HOME");
    if (!home_env) {
        __android_log_print(ANDROID_LOG_ERROR, "Kioku", "KIOKU_PYTHON_HOME not set");
        return 1;
    }
    std::string home(home_env);
    // Qt's Android accessibility bridge blocks the UI thread on the Qt thread;
    // with an accessibility service enabled (a screen reader, a mirroring
    // tool) that deadlocks against the Java bridge and Qt aborts in its
    // deadlock protector. Anki's UI lives in native web views, which keep
    // their own accessibility; Qt's is switched off
    // (patches/qtforandroid-disable-accessibility.patch).
    setenv("QT_ANDROID_DISABLE_ACCESSIBILITY", "1", 1);

    PyImport_AppendInittab("PyQt6.sip", PyInit_sip);
    PyImport_AppendInittab("PyQt6.QtCore", PyInit_QtCore);
    PyImport_AppendInittab("PyQt6.QtGui", PyInit_QtGui);
    PyImport_AppendInittab("PyQt6.QtWidgets", PyInit_QtWidgets);
    PyImport_AppendInittab("PyQt6.QtNetwork", PyInit_QtNetwork);
    PyImport_AppendInittab("PyQt6.QtSvg", PyInit_QtSvg);
    PyImport_AppendInittab("anki._rsbridge", PyInit__rsbridge);
    PyImport_AppendInittab("orjson.orjson", PyInit_orjson);
    PyImport_AppendInittab("rpds", PyInit_rpds);
    PyImport_AppendInittab("_kioku_android", PyInit__kioku_android);

    PyPreConfig preconfig;
    PyPreConfig_InitIsolatedConfig(&preconfig);
    preconfig.utf8_mode = 1;
    PyStatus status = Py_PreInitialize(&preconfig);
    if (PyStatus_Exception(status)) fail("pre-init", status);

    PyConfig config;
    PyConfig_InitIsolatedConfig(&config);
    config.buffered_stdio = 0;
    config.write_bytecode = 0;
    config.install_signal_handlers = 1;

    wchar_t *whome = Py_DecodeLocale(home.c_str(), nullptr);
    status = PyConfig_SetString(&config, &config.home, whome);
    PyMem_RawFree(whome);
    if (PyStatus_Exception(status)) fail("home", status);

    std::string stdlib = home + "/lib/python" KIOKU_PYTHON_VERSION;  // from CMake
    config.module_search_paths_set = 1;
    append_path(&config, home + "/app");
    append_path(&config, home + "/app_packages");
    append_path(&config, stdlib);
    append_path(&config, stdlib + "/lib-dynload");

    status = PyConfig_SetBytesArgv(&config, argc, argv);
    if (PyStatus_Exception(status)) fail("argv", status);
    status = PyConfig_SetString(&config, &config.run_module, L"kioku");
    if (PyStatus_Exception(status)) fail("run_module", status);

    status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) fail("init", status);
    int result = Py_RunMain();
    // Python is finalized; Qt's Android plugin still logs while shutting down,
    // which must not reach a Python message handler (kioku.devtools)
    qInstallMessageHandler(nullptr);
    return result;
}
