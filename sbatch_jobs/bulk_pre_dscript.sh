#!/bin/bash
# Usage:
#   ./bulk_pre_dscript.sh GCF_002263795.3 GCF_000001405.40 ...
#   ./bulk_pre_dscript.sh accessions.txt

PHILHARMONIC_CODE=$WORK/philharmonic
RESULTS_BASE=$WORK/philharmonic_results/bulk_results

if [[ $# -eq 1 && -f "$1" ]]; then
    mapfile -t ACCS < <(grep -v '^\s*#' "$1" | grep -v '^\s*$')
else
    ACCS=("$@")
fi

for ACC in "${ACCS[@]}"; do
    mkdir -p "$RESULTS_BASE/${ACC}_results/logs"
    sbatch -p gg \
        --output="$RESULTS_BASE/${ACC}_results/logs/pre_dscript_%j.out" \
        --error="$RESULTS_BASE/${ACC}_results/logs/pre_dscript_%j.err" \
        "$PHILHARMONIC_CODE/sbatch_jobs/pre_dscript.sh" "$ACC"
done
