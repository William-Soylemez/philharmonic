#!/bin/bash
#SBATCH --job-name=pre_dscript
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --time=06:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=144
#SBATCH --mem=0

SPECIES=$1
PHILHARMONIC_CODE=$WORK/philharmonic
RESULTS_BASE=$WORK/philharmonic_results/bulk_results

mkdir -p "$RESULTS_BASE/${SPECIES}_results/logs"
exec > "$RESULTS_BASE/${SPECIES}_results/logs/pre_dscript_${SLURM_JOB_ID}.out" 2>&1

module load gcc cuda python3
source $WORK/venv/bin/activate

export OPENAI_API_KEY=""

cd "$RESULTS_BASE"
snakemake --snakefile "$PHILHARMONIC_CODE/Snakefile_slurm" \
    --configfile "$PHILHARMONIC_CODE/configs/config_slurm.yml" \
    --nolock \
    -j144 \
    "${SPECIES}_results/${SPECIES}_candidates.tsv"
