#!/bin/bash
# Usage:
#   ./bulk_post_describe.sh GCF_002263795.3 GCF_000001405.40 ...
#   ./bulk_post_describe.sh accessions.txt
# Skips species already described (zip exists) or not yet clustered.

PHILHARMONIC_CODE=$WORK/philharmonic
RESULTS_BASE=$WORK/philharmonic_results/bulk_results

if [[ $# -eq 1 && -f "$1" ]]; then
    mapfile -t ACCS < <(grep -v '^\s*#' "$1" | grep -v '^\s*$')
else
    ACCS=("$@")
fi

for ACC in "${ACCS[@]}"; do
    SPECIES_DIR="$RESULTS_BASE/${ACC}_results"

    if [[ -f "$SPECIES_DIR/${ACC}.zip" ]]; then
        echo "[$ACC] already done, skipping"
        continue
    fi

    if [[ ! -f "$SPECIES_DIR/${ACC}_clusters.pre.json" ]]; then
        echo "[$ACC] not yet clustered, skipping"
        continue
    fi

    mkdir -p "$SPECIES_DIR/logs"
    RESULT=$(sbatch -p gg \
        --output="$SPECIES_DIR/logs/post_describe_%j.out" \
        --error="$SPECIES_DIR/logs/post_describe_%j.err" \
        "$PHILHARMONIC_CODE/sbatch_jobs/post_describe.sh" "$ACC" 2>&1)
    if [[ $? -eq 0 ]]; then
        echo "[$ACC] submitted — $RESULT"
    else
        echo "[$ACC] FAILED — $RESULT"
    fi
done
