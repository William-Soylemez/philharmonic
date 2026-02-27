#!/bin/bash
#SBATCH --job-name=hmmscan
#SBATCH --output=hmmscan_%j.out
#SBATCH --error=hmmscan_%j.err
#SBATCH --time=04:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=144
#SBATCH --mem=0

# Load necessary modules and activate virtual environment
cd $SCRATCH
module load gcc cuda python3
source venv/bin/activate

# Environment variables
export SNAKE="snakemake --snakefile Snakefile_slurm --configfile configs/config_slurm.yml -j1"
export SPECIES="malaria"
export OPENAI_API_KEY=""

# Run the Snakemake workflow
cd $SCRATCH/philharmonic
$SNAKE malaria_results/malaria_hmmscan.tblout