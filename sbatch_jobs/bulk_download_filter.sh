#!/bin/bash
#SBATCH --job-name=bulk_download_filter
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --time=04:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=144
#SBATCH --mem=0

# Usage:
#   sbatch sbatch_jobs/bulk_download_filter.sh <accessions_file>
#   sbatch sbatch_jobs/bulk_download_filter.sh GCF_002263795.3 GCF_000001405.40

PHILHARMONIC_CODE=$WORK/philharmonic
RESULTS_BASE=$WORK/philharmonic_results/bulk_results
GLOBAL_LOGS=$WORK/philharmonic_results/logs

mkdir -p "$RESULTS_BASE" "$GLOBAL_LOGS"
exec > "$GLOBAL_LOGS/bulk_download_filter_${SLURM_JOB_ID}.out" 2>&1

module load gcc cuda python3
source $WORK/venv/bin/activate

export OPENAI_API_KEY=""

cd "$RESULTS_BASE"

if [[ $# -ge 1 && -f "$1" ]]; then
    FILE_ARG="--file $1"
    shift
    ACCS=()
else
    FILE_ARG=""
    ACCS=("$@")
    set --
fi

python "$PHILHARMONIC_CODE/sbatch_jobs/bulk_download_filter.py" \
    --snakefile "$PHILHARMONIC_CODE/Snakefile_slurm" \
    --configfile "$PHILHARMONIC_CODE/configs/config_slurm.yml" \
    $FILE_ARG \
    --jobs 144 \
    --continue-on-error \
    "${ACCS[@]}" \
    "$@"
