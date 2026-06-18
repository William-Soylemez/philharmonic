#!/bin/bash
# Backfill each species' status.json from its logs and output artifacts.
# Use for species that ran before status tracking existed (group one), or to
# repair a stale status.json. Runs interactively on the login node (like
# checkup.sh) -- ambiguous steps print a log tail and ask you to decide.
#
# Usage:
#   ./populate_status.sh GCF_002263795.3 GCF_000001405.40 ...
#   ./populate_status.sh accessions.txt
#   ./populate_status.sh --auto accessions.txt        # never prompt
#   ./populate_status.sh --steps describe,cluster GCF_002263795.3
#
# Any options (--auto, --always-ask, --overwrite, --steps, --tail, --file) are
# forwarded straight through to populate_status.py.

source /work/11301/wsoylemez/vista/philharmonic/sbatch_jobs/common.sh

python3 "$PHILHARMONIC_CODE/sbatch_jobs/populate_status.py" \
    --results-base "$RESULTS_BASE" \
    --embeddings-dir "$EMBEDDINGS_DIR" \
    --global-logs "$GLOBAL_LOGS" \
    "$@"
