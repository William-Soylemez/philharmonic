#!/bin/bash
#SBATCH --job-name=pre_dscript
#SBATCH --output=pre_dscript_%j.out
#SBATCH --error=pre_dscript_%j.err
#SBATCH --time=06:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=144
#SBATCH --mem=0

export SPECIES=$1

cd $SCRATCH
module load gcc cuda python3
source $WORK/venv/bin/activate

export OPENAI_API_KEY=""

cd philharmonic
mkdir -p ${SPECIES}_results
snakemake --snakefile Snakefile_slurm --configfile configs/config_slurm.yml -j144 \
    ${SPECIES}_results/${SPECIES}_candidates.tsv
