# Visualizer preprocessing (viz_preprocess)

Converts each described species' pipeline outputs into the compact JSON layout the
Db-Visualizer frontend reads, then you upload that to Cloudflare R2. This lives in
the philharmonic repo so the pipeline is self-contained; the frontend only ever
consumes the generated data.

| File | Role |
|------|------|
| `preprocess.py` | Convert one described species' outputs → compact JSON (+ `.mfd`). |
| `medford.py` | MEDFORD metadata generation (imported by `preprocess.py`). |
| `schemas.py` | pydantic models defining the output JSON contract. |
| `build_index.py` | Aggregate every species' `manifest.json` → top-level `species_index.json`. |
| `build_go_terms.py` | One-time global GO id → name map from `go-basic.obo`. |
| `viz_preprocess.sh` | **The bulk job** — iterates a group of species in one allocation. |

Data flow: the pipeline writes each species to `$RESULTS_BASE/<ACC>_results/`; the
job reads those, writes compact JSON to `$VIZ_OUT/species/<ACC>/`, then you
`rclone` `$VIZ_OUT` up to R2. Paths come from `common.sh`; `VIZ_OUT` is set at the
top of `viz_preprocess.sh` (`VIZ_CODE` is derived from `$PHILHARMONIC_CODE`).

## 1. One-time: the one extra dependency

The job runs on the shared philharmonic venv (via `activate_env`); the only thing
it adds beyond the stdlib is pydantic:

```bash
source /work/11301/wsoylemez/vista/venv/bin/activate
pip install pydantic
```

## 2. Run the bulk preprocessing

Submit one job over a group of species (file or inline args):

```bash
sbatch sbatch_jobs/viz_preprocess/viz_preprocess.sh accessions.txt
# or
sbatch sbatch_jobs/viz_preprocess/viz_preprocess.sh GCF_000002765.6 GCF_000146045.2 ...
```

It skips species that aren't described yet, re-runs the described ones (overwrites
— cheap, so resubmit any time to pick up code/data changes), and rebuilds
`species_index.json` at the end. Watch progress in
`$GLOBAL_LOGS/viz_preprocess_<jobid>.out`.

Build the global GO-term map once (independent of species):

```bash
python sbatch_jobs/viz_preprocess/build_go_terms.py "$VIZ_OUT/go_terms.json"
```

## 3. One-time: rclone → Cloudflare R2

Install rclone (no root):

```bash
mkdir -p $HOME/bin && cd /tmp
curl -O https://downloads.rclone.org/rclone-current-linux-amd64.zip
unzip rclone-current-linux-amd64.zip && mv rclone-*/rclone $HOME/bin/
chmod +x $HOME/bin/rclone
echo 'export PATH=$HOME/bin:$PATH' >> ~/.bashrc && source ~/.bashrc
```

Configure the remote (`rclone config` → new remote named `r2`, storage `s3`,
provider `Cloudflare`, paste the Access Key ID / Secret / endpoint from an R2
"Object Read & Write" API token; leave region/acl blank). Verify:

```bash
rclone lsd r2:    # should list the philharmonic-db bucket
```

## 4. Upload

```bash
rclone sync "$VIZ_OUT" r2:philharmonic-db --progress --transfers=16
```

## 5. Make the bucket readable from the website

- **Quick:** R2 → bucket → Settings → enable the **r2.dev public URL**, then set
  `NEXT_PUBLIC_DATA_BASE_URL` to `https://pub-<hash>.r2.dev` in the frontend.
- **Production:** attach a custom domain and add a CORS policy allowing
  `GET`/`HEAD` from your site origin so `fetch().json()` works cross-origin.

Verify: `curl -I https://<bucket-public-url>/species_index.json` → `HTTP 200`
with `access-control-allow-origin`.

## Re-running one species

```bash
python sbatch_jobs/viz_preprocess/preprocess.py GCF_000001215.4 \
    "$RESULTS_BASE/GCF_000001215.4_results" "$VIZ_OUT"
python sbatch_jobs/viz_preprocess/build_index.py "$VIZ_OUT"   # refresh the index
rclone sync "$VIZ_OUT/species/GCF_000001215.4" \
    r2:philharmonic-db/species/GCF_000001215.4
```

## Local development (frontend)

To generate data locally for frontend dev, point the output at the Db-Visualizer
workdir's `preprocessed_data/` (which the frontend reads via `../preprocessed_data`):

```bash
python sbatch_jobs/viz_preprocess/preprocess.py GCF_000002765.6 \
    /path/to/example_data/GCF_000002765.6 /path/to/preprocessed_data
python sbatch_jobs/viz_preprocess/build_index.py /path/to/preprocessed_data
```
