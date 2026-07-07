"""Preprocess one PHILHARMONIC species into a compact, directly-readable JSON layout.

The newer pipeline output embeds the LLM annotations and an aggregated GO-term map
directly in clusters.json, which makes several inputs redundant. This script strips
that redundancy and rounds floats so the browser fetches small, ready-to-use JSON.

Usage:
    python preprocess.py <species_id> <input_dir_or_zip> <output_root>

Input must contain files named `<species_id>_<suffix>`:
    clusters.json                  # per-cluster: members, graph, recipe, GO_terms, llm_*, human_readable
    cluster_graph.tsv              # cluster-of-clusters edges
    cluster_graph_functions.tsv    # per-cluster top function label
    GO_map.csv                     # protein -> pfam, GO annotations
    network.positive.tsv           # full PPI network (kept only as gzipped download)
    human_readable.txt             # DROPPED: fully redundant with clusters.json

Output (under <output_root>/species/<species_id>/):
    manifest.json
    clusters.json                  # summaries (top-5 GO terms), sorted by size desc
    cluster_graph.json             # meta-graph + spring layout, go_fn folded into nodes
    gene_index.json                # accession -> cluster_hash
    clusters/<hash>.json           # full detail incl. all GO terms
    proteins.json                  # {accession: detail} map, loaded once per species
    raw/network.positive.tsv.gz    # gzipped full network, download-only

Redundancy removed vs. raw:
    - network.positive.tsv         -> gzipped, not loaded by any page
    - human_readable.txt           -> deleted (llm_* fields already structured)
    - clusters.json.human_readable -> deleted (we parse out only Triangles/MaxDegree)
    - clusters.json.GO_terms       -> kept in detail only; summary keeps top-5
    - clusters.json.recipe         -> hoisted to manifest; per-cluster keeps re-added list
    - graph weights                -> rounded to 3 dp
    - GO_map manual_annot column   -> dropped; GO IDs deduped per protein
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from medford import write_medford
from schemas import (
    ClusterDetail,
    ClusterGraph,
    ClusterGraphEdge,
    ClusterGraphNode,
    ClusterMember,
    ClusterSummary,
    GoTermCount,
    ProteinDetail,
    SpeciesManifest,
)

TOP_GO_TERMS_IN_SUMMARY = 5
WEIGHT_DP = 3

STATS_RE = re.compile(r"Triangles:\s*(\d+).*?Max Degree:\s*(\d+)", re.S)


# --------------------------------------------------------------------------- io

def _resolve_input_dir(input_path: Path, species_id: str) -> tuple[Path, Path | None]:
    """If input is a zip, extract to tempdir. Returns (working_dir, tempdir_to_cleanup)."""
    if input_path.is_dir():
        return input_path, None
    if input_path.suffix == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix=f"philharmonic_{species_id}_"))
        with zipfile.ZipFile(input_path) as zf:
            zf.extractall(tmp)
        marker = f"{species_id}_clusters.json"
        for candidate in [tmp, *tmp.iterdir()]:
            if candidate.is_dir() and (candidate / marker).exists():
                return candidate, tmp
        return tmp, tmp
    raise ValueError(f"input must be a directory or .zip, got {input_path}")


def _path(work: Path, species_id: str, suffix: str) -> Path:
    return work / f"{species_id}_{suffix}"


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(",", ":")))


# ------------------------------------------------------------------ transforms

def _normalize_confidence(raw: str | None) -> str:
    if not raw:
        return ""
    v = raw.strip()
    if v.lower().startswith("confidence:"):
        v = v.split(":", 1)[1].strip()
    if v in ("Low", "Medium", "High"):
        return v
    return ""  # "Unknown", "None", "" -> empty


def _parse_stats(human_readable: str) -> tuple[int, int]:
    """Pull (triangles, max_degree) out of the embedded text block."""
    m = STATS_RE.search(human_readable or "")
    if not m:
        return 0, 0
    return int(m.group(1)), int(m.group(2))


def _recipe_readded(recipe: dict) -> list[str]:
    """Flatten ReCIPE re-added accessions out of recipe[method][threshold]."""
    out: list[str] = []
    for method_val in (recipe or {}).values():
        if isinstance(method_val, dict):
            for thr_val in method_val.values():
                if isinstance(thr_val, list):
                    out.extend(thr_val)
    return out


def _global_recipe(recipe: dict) -> dict:
    """The recipe structure with re-added lists stripped (just method/threshold keys)."""
    out: dict = {}
    for method, method_val in (recipe or {}).items():
        if isinstance(method_val, dict):
            out[method] = list(method_val.keys())
    return out


def _load_go_map(path: Path) -> dict[str, dict]:
    """{accession: {pfam: [...], go_terms: [...deduped...]}}, dropping manual_annot."""
    out: dict[str, dict] = {}
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            acc = (row.get("prot_id") or "").strip()
            if not acc:
                continue
            pfam = [p for p in (row.get("pfam_list") or "").split(";") if p]
            seen: set[str] = set()
            go: list[str] = []
            for g in (row.get("GO_list") or "").split(";"):
                if g and g not in seen:
                    seen.add(g)
                    go.append(g)
            out[acc] = {"pfam": pfam, "go_terms": go}
    return out


def _load_functions(path: Path) -> dict[str, str | None]:
    """{cluster_hash: go_fn or None}."""
    out: dict[str, str | None] = {}
    with path.open(newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            fn = (row.get("go_fn") or "").strip()
            out[str(row["key"])] = fn or None
    return out


def _load_cluster_graph(path: Path) -> list[tuple[str, str, float]]:
    """[(source_hash, target_hash, weight), ...]."""
    out: list[tuple[str, str, float]] = []
    with path.open(newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            out.append((str(row["source"]), str(row["target"]), float(row["weight"])))
    return out


# --------------------------------------------------------------------- builders

def _build_clusters(
    clusters: dict,
    functions: dict[str, str | None],
) -> tuple[list[ClusterSummary], dict[str, ClusterDetail]]:
    summaries: list[ClusterSummary] = []
    details: dict[str, ClusterDetail] = {}

    for chash, c in clusters.items():
        chash = str(chash)
        members = c.get("members", [])
        size = len(members)
        graph = [(str(a), str(b), round(float(w), WEIGHT_DP)) for a, b, w in c.get("graph", [])]
        go_counts = {str(k): int(v) for k, v in (c.get("GO_terms") or {}).items()}
        triangles, max_degree = _parse_stats(c.get("human_readable", ""))
        top_function = functions.get(chash)
        confidence = _normalize_confidence(c.get("llm_confidence"))
        title = c.get("llm_name") or ""
        description = c.get("llm_explanation") or ""

        top_go = sorted(go_counts.items(), key=lambda kv: kv[1], reverse=True)[:TOP_GO_TERMS_IN_SUMMARY]
        top_go_terms = [GoTermCount(id=gid, count=cnt) for gid, cnt in top_go]

        summaries.append(
            ClusterSummary(
                hash=chash,
                title=title,
                description=description,
                confidence=confidence,
                size=size,
                edges=len(graph),
                triangles=triangles,
                max_degree=max_degree,
                top_function=top_function,
                top_go_terms=top_go_terms,
            )
        )
        details[chash] = ClusterDetail(
            hash=chash,
            title=title,
            description=description,
            confidence=confidence,
            size=size,
            edges=len(graph),
            triangles=triangles,
            max_degree=max_degree,
            top_function=top_function,
            members=[],  # filled in by _attach_members
            graph=graph,
            all_go_terms=go_counts,
            recipe_readded=_recipe_readded(c.get("recipe", {})),
        )

    summaries.sort(key=lambda s: s.size, reverse=True)
    return summaries, details


def _attach_members(
    clusters: dict,
    details: dict[str, ClusterDetail],
    go_map: dict[str, dict],
) -> None:
    for chash, c in clusters.items():
        detail = details[str(chash)]
        detail.members = [
            ClusterMember(accession=acc, go_terms=go_map.get(acc, {}).get("go_terms", []))
            for acc in c.get("members", [])
        ]


def _build_cluster_graph(
    edges: list[tuple[str, str, float]],
    summaries: list[ClusterSummary],
) -> ClusterGraph:
    """Meta-graph of clusters. Layout is done client-side (fcose), so no coords."""
    by_hash = {s.hash: s for s in summaries}
    nodes = [
        ClusterGraphNode(id=s.hash, size=s.size, top_function=s.top_function)
        for s in summaries
    ]
    graph_edges = [
        ClusterGraphEdge(source=src, target=tgt, weight=weight)
        for src, tgt, weight in edges
        if src in by_hash and tgt in by_hash
    ]
    return ClusterGraph(nodes=nodes, edges=graph_edges)


def _build_gene_index(clusters: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for chash, c in clusters.items():
        for acc in c.get("members", []):
            out[acc] = str(chash)
    return out


_SPECIES_BRACKET_RE = re.compile(r"\s*\[[^\]]*\]\s*$")


def _load_protein_names(fasta_path: Path) -> dict[str, str]:
    """{accession: name} from FASTA headers `>accession name... [Genus species]`.

    The name is the header minus the leading accession token and the trailing
    `[species]` bracket. Only header lines are read.
    """
    names: dict[str, str] = {}
    if not fasta_path.exists():
        return names
    with fasta_path.open() as f:
        for line in f:
            if not line.startswith(">"):
                continue
            parts = line[1:].strip().split(None, 1)
            acc = parts[0]
            rest = parts[1] if len(parts) > 1 else ""
            names[acc] = _SPECIES_BRACKET_RE.sub("", rest).strip()
    return names


def _build_proteins(
    go_map: dict[str, dict],
    gene_index: dict[str, str],
    names: dict[str, str],
) -> dict[str, ProteinDetail]:
    # Every protein gets an entry — the union of GO-mapped proteins and all
    # cluster members — so a gene page always loads, even with no annotations.
    accessions = set(go_map) | set(gene_index)
    return {
        acc: ProteinDetail(
            accession=acc,
            name=names.get(acc, ""),
            pfam=go_map.get(acc, {}).get("pfam", []),
            go_terms=go_map.get(acc, {}).get("go_terms", []),
            cluster_hash=gene_index.get(acc),
            ncbi_url=f"https://www.ncbi.nlm.nih.gov/protein/{acc}",
        )
        for acc in accessions
    }


def _gzip_network(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("rb") as fi, gzip.open(dst, "wb", compresslevel=6) as fo:
        shutil.copyfileobj(fi, fo)


# ----------------------------------------------------------------------- driver

def preprocess(species_id: str, input_path: Path, output_root: Path) -> None:
    work, tmp_to_clean = _resolve_input_dir(input_path, species_id)
    try:
        clusters_path = _path(work, species_id, "clusters.json")
        graph_path = _path(work, species_id, "cluster_graph.tsv")
        functions_path = _path(work, species_id, "cluster_graph_functions.tsv")
        go_map_path = _path(work, species_id, "GO_map.csv")
        network_path = _path(work, species_id, "network.positive.tsv")

        if not clusters_path.exists():
            raise FileNotFoundError(clusters_path)

        # Original species dir (parent of the zip, when input is a zip). Holds the
        # describe logs and the unfiltered FASTA used for names + MEDFORD.
        species_dir = input_path if input_path.is_dir() else input_path.parent

        with clusters_path.open() as f:
            clusters = json.load(f)
        functions = _load_functions(functions_path) if functions_path.exists() else {}
        go_map = _load_go_map(go_map_path) if go_map_path.exists() else {}
        cluster_edges = _load_cluster_graph(graph_path) if graph_path.exists() else []
        names = _load_protein_names(species_dir / f"{species_id}_unfiltered.fasta")

        # global recipe (assume uniform; take the first cluster's structure)
        first = next(iter(clusters.values())) if clusters else {}
        global_recipe = _global_recipe(first.get("recipe", {}))

        out_dir = output_root / "species" / species_id
        (out_dir / "clusters").mkdir(parents=True, exist_ok=True)

        summaries, details = _build_clusters(clusters, functions)
        _attach_members(clusters, details, go_map)

        _write_json(out_dir / "clusters.json", [s.model_dump() for s in summaries])
        for chash, detail in details.items():
            _write_json(out_dir / "clusters" / f"{chash}.json", detail.model_dump())

        cluster_graph = _build_cluster_graph(cluster_edges, summaries)
        _write_json(out_dir / "cluster_graph.json", cluster_graph.model_dump())

        gene_index = _build_gene_index(clusters)
        _write_json(out_dir / "gene_index.json", gene_index)

        proteins = _build_proteins(go_map, gene_index, names)
        _write_json(
            out_dir / "proteins.json",
            {acc: detail.model_dump() for acc, detail in proteins.items()},
        )

        has_network = network_path.exists()
        if has_network:
            _gzip_network(network_path, out_dir / "raw" / "network.positive.tsv.gz")

        manifest = SpeciesManifest(
            id=species_id,
            display_name=species_id,
            n_clusters=len(summaries),
            n_proteins=len(proteins),
            recipe=global_recipe,
            has_network_download=has_network,
        )
        _write_json(out_dir / "manifest.json", manifest.model_dump())

        # MEDFORD metadata (uses describe logs / unfiltered FASTA in species_dir).
        try:
            write_medford(species_id, species_dir, out_dir)
        except Exception as e:
            print(f"[{species_id}] MEDFORD generation failed: {e}", file=sys.stderr)

        print(f"[{species_id}] {len(summaries)} clusters, {len(proteins)} proteins → {out_dir}")
    finally:
        if tmp_to_clean is not None:
            shutil.rmtree(tmp_to_clean, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("species_id")
    ap.add_argument("input_path", type=Path, help="dir or .zip with the raw files")
    ap.add_argument("output_root", type=Path)
    args = ap.parse_args()
    preprocess(args.species_id, args.input_path, args.output_root)


if __name__ == "__main__":
    main()
