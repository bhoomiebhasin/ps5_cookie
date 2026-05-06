"""
OWNER: Track B (Strategy)

Trust + rivalry graph. Adjacency lookups for fast metric computation.

Build once at the start of consensus and pass everywhere downstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.schema import Edge


@dataclass
class TrustGraph:
    """Directed graph indexed both ways."""
    out_edges: dict[str, dict[str, Edge]] = field(default_factory=dict)
    in_edges: dict[str, dict[str, Edge]] = field(default_factory=dict)

    def get(self, src: str, dst: str) -> Edge | None:
        return self.out_edges.get(src, {}).get(dst)

    def outgoing(self, src: str) -> list[Edge]:
        return list(self.out_edges.get(src, {}).values())

    def incoming(self, dst: str) -> list[Edge]:
        return list(self.in_edges.get(dst, {}).values())


def build_graph(edges: list[Edge]) -> TrustGraph:
    """
    Build adjacency dicts from the edge list. Last write wins on duplicates
    (Track A should have already deduped, this is just defensive).
    """
    raise NotImplementedError("Track B: implement build_graph")
