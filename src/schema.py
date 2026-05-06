"""
Shared dataclasses. Frozen contract between Track A (data) and Track B (strategy).

DO NOT modify field names without notifying the team.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Rep:
    id: str
    name: str
    faction: str
    influence: float
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Proposal:
    id: str
    title: str
    sponsor: str
    priority: float


@dataclass
class Objection:
    rep_id: str
    proposal_id: str
    severity: float
    reason: Optional[str] = None


@dataclass
class Edge:
    from_id: str
    to_id: str
    trust: float
    rivalry: float
    betrayal_prob: float


@dataclass
class DataQualityReport:
    rejected_reps: list[tuple[str, str]] = field(default_factory=list)
    rejected_proposals: list[tuple[str, str]] = field(default_factory=list)
    rejected_objections: list[tuple[str, str]] = field(default_factory=list)
    rejected_edges: list[tuple[str, str]] = field(default_factory=list)
    normalized_ids: dict[str, str] = field(default_factory=dict)
    deduped: list[tuple[str, str]] = field(default_factory=list)
    clamped_values: list[tuple[str, str, str]] = field(default_factory=list)


@dataclass
class CleanedData:
    reps: list[Rep]
    proposals: list[Proposal]
    objections: list[Objection]
    edges: list[Edge]
    quality_report: DataQualityReport


@dataclass
class RepTrace:
    rep_id: str
    status: str
    metrics: dict[str, float] = field(default_factory=dict)
    rejections: list[str] = field(default_factory=list)
    selected_for_alliance_with: list[str] = field(default_factory=list)


@dataclass
class ProposalTrace:
    proposal_id: str
    status: str
    metrics: dict[str, float] = field(default_factory=dict)
    rejection_reason: Optional[str] = None


@dataclass
class DecisionTrace:
    reps: list[RepTrace] = field(default_factory=list)
    proposals: list[ProposalTrace] = field(default_factory=list)
    thresholds: dict[str, float] = field(default_factory=dict)
    summary: dict[str, int] = field(default_factory=dict)


@dataclass
class ConsensusResult:
    final_agreement: dict[str, list[str]]
    alliances: list[list[str]]
    trace: DecisionTrace
