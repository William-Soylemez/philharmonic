#!/bin/bash
# Usage:
#   ./bulk_dscript_array.sh GCF_002263795.3 GCF_000001405.40 ...
#   ./bulk_dscript_array.sh accessions.txt
# Skips species whose network file already exists.

PHILHARMONIC_CODE=$WORK/philharmonic
RESULTS_BASE=$WORK/philharmonic_results/bulk_results

if [[ $# -eq 1 && -f "$1" ]]; then
    mapfile -t ACCS < <(grep -v '^\s*#' "$1" | grep -v '^\s*$')
else
    ACCS=("$@")
fi

for ACC in "${ACCS[@]}"; do
    SPECIES_DIR="$RESULTS_BASE/${ACC}_results"

    if [[ -f "$SPECIES_DIR/${ACC}_network.positive.tsv" ]]; then
        echo "[$ACC] network already exists, skipping"
        continue
    fi

    TASKFILE=$(ls "$SPECIES_DIR/dscript_work"/dscript_*_tasks.sh 2>/dev/null | head -1)
    if [[ -z "$TASKFILE" ]]; then
        echo "[$ACC] no task file found, skipping (run bulk_dscript_split first)"
        continue
    fi

    N=$(wc -l < "$TASKFILE")
    mkdir -p "$SPECIES_DIR/logs"
    sbatch -p gh \
        --array="1-${N}" \
        --output="$SPECIES_DIR/logs/dscript_%A_%a.out" \
        --error="$SPECIES_DIR/logs/dscript_%A_%a.err" \
        "$PHILHARMONIC_CODE/sbatch_jobs/dscript_array.sh" "$ACC"
done
