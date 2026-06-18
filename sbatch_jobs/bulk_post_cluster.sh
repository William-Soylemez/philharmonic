#!/bin/bash
# Usage:
#   ./bulk_post_cluster.sh GCF_002263795.3 GCF_000001405.40 ...
#   ./bulk_post_cluster.sh accessions.txt
# Skips species already clustered or whose dscript inference is incomplete.

source /work/11301/wsoylemez/vista/philharmonic/sbatch_jobs/common.sh
parse_accessions "$@"

for ACC in "${ACCS[@]}"; do
    SPECIES_DIR="$RESULTS_BASE/${ACC}_results"

    if [[ -f "$SPECIES_DIR/${ACC}_clusters.pre.json" ]]; then
        echo "[$ACC] already clustered, skipping"
        continue
    fi

    TASKFILE=$(ls "$SPECIES_DIR/dscript_work"/dscript_*_tasks.sh 2>/dev/null | head -1)
    if [[ -z "$TASKFILE" ]]; then
        echo "[$ACC] dscript not staged, skipping"
        continue
    fi

    N_TASKS=$(wc -l < "$TASKFILE")
    N_DONE=$(ls "$SPECIES_DIR/dscript_work"/predictions_task_*.positive.tsv 2>/dev/null | wc -l)
    if [[ $N_DONE -lt $N_TASKS ]]; then
        echo "[$ACC] dscript incomplete ($N_DONE/$N_TASKS tasks), skipping"
        continue
    fi

    mkdir -p "$SPECIES_DIR/logs"
    RESULT=$(sbatch -p gg \
        --output="$SPECIES_DIR/logs/post_cluster_%j.out" \
        --error="$SPECIES_DIR/logs/post_cluster_%j.err" \
        "$PHILHARMONIC_CODE/sbatch_jobs/post_cluster.sh" "$ACC" 2>&1)
    if [[ $? -eq 0 ]]; then
        echo "[$ACC] submitted — $RESULT"
    else
        echo "[$ACC] FAILED — $RESULT"
    fi
done
