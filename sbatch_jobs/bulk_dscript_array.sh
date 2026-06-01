#!/bin/bash
# Usage:
#   ./bulk_dscript_array.sh GCF_002263795.3 GCF_000001405.40 ...
#   ./bulk_dscript_array.sh accessions.txt
# Skips species whose network file already exists.

source $WORK/philharmonic/sbatch_jobs/common.sh
parse_accessions "$@"

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
    N_DONE=$(ls "$SPECIES_DIR/dscript_work"/predictions_task_*.positive.tsv 2>/dev/null | wc -l)
    if [[ $N_DONE -eq $N ]]; then
        echo "[$ACC] all $N tasks already done, skipping"
        continue
    fi
    mkdir -p "$SPECIES_DIR/logs"
    RESULT=$(sbatch -p gh \
        --array="1-${N}" \
        --output="$SPECIES_DIR/logs/dscript_%A_%a.out" \
        --error="$SPECIES_DIR/logs/dscript_%A_%a.err" \
        "$PHILHARMONIC_CODE/sbatch_jobs/dscript_array.sh" "$ACC" 2>&1)
    if [[ $? -eq 0 ]]; then
        echo "[$ACC] submitted $N-task array — $RESULT"
    else
        echo "[$ACC] FAILED — $RESULT"
    fi
done
