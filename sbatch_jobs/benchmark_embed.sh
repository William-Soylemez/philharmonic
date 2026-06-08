#!/bin/bash
# Benchmark GPU time spent on the dscript embed step, per species.
#
# Usage:
#   ./benchmark_embed.sh accessions.txt
#   ./benchmark_embed.sh [--perfect] GCF_002263795.3 GCF_000001405.40 ...
#
# Embed is a single (non-array) job whose SLURM job ID is encoded in its log
# name: logs/dscript_embed_<JobID>.out. We map those IDs to sacct ElapsedRaw
# (1 GH200 node = 1 GPU, so wall-seconds = GPU-seconds).
#
# Time accounting modes:
#   default     sum every embed job ever run for the species (all reruns) =
#               real GPU time, including failed/retried attempts.
#   --perfect   count only the most recent COMPLETED embed run = ideal time.

source $WORK/philharmonic/sbatch_jobs/common.sh

PERFECT=0
ARGS=()
for a in "$@"; do
    case "$a" in
        --perfect|--ideal|--no-retries) PERFECT=1 ;;
        *) ARGS+=("$a") ;;
    esac
done
parse_accessions "${ARGS[@]}"

printf '%-30s %12s\n' accession gpu_hours
printf '%-30s %12s\n' '------------------------------' '------------'

TOTAL_SECS=0
N=0

for ACC in "${ACCS[@]}"; do
    LOGDIR="$RESULTS_BASE/${ACC}_results/logs"

    # Embed job IDs are encoded in the log filenames: dscript_embed_<JobID>.out
    JIDS=$(ls "$LOGDIR"/dscript_embed_*.out 2>/dev/null \
        | sed -E 's#.*/dscript_embed_([0-9]+)\.out$#\1#' | sort -u)
    if [[ -z "$JIDS" ]]; then
        echo "[$ACC] skip: no embed logs to map to sacct"
        continue
    fi

    if [[ "$PERFECT" == 1 ]]; then
        # Most recent COMPLETED embed run only.
        SECS=$(
            for JID in $JIDS; do
                sacct -X -n -P -j "$JID" --format=JobID,State,ElapsedRaw 2>/dev/null
            done | awk -F'|' '$2=="COMPLETED"{s=$3} END{print s+0}'
        )
        if [[ "$SECS" -eq 0 ]]; then
            echo "[$ACC] warn: no COMPLETED embed run found in sacct"
        fi
    else
        # Real time: sum every embed submission, regardless of state.
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
    echo "Mode:             perfect (most recent COMPLETED embed run only)"
else
    echo "Mode:             actual (all embed submissions summed)"
fi
echo "Species:          $N"
echo "Total GPU-hours:  $TOTAL_HOURS"
