"""Print per-species pipeline status from each species' status.json.

Usage (normally via checkup_v2.sh, which supplies these args):
    python checkup_v2.py <results_base> <accession> [<accession> ...]
"""
import os
import sys

import status

STATUS_LABELS = {
    "done": "done",
    "error": "error",
    "not_started": "not started",
}


def detail(entry: dict) -> str:
    if entry.get("status") == "done":
        return entry.get("timestamp", "")
    if entry.get("status") == "error":
        return entry.get("message", "")
    return ""


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    results_base, accessions = sys.argv[1], sys.argv[2:]

    header = ["accession", *status.STEPS, "detail"]
    widths = [30, *[14] * len(status.STEPS), 40]
    fmt = "  ".join(f"%-{w}s" for w in widths)

    print(fmt % tuple(header))
    print(fmt % tuple("-" * (w - 1) for w in widths))

    for acc in accessions:
        species_dir = os.path.join(results_base, f"{acc}_results")
        cells = [acc]
        last_detail = ""
        for step in status.STEPS:
            entry = status.get_step(species_dir, step)
            cells.append(STATUS_LABELS.get(entry.get("status"), entry.get("status", "?")))
            last_detail = detail(entry) or last_detail
        cells.append(last_detail[:40])
        print(fmt % tuple(cells))

    return 0


if __name__ == "__main__":
    sys.exit(main())
