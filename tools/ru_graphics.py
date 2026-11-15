"""RU fork: user-approved Russian sprite labels (PACKA textures) and the exe strings
that are drawn into textures next to them.

Data: tools/ru_graphics_data.json, produced by localization/graphics_ru/export_approved.py
from the numbered variants the user approved.  It holds finished palette indices, so the
build does not depend on fonts or on the review tools.

Every step is checked:
  * each texture is located in PACKA by its full TIM header + CLUT signature (one hit only);
  * the whole pixel block must hash to the stock SHA-256 before patching;
  * each rectangle must contain exactly the stock pixels (per-patch SHA-256), lie inside
    the texture and receive only indices 0-15 of the existing palette (CLUT is not touched);
  * after patching the block must hash to the recorded patched SHA-256;
  * exe strings are replaced only if the original bytes match and the length is unchanged.
"""
import hashlib
import json
from pathlib import Path

DATA = Path(__file__).with_name("ru_graphics_data.json")
EXE_LOAD = 0x80010000
EXE_HEADER = 0x800


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _rect_text(packa, pix, width, rect, bpp=4):
    x, y, w, h = rect
    rows = []
    if bpp == 8:
        for yy in range(y, y + h):
            rows.append("".join("%02x" % packa[pix + yy * width + xx] for xx in range(x, x + w)))
        return rows
    stride = width // 2
    for yy in range(y, y + h):
        row = []
        for xx in range(x, x + w):
            b = packa[pix + yy * stride + xx // 2]
            row.append("%x" % ((b >> 4) if xx & 1 else (b & 15)))
        rows.append("".join(row))
    return rows


def _write_rect(packa, pix, width, rect, rows, bpp=4):
    x, y, w, h = rect
    if bpp == 8:
        if len(rows) != h or any(len(r) != 2 * w for r in rows):
            raise SystemExit(f"RU graphics: patch rows do not match rect {rect}")
        for dy, row in enumerate(rows):
            packa[pix + (y + dy) * width + x:pix + (y + dy) * width + x + w] = bytes.fromhex(row)
        return
    stride = width // 2
    if len(rows) != h or any(len(r) != w for r in rows):
        raise SystemExit(f"RU graphics: patch rows do not match rect {rect}")
    for dy, row in enumerate(rows):
        for dx, ch in enumerate(row):
            v = int(ch, 16)
            xx, yy = x + dx, y + dy
            o = pix + yy * stride + xx // 2
            if xx & 1:
                packa[o] = (packa[o] & 0x0F) | (v << 4)
            else:
                packa[o] = (packa[o] & 0xF0) | v


def _find(packa, signature, name):
    sig = bytes.fromhex(signature)
    hits = []
    i = packa.find(sig)
    while i >= 0:
        hits.append(i)
        i = packa.find(sig, i + 1)
    if len(hits) != 1:
        raise SystemExit(f"RU graphics: texture '{name}' found {len(hits)} times in PACKA (need 1)")
    return hits[0]


def apply(packa, exe, data_path=DATA, log=print):
    if not Path(data_path).exists():
        log("  RU graphics: no approved data, skipped")
        return {}
    data = json.loads(Path(data_path).read_text(encoding="utf-8"))
    report = {}
    for atlas in data["atlases"]:
        name = atlas["name"]
        off = _find(packa, atlas["signature"], name)
        pix = off + len(bytes.fromhex(atlas["signature"]))
        width, height = atlas["width"], atlas["height"]
        bpp = atlas.get("bpp", 4)
        size = width * height * bpp // 8
        if _sha(bytes(packa[pix:pix + size])) != atlas["pixels_sha256_original"]:
            raise SystemExit(f"RU graphics: texture '{name}' at PACKA 0x{off:x} is not stock")
        for p in atlas["patches"]:
            x, y, w, h = p["rect"]
            if x < 0 or y < 0 or x + w > width or y + h > height:
                raise SystemExit(f"RU graphics: {p['id']} rect {p['rect']} outside {width}x{height}")
            cur = _rect_text(packa, pix, width, p["rect"], bpp)
            if _sha("\n".join(cur).encode()) != p["orig"]:
                raise SystemExit(f"RU graphics: {p['id']} rect {p['rect']} does not hold the expected pixels")
            _write_rect(packa, pix, width, p["rect"], p["rows"], bpp)
        if _sha(bytes(packa[pix:pix + size])) != atlas["pixels_sha256_patched"]:
            raise SystemExit(f"RU graphics: texture '{name}' result hash mismatch")
        report[name] = len(atlas["patches"])
        log(f"  RU graphics: {name} @PACKA 0x{off:x}: {len(atlas['patches'])} labels")
    for s in data.get("exe", []):
        addr = int(s["address"], 16)
        o = addr - EXE_LOAD + EXE_HEADER
        old, new = bytes.fromhex(s["original"]), bytes.fromhex(s["new"])
        if len(old) != len(new):
            raise SystemExit(f"RU graphics: {s['id']} exe string length changes")
        if bytes(exe[o:o + len(old)]) != old:
            raise SystemExit(f"RU graphics: {s['id']} exe bytes at {addr:#x} are not the expected original")
        exe[o:o + len(new)] = new
        log(f"  RU graphics: exe {addr:#x} {s['what']}")
    for g in data.get("font10", []):
        _set_glyph10(exe, int(g["code"], 16), g["original_bits"], g["new_bits"], g["id"])
    if data.get("font10"):
        log(f"  RU graphics: {len(data['font10'])} heavy 10x10 glyphs for the greyed confirm options")
    return report


def apply_overlay(name, buf, entries, log=print):
    """Overlay file bytes (e.g. 3DMAP.BIN), applied after the text patcher of that file:
    each entry replaces bytes at a file offset only if the original bytes match."""
    buf = bytearray(buf)
    for s in entries:
        o = int(s["offset"], 16)
        old, new = bytes.fromhex(s["original"]), bytes.fromhex(s["new"])
        if len(old) != len(new):
            raise SystemExit(f"RU graphics: {name} {s['id']} length changes")
        if bytes(buf[o:o + len(old)]) != old:
            raise SystemExit(f"RU graphics: {name} +0x{o:x} is not the expected original ({s['id']})")
        buf[o:o + len(new)] = new
    log(f"  RU graphics: {name}: {len(entries)} patches ({', '.join(sorted(set(e['what'] for e in entries)))})")
    return bytes(buf)


FONT10 = 0x800D25D8   # 10x10 font, 100 bits per glyph, SJIS rows 0x81-0x83


def _sidx(code):
    b1, b2 = code >> 8, code & 0xFF
    row = (b1 - 0x81) if b1 < 0xA0 else (b1 - 0xC1)
    return (b2 - 0x40) + row * 189


def _set_glyph10(exe, code, original_bits, new_bits, ident):
    if len(original_bits) != 100 or len(new_bits) != 100:
        raise SystemExit(f"RU graphics: {ident} 10x10 glyph must have 100 bits")
    base = FONT10 - EXE_LOAD + EXE_HEADER
    start = _sidx(code) * 100
    cur = "".join(str((exe[base + ((start + k) >> 3)] >> (7 - ((start + k) & 7))) & 1) for k in range(100))
    if cur != original_bits:
        raise SystemExit(f"RU graphics: {ident} glyph 0x{code:04X} is not the expected original")
    for k, ch in enumerate(new_bits):
        o = base + ((start + k) >> 3)
        mask = 1 << (7 - ((start + k) & 7))
        exe[o] = (exe[o] | mask) if ch == "1" else (exe[o] & ~mask & 0xFF)
