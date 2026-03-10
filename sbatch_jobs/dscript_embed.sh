#!/bin/bash
#SBATCH --job-name=dscript_embed
#SBATCH --output=dscript_embed_%j.out
#SBATCH --error=dscript_embed_%j.err
#SBATCH --time=4:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --mem=0

cd $SCRATCH
module load gcc cuda python3
source venv/bin/activate

export SPECIES=$1

cd philharmonic/${SPECIES}_results
dscript embed --seqs ${SPECIES}_clean.fasta --outfile ${SPECIES}_embed.h5 --device 0
mkdir -p dscript_work