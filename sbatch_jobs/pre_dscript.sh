#!/bin/bash
#SBATCH --job-name=pre_dscript
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --time=30:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=144
#SBATCH --mem=0

source $WORK/philharmonic/sbatch_jobs/common.sh

SPECIES=$1
redirect_log "$RESULTS_BASE/${SPECIES}_results/logs/pre_dscript_${SLURM_JOB_ID}.out"
activate_env

cd "$RESULTS_BASE"
snakemake --snakefile "$PHILHARMONIC_CODE/Snakefile_slurm" \
    --configfile "$PHILHARMONIC_CODE/configs/config_slurm.yml" \
    --nolock \
    -j144 \
    "${SPECIES}_results/${SPECIES}_candidates.tsv"
