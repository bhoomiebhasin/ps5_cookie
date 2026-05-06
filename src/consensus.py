"""
OWNER: Track B (Strategy)

Top-level orchestrator. Eight-stage pipeline that turns CleanedData into a
ConsensusResult (final agreement, alliances, decision trace).

Order matters - each stage depends on the previous.
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
        4. detect alliances among accepted reps
        5. score proposals
        6. select proposals (greedy under objection budget)
        7. select supporters (coherence + cascade safety)
        8. assemble result + trace

    Track B: this body is yours to fill. The function MUST return a
    ConsensusResult even on degenerate input.
    """
    graph = build_graph(data.edges)
    accepted, rep_traces = filter_reps(data, graph)
    accepted_ids = {r.id for r in accepted}

    alliances = detect_alliances(accepted, graph)
    prop_traces = score_proposals(data, accepted)
    selected_props = select_proposals(data.proposals, prop_traces, accepted_ids)
    supporters = select_supporters(accepted, selected_props, data, graph)

    trace = DecisionTrace(
        reps=rep_traces,
        proposals=prop_traces,
        thresholds=thresholds.as_dict(),
        summary={
            "accepted_reps": len(accepted),
            "rejected_reps": len(rep_traces) - len(accepted),
            "alliances": len(alliances),
            "selected_proposals": len(selected_props),
            "supporters": len(supporters),
        },
    )

    return ConsensusResult(
        final_agreement={
            "proposals": [p.id for p in selected_props],
            "supporting_reps": [r.id for r in supporters],
        },
        alliances=alliances,
        trace=trace,
    )
