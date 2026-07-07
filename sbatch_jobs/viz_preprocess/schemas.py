"""Output JSON schemas — single source of truth for what the frontend consumes.

GO term *names* are never stored in cluster/protein data; only GO IDs (+ counts).
The frontend resolves IDs to names via the global `go_terms.json` map.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Confidence = Literal["Low", "Medium", "High", ""]


class GoTermCount(BaseModel):
    id: str
    count: int


class ClusterSummary(BaseModel):
    hash: str
    title: str
    description: str
    confidence: Confidence
    size: int
    edges: int
    triangles: int
    max_degree: int
    top_function: str | None
    # Top-N GO terms by member count; names resolved client-side via go_terms.json.
    top_go_terms: list[GoTermCount]


class ClusterGraphNode(BaseModel):
    id: str
    size: int
    top_function: str | None


class ClusterGraphEdge(BaseModel):
    source: str
    target: str
    weight: float


class ClusterGraph(BaseModel):
    nodes: list[ClusterGraphNode]
    edges: list[ClusterGraphEdge]


class ClusterMember(BaseModel):
    accession: str
    go_terms: list[str]


class ClusterDetail(BaseModel):
    hash: str
    title: str
    description: str
    confidence: Confidence
    size: int
    edges: int
    triangles: int
    max_degree: int
    top_function: str | None
    members: list[ClusterMember]
    # Intra-cluster PPI edges [a, b, weight]; weights rounded to 3 dp.
    graph: list[tuple[str, str, float]]
    # Full per-cluster GO term counts {GO_id: n_member_proteins}.
    all_go_terms: dict[str, int]
    # ReCIPE proteins re-added at this recipe threshold; omitted when empty.
    recipe_readded: list[str] = Field(default_factory=list)


class ProteinDetail(BaseModel):
    accession: str
    pfam: list[str]
    go_terms: list[str]
    cluster_hash: str | None
    ncbi_url: str


class SpeciesManifest(BaseModel):
    id: str
    display_name: str
    taxid: int | None = None
    lineage: list[str] = Field(default_factory=list)
    image_url: str | None = None
    n_clusters: int
    n_proteins: int
    # Global clustering recipe, hoisted out of per-cluster data (it's near-constant).
    recipe: dict = Field(default_factory=dict)
    # Whether a gzipped raw network is available at raw/network.positive.tsv.gz.
    has_network_download: bool = False


class SpeciesIndexEntry(BaseModel):
    id: str
    display_name: str
    taxid: int | None = None
    lineage: list[str] = Field(default_factory=list)
