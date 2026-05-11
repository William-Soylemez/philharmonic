#!/bin/bash
#SBATCH --job-name=bulk_download_filter
#SBATCH --output=bulk_download_filter_%j.out
#SBATCH --error=bulk_download_filter_%j.err
#SBATCH --time=04:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#
# Downloads NCBI protein FASTAs for a list of assembly accessions, places each
# at <accession>_results/<accession>_unfiltered.fasta, and invokes the
# Snakefile_slurm filter_seqs rule to produce {_filtered,_clean}.fasta.
#
# Usage:
#   sbatch bulk_download_filter.sh <accessions_file>
#   sbatch bulk_download_filter.sh GCF_002263795.3 GCF_000001405.40
#
# Extra snakemake flags can be appended after `--`, e.g.:
#   sbatch bulk_download_filter.sh species.txt -- --rerun-incomplete

set -euo pipefail

cd "$SCRATCH"
module load gcc python3
source "$WORK/venv/bin/activate"
cd philharmonic

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ARGS=()
FILE_ARG=""

if [[ $# -ge 1 && -f "$1" ]]; then
    FILE_ARG="--file $1"
    shift
else
    while [[ $# -gt 0 && "$1" != "--" ]]; do
        ARGS+=("$1")
        shift
    done
fi

python "$SCRIPT_DIR/bulk_download_filter.py" \
    $FILE_ARG \
    --jobs "${SLURM_CPUS_PER_TASK:-8}" \
    --continue-on-error \
    "${ARGS[@]}" \
    "$@"
