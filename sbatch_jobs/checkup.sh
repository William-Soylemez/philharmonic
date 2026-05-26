#!/bin/bash
# Usage:
#   ./checkup.sh GCF_002263795.3 GCF_000001405.40 ...
#   ./checkup.sh accessions.txt

RESULTS_BASE=$WORK/philharmonic_results/bulk_results
EMBEDDINGS_DIR=$SCRATCH/philharmonic_embeddings

if [[ $# -eq 1 && -f "$1" ]]; then
    mapfile -t ACCS < <(grep -v '^\s*#' "$1" | grep -v '^\s*$')
else
    ACCS=("$@")
fi

printf '%-30s  %-10s %-12s %-10s %-10s %-20s %-10s\n' \
    accession filtered candidates embedded split inference postproc
printf '%-30s  %-10s %-12s %-10s %-10s %-20s %-10s\n' \
    '------------------------------' '----------' '------------' '----------' '----------' '--------------------' '----------'

for ACC in "${ACCS[@]}"; do
    SPECIES_DIR="$RESULTS_BASE/${ACC}_results"

    [[ -f "$SPECIES_DIR/${ACC}_clean.fasta" ]]    && FILTERED="yes" || FILTERED="no"
    [[ -f "$SPECIES_DIR/${ACC}_candidates.tsv" ]] && CANDS="yes"    || CANDS="no"
    [[ -f "$EMBEDDINGS_DIR/${ACC}_embed.h5" ]]    && EMBED="yes"    || EMBED="no"

    TASKFILE=$(ls "$SPECIES_DIR/dscript_work"/dscript_*_tasks.sh 2>/dev/null | head -1)
    if [[ -z "$TASKFILE" ]]; then
        SPLIT="no"
        INFER="—"
    else
        SPLIT="yes"
        N_TASKS=$(wc -l < "$TASKFILE")
        N_DONE=$(ls "$SPECIES_DIR/dscript_work"/predictions_task_*.positive.tsv 2>/dev/null | wc -l)
        if [[ $N_DONE -eq $N_TASKS ]]; then
            INFER="done ($N_TASKS/$N_TASKS)"
        else
            INFER="$N_DONE/$N_TASKS tasks"
        fi
    fi

    [[ -f "$SPECIES_DIR/${ACC}.zip" ]] && POST="yes" || POST="no"

    printf '%-30s  %-10s %-12s %-10s %-10s %-20s %-10s\n' \
        "$ACC" "$FILTERED" "$CANDS" "$EMBED" "$SPLIT" "$INFER" "$POST"
done
