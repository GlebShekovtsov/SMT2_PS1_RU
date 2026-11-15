"""Export every translatable string of SMT2 (PSX) as JSON: Japanese original,
current English (from the fan-translation sources) and an empty Russian field.

    python ru/extract.py --input "Shin Megami Tensei II (Japan) (Rev 1).bin" --out text

If the output directory already holds files with Russian filled in, those RU
values are preserved (merge by "id"), so re-running after a source update is safe.

Each output file is {"meta": {...}, "entries": [ {id, jp, en, ru, ...}, ... ]}.
See TRANSLATION_GUIDE.md for the field and tag conventions.
"""
import argparse
import json
import struct
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (Disc, foff, u16, decode_stream, decode_cd_block, render_jp,
                    author_to_tagged, CD_STRUCT, CD_SYM, AB_STRUCT, AB_SYM, ED)

import translations as TR
import name_tables as NT
import menu_table as MT
import sys_strings as SS
import map_names as MN
import party_names as PN
import rdlogo as RD
import opening_movie as OM
import overlay_text as OT
import literals as LIT

# ---------------------------------------------------------------- dialogue
BANKS = [
    # bank, description, source, base, allocation, tree
    (0, "field/system: COMP, shops, churches, early story", "packa", 0x32FB000, 0x7800, "CD"),
    (1, "field: Hanada's lab, STEVEN", "packa", 0x3302800, 0x1000, "CD"),
    (2, "town/NPC: casino, Lucifer, Keter", "packa", 0x3303800, 0x8000, "CD"),
    (3, "story/events", "packa", 0x330B800, 0x6800, "CD"),
    (4, "demon negotiation fragments (A/B)", "packa", 0x32F1000, 0x7800, "AB"),
    (5, "battle-command / event fragments (A/B)", "packa", 0x32F8800, 0x2800, "AB"),
    (6, "battle messages (exe)", "slpm", foff(0x80115BD8), 0x80116F2C - 0x80115BD8, "CD"),
    (7, "clear data / shop responses / endings (exe)", "slpm", foff(0x80116F2C), 0x80117CC8 - 0x80116F2C, "CD"),
]


def _ab_bank(buf, base, alloc, exe):
    do = struct.unpack_from("<H", buf, base)[0]
    n = (do - 2) // 2
    offs = struct.unpack_from(f"<{n}H", buf, base + 2)
    uniq = sorted(set(offs))
    nxt = {o: (uniq[i + 1] if i + 1 < len(uniq) else None) for i, o in enumerate(uniq)}
    out = []
    for o in offs:
        start = base + do + o
        if nxt[o] is None:
            end = buf.find(b"\xCC" * 16, start, base + alloc)
        else:
            end = base + do + nxt[o]
        out.append(decode_stream(buf, start, exe, AB_STRUCT, AB_SYM, end=end,
                                 stop_at_ed=False, ab=True))
    return out


def export_dialogue(disc):
    files = {}
    src = {"packa": disc.packa, "slpm": disc.slpm}
    for bank, desc, s, base, alloc, tree in BANKS:
        buf = src[s]
        if tree == "CD":
            msgs = decode_cd_block(buf, base, disc.slpm)
            if bank in (6, 7):
                pass
        else:
            msgs = _ab_bank(buf, base, alloc, disc.slpm)
        entries = []
        seen = {}
        for i, toks in enumerate(msgs):
            mid = (bank << 12) | i
            author = TR.TRANS.get(mid)
            en = author_to_tagged(author) if author else ""
            jp = render_jp(toks, ab=(tree == "AB"))
            e = {"id": f"dlg:{mid:#06x}", "jp": jp, "en": en, "ru": ""}
            key = (jp, en)
            if key in seen:
                e["same_as"] = seen[key]
            else:
                seen[key] = e["id"]
            entries.append(e)
        files[f"dialogue_bank{bank}.json"] = {
            "meta": {
                "category": "dialogue",
                "bank": bank,
                "description": desc,
                "tree": tree,
                "format": "tagged",
                "notes": ("A/B bank: no {ED}; keep every {Axx} tag exactly as in EN"
                          if tree == "AB" else
                          "C/D bank: every entry must end with {ED}; keep inserts (SY, MG, IT...) "),
            },
            "entries": entries,
        }
    return files


# ---------------------------------------------------------------- name tables
def _single(slpm, base, n):
    out = []
    for i in range(n):
        o = u16(slpm, base + i * 2)
        toks = decode_stream(slpm, foff(base + o), slpm, CD_STRUCT, CD_SYM)
        out.append(render_jp(toks, cr_as_newline=True).replace("{ED}", ""))
    return out


def _twolevel(slpm, base, n):
    do = u16(slpm, base)
    out = []
    for i in range(n):
        o = u16(slpm, base + (i + 1) * 2)
        toks = decode_stream(slpm, foff(base + do + o), slpm, CD_STRUCT, CD_SYM)
        out.append(render_jp(toks, cr_as_newline=True).replace("{ED}", ""))
    return out


NAME_TABLES = [
    # key, list attr, layout, base, count, note
    ("demons", "DEMONS", "single", 0x80102962, 311,
     "Demon names. Used in dialogue inserts, menus, overlays and a 17-byte record "
     "cache: max 17 chars. Party HUD plate is 80px of 10x10 font."),
    ("races", "RACES", "single", 0x801043f8, 44, "Demon races (clans)."),
    ("npcs", "NPCS", "single", 0x801119f2, 23, "Generic NPC names. Table is tiny: keep short!"),
    ("locations", "LOCATIONS", "single", 0x801132f2, 16, "Region names (terminals)."),
    ("drinks", "DRINKS", "single", 0x80113388, 9, "Valhalla bar drinks. Table is tiny."),
    ("spells", "SPELLS", "twolevel", 0x80113486, 321,
     "0-159 spell names, 160-320 descriptions ('\\n' = line break, each line <= 124px)."),
    ("items", "ITEMS", "twolevel", 0x80114952, 349, "Item / equipment names and descriptions."),
]


def export_names(disc):
    files = {}
    for key, attr, layout, base, n, note in NAME_TABLES:
        en_list = getattr(NT, attr)
        if len(en_list) != n:
            raise SystemExit(f"{attr}: {len(en_list)} != {n}")
        jp = (_single if layout == "single" else _twolevel)(disc.slpm, base, n)
        entries = [{"id": f"name:{key}:{i}", "jp": jp[i], "en": en_list[i], "ru": ""}
                   for i in range(n)]
        files[f"names_{key}.json"] = {
            "meta": {"category": "names", "table": attr, "format": "plain",
                     "notes": note + " All name tables share one byte budget each; "
                              "see check report."},
            "entries": entries,
        }
    # traits: keyed by the Japanese text (CR shown as '/')
    entries = [{"id": f"trait:{jp}", "jp": jp.replace("/", "\n"), "en": en, "ru": ""}
               for jp, en in NT.TRAITS_MAP.items()]
    files["names_traits.json"] = {
        "meta": {"category": "names", "table": "TRAITS_MAP", "format": "plain",
                 "notes": "Demon affinity summaries; '\\n' = line break (max 3 lines)."},
        "entries": entries,
    }
    return files


# ---------------------------------------------------------------- menus
def export_menus(disc):
    slpm = disc.slpm
    files = {}
    entries = []
    for i in range(MT.N_MENU):
        o = u16(slpm, MT.MENU_OT + i * 2)
        toks = decode_stream(slpm, foff(MT.MENU_DATA + o), slpm, CD_STRUCT, CD_SYM)
        en = MT.MENU.get(i, "")
        entries.append({"id": f"menu:{i}", "jp": render_jp(toks).replace("{ED}", ""),
                        "en": en, "ru": ""})
    files["menu.json"] = {
        "meta": {"category": "menu", "format": "plain",
                 "notes": "Field/shop/COMP command menus (12x12 font). Empty EN = keep empty."},
        "entries": entries,
    }
    entries = []
    for i in range(MT.N_AB_MENU):
        o = u16(slpm, MT.AB_MENU_OT + i * 2)
        toks = decode_stream(slpm, foff(MT.AB_MENU_STOCK_DATA + o), slpm, AB_STRUCT, AB_SYM,
                             stop_at_ed=False, ab=True, stop_at_any_ctrl=True)
        jp = render_jp([t for t in toks if not t[1]])
        entries.append({"id": f"abmenu:{i}", "jp": jp, "en": MT.AB_MENU[i], "ru": ""})
    files["menu_negotiation.json"] = {
        "meta": {"category": "menu", "format": "plain",
                 "notes": "Negotiation answer choices. Window text width is 276px (12x12 font). "
                          "Sentence case (first letter capital)."},
        "entries": entries,
    }
    return files


# ---------------------------------------------------------------- exe system strings
def export_system(disc):
    slpm = disc.slpm
    entries = []
    for off in sorted(set(SS.SYS) | set(SS.AUDITED_SYSTEM_TEXT)):
        end = slpm.index(0, off)
        jp = slpm[off:end].decode("cp932", errors="replace")
        if off in SS.SYS:
            gap, en = SS.SYS[off]
            src = "SYS"
        else:
            en = SS.AUDITED_SYSTEM_TEXT[off]
            gap = ((end - off + 1 + 3) // 4) * 4
            src = "AUDITED"
        fw = off in SS.FULLWIDTH_SYSTEM_TEXT
        gap = min(gap, SS.FIXED_COPY_BYTES.get(off, gap))
        limit = (gap - 1) // 2 if fw else gap - 2
        entries.append({
            "id": f"sys:{off:#06x}", "jp": jp, "en": en, "ru": "",
            "max_chars": limit,
            "encoding": "fullwidth" if fw else "1-byte",
            "src": src,
        })
    return {"system.json": {
        "meta": {"category": "system", "format": "plain",
                 "notes": "Fixed-size slots inside the executable. RU must not exceed max_chars "
                          "(hard limit; the build refuses longer strings). Leading/trailing spaces "
                          "are significant (text is glued to a name)."},
        "entries": entries,
    }}


# ---------------------------------------------------------------- map names
def export_map_names(disc):
    slpm = disc.slpm
    area = [struct.unpack_from("<I", slpm, foff(MN.AREA_TABLE) + i * 4)[0] for i in range(MN.AREA_COUNT)]
    mapt = [struct.unpack_from("<I", slpm, foff(MN.MAP_TABLE) + i * 4)[0] for i in range(MN.MAP_COUNT)]
    uniq = sorted({p for p in area + mapt if MN.STR_LO <= p < MN.STR_HI})
    entries = []
    for i, (addr, en) in enumerate(zip(uniq, MN.ENGLISH)):
        raw = slpm[foff(addr):slpm.index(0, foff(addr))]
        jp = ""
        j = 0
        while j < len(raw):
            if raw[j] >= 0x80:
                code = (raw[j] << 8) | raw[j + 1]
                jp += "@" if code == MN.BR else bytes(raw[j:j + 2]).decode("cp932", "replace")
                j += 2
            else:
                jp += chr(raw[j]); j += 1
        e = {"id": f"map:{i}", "jp": jp, "en": en if en is not None else "", "ru": ""}
        if en is None:
            e["keep"] = True
        entries.append(e)
    return {"map_names.json": {
        "meta": {"category": "map_names", "format": "plain",
                 "notes": "Location names (save list, automap header). '@' = line break for the "
                          "two-line save display; do NOT put a space before '@'. Entries with "
                          "keep=true are not translated (left as in the original)."},
        "entries": entries,
    }}


# ---------------------------------------------------------------- misc
def export_misc(disc):
    entries = []
    for i, (en, jp) in enumerate(PN.NAMES):
        entries.append({"id": f"party:{i}", "jp": jp, "en": en, "ru": "", "max_chars": 8,
                        "note": "Default party name (fullwidth, max 8 chars)."})
    jp_rd = ["このゲームはフィクションであり",
             "登場する人物や団体は実在の個人および団体とは一切関係ありません", ""]
    for i, en in enumerate(RD.LINES):
        entries.append({"id": f"rdlogo:{i}", "jp": jp_rd[i], "en": en, "ru": "",
                        "note": "Boot disclaimer line. All three lines share 105 bytes (1 byte/char + 2)."})
    for key, (jp, en, note) in LIT.overlay_entries().items():
        entries.append({"id": key, "jp": jp, "en": en, "ru": "", "note": note})
    for key, item in LIT.LITERALS.items():
        e = {"id": f"lit:{key}", "jp": item.get("jp", ""), "en": item["en"], "ru": ""}
        if "note" in item:
            e["note"] = item["note"]
        if "max_chars" in item:
            e["max_chars"] = item["max_chars"]
        entries.append(e)
    files = {"misc.json": {
        "meta": {"category": "misc", "format": "plain",
                 "notes": "Party names, boot disclaimer, overlay (automap/casino/Rag) strings and "
                          "short UI literals that live in code. Respect max_chars where given."},
        "entries": entries,
    }}
    movie = []
    for key, lines in LIT.movie_lines().items():
        for i, en in enumerate(lines):
            movie.append({"id": f"movie:{key}:{i}", "jp": "", "en": en, "ru": "",
                          "note": "Burned into the opening/game-over movie with the 12x12 font; "
                                  "each line must fit 320px."})
    files["movies.json"] = {
        "meta": {"category": "movies", "format": "plain",
                 "notes": "Movie captions (only used when movies are rebuilt; needs ffmpeg). "
                          "No Japanese text source: the original text is baked into the video."},
        "entries": movie,
    }
    return files


# ---------------------------------------------------------------- driver
def merge_existing(path, new):
    if not path.exists():
        return new
    old = json.loads(path.read_text(encoding="utf-8"))
    ru = {e["id"]: e for e in old.get("entries", [])}
    for e in new["entries"]:
        o = ru.get(e["id"])
        if o:
            for k in ("ru", "ru_note", "status"):
                if o.get(k):
                    e[k] = o[k]
    return new


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="Japan Rev 1 MODE2/2352 BIN")
    ap.add_argument("--out", default="text", help="output directory (default: text)")
    args = ap.parse_args(argv)
    disc = Disc(args.input)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    for fn in (export_dialogue, export_names, export_menus, export_system,
               export_map_names, export_misc):
        files.update(fn(disc))
    total = 0
    for name, doc in files.items():
        p = out / name
        doc = merge_existing(p, doc)
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        n = len(doc["entries"])
        total += n
        print(f"  {name:28s} {n:5d} entries")
    print(f"{total} entries -> {out}/")


if __name__ == "__main__":
    main()
