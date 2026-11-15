"""Shared helpers for the Russian toolkit: BIN access, stock Huffman decoders,
and the tag syntax used in the translation JSON files.

Tag syntax (identical for JP / EN / RU fields):
  {CR} {WT} {PG} {ED} {SY} ...  C/D dialogue controls (see translate_pipeline.CTRL_NAME)
  {A0F} {A14} {A65} ...          A/B (negotiation / battle) controls
  {X:c095}                       raw control token (sym=0xc095, control flag set)
  plain text                     everything else
"""
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
for p in (str(ROOT), str(TOOLS)):
    if p not in sys.path:
        sys.path.insert(0, p)

SECTOR = 2352
EXPECTED_BIN_SIZE = 222_694_416
SLPM_SECTOR, SLPM_SIZE = 67202, 2_025_472
PACKA_SECTOR, PACKA_SIZE = 68191, 53_948_416
CMDINIT_SECTOR, CMDINIT_SIZE = 67152, 1519
RDLOGO_SECTOR, RDLOGO_SIZE = 67181, 1728

CD_STRUCT, CD_SYM = 0x80117EC4, 0x801187A4
AB_STRUCT, AB_SYM = 0x8010130C, 0x80101978
ED = (0x4544, True)


def foff(a):
    return (a - 0x80010000) + 0x800


def extract(bin_data, base_sector, size):
    out = bytearray()
    s = base_sector
    while len(out) < size:
        st = s * SECTOR + 24
        out += bin_data[st:st + 2048]
        s += 1
    return bytes(out[:size])


class Disc:
    """Lazy access to the files the toolkit needs from a Japan Rev 1 BIN."""

    def __init__(self, path):
        self.path = Path(path)
        data = self.path.read_bytes()
        if len(data) != EXPECTED_BIN_SIZE:
            raise SystemExit(f"{path}: unexpected size {len(data):,} (need {EXPECTED_BIN_SIZE:,})")
        self.data = data
        self.slpm = extract(data, SLPM_SECTOR, SLPM_SIZE)
        self._packa = None

    @property
    def packa(self):
        if self._packa is None:
            self._packa = extract(self.data, PACKA_SECTOR, PACKA_SIZE)
        return self._packa

    def file(self, sector, size):
        return extract(self.data, sector, size)


def u16(buf, ram):
    return struct.unpack_from("<H", buf, foff(ram))[0]


def decode_stream(buf, pos, exe, struct_base, sym_base, *, end=None, stop_at_ed=True,
                  ab=False, stop_at_any_ctrl=False, max_tokens=4000):
    """Decode one nibble-Huffman stream. Returns list of tokens.

    C/D tokens: (sym, is_ctrl).  A/B tokens: (sym, is_ctrl, index) for controls.
    """
    hi = True
    toks = []
    for _ in range(max_tokens):
        node = 0
        while True:
            if end is not None and pos >= end:
                return toks
            b = buf[pos]
            nib = (b >> 4) if hi else (b & 0xF)
            hi = not hi
            if hi:
                pos += 1
            ea = (node & 0xFFFE) + nib * 2
            nx = u16(exe, struct_base + ea)
            if nx == 0x7FFF:
                return toks
            if nx & 0x8000:
                sym = u16(exe, sym_base + ea)
                ctrl = bool(nx & 0x4000)
                if ab and ctrl:
                    toks.append((sym, True, nx & 0x3FFF))
                else:
                    toks.append((sym, ctrl))
                break
            node = nx
        t = toks[-1]
        if stop_at_ed and t[:2] == ED and not ab:
            return toks
        if stop_at_any_ctrl and t[1]:
            return toks
    return toks


def _ctrl_name(sym):
    try:
        s = struct.pack(">H", sym).decode("ascii")
        if s.isalnum():
            return s
    except UnicodeDecodeError:
        pass
    return None


def render_jp(tokens, ab=False, cr_as_newline=False):
    """Render stock (Japanese) tokens using the tag syntax."""
    out = []
    for t in tokens:
        sym, ctrl = t[0], t[1]
        if ab and ctrl and len(t) == 3:
            out.append("{A%02X}" % t[2])
            continue
        if ctrl:
            if cr_as_newline and sym == 0x4352:
                out.append("\n")
                continue
            name = _ctrl_name(sym)
            out.append("{%s}" % name if name else "{X:%04x}" % sym)
            continue
        if sym == 0x8140:
            out.append("　")
            continue
        try:
            out.append(struct.pack(">H", sym).decode("cp932"))
        except UnicodeDecodeError:
            out.append("{G:%04x}" % sym)
    return "".join(out)


def decode_cd_block(buf, base, exe):
    """Decode every message of a C/D block [u16 data_off][u16 offs[N]][streams]."""
    do = struct.unpack_from("<H", buf, base)[0]
    n = (do - 2) // 2
    offs = struct.unpack_from(f"<{n}H", buf, base + 2)
    return [decode_stream(buf, base + do + o, exe, CD_STRUCT, CD_SYM) for o in offs]


# ---------------------------------------------------------------- tag syntax
TAG_RE = re.compile(r"\{([^{}]+)\}")


def author_to_tagged(author):
    """translations.py list form -> tagged string."""
    out = []
    for part in author:
        if isinstance(part, tuple):
            sym = part[0]
            if len(part) >= 3:
                out.append("{XA:%04x:%02x}" % (sym, part[2]))
            else:
                out.append("{X:%04x}" % sym)
        elif _is_control_name(part):
            out.append("{%s}" % part)
        else:
            if "{" in part or "}" in part:
                raise ValueError(f"brace in text: {part!r}")
            out.append(part)
    return "".join(out)


def _is_control_name(part):
    import translate_pipeline as TP
    return part in TP.CTRL_NAME or part in TP.AB_CTRL_INDEX


def tagged_to_author(text):
    """Tagged string -> translations.py list form (strings + control names + tuples)."""
    import translate_pipeline as TP
    parts = []
    pos = 0
    for m in TAG_RE.finditer(text):
        if m.start() > pos:
            parts.append(text[pos:m.start()])
        tag = m.group(1)
        if tag in TP.CTRL_NAME or tag in TP.AB_CTRL_INDEX:
            parts.append(tag)
        elif tag.startswith("X:"):
            parts.append((int(tag[2:], 16), True))
        elif tag.startswith("XA:"):
            _x, sym, idx = tag.split(":")
            parts.append((int(sym, 16), True, int(idx, 16)))
        else:
            raise ValueError(f"unknown tag {{{tag}}} in {text!r}")
        pos = m.end()
    if pos < len(text):
        parts.append(text[pos:])
    return parts


def tags_of(text):
    return [m.group(1) for m in TAG_RE.finditer(text)]


def strip_tags(text):
    return TAG_RE.sub("", text)
