#!/bin/bash
# Shared setup sourced by all sbatch_jobs scripts.
# Defines common paths plus helper functions for logging, environment
# activation, and accession parsing. Source it as the first line of a script:
#   source /work/11301/wsoylemez/vista/philharmonic/sbatch_jobs/common.sh

PHILHARMONIC_CODE=/work/11301/wsoylemez/vista/philharmonic
RESULTS_BASE=/work/11301/wsoylemez/vista/philharmonic_results/bulk_results
EMBEDDINGS_DIR=$SCRATCH/philharmonic_embeddings
GLOBAL_LOGS=/work/11301/wsoylemez/vista/philharmonic_results/logs

# Set global group read/write permissions for all files created by this script, so that other
# users in the group can use them.
umask 0002

# Redirect all stdout/stderr to the given log file, creating its directory.
# Call this before activate_env so module-load output is captured in the log.
redirect_log() {
    mkdir -p "$(dirname "$1")"
    exec > "$1" 2>&1
}

# Load modules and activate the venv. Sets an empty OPENAI_API_KEY so the
# Snakefile's `envvars: OPENAI_API_KEY` requirement is satisfied; scripts that
# need a real key should `source /work/11301/wsoylemez/vista/.env_secrets` afterwards.
activate_env() {
    module load gcc cuda python3
    source /work/11301/wsoylemez/vista/venv/bin/activate
    export OPENAI_API_KEY=""
}

# Record a pipeline step's status into the species status.json, mirroring what
# bulk_download_filter.py does in Python.
# Usage: record_status <species_dir> <step> <status> [message]
record_status() {
    python3 "$PHILHARMONIC_CODE/sbatch_jobs/status.py" set "$@"
}

# Seed the inference (job-array) step with its total task count, at split time.
# Usage: init_inference <species_dir> <n_tasks>
init_inference() {
    python3 "$PHILHARMONIC_CODE/sbatch_jobs/status.py" init-inference "$@"
}

# Record a single array task's outcome (race-free per-task marker).
# Usage: record_task <species_dir> <task_id> <done|failed>
record_task() {
    python3 "$PHILHARMONIC_CODE/sbatch_jobs/status.py" task "$@"
}

# Populate the ACCS array from either a single accessions file or CLI args.
# Usage: parse_accessions "$@"
parse_accessions() {
    if [[ $# -eq 1 && -f "$1" ]]; then
        mapfile -t ACCS < <(grep -v '^\s*#' "$1" | grep -v '^\s*$')
    else
        ACCS=("$@")
    fi
}
