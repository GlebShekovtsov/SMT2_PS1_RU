"""RU fork: Russian character grid for the naming screen.

Replaces the English layout of tools/name_entry.py (same three pieces: selection
table in the exe, END-row / scroll constants, pre-rendered grid atlas in PACKA).
Only the layout chosen by the user (key "name_entry" in ru_graphics_data.json) is used.

Letters are stored as the RU build's Cyrillic SJIS codes (hiragana cells 0x829F+i),
so entered names print with the same Cyrillic glyphs as the rest of the text.  The grid
atlas is drawn from the stock JIS Cyrillic block of the pristine 12x12 font (centred
glyphs, like the stock kana), index 1 over an index-2 shadow at (+1,+1).
"""
import hashlib
import struct

import build_en_tree as ET
import cyrillic as CY
import name_entry as NE

UP = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
LO = UP.lower()


def _blocks(letters):
    return [letters[i:i + 5].ljust(5) for i in range(0, len(letters), 5)]


def _layout_cyr():
    right = ["012", "345", "678", "9?!", "'-.", "   ", "   "]
    rows = [u + l + r for u, l, r in zip(_blocks(UP), _blocks(LO), right)]
    return rows                                    # 7 rows, END on row 6


def _layout_cyr_lat():
    rows = _layout_cyr()
    latin = [row[:10] + "   " for row in NE.LAYOUT[:6]]    # Latin rows without the digits
    return rows + latin                            # 13 rows, END on row 12


LAYOUTS = {"N1": _layout_cyr, "N2": _layout_cyr_lat}


def layout(variant):
    rows = LAYOUTS[variant]()
    rows = rows + [" " * NE.COLS] * (NE.ROWS - len(rows))
    for r in rows:
        assert len(r) == NE.COLS, r
    return rows


def end_row(variant):
    return len(LAYOUTS[variant]()) - 1


def build_table(variant):
    out = bytearray()
    for row in layout(variant):
        for ch in row:
            out += struct.pack(">H", ET.fullwidth(ch))
        out += b"\x00\x00"
    return bytes(out)


def apply_name_entry(exe, variant):
    cfg = _cfg(variant)
    variant = cfg["layout"]
    lab = cfg.get("label")               # approved replacement of the "NAME:" string
    if lab:
        o = int(lab["address"], 16) - NE.PSX_EXE_LOAD + NE.PSX_EXE_HEADER
        old, new = bytes.fromhex(lab["original"]), bytes.fromhex(lab["new"])
        if len(old) != len(new) or bytes(exe[o:o + len(old)]) != old:
            raise ValueError("name-entry label: unexpected original bytes")
        exe[o:o + len(new)] = new
    off = NE.TABLE_FILE_OFF
    if exe[off:off + len(NE._STOCK_ROW0)] != NE._STOCK_ROW0:
        raise ValueError("name-entry table anchor mismatch at 0x%x" % off)
    end = end_row(variant)
    if layout(variant)[end][10:13] != "   ":
        raise ValueError("END row must keep its right block empty")
    table = build_table(variant)
    exe[off:off + len(table)] = table
    return len(table)


def end_button_patches(variant):
    """Same constants as name_entry.END_ROW_PATCHES, recomputed for this layout."""
    r = end_row(variant)
    m = r - 3                        # 4 visible rows
    k = round(35.25 * 4096 / m)      # slider still sweeps the stock 35-px track
    if k > 0xFFFF:
        raise ValueError("slider factor out of range")
    slider = (0x24020000 | k) if k < 0x8000 else (0x34020000 | k)   # addiu / ori v0,zero,k
    stock = [w for _a, w, _p in NE.END_ROW_PATCHES]
    new = [
        0x28620000 | m,          # page-down gate
        0x28420000 | (m + 1),    # page-down overflow
        0x24020000 | m,          # page-down clamp
        0x28620000 | m,          # down-arrow gate
        0x24020000 | r,          # right-move END row
        0x24020000 | r,          # left-move END row
        0x24020000 | r,          # END-row col snap
        0x24020000 | r,          # END sprite draw
        0x24020000 | r,          # confirm on END
        0x24020000 | m,          # name-full auto jump
        0x24020000 | m,          # jump-to-END button
        0x24030000 | (r + 1),    # hide down arrow
        slider,
        0x00032900,              # sll a1,v1,4 (stock shift)
    ]
    return [(a, s, n) for (a, s, _p), n in zip(NE.END_ROW_PATCHES, new)]


def apply_end_button(exe, variant):
    variant = _cfg(variant)["layout"]
    for address, stock, patched in end_button_patches(variant):
        off = address - NE.PSX_EXE_LOAD + NE.PSX_EXE_HEADER
        cur = struct.unpack_from("<I", exe, off)[0]
        if cur != stock:
            raise ValueError(f"name-entry patch at 0x{address:08x}: expected 0x{stock:08x}, found 0x{cur:08x}")
        struct.pack_into("<I", exe, off, patched)


def _atlas_code(ch):
    """Glyph source in the PRISTINE font: stock JIS Cyrillic for Cyrillic letters."""
    if ch in UP or ch in LO:
        return CY._stock_cyr_code(ch)
    return ET.fullwidth(ch)


def atlas_rows(slpm, variant):
    """Index matrix (192 x 156) of the grid part of the atlas, row 0 kept as is."""
    img = [[0] * NE.ATLAS_WIDTH for _ in range(NE.ATLAS_GRID_HEIGHT)]
    for pass_index, value in ((1, NE.SHADOW_INDEX), (0, NE.FG_INDEX)):
        for ri, row in enumerate(layout(variant)):
            for ci, ch in enumerate(row):
                if ch == " ":
                    continue
                glyph = NE._glyph12(slpm, _atlas_code(ch))
                ox = NE.GLYPH_X_OFF + ci * 12 + pass_index
                oy = NE.GLYPH_Y_OFF + ri * 12 + pass_index
                for gy in range(12):
                    for gx in range(12):
                        if glyph[gy][gx]:
                            x, y = ox + gx, oy + gy
                            if x < NE.ATLAS_WIDTH and 1 <= y < NE.ATLAS_GRID_HEIGHT:
                                img[y][x] = value
    return img


def _cfg(variant):
    return variant if isinstance(variant, dict) else {"layout": variant}


def patch_atlas(packa, slpm, variant):
    cfg = _cfg(variant)
    variant = cfg["layout"]
    region = bytes(packa[NE.ATLAS_PACKA_OFF:NE.ATLAS_PACKA_OFF + NE.ATLAS_GRID_HEIGHT * NE.ATLAS_STRIDE])
    if hashlib.sha256(region).hexdigest() != NE.ATLAS_SHA256:
        raise SystemExit("name-entry atlas: unexpected SHA-256 (stock grid expected)")
    img = atlas_rows(slpm, variant)
    for y in range(1, NE.ATLAS_GRID_HEIGHT):
        for x in range(NE.ATLAS_WIDTH):
            NE._atlas_pixel(packa, x, y, img[y][x])
    end = cfg.get("end_sprite")          # approved replacement of the "-END-" sprite
    if end:
        # The sprite's right edge spills into the first pixels of the next image row
        # (VRAM rows are read 160 px wide), so the data holds two rectangles.
        for p in end["patches"]:
            x0, y0, w, h = p["rect"]
            if x0 + w > NE.ATLAS_WIDTH or y0 < NE.ATLAS_GRID_HEIGHT or y0 + h > 208:
                raise SystemExit("END sprite rect outside the label area")
            cur = []
            for y in range(y0, y0 + h):
                row = ""
                for x in range(x0, x0 + w):
                    b = packa[NE.ATLAS_PACKA_OFF + y * NE.ATLAS_STRIDE + x // 2]
                    row += "%x" % ((b >> 4) if x & 1 else (b & 15))
                cur.append(row)
            if hashlib.sha256("\n".join(cur).encode()).hexdigest() != p["orig"]:
                raise SystemExit("END sprite: unexpected stock pixels")
            for dy, row in enumerate(p["rows"]):
                for dx, ch in enumerate(row):
                    NE._atlas_pixel(packa, x0 + dx, y0 + dy, int(ch, 16))
