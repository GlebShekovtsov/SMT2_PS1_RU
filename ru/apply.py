"""Load translated JSON files (text/*.json) into the build's data modules.

Only entries whose "ru" field is non-empty are applied; everything else keeps
the English text, so partial translations build and can be tested in-game.
An entry with an empty "ru" but a "same_as" pointing at a translated entry
inherits that translation.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: F401  (sets sys.path)
from common import tagged_to_author

import translations as TR
import name_tables as NT
import menu_table as MT
import sys_strings as SS
import map_names as MN
import party_names as PN
import rdlogo as RD
import opening_movie as OM
import literals as LIT

NAME_ATTR = {
    "demons": "DEMONS", "races": "RACES", "npcs": "NPCS", "locations": "LOCATIONS",
    "drinks": "DRINKS", "spells": "SPELLS", "items": "ITEMS",
}


def normalize(text):
    """Light typographic normalisation applied to every RU string."""
    return (text.replace(" ", " ")
                .replace(" ", " ")
                .replace("\r\n", "\n"))


def load_entries(text_dir):
    """id -> entry for every JSON file in text_dir (RU resolved via same_as)."""
    entries = {}
    for path in sorted(Path(text_dir).glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for e in doc["entries"]:
            e["_file"] = path.name
            entries[e["id"]] = e
    for e in entries.values():
        if not e.get("ru") and e.get("same_as"):
            src = entries.get(e["same_as"])
            if src and src.get("ru"):
                e["ru"] = src["ru"]
                e["_inherited"] = True
    return entries


STUB_TEXT = "~"


def stub_dialogue(tagged):
    """Keep every control tag of a message but drop its text (test builds)."""
    parts = tagged_to_author(tagged)
    out = []
    for p in parts:
        if isinstance(p, str) and not (p in _ctrl_names()):
            continue
        out.append(p)
    return [STUB_TEXT] + out


def _ctrl_names():
    import translate_pipeline as TP
    return set(TP.CTRL_NAME) | set(TP.AB_CTRL_INDEX)


def apply(text_dir, verbose=True, stub_untranslated=False):
    """Apply RU text.  stub_untranslated: replace untranslated DIALOGUE with a
    one-character stub (controls kept) so a partial translation always fits;
    useful only for in-game testing of what is already translated."""
    entries = load_entries(text_dir)
    counts = {}
    if stub_untranslated:
        stubbed = 0
        for eid, e in entries.items():
            if eid.startswith("dlg:") and not e.get("ru") and e.get("en"):
                TR.TRANS[int(eid[4:], 16)] = stub_dialogue(e["en"])
                stubbed += 1
        if verbose:
            print(f"RU: {stubbed} untranslated dialogue entries stubbed with {STUB_TEXT!r}")

    def bump(cat):
        counts[cat] = counts.get(cat, 0) + 1

    movies = {"gameover": list(OM.GAMEOVER_LINES), "crawl": list(OM.CRAWL_LINES)}
    for eid, e in entries.items():
        ru = e.get("ru")
        if not ru:
            continue
        ru = normalize(ru)
        kind, _, rest = eid.partition(":")
        if kind == "dlg":
            TR.TRANS[int(rest, 16)] = tagged_to_author(ru)
            bump("dialogue")
        elif kind == "name":
            table, idx = rest.split(":")
            getattr(NT, NAME_ATTR[table])[int(idx)] = ru
            bump("names")
        elif kind == "trait":
            NT.TRAITS_MAP[rest] = ru
            bump("names")
        elif kind == "menu":
            MT.MENU[int(rest)] = ru
            bump("menu")
        elif kind == "abmenu":
            lst = list(MT.AB_MENU)
            lst[int(rest)] = ru
            MT.AB_MENU = tuple(lst)
            bump("menu")
        elif kind == "sys":
            off = int(rest, 16)
            if off in SS.SYS:
                SS.SYS[off] = (SS.SYS[off][0], ru)
            else:
                SS.AUDITED_SYSTEM_TEXT[off] = ru
            bump("system")
        elif kind == "map":
            if not e.get("keep"):
                MN.ENGLISH[int(rest)] = ru
                bump("map_names")
        elif kind == "party":
            i = int(rest)
            PN.NAMES[i] = (ru, PN.NAMES[i][1])
            PN.ENGLISH[i] = ru
            bump("misc")
        elif kind == "rdlogo":
            RD.LINES[int(rest)] = ru
            bump("misc")
        elif kind in ("3dmap", "casino3", "rag"):
            LIT.OVERRIDES[eid] = ru
            bump("misc")
        elif kind == "lit":
            LIT.OVERRIDES[rest] = ru
            bump("misc")
        elif kind == "movie":
            which, idx = rest.split(":")
            movies[which][int(idx)] = ru
            bump("movies")
        else:
            raise SystemExit(f"unknown entry id {eid!r}")
    import translate_pipeline as TP
    TP.CONTROL_SUFFIX["AG"] = LIT.T("party_suffix")
    TP.AB_CONTROL_SUFFIX["A6F"] = LIT.T("party_suffix")
    OM.GAMEOVER_LINES = tuple(movies["gameover"])
    OM.CRAWL_LINES = tuple(movies["crawl"])
    if verbose:
        total = sum(counts.values())
        print(f"RU: applied {total} translated entries " +
              ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return entries, counts
