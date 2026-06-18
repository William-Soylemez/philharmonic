#!/bin/bash
#SBATCH --job-name=redo_describe
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#SBATCH --time=12:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=0

# Re-run LLM cluster naming for a species that was already described, re-calling
# the model ONLY for clusters whose previous attempt failed (llm_confidence ==
# "Unknown", typically from rate limiting). Reads and rewrites the described
# clusters.json in place, regenerates the human-readable summary, then re-zips.
#
# summarize-clusters is idempotent: clusters that already have a confident name
# are kept as-is, so this is cheap and safe to re-run.

source /work/11301/wsoylemez/vista/philharmonic/sbatch_jobs/common.sh

SPECIES=$1
SPECIES_DIR="$RESULTS_BASE/${SPECIES}_results"
redirect_log "$SPECIES_DIR/logs/redo_describe_${SLURM_JOB_ID}.out"
activate_env
source /work/11301/wsoylemez/vista/.env_secrets

CLUSTERS_JSON="$SPECIES_DIR/${SPECIES}_clusters.json"
if [[ ! -f "$CLUSTERS_JSON" ]]; then
    record_status "$SPECIES_DIR" describe error \
        "redo_describe: $CLUSTERS_JSON not found; run the normal describe step first (job ${SLURM_JOB_ID})"
    exit 1
fi

MODEL=$(python3 -c "import yaml; print(yaml.safe_load(open('$PHILHARMONIC_CODE/configs/config_slurm.yml'))['llm']['model'])")

cd "$RESULTS_BASE"

# Re-name only the previously-failed (Unknown) clusters, in place. Backoff in
# summarize-clusters keeps a fresh round of rate limits from re-failing them.
if philharmonic summarize-clusters --llm-name \
    --model "$MODEL" \
    --api-key "$OPENAI_API_KEY" \
    -o "$SPECIES_DIR/${SPECIES}_human_readable.txt" \
    --json "$CLUSTERS_JSON" \
    --go_db shared/go.obo \
    -cfp "$CLUSTERS_JSON"; then
    # clusters.json / human_readable are now newer than clusters.pre.json, so
    # snakemake re-zips without re-running describe (which would read pre.json
    # and clobber our re-named result).
    snakemake \
        --snakefile "$PHILHARMONIC_CODE/Snakefile_slurm" \
        --configfile "$PHILHARMONIC_CODE/configs/config_slurm.yml" \
        --cores 8 \
        --rerun-incomplete \
        --nolock \
        "${SPECIES}_results/${SPECIES}.zip"
    record_status "$SPECIES_DIR" describe done
else
    record_status "$SPECIES_DIR" describe error \
        "redo_describe summarize-clusters failed (job ${SLURM_JOB_ID}); see logs/redo_describe_${SLURM_JOB_ID}.out"
fi
