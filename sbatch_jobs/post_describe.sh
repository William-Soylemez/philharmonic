#!/bin/bash
#SBATCH --job-name=post_describe
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --time=12:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=0

SPECIES=$1
PHILHARMONIC_CODE=$WORK/philharmonic
RESULTS_BASE=$WORK/philharmonic_results/bulk_results
SPECIES_DIR="$RESULTS_BASE/${SPECIES}_results"

mkdir -p "$SPECIES_DIR/logs"
exec > "$SPECIES_DIR/logs/post_describe_${SLURM_JOB_ID}.out" 2>&1

module load gcc cuda python3
source $WORK/venv/bin/activate
source $WORK/.env_secrets

cd "$RESULTS_BASE"
snakemake \
    --snakefile "$PHILHARMONIC_CODE/Snakefile_slurm" \
    --configfile "$PHILHARMONIC_CODE/configs/config_slurm.yml" \
    --cores 8 \
    --rerun-incomplete \
    --nolock \
    "${SPECIES}_results/${SPECIES}.zip"
