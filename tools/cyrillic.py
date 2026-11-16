# -*- coding: utf-8 -*-
"""Cyrillic support for the SMT2 PSX translation build (RU fork).

Where the letters live
----------------------
The English build already spends the 12x12 font's own SJIS Cyrillic block
(0x8440-0x849e, glyphs 567+) on code caves, and the 10x10 font has no Cyrillic
at all.  A Russian build has no use for kana, so every Cyrillic letter is
assigned to a HIRAGANA cell instead:

    CYR[i]  ->  SJIS 0x829F + i        (66 letters: А..Я Ё а..я ё)

Hiragana sits in SJIS lead byte 0x82, which every VWF width table of the
English engine already covers (tables are indexed by lead bytes 0x81/0x82), so
the letters get proportional widths everywhere without new code.

12x12 glyphs are copied from the stock SJIS Cyrillic block of the pristine
executable (before the English patch reuses those bytes); 10x10 glyphs are
hand-drawn below in the same 5x7 style as the English build's compact capitals.

One-byte (marker 0x1f) strings
------------------------------
Marker-prefixed system strings store one byte per character and expand each
byte through a 256-entry table.  Bytes 0x20-0x7e are ASCII, 0x7f is the Macca
sign and bytes 0x80+i are CYR[i].  The table is relocated from 0x800d8400
(where only 128 entries fit) into the 12x12 font's KATAKANA cells, which the
Russian build no longer needs.
"""
import struct

CYR = ("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
       "абвгдеёжзийклмнопрстуфхцчшщъыьэюя")
assert len(CYR) == 66
CODE_BASE = 0x829F            # first hiragana cell
BYTE_BASE = 0x80              # first one-byte code
CODES = [CODE_BASE + i for i in range(len(CYR))]
BYTE_END = BYTE_BASE + len(CYR)   # exclusive

# Typographic extras that map onto existing glyphs.
EXTRA_FULLWIDTH = {
    "«": 0x8167,   # “
    "»": 0x8168,   # ”
    "—": 0x815D,   # -
    "–": 0x815D,
    "*": 0x8196,   # ＊ (the English build silently turned '*' into a space)
    "№": None,     # unsupported, rejected by the checker
}
EXTRA_ONE_BYTE = {"«": '"', "»": '"', "—": "-", "–": "-"}

# One-byte expansion table location: katakana cells of the 12x12 font
# (SJIS 0x8340.. = glyph 378 -> 0x800d5c1c).  512 bytes, 2-byte aligned.
ASCII_TABLE = 0x800D5C20
ASCII_TABLE_SIZE = 512
FONT12 = 0x800D4188
KATAKANA_FIRST = FONT12 + 378 * 18          # 0x800d5c1c
KATAKANA_END = FONT12 + 465 * 18            # end of 0x8396


def fullwidth_code(ch):
    """Cyrillic / extra char -> SJIS code, or None if not handled here."""
    i = CYR.find(ch)
    if i >= 0:
        return CODE_BASE + i
    return EXTRA_FULLWIDTH.get(ch)


def one_byte(ch):
    """Char -> one-byte code for marker strings (raises on unsupported)."""
    if ch == "ћ":
        return 0x7F
    i = CYR.find(ch)
    if i >= 0:
        return BYTE_BASE + i
    ch = EXTRA_ONE_BYTE.get(ch, ch)
    o = ord(ch)
    if 0x20 <= o <= 0x7E:
        return o
    raise SystemExit(f"unsupported one-byte character {ch!r}")


def encode_one_byte(text, marker=0x1F):
    text = text.replace("…", "...")
    return bytes([marker]) + bytes(one_byte(c) for c in text) + b"\0"


def one_byte_table(fullwidth):
    """256-entry big-endian SJIS table for the marker printers."""
    table = bytearray()
    for value in range(256):
        if value == 0x7F:
            code = 0x8192
        elif 0x20 <= value <= 0x7E:
            try:
                code = fullwidth(chr(value))
            except KeyError:
                code = fullwidth("?")
        elif BYTE_BASE <= value < BYTE_END:
            code = CODES[value - BYTE_BASE]
        else:
            code = fullwidth("?")
        table += struct.pack(">H", code)
    return table


# --------------------------------------------------------------------- glyphs
def _foff(a):
    return (a - 0x80010000) + 0x800


def _sidx(code):
    b1, b2 = code >> 8, code & 0xFF
    row = (b1 - 0x81) if b1 < 0xA0 else (b1 - 0xC1)
    return (b2 - 0x40) + row * 189


def _stock_cyr_code(ch):
    """SJIS code of the letter in the stock JIS X 0208 Cyrillic block."""
    return struct.unpack(">H", ch.encode("cp932"))[0]


# 10x10 glyphs.  Rows are given from the TOP of the cell (row 0); the build
# later lowers the whole Latin/punctuation/Cyrillic repertoire by one pixel
# (kern_font baseline pass), so capitals occupy rows 1-7 here, lowercase
# x-height rows 3-7, descenders row 8, and row 9 must stay empty.
# Each entry: (first_row, "row/row/...")
GLYPHS10 = {
    # capitals ------------------------------------------------------------
    "А": (1, ".###./#...#/#...#/#####/#...#/#...#/#...#"),
    "Б": (1, "#####/#..../#..../####./#...#/#...#/####."),
    "В": (1, "####./#...#/#...#/####./#...#/#...#/####."),
    "Г": (1, "#####/#..../#..../#..../#..../#..../#...."),
    "Д": (1, ".###./.#.#./.#.#./.#.#./.#.#./.#.#./#####/#...#"),
    "Е": (1, "#####/#..../#..../####./#..../#..../#####"),
    "Ё": (0, ".#.#./....../#####/#..../####./#..../#..../#####"),
    "Ж": (1, "#.#.#/#.#.#/.###./..#../.###./#.#.#/#.#.#"),
    "З": (1, ".###./#...#/....#/..##./....#/#...#/.###."),
    "И": (1, "#...#/#...#/#..##/#.#.#/##..#/#...#/#...#"),
    "Й": (0, ".###./....../#...#/#..##/#.#.#/##..#/#...#/#...#"),
    "К": (1, "#...#/#..#./#.#../##.../#.#../#..#./#...#"),
    "Л": (1, "..###/.#..#/.#..#/.#..#/.#..#/.#..#/#...#"),
    "М": (1, "#...#/##.##/#.#.#/#.#.#/#...#/#...#/#...#"),
    "Н": (1, "#...#/#...#/#...#/#####/#...#/#...#/#...#"),
    "О": (1, ".###./#...#/#...#/#...#/#...#/#...#/.###."),
    "П": (1, "#####/#...#/#...#/#...#/#...#/#...#/#...#"),
    "Р": (1, "####./#...#/#...#/####./#..../#..../#...."),
    "С": (1, ".###./#...#/#..../#..../#..../#...#/.###."),
    "Т": (1, "#####/..#../..#../..#../..#../..#../..#.."),
    "У": (1, "#...#/#...#/#...#/.####/....#/#...#/.###."),
    "Ф": (1, "..#../.###./#.#.#/#.#.#/#.#.#/.###./..#.."),
    "Х": (1, "#...#/#...#/.#.#./..#../.#.#./#...#/#...#"),
    "Ц": (1, "#..#./#..#./#..#./#..#./#..#./#..#./#####/....#"),
    "Ч": (1, "#...#/#...#/#...#/.####/....#/....#/....#"),
    "Ш": (1, "#.#.#/#.#.#/#.#.#/#.#.#/#.#.#/#.#.#/#####"),
    "Щ": (1, "#.#.#./#.#.#./#.#.#./#.#.#./#.#.#./#.#.#./######/.....#"),
    "Ъ": (1, "##.../.#.../.#.../.###./.#..#/.#..#/.###."),
    "Ы": (1, "#...#/#...#/#...#/###.#/#.#.#/#.#.#/###.#"),
    "Ь": (1, "#..../#..../#..../####./#...#/#...#/####."),
    "Э": (1, ".###./#...#/....#/.####/....#/#...#/.###."),
    "Ю": (1, "#..##./#.#..#/#.#..#/###..#/#.#..#/#.#..#/#..##."),
    "Я": (1, ".####/#...#/#...#/.####/..#.#/.#..#/#...#"),
    # lowercase -----------------------------------------------------------
    "а": (3, ".###./....#/.####/#...#/.####"),
    "б": (1, "..###/.#.../#..../####./#...#/#...#/.###."),
    "в": (3, "####./#...#/####./#...#/####."),
    "г": (3, "####/#.../#.../#.../#..."),
    "д": (3, "..##./.#.#./.#.#./.#.#./#####/#...#"),
    "е": (3, ".###./#...#/#####/#..../.###."),
    "ё": (1, ".#.#./....../.###./#...#/#####/#..../.###."),
    "ж": (3, "#.#.#/#.#.#/.###./#.#.#/#.#.#"),
    "з": (3, "###./...#/.##./...#/###."),
    "и": (3, "#...#/#..##/#.#.#/##..#/#...#"),
    "й": (1, ".###./....../#...#/#..##/#.#.#/##..#/#...#"),
    "к": (3, "#..#/#.#./##../#.#./#..#"),
    "л": (3, "..###/.#..#/.#..#/.#..#/#...#"),
    "м": (3, "#...#/##.##/#.#.#/#...#/#...#"),
    "н": (3, "#...#/#...#/#####/#...#/#...#"),
    "о": (3, ".###./#...#/#...#/#...#/.###."),
    "п": (3, "#####/#...#/#...#/#...#/#...#"),
    "р": (3, "####./#...#/#...#/####./#..../#...."),
    "с": (3, ".###./#...#/#..../#...#/.###."),
    "т": (3, "#####/..#../..#../..#../..#.."),
    "у": (3, "#...#/#...#/#...#/.####/....#/.###."),
    "ф": (1, "..#../..#../.###./#.#.#/#.#.#/#.#.#/.###./..#.."),
    "х": (3, "#...#/.#.#./..#../.#.#./#...#"),
    "ц": (3, "#..#./#..#./#..#./#..#./#####/....#"),
    "ч": (3, "#...#/#...#/.####/....#/....#"),
    "ш": (3, "#.#.#/#.#.#/#.#.#/#.#.#/#####"),
    "щ": (3, "#.#.#./#.#.#./#.#.#./#.#.#./######/.....#"),
    "ъ": (3, "##.../.#.../.###./.#..#/.###."),
    "ы": (3, "#...#/#...#/###.#/#.#.#/###.#"),
    "ь": (3, "#.../#.../###./#..#/###."),
    "э": (3, "###./...#/.###/...#/###."),
    "ю": (3, "#..##./#.#..#/###..#/#.#..#/#..##."),
    "я": (3, ".####/#...#/.####/.#..#/#...#"),
}
assert set(GLYPHS10) == set(CYR), set(CYR) ^ set(GLYPHS10)

# Compact 12x12 Cyrillic glyphs (5px base width -> 6px advance, 7-8px for wide letters)
GLYPHS12 = {
    "А": (1, "..#../.#.#./.#.#./#...#/#...#/#####/#...#/#...#/#...#"),
    "Б": (1, "#####/#..../#..../#..../####./#...#/#...#/#...#/####."),
    "В": (1, "####./#...#/#...#/#...#/####./#...#/#...#/#...#/####."),
    "Г": (1, "#####/#..../#..../#..../#..../#..../#..../#..../#...."),
    "Д": (1, ".###./.#.#./.#.#./.#.#./.#.#./.#.#./.#.#./.#.#./#####/#...#"),
    "Е": (1, "#####/#..../#..../#..../####./#..../#..../#..../#####"),
    "Ё": (0, ".#.#./...../#####/#..../#..../####./#..../#..../#..../#####"),
    "Ж": (1, "#..#..#/#..#..#/.#.#.#./.#.#.#./..###../.#.#.#./.#.#.#./#..#..#/#..#..#"),
    "З": (1, ".###./#...#/....#/....#/..##./....#/....#/#...#/.###."),
    "И": (1, "#...#/#...#/#..##/#.#.#/#.#.#/##..#/#...#/#...#/#...#"),
    "Й": (0, ".###./...../#...#/#...#/#..##/#.#.#/##..#/#...#/#...#/#...#"),
    "К": (1, "#...#/#..#./#.#../##.../##.../#.#../#..#./#...#/#...#"),
    "Л": (1, ".####/.#..#/.#..#/.#..#/.#..#/.#..#/.#..#/#...#/#...#"),
    "М": (1, "#.....#/##...##/##...##/#.#.#.#/#.#.#.#/#..#..#/#.....#/#.....#/#.....#"),
    "Н": (1, "#...#/#...#/#...#/#...#/#####/#...#/#...#/#...#/#...#"),
    "О": (1, ".###./#...#/#...#/#...#/#...#/#...#/#...#/#...#/.###."),
    "П": (1, "#####/#...#/#...#/#...#/#...#/#...#/#...#/#...#/#...#"),
    "Р": (1, "####./#...#/#...#/#...#/####./#..../#..../#..../#...."),
    "С": (1, ".###./#...#/#..../#..../#..../#..../#..../#...#/.###."),
    "Т": (1, "#####/..#../..#../..#../..#../..#../..#../..#../..#.."),
    "У": (1, "#...#/#...#/#...#/#...#/.####/....#/....#/#...#/.###."),
    "Ф": (1, "..#../.###./#.#.#/#.#.#/#.#.#/.###./..#../..#../..#.."),
    "Х": (1, "#...#/#...#/.#.#./..#../..#../..#../.#.#./#...#/#...#"),
    "Ц": (1, "#..#./#..#./#..#./#..#./#..#./#..#./#..#./#..#./#####/....#"),
    "Ч": (1, "#...#/#...#/#...#/#...#/.####/....#/....#/....#/....#"),
    "Ш": (1, "#..#..#/#..#..#/#..#..#/#..#..#/#..#..#/#..#..#/#..#..#/#..#..#/#######"),
    "Щ": (1, "#..#..#./#..#..#./#..#..#./#..#..#./#..#..#./#..#..#./#..#..#./#..#..#./########/.......#"),
    "Ъ": (1, "##..../.#..../.#..../.#..../.####./.#...#/.#...#/.#...#/.####."),
    "Ы": (1, "#....#/#....#/#....#/#....#/###..#/#..#.#/#..#.#/#..#.#/###..#"),
    "Ь": (1, "#..../#..../#..../#..../####./#...#/#...#/#...#/####."),
    "Э": (1, ".###./#...#/....#/....#/..###/....#/....#/#...#/.###."),
    "Ю": (1, "#..###./#.#...#/#.#...#/#.#...#/###...#/#.#...#/#.#...#/#.#...#/#..###."),
    "Я": (1, ".####/#...#/#...#/#...#/.####/..#.#/.#..#/#...#/#...#"),
    "а": (3, ".###./....#/.####/#...#/#...#/#...#/.####"),
    "б": (1, "..###/.#.../#..../####./#...#/#...#/#...#/#...#/.###."),
    "в": (3, "####./#...#/#...#/####./#...#/#...#/####."),
    "г": (3, "####./#..../#..../#..../#..../#..../#...."),
    "д": (3, ".###./.#.#./.#.#./.#.#./.#.#./#####/#...#"),
    "е": (3, ".###./#...#/#...#/#####/#..../#...#/.###."),
    "ё": (1, ".#.#./...../.###./#...#/#...#/#####/#..../#...#/.###."),
    "ж": (3, "#..#..#/.#.#.#./.#.#.#./..###../.#.#.#./.#.#.#./#..#..#"),
    "з": (3, ".###./#...#/....#/..##./....#/#...#/.###."),
    "и": (3, "#...#/#...#/#..##/#.#.#/##..#/#...#/#...#"),
    "й": (1, ".###./...../#...#/#...#/#..##/#.#.#/##..#/#...#/#...#"),
    "к": (3, "#...#/#..#./#.#../##.../#.#../#..#./#...#"),
    "л": (3, ".####/.#..#/.#..#/.#..#/.#..#/#...#/#...#"),
    "м": (3, "#.....#/##...##/#.#.#.#/#.#.#.#/#..#..#/#.....#/#.....#"),
    "н": (3, "#...#/#...#/#...#/#####/#...#/#...#/#...#"),
    "о": (3, ".###./#...#/#...#/#...#/#...#/#...#/.###."),
    "п": (3, "#####/#...#/#...#/#...#/#...#/#...#/#...#"),
    "р": (3, "####./#...#/#...#/#...#/#...#/####./#..../#...."),
    "с": (3, ".###./#...#/#..../#..../#..../#...#/.###."),
    "т": (3, "#####/..#../..#../..#../..#../..#../..#.."),
    "у": (3, "#...#/#...#/#...#/#...#/.####/....#/.###."),
    "ф": (1, "..#../..#../.###./#.#.#/#.#.#/#.#.#/.###./..#../..#.."),
    "х": (3, "#...#/#...#/.#.#./..#../.#.#./#...#/#...#"),
    "ц": (3, "#..#./#..#./#..#./#..#./#..#./#..#./#####/....#"),
    "ч": (3, "#...#/#...#/#...#/.####/....#/....#/....#"),
    "ш": (3, "#..#..#/#..#..#/#..#..#/#..#..#/#..#..#/#..#..#/#######"),
    "щ": (3, "#..#..#./#..#..#./#..#..#./#..#..#./#..#..#./#..#..#./########/.......#"),
    "ъ": (3, "##.../.#.../.####/.#..#/.#..#/.#..#/.####"),
    "ы": (3, "#....#/#....#/###..#/#..#.#/#..#.#/#..#.#/###..#"),
    "ь": (3, "#..../#..../####./#...#/#...#/#...#/####."),
    "э": (3, ".###./#...#/....#/..###/....#/#...#/.###."),
    "ю": (3, "#..###./#.#...#/###...#/#.#...#/#.#...#/#.#...#/#..###."),
    "я": (3, ".####/#...#/#...#/.####/..#.#/.#..#/#...#"),
}
assert set(GLYPHS12) == set(CYR), set(CYR) ^ set(GLYPHS12)


def _encode_12x12(first, art):
    """Pack a 12x12 glyph definition into 18 bytes (12 rows x 12 bits, MSB first)."""
    rows = art.split("/")
    if first + len(rows) > 12:
        raise SystemExit(f"12x12 glyph overflows 12 rows: {art!r}")
    bits = [0] * 144
    for y, row in enumerate(rows):
        if len(row) > 12:
            raise SystemExit(f"12x12 glyph overflows 12 cols: {row!r}")
        for x, ch in enumerate(row):
            if ch == "#":
                bits[(first + y) * 12 + x] = 1
    return bytes(
        sum(bits[i * 8 + b] << (7 - b) for b in range(8))
        for i in range(18)
    )


def install_glyphs(slpm):
    """Return a copy of the pristine exe with Cyrillic drawn into the hiragana
    cells of both fonts.  Must run on the PRISTINE exe (stock Cyrillic block
    intact), i.e. before build.kern_font."""
    exe = bytearray(slpm)
    F12, GB = FONT12, 18
    base12 = _foff(F12)
    for ch, code in zip(CYR, CODES):
        dst = base12 + _sidx(code) * GB
        first, art = GLYPHS12[ch]
        exe[dst:dst + GB] = _encode_12x12(first, art)

    F10 = _foff(0x800D25D8)

    def setbit(k, v):
        m = 1 << (7 - (k & 7))
        if v:
            exe[F10 + (k >> 3)] |= m
        else:
            exe[F10 + (k >> 3)] &= ~m & 0xFF

    for ch, code in zip(CYR, CODES):
        first, art = GLYPHS10[ch]
        rows = art.split("/")
        if first + len(rows) > 9:
            raise SystemExit(f"10x10 glyph {ch!r} reaches the last row")
        start = _sidx(code) * 100
        for k in range(100):
            setbit(start + k, 0)
        for y, row in enumerate(rows):
            if len(row) > 9:
                raise SystemExit(f"10x10 glyph {ch!r} too wide")
            for x, px in enumerate(row):
                if px == "#":
                    setbit(start + (first + y) * 10 + x, 1)
    return bytes(exe)


# ------------------------------------------------------------ freed RAM
# Kana cells the Russian build no longer draws.  They hold extra compression-
# dictionary strings (build_prod_exe.DICT_EXTRA_REGIONS).  12x12: hiragana
# cells after the 66 Cyrillic letters (sidx 350..) through the unassigned
# cells before Greek (sidx 473), minus the one-byte table.  10x10: the same
# cells, bit-addressed (100 bits per glyph), trimmed to whole bytes.
FONT10 = 0x800D25D8


def free_regions():
    first = _sidx(CODES[-1]) + 1          # first unused hiragana cell
    last = 473                            # first Greek cell (0x839F)
    # (FONT12 + first*18 .. ASCII_TABLE) is given to map names: map_cave().
    r12 = [(ASCII_TABLE + ASCII_TABLE_SIZE, FONT12 + last * 18)]
    return [r for r in r12 if r[1] > r[0]]


def ab_regions():
    """Freed 10x10 kana cells (bit-addressed font, trimmed to whole bytes):
    home of the negotiation (A/B) dictionary pointer table and strings."""
    first = _sidx(CODES[-1]) + 1
    last = 473
    b0 = (first * 100 + 7) // 8
    b1 = (last * 100) // 8
    start = (FONT10 + b0 + 3) & ~3            # word-aligned for the u32 table
    return [(start, FONT10 + b1)]


def map_cave():
    """Freed 12x12 hiragana cells before the one-byte table: extra map-name space."""
    first = _sidx(CODES[-1]) + 1
    return (FONT12 + first * 18, ASCII_TABLE)
