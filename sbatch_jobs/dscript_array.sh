#!/bin/bash
#SBATCH --job-name=dscript
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --time=1-00:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --mem=0
#SBATCH --array=1-1

SPECIES=$1
RESULTS_BASE=$WORK/philharmonic_results/bulk_results
SPECIES_DIR="$RESULTS_BASE/${SPECIES}_results"

mkdir -p "$SPECIES_DIR/logs"
exec > "$SPECIES_DIR/logs/dscript_${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}.out" 2>&1

module load gcc cuda python3
source $WORK/venv/bin/activate

TASKFILE=$(ls "$SPECIES_DIR/dscript_work"/dscript_*_tasks.sh)
sed -n "${SLURM_ARRAY_TASK_ID}p" "$TASKFILE" | bash