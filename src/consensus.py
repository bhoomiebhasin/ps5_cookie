"""
OWNER: Anirudh (Strategy)

Top-level orchestrator. Eight-stage pipeline that turns CleanedData into a
ConsensusResult (final agreement, alliances, decision trace).
"""

from __future__ import annotations

from src import thresholds
from src.graph import build_graph
from src.schema import CleanedData, ConsensusResult, DecisionTrace
from src.strategy import (
    detect_alliances,
    filter_reps,
    score_proposals,
    select_proposals,
    select_supporters,
)


def run_consensus(data: CleanedData) -> ConsensusResult:
    """
    Stages:
        1. build directed trust graph
        2. compute per-rep metrics (inside filter_reps)
        3. filter Trojans + Infiltrators
        4. score proposals (canonical + coalition + sponsor adjustments)
        5. select proposals (Pareto-optimal exhaustive search under budget)
        6. detect alliances (bidirectional reciprocity + low rivalry)
        7. select supporters (Coherence + Cascade + multiplicative score)
        8. assemble result + trace

    Returns a ConsensusResult on every input, including degenerate cases.
    """
    graph = build_graph(data.edges)

    accepted, rep_traces = filter_reps(data, graph)
    accepted_ids = {r.id for r in accepted}

    prop_traces = score_proposals(data, accepted)
    selected_props = select_proposals(
        data.proposals, prop_traces, accepted_ids,
        data.objections, accepted,
    )
    alliances = detect_alliances(accepted, graph)
    supporters = select_supporters(accepted, selected_props, data, graph)

    # Enrich rep traces with final status
    supporter_ids = {r.id for r in supporters}
    in_alliance: set[str] = set()
    for pair in alliances:
        in_alliance.update(pair)

    for trace in rep_traces:
        if trace.status == "rejected":
            continue
        if trace.rep_id in supporter_ids:
            trace.status = "supporter"
        elif trace.rep_id in in_alliance:
            trace.status = "alliance_only"
        else:
            trace.status = "unaligned"
        for pair in alliances:
            if trace.rep_id in pair:
                partner = pair[1] if pair[0] == trace.rep_id else pair[0]
                trace.selected_for_alliance_with.append(partner)

    summary = {
        "total_reps": len(data.reps),
        "accepted_reps": len(accepted),
        "rejected_reps": sum(1 for t in rep_traces if t.status == "rejected"),
        "supporters": len(supporters),
        "alliances": len(alliances),
        "total_proposals": len(data.proposals),
        "selected_proposals": len(selected_props),
        "rejected_proposals": sum(
            1 for t in prop_traces if t.status == "rejected"
        ),
    }

    trace = DecisionTrace(
        reps=rep_traces,
        proposals=prop_traces,
        thresholds=thresholds.as_dict(),
        summary=summary,
    )

    return ConsensusResult(
        final_agreement={
            "proposals": [p.id for p in selected_props],
            "supporting_reps": [r.id for r in supporters],
        },
        alliances=alliances,
        trace=trace,
    )
