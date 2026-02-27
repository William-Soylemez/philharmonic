import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import typer
from Bio import SeqIO
from loguru import logger

app = typer.Typer()

PREFIX_PRIORITY = {"NP": 0, "XP": 1, "YP": 2}

scratch_tmp = Path(os.environ.get("SCRATCH", "/tmp")) / "tmp"
scratch_tmp.mkdir(exist_ok=True)

def accession_sort_key(accession: str) -> tuple[int, int]:
    """Sort key: prioritize NP < XP < YP, then by numeric accession."""
    match = re.match(r"([A-Z]+)_(\d+)", accession)
    if match:
        prefix = match.group(1)
        number = int(match.group(2))
        return (PREFIX_PRIORITY.get(prefix, 99), number)
    return (99, 0)


@app.command()
def main(
    input_fasta: Path = typer.Argument(..., help="Input FASTA file"),
    output_fasta: Path = typer.Argument(..., help="Output FASTA file"),
    min_length: int = typer.Option(50, "--min-length", help="Minimum sequence length (AAs)"),
    max_length: int = typer.Option(1200, "--max-length", help="Maximum sequence length (AAs)"),
    identity: float = typer.Option(0.95, "--identity", help="MMseqs2 sequence identity threshold"),
    threads: int = typer.Option(4, "--threads", help="Number of threads for MMseqs2"),
):
    """Filter sequences by length and deduplicate with MMseqs2."""
    if shutil.which("mmseqs") is None:
        logger.error("mmseqs2 is not installed or not in PATH")
        raise typer.Exit(code=1)

    # --- Length filtering ---
    records = list(SeqIO.parse(input_fasta, "fasta"))
    total = len(records)
    logger.info(f"Read {total} sequences from {input_fasta}")

    too_short = [r for r in records if len(r.seq) < min_length]
    too_long = [r for r in records if len(r.seq) > max_length]
    kept = [r for r in records if min_length <= len(r.seq) <= max_length]

    logger.info(f"Dropped {len(too_short)} sequences shorter than {min_length} AAs")
    logger.info(f"Dropped {len(too_long)} sequences longer than {max_length} AAs")
    logger.info(f"Kept {len(kept)} sequences after length filtering")

    if not kept:
        logger.error("No sequences remain after length filtering")
        raise typer.Exit(code=1)

    # --- MMseqs2 deduplication ---
    with tempfile.TemporaryDirectory(dir=scratch_tmp) as tmpdir:
        tmp = Path(tmpdir)
        filtered_fasta = tmp / "filtered.fasta"
        SeqIO.write(kept, filtered_fasta, "fasta")

        db = tmp / "db"
        result_db = tmp / "result"
        cluster_tsv = tmp / "cluster.tsv"

        # Create MMseqs2 database
        _run_mmseqs(["createdb", str(filtered_fasta), str(db)])

        # Cluster
        _run_mmseqs([
            "cluster", str(db), str(result_db), str(tmpdir),
            "--min-seq-id", str(identity),
            "--threads", str(threads),
            "-c", "0.8",
            "--cov-mode", "0",
        ])

        # Convert to TSV (representative \t member)
        _run_mmseqs(["createtsv", str(db), str(db), str(result_db), str(cluster_tsv)])

        # Parse clusters and pick best representative per cluster
        clusters: dict[str, list[str]] = {}
        with open(cluster_tsv) as f:
            for line in f:
                rep, member = line.strip().split("\t")
                clusters.setdefault(rep, []).append(member)

        # For each cluster, pick the member with the best accession
        selected_ids: set[str] = set()
        for members in clusters.values():
            best = min(members, key=accession_sort_key)
            selected_ids.add(best)

        deduplicated = [r for r in kept if r.id in selected_ids]

    logger.info(
        f"MMseqs2 clustering at {identity:.0%} identity: "
        f"{len(kept)} → {len(deduplicated)} sequences "
        f"({len(kept) - len(deduplicated)} redundant sequences removed)"
    )

    SeqIO.write(deduplicated, output_fasta, "fasta")
    logger.info(f"Wrote {len(deduplicated)} sequences to {output_fasta}")


def _run_mmseqs(args: list[str]) -> None:
    """Run an mmseqs subcommand, raising on failure."""
    cmd = ["mmseqs", *args]
    logger.debug(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"MMseqs2 failed:\n{result.stderr}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
