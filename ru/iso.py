"""Minimal ISO9660 reader for MODE2/2352 PSX BIN images (list / extract files).

    python ru/iso.py --input game.bin --list
    python ru/iso.py --input game.bin --extract outdir
"""
import argparse
import struct
from pathlib import Path

SECTOR = 2352


def sector(data, lba):
    o = lba * SECTOR + 24
    return data[o:o + 2048]


def read_extent(data, lba, size):
    out = bytearray()
    n = (size + 2047) // 2048
    for i in range(n):
        out += sector(data, lba + i)
    return bytes(out[:size])


def walk(data):
    pvd = sector(data, 16)
    if pvd[1:6] != b"CD001":
        raise SystemExit("not an ISO9660 image")
    root = pvd[156:156 + 34]
    stack = [("", struct.unpack_from("<I", root, 2)[0], struct.unpack_from("<I", root, 10)[0])]
    seen = set()
    while stack:
        path, lba, size = stack.pop()
        if lba in seen:
            continue
        seen.add(lba)
        d = read_extent(data, lba, size)
        pos = 0
        while pos < len(d):
            n = d[pos]
            if n == 0:
                pos = (pos // 2048 + 1) * 2048
                continue
            rec = d[pos:pos + n]
            elba = struct.unpack_from("<I", rec, 2)[0]
            esize = struct.unpack_from("<I", rec, 10)[0]
            flags = rec[25]
            nl = rec[32]
            name = rec[33:33 + nl]
            pos += n
            if name in (b"\x00", b"\x01"):
                continue
            name = name.decode("ascii", "replace").split(";")[0]
            full = f"{path}/{name}"
            if flags & 2:
                stack.append((full, elba, esize))
            else:
                yield full, elba, esize


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--extract")
    args = ap.parse_args(argv)
    data = Path(args.input).read_bytes()
    files = sorted(walk(data), key=lambda f: f[1])
    for path, lba, size in files:
        if args.list:
            print(f"{lba:7d} {size:10d} {path}")
        if args.extract:
            out = Path(args.extract) / path.lstrip("/")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(read_extent(data, lba, size))
    if args.extract:
        print(f"{len(files)} files -> {args.extract}")


if __name__ == "__main__":
    main()
