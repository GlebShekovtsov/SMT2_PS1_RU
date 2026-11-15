"""Merge a flat {id: ru_text} JSON (or several) into the text/*.json files.

    python ru/merge.py --text text batch_001.json batch_002.json

Useful when translation is produced in batches: each batch is a small JSON
object mapping entry ids to Russian strings.  Unknown ids are reported.
Pass --overwrite to replace RU values that are already filled.
"""
import argparse
import json
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--text", default="text")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("batches", nargs="+")
    args = ap.parse_args(argv)
    updates = {}
    for b in args.batches:
        updates.update(json.loads(Path(b).read_text(encoding="utf-8")))
    seen = set()
    changed = skipped = 0
    for path in sorted(Path(args.text).glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        dirty = False
        for e in doc["entries"]:
            if e["id"] in updates:
                seen.add(e["id"])
                if e.get("ru") and not args.overwrite and e["ru"] != updates[e["id"]]:
                    skipped += 1
                    continue
                if e.get("ru") != updates[e["id"]]:
                    e["ru"] = updates[e["id"]]
                    changed += 1
                    dirty = True
        if dirty:
            path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    unknown = sorted(set(updates) - seen)
    print(f"merged {changed} entries; {skipped} kept (already translated, use --overwrite)")
    if unknown:
        print(f"unknown ids ({len(unknown)}): {', '.join(unknown[:20])}{' ...' if len(unknown) > 20 else ''}")


if __name__ == "__main__":
    main()
