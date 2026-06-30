#!/bin/bash
#SBATCH --job-name=viz_preprocess
#SBATCH --partition=gg
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=0
#
# Bulk-preprocess described species into the visualizer's compact JSON layout.
# A single submitted job iterates over a group of species in one allocation
# (each species is cheap: pure-stdlib + pydantic, no GPU).
#
# Usage:
#     sbatch viz_preprocess.sh accessions.txt
#     sbatch viz_preprocess.sh GCF_000002765.6 GCF_000146045.2 ...
#
# Behavior:
#   - SKIPS species that aren't described yet (no clusters.json and no .zip).
#   - ALWAYS re-runs preprocessing for described species (cheap, overwrites) so
#     picking up code/data changes is just a resubmit — no stale outputs.
#   - Rebuilds species_index.json across ALL preprocessed species at the end.
#
# Requirements: uses the shared philharmonic venv (via activate_env). The only
# extra dependency is pydantic — install it once: pip install pydantic.

source /work/11301/wsoylemez/vista/philharmonic/sbatch_jobs/common.sh

# --- cluster-specific paths (adjust to where the Db-Visualizer repo lives) -----
VIZ_CODE=/work/11301/wsoylemez/vista/Db-Visualizer/preprocessing
VIZ_OUT=/work/11301/wsoylemez/vista/philharmonic_results/visualizer_data

redirect_log "$GLOBAL_LOGS/viz_preprocess_${SLURM_JOB_ID:-local}.out"
activate_env
parse_accessions "$@"

mkdir -p "$VIZ_OUT"

n_done=0; n_skipped=0; n_failed=0
for ACC in "${ACCS[@]}"; do
    SPECIES_DIR="$RESULTS_BASE/${ACC}_results"

    # Pick the input: loose pipeline outputs if present, else the describe zip
    # (preprocess.py handles either a directory or a .zip).
    if [[ -f "$SPECIES_DIR/${ACC}_clusters.json" ]]; then
        INPUT="$SPECIES_DIR"
    elif [[ -f "$SPECIES_DIR/${ACC}.zip" ]]; then
        INPUT="$SPECIES_DIR/${ACC}.zip"
    else
        echo "[$ACC] not described yet (no clusters.json or zip), skipping"
        n_skipped=$((n_skipped + 1))
        continue
    fi

    echo "[$ACC] preprocessing -> $VIZ_OUT/species/$ACC"
    if python3 "$VIZ_CODE/preprocess.py" "$ACC" "$INPUT" "$VIZ_OUT"; then
        record_status "$SPECIES_DIR" visualize done || true
        n_done=$((n_done + 1))
    else
        echo "[$ACC] FAILED"
        record_status "$SPECIES_DIR" visualize error \
            "viz preprocess failed (job ${SLURM_JOB_ID:-local})" || true
        n_failed=$((n_failed + 1))
    fi
done

# --- rebuild the top-level index across everything preprocessed so far ---------
python3 "$VIZ_CODE/build_index.py" "$VIZ_OUT"

echo "done: $n_done preprocessed, $n_skipped skipped, $n_failed failed"
