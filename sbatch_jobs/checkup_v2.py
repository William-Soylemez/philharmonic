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
    "pending": "not started",
    "running": "running",
}


def detail(entry: dict) -> str:
    if entry.get("status") == "done":
        return entry.get("timestamp", "")
    if entry.get("status") == "error":
        return entry.get("message", "")
    return ""


def inference_cell(species_dir):
    """Return (cell, detail) for the inference step.

    Shows m/n completed like checkup v1. If any tasks started but failed, flags
    the cell with (!) and surfaces which task IDs failed in the detail column.
    Persists the aggregate back into status.json so it records the outcomes.
    """
    summary = status.refresh_inference(species_dir)
    n = summary["n_tasks"]
    if n is None:
        return "not started", ""
    cell = f"{summary['done']}/{n}"
    det = ""
    if summary["failed"]:
        cell += " (!)"
        det = f"inference failed: {','.join(summary['failed'])}"
    elif summary["done"] >= n:
        det = status.get_step(species_dir, "inference").get("timestamp", "")
    return cell, det


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    results_base, accessions = sys.argv[1], sys.argv[2:]

    header = ["accession", *status.STEPS, "detail"]
    widths = [30, *[15] * len(status.STEPS), 40]
    fmt = "  ".join(f"%-{w}s" for w in widths)

    print(fmt % tuple(header))
    print(fmt % tuple("-" * (w - 1) for w in widths))

    for acc in accessions:
        species_dir = os.path.join(results_base, f"{acc}_results")
        cells = [acc]
        # Prefer surfacing an error/failure detail over a later "done" timestamp.
        error_detail = ""
        last_detail = ""
        for step in status.STEPS:
            if step == "inference":
                cell, det = inference_cell(species_dir)
                cells.append(cell)
                if cell.endswith("(!)"):
                    error_detail = error_detail or det
                else:
                    last_detail = det or last_detail
                continue
            entry = status.get_step(species_dir, step)
            cells.append(STATUS_LABELS.get(entry.get("status"), entry.get("status", "?")))
            det = detail(entry)
            if entry.get("status") == "error":
                error_detail = error_detail or det
            else:
                last_detail = det or last_detail
        cells.append((error_detail or last_detail)[:40])
        print(fmt % tuple(cells))

    return 0


if __name__ == "__main__":
    sys.exit(main())
