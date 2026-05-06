"""
OWNER: Anirudh (Strategy)

Trust + rivalry graph. Adjacency lookups for fast metric computation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.schema import Edge


@dataclass
class TrustGraph:
    """
    Directed graph indexed both ways.

    out_edges[v][u] = Edge(v -> u)   - what v thinks of u
    in_edges[u][v]  = Edge(v -> u)   - same edge, indexed by destination
    """
    out_edges: dict[str, dict[str, Edge]] = field(default_factory=dict)
    in_edges: dict[str, dict[str, Edge]] = field(default_factory=dict)

    def get(self, src: str, dst: str) -> Edge | None:
        return self.out_edges.get(src, {}).get(dst)

    def outgoing(self, src: str) -> list[Edge]:
        return list(self.out_edges.get(src, {}).values())

    def incoming(self, dst: str) -> list[Edge]:
        return list(self.in_edges.get(dst, {}).values())

    def has_node(self, rep_id: str) -> bool:
        return rep_id in self.out_edges or rep_id in self.in_edges


def build_graph(edges: list[Edge]) -> TrustGraph:
    """
    Build adjacency dicts from the edge list. Last write wins on duplicates
    (Track A's cleaner already dedupes, this is just defensive).
    """
    graph = TrustGraph()
    for e in edges:
        graph.out_edges.setdefault(e.from_id, {})[e.to_id] = e
        graph.in_edges.setdefault(e.to_id, {})[e.from_id] = e
    return graph
