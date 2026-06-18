#!/bin/bash
# Usage:
#   ./bulk_pre_dscript.sh GCF_002263795.3 GCF_000001405.40 ...
#   ./bulk_pre_dscript.sh accessions.txt

source /work/11301/wsoylemez/vista/philharmonic/sbatch_jobs/common.sh
parse_accessions "$@"

for ACC in "${ACCS[@]}"; do
    mkdir -p "$RESULTS_BASE/${ACC}_results/logs"
    sbatch -p gg \
        --output="$RESULTS_BASE/${ACC}_results/logs/pre_dscript_%j.out" \
        --error="$RESULTS_BASE/${ACC}_results/logs/pre_dscript_%j.err" \
        "$PHILHARMONIC_CODE/sbatch_jobs/pre_dscript.sh" "$ACC"
done
