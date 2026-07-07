"""Batch-process every species zip in an input directory, then build species_index.json.

Usage:
    python process_all.py <zips_dir> <output_dir>

Expects each input zip named `<species_id>.zip` or `<species_id>_*.zip`.
After processing, writes <output_dir>/species_index.json aggregating every manifest.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from preprocess import preprocess
from schemas import SpeciesIndexEntry


SPECIES_ID_RE = re.compile(r"(GCF_\d+\.\d+|GCA_\d+\.\d+)")


def _species_id_from_zip(zip_path: Path) -> str | None:
    m = SPECIES_ID_RE.search(zip_path.stem)
    return m.group(1) if m else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("zips_dir", type=Path)
    ap.add_argument("output_dir", type=Path)
    args = ap.parse_args()

    zips = sorted(args.zips_dir.glob("*.zip"))
    if not zips:
        print(f"no zips found in {args.zips_dir}", file=sys.stderr)
        sys.exit(1)

    processed: list[SpeciesIndexEntry] = []
    for z in zips:
        sid = _species_id_from_zip(z)
        if sid is None:
            print(f"skip {z.name}: no species id pattern matched", file=sys.stderr)
            continue
        try:
            preprocess(sid, z, args.output_dir)
        except Exception as e:
            print(f"FAILED {sid}: {e}", file=sys.stderr)
            continue
        manifest_path = args.output_dir / "species" / sid / "manifest.json"
        if manifest_path.exists():
            m = json.loads(manifest_path.read_text())
            processed.append(
                SpeciesIndexEntry(
                    id=m["id"],
                    display_name=m.get("display_name", m["id"]),
                    taxid=m.get("taxid"),
                    lineage=m.get("lineage", []),
                )
            )

    index_path = args.output_dir / "species_index.json"
    index_path.write_text(
        json.dumps([e.model_dump() for e in processed], separators=(",", ":"))
    )
    print(f"wrote species_index.json with {len(processed)} entries → {index_path}")
    print(
        "\nUpload with rclone (configure remote `r2` first):\n"
        f"    rclone sync {args.output_dir} r2:philharmonic-db --progress"
    )


if __name__ == "__main__":
    main()
