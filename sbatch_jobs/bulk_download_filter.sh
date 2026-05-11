#!/bin/bash
#SBATCH --job-name=bulk_download_filter
#SBATCH --output=bulk_download_filter_%j.out
#SBATCH --error=bulk_download_filter_%j.err
#SBATCH --time=04:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=144
#SBATCH --mem=0

# Usage:
#   sbatch bulk_download_filter.sh <accessions_file>
#   sbatch bulk_download_filter.sh GCF_002263795.3 GCF_000001405.40

cd $SCRATCH
module load gcc cuda python3
source $WORK/venv/bin/activate

export OPENAI_API_KEY=""

cd philharmonic

if [[ $# -ge 1 && -f "$1" ]]; then
    FILE_ARG="--file $1"
    shift
    ACCS=()
else
    FILE_ARG=""
    ACCS=("$@")
    set --
fi

python sbatch_jobs/bulk_download_filter.py \
    $FILE_ARG \
    --jobs 144 \
    --continue-on-error \
    "${ACCS[@]}" \
    "$@"
