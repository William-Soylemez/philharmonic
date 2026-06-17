#!/bin/bash
# Usage:
#   ./bulk_redo_describe.sh GCF_002263795.3 GCF_000001405.40 ...
#   ./bulk_redo_describe.sh accessions.txt
# Re-runs LLM naming for already-described species, re-calling the model only for
# clusters that previously failed (llm_confidence == "Unknown"). Skips species
# that were never described, and species with no remaining Unknown clusters.

source $WORK/philharmonic/sbatch_jobs/common.sh
parse_accessions "$@"

for ACC in "${ACCS[@]}"; do
    SPECIES_DIR="$RESULTS_BASE/${ACC}_results"
    CLUSTERS_JSON="$SPECIES_DIR/${ACC}_clusters.json"

    if [[ ! -f "$CLUSTERS_JSON" ]]; then
        echo "[$ACC] not yet described (no clusters.json), skipping"
        continue
    fi

    if ! grep -q '"llm_confidence": "Unknown"' "$CLUSTERS_JSON"; then
        echo "[$ACC] no Unknown-confidence clusters, skipping"
        continue
    fi

    mkdir -p "$SPECIES_DIR/logs"
    RESULT=$(sbatch -p gg \
        --output="$SPECIES_DIR/logs/redo_describe_%j.out" \
        --error="$SPECIES_DIR/logs/redo_describe_%j.err" \
        "$PHILHARMONIC_CODE/sbatch_jobs/redo_describe.sh" "$ACC" 2>&1)
    if [[ $? -eq 0 ]]; then
        echo "[$ACC] submitted — $RESULT"
    else
        echo "[$ACC] FAILED — $RESULT"
    fi
done
