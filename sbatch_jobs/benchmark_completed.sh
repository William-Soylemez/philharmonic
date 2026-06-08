#!/bin/bash
# Benchmark actual GPU time for species whose dscript inference has fully completed.
#
# Usage:
#   ./benchmark_completed.sh accessions.txt
#   ./benchmark_completed.sh [--perfect] GCF_002263795.3 GCF_000001405.40 ...
#
# For each species where every prediction task is present, sums the wall time of
# the dscript array tasks via sacct (1 GH200 node = 1 GPU, so task-hours =
# GPU-hours) and reports it next to the protein-pair count. The overall
# pairs/GPU-hour at the bottom is the throughput to feed into benchmark_pairs.sh.
#
# Time accounting modes:
#   default     sum ALL array tasks ever run (every state, every resubmission) =
#               real GPU time spent, including retries/timeouts.
#   --perfect   count one COMPLETED run per task index = ideal "everything went
#               right the first time" GPU time, retries excluded.

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

count_proteins() {
    local dir="$1" acc="$2"
    if [[ -f "$dir/${acc}_proteins_list.txt" ]]; then
        wc -l < "$dir/${acc}_proteins_list.txt"
    else
        grep -c '^>' "$dir/${acc}_clean.fasta"
    fi
}

printf '%-30s %12s %16s %12s %16s\n' accession proteins pairs gpu_hours pairs_per_gpu_hr
printf '%-30s %12s %16s %12s %16s\n' \
    '------------------------------' '------------' '----------------' '------------' '----------------'

TOTAL_PAIRS=0
TOTAL_SECS=0
N_COMPLETED=0

for ACC in "${ACCS[@]}"; do
    SPECIES_DIR="$RESULTS_BASE/${ACC}_results"
    WORKDIR="$SPECIES_DIR/dscript_work"

    TASKFILE=$(ls "$WORKDIR"/dscript_*_tasks.sh 2>/dev/null | head -1)
    if [[ -z "$TASKFILE" ]]; then
        echo "[$ACC] skip: not split"
        continue
    fi
    N_TASKS=$(wc -l < "$TASKFILE")
    N_DONE=$(ls "$WORKDIR"/predictions_task_*.positive.tsv 2>/dev/null | wc -l)
    if [[ "$N_TASKS" -eq 0 || "$N_DONE" -ne "$N_TASKS" ]]; then
        echo "[$ACC] skip: inference incomplete ($N_DONE/$N_TASKS)"
        continue
    fi

    PROT=$(count_proteins "$SPECIES_DIR" "$ACC")
    PAIRS=$(awk -v p="$PROT" 'BEGIN{printf "%.0f", p*(p-1)/2}')

    # Array job IDs are encoded in the log filenames: dscript_<ArrayJobID>_<Task>.out
    AIDS=$(ls "$SPECIES_DIR/logs"/dscript_*_*.out 2>/dev/null \
        | sed -E 's#.*/dscript_([0-9]+)_[0-9]+\.out$#\1#' | sort -u)
    if [[ -z "$AIDS" ]]; then
        echo "[$ACC] skip: no array logs to map to sacct"
        continue
    fi

    if [[ "$PERFECT" == 1 ]]; then
        # One COMPLETED run per task index, deduped across all array job IDs.
        read SECS NCOMP < <(
            for AID in $AIDS; do
                sacct -X -n -P -j "$AID" --format=JobID,State,ElapsedRaw 2>/dev/null
            done | awk -F'|' '
                $2=="COMPLETED" { n=split($1,a,"_"); t[a[n]]=$3 }  # last COMPLETED per task wins
                END { s=0; c=0; for (k in t) { s+=t[k]; c++ } printf "%.0f %d", s, c }'
        )
        [[ -z "$SECS" ]] && { SECS=0; NCOMP=0; }
        if [[ "$NCOMP" -ne "$N_TASKS" ]]; then
            echo "[$ACC] warn: only $NCOMP/$N_TASKS tasks have a COMPLETED sacct record; perfect time may be understated"
        fi
    else
        # Real time: sum every task of every submission, regardless of state.
        SECS=0
        for AID in $AIDS; do
            S=$(sacct -X -n -P -j "$AID" --format=ElapsedRaw 2>/dev/null \
                | awk '{s+=$1} END{print s+0}')
            SECS=$(awk -v a="$SECS" -v b="$S" 'BEGIN{printf "%.0f", a+b}')
        done
    fi

    if [[ "$SECS" -eq 0 ]]; then
        echo "[$ACC] warn: sacct returned no time (accounting aged out?), counting pairs only"
    fi

    HOURS=$(awk -v s="$SECS" 'BEGIN{printf "%.2f", s/3600}')
    PPH=$(awk -v p="$PAIRS" -v s="$SECS" 'BEGIN{ if(s>0) printf "%.0f", p/(s/3600); else print "NA"}')

    printf '%-30s %12s %16s %12s %16s\n' "$ACC" "$PROT" "$PAIRS" "$HOURS" "$PPH"

    TOTAL_PAIRS=$(awk -v a="$TOTAL_PAIRS" -v b="$PAIRS" 'BEGIN{printf "%.0f", a+b}')
    TOTAL_SECS=$(awk -v a="$TOTAL_SECS" -v b="$SECS" 'BEGIN{printf "%.0f", a+b}')
    N_COMPLETED=$((N_COMPLETED + 1))
done

TOTAL_HOURS=$(awk -v s="$TOTAL_SECS" 'BEGIN{printf "%.2f", s/3600}')
OVERALL_PPH=$(awk -v p="$TOTAL_PAIRS" -v s="$TOTAL_SECS" 'BEGIN{ if(s>0) printf "%.0f", p/(s/3600); else print "NA"}')

echo
if [[ "$PERFECT" == 1 ]]; then
    echo "Mode:                   perfect (one COMPLETED run per task; retries excluded)"
else
    echo "Mode:                   actual (all tasks/resubmissions summed; retries included)"
fi
echo "Completed species:      $N_COMPLETED"
echo "Total pairs:            $TOTAL_PAIRS"
echo "Total GPU-hours:        $TOTAL_HOURS"
echo "Overall pairs/GPU-hour: $OVERALL_PPH"
