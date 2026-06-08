"""Download NCBI protein FASTAs for a list of assembly accessions and run the Snakefile_slurm filter_seqs rule on each."""
import argparse
import gzip
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import status

NCBI_BASE = "https://ftp.ncbi.nlm.nih.gov/genomes/all"
ACCESSION_RE = re.compile(r"^(GCF|GCA)_(\d{3})(\d{3})(\d{3})\.\d+$")


def parent_url(accession: str) -> str:
    m = ACCESSION_RE.match(accession)
    if not m:
        raise ValueError(f"Bad accession format: {accession!r} (expected e.g. GCF_002263795.3)")
    prefix, a, b, c = m.groups()
    return f"{NCBI_BASE}/{prefix}/{a}/{b}/{c}/"


def resolve_assembly_dir(accession: str) -> str:
    parent = parent_url(accession)
    with urllib.request.urlopen(parent, timeout=60) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    matches = re.findall(rf'href="({re.escape(accession)}_[^"/]+)/"', html)
    if not matches:
        raise RuntimeError(f"No assembly directory found at {parent} for {accession}")
    return matches[0]


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=300) as resp, open(tmp, "wb") as f:
        shutil.copyfileobj(resp, f)
    tmp.rename(dest)


def gunzip(src: Path, dest: Path) -> None:
    with gzip.open(src, "rb") as fin, open(dest, "wb") as fout:
        shutil.copyfileobj(fin, fout)


def stage_unfiltered(accession: str, keep_gz: bool) -> Path:
    """Download protein.faa.gz and place it at <accession>_results/<accession>_unfiltered.fasta."""
    species_dir = Path(f"{accession}_results")
    unfiltered = species_dir / f"{accession}_unfiltered.fasta"
    if unfiltered.exists():
        print(f"[{accession}] {unfiltered} already exists; skipping download", flush=True)
        return unfiltered

    asm_dir = resolve_assembly_dir(accession)
    fname = f"{asm_dir}_protein.faa.gz"
    url = f"{parent_url(accession)}{asm_dir}/{fname}"
    gz_path = species_dir / fname

    print(f"[{accession}] downloading {url}", flush=True)
    try:
        download(url, gz_path)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # GenBank/GCA assemblies without RefSeq annotation often publish no
            # curated _protein.faa.gz. Fail loudly rather than silently falling
            # back to _translated_cds.faa.gz, whose IDs and redundancy differ.
            raise RuntimeError(
                f"{accession}: no curated _protein.faa.gz published at {url} "
                f"(typical for unannotated GenBank/GCA assemblies). Handle this "
                f"accession manually — _translated_cds.faa.gz may exist but uses a "
                f"different protein-ID convention and is not used automatically."
            ) from e
        raise
    gunzip(gz_path, unfiltered)
    if not keep_gz:
        gz_path.unlink()
    return unfiltered


def run_snakemake(accession: str, snakefile: Path, configfile: Path, jobs: int, extra: list[str]) -> None:
    target = f"{accession}_results/{accession}_clean.fasta"
    cmd = [
        "snakemake",
        "--snakefile", str(snakefile),
        "--configfile", str(configfile),
        "-j", str(jobs),
        target,
        *extra,
    ]
    print(f"[{accession}] {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("accessions", nargs="*", help="Accession IDs (e.g. GCF_002263795.3). Omit to read from --file or stdin.")
    p.add_argument("--file", type=Path, help="File with one accession per line (# comments allowed).")
    p.add_argument("--snakefile", type=Path, default=Path("Snakefile_slurm"), help="Snakefile to use.")
    p.add_argument("--configfile", type=Path, default=Path("configs/config_slurm.yml"), help="Snakemake config file.")
    p.add_argument("--jobs", type=int, default=1, help="snakemake -j value.")
    p.add_argument("--keep-gz", action="store_true", help="Keep the downloaded .gz file.")
    p.add_argument("--continue-on-error", action="store_true", help="Keep going if one accession fails.")
    p.add_argument("snakemake_args", nargs=argparse.REMAINDER, help="Extra args after `--` are forwarded to snakemake.")
    args = p.parse_args()

    accs: list[str] = list(args.accessions)
    if args.file:
        for line in args.file.read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                accs.append(line)
    if not accs and not sys.stdin.isatty():
        accs.extend(line.strip() for line in sys.stdin if line.strip() and not line.startswith("#"))
    if not accs:
        p.error("No accessions provided (pass as args, --file, or stdin).")

    fwd = args.snakemake_args
    if fwd and fwd[0] == "--":
        fwd = fwd[1:]

    failures: list[tuple[str, str]] = []
    for acc in accs:
        species_dir = f"{acc}_results"
        try:
            stage_unfiltered(acc, args.keep_gz)
            run_snakemake(acc, args.snakefile, args.configfile, args.jobs, fwd)
            status.set_status(species_dir, "download_filter", "done")
        except Exception as e:
            status.set_status(species_dir, "download_filter", "error", message=str(e))
            print(f"[{acc}] ERROR: {e}", file=sys.stderr, flush=True)
            failures.append((acc, str(e)))
            if not args.continue_on_error:
                return 1

    if failures:
        print(f"\n{len(failures)} failure(s):", file=sys.stderr)
        for acc, msg in failures:
            print(f"  {acc}: {msg}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
