"""Per-species pipeline status tracking, stored as <species_dir>/status.json.

Each species results directory gets one status.json of the form:

    {
      "steps": {
        "download_filter": {"status": "done", "timestamp": "2026-06-07T12:34:56+00:00"},
        ...
      }
    }

A step is one of: "not_started" (the implicit default when absent), "done"
(carries a UTC timestamp), or "error" (carries a message). Steps are added one
at a time as the pipeline is migrated onto this tracker; only download_filter is
wired up so far.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

STATUS_FILE = "status.json"

# Canonical step order, used by checkup for display. Steps not yet wired into the
# pipeline simply show as "not started" until their job starts recording status.
STEPS = ["download_filter"]


def _path(species_dir) -> Path:
    return Path(species_dir) / STATUS_FILE


def read(species_dir) -> dict:
    """Return the parsed status dict for a species, or {} if missing/corrupt."""
    p = _path(species_dir)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def get_step(species_dir, step) -> dict:
    """Return a single step entry, defaulting to {"status": "not_started"}."""
    return read(species_dir).get("steps", {}).get(step, {"status": "not_started"})


def set_status(species_dir, step, status, message=None) -> dict:
    """Record a step's status. "done" gets a UTC timestamp; message is optional."""
    data = read(species_dir)
    steps = data.setdefault("steps", {})
    entry = {"status": status}
    if status == "done":
        entry["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if message:
        entry["message"] = message
    steps[step] = entry

    p = _path(species_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) + "\n")
    return entry
