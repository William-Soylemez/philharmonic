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
SPECIES_DIR="$RESULTS_BASE/${SPECIES}_results"
redirect_log "$SPECIES_DIR/logs/dscript_embed_${SLURM_JOB_ID}.out"
mkdir -p "$EMBEDDINGS_DIR"
activate_env

if dscript embed \
    --seqs "$SPECIES_DIR/${SPECIES}_clean.fasta" \
    --outfile "$EMBEDDINGS_DIR/${SPECIES}_embed.h5" \
    --device 0; then
    mkdir -p "$SPECIES_DIR/dscript_work"
    record_status "$SPECIES_DIR" embed done
else
    record_status "$SPECIES_DIR" embed error \
        "dscript embed failed (job ${SLURM_JOB_ID}); see logs/dscript_embed_${SLURM_JOB_ID}.out"
fi