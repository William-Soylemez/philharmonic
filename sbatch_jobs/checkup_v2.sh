#!/bin/bash
# Status checkup driven by each species' status.json (written by the pipeline jobs).
# Usage:
#   ./checkup_v2.sh GCF_002263795.3 GCF_000001405.40 ...
#   ./checkup_v2.sh accessions.txt
#
# Only steps wired into status tracking are shown (currently: download_filter).
# Anything not yet recorded shows as "not started".

source $WORK/philharmonic/sbatch_jobs/common.sh
parse_accessions "$@"

python3 "$PHILHARMONIC_CODE/sbatch_jobs/checkup_v2.py" "$RESULTS_BASE" "${ACCS[@]}"
