#!/bin/bash
#SBATCH --job-name=post_dscript
#SBATCH --output=post_dscript_%j.out
#SBATCH --error=post_dscript_%j.err
#SBATCH --time=04:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=144
#SBATCH --mem=0

export SPECIES=$1

# Load necessary modules and activate virtual environment
cd $SCRATCH
module load gcc cuda python3
source $WORK/venv/bin/activate

# Environment variables
export SNAKE="snakemake --snakefile Snakefile_slurm --configfile configs/config_slurm.yml --cores 144 --rerun-incomplete"
export OPENAI_API_KEY=""

# Run the Snakemake workflow
cd $SCRATCH/philharmonic
cat ${SPECIES}_results/dscript_work/predictions_task_*.positive.tsv > ${SPECIES}_results/${SPECIES}_network.positive.tsv
$SNAKE ${SPECIES}_results/${SPECIES}.zip
