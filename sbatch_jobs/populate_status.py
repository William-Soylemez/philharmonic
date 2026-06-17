"""Backfill each species' status.json by scanning pipeline logs and artifacts.

Intended for species that ran before per-species status tracking existed (or
whose status.json is stale). The original checkup only checked whether output
files existed; this additionally scans each step's log for errors, so a step
that left a partial/old artifact behind but actually errored gets flagged.

For each step it combines two signals:
  * artifact  -- did the step's expected output file get produced?
  * log       -- does the step's log show error markers?

and resolves them:
  artifact present, no error   -> done           (recorded automatically)
  artifact missing, error      -> error          (recorded automatically)
  artifact missing, no log     -> not started    (recorded automatically)
  artifact present, but error  -> ASK  (artifact exists yet the log errored)
  artifact missing, log clean  -> ASK  (ran, no obvious error, but no output)

For the ambiguous cases it prints the tail of the relevant log and asks you to
decide, unless --auto (which resolves ambiguous cases to "error" with a note).

The inference step is a SLURM job array; it is reconstructed into the same
per-task marker files that status.py uses, so checkup_v2 keeps working.

Usage (normally via populate_status.sh, which supplies paths from common.sh):
    python populate_status.py --results-base <dir> [options] <accession> ...
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import status

# Error signatures scanned for in logs (case-insensitive). Heuristic: a false
# positive just routes a step to the interactive prompt, so we err toward broad.
ERROR_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"traceback \(most recent call last\)",
        r"\berror:",
        r"\bexception\b",
        r"\bfailed\b",
        r"\bfatal\b",
        r"slurmstepd: error",
        r"\bcancelled\b",
        r"due to time limit",
        r"out of memory",
        r"oom[-_ ]?kill",
        r"\bkilled\b",
        r"command not found",
        r"no such file or directory",
        r"cuda (out of memory|error)",
        r"segmentation fault",
        r"core dumped",
        r"memoryerror",
    )
]


def newest(*globs: Path):
    """Return the most recently modified file matching any of the given globs."""
    candidates = []
    for g in globs:
        candidates.extend(p for p in g.parent.glob(g.name) if p.is_file())
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def log_errors(path: Path) -> list[str]:
    """Return error-matching lines from a log file (empty if none / unreadable)."""
    if path is None or not path.is_file():
        return []
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return []
    return [ln for ln in lines if any(p.search(ln) for p in ERROR_PATTERNS)]


def tail(path: Path, n: int) -> str:
    try:
        return "\n".join(path.read_text(errors="replace").splitlines()[-n:])
    except OSError:
        return "<unreadable>"


def ask(step: str, log_path: Path, reason: str, tail_n: int) -> str | None:
    """Show context and ask the user how to record an ambiguous step.

    Returns a status string, or None to leave the step unchanged.
    """
    print(f"\n  ? {step}: {reason}")
    if log_path is not None:
        print(f"    log: {log_path}")
        print("    --- tail " + "-" * 50)
        for line in tail(log_path, tail_n).splitlines():
            print(f"    | {line}")
        print("    " + "-" * 59)
    else:
        print("    (no log found for this step)")
    while True:
        choice = input(
            "    record as [d]one / [e]rror / [n]ot started / [s]kip? "
        ).strip().lower()
        if choice in ("d", "done"):
            return "done"
        if choice in ("e", "error"):
            return "error"
        if choice in ("n", "not", "not_started"):
            return "not_started"
        if choice in ("s", "skip", ""):
            return None
        print("    please answer d, e, n, or s")


def resolve_generic(step, species_dir, logs_dir, artifacts, log_globs, args):
    """Decide and record a non-inference step's status."""
    artifact_ok = bool(artifacts) and all(a.exists() for a in artifacts)
    log_path = newest(*[logs_dir / g for g in log_globs]) if log_globs else None
    errors = log_errors(log_path)

    if artifact_ok and not errors:
        chosen, message, auto = "done", None, True
    elif not artifact_ok and not log_path:
        chosen, message, auto = "not_started", None, True
    elif not artifact_ok and errors:
        chosen, message, auto = "error", f"log shows: {errors[0][:160]}", True
    elif artifact_ok and errors:
        chosen, message, auto = (
            None,
            None,
            False,
        )  # artifact present but log errored -> ambiguous
    else:  # not artifact_ok and log_path and not errors
        chosen, message, auto = None, None, False  # ran, no output, no obvious error

    if auto and not args.always_ask:
        status.set_status(species_dir, step, chosen, message=message)
        detail = f" ({message})" if message else ""
        print(f"  {step:16s} -> {chosen}{detail}")
        return

    # Ambiguous (or --always-ask). Build a reason for the prompt.
    if not auto:
        reason = (
            "artifact present but log shows errors"
            if artifact_ok
            else "no output artifact produced, but log shows no obvious error"
        )
    else:
        reason = f"auto-resolved to {chosen}; confirm"

    if args.auto:
        # Non-interactive: lean toward error for ambiguous cases, keep auto picks.
        chosen = chosen if auto else "error"
        message = message or reason
        status.set_status(species_dir, step, chosen, message=message)
        print(f"  {step:16s} -> {chosen} ({message})")
        return

    decision = ask(step, log_path, reason, args.tail)
    if decision is None:
        print(f"  {step:16s} -> (unchanged)")
    else:
        msg = (errors[0][:160] if (decision == "error" and errors) else None)
        status.set_status(species_dir, step, decision, message=msg)
        print(f"  {step:16s} -> {decision}")


def resolve_inference(species_dir, logs_dir, args):
    """Reconstruct the inference job-array state into per-task markers.

    done   = a predictions_task_<i>.positive.tsv exists for the task
    failed = the task's array log shows errors
    Tasks that ran but left no output and no obvious error are surfaced together
    and resolved interactively (or to failed under --auto).
    """
    work = Path(species_dir) / "dscript_work"
    taskfiles = sorted(work.glob("dscript_*_tasks.sh"))
    if not taskfiles:
        print("  inference        -> not started (no task file; split not done)")
        return

    n_tasks = sum(1 for _ in taskfiles[0].open())
    # Seed n_tasks only if this species was never tracked, so we don't wipe real
    # markers from a tracked run (init_inference clears the marker directory).
    if status.get_step(species_dir, "inference").get("n_tasks") is None:
        status.init_inference(species_dir, n_tasks)

    marker_dir = Path(species_dir) / status.TASK_STATUS_DIR
    is_array_log = re.compile(r"^dscript_\d+_\d+\.out$")

    def pred(i):
        return work / f"predictions_task_{i}.positive.tsv"

    def task_log(i):
        return newest(logs_dir / f"dscript_*_{i}.out")

    done, failed, ambiguous, not_run = [], [], [], []
    for i in range(1, n_tasks + 1):
        if marker_dir.is_dir() and (marker_dir / str(i)).exists() and not args.overwrite:
            continue  # keep an existing real marker
        if pred(i).exists():
            done.append(i)
            continue
        lg = task_log(i)
        if lg is not None and not is_array_log.match(lg.name):
            lg = None  # avoid matching e.g. dscript_embed_<jobid>.out
        if lg is not None and log_errors(lg):
            failed.append(i)
        elif lg is not None:
            ambiguous.append(i)
        else:
            not_run.append(i)

    for i in done:
        status.record_task(species_dir, i, "done")
    for i in failed:
        status.record_task(species_dir, i, "failed")

    if ambiguous:
        sample = task_log(ambiguous[0])
        print(
            f"\n  ? inference: {len(ambiguous)} task(s) ran but produced no output "
            f"and show no obvious error (e.g. task {ambiguous[0]})"
        )
        if args.auto:
            outcome = "failed"
        else:
            if sample is not None:
                print(f"    sample log: {sample}")
                print("    --- tail " + "-" * 50)
                for line in tail(sample, args.tail).splitlines():
                    print(f"    | {line}")
                print("    " + "-" * 59)
            while True:
                c = input(
                    f"    mark these {len(ambiguous)} task(s) as [f]ailed / [d]one / [s]kip? "
                ).strip().lower()
                if c in ("f", "failed"):
                    outcome = "failed"
                    break
                if c in ("d", "done"):
                    outcome = "done"
                    break
                if c in ("s", "skip", ""):
                    outcome = None
                    break
                print("    please answer f, d, or s")
        if outcome is not None:
            for i in ambiguous:
                status.record_task(species_dir, i, outcome)
            failed += [i for i in ambiguous if outcome == "failed"]
            done += [i for i in ambiguous if outcome == "done"]

    summary = status.refresh_inference(species_dir)
    note = ""
    if summary["failed"]:
        note = f" failed: {','.join(summary['failed'][:10])}" + (
            " ..." if len(summary["failed"]) > 10 else ""
        )
    if not_run:
        note += f" (not_run: {len(not_run)})"
    print(f"  inference        -> {summary['done']}/{summary['n_tasks']}{note}")


def resolve_accessions(args) -> list[str]:
    accs = list(args.accessions)
    # parse_accessions parity: a single arg that is a file is an accession list.
    if len(accs) == 1 and Path(accs[0]).is_file():
        args.file = args.file or Path(accs[0])
        accs = []
    if args.file:
        for line in Path(args.file).read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                accs.append(line)
    return accs


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--results-base", required=True, help="Base dir holding <accession>_results/.")
    p.add_argument("--embeddings-dir", default=None, help="Dir holding <accession>_embed.h5 (for the embed step).")
    p.add_argument("--global-logs", default=None, help="Shared logs dir (reserved; split logs are global).")
    p.add_argument("accessions", nargs="*", help="Accession IDs, or a single accessions file.")
    p.add_argument("--file", type=Path, help="File with one accession per line (# comments allowed).")
    p.add_argument("--steps", help="Comma-separated subset of steps to process (default: all).")
    p.add_argument("--auto", action="store_true", help="Never prompt; auto-resolve ambiguous steps to error.")
    p.add_argument("--always-ask", action="store_true", help="Prompt on every step, even confident ones.")
    p.add_argument("--overwrite", action="store_true", help="Re-evaluate steps already recorded as done.")
    p.add_argument("--tail", type=int, default=25, help="Lines of log tail to show when prompting.")
    args = p.parse_args()

    accs = resolve_accessions(args)
    if not accs:
        p.error("No accessions provided (pass as args, a file, or --file).")

    steps = status.STEPS
    if args.steps:
        wanted = {s.strip() for s in args.steps.split(",")}
        unknown = wanted - set(status.STEPS)
        if unknown:
            p.error(f"Unknown step(s): {', '.join(sorted(unknown))}. Valid: {', '.join(status.STEPS)}")
        steps = [s for s in status.STEPS if s in wanted]

    results_base = Path(args.results_base)
    embeddings_dir = Path(args.embeddings_dir) if args.embeddings_dir else None

    for acc in accs:
        species_dir = results_base / f"{acc}_results"
        logs_dir = species_dir / "logs"
        print(f"\n=== {acc} ({species_dir}) ===")
        if not species_dir.is_dir():
            print("  results directory not found, skipping")
            continue

        # Per-step artifact paths and candidate log globs (in logs_dir).
        embed_artifacts = [embeddings_dir / f"{acc}_embed.h5"] if embeddings_dir else []
        step_config = {
            "download_filter": ([species_dir / f"{acc}_clean.fasta"], []),
            "candidates": ([species_dir / f"{acc}_candidates.tsv"], ["pre_dscript_*.out"]),
            "embed": (embed_artifacts, ["dscript_embed_*.out"]),
            "split": (sorted((species_dir / "dscript_work").glob("dscript_*_tasks.sh"))[:1], []),
            "cluster": ([species_dir / f"{acc}_clusters.pre.json"], ["post_cluster_*.out", "post_dscript_*.out"]),
            "describe": ([species_dir / f"{acc}.zip"], ["post_describe_*.out", "redo_describe_*.out", "post_dscript_*.out"]),
        }

        for step in steps:
            recorded = status.get_step(species_dir, step)
            if (
                recorded.get("status") == "done"
                and not args.overwrite
                and not args.always_ask
            ):
                print(f"  {step:16s} -> already done, skipping")
                continue

            if step == "inference":
                resolve_inference(str(species_dir), logs_dir, args)
                continue

            artifacts, log_globs = step_config[step]
            resolve_generic(step, str(species_dir), logs_dir, artifacts, log_globs, args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
