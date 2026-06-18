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

source /work/11301/wsoylemez/vista/philharmonic/sbatch_jobs/common.sh

mkdir -p "$RESULTS_BASE"
redirect_log "$GLOBAL_LOGS/bulk_download_filter_${SLURM_JOB_ID}.out"
activate_env

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
