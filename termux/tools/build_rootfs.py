#!/usr/bin/env python3
"""Turn a Termux prefix snapshot into the bootstrap archive shipped in the APK.

Steps:
  1. copy the pulled prefix into a staging dir
  2. drop packages and paths that Anki does not need at runtime
  3. verify every ELF's DT_NEEDED still resolves (prefix or Android system libs)
  4. rewrite the hardcoded Termux rootfs (/data/data/com.termux/files) to the
     app's own (/data/data/<package>/<rootfs-dir>); same-length replacement, so
     ELF offsets stay valid. A package name one character longer than
     com.termux takes the rootfs dir "file", two longer "fil", and so on.
  5. write a zip + SYMLINKS.txt + EXECUTABLES.txt for the app to extract

Usage:
  build_rootfs.py --src build/rootfs-pulled/usr --owners build/file-owners.tsv \
                  --extra rootfs-overlay --package io.ankidesk --rootfs-dir file \
                  --out app/src/main/assets/bootstrap-aarch64.zip
"""
import argparse
import os
import re
import shutil
import stat
import struct
import sys
import zipfile
from collections import Counter, defaultdict

OLD_ROOT = b"/data/data/com.termux"
OLD_ROOT_USER = b"/data/user/0/com.termux"
OLD_ROOTFS = OLD_ROOT + b"/files"
OLD_ROOTFS_USER = OLD_ROOT_USER + b"/files"

# Whole packages that are only pulled in through build-time or desktop
# integration dependencies (xdg-utils, mesa's llvmpipe, gstreamer backend ...).
DROP_PACKAGES = {
    "perl", "make", "make-guile", "xdg-utils", "desktop-file-utils", "file",
    "libllvm", "mesa", "mesa-vulkan-icd-swrast", "vulkan-icd",
    "gstreamer", "gst-plugins-base", "gst-plugins-bad", "gst-libav",
    "shared-mime-info", "xorg-xprop", "geoclue", "libnotify", "libsoup3",
    "json-glib", "libpsl",
}

# Paths (relative to usr/) that are never needed at runtime.
DROP_PATTERNS = [
    r"^include/", r"\.a$", r"\.la$", r"\.prl$",
    r"^share/(doc|man|info|locale|gtk-doc|devhelp|bash-completion|zsh|fish|aclocal|pkgconfig|vala|gir-1\.0|applications|metainfo|icons/(?!hicolor/128x128/apps/anki))/",
    r"^lib/(cmake|pkgconfig|girepository-1\.0)/",
    r"^lib/qt6/(mkspecs|metatypes|modules|sbom)/",
    r"^lib/qt6/plugins/(designer|qmltooling|printsupport/libcups|multimedia/libgstreamer|sqldrivers/libqsql(?!ite))",
    r"^lib/qt6/(bin|libexec)/(?!QtWebEngineProcess)",
    r"^lib/qt6/[^/]*\.(sh)$",
    r"^bin/(designer|linguist|assistant|qdbus|qtdiag6?|qtpaths6?|lupdate|lrelease|lconvert|pixeltool|qdistancefieldgenerator|qmlls|qml|qmlscene|qmlplugindump|qmleasing|qmlpreview|qmlprofiler|qmltestrunner|qmltime|uic|rcc|moc|ffplay|ffprobe|x26[45]|cjxl|djxl|cjpegli|djpegli|jxlinfo|tiff.*|openssl|c_rehash|k(init|list|destroy|passwd|su|switch|tutil|vno|5srvutil|admin.*|db5_util|propd|proplog)|gst-.*|pa(cat|cmd|ctl|mon|play|rec|record|split|-info)|pulseaudio|esdcompat|start-pulseaudio-x11)$",
    r"^share/qt6/translations/qtwebengine_locales/(?!en-US)",
    r"^share/qt6/resources/qtwebengine_devtools_resources",
    r"^share/qt6/(phrasebooks|doc)/",
    r"^lib/python3\.\d+/(test|idlelib|tkinter|turtledemo|ensurepip|lib2to3|config-3\.\d+-[^/]*|pydoc_data)/",
    r"^lib/python3\.\d+/site-packages/PyQt6/(bindings|uic|lupdate)/",
    r"^lib/python3\.\d+/site-packages/PyQt6/.*\.pyi$",
    r"^lib/python3\.\d+/site-packages/.*/tests?/",
    r"^var/(cache|lib/dpkg|lib/apt|log)/",
    r"^(libexec|share)/installed-tests/",
    r"^etc/apt/",
]

# Libraries provided by Android itself.
SYSTEM_LIBS = {
    "libc.so", "libm.so", "libdl.so", "liblog.so", "libandroid.so", "libEGL.so",
    "libGLESv1_CM.so", "libGLESv2.so", "libGLESv3.so", "libvulkan.so", "libz.so",
    "libjnigraphics.so", "libmediandk.so", "libOpenSLES.so", "libaaudio.so",
    "libnativewindow.so", "libsync.so", "libcamera2ndk.so", "libbinder_ndk.so",
    "libstdc++.so", "libicu.so", "libamidi.so", "libneuralnetworks.so",
}

# Files kept even though their package is dropped: linked (not just
# dlopened) by libraries we ship.
KEEP_PATTERNS = [
    r"^lib/libgbm\.so",
]

DROP_RE = re.compile("|".join(DROP_PATTERNS))
KEEP_RE = re.compile("|".join(KEEP_PATTERNS))


def elf_needed(path):
    """Return (is_elf, [DT_NEEDED], soname) for a 64-bit little-endian ELF."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(64)
            if len(head) < 64 or head[:4] != b"\x7fELF" or head[4] != 2:
                return False, [], None
            phoff, = struct.unpack_from("<Q", head, 0x20)
            phentsize, phnum = struct.unpack_from("<HH", head, 0x36)
            fh.seek(phoff)
            ph = fh.read(phentsize * phnum)
            loads, dyn = [], None
            for i in range(phnum):
                p_type, _, p_offset, p_vaddr, _, p_filesz, _, _ = struct.unpack_from("<IIQQQQQQ", ph, i * phentsize)
                if p_type == 1:
                    loads.append((p_vaddr, p_offset, p_filesz))
                elif p_type == 2:
                    dyn = (p_offset, p_filesz)
            if not dyn:
                return True, [], None
            fh.seek(dyn[0])
            data = fh.read(dyn[1])
            entries, strtab = [], None
            for i in range(0, len(data) - 15, 16):
                tag, val = struct.unpack_from("<qQ", data, i)
                if tag == 0:
                    break
                if tag == 5:
                    strtab = val
                entries.append((tag, val))

            def v2o(addr):
                for vaddr, off, size in loads:
                    if vaddr <= addr < vaddr + size:
                        return addr - vaddr + off
                return None

            if strtab is None or v2o(strtab) is None:
                return True, [], None
            base = v2o(strtab)

            def rd(off):
                fh.seek(base + off)
                out = b""
                while True:
                    chunk = fh.read(64)
                    if not chunk:
                        break
                    idx = chunk.find(b"\0")
                    if idx >= 0:
                        out += chunk[:idx]
                        break
                    out += chunk
                return out.decode("utf-8", "replace")

            needed = [rd(v) for t, v in entries if t == 1]
            soname = next((rd(v) for t, v in entries if t == 14), None)
            return True, needed, soname
    except OSError:
        return False, [], None


def walk(root):
    for d, dirs, files in os.walk(root):
        for name in files + [x for x in dirs if os.path.islink(os.path.join(d, x))]:
            full = os.path.join(d, name)
            yield os.path.relpath(full, root), full


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--owners", required=True)
    ap.add_argument("--extra", action="append", default=[],
                    help="dir overlaid on top of the prefix (launch scripts, configs, Python deps); repeatable")
    ap.add_argument("--package", required=True)
    ap.add_argument("--rootfs-dir", default="files",
                    help="name of the rootfs dir in the app's data dir (files for Termux)")
    ap.add_argument("--stage", default="build/rootfs-stage")
    ap.add_argument("--out", required=True)
    ap.add_argument("--keep-going", action="store_true")
    a = ap.parse_args()

    new_root = f"/data/data/{a.package}".encode()
    new_rootfs = f"/data/data/{a.package}/{a.rootfs_dir}".encode()
    new_rootfs_user = f"/data/user/0/{a.package}/{a.rootfs_dir}".encode()
    # Stock Termux packages can only be retargeted when the new path has the
    # same length. Packages built with TERMUX_APP__PACKAGE_NAME=<package>
    # already contain the right path and need no patching.
    can_patch = len(new_rootfs) == len(OLD_ROOTFS)
    # A bare app data dir (no /files after it) only keeps its length for a
    # 10-character name. Only termux-exec has one, as a default it takes from
    # TERMUX_APP__DATA_DIR at run time (Prefix.environment()).
    unpatched_bare = []

    owners = defaultdict(set)
    for line in open(a.owners, encoding="utf-8"):
        pkg, _, path = line.rstrip("\n").partition("\t")
        owners[path].add(pkg)

    if os.path.exists(a.stage):
        shutil.rmtree(a.stage)
    shutil.copytree(a.src, a.stage, symlinks=True)
    for extra in a.extra:
        shutil.copytree(extra, a.stage, symlinks=True, dirs_exist_ok=True)

    removed = Counter()
    for rel, full in list(walk(a.stage)):
        pk = owners.get(rel, set())
        if ((pk and pk <= DROP_PACKAGES) or DROP_RE.search(rel)) and not KEEP_RE.search(rel):
            size = os.lstat(full).st_size
            os.unlink(full)
            removed["/".join(sorted(pk)) or "path-rule"] += size
    for d, dirs, files in os.walk(a.stage, topdown=False):
        if not os.listdir(d) and d != a.stage:
            os.rmdir(d)
    print(f"removed {sum(removed.values()) / 2**20:.1f} MiB")
    for k, v in removed.most_common(12):
        print(f"  {v / 2**20:7.1f} MiB  {k}")

    # Library resolution check. Search path mirrors the runtime LD_LIBRARY_PATH.
    present = set()
    for rel, full in walk(a.stage):
        if rel.startswith("lib/") and rel.count("/") == 1:
            present.add(os.path.basename(rel))
    present |= SYSTEM_LIBS
    missing = defaultdict(list)
    for rel, full in walk(a.stage):
        if os.path.islink(full):
            continue
        is_elf, needed, _ = elf_needed(full)
        for n in needed:
            if n not in present and not (n.startswith("/") and os.path.exists(a.stage + n.split("/files/usr", 1)[-1])):
                missing[n].append(rel)
    if missing:
        print("UNRESOLVED DT_NEEDED:")
        for lib, users in sorted(missing.items()):
            print(f"  {lib}  <- {', '.join(users[:4])}{' ...' if len(users) > 4 else ''}")
        if not a.keep_going:
            sys.exit(1)

    # Patch the prefix and collect metadata.
    patched = 0
    symlinks, executables = [], []
    for rel, full in sorted(walk(a.stage)):
        if os.path.islink(full):
            target = os.readlink(full)
            target = target.replace(OLD_ROOTFS.decode(), new_rootfs.decode())
            symlinks.append(f"{target}←{rel}")
            continue
        st = os.stat(full)
        if st.st_mode & stat.S_IXUSR:
            executables.append(rel)
        with open(full, "rb") as fh:
            data = fh.read()
        if new_rootfs != OLD_ROOTFS and (OLD_ROOT in data or OLD_ROOT_USER in data):
            if not can_patch:
                sys.exit(f"{rel} contains {OLD_ROOTFS.decode()}, which can only be rewritten to a path "
                         f"of the same length; {new_rootfs.decode()} is not. Pick --rootfs-dir to fit, "
                         f"or build the packages with TERMUX_APP__PACKAGE_NAME={a.package}.")
            data = data.replace(OLD_ROOTFS, new_rootfs).replace(OLD_ROOTFS_USER, new_rootfs_user)
            if len(new_root) == len(OLD_ROOT):
                data = data.replace(OLD_ROOT, new_root).replace(OLD_ROOT_USER, new_root.replace(b"/data/data/", b"/data/user/0/"))
            for m in re.finditer(re.escape(OLD_ROOT) + b"|" + re.escape(OLD_ROOT_USER), data):
                if data[m.end():m.end() + 1] == b"/":
                    sys.exit(f"{rel} has a path under {m.group().decode()} outside files/, "
                             f"which cannot be rewritten in place")
                unpatched_bare.append(rel)
            with open(full, "wb") as fh:
                fh.write(data)
            patched += 1
    print(f"patched prefix in {patched} files, {len(symlinks)} symlinks, {len(executables)} executables")
    for rel in sorted(set(unpatched_bare)):
        print(f"  kept the bare {OLD_ROOT.decode()} in {rel} (set from the environment at run time)")

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    tmp = a.out + ".tmp"
    regular = [(rel, full) for rel, full in sorted(walk(a.stage)) if not os.path.islink(full)]
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        # First entry, so the app can check the package and size the progress bar
        # before unpacking anything.
        z.writestr("MANIFEST.txt", f"package={a.package}\nrootfs={a.rootfs_dir}\nbytes={sum(os.path.getsize(f) for _, f in regular)}\n"
                                   f"files={len(regular)}\n")
        for rel, full in sorted(walk(a.stage)):
            if not os.path.islink(full):
                z.write(full, rel)
        z.writestr("SYMLINKS.txt", "\n".join(symlinks) + "\n")
        z.writestr("EXECUTABLES.txt", "\n".join(executables) + "\n")
    os.replace(tmp, a.out)
    total = sum(os.lstat(f).st_size for _, f in walk(a.stage))
    print(f"staged {total / 2**20:.1f} MiB -> {a.out} {os.path.getsize(a.out) / 2**20:.1f} MiB")


if __name__ == "__main__":
    main()
