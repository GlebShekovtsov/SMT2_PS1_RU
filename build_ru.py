#!/usr/bin/env python3
"""SMT2 PSX — Russian build (fork of the English translation build).

    python build_ru.py --input "Shin Megami Tensei II (Japan) (Rev 1).bin" --text text

Loads translated strings from text/*.json (see ru/extract.py and
TRANSLATION_GUIDE.md), then runs the normal build pipeline.  Untranslated
entries fall back to English, so partial translations can be tested.

--stub-untranslated replaces untranslated dialogue with '~' (controls kept):
mixing English and Russian in one Huffman tree inflates both, so a partially
translated script may not fit until the stub is used.

Every option of build.py is accepted (--skip-movies, --no-enhancements,
--output-dir, --xdelta ...).  Output: build/SMT2_RU.bin (+ SMT2_RU.xdelta).
"""
import argparse
import os
import shutil
import subprocess
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "ru"))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))


def _xdelta_cli_fallback(build):
    """Use an xdelta3 executable when the pyxdelta module is unavailable."""
    exe = shutil.which("xdelta3") or shutil.which("xdelta3.exe")
    if exe is None:
        return
    class CLI:
        @staticmethod
        def run(src, dst, patch):
            subprocess.run([exe, "-e", "-9", "-f", "-s", src, dst, patch], check=True)
            return True
    def require():
        try:
            import pyxdelta  # noqa: F401
            return pyxdelta
        except ImportError:
            return CLI
    build.require_pyxdelta = require


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--text", default="text", help="directory with translated JSON (default: text)")
    ap.add_argument("--stub-untranslated", action="store_true",
                    help="test builds: replace untranslated dialogue with '~' so partial "
                         "translations always fit the banks")
    ap.add_argument("-h", "--help", action="store_true")
    args, rest = ap.parse_known_args()
    if args.help:
        print(__doc__)
        rest = ["--help"]
    import apply as RU
    if Path(args.text).is_dir():
        RU.apply(args.text, stub_untranslated=args.stub_untranslated)
    else:
        print(f"RU: text directory {args.text!r} not found - building English text only")
    import build
    build.OUTPUT_BIN_NAME = "SMT2_RU.bin"
    build.OUTPUT_XDELTA_NAME = "SMT2_RU.xdelta"
    _xdelta_cli_fallback(build)
    _hook_graphics(build)
    build.main(rest)


def _hook_graphics(build):
    """Apply user-approved Russian sprite labels right after the stock status-texture
    patch (PACKA already has its final layout there; exe is written afterwards)."""
    import ru_graphics
    stock = build.STATUS.patch_status_texture

    def patch_status_texture(packa, exe):
        stock(packa, exe)
        data = os.environ.get("RU_GRAPHICS_DATA")   # review/test builds only
        ru_graphics.apply(packa, exe, data) if data else ru_graphics.apply(packa, exe)

    build.STATUS.patch_status_texture = patch_status_texture

    # Russian naming-screen grid (only when a layout was approved)
    import json
    path = os.environ.get("RU_GRAPHICS_DATA") or str(ru_graphics.DATA)
    variant = None
    overlays = {}
    if Path(path).exists():
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        variant = data.get("name_entry")
        overlays = data.get("overlays", {})
    # approved overlay strings (automap ...), applied after the overlay's own text patcher
    for name, entries in overlays.items():
        sector, size, patcher = build.OVERLAY_FILES[name]

        def wrapped(src, _p=patcher, _n=name, _e=entries):
            return ru_graphics.apply_overlay(_n, _p(src), _e)
        build.OVERLAY_FILES[name] = (sector, size, wrapped)
    if variant:
        import ru_name_entry as RNE
        build.NE.apply_name_entry = lambda exe: RNE.apply_name_entry(exe, variant)
        build.NE.apply_end_button = lambda exe: RNE.apply_end_button(exe, variant)
        build.NE.patch_atlas = lambda packa, slpm: RNE.patch_atlas(packa, slpm, variant)
        print(f"RU: naming screen layout {variant if isinstance(variant, str) else variant['layout']}")


if __name__ == "__main__":
    main()
