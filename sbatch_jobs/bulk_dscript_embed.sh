#!/bin/bash
# Usage:
#   ./bulk_dscript_embed.sh GCF_002263795.3 GCF_000001405.40 ...
#   ./bulk_dscript_embed.sh accessions.txt

source /work/11301/wsoylemez/vista/philharmonic/sbatch_jobs/common.sh
parse_accessions "$@"

for ACC in "${ACCS[@]}"; do
    mkdir -p "$RESULTS_BASE/${ACC}_results/logs"
    sbatch -p gh \
        --output="$RESULTS_BASE/${ACC}_results/logs/dscript_embed_%j.out" \
        --error="$RESULTS_BASE/${ACC}_results/logs/dscript_embed_%j.err" \
        "$PHILHARMONIC_CODE/sbatch_jobs/dscript_embed.sh" "$ACC"
done
