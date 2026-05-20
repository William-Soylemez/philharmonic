#!/bin/bash
#SBATCH --job-name=bulk_dscript_split
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=0

# Usage:
#   sbatch sbatch_jobs/bulk_dscript_split.sh accessions.txt
#   sbatch sbatch_jobs/bulk_dscript_split.sh GCF_002263795.3 GCF_000001405.40 ...

PHILHARMONIC_CODE=$WORK/philharmonic
RESULTS_BASE=$WORK/philharmonic_results/bulk_results
EMBEDDINGS_DIR=$SCRATCH/philharmonic_embeddings
GLOBAL_LOGS=$WORK/philharmonic_results/logs

mkdir -p "$GLOBAL_LOGS"
exec > "$GLOBAL_LOGS/bulk_dscript_split_${SLURM_JOB_ID}.out" 2>&1

module load gcc cuda python3
source $WORK/venv/bin/activate

if [[ $# -eq 1 && -f "$1" ]]; then
    mapfile -t ACCS < <(grep -v '^\s*#' "$1" | grep -v '^\s*$')
else
    ACCS=("$@")
fi

printf '%-30s %10s %15s %13s %8s %15s\n' \
    species proteins pairs split_blocks n_jobs pairs_per_job

for ACC in "${ACCS[@]}"; do
    SPECIES_DIR="$RESULTS_BASE/${ACC}_results"

    grep "^>" "$SPECIES_DIR/${ACC}_kept_proteins.txt" | sed 's/>//' \
        > "$SPECIES_DIR/${ACC}_proteins_list.txt"

    PROTEINS=$(wc -l < "$SPECIES_DIR/${ACC}_proteins_list.txt")

    read PAIRS SPLIT_BLOCKS N_JOBS PAIRS_PER_JOB < <(python3 -c "
import math
p = $PROTEINS
pairs = p * (p - 1) // 2
target = 24_000_000
half = max(1, math.ceil(math.sqrt(pairs / target)))
split_blocks = 2 * half
n_jobs = half ** 2
pairs_per_job = pairs // n_jobs
print(pairs, split_blocks, n_jobs, pairs_per_job)
")

    printf '%-30s %10d %15d %13d %8d %15d\n' \
        "$ACC" "$PROTEINS" "$PAIRS" "$SPLIT_BLOCKS" "$N_JOBS" "$PAIRS_PER_JOB"

    dscript split_tasks \
        --proteins "$SPECIES_DIR/${ACC}_proteins_list.txt" \
        --embeddings "$EMBEDDINGS_DIR/${ACC}_embed.h5" \
        --workdir "$SPECIES_DIR/dscript_work" \
        --split_blocks "$SPLIT_BLOCKS" \
        --blocks 10

    mkdir -p "$SPECIES_DIR/logs"
    sbatch -p gh \
        --array="1-${N_JOBS}" \
        --output="$SPECIES_DIR/logs/dscript_%A_%a.out" \
        --error="$SPECIES_DIR/logs/dscript_%A_%a.err" \
        "$PHILHARMONIC_CODE/sbatch_jobs/dscript_array.sh" "$ACC"
done
