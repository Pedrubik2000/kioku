#!/usr/bin/env python3
"""Unpack Termux .deb files into a prefix tree for tools/build_rootfs.py.

Use this with packages built by tools/build-termux-packages.sh, which already
contain /data/data/<package>/files/usr paths, so no patching is needed.

  tools/debs_to_prefix.py --package io.ankidesk \
      --debs /path/to/termux-packages/output --out build/rootfs-native
  # -> build/rootfs-native/usr, build/rootfs-native/file-owners.tsv
"""
import argparse
import io
import os
import shutil
import tarfile


def ar_members(path):
    with open(path, "rb") as fh:
        if fh.read(8) != b"!<arch>\n":
            raise ValueError(f"{path} is not an ar archive")
        while True:
            header = fh.read(60)
            if len(header) < 60:
                return
            name = header[:16].decode().strip().rstrip("/")
            size = int(header[48:58].decode().strip())
            data = fh.read(size)
            if size % 2:
                fh.read(1)
            yield name, data


def control_field(control_tar, field):
    with tarfile.open(fileobj=io.BytesIO(control_tar)) as t:
        for m in t.getmembers():
            if os.path.basename(m.name) == "control":
                for line in t.extractfile(m).read().decode().splitlines():
                    if line.startswith(field + ":"):
                        return line.split(":", 1)[1].strip()
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True, help="Android package the debs were built for")
    ap.add_argument("--debs", required=True, help="directory containing .deb files")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    root = f"data/data/{a.package}/files/usr/"
    usr = os.path.join(a.out, "usr")
    if os.path.exists(a.out):
        shutil.rmtree(a.out)
    os.makedirs(usr)

    debs = sorted(f for f in os.listdir(a.debs) if f.endswith(".deb"))
    if not debs:
        raise SystemExit(f"no .deb files in {a.debs}")
    with open(os.path.join(a.out, "file-owners.tsv"), "w", encoding="utf-8") as owners:
        for deb in debs:
            members = dict(ar_members(os.path.join(a.debs, deb)))
            control = next(v for k, v in members.items() if k.startswith("control.tar"))
            data = next(v for k, v in members.items() if k.startswith("data.tar"))
            pkg = control_field(control, "Package")
            with tarfile.open(fileobj=io.BytesIO(data)) as t:
                for m in t.getmembers():
                    name = m.name.lstrip("./")
                    if not name.startswith(root):
                        if m.isfile():
                            raise SystemExit(f"{deb}: {m.name} is outside {root}; "
                                             f"was it built for another package name?")
                        continue
                    rel = name[len(root):]
                    if not rel:
                        continue
                    m.name = rel
                    t.extract(m, usr, set_attrs=True, filter="tar")
                    if not m.isdir():
                        owners.write(f"{pkg}\t{rel}\n")
            print(f"{pkg:40s} {deb}")
    print(f"{len(debs)} packages -> {usr}")


if __name__ == "__main__":
    main()
