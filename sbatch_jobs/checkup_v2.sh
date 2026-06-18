#!/bin/bash
# Status checkup driven by each species' status.json (written by the pipeline jobs).
# Usage:
#   ./checkup_v2.sh GCF_002263795.3 GCF_000001405.40 ...
#   ./checkup_v2.sh accessions.txt
#
# Shows every pipeline step (download_filter, candidates, embed, split,
# inference, cluster, describe). Anything not yet recorded shows as "not started".

source /work/11301/wsoylemez/vista/philharmonic/sbatch_jobs/common.sh
parse_accessions "$@"

python3 "$PHILHARMONIC_CODE/sbatch_jobs/checkup_v2.py" "$RESULTS_BASE" "${ACCS[@]}"
