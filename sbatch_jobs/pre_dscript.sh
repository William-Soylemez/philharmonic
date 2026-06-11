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

SPECIES_DIR="$RESULTS_BASE/${SPECIES}_results"

cd "$RESULTS_BASE"
if snakemake --snakefile "$PHILHARMONIC_CODE/Snakefile_slurm" \
    --configfile "$PHILHARMONIC_CODE/configs/config_slurm.yml" \
    --nolock \
    -j144 \
    "${SPECIES}_results/${SPECIES}_candidates.tsv"; then
    record_status "$SPECIES_DIR" candidates done
else
    record_status "$SPECIES_DIR" candidates error \
        "pre_dscript snakemake failed (job ${SLURM_JOB_ID}); see logs/pre_dscript_${SLURM_JOB_ID}.out"
fi
