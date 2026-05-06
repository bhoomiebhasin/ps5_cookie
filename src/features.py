"""
OWNER: Anirudh (Strategy)

Pure metric functions. No graph traversal, no decisions, no IO.
Every function is independently testable and used by src/strategy.py.

These are the CANONICAL metrics. Layered enhancements (coalition
concentration, supporter scoring, etc.) live in src/strategy.py where
decisions are made; features.py stays a clean reference library.
"""

from __future__ import annotations

from typing import Iterable

from src.schema import Edge, Objection, Rep


# ---------------------------------------------------------------------------
# Edge-level metrics
# ---------------------------------------------------------------------------

def relationship_score(trust: float, betrayal_prob: float) -> float:
    """
    relationship_score = (trust / 100) * (1 - betrayal_prob)

    Range [0, 1]. Multiplicative, so high trust is meaningless if betrayal
    is also high. This is the foundation that kills Trojan Horse and
    False Friend at the metric level.

    >>> round(relationship_score(85, 0.05), 4)
    0.8075
    >>> round(relationship_score(20, 0.65), 4)
    0.07
    >>> round(relationship_score(90, 0.02), 4)
    0.882
    """
    return (trust / 100.0) * (1.0 - betrayal_prob)


def reciprocity(score_ab: float, score_ba: float) -> float:
    """
    reciprocity(A, B) = min(relationship_score(A->B), relationship_score(B->A))

    `min` is critical. `mean` would let a strong one-way relationship mask a
    weak return direction and break False-Friend detection.

    >>> reciprocity(0.85, 0.10)
    0.1
    >>> reciprocity(0.85, 0.85)
    0.85
    """
    return min(score_ab, score_ba)


# ---------------------------------------------------------------------------
# Per-rep metrics
# ---------------------------------------------------------------------------

def personal_betrayal_risk(rep_id: str, edges: Iterable[Edge]) -> float:
    """
    Trust-weighted maximum betrayal probability across outgoing edges.

        risk(v) = max over outgoing edges (v -> u) of:
                    betrayal_prob(v -> u) * (0.7 + 0.3 * trust(v -> u) / 100)

    Range [0, 1]. The (0.7 + 0.3 * trust/100) weight is in [0.7, 1.0]:
      - betraying a high-trust ally (trust=100) counts at full weight 1.0
      - betraying a low-trust enemy (trust=0) counts at weight 0.7

    Why trust-weighted: betraying someone you already distrust is just
    consistent rivalry, not a Trojan signal. A rep with `betrayal=0.65,
    trust=20` toward an enemy gets risk 0.494 (passes filter), while a
    rep with `betrayal=0.65, trust=85` toward a supposed ally gets risk
    0.616 (Trojan flagged). Naive `max(betrayal)` confuses the two.

    Returns 0.0 if rep has no outgoing edges (no evidence of risk).
    `max` not `mean`: one strong betrayal signal is enough.

    Kills: Trojan Horse (sharper than naive max-betrayal).
    """
    outgoing = [e for e in edges if e.from_id == rep_id]
    if not outgoing:
        return 0.0
    return max(
        e.betrayal_prob * (0.7 + 0.3 * e.trust / 100.0)
        for e in outgoing
    )


def faction_loyalty(rep: Rep, all_reps: list[Rep], edges: Iterable[Edge]) -> float:
    """
    F = faction(v)
    peers = {u in V : faction(u) == F, u != v}
    faction_loyalty(v) = 1 - mean over u in peers of betrayal_prob(v -> u)
                          (mean only over peers that v has an edge to)

    If rep has no edges to faction peers, return 1.0 (no evidence either
    way - innocent until proven guilty).

    Range [0, 1]. Lower = more likely an infiltrator.
    Kills: Faction Infiltrator.
    """
    peer_ids = {r.id for r in all_reps if r.faction == rep.faction and r.id != rep.id}
    if not peer_ids:
        return 1.0
    in_faction = [e for e in edges if e.from_id == rep.id and e.to_id in peer_ids]
    if not in_faction:
        return 1.0
    mean_betrayal = sum(e.betrayal_prob for e in in_faction) / len(in_faction)
    return 1.0 - mean_betrayal


def cascade_risk(
    rep_id: str,
    edges: list[Edge],
    valid_intermediates: set[str] | None = None,
) -> float:
    """
    cascade_risk(v) = max over 2-hop paths v -> u -> w of [
        relationship_score(v -> u) * betrayal_prob(u -> w)
    ]
    where w != v (a backstabber TWO steps out, not v itself).

    If `valid_intermediates` is given, only chains where u is in that set
    are counted. This is critical for select_supporters: a chain through
    an already-rejected Trojan never actually materializes, so it
    shouldn't disqualify v. Calling with valid_intermediates = set of
    accepted reps gives the realistic exposure.

    Range [0, 1]. Higher = more exposed to a downstream backstabber.

    Interpretation: if v strongly trusts u (high score), and u trusts a
    backstabber w (high betrayal), then bringing v in pulls the chain
    that leads to w. Excluding v from supporters protects coherence.

    Kills: Cascading Betrayal.
    """
    outgoing = [e for e in edges if e.from_id == rep_id]
    if not outgoing:
        return 0.0
    max_risk = 0.0
    for first in outgoing:
        if valid_intermediates is not None and first.to_id not in valid_intermediates:
            continue
        first_score = relationship_score(first.trust, first.betrayal_prob)
        if first_score == 0.0:
            continue
        for second in edges:
            if second.from_id != first.to_id:
                continue
            if second.to_id == rep_id:
                continue
            risk = first_score * second.betrayal_prob
            if risk > max_risk:
                max_risk = risk
    return max_risk


# ---------------------------------------------------------------------------
# Per-proposal metrics
# ---------------------------------------------------------------------------

def objection_weight(
    proposal_id: str,
    objections: Iterable[Objection],
    reps_by_id: dict[str, Rep],
) -> float:
    """
    objection_weight(p) = sum over objectors r of [
        severity(r, p) * (influence(r) / 100)
    ]

    Range typically [0, 50]. Skips objectors not in reps_by_id (ghosts).
    A high-influence rep's severe objection is far more damaging than a
    fringe rep's tantrum, and the math reflects that.
    """
    total = 0.0
    for o in objections:
        if o.proposal_id != proposal_id:
            continue
        rep = reps_by_id.get(o.rep_id)
        if rep is None:
            continue
        total += o.severity * (rep.influence / 100.0)
    return total


def controversy(
    proposal_id: str,
    objections: Iterable[Objection],
    reps_by_id: dict[str, Rep],
) -> float:
    """
    Normalized controversy in [0, 1].

    total_capacity = 10 * sum over r in V of (influence(r) / 100)
    controversy(p) = min(1.0, objection_weight(p) / total_capacity)

    Capacity = "what would happen if every rep objected at max severity".
    Returns 0.0 if total capacity is 0 (degenerate input).
    """
    weight = objection_weight(proposal_id, objections, reps_by_id)
    capacity = 10.0 * sum(r.influence / 100.0 for r in reps_by_id.values())
    if capacity == 0:
        return 0.0
    return min(1.0, weight / capacity)


def viability(priority: float, controversy_score: float) -> float:
    """
    viability(p) = priority * (1 - controversy)

    Range [0, 10]. The Poison-Pill killer:
    a priority-10 proposal with controversy 1.0 has viability 0.

    Kills: Poison Pill, Priority vs Objection, Faction War.

    >>> viability(10, 1.0)
    0.0
    >>> viability(8, 0.0)
    8.0
    >>> viability(10, 0.5)
    5.0
    """
    return priority * (1.0 - controversy_score)
