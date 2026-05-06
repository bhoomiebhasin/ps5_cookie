"""
All tunable thresholds, with written justifications.

Each value MUST keep its docstring sentence. The dashboard surfaces these as
sliders, and APPROACH.md cites them. Changing a number without updating the
justification is a bug.
"""

TAU_BETRAY = 0.5
"""Trojan Horse cutoff. A rep with personal_betrayal_risk >= 0.5 betrays at
least half the time and is rejected as a supporter regardless of influence.
The brief's Trojan example uses betrayal=0.95; strong-alliance examples use
0.02-0.05. 0.5 cleanly separates them."""

TAU_ALLIANCE = 0.5
"""Bidirectional reciprocity required for alliance.
min(rel_score(A->B), rel_score(B->A)) >= 0.5 means both directions are at
least 50% reliable. Strong-alliance pair in sample data hits 0.808; false
friend hits 0.0."""

TAU_RIVALRY = 50.0
"""Rivalry score (0-100). Above the midpoint the relationship is more
adversarial than cooperative. Used to veto otherwise-qualified alliances."""

TAU_LOYALTY = 0.6
"""Faction Infiltrator cutoff. faction_loyalty < 0.6 means the rep's mean
betrayal probability against own-faction peers exceeds 0.4 - more enemy than
ally inside their own faction."""

TAU_CASCADE = 0.4
"""Cascading Betrayal cutoff. Max value of trust(v->u) * betrayal(u->w)
across two-hop paths. Allows mild secondary risk; above this the trust chain
leaks too much."""

TAU_VIABILITY = 3.0
"""Proposal viability cutoff (priority * (1 - controversy), 0-10 scale).
Below 3 means either low priority OR heavy controversy. Poison Pill killer."""

TAU_OBJ_BLOCK = 5.0
"""A supporter cannot have objected to a chosen proposal at this severity or
higher. Light-severity (<5) objections are tolerated as legitimate critique."""

TAU_BUDGET = 30.0
"""Cumulative objection_weight allowed across all selected proposals.
Prevents stacking multiple controversial proposals."""

K_MAX_PROPOSALS = 5
"""Cap on selected proposals."""

S_MAX_SUPPORTERS = 7
"""Cap on supporters."""


def as_dict() -> dict[str, float]:
    """Return all thresholds as a dict for the DecisionTrace and dashboard."""
    return {
        "TAU_BETRAY": TAU_BETRAY,
        "TAU_ALLIANCE": TAU_ALLIANCE,
        "TAU_RIVALRY": TAU_RIVALRY,
        "TAU_LOYALTY": TAU_LOYALTY,
        "TAU_CASCADE": TAU_CASCADE,
        "TAU_VIABILITY": TAU_VIABILITY,
        "TAU_OBJ_BLOCK": TAU_OBJ_BLOCK,
        "TAU_BUDGET": TAU_BUDGET,
        "K_MAX_PROPOSALS": float(K_MAX_PROPOSALS),
        "S_MAX_SUPPORTERS": float(S_MAX_SUPPORTERS),
    }
