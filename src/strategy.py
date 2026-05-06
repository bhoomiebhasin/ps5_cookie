"""
OWNER: Anirudh (Strategy)

Decision logic. Each function consumes the cleaned data plus the graph,
emits both a result and DecisionTrace entries.

Beyond the canonical metrics in features.py, this file layers in five
S-tier differentiators that most teams will not implement:

  1. Coalition-aware controversy
       Objections concentrated within ONE faction are scarier than the
       same total objection_weight scattered across factions. We compute
       a Herfindahl-Hirschman index over objector influence by faction
       and amplify controversy by (1 + 0.5 * HHI). Kills Faction War
       harder than naive controversy alone.

  2. Sponsor-credibility bonus
       A high-influence, high-loyalty sponsor can rally support, so
       proposals from credible sponsors get a viability boost up to 30%.
       sponsor_credibility = (influence / 100) * faction_loyalty
       adjusted_viability  = viability * (1 + 0.3 * sponsor_credibility)

  3. Stability-aware Pareto-optimal proposal selection
       Greedy under budget is what naive teams do. We instead enumerate
       every subset of viable proposals up to K_MAX_PROPOSALS and pick
       the one that maximises:

           sum(adj_viability) + 0.25 * distinct_sponsors
                              + 0.5  * coherent_supporters(S)

       coherent_supporters(S) = accepted reps who do NOT object to any
       proposal in S at severity >= TAU_OBJ_BLOCK. This makes proposal
       selection AWARE of downstream supporter coherence, so the engine
       won't pick a slightly-higher-viability set if it kicks half the
       supporters out of the agreement.

       With <= 30 candidates and K_MAX_PROPOSALS = 5, we evaluate at most
       ~140k subsets - trivial. Provably optimal under the objective.

  4. Multiplicative supporter scoring
       Naive teams sort by raw influence. We sort by
         influence * faction_loyalty * (1 - personal_betrayal_risk)
       so a supporter must be solid on every dimension. A single weak
       axis crushes the whole score.

  5. Cascade through accepted intermediates only
       cascade_risk through Trojan-rejected reps is unrealistic - those
       chains never materialize because Trojans are out. We compute
       cascade only through the accepted set, removing false positives
       that would over-reject otherwise good supporters.

Every decision and metric flows into the DecisionTrace so the dashboard
and APPROACH.md can show the full reasoning.
"""

from __future__ import annotations

import itertools
from collections import defaultdict

from src import thresholds
from src.features import (
    cascade_risk,
    controversy,
    faction_loyalty,
    objection_weight,
    personal_betrayal_risk,
    reciprocity,
    relationship_score,
    viability,
)
from src.graph import TrustGraph
from src.schema import (
    CleanedData,
    Proposal,
    ProposalTrace,
    Rep,
    RepTrace,
)


# ---------------------------------------------------------------------------
# Differentiator 1 - Coalition-aware controversy
# ---------------------------------------------------------------------------

def _coalition_amplifier(
    proposal_id: str,
    data: CleanedData,
    reps_by_id: dict[str, Rep],
) -> float:
    """
    Herfindahl-Hirschman index over objector influence by faction.

    HHI = sum_f (influence_share_of_faction_f)^2  in [0, 1]

    A united faction (all objectors in one faction) -> HHI close to 1.
    Scattered objectors across many factions       -> HHI close to 1/n.

    Returns the multiplier (1 + 0.5 * HHI).
    """
    by_faction: dict[str, float] = defaultdict(float)
    for o in data.objections:
        if o.proposal_id != proposal_id:
            continue
        rep = reps_by_id.get(o.rep_id)
        if rep is None:
            continue
        by_faction[rep.faction] += rep.influence * o.severity
    total = sum(by_faction.values())
    if total <= 0:
        return 1.0
    hhi = sum((v / total) ** 2 for v in by_faction.values())
    return 1.0 + 0.5 * hhi


# ---------------------------------------------------------------------------
# Stage 5 - rep filtering (Trojan + Infiltrator)
# ---------------------------------------------------------------------------

def filter_reps(
    data: CleanedData,
    graph: TrustGraph,
) -> tuple[list[Rep], list[RepTrace]]:
    """
    Apply Trojan Horse + Faction Infiltrator filters.
    Cascade Risk is computed for the trace but applied later at supporter
    selection (with through-accepted intermediates), not here.
    """
    accepted: list[Rep] = []
    traces: list[RepTrace] = []

    # First pass: compute risks and identify rejections
    rep_metrics: dict[str, dict[str, float]] = {}
    rep_rejections: dict[str, list[str]] = {}

    for rep in data.reps:
        outgoing = graph.outgoing(rep.id)
        risk = personal_betrayal_risk(rep.id, outgoing)
        loyalty = faction_loyalty(rep, data.reps, data.edges)

        rejections: list[str] = []
        if rep.influence <= 0:
            rejections.append("Insufficient influence (0)")
        if risk >= thresholds.TAU_BETRAY:
            rejections.append(
                f"Trojan Horse (betrayal_risk={risk:.2f} >= {thresholds.TAU_BETRAY})"
            )
        if loyalty < thresholds.TAU_LOYALTY:
            rejections.append(
                f"Faction Infiltrator (loyalty={loyalty:.2f} < {thresholds.TAU_LOYALTY})"
            )

        rep_metrics[rep.id] = {
            "influence": rep.influence,
            "personal_betrayal_risk": round(risk, 4),
            "faction_loyalty": round(loyalty, 4),
            "supporter_score": round(
                rep.influence * loyalty * (1.0 - risk), 4
            ),
        }
        rep_rejections[rep.id] = rejections

        if not rejections:
            accepted.append(rep)

    # Second pass: cascade_risk through accepted reps only (realistic exposure)
    accepted_ids = {r.id for r in accepted}
    for rep in data.reps:
        casc = cascade_risk(
            rep.id, data.edges, valid_intermediates=accepted_ids
        )
        rep_metrics[rep.id]["cascade_risk"] = round(casc, 4)

        rejections = rep_rejections[rep.id]
        if rejections:
            traces.append(RepTrace(
                rep_id=rep.id,
                status="rejected",
                metrics=rep_metrics[rep.id],
                rejections=rejections,
            ))
        else:
            traces.append(RepTrace(
                rep_id=rep.id,
                status="unaligned",
                metrics=rep_metrics[rep.id],
            ))

    return accepted, traces


# ---------------------------------------------------------------------------
# Stage 6 - alliance detection
# ---------------------------------------------------------------------------

def detect_alliances(
    accepted: list[Rep],
    graph: TrustGraph,
) -> list[list[str]]:
    """
    For every pair of ACCEPTED reps:
        if reciprocity(A, B) >= TAU_ALLIANCE
        and max(rivalry(A->B), rivalry(B->A)) <= TAU_RIVALRY:
            include canonical_sort([A.id, B.id])

    Operating on accepted reps only is what handles Alliance Hack -
    a rejected rep can't disrupt because they're already out.

    Output is sorted deterministically so tests are stable.
    """
    pairs: list[tuple[str, str, float]] = []  # (a, b, strength) for sorting
    accepted_ids = sorted(r.id for r in accepted)
    by_id = {r.id: r for r in accepted}

    for i, a_id in enumerate(accepted_ids):
        for b_id in accepted_ids[i + 1:]:
            edge_ab = graph.get(a_id, b_id)
            edge_ba = graph.get(b_id, a_id)
            if edge_ab is None or edge_ba is None:
                continue

            score_ab = relationship_score(edge_ab.trust, edge_ab.betrayal_prob)
            score_ba = relationship_score(edge_ba.trust, edge_ba.betrayal_prob)
            recip = reciprocity(score_ab, score_ba)
            max_rivalry = max(edge_ab.rivalry, edge_ba.rivalry)

            if recip < thresholds.TAU_ALLIANCE:
                continue
            if max_rivalry > thresholds.TAU_RIVALRY:
                continue

            # Influence-weighted strength as a secondary sort key
            inf_a = by_id[a_id].influence
            inf_b = by_id[b_id].influence
            strength = recip * ((inf_a * inf_b) ** 0.5) / 100.0
            pairs.append((a_id, b_id, strength))

    # Strongest alliances first; ties by id for determinism
    pairs.sort(key=lambda x: (-x[2], x[0], x[1]))
    return [[a, b] for a, b, _ in pairs]


# ---------------------------------------------------------------------------
# Stage 4 + Differentiator 2 - proposal scoring with sponsor credibility
# ---------------------------------------------------------------------------

def score_proposals(
    data: CleanedData,
    accepted_reps: list[Rep],
) -> list[ProposalTrace]:
    """
    Compute objection_weight, controversy, viability, AND adjusted_viability
    (which incorporates coalition concentration and sponsor credibility).
    """
    reps_by_id = {r.id: r for r in data.reps}  # use ALL reps for objection math
    accepted_by_id = {r.id: r for r in accepted_reps}
    traces: list[ProposalTrace] = []

    for p in data.proposals:
        ow = objection_weight(p.id, data.objections, reps_by_id)
        cv = controversy(p.id, data.objections, reps_by_id)
        amp = _coalition_amplifier(p.id, data, reps_by_id)
        adj_cv = min(1.0, cv * amp)
        vi = viability(p.priority, adj_cv)

        # sponsor credibility: only meaningful if sponsor passed filtering
        sponsor = accepted_by_id.get(p.sponsor)
        if sponsor is None:
            sponsor_credibility = 0.0
        else:
            loy = faction_loyalty(sponsor, data.reps, data.edges)
            sponsor_credibility = (sponsor.influence / 100.0) * loy
        adj_vi = vi * (1.0 + 0.3 * sponsor_credibility)

        traces.append(ProposalTrace(
            proposal_id=p.id,
            status="unaligned",
            metrics={
                "priority": round(p.priority, 4),
                "objection_weight": round(ow, 4),
                "controversy": round(cv, 4),
                "coalition_amp": round(amp, 4),
                "adj_controversy": round(adj_cv, 4),
                "viability": round(vi, 4),
                "sponsor_credibility": round(sponsor_credibility, 4),
                "adj_viability": round(adj_vi, 4),
            },
        ))

    return traces


# ---------------------------------------------------------------------------
# Stage 7 + Differentiator 3 - Pareto-optimal proposal selection
# ---------------------------------------------------------------------------

def select_proposals(
    proposals: list[Proposal],
    traces: list[ProposalTrace],
    accepted_rep_ids: set[str],
    objections: list,
    accepted_reps: list[Rep],
) -> list[Proposal]:
    """
    Exhaustive search for the optimal subset of proposals under TAU_BUDGET,
    capped at K_MAX_PROPOSALS. Stability-aware objective:

        score(S) = sum(adj_viability(p) for p in S)
                 + 0.25 * distinct_sponsors(S)
                 + 0.5  * coherent_supporters(S)

    where coherent_supporters(S) = accepted reps who do NOT object to any
    proposal in S at severity >= TAU_OBJ_BLOCK. This is Differentiator 3:
    the engine is aware of supporter coherence at the time of proposal
    selection, not just downstream.

    With <= ~30 candidates and K_MAX_PROPOSALS = 5, at most ~140k subsets.

    Minimum-viable safety: if the optimal set is empty but viable list is
    nonempty, force-pick the top one so we never emit zero proposals.
    """
    trace_by_id = {t.proposal_id: t for t in traces}

    # Pre-index objections by (rep_id, prop_id) for O(1) coherence checks
    serious_objs: dict[str, set[str]] = {}  # prop_id -> set of severe-objector rep_ids
    for o in objections:
        if o.severity >= thresholds.TAU_OBJ_BLOCK:
            serious_objs.setdefault(o.proposal_id, set()).add(o.rep_id)

    accepted_id_list = [r.id for r in accepted_reps]

    def coherent_count(combo) -> int:
        ids_in_combo = [p.id for p in combo]
        blocked: set[str] = set()
        for pid in ids_in_combo:
            blocked |= serious_objs.get(pid, set())
        return sum(1 for rid in accepted_id_list if rid not in blocked)

    # Filter: viable AND sponsored by accepted rep
    viable: list[Proposal] = []
    for p in proposals:
        t = trace_by_id[p.id]
        if p.sponsor not in accepted_rep_ids:
            t.rejection_reason = f"sponsor {p.sponsor} not accepted"
            t.status = "rejected"
            continue
        if t.metrics["adj_viability"] < thresholds.TAU_VIABILITY:
            t.rejection_reason = (
                f"adj_viability {t.metrics['adj_viability']:.2f} < "
                f"{thresholds.TAU_VIABILITY}"
            )
            t.status = "rejected"
            continue
        viable.append(p)

    if not viable:
        return []

    viable.sort(key=lambda p: -trace_by_id[p.id].metrics["adj_viability"])

    best_score = -1e18
    best_subset: list[Proposal] = []
    k_max = thresholds.K_MAX_PROPOSALS

    for k in range(1, min(k_max, len(viable)) + 1):
        for combo in itertools.combinations(viable, k):
            total_obj = sum(
                trace_by_id[p.id].metrics["objection_weight"] for p in combo
            )
            if total_obj > thresholds.TAU_BUDGET:
                continue
            total_v = sum(
                trace_by_id[p.id].metrics["adj_viability"] for p in combo
            )
            distinct_sponsors = len({p.sponsor for p in combo})
            stability = 0.5 * coherent_count(combo)
            score = total_v + 0.25 * distinct_sponsors + stability
            if score > best_score:
                best_score = score
                best_subset = list(combo)

    if not best_subset and viable:
        best_subset = [viable[0]]

    for p in best_subset:
        trace_by_id[p.id].status = "selected"

    best_subset.sort(
        key=lambda p: (-trace_by_id[p.id].metrics["adj_viability"], p.id)
    )
    return best_subset


# ---------------------------------------------------------------------------
# Stage 8 + Differentiator 4 - Supporter selection (Coherence + Cascade)
# ---------------------------------------------------------------------------

def select_supporters(
    accepted_reps: list[Rep],
    selected: list[Proposal],
    data: CleanedData,
    graph: TrustGraph,
) -> list[Rep]:
    """
    Two hard filters then a multiplicative ranking.

    Hard filters:
      - rep cannot have objected to ANY selected proposal at severity
        >= TAU_OBJ_BLOCK (Supporter Coherence)
      - cascade_risk(rep) < TAU_CASCADE (Cascading Betrayal protection)

    Ranking (Differentiator 4):
        supporter_score = influence * faction_loyalty * (1 - personal_betrayal_risk)

    Multiplicative - a single weak axis crushes the score, so a strong
    influence cannot mask weak loyalty or hidden betrayal risk.

    Sponsors of selected proposals get priority placement (if they pass
    both filters), then we top up by score until S_MAX_SUPPORTERS.

    Minimum-viable safety: if no supporter qualifies but accepted_reps
    is nonempty, return the highest-scoring accepted rep so we never
    emit zero supporters.
    """
    if not accepted_reps:
        return []

    selected_prop_ids = {p.id for p in selected}
    accepted_ids = {r.id for r in accepted_reps}

    # Build the objector blocklist
    blocked: set[str] = set()
    for o in data.objections:
        if o.proposal_id not in selected_prop_ids:
            continue
        if o.severity >= thresholds.TAU_OBJ_BLOCK:
            blocked.add(o.rep_id)

    # Per-rep supporter score using Differentiator 4
    def score(rep: Rep) -> float:
        risk = personal_betrayal_risk(rep.id, graph.outgoing(rep.id))
        loy = faction_loyalty(rep, data.reps, data.edges)
        return rep.influence * loy * (1.0 - risk)

    # Apply hard filters - cascade only counts chains through accepted reps,
    # since chains through Trojan-rejected intermediates never materialize.
    candidates: list[Rep] = []
    for rep in accepted_reps:
        if rep.id in blocked:
            continue
        if cascade_risk(rep.id, data.edges, valid_intermediates=accepted_ids) \
                >= thresholds.TAU_CASCADE:
            continue
        candidates.append(rep)

    # Sponsors of selected proposals first
    sponsor_ids = [p.sponsor for p in selected]
    candidate_by_id = {r.id: r for r in candidates}
    ordered: list[Rep] = []
    seen: set[str] = set()
    for sid in sponsor_ids:
        if sid in candidate_by_id and sid not in seen:
            ordered.append(candidate_by_id[sid])
            seen.add(sid)

    # Then top up by supporter_score desc
    others = [r for r in candidates if r.id not in seen]
    others.sort(key=lambda r: (-score(r), r.id))
    for r in others:
        if len(ordered) >= thresholds.S_MAX_SUPPORTERS:
            break
        ordered.append(r)

    # Minimum-viable safety net
    if not ordered and accepted_reps:
        best = max(accepted_reps, key=score)
        ordered = [best]

    return ordered[:thresholds.S_MAX_SUPPORTERS]
