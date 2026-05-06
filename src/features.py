"""
OWNER: Track B (Strategy)

Pure metric functions. No graph traversal, no decisions, no IO.
Each function takes primitives or simple containers and returns a number.
Each docstring contains the formula and the test it kills.

You implement these first. They're independently testable - you can
unit-test each one with two-line fixtures.
"""

from __future__ import annotations

from typing import Iterable

from src.schema import Edge, Objection, Rep


def relationship_score(trust: float, betrayal_prob: float) -> float:
    """
    relationship_score = (trust / 100) * (1 - betrayal_prob)

    Range [0, 1]. Multiplicative - high trust is meaningless if betrayal is high.
    Kills: Trojan Horse, False Friend at the metric level.

    >>> relationship_score(85, 0.05)  # strong alliance pair
    0.8075
    >>> relationship_score(20, 0.65)  # false friend pair
    0.07
    """
    raise NotImplementedError("Track B: implement relationship_score")


def reciprocity(score_ab: float, score_ba: float) -> float:
    """
    reciprocity(A, B) = min(relationship_score(A->B), relationship_score(B->A))

    Use min, not mean. The mean would let a strong one-way relationship mask a
    weak one and break False-Friend detection.
    """
    raise NotImplementedError("Track B: implement reciprocity")


def personal_betrayal_risk(rep_id: str, edges: Iterable[Edge]) -> float:
    """
    personal_betrayal_risk(v) = max over outgoing edges of betrayal_prob(v -> *)

    Use max, not mean. One high-betrayal target is enough to flag a Trojan.
    Returns 0.0 if rep has no outgoing edges.
    Kills: Trojan Horse.
    """
    raise NotImplementedError("Track B: implement personal_betrayal_risk")


def faction_loyalty(rep: Rep, all_reps: list[Rep], edges: Iterable[Edge]) -> float:
    """
    F = faction(v)
    peers = {u : faction(u) == F, u != v}
    faction_loyalty(v) = 1 - mean over u in peers of betrayal_prob(v -> u)

    If rep has no edges to faction peers, return 1.0 (no evidence either way).
    Range [0, 1]. Lower = more likely an infiltrator.
    Kills: Faction Infiltrator.
    """
    raise NotImplementedError("Track B: implement faction_loyalty")


def cascade_risk(rep_id: str, edges: list[Edge]) -> float:
    """
    cascade_risk(v) = max over 2-hop paths v -> u -> w of [
        relationship_score(v -> u) * betrayal_prob(u -> w)
    ]

    Returns 0.0 if no 2-hop paths exist.
    Range [0, 1]. Higher = more exposed to a downstream backstabber.
    Kills: Cascading Betrayal.
    """
    raise NotImplementedError("Track B: implement cascade_risk")


def objection_weight(proposal_id: str, objections: Iterable[Objection],
                     reps_by_id: dict[str, Rep]) -> float:
    """
    objection_weight(p) = sum over objectors r of [
        severity(r, p) * (influence(r) / 100)
    ]

    Range typically [0, 50]. Skips objectors not in reps_by_id (ghosts).
    """
    raise NotImplementedError("Track B: implement objection_weight")


def controversy(proposal_id: str, objections: Iterable[Objection],
                reps_by_id: dict[str, Rep]) -> float:
    """
    total_capacity = 10 * sum over r in V of (influence(r) / 100)
    controversy(p) = objection_weight(p) / total_capacity

    Range [0, 1]. Returns 0.0 if total_capacity is 0.
    """
    raise NotImplementedError("Track B: implement controversy")


def viability(priority: float, controversy_score: float) -> float:
    """
    viability(p) = priority * (1 - controversy)

    Range [0, 10]. The Poison-Pill killer:
    a priority-10 proposal with controversy 1.0 has viability 0.
    Kills: Poison Pill, Priority vs Objection, Faction War.
    """
    raise NotImplementedError("Track B: implement viability")
