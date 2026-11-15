# -*- coding: utf-8 -*-
"""Registry of short player-facing strings that the English build hard-codes
inside patch code (rather than in the big data tables).

The RU toolkit fork routes every such site through ``T(key)``, so a translation
can override it without touching code.  ``ru/extract.py`` exports this registry
to text/misc.json; ``ru/apply.py`` fills OVERRIDES from the translated file.

Each literal: en (current English), jp (stock Japanese, for reference),
max_chars (hard slot limit, when the slot is fixed), note.
"""

OVERRIDES = {}


def T(key):
    """Return the active text for a registered literal (RU override or EN)."""
    if key in OVERRIDES and OVERRIDES[key]:
        return OVERRIDES[key]
    return LITERALS[key]["en"]


LITERALS = {
    # --- build.py _patch_message_control_literals (fullwidth, fixed slots)
    "bar_drink_prompt": {"en": "Your drink?", "jp": "どちらが飲みますか？", "max_chars": 11,
                         "note": "Valhalla bar prompt (fullwidth slot, 24 bytes)."},
    "stat_st": {"en": "ST", "jp": "力", "max_chars": 3, "note": "PP insert: Strength abbreviation."},
    "stat_in": {"en": "IN", "jp": "知恵", "max_chars": 3, "note": "PP insert: Intelligence abbreviation."},
    "stat_ma": {"en": "MA", "jp": "魔力", "max_chars": 3, "note": "PP insert: Magic abbreviation."},
    "stat_vi": {"en": "VI", "jp": "体力", "max_chars": 3, "note": "PP insert: Vitality abbreviation."},
    "stat_ag": {"en": "AG", "jp": "速さ", "max_chars": 3, "note": "PP insert: Agility abbreviation."},
    "stat_lu": {"en": "LU", "jp": "運", "max_chars": 3, "note": "PP insert: Luck abbreviation."},
    # --- build.py casino prize panel (raw literal, centred in a 96px sprite)
    "casino_item_max": {"en": "ITEM MAX", "jp": "ＩＴＥＭ　ＭＡＸ", "max_chars": 8,
                        "note": "Casino prize panel placeholder (fullwidth, 96px wide)."},
    # --- sys_strings.patch_composed_prompts: '<verb> <name>?' one-line confirms
    "dismiss_verb": {"en": "Dismiss ", "jp": "と別れます／よろしいですか？", "max_chars": 8,
                     "note": "Verb placed BEFORE a demon name: '<verb><name>?'. Keep trailing space."},
    "discard_verb": {"en": "Discard ", "jp": "を捨てます／よろしいですか？", "max_chars": 8,
                     "note": "Verb placed BEFORE an item name: '<verb><item>?'. Keep trailing space."},
    "save_title": {"en": "SMT II", "jp": "真・女神転生２", "max_chars": 7,
                   "note": "Game title at the start of every save-list row (fullwidth)."},
    # --- build_prod_exe item target prompt (fullwidth copy, 32 bytes)
    "item_target_prompt": {"en": "Use it on whom?", "jp": "誰に使いますか？", "max_chars": 15,
                           "note": "Field item target prompt (fullwidth)."},
    # --- compendium (enhanced build only)
    "compendium_menu": {"en": "Demon Compendium", "jp": "",
                        "note": "Cathedral menu entry added by the Compendium enhancement."},
    "compendium_cost": {"en": "Summon Cost:        Macca", "jp": "", "max_chars": 26,
                        "note": "Compendium price line. Characters 13-18 (0-based) MUST be spaces: "
                                "the game writes a right-aligned 6-digit price there. "
                                "Example: 'Цена вызова:         макка'."},
    # --- translate_pipeline: text appended after the party-leader inserts
    "party_suffix": {"en": "'s party", "jp": "たち",
                     "note": "Appended automatically after {AG} / {A6F} (party leader name). "
                             "Russian cannot decline the inserted name, so use a form that "
                             "follows a nominative name, e.g. ' и отряд' -> 'Хоук и отряд'."},
    # --- opening movie date card
    "movie_date_card": {"en": "20XX  TOKYO", "jp": "２０ＸＸ年　東京",
                        "note": "Opening date card (movie rebuild only)."},
}


# ---- overlay strings (3DMAP.BIN / CASINO3.BIN / RAG.BIN), one-byte encoded
# key -> (file offset, slot bytes, stock Japanese, English)
OVERLAY_3DMAP = {
    "3dmap:0x024": (0x024, 0x24, "ここではＣＯＭＰを使用できません", "The COMP can't be used here."),
    "3dmap:0x048": (0x048, 0x23, "ＣＯＭＰを使える状態ではありません", "You can't use the COMP now."),
    "3dmap:0x20c": (0x20C, 0x18, "その他の状況に応じて", "Other purposes:"),
    "3dmap:0x224": (0x224, 0x10, "ボス部屋などに", "Boss areas:"),
    "3dmap:0x234": (0x234, 0x14, "宝箱の設置ポイント", "Treasure spots:"),
    "3dmap:0x248": (0x248, 0x18, "イベント発生ポイント", "Event locations:"),
    "3dmap:0x260": (0x260, 0x10, "通常の用途に", "General use:"),
    "3dmap:0x270": (0x270, 0x14, "などに使用します", "Mark this spot."),
    "3dmap:0x284": (0x284, 0x0C, "使用します", "Mark here."),
    "3dmap:0x290": (0x290, 0x18, "このマーカーを消します", "Delete this marker."),
    "3dmap:0x2a8": (0x2A8, 0x24, "マーカーの種類を選択してください", "Select a marker type."),
    "3dmap:0x2cc": (0x2CC, 0x28, "その場所にはマーカーをセットできません", "You can't place a marker there."),
    "3dmap:0x2f4": (0x2F4, 0x18, "マーカーをセットします", "Place a marker."),
}
OVERLAY_CASINO3 = {
    "casino3:0xc98": (0xC98, 0x0C, "ハズサナイ", "Keep"),
    "casino3:0xca4": (0xCA4, 0x0C, "センコウ", "First"),
    "casino3:0xcb0": (0xCB0, 0x0C, "コウコウ", "Second"),
    "casino3:0xcbc": (0xCBC, 0x10, "あくま　ＭＡＸ", "DEMON MAX"),
    "casino3:0xccc": (0xCCC, 0x10, "どうしますか？", "What now?"),
    "casino3:0xcdc": (0xCDC, 0x10, "ドレカハズス", "Remove which?"),
}
OVERLAY_RAG = {
    "rag:0x008": (0x008, 0x10, "アーシーズ", "Earthies"),
}
OVERLAY_GROUPS = {"3DMAP": OVERLAY_3DMAP, "CASINO3": OVERLAY_CASINO3, "RAG": OVERLAY_RAG}


def overlay_text(key):
    for group in OVERLAY_GROUPS.values():
        if key in group:
            en = group[key][3]
            return OVERRIDES.get(key) or en
    raise KeyError(key)


def overlay_entries():
    """key -> (jp, en, note) for export."""
    out = {}
    for name, group in OVERLAY_GROUPS.items():
        for key, (off, gap, jp, en) in group.items():
            out[key] = (jp, en, f"{name}.BIN overlay slot, 1 byte/char, max {gap - 2} chars.")
    return out


def movie_lines():
    import opening_movie as OM
    return {"gameover": list(OM.GAMEOVER_LINES), "crawl": list(OM.CRAWL_LINES)}
