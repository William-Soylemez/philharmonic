#!/bin/bash
#SBATCH --job-name=dscript_embed
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --time=4:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --mem=0

SPECIES=$1
RESULTS_BASE=$WORK/philharmonic_results/bulk_results
EMBEDDINGS_DIR=$SCRATCH/philharmonic_embeddings

mkdir -p "$RESULTS_BASE/${SPECIES}_results/logs" "$EMBEDDINGS_DIR"
exec > "$RESULTS_BASE/${SPECIES}_results/logs/dscript_embed_${SLURM_JOB_ID}.out" 2>&1

module load gcc cuda python3
source $WORK/venv/bin/activate

dscript embed \
    --seqs "$RESULTS_BASE/${SPECIES}_results/${SPECIES}_clean.fasta" \
    --outfile "$EMBEDDINGS_DIR/${SPECIES}_embed.h5" \
    --device 0

mkdir -p "$RESULTS_BASE/${SPECIES}_results/dscript_work"