"""Per-species pipeline status tracking, stored as <species_dir>/status.json.

Each species results directory gets one status.json of the form:

    {
      "steps": {
        "download_filter": {"status": "done", "timestamp": "2026-06-07T12:34:56+00:00"},
        "inference": {"status": "running", "n_tasks": 49, "done": 47, "failed": ["12"]},
        ...
      }
    }

A step is one of: "not_started" (the implicit default when absent), "done"
(carries a UTC timestamp), or "error" (carries a message).

The inference step is special: it is produced by a SLURM job array of up to a
few hundred independent tasks running on different nodes. Concurrently mutating
one JSON file from all of them would race, so each array task instead drops its
own marker file under <species_dir>/dscript_work/task_status/<task_id> containing
"done" or "failed" (race-free, since the filenames are distinct). The inference
JSON entry is seeded with n_tasks at split time; inference_summary()/
refresh_inference() aggregate the markers into a done count + failed list.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

STATUS_FILE = "status.json"

# Where per-array-task outcome markers live, relative to the species dir.
TASK_STATUS_DIR = "dscript_work/task_status"

# Canonical step order, used by checkup for display. Steps not yet recorded for a
# species simply show as "not started".
STEPS = [
    "download_filter",
    "candidates",
    "embed",
    "split",
    "inference",
    "cluster",
    "describe",
    "visualize",
]


def _path(species_dir) -> Path:
    return Path(species_dir) / STATUS_FILE


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read(species_dir) -> dict:
    """Return the parsed status dict for a species, or {} if missing/corrupt."""
    p = _path(species_dir)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write(species_dir, data) -> None:
    p = _path(species_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) + "\n")


def get_step(species_dir, step) -> dict:
    """Return a single step entry, defaulting to {"status": "not_started"}."""
    return read(species_dir).get("steps", {}).get(step, {"status": "not_started"})


def set_status(species_dir, step, status, message=None) -> dict:
    """Record a step's status. "done" gets a UTC timestamp; message is optional."""
    data = read(species_dir)
    steps = data.setdefault("steps", {})
    entry = {"status": status}
    if status == "done":
        entry["timestamp"] = _now()
    if message:
        entry["message"] = message
    steps[step] = entry
    _write(species_dir, data)
    return entry


# --- inference (job-array) tracking -----------------------------------------

def init_inference(species_dir, n_tasks) -> dict:
    """Seed the inference step at split time with the total task count.

    Resets any stale done/failed aggregate so a re-split starts clean. Per-task
    markers are cleared too, since the task numbering may have changed.
    """
    n_tasks = int(n_tasks)
    data = read(species_dir)
    steps = data.setdefault("steps", {})
    steps["inference"] = {"status": "pending", "n_tasks": n_tasks, "done": 0, "failed": []}
    _write(species_dir, data)

    marker_dir = Path(species_dir) / TASK_STATUS_DIR
    if marker_dir.is_dir():
        for f in marker_dir.iterdir():
            if f.is_file():
                f.unlink()
    return steps["inference"]


def record_task(species_dir, task_id, outcome) -> None:
    """Race-free per-task outcome marker (one distinct file per array task)."""
    if outcome not in ("done", "failed"):
        raise ValueError(f"task outcome must be 'done' or 'failed', got {outcome!r}")
    d = Path(species_dir) / TASK_STATUS_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / str(task_id)).write_text(outcome + "\n")


def inference_summary(species_dir) -> dict:
    """Aggregate per-task markers. Returns {n_tasks, done, failed, started}.

    n_tasks is None when split hasn't recorded the array size yet. failed is a
    sorted list of task-id strings. This is a pure read (no writes).
    """
    n_tasks = get_step(species_dir, "inference").get("n_tasks")
    d = Path(species_dir) / TASK_STATUS_DIR
    done, failed = 0, []
    if d.is_dir():
        for f in sorted(d.iterdir()):
            if not f.is_file():
                continue
            try:
                outcome = f.read_text().strip()
            except OSError:
                continue
            if outcome == "done":
                done += 1
            elif outcome == "failed":
                failed.append(f.name)
    failed.sort(key=lambda x: (0, int(x)) if x.isdigit() else (1, x))
    return {"n_tasks": n_tasks, "done": done, "failed": failed, "started": done + len(failed)}


def refresh_inference(species_dir) -> dict:
    """Recompute the inference aggregate from markers and persist it into the JSON.

    Returns the summary. Status is derived: "error" if any task failed, "done"
    when all n_tasks succeeded, "running" once some have started, else "pending".
    No-op (returns summary only) if split hasn't seeded the inference entry.
    """
    summary = inference_summary(species_dir)
    data = read(species_dir)
    entry = data.get("steps", {}).get("inference")
    if entry is None:
        return summary

    n, done, failed = summary["n_tasks"], summary["done"], summary["failed"]
    if failed:
        st = "error"
    elif n is not None and done >= n:
        st = "done"
    elif summary["started"] > 0:
        st = "running"
    else:
        st = "pending"

    entry["status"] = st
    entry["done"] = done
    entry["failed"] = failed
    if st == "done" and "timestamp" not in entry:
        entry["timestamp"] = _now()
    elif st != "done":
        entry.pop("timestamp", None)
    data["steps"]["inference"] = entry
    _write(species_dir, data)
    return summary


def main(argv=None) -> int:
    """CLI so shell jobs can record status. Subcommands:

        status.py set <species_dir> <step> <status> [message]
        status.py init-inference <species_dir> <n_tasks>
        status.py task <species_dir> <task_id> <done|failed>
        status.py refresh-inference <species_dir>
    """
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else ""

    if cmd == "set" and len(argv) >= 4:
        _, species_dir, step, st = argv[:4]
        message = argv[4] if len(argv) > 4 else None
        set_status(species_dir, step, st, message=message)
        return 0
    if cmd == "init-inference" and len(argv) == 3:
        init_inference(argv[1], argv[2])
        return 0
    if cmd == "task" and len(argv) == 4:
        record_task(argv[1], argv[2], argv[3])
        return 0
    if cmd == "refresh-inference" and len(argv) == 2:
        refresh_inference(argv[1])
        return 0

    print(main.__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
