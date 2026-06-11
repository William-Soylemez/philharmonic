#!/bin/bash
#SBATCH --job-name=dscript
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --time=1-00:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --mem=0
#SBATCH --array=1-1

source $WORK/philharmonic/sbatch_jobs/common.sh

SPECIES=$1
SPECIES_DIR="$RESULTS_BASE/${SPECIES}_results"
redirect_log "$SPECIES_DIR/logs/dscript_${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}.out"
activate_env

TASKFILE=$(ls "$SPECIES_DIR/dscript_work"/dscript_*_tasks.sh)
if sed -n "${SLURM_ARRAY_TASK_ID}p" "$TASKFILE" | bash; then
    record_task "$SPECIES_DIR" "$SLURM_ARRAY_TASK_ID" done
else
    record_task "$SPECIES_DIR" "$SLURM_ARRAY_TASK_ID" failed
fi