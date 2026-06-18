#!/bin/bash
#SBATCH --job-name=post_cluster
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --time=12:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=144
#SBATCH --mem=0

source /work/11301/wsoylemez/vista/philharmonic/sbatch_jobs/common.sh

SPECIES=$1
SPECIES_DIR="$RESULTS_BASE/${SPECIES}_results"
redirect_log "$SPECIES_DIR/logs/post_cluster_${SLURM_JOB_ID}.out"
activate_env

cd "$RESULTS_BASE"
cat "$SPECIES_DIR/dscript_work"/predictions_task_*.positive.tsv \
    > "$SPECIES_DIR/${SPECIES}_network.positive.tsv"

if snakemake \
    --snakefile "$PHILHARMONIC_CODE/Snakefile_slurm" \
    --configfile "$PHILHARMONIC_CODE/configs/config_slurm.yml" \
    --cores 144 \
    --rerun-incomplete \
    --nolock \
    "${SPECIES}_results/${SPECIES}_clusters.pre.json"; then
    record_status "$SPECIES_DIR" cluster done
else
    record_status "$SPECIES_DIR" cluster error \
        "post_cluster snakemake failed (job ${SLURM_JOB_ID}); see logs/post_cluster_${SLURM_JOB_ID}.out"
fi
