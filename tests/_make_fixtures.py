"""
One-shot generator for the 18 hidden-scenario fixtures.

Run from repo root:
    python tests/_make_fixtures.py

Each scenario creates a folder under tests/fixtures/ containing:
    representatives.json
    proposals.json
    objections.json
    relations.csv
    expected.json    (target asserted by tests/test_scenarios.py)
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "fixtures"


def write_fixture(
    name: str,
    reps: list[dict],
    proposals: list[dict],
    objections: list[dict],
    relations: list[dict],
    expected: dict,
) -> None:
    out = ROOT / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "representatives.json").write_text(
        json.dumps(reps, indent=2), encoding="utf-8"
    )
    (out / "proposals.json").write_text(
        json.dumps(proposals, indent=2), encoding="utf-8"
    )
    (out / "objections.json").write_text(
        json.dumps(objections, indent=2), encoding="utf-8"
    )
    fields = ["from", "to", "trust", "rivalry", "betrayal_prob", "last_interaction"]
    with open(out / "relations.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in relations:
            full = {k: row.get(k, "") for k in fields}
            w.writerow(full)
    (out / "expected.json").write_text(
        json.dumps(expected, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Helpers for crafted edge sets
# ---------------------------------------------------------------------------

def edge(src, dst, trust, rivalry, bet, date="2024-10-01"):
    return {
        "from": src, "to": dst, "trust": trust, "rivalry": rivalry,
        "betrayal_prob": bet, "last_interaction": date,
    }


# ---------------------------------------------------------------------------
# 01 - Trojan Horse
# A rep with great metrics on the surface but a betrayal signal.
# ---------------------------------------------------------------------------

write_fixture(
    "01_trojan_horse",
    reps=[
        {"id": "rep_a", "name": "Anchor", "faction": "Progressives", "influence": 80},
        {"id": "rep_b", "name": "Backer", "faction": "Progressives", "influence": 75},
        {"id": "rep_t", "name": "Trojan",  "faction": "Progressives", "influence": 98},
    ],
    proposals=[
        {"id": "prop_1", "title": "Reform Bill", "sponsor": "rep_a", "priority": 8}
    ],
    objections=[],
    relations=[
        edge("rep_a", "rep_b", 80, 10, 0.05),
        edge("rep_b", "rep_a", 80, 10, 0.05),
        edge("rep_t", "rep_a", 90, 5,  0.95),
        edge("rep_t", "rep_b", 88, 5,  0.92),
        edge("rep_a", "rep_t", 70, 10, 0.05),
        edge("rep_b", "rep_t", 70, 10, 0.05),
    ],
    expected={"supporters_must_exclude": ["rep_t"]},
)


# ---------------------------------------------------------------------------
# 02 - Poison Pill
# Priority-10 proposal with universal severe objection.
# ---------------------------------------------------------------------------

write_fixture(
    "02_poison_pill",
    reps=[
        {"id": "rep_a", "name": "A", "faction": "X", "influence": 90},
        {"id": "rep_b", "name": "B", "faction": "X", "influence": 85},
        {"id": "rep_c", "name": "C", "faction": "Y", "influence": 80},
    ],
    proposals=[
        {"id": "prop_pill", "title": "Universally Hated Bill", "sponsor": "rep_a", "priority": 10},
        {"id": "prop_safe", "title": "Boring But Safe",        "sponsor": "rep_a", "priority": 6},
    ],
    objections=[
        {"rep_id": "rep_a", "proposal_id": "prop_pill", "severity": 10},
        {"rep_id": "rep_b", "proposal_id": "prop_pill", "severity": 10},
        {"rep_id": "rep_c", "proposal_id": "prop_pill", "severity": 10},
    ],
    relations=[
        edge("rep_a", "rep_b", 80, 10, 0.10),
        edge("rep_b", "rep_a", 80, 10, 0.10),
        edge("rep_a", "rep_c", 70, 15, 0.15),
        edge("rep_c", "rep_a", 65, 20, 0.15),
    ],
    expected={
        "proposals_must_exclude": ["prop_pill"],
        "proposals_must_include": ["prop_safe"],
    },
)


# ---------------------------------------------------------------------------
# 03 - False Friend
# A trusts B; B doesn't trust A back.
# ---------------------------------------------------------------------------

write_fixture(
    "03_false_friend",
    reps=[
        {"id": "rep_a", "name": "A", "faction": "X", "influence": 80},
        {"id": "rep_b", "name": "B", "faction": "X", "influence": 75},
    ],
    proposals=[
        {"id": "prop_x", "title": "Minor Bill", "sponsor": "rep_a", "priority": 6}
    ],
    objections=[],
    relations=[
        edge("rep_a", "rep_b", 95, 5,  0.05),
        edge("rep_b", "rep_a", 25, 40, 0.85),
    ],
    expected={"alliances_must_be_empty": True},
)


# ---------------------------------------------------------------------------
# 04 - Clear Alliance
# Both directions strong, low rivalry, low betrayal.
# ---------------------------------------------------------------------------

write_fixture(
    "04_clear_alliance",
    reps=[
        {"id": "rep_a", "name": "A", "faction": "X", "influence": 85},
        {"id": "rep_b", "name": "B", "faction": "X", "influence": 80},
    ],
    proposals=[
        {"id": "prop_x", "title": "Shared Bill", "sponsor": "rep_a", "priority": 7}
    ],
    objections=[],
    relations=[
        edge("rep_a", "rep_b", 90, 5, 0.03),
        edge("rep_b", "rep_a", 92, 5, 0.02),
    ],
    expected={"alliances_must_include": [["rep_a", "rep_b"]]},
)


# ---------------------------------------------------------------------------
# 05 - Faction War
# Two viable proposals; pick least-objected.
# ---------------------------------------------------------------------------

write_fixture(
    "05_faction_war",
    reps=[
        {"id": "rep_a", "name": "A", "faction": "Progressives",  "influence": 85},
        {"id": "rep_b", "name": "B", "faction": "Progressives",  "influence": 80},
        {"id": "rep_c", "name": "C", "faction": "Conservatives", "influence": 90},
        {"id": "rep_d", "name": "D", "faction": "Conservatives", "influence": 88},
        {"id": "rep_e", "name": "E", "faction": "Conservatives", "influence": 92},
    ],
    proposals=[
        # Higher priority but a unified Conservative bloc objects severely.
        # Coalition amplifier + controversy combine to crush its viability.
        {"id": "prop_divisive",  "title": "Divisive Bill",  "sponsor": "rep_a", "priority": 9},
        # Lower priority, near-zero objection - should beat divisive cleanly.
        {"id": "prop_consensus", "title": "Consensus Bill", "sponsor": "rep_b", "priority": 7},
    ],
    objections=[
        {"rep_id": "rep_c", "proposal_id": "prop_divisive", "severity": 10},
        {"rep_id": "rep_d", "proposal_id": "prop_divisive", "severity": 10},
        {"rep_id": "rep_e", "proposal_id": "prop_divisive", "severity": 10},
        {"rep_id": "rep_a", "proposal_id": "prop_consensus", "severity": 2},
    ],
    relations=[
        edge("rep_a", "rep_b", 85, 10, 0.05),
        edge("rep_b", "rep_a", 85, 10, 0.05),
        edge("rep_c", "rep_d", 80, 15, 0.10),
        edge("rep_d", "rep_c", 80, 15, 0.10),
        edge("rep_d", "rep_e", 78, 18, 0.10),
        edge("rep_e", "rep_d", 80, 15, 0.10),
    ],
    expected={
        "proposals_must_include": ["prop_consensus"],
        "proposals_must_exclude": ["prop_divisive"],
    },
)


# ---------------------------------------------------------------------------
# 06 - Priority vs Objection
# High priority but heavy objection -> low viability.
# ---------------------------------------------------------------------------

write_fixture(
    "06_priority_vs_objection",
    reps=[
        {"id": "rep_a", "name": "A", "faction": "X", "influence": 90},
        {"id": "rep_b", "name": "B", "faction": "X", "influence": 85},
        {"id": "rep_c", "name": "C", "faction": "Y", "influence": 80},
        {"id": "rep_d", "name": "D", "faction": "Y", "influence": 90},
    ],
    proposals=[
        {"id": "prop_high",   "title": "High-Priority Doomed", "sponsor": "rep_a", "priority": 10},
        {"id": "prop_modest", "title": "Modest But Clean",     "sponsor": "rep_b", "priority": 5},
    ],
    objections=[
        {"rep_id": "rep_b", "proposal_id": "prop_high", "severity": 9},
        {"rep_id": "rep_c", "proposal_id": "prop_high", "severity": 9},
        {"rep_id": "rep_d", "proposal_id": "prop_high", "severity": 10},
    ],
    relations=[
        edge("rep_a", "rep_b", 70, 15, 0.10),
        edge("rep_b", "rep_a", 70, 15, 0.10),
        edge("rep_c", "rep_d", 75, 10, 0.10),
        edge("rep_d", "rep_c", 75, 10, 0.10),
    ],
    expected={
        "proposals_must_include": ["prop_modest"],
        "proposals_must_exclude": ["prop_high"],
    },
)


# ---------------------------------------------------------------------------
# 07 - Supporter Coherence
# Severe objector cannot be a supporter.
# ---------------------------------------------------------------------------

write_fixture(
    "07_supporter_coherence",
    reps=[
        {"id": "rep_a", "name": "A", "faction": "X", "influence": 80},
        {"id": "rep_b", "name": "B", "faction": "X", "influence": 70},
        {"id": "rep_c", "name": "C", "faction": "X", "influence": 90},
    ],
    proposals=[
        {"id": "prop_x", "title": "Bill", "sponsor": "rep_a", "priority": 8}
    ],
    objections=[
        {"rep_id": "rep_b", "proposal_id": "prop_x", "severity": 8},
    ],
    relations=[
        edge("rep_a", "rep_b", 70, 15, 0.10),
        edge("rep_b", "rep_a", 70, 15, 0.10),
        edge("rep_a", "rep_c", 75, 10, 0.10),
        edge("rep_c", "rep_a", 75, 10, 0.10),
    ],
    expected={
        "proposals_must_include": ["prop_x"],
        "supporters_must_exclude": ["rep_b"],
    },
)


# ---------------------------------------------------------------------------
# 08 - Faction Infiltrator
# Same faction but high in-faction betrayal.
# ---------------------------------------------------------------------------

write_fixture(
    "08_faction_infiltrator",
    reps=[
        {"id": "rep_a",   "name": "A",   "faction": "Progressives", "influence": 80},
        {"id": "rep_b",   "name": "B",   "faction": "Progressives", "influence": 75},
        {"id": "rep_spy", "name": "Spy", "faction": "Progressives", "influence": 85},
    ],
    proposals=[
        {"id": "prop_p", "title": "Progressive Bill", "sponsor": "rep_a", "priority": 8}
    ],
    objections=[],
    relations=[
        edge("rep_a", "rep_b", 85, 10, 0.05),
        edge("rep_b", "rep_a", 85, 10, 0.05),
        # Infiltrator's outgoing trust looks fine but betrayal toward
        # same-faction members is high.
        edge("rep_spy", "rep_a", 60, 30, 0.85),
        edge("rep_spy", "rep_b", 55, 30, 0.90),
        edge("rep_a", "rep_spy", 50, 40, 0.20),
        edge("rep_b", "rep_spy", 50, 40, 0.20),
    ],
    expected={"supporters_must_exclude": ["rep_spy"]},
)


# ---------------------------------------------------------------------------
# 09 - Cascading Betrayal
# Trust chain with a Trojan endpoint.
# ---------------------------------------------------------------------------

write_fixture(
    "09_cascading_betrayal",
    reps=[
        {"id": "rep_a", "name": "A", "faction": "X", "influence": 80},
        {"id": "rep_b", "name": "B", "faction": "X", "influence": 75},
        {"id": "rep_c", "name": "C (Trojan endpoint)", "faction": "X", "influence": 90},
    ],
    proposals=[
        {"id": "prop_x", "title": "Bill", "sponsor": "rep_a", "priority": 8}
    ],
    objections=[],
    relations=[
        # A trusts B, B trusts C, but C has Trojan-grade betrayal toward both.
        edge("rep_a", "rep_b", 90, 5,  0.05),
        edge("rep_b", "rep_a", 90, 5,  0.05),
        edge("rep_b", "rep_c", 85, 5,  0.10),
        edge("rep_c", "rep_b", 80, 5,  0.95),
        edge("rep_c", "rep_a", 80, 5,  0.92),
        edge("rep_a", "rep_c", 60, 10, 0.10),
    ],
    expected={"supporters_must_exclude": ["rep_c"]},
)


# ---------------------------------------------------------------------------
# 10 - Alliance Hack
# Stable alliance survives a high-rivalry disruptor.
# ---------------------------------------------------------------------------

write_fixture(
    "10_alliance_hack",
    reps=[
        {"id": "rep_a", "name": "A", "faction": "X", "influence": 85},
        {"id": "rep_b", "name": "B", "faction": "X", "influence": 80},
        {"id": "rep_d", "name": "Disruptor", "faction": "Z", "influence": 75},
    ],
    proposals=[
        {"id": "prop_x", "title": "Bill", "sponsor": "rep_a", "priority": 7}
    ],
    objections=[],
    relations=[
        edge("rep_a", "rep_b", 90, 5,  0.03),
        edge("rep_b", "rep_a", 92, 5,  0.02),
        # Disruptor declares high rivalry against the alliance pair.
        edge("rep_d", "rep_a", 10, 95, 0.30),
        edge("rep_d", "rep_b", 10, 95, 0.30),
        edge("rep_a", "rep_d", 20, 80, 0.30),
        edge("rep_b", "rep_d", 20, 80, 0.30),
    ],
    expected={"alliances_must_include": [["rep_a", "rep_b"]]},
)


# ---------------------------------------------------------------------------
# 11 - Complete Rivalry
# Every pair is mutually hostile.
# ---------------------------------------------------------------------------

write_fixture(
    "11_complete_rivalry",
    reps=[
        {"id": "rep_a", "name": "A", "faction": "X", "influence": 80},
        {"id": "rep_b", "name": "B", "faction": "Y", "influence": 75},
        {"id": "rep_c", "name": "C", "faction": "Z", "influence": 70},
    ],
    proposals=[
        {"id": "prop_x", "title": "Bill", "sponsor": "rep_a", "priority": 6}
    ],
    objections=[],
    relations=[
        edge("rep_a", "rep_b", 15, 90, 0.40),
        edge("rep_b", "rep_a", 10, 95, 0.45),
        edge("rep_a", "rep_c", 20, 85, 0.40),
        edge("rep_c", "rep_a", 15, 88, 0.45),
        edge("rep_b", "rep_c", 10, 92, 0.40),
        edge("rep_c", "rep_b", 12, 90, 0.45),
    ],
    expected={"alliances_must_be_empty": True},
)


# ---------------------------------------------------------------------------
# 12 - Ghost Sponsor
# Proposal with non-existent sponsor must be dropped.
# ---------------------------------------------------------------------------

write_fixture(
    "12_ghost_sponsor",
    reps=[
        {"id": "rep_a", "name": "A", "faction": "X", "influence": 80},
        {"id": "rep_b", "name": "B", "faction": "X", "influence": 75},
    ],
    proposals=[
        {"id": "prop_real",  "title": "Real Bill",  "sponsor": "rep_a",  "priority": 7},
        {"id": "prop_ghost", "title": "Ghost Bill", "sponsor": "rep_999", "priority": 9},
    ],
    objections=[],
    relations=[
        edge("rep_a", "rep_b", 80, 10, 0.05),
        edge("rep_b", "rep_a", 80, 10, 0.05),
    ],
    expected={
        "proposals_must_include": ["prop_real"],
        "proposals_must_exclude": ["prop_ghost"],
    },
)


# ---------------------------------------------------------------------------
# 13 - Minimum Viable
# 1 valid rep, 1 valid proposal. No edges, no objections.
# ---------------------------------------------------------------------------

write_fixture(
    "13_minimum_viable",
    reps=[
        {"id": "rep_solo", "name": "Solo", "faction": "X", "influence": 60}
    ],
    proposals=[
        {"id": "prop_solo", "title": "Lonely Bill", "sponsor": "rep_solo", "priority": 5}
    ],
    objections=[],
    relations=[],
    expected={
        "proposals_must_include": ["prop_solo"],
        "supporters_must_include": ["rep_solo"],
    },
)


# ---------------------------------------------------------------------------
# 14 - ID Normalization
# Mixed-case and whitespace IDs across files.
# ---------------------------------------------------------------------------

write_fixture(
    "14_id_normalization",
    reps=[
        {"id": "REP_001", "name": "Capitalized", "faction": "X", "influence": 80},
        {"id": "rep_001", "name": "Lowercase",   "faction": "X", "influence": 85},
        {"id": " rep_002 ", "name": "Whitespace", "faction": "X", "influence": 75},
    ],
    proposals=[
        # Proposal sponsor uses the uppercase form
        {"id": "PROP_X", "title": "Bill", "sponsor": "REP_001", "priority": 7}
    ],
    objections=[
        # Objection rep uses whitespace-padded form
        {"rep_id": " rep_002 ", "proposal_id": "PROP_X", "severity": 3}
    ],
    relations=[
        # Use yet another casing for the edges
        {"from": "REP_001", "to": " rep_002 ", "trust": 80, "rivalry": 10,
         "betrayal_prob": 0.10, "last_interaction": "2024-09-01"},
        {"from": "rep_002", "to": "rep_001", "trust": 80, "rivalry": 10,
         "betrayal_prob": 0.10, "last_interaction": "2024-09-01"},
    ],
    # We just need the engine to NOT crash and to produce SOME proposal.
    expected={"proposals_must_include": ["prop_x"]},
)


# ---------------------------------------------------------------------------
# 15 - Duplicate Proposals
# Same id appears twice with different priorities.
# ---------------------------------------------------------------------------

write_fixture(
    "15_duplicate_proposals",
    reps=[
        {"id": "rep_a", "name": "A", "faction": "X", "influence": 80}
    ],
    proposals=[
        {"id": "prop_dup", "title": "Original",  "sponsor": "rep_a", "priority": 9.5},
        {"id": "prop_dup", "title": "Revision",  "sponsor": "rep_a", "priority": 6.0},
    ],
    objections=[],
    relations=[],
    # We expect prop_dup selected (highest-priority dedup keeps 9.5)
    # and only ONCE in the output (duplicate handled).
    expected={"proposals_must_include": ["prop_dup"]},
)


# ---------------------------------------------------------------------------
# 16 - Null Influence
# Rep with influence=null must not crash.
# ---------------------------------------------------------------------------

write_fixture(
    "16_null_influence",
    reps=[
        {"id": "rep_a", "name": "A", "faction": "X", "influence": 80},
        {"id": "rep_n", "name": "Null", "faction": "X", "influence": None},
        {"id": "rep_b", "name": "B", "faction": "X", "influence": 70},
    ],
    proposals=[
        {"id": "prop_x", "title": "Bill", "sponsor": "rep_a", "priority": 7}
    ],
    objections=[],
    relations=[
        edge("rep_a", "rep_b", 80, 10, 0.10),
        edge("rep_b", "rep_a", 80, 10, 0.10),
    ],
    expected={"proposals_must_include": ["prop_x"]},
)


# ---------------------------------------------------------------------------
# 17 - Scale Correctness
# 50 reps, 30 proposals, must still produce sensible output.
# ---------------------------------------------------------------------------

random.seed(7)
N_REPS, N_PROPS = 50, 30
factions = ["Progressives", "Moderates", "Conservatives", "Independents"]
big_reps = [
    {
        "id": f"rep_{i:03d}",
        "name": f"Rep {i}",
        "faction": random.choice(factions),
        "influence": random.randint(40, 95),
    }
    for i in range(N_REPS)
]
# Anchor: ensure at least one obvious Trojan and one obvious clear-alliance pair
big_reps[0]["influence"] = 92
big_reps[1]["influence"] = 88

big_proposals = [
    {
        "id": f"prop_{i:03d}",
        "title": f"Bill {i}",
        "sponsor": f"rep_{random.randint(0, N_REPS - 1):03d}",
        "priority": round(random.uniform(3, 10), 1),
    }
    for i in range(N_PROPS)
]
big_objections = []
for _ in range(80):
    rid = f"rep_{random.randint(0, N_REPS - 1):03d}"
    pid = f"prop_{random.randint(0, N_PROPS - 1):03d}"
    big_objections.append(
        {"rep_id": rid, "proposal_id": pid, "severity": random.randint(1, 9)}
    )
big_edges = []
for _ in range(180):
    a = random.randint(0, N_REPS - 1)
    b = random.randint(0, N_REPS - 1)
    if a == b:
        continue
    big_edges.append(edge(
        f"rep_{a:03d}", f"rep_{b:03d}",
        random.randint(20, 95),
        random.randint(0, 80),
        round(random.uniform(0.0, 0.6), 2),
    ))
# Plant the clear alliance
big_edges.extend([
    edge("rep_000", "rep_001", 92, 5, 0.03),
    edge("rep_001", "rep_000", 92, 5, 0.02),
])

write_fixture(
    "17_scale_correctness",
    reps=big_reps,
    proposals=big_proposals,
    objections=big_objections,
    relations=big_edges,
    expected={"alliances_must_include": [["rep_000", "rep_001"]]},
)


# ---------------------------------------------------------------------------
# 18 - Dirty CSV
# Bad rows must not destroy good rows. Sample also includes a duplicate.
# ---------------------------------------------------------------------------

write_fixture(
    "18_dirty_csv",
    reps=[
        {"id": "rep_a", "name": "A", "faction": "X", "influence": 80},
        {"id": "rep_b", "name": "B", "faction": "X", "influence": 75},
        {"id": "rep_c", "name": "C", "faction": "X", "influence": 70},
    ],
    proposals=[
        {"id": "prop_x", "title": "Bill", "sponsor": "rep_a", "priority": 7}
    ],
    objections=[],
    relations=[
        # Good rows: alliance edges, both directions.
        edge("rep_a", "rep_b", 90, 5, 0.03, "2024-10-01"),
        edge("rep_b", "rep_a", 91, 5, 0.04, "2024-09-15"),
        # Bad row: trust empty. Involves rep_c so it can't poison the alliance.
        {"from": "rep_c", "to": "rep_a", "trust": "", "rivalry": 5,
         "betrayal_prob": 0.05, "last_interaction": "2024-10-01"},
        # Salvageable row: rivalry "high" mapped via RIVALRY_WORD_MAP.
        {"from": "rep_c", "to": "rep_b", "trust": 60, "rivalry": "high",
         "betrayal_prob": 0.20, "last_interaction": "2024-09-01"},
        # Bad row: betrayal_prob > 1, clamped to 1.0. Involves rep_c only.
        edge("rep_c", "rep_a", 50, 30, 1.5),
        # Bad row: ghost endpoint.
        {"from": "rep_a", "to": "rep_999", "trust": 50, "rivalry": 30,
         "betrayal_prob": 0.50, "last_interaction": "2024-09-01"},
        # Exact-duplicate row of an earlier good edge.
        edge("rep_a", "rep_b", 90, 5, 0.03, "2024-10-01"),
    ],
    # Despite the bad rows, the alliance between rep_a and rep_b survives.
    expected={"alliances_must_include": [["rep_a", "rep_b"]]},
)


print(f"Wrote 18 fixtures under {ROOT}")
