#!/bin/bash
#SBATCH --job-name=dscript
#SBATCH --output=dscript_%A_%a.out
#SBATCH --error=dscript_%A_%a.err
#SBATCH --time=1-00:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --mem=0
#SBATCH --array=1-1

export SPECIES=$1

cd $SCRATCH
module load gcc cuda python3
source venv/bin/activate

cd philharmonic/${SPECIES}_results
TASKFILE=$(ls dscript_work/dscript_*_tasks.sh)
sed -n "${SLURM_ARRAY_TASK_ID}p" "$TASKFILE" | bash