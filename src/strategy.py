"""
OWNER: Track B (Strategy)

Decision logic. Each function consumes the cleaned data plus the graph,
emits both a result and DecisionTrace entries.

Functions are independent and testable. consensus.py orchestrates them.
"""

from __future__ import annotations

from src.graph import TrustGraph
from src.schema import (
    CleanedData,
    Proposal,
    ProposalTrace,
    Rep,
    RepTrace,
)


def filter_reps(
    data: CleanedData,
    graph: TrustGraph,
) -> tuple[list[Rep], list[RepTrace]]:
    """
    Apply the Trojan Horse + Faction Infiltrator filters.
    Cascade Risk is applied later, at supporter selection.

    Returns:
        accepted_reps, traces (one trace per rep regardless of decision)

    Reject if:
        personal_betrayal_risk(v) >= TAU_BETRAY  -> "Trojan Horse"
        faction_loyalty(v)        <  TAU_LOYALTY -> "Faction Infiltrator"
        influence(v) <= 0                        -> "Insufficient influence"
    """
    raise NotImplementedError("Track B: implement filter_reps")


def detect_alliances(
    accepted: list[Rep],
    graph: TrustGraph,
) -> list[list[str]]:
    """
    For every pair of accepted reps:
        if reciprocity(A, B) >= TAU_ALLIANCE
        and max(rivalry(A->B), rivalry(B->A)) <= TAU_RIVALRY:
            include canonical_sort([A.id, B.id])

    Returns sorted, deterministic list of pairs.
    Empty list if no pair qualifies (Complete Rivalry test).
    """
    raise NotImplementedError("Track B: implement detect_alliances")


def score_proposals(
    data: CleanedData,
    accepted_reps: list[Rep],
) -> list[ProposalTrace]:
    """
    For each proposal, compute objection_weight, controversy, viability.
    Return a ProposalTrace per proposal.
    Proposals with sponsors not in accepted_reps are still scored but
    flagged for rejection by select_proposals.
    """
    raise NotImplementedError("Track B: implement score_proposals")


def select_proposals(
    proposals: list[Proposal],
    traces: list[ProposalTrace],
    accepted_rep_ids: set[str],
) -> list[Proposal]:
    """
    Greedy under TAU_BUDGET, capped at K_MAX_PROPOSALS.

    1. Drop proposals whose sponsor not in accepted_rep_ids.
    2. Drop proposals with viability < TAU_VIABILITY.
    3. Sort by viability desc.
    4. Pick while cumulative objection_weight <= TAU_BUDGET and len < K_MAX.
    5. Minimum-Viable safety: if nothing picked but viable list is nonempty,
       pick the top one anyway (pass Minimum Viable test).
    """
    raise NotImplementedError("Track B: implement select_proposals")


def select_supporters(
    accepted_reps: list[Rep],
    selected: list[Proposal],
    data: CleanedData,
    graph: TrustGraph,
) -> list[Rep]:
    """
    Supporter Coherence + Cascade safety.

    Hard filters:
    - Cannot have objected to ANY selected proposal at severity >= TAU_OBJ_BLOCK
    - cascade_risk(v) < TAU_CASCADE
    - Already passed filter_reps (Trojan + Infiltrator)

    Ranking:
    - Sponsors of selected proposals first (if they pass filters)
    - Then by influence * faction_loyalty desc
    - Cap at S_MAX_SUPPORTERS
    - Minimum-Viable safety: if no supporter qualifies but accepted_reps is
      nonempty, return the top accepted rep.
    """
    raise NotImplementedError("Track B: implement select_supporters")
