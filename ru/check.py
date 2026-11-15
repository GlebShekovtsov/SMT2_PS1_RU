"""Validate a Russian translation and measure every fixed-size allocation.

    python ru/check.py --input "Shin Megami Tensei II (Japan) (Rev 1).bin" --text text
    python ru/check.py --input ... --text text --static-only      # fast, no trial build
    python ru/check.py --input ... --text text --report report.md --json report.json

Two stages:
 1. STATIC checks for every entry with a non-empty "ru": control tags, supported
    characters, hard per-slot limits (max_chars), pixel widths of dialogue lines,
    names, spell descriptions, menus.
 2. TRIAL BUILD in report-only mode (no BIN written): every compressed bank,
    name table, menu and overlay table is encoded with the real compressor and
    its fill level is reported, together with every layout violation the build
    itself detects.  Entries that failed stage 1 are built in English so the
    remaining measurements stay meaningful.

Exit code 0 = no errors (warnings allowed), 1 = errors found.
"""
import argparse
import contextlib
import io
import json
import re
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import Disc, tags_of, strip_tags, TAG_RE

import build_en_tree as ET
import cyrillic as CY
import translate_pipeline as TP

# ------------------------------------------------------------------ rules
CD_LAYOUT = {"CR", "WT", "PG"}             # may be added/removed freely
AB_LAYOUT = {"A65", "A68"}                 # A65 = line break, A68 = pause
DIALOGUE_SOFT_PX = 240                     # widest English C/D line ~240px
DIALOGUE_HARD_PX = 266                     # measured in-game: ~266px fit, 278px wraps
AB_SOFT_PX = 260
INSERT_PX = {"SY": 56, "SN": 56, "FI": 56, "FO": 56, "NI": 56, "AG": 100, "AL": 70,
             "MG": 80, "MN": 80, "IT": 96, "MH": 70, "OT": 60, "SU": 30, "S2": 30,
             "PP": 20, "A63": 80, "A64": 60, "A6B": 56, "A6F": 100, "A69": 30, "A62": 96}
DEMON_MAX_CHARS = 17
DEMON_MAX_PX10 = 80
ITEM_NAME_MAX_PX = 96          # casino prize panel (items 0-299)
ITEM_DESC_MAX_PX = 108         # shop/status description box (items 300+)
SPELL_DESC_MAX_PX = 124        # status box (spells 160+)
SPELL_NAME_MAX_PX = 95         # skill lists: name x=4, cost column x=102 (spells 0-159)
NEGOTIATION_MENU_PX = 276
MOVIE_LINE_PX = 304            # opening crawl / game-over captions


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def err(self, eid, msg):
        self.errors.append((eid, msg))

    def warn(self, eid, msg):
        self.warnings.append((eid, msg))


def load_widths(disc):
    """Kerned 12px/10px advance widths of the RU build, keyed by character."""
    import build
    _font, w12, w10 = build.kern_font(disc.slpm)

    def make(table, default):
        cache = {}

        def width(ch):
            if ch not in cache:
                try:
                    code = ET.fullwidth(ch)
                except KeyError:
                    cache[ch] = None
                    return None
                cache[ch] = table.get(build_sidx(code), default)
            return cache[ch]
        return width
    return make(w12, 12), make(w10, 10)


def build_sidx(code):
    b1, b2 = code >> 8, code & 0xFF
    row = (b1 - 0x81) if b1 < 0xA0 else (b1 - 0xC1)
    return (b2 - 0x40) + row * 189


def unsupported_chars(text, one_byte=False):
    bad = set()
    for ch in text:
        if ch == "\n":
            continue
        try:
            if one_byte:
                CY.one_byte(ch) if ch != "…" else None
            else:
                ET.fullwidth(ch)
        except (KeyError, SystemExit):
            bad.add(ch)
    return sorted(bad)


def px(text, width):
    return sum((width(c) or 12) for c in text)


# ------------------------------------------------------------------ static
def check_dialogue(e, ru, rep, w12):
    eid = e["id"]
    en = e["en"]
    bank = int(eid.split(":")[1], 16) >> 12
    ab = bank in (4, 5)
    try:
        common.tagged_to_author(ru)
    except ValueError as exc:
        rep.err(eid, str(exc))
        return False
    t_en, t_ru = tags_of(en), tags_of(ru)
    layout = AB_LAYOUT if ab else CD_LAYOUT
    s_en = [t for t in t_en if t not in layout]
    s_ru = [t for t in t_ru if t not in layout]
    ok = True
    if s_en != s_ru:
        rep.err(eid, f"control tags differ from EN: EN {s_en} vs RU {s_ru}")
        ok = False
    if not ab and (not t_ru or t_ru[-1] != "ED"):
        rep.err(eid, "C/D message must end with {ED}")
        ok = False
    if not ab:
        for t in ("WT", "PG"):
            if Counter(t_en)[t] != Counter(t_ru)[t]:
                rep.warn(eid, f"{{{t}}} count changed ({Counter(t_en)[t]} -> {Counter(t_ru)[t]}); "
                              "fine if intended (page/wait layout)")
    bad = unsupported_chars(strip_tags(ru))
    if bad:
        rep.err(eid, f"unsupported characters {bad}")
        ok = False
    # line widths
    breaks = {"CR", "WT", "PG", "ED", "A0F", "A14", "A65"}
    line, est = "", 0
    widest = (0, "")
    for part in re.split(r"(\{[^{}]+\})", ru):
        m = TAG_RE.fullmatch(part) if part else None
        if m:
            tag = m.group(1)
            if tag in breaks:
                widest = max(widest, (px(line, w12) + est, line))
                line, est = "", 0
            else:
                est += INSERT_PX.get(tag, 0)
            continue
        line += part
    widest = max(widest, (px(line, w12) + est, line))
    limit = AB_SOFT_PX if ab else DIALOGUE_SOFT_PX
    if widest[0] > DIALOGUE_HARD_PX and not ab:
        rep.err(eid, f"line ~{widest[0]}px > {DIALOGUE_HARD_PX}px (window): {widest[1]!r}")
        ok = False
    elif widest[0] > limit:
        rep.warn(eid, f"long line ~{widest[0]}px (EN max ~{limit}px): {widest[1]!r}")
    return ok


def check_plain(e, ru, rep, w12, w10):
    eid = e["id"]
    kind = eid.split(":")[0]
    ok = True
    one_byte = (e.get("encoding") == "1-byte" or kind in ("3dmap", "casino3", "rag", "rdlogo"))
    # Map names encode '@' as the native 0x8197 line-break control, not a glyph.
    bad = unsupported_chars(ru.replace('@', '') if kind == 'map' else ru, one_byte=one_byte)
    if bad:
        rep.err(eid, f"unsupported characters {bad}")
        ok = False
    if "{" in ru or "}" in ru:
        rep.err(eid, "tags are not allowed in this field")
        ok = False
    if "max_chars" in e:
        n = len(ru.replace("…", "...")) if one_byte else len(ru)
        if n > e["max_chars"]:
            rep.err(eid, f"{n} chars > max {e['max_chars']}")
            ok = False
    if kind in ("3dmap", "casino3", "rag"):
        import literals as LIT
        for g in LIT.OVERLAY_GROUPS.values():
            if eid in g and len(CY.encode_one_byte(ru)) > g[eid][1]:
                rep.err(eid, f"{len(ru)} chars > max {g[eid][1] - 2}")
                ok = False
    if kind == "name":
        table, idx = eid.split(":")[1], int(eid.split(":")[2])
        if table == "demons":
            if len(ru) > DEMON_MAX_CHARS:
                rep.err(eid, f"demon name {len(ru)} chars > {DEMON_MAX_CHARS}")
                ok = False
            if px(ru, w10) > DEMON_MAX_PX10:
                rep.err(eid, f"demon name {px(ru, w10)}px > {DEMON_MAX_PX10}px (party plate, 10px font)")
                ok = False
        if table == "items" and idx < 300 and px(ru, w12) > ITEM_NAME_MAX_PX:
            rep.err(eid, f"item name {px(ru, w12)}px > {ITEM_NAME_MAX_PX}px (casino prize panel)")
            ok = False
        if table == "items" and idx >= 300:
            for ln in ru.split("\n"):
                if px(ln, w12) > ITEM_DESC_MAX_PX:
                    rep.err(eid, f"item description line {px(ln, w12)}px > {ITEM_DESC_MAX_PX}px: {ln!r}")
                    ok = False
        if table == "spells" and idx < 160 and px(ru, w12) > SPELL_NAME_MAX_PX:
            rep.err(eid, f"skill name {px(ru, w12)}px > {SPELL_NAME_MAX_PX}px (skill list cost column)")
            ok = False
        if table == "spells" and idx >= 160:
            for ln in ru.split("\n"):
                if px(ln, w12) > SPELL_DESC_MAX_PX:
                    rep.err(eid, f"description line {px(ln, w12)}px > {SPELL_DESC_MAX_PX}px: {ln!r}")
                    ok = False
        if e["en"].count("\n") != ru.count("\n") and table in ("spells", "items"):
            rep.warn(eid, f"line count changed ({e['en'].count(chr(10)) + 1} -> {ru.count(chr(10)) + 1})")
    if kind == "movie" and px(ru, w12) > MOVIE_LINE_PX:
        rep.err(eid, f"caption {px(ru, w12)}px > {MOVIE_LINE_PX}px (320px frame)")
        ok = False
    if kind == "abmenu" and px(ru, w12) > NEGOTIATION_MENU_PX:
        rep.err(eid, f"{px(ru, w12)}px > {NEGOTIATION_MENU_PX}px")
        ok = False
    if kind == "map":
        if " @" in ru:
            rep.warn(eid, "do not put a space before '@' (it is added automatically)")
        if e["en"].count("@") != ru.count("@"):
            rep.warn(eid, "'@' line-break count differs from EN")
    if kind == "trait" and ru.count("\n") > 2:
        rep.err(eid, "max 3 lines")
        ok = False
    if (e["en"][:1] == " ") != (ru[:1] == " ") or (e["en"][-1:] == " ") != (ru[-1:] == " "):
        rep.warn(eid, "leading/trailing space differs from EN (often significant)")
    return ok


def cathedral_checks(entries, rep, w10):
    """Race/demon widths on the Cathedral fusion screens (10px font)."""
    import build
    import name_tables as NT
    from bisect import bisect_right
    demons = list(NT.DEMONS); races = list(NT.RACES)
    for eid, e in entries.items():
        if e.get("ru") and eid.startswith("name:demons:"):
            demons[int(eid.split(":")[2])] = e["ru"]
        if e.get("ru") and eid.startswith("name:races:"):
            races[int(eid.split(":")[2])] = e["ru"]
    race_cap = build._CATHEDRAL_FIRST_NAME_X - build._CATHEDRAL_PAIR_GAP - build._CATHEDRAL_SOURCE_X
    name_cap = build._CATHEDRAL_FIRST_LEVEL_X - 8 - build._CATHEDRAL_FIRST_NAME_X
    pair_cap = min(134 - build._CATHEDRAL_SOURCE_X,
                   build._CATHEDRAL_RESULT_LEVEL_X - 4 - build._CATHEDRAL_RESULT_X)
    for i, r in enumerate(races[:build._COMPACT_RACE_COUNT]):
        if px(r, w10) > race_cap:
            rep.err(f"name:races:{i}", f"race {r!r} is {px(r, w10)}px > {race_cap}px (Cathedral race column, 10px font)")
    for i, d in enumerate(demons):
        if px(d, w10) > name_cap:
            rep.err(f"name:demons:{i}", f"demon {d!r} is {px(d, w10)}px > {name_cap}px (Cathedral name column)")
    for i, d in enumerate(demons[:255]):
        r = races[bisect_right(build._CATHEDRAL_RACE_BOUNDARIES, i)]
        w = px(r, w10) + build._CATHEDRAL_PAIR_GAP + px(d, w10)
        if w > pair_cap:
            rep.err(f"name:demons:{i}", f"race+name {r!r} {d!r} is {w}px > {pair_cap}px (Cathedral fusion row)")


def static_checks(entries, rep, w12, w10):
    cathedral_checks(entries, rep, w10)
    failed = set()
    for eid, e in entries.items():
        ru = e.get("ru")
        if not ru:
            continue
        if eid.startswith("dlg:"):
            ok = check_dialogue(e, ru, rep, w12)
        else:
            ok = check_plain(e, ru, rep, w12, w10)
        if not ok:
            failed.add(eid)
    return failed


# ------------------------------------------------------------------ trial build
LAYOUT_FUNCS = [
    "_patch_cathedral_columns", "_patch_long_demon_name_layouts", "_validate_spell_description_widths",
    "_patch_casino_prize_sprite", "_patch_equipment_shop_affinity_layout", "_patch_compact_race_labels",
    "_patch_bar_drink_menu", "_patch_casino_prize_menu", "_install_compact_demon_name_cache",
    "apply_exe_default_names", "apply_exe_default_hero_name", "apply_cmdinit_names",
    "verify_ab_banks",
]


def trial_build(input_bin, text_dir, failed, rep, dict_budget=None):
    import apply as RU
    entries, _counts = RU.apply(text_dir, verbose=False)
    # restore EN for entries that failed static checks
    import translations as TR
    for eid in failed:
        e = entries[eid]
        e["ru"] = ""
    # re-apply cleanly from scratch is simpler: reload modules is not possible
    # in-process, so instead overwrite failed entries with their English text.
    for eid in failed:
        e = entries[eid]
        if eid.startswith("dlg:"):
            TR.TRANS[int(eid.split(":")[1], 16)] = common.tagged_to_author(e["en"])
    _restore_plain(entries, failed)

    import build
    import capacity as CAP
    import overlay_text as OT
    import menu_table as MT
    CAP.REPORT_ONLY = True
    CAP.CAPACITY.clear()
    if dict_budget is not None:
        build.DICT_BUDGET = dict_budget
    layout_errors = []

    def wrap(mod, name):
        fn = getattr(mod, name)

        def inner(*a, **k):
            try:
                return fn(*a, **k)
            except (SystemExit, RuntimeError, ValueError) as exc:
                layout_errors.append((name, str(exc)))
                return None
        setattr(mod, name, inner)
    for name in LAYOUT_FUNCS:
        if hasattr(build, name):
            wrap(build, name)
    for name in ("verify_ab_menu_layout", "patch_ab_menu_layout"):
        wrap(MT, name)
    # overlay patchers are referenced through build.OVERLAY_FILES
    for key, (sector, size, fn) in list(build.OVERLAY_FILES.items()):
        def make(fn=fn, key=key):
            def inner(src):
                try:
                    return fn(src)
                except (SystemExit, RuntimeError, ValueError) as exc:
                    layout_errors.append((key, str(exc)))
                    return src
            return inner
        build.OVERLAY_FILES[key] = (sector, size, make())
    out = io.StringIO()
    fatal = None
    try:
        with contextlib.redirect_stdout(out):
            build.main(["--input", str(input_bin), "--skip-movies", "--output-dir", "build/_check"])
    except SystemExit as exc:
        fatal = str(exc)
    except Exception as exc:  # noqa: BLE001
        fatal = f"{type(exc).__name__}: {exc}"
    for name, msg in layout_errors:
        rep.err(f"layout:{name}", msg)
    if fatal:
        rep.err("build", f"trial build stopped: {fatal}")
    return dict(CAP.CAPACITY), out.getvalue()


def _restore_plain(entries, failed):
    import name_tables as NT, menu_table as MT, sys_strings as SS, map_names as MN
    import party_names as PN, rdlogo as RD, literals as LIT
    from apply import NAME_ATTR
    for eid in failed:
        e = entries[eid]
        kind, _, rest = eid.partition(":")
        en = e["en"]
        if kind == "name":
            t, i = rest.split(":")
            getattr(NT, NAME_ATTR[t])[int(i)] = en
        elif kind == "trait":
            NT.TRAITS_MAP[rest] = en
        elif kind == "menu":
            MT.MENU[int(rest)] = en
        elif kind == "abmenu":
            lst = list(MT.AB_MENU); lst[int(rest)] = en; MT.AB_MENU = tuple(lst)
        elif kind == "sys":
            off = int(rest, 16)
            if off in SS.SYS:
                SS.SYS[off] = (SS.SYS[off][0], en)
            else:
                SS.AUDITED_SYSTEM_TEXT[off] = en
        elif kind == "map" and not e.get("keep"):
            MN.ENGLISH[int(rest)] = en
        elif kind == "party":
            i = int(rest); PN.NAMES[i] = (en, PN.NAMES[i][1]); PN.ENGLISH[i] = en
        elif kind == "rdlogo":
            RD.LINES[int(rest)] = en
        elif kind in ("3dmap", "casino3", "rag"):
            LIT.OVERRIDES.pop(eid, None)
        elif kind == "lit":
            LIT.OVERRIDES.pop(rest, None)


NAME_LABELS = {
    "names@0x80102962": "names: demons", "names@0x800d66ba": "names: races",
    "names@0x800d3fae": "names: NPCs", "names@0x800d8400": "names: locations",
    "names@0x800d40de": "names: drinks", "names@0x80113486": "names: spells+descriptions",
    "names@0x80114952": "names: items+descriptions", "names@0x801034da": "names: traits",
}


# ------------------------------------------------------------------ projection
def _nibble_lengths(counter):
    import heapq
    items = list(counter.items())
    pad = (-(len(items) - 1)) % 15
    heap = [(f, i, [s]) for i, (s, f) in enumerate(items)] + [(0, -k - 1, []) for k in range(pad)]
    heapq.heapify(heap)
    depth = Counter()
    n = len(heap) + 1
    while len(heap) > 1:
        kids = [heapq.heappop(heap) for _ in range(min(16, len(heap)))]
        syms = [x for k in kids for x in k[2]]
        for x in syms:
            depth[x] += 1
        heapq.heappush(heap, (sum(k[0] for k in kids), n, syms))
        n += 1
    return depth


def _group(eid):
    if eid.startswith("dlg:"):
        return "bank%d" % (int(eid[4:], 16) >> 12)
    if eid.startswith("name:"):
        return {"demons": "names@0x80102962", "races": "names@0x800d66ba", "npcs": "names@0x800d3fae",
                "locations": "names@0x800d8400", "drinks": "names@0x800d40de",
                "spells": "names@0x80113486", "items": "names@0x80114952"}[eid.split(":")[1]]
    if eid.startswith("trait:"):
        return "names@0x801034da"
    if eid.startswith("menu:"):
        return "menu (field/shop commands)"
    return None


def project(entries, baseline):
    """Projected fill at 100% translation: EN baseline x (RU cost / EN cost)
    measured on the entries translated so far, each language with its own
    16-ary Huffman model (the build retrains its tree on the final corpus)."""
    en_c, ru_c = Counter(), Counter()
    for e in entries.values():
        if _group(e["id"]):
            en_c.update(strip_tags(e["en"]))
            if e.get("ru"):
                ru_c.update(strip_tags(e["ru"]))
    if sum(ru_c.values()) < 300:
        return {}
    for ch in en_c:                      # keep Latin in the RU model at a floor
        ru_c[ch] += 1
    le, lr = _nibble_lengths(en_c), _nibble_lengths(ru_c)
    sums = {}
    for e in entries.values():
        g = _group(e["id"])
        if not g or not e.get("ru") or e.get("_inherited"):
            continue
        a, b = sums.get(g, (0, 0))
        tags = len(tags_of(e["en"]))
        sums[g] = (a + sum(le[c] for c in strip_tags(e["en"])) + tags * 2,
                   b + sum(lr[c] for c in strip_tags(e["ru"])) + tags * 2)
    tot_en = sum(a for a, _ in sums.values()) or 1
    tot_ru = sum(b for _, b in sums.values())
    glob = tot_ru / tot_en
    out = {}
    for name, (used, alloc) in baseline.items():
        a, b = sums.get(name, (0, 0))
        ratio = b / a if a > 400 else glob
        out[name] = (round(used * ratio), alloc, ratio, a > 400)
    return out


def en_baseline(input_bin):
    """Capacity of the pure-English build (cached; computed in a subprocess)."""
    import hashlib
    import subprocess
    root = common.ROOT
    h = hashlib.sha256()
    for f in sorted([root / "build.py", *(root / "tools").glob("*.py")]):
        h.update(f.read_bytes())
    cache = root / "build" / "_check" / f"en_baseline_{h.hexdigest()[:16]}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    cache.parent.mkdir(parents=True, exist_ok=True)
    empty = cache.parent / "empty_text"
    empty.mkdir(exist_ok=True)
    code = ("import sys,json;sys.path[:0]=[%r,%r,%r];import capacity as C;C.REPORT_ONLY=True;"
            "import build,io,contextlib;f=io.StringIO()\n"
            "with contextlib.redirect_stdout(f): build.main(['--input',%r,'--skip-movies','--output-dir',%r])\n"
            "print(json.dumps(C.CAPACITY))") % (str(root / "ru"), str(root / "tools"), str(root),
                                                str(input_bin), str(cache.parent))
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=root)
    if res.returncode:
        raise SystemExit("baseline build failed:\n" + res.stderr[-2000:])
    data = json.loads(res.stdout.strip().splitlines()[-1])
    cache.write_text(json.dumps(data))
    return data


# ------------------------------------------------------------------ report
def progress(entries):
    per = {}
    for e in entries.values():
        f = e["_file"]
        t, d = per.get(f, (0, 0))
        per[f] = (t + 1, d + (1 if e.get("ru") else 0))
    return per


def render_report(entries, rep, cap, static_only, proj=None):
    lines = ["# SMT2 RU — translation check", ""]
    per = progress(entries)
    tot = sum(t for t, _ in per.values())
    done = sum(d for _, d in per.values())
    lines += [f"Translated: **{done}/{tot}** entries ({100 * done / max(tot, 1):.1f}%)", "",
              "| file | translated |", "|---|---|"]
    for f, (t, d) in sorted(per.items()):
        lines.append(f"| {f} | {d}/{t} |")
    if not static_only:
        lines += ["", "## Capacity (real compressor, current text)", "",
                  "| allocation | used | size | fill |", "|---|---|---|---|"]
        for name, (used, alloc) in sorted(cap.items(), key=lambda kv: -kv[1][0] / max(kv[1][1], 1)):
            pct = 100 * used / max(alloc, 1)
            flag = " **OVERFLOW**" if used > alloc else (" (tight)" if pct > 97 else "")
            lines.append(f"| {NAME_LABELS.get(name, name)} | {used} | {alloc} | {pct:.1f}%{flag} |")
    if proj:
        lines += ["", "## Projection at 100% translation", "",
                  "EN baseline x (RU/EN cost ratio measured on what is translated; "
                  "'global' = too little text in that table yet, overall ratio used).", "",
                  "| allocation | projected | size | fill | ratio |", "|---|---|---|---|---|"]
        for name, (p, alloc, ratio, own) in sorted(proj.items(), key=lambda kv: -kv[1][0] / max(kv[1][1], 1)):
            if not (name.startswith("bank") or name.startswith("names@") or name.startswith("menu")):
                continue
            pct = 100 * p / max(alloc, 1)
            flag = " **OVER**" if p > alloc else (" (tight)" if pct > 97 else "")
            lines.append(f"| {NAME_LABELS.get(name, name)} | {p} | {alloc} | {pct:.1f}%{flag} | "
                         f"{ratio:.3f}{'' if own else ' global'} |")
    lines += ["", f"## Errors ({len(rep.errors)})", ""]
    lines += [f"- `{eid}` {msg}" for eid, msg in rep.errors] or ["none"]
    lines += ["", f"## Warnings ({len(rep.warnings)})", ""]
    lines += [f"- `{eid}` {msg}" for eid, msg in rep.warnings] or ["none"]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True)
    ap.add_argument("--text", default="text")
    ap.add_argument("--static-only", action="store_true")
    ap.add_argument("--report", help="write a Markdown report here")
    ap.add_argument("--json", help="write machine-readable results here")
    ap.add_argument("--dict-budget", type=int, help="override build.DICT_BUDGET for the trial")
    args = ap.parse_args(argv)

    import apply as RU
    disc = Disc(args.input)
    entries = RU.load_entries(args.text)
    for e in entries.values():
        if e.get("ru"):
            e["ru"] = RU.normalize(e["ru"])
    w12, w10 = load_widths(disc)
    rep = Report()
    failed = static_checks(entries, rep, w12, w10)
    cap = {}
    if not args.static_only:
        cap, _log = trial_build(args.input, args.text, failed, rep, args.dict_budget)
        for name, (used, alloc) in cap.items():
            if used > alloc:
                rep.err(f"capacity:{NAME_LABELS.get(name, name)}",
                        f"{used}/{alloc} bytes (+{used - alloc}); shorten text in this table/bank")
    proj = None
    if not args.static_only:
        try:
            proj = project(entries, en_baseline(Path(args.input).resolve()))
        except SystemExit as exc:
            rep.warn("projection", str(exc))
    text = render_report(entries, rep, cap, args.static_only, proj)
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps({
            "errors": rep.errors, "warnings": rep.warnings,
            "capacity": {NAME_LABELS.get(k, k): v for k, v in cap.items()},
        }, ensure_ascii=False, indent=1), encoding="utf-8")
    # console summary
    print(text if len(text) < 6000 else text[:6000] + "\n... (see --report for the full list)")
    sys.exit(1 if rep.errors else 0)


if __name__ == "__main__":
    main()
