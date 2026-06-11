#!/bin/bash
#SBATCH --job-name=bulk_dscript_split
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=0

# Usage:
#   sbatch sbatch_jobs/bulk_dscript_split.sh accessions.txt
#   sbatch sbatch_jobs/bulk_dscript_split.sh GCF_002263795.3 GCF_000001405.40 ...

source $WORK/philharmonic/sbatch_jobs/common.sh

redirect_log "$GLOBAL_LOGS/bulk_dscript_split_${SLURM_JOB_ID}.out"
activate_env
parse_accessions "$@"

printf '%-30s %10s %15s %13s %8s %15s\n' \
    species proteins pairs split_blocks n_jobs pairs_per_job

for ACC in "${ACCS[@]}"; do
    SPECIES_DIR="$RESULTS_BASE/${ACC}_results"

    grep "^>" "$SPECIES_DIR/${ACC}_kept_proteins.txt" | sed 's/>//' \
        > "$SPECIES_DIR/${ACC}_proteins_list.txt"

    PROTEINS=$(wc -l < "$SPECIES_DIR/${ACC}_proteins_list.txt")

    read PAIRS SPLIT_BLOCKS N_JOBS PAIRS_PER_JOB < <(python3 -c "
import math
p = $PROTEINS
pairs = p * (p - 1) // 2
target = 24_000_000
half = max(1, math.ceil(math.sqrt(pairs / target)))
split_blocks = 2 * half
n_jobs = half ** 2
pairs_per_job = pairs // n_jobs
print(pairs, split_blocks, n_jobs, pairs_per_job)
")

    printf '%-30s %10d %15d %13d %8d %15d\n' \
        "$ACC" "$PROTEINS" "$PAIRS" "$SPLIT_BLOCKS" "$N_JOBS" "$PAIRS_PER_JOB"

    if dscript split_tasks \
        --proteins "$SPECIES_DIR/${ACC}_proteins_list.txt" \
        --embeddings "$EMBEDDINGS_DIR/${ACC}_embed.h5" \
        --workdir "$SPECIES_DIR/dscript_work" \
        --model "samsl/dscript_human_v1" \
        --split_blocks "$SPLIT_BLOCKS" \
        --blocks 10; then
        record_status "$SPECIES_DIR" split done
        # Seed the inference array tracker with the actual number of tasks
        # produced (= lines in the generated task file), so checkup can show m/n.
        TASKFILE=$(ls "$SPECIES_DIR/dscript_work"/dscript_*_tasks.sh 2>/dev/null | head -1)
        if [[ -n "$TASKFILE" ]]; then
            init_inference "$SPECIES_DIR" "$(wc -l < "$TASKFILE")"
        fi
    else
        record_status "$SPECIES_DIR" split error \
            "dscript split_tasks failed (job ${SLURM_JOB_ID}); see bulk_dscript_split_${SLURM_JOB_ID}.out"
    fi
done
