#!/bin/bash
# Sum protein pairs across all downloaded+filtered species, to size remaining work.
#
# Usage:
#   ./benchmark_pairs.sh accessions.txt [PAIRS_PER_GPU_HOUR]
#   ./benchmark_pairs.sh GCF_002263795.3 GCF_000001405.40 ... [PAIRS_PER_GPU_HOUR]
#
# Counts every species that has been filtered (has _clean.fasta) and reports its
# protein pair count. If a trailing pairs/GPU-hour rate is given (e.g. the
# "Overall pairs/GPU-hour" from benchmark_completed.sh), also prints the estimated
# total GPU-hours to run dscript inference across the whole suite.

source /work/11301/wsoylemez/vista/philharmonic/sbatch_jobs/common.sh

# Strip an optional trailing numeric rate before parsing accessions. Accessions
# always contain letters/underscores, so a purely numeric arg is unambiguously
# the rate.
RATE=""
ARGS=("$@")
if [[ "${#ARGS[@]}" -ge 1 ]]; then
    LAST_IDX=$(( ${#ARGS[@]} - 1 ))
    if [[ "${ARGS[$LAST_IDX]}" =~ ^[0-9]+$ ]]; then
        RATE="${ARGS[$LAST_IDX]}"
        unset 'ARGS[$LAST_IDX]'
    fi
fi
parse_accessions "${ARGS[@]}"

count_proteins() {
    local dir="$1" acc="$2"
    if [[ -f "$dir/${acc}_proteins_list.txt" ]]; then
        wc -l < "$dir/${acc}_proteins_list.txt"
    else
        grep -c '^>' "$dir/${acc}_clean.fasta"
    fi
}

printf '%-30s %12s %16s\n' accession proteins pairs
printf '%-30s %12s %16s\n' \
    '------------------------------' '------------' '----------------'

TOTAL_PAIRS=0
N=0

for ACC in "${ACCS[@]}"; do
    SPECIES_DIR="$RESULTS_BASE/${ACC}_results"
    if [[ ! -f "$SPECIES_DIR/${ACC}_clean.fasta" ]]; then
        echo "[$ACC] skip: not filtered"
        continue
    fi

    PROT=$(count_proteins "$SPECIES_DIR" "$ACC")
    PAIRS=$(awk -v p="$PROT" 'BEGIN{printf "%.0f", p*(p-1)/2}')
    printf '%-30s %12s %16s\n' "$ACC" "$PROT" "$PAIRS"

    TOTAL_PAIRS=$(awk -v a="$TOTAL_PAIRS" -v b="$PAIRS" 'BEGIN{printf "%.0f", a+b}')
    N=$((N + 1))
done

echo
echo "Filtered species: $N"
echo "Total pairs:      $TOTAL_PAIRS"
if [[ -n "$RATE" ]]; then
    EST=$(awk -v p="$TOTAL_PAIRS" -v r="$RATE" 'BEGIN{printf "%.1f", p/r}')
    echo "Rate:             $RATE pairs/GPU-hour"
    echo "Est. GPU-hours:   $EST"
fi
