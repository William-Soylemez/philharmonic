#!/bin/bash
# Usage:
#   ./checkup.sh GCF_002263795.3 GCF_000001405.40 ...
#   ./checkup.sh accessions.txt

source $WORK/philharmonic/sbatch_jobs/common.sh
parse_accessions "$@"

printf '%-30s  %-10s %-12s %-10s %-10s %-20s %-10s %-10s %-10s\n' \
    accession filtered candidates embedded split inference clustered annotated zip
printf '%-30s  %-10s %-12s %-10s %-10s %-20s %-10s %-10s %-10s\n' \
    '------------------------------' '----------' '------------' '----------' '----------' '--------------------' '----------' '----------' '----------'

for ACC in "${ACCS[@]}"; do
    SPECIES_DIR="$RESULTS_BASE/${ACC}_results"

    [[ -f "$SPECIES_DIR/${ACC}_clean.fasta" ]]        && FILTERED="yes" || FILTERED="no"
    [[ -f "$SPECIES_DIR/${ACC}_candidates.tsv" ]]     && CANDS="yes"    || CANDS="no"
    [[ -f "$EMBEDDINGS_DIR/${ACC}_embed.h5" ]]        && EMBED="yes"    || EMBED="no"
    [[ -f "$SPECIES_DIR/${ACC}_clusters.pre.json" ]]  && CLUST="yes"    || CLUST="no"
    [[ -f "$SPECIES_DIR/${ACC}_human_readable.txt" ]] && ANNOT="yes"    || ANNOT="no"
    [[ -f "$SPECIES_DIR/${ACC}.zip" ]]                && ZIP="yes"      || ZIP="no"

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

    printf '%-30s  %-10s %-12s %-10s %-10s %-20s %-10s %-10s %-10s\n' \
        "$ACC" "$FILTERED" "$CANDS" "$EMBED" "$SPLIT" "$INFER" "$CLUST" "$ANNOT" "$ZIP"
done
