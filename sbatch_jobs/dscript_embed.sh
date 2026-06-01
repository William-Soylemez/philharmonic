#!/bin/bash
#SBATCH --job-name=dscript_embed
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --time=4:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --mem=0

source $WORK/philharmonic/sbatch_jobs/common.sh

SPECIES=$1
redirect_log "$RESULTS_BASE/${SPECIES}_results/logs/dscript_embed_${SLURM_JOB_ID}.out"
mkdir -p "$EMBEDDINGS_DIR"
activate_env

dscript embed \
    --seqs "$RESULTS_BASE/${SPECIES}_results/${SPECIES}_clean.fasta" \
    --outfile "$EMBEDDINGS_DIR/${SPECIES}_embed.h5" \
    --device 0

mkdir -p "$RESULTS_BASE/${SPECIES}_results/dscript_work"