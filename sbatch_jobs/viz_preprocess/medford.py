"""Generate a MEDFORD metadata file for a species.

Most fields are constant; the per-species variable parts are:
  - @Dscript-Model   : topsy_turvy for a known set of accessions, else dscript.
  - @Date            : completion time of the last describe step (from its logs).
  - @Data_Ref-URI    : the NCBI protein FASTA URI, resolved the same way the
                       download/fetch step does (parse accession + list the dir).
  - @Data_Ref-Size   : human-readable size of the unfiltered protein FASTA.

Generation is best-effort: anything that can't be resolved (no describe log, no
unfiltered FASTA, no network for the URI) is left blank rather than failing.
"""

from __future__ import annotations

import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

# Accessions whose D-SCRIPT predictions used the Topsy-Turvy model; everything
# else used the plain D-SCRIPT human model.
TOPSY_TURVY_ACCESSIONS = {
    "GCF_002263795.3",
    "GCF_016699485.2",
    "GCF_000004195.4",
    "GCF_049306965.1",
    "GCF_000002235.5",
    "GCF_000001215.4",
    "GCF_000146045.2",
    "GCF_000149245.1",
    "GCF_000004695.1",
    "GCF_000002765.6",
    "GCF_000210295.1",
}

NCBI_BASE = "https://ftp.ncbi.nlm.nih.gov/genomes/all"
ACCESSION_RE = re.compile(r"^(GCF|GCA)_(\d{3})(\d{3})(\d{3})\.\d+$")

TEMPLATE = """\
# Author: William Soylemez
# Date: {header_date}

@MEDFORD description
@MEDFORD-Version 1.0

@Dscript-Model {dscript_model}

{describe_models}

@Date {date}
@Date-Note Analysis completed

@Data_Ref {accession}
@Data_Ref-Type FASTA
@Data_Ref-URI {uri}
@Data_Ref-Size {size}

@Code_Ref Dscript
@Code_Ref-Type PPI
@Code_Ref-URI https://github.com/philharmonic/dscript
@Code_Ref-Version 0.3.1

@Code_Ref PHILHARMONIC
@Code_Ref-Type Functional Clustering
@Code_Ref-URI https://github.com/samsledje/philharmonic
@Code_Ref-Version 0.8.2.dev34

@Code_Ref HMMER
@Code_Ref-Type GO Labeling
@Code_Ref-URI http://hmmer.org/
@Code_Ref-Version 3.4

@Code_Ref Scikit-learn
@Code_Ref-Type Machine Learning Tools
@Code_Ref-URI https://scikit-learn.org/
@Code_Ref-Version 1.6.1

@Code_Ref MMseqs2
@Code_Ref-Type Sequence Clustering and Filtering
@Code_Ref-URI https://github.com/soedinglab/MMseqs2
@Code_Ref-Version dca44bc6b867b16ab47932178272440eb27612bd

@Data_Ref GO Database
@Data_Ref-Type GO Labeling
@Data_Ref-URI http://geneontology.org/
@Data_Ref-Version releases/2026-03-25

@Sequence_Filtering-Max_Length 1200
@Sequence_Filtering-Min_Length 50
@Sequence_Filtering-Identity 0.95

@Data_Ref Processed Data
@Data_Ref-Type Multiple files
@Data_Ref-URI https://cb.csail.mit.edu/philharmonicDB/preprocessed_data/
"""


def _dscript_model(accession: str) -> str:
    if accession in TOPSY_TURVY_ACCESSIONS:
        return "samsl/topsy_turvy_human_v1"
    return "samsl/dscript_human_v1"


def _describe_models(accession: str) -> str:
    """Topsy-Turvy species were described with gpt-4o + gpt-5-nano; the rest
    with gpt-5-nano only."""
    if accession in TOPSY_TURVY_ACCESSIONS:
        return "@Describe-Model gpt-4o\n@Describe-Model gpt-5-nano"
    return "@Describe-Model gpt-5-nano"


def _parent_url(accession: str) -> str:
    m = ACCESSION_RE.match(accession)
    if not m:
        raise ValueError(f"bad accession format: {accession!r}")
    prefix, a, b, c = m.groups()
    return f"{NCBI_BASE}/{prefix}/{a}/{b}/{c}/"


def _resolve_assembly_dir(accession: str, species_dir: Path) -> str:
    """Find the `{accession}_GCA_...` assembly directory name.

    Prefers a locally-kept `*_protein.faa.gz` (no network); otherwise lists the
    NCBI parent directory the same way the download/fetch step does.
    """
    local = sorted(species_dir.glob(f"{accession}_*_protein.faa.gz"))
    if local:
        return local[0].name[: -len("_protein.faa.gz")]
    parent = _parent_url(accession)
    with urllib.request.urlopen(parent, timeout=60) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    matches = re.findall(rf'href="({re.escape(accession)}_[^"/]+)/"', html)
    if not matches:
        raise RuntimeError(f"no assembly dir for {accession} at {parent}")
    return matches[0]


def _data_ref_uri(accession: str, species_dir: Path) -> str:
    asm = _resolve_assembly_dir(accession, species_dir)
    return f"{_parent_url(accession)}{asm}/{asm}_protein.faa.gz"


def _human_size(num_bytes: int) -> str:
    """du -h style, e.g. 2411724 -> '2.3M'."""
    size = float(num_bytes)
    for unit in ["", "K", "M", "G", "T", "P"]:
        if size < 1024 or unit == "P":
            s = f"{size:.1f}".rstrip("0").rstrip(".")
            return f"{s}{unit}"
        size /= 1024
    return f"{num_bytes}"


def _describe_timestamp(species_dir: Path, fallback: Path | None) -> str:
    """Completion time of the most recent describe step, from its logs.

    Falls back to the mtime of the given file (e.g. clusters.json) if no
    describe log is present.
    """
    logs_dir = species_dir / "logs"
    candidates = (
        sorted(logs_dir.glob("post_describe_*"), key=lambda p: p.stat().st_mtime)
        if logs_dir.is_dir()
        else []
    )
    source = candidates[-1] if candidates else fallback
    if source and source.exists():
        return datetime.fromtimestamp(source.stat().st_mtime).replace(microsecond=0).isoformat()
    return ""


def write_medford(species_id: str, species_dir: Path, out_dir: Path) -> Path:
    """Write `<out_dir>/<species_id>.mfd`. Best-effort on the variable fields."""
    clusters_json = species_dir / f"{species_id}_clusters.json"

    date = _describe_timestamp(species_dir, clusters_json)

    try:
        uri = _data_ref_uri(species_id, species_dir)
    except Exception as e:  # network/format issues shouldn't block preprocessing
        print(f"[{species_id}] MEDFORD: could not resolve Data_Ref URI: {e}", file=sys.stderr)
        uri = ""

    unfiltered = species_dir / f"{species_id}_unfiltered.fasta"
    size = _human_size(unfiltered.stat().st_size) if unfiltered.exists() else ""
    if not size:
        print(f"[{species_id}] MEDFORD: unfiltered FASTA not found at {unfiltered}", file=sys.stderr)

    now = datetime.now()
    content = TEMPLATE.format(
        header_date=f"{now:%B} {now.day}, {now:%Y}",
        dscript_model=_dscript_model(species_id),
        describe_models=_describe_models(species_id),
        date=date,
        accession=species_id,
        uri=uri,
        size=size,
    )
    out_path = out_dir / f"{species_id}.mfd"
    out_path.write_text(content)
    return out_path
