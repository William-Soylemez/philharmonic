#!/bin/bash
#SBATCH --job-name=post_describe
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --time=12:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=0

source $WORK/philharmonic/sbatch_jobs/common.sh

SPECIES=$1
SPECIES_DIR="$RESULTS_BASE/${SPECIES}_results"
redirect_log "$SPECIES_DIR/logs/post_describe_${SLURM_JOB_ID}.out"
activate_env
source $WORK/.env_secrets

cd "$RESULTS_BASE"
snakemake \
    --snakefile "$PHILHARMONIC_CODE/Snakefile_slurm" \
    --configfile "$PHILHARMONIC_CODE/configs/config_slurm.yml" \
    --cores 8 \
    --rerun-incomplete \
    --nolock \
    "${SPECIES}_results/${SPECIES}.zip"
