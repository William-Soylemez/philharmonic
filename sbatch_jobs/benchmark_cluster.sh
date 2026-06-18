#!/bin/bash
# Benchmark wall time spent on the post_cluster step, per species.
#
# Usage:
#   ./benchmark_cluster.sh accessions.txt
#   ./benchmark_cluster.sh [--perfect] GCF_002263795.3 GCF_000001405.40 ...
#
# Clustering is a single (non-array) CPU job whose SLURM job ID is encoded in
# its log name: logs/post_cluster_<JobID>.out. We map those IDs to sacct
# ElapsedRaw. Note this runs on a CPU node (not a GPU), so these are wall/CPU
# hours and should NOT be added into the GPU-hour totals.
#
# Time accounting modes:
#   default     sum every post_cluster job ever run for the species (all reruns).
#   --perfect   count only the most recent COMPLETED run = ideal time.

source /work/11301/wsoylemez/vista/philharmonic/sbatch_jobs/common.sh

PERFECT=0
ARGS=()
for a in "$@"; do
    case "$a" in
        --perfect|--ideal|--no-retries) PERFECT=1 ;;
        *) ARGS+=("$a") ;;
    esac
done
parse_accessions "${ARGS[@]}"

printf '%-30s %12s\n' accession wall_hours
printf '%-30s %12s\n' '------------------------------' '------------'

TOTAL_SECS=0
N=0

for ACC in "${ACCS[@]}"; do
    LOGDIR="$RESULTS_BASE/${ACC}_results/logs"

    # Cluster job IDs are encoded in the log filenames: post_cluster_<JobID>.out
    JIDS=$(ls "$LOGDIR"/post_cluster_*.out 2>/dev/null \
        | sed -E 's#.*/post_cluster_([0-9]+)\.out$#\1#' | sort -u)
    if [[ -z "$JIDS" ]]; then
        echo "[$ACC] skip: no post_cluster logs to map to sacct"
        continue
    fi

    if [[ "$PERFECT" == 1 ]]; then
        # Most recent COMPLETED run only.
        SECS=$(
            for JID in $JIDS; do
                sacct -X -n -P -j "$JID" --format=JobID,State,ElapsedRaw 2>/dev/null
            done | awk -F'|' '$2=="COMPLETED"{s=$3} END{print s+0}'
        )
        if [[ "$SECS" -eq 0 ]]; then
            echo "[$ACC] warn: no COMPLETED post_cluster run found in sacct"
        fi
    else
        # Real time: sum every submission, regardless of state.
        SECS=0
        for JID in $JIDS; do
            S=$(sacct -X -n -P -j "$JID" --format=ElapsedRaw 2>/dev/null \
                | awk '{s+=$1} END{print s+0}')
            SECS=$(awk -v a="$SECS" -v b="$S" 'BEGIN{printf "%.0f", a+b}')
        done
    fi

    HOURS=$(awk -v s="$SECS" 'BEGIN{printf "%.2f", s/3600}')
    printf '%-30s %12s\n' "$ACC" "$HOURS"

    TOTAL_SECS=$(awk -v a="$TOTAL_SECS" -v b="$SECS" 'BEGIN{printf "%.0f", a+b}')
    N=$((N + 1))
done

TOTAL_HOURS=$(awk -v s="$TOTAL_SECS" 'BEGIN{printf "%.2f", s/3600}')

echo
if [[ "$PERFECT" == 1 ]]; then
    echo "Mode:             perfect (most recent COMPLETED run only)"
else
    echo "Mode:             actual (all submissions summed)"
fi
echo "Species:          $N"
echo "Total wall-hours: $TOTAL_HOURS (CPU node; not GPU hours)"
