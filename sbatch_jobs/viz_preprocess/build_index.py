"""Aggregate every species/<id>/manifest.json into a top-level species_index.json.

Usage:
    python build_index.py <output_root>

Run after preprocessing one or more species. Safe to re-run; it scans whatever
species directories currently exist.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schemas import SpeciesIndexEntry


def build_index(output_root: Path) -> int:
    species_dir = output_root / "species"
    if not species_dir.is_dir():
        print(f"no species dir at {species_dir}", file=sys.stderr)
        return 0
    entries: list[SpeciesIndexEntry] = []
    for manifest_path in sorted(species_dir.glob("*/manifest.json")):
        m = json.loads(manifest_path.read_text())
        entries.append(
            SpeciesIndexEntry(
                id=m["id"],
                display_name=m.get("display_name", m["id"]),
                taxid=m.get("taxid"),
                lineage=m.get("lineage", []),
            )
        )
    out = output_root / "species_index.json"
    out.write_text(json.dumps([e.model_dump() for e in entries], separators=(",", ":")))
    print(f"wrote {len(entries)} species → {out}")
    return len(entries)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("output_root", type=Path)
    args = ap.parse_args()
    build_index(args.output_root)


if __name__ == "__main__":
    main()
