#!/bin/bash
#SBATCH --job-name=post_dscript
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --time=08:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=144
#SBATCH --mem=0

source $WORK/philharmonic/sbatch_jobs/common.sh

SPECIES=$1
SPECIES_DIR="$RESULTS_BASE/${SPECIES}_results"
redirect_log "$SPECIES_DIR/logs/post_dscript_${SLURM_JOB_ID}.out"
activate_env
source $WORK/.env_secrets

cd "$RESULTS_BASE"
cat "$SPECIES_DIR/dscript_work"/predictions_task_*.positive.tsv \
    > "$SPECIES_DIR/${SPECIES}_network.positive.tsv"

# This single snakemake invocation runs both the cluster and describe stages of
# the DAG on the way to the .zip. We can't hook between the two stages, so after
# the run we record each step separately by which artifact it produced:
#   clusters.pre.json -> cluster done; <species>.zip -> describe done.
snakemake \
    --snakefile "$PHILHARMONIC_CODE/Snakefile_slurm" \
    --configfile "$PHILHARMONIC_CODE/configs/config_slurm.yml" \
    --cores 144 \
    --rerun-incomplete \
    --nolock \
    "${SPECIES}_results/${SPECIES}.zip"

if [[ -f "$SPECIES_DIR/${SPECIES}_clusters.pre.json" ]]; then
    record_status "$SPECIES_DIR" cluster done
else
    record_status "$SPECIES_DIR" cluster error \
        "post_dscript: clustering did not complete (job ${SLURM_JOB_ID}); see logs/post_dscript_${SLURM_JOB_ID}.out"
fi

if [[ -f "$SPECIES_DIR/${SPECIES}.zip" ]]; then
    record_status "$SPECIES_DIR" describe done
else
    record_status "$SPECIES_DIR" describe error \
        "post_dscript: describe did not complete (job ${SLURM_JOB_ID}); see logs/post_dscript_${SLURM_JOB_ID}.out"
fi
