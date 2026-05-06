"""
OWNER: Teammate 1 (Data - Reps + Proposals)

Responsibilities:
- read all 4 raw files (parsing only - no cleaning logic here)
- clean reps:        normalize ids, coerce influence, clamp range, dedup
- clean proposals:   normalize ids, coerce priority, dedup, reject ghost sponsors
- orchestrate the full load_clean() that combines your output with Teammate 2's

Teammate 2 owns src/cleaner.py (objections + edges). You import their
functions in load_clean() and merge the quality reports.
"""

from __future__ import annotations

import json
from pathlib import Path

from src._helpers import normalize_id, safe_float
from src.cleaner import clean_edges, clean_objections
from src.schema import (
    CleanedData,
    DataQualityReport,
    Proposal,
    Rep,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


# ---------------------------------------------------------------------------
# raw parsing - just reads bytes off disk
# ---------------------------------------------------------------------------

def load_raw(data_dir: Path = DATA_DIR) -> dict:
    """Return raw lists/strings exactly as they exist on disk. No cleaning."""
    with open(data_dir / "representatives.json", "r", encoding="utf-8") as f:
        raw_reps = json.load(f)
    with open(data_dir / "proposals.json", "r", encoding="utf-8") as f:
        raw_props = json.load(f)
    with open(data_dir / "objections.json", "r", encoding="utf-8") as f:
        raw_objs = json.load(f)
    return {
        "reps": raw_reps,
        "proposals": raw_props,
        "objections": raw_objs,
        "csv_path": data_dir / "relations.csv",
    }


# ---------------------------------------------------------------------------
# YOUR WORK - reps
# ---------------------------------------------------------------------------

def clean_reps(raw_reps: list[dict]) -> tuple[list[Rep], DataQualityReport]:
    """
    Turn the raw representatives list into clean Rep objects.

    Invariants you must guarantee:
        - every Rep.id is normalized (lowercase + stripped)
        - no two Reps share an id (document your merge rule below)
        - every Rep.influence is a float in [0, 100]
            * "70" -> 70.0
            * null -> imputed or rep dropped (your choice, document)
            * 150  -> clamped to 100.0
        - rep is dropped if id is empty/missing

    Document your dedup rule in this docstring when you implement it.
    Examples in the dataset:
        - "REP_001" with influence 80 vs "rep_001" with influence 85 -> ?
        - " rep_004" with influence 60 vs "rep_004" with influence null -> ?

    Suggested rule (you can change): keep first occurrence, log the
    duplicate in report.deduped.
    """
    report = DataQualityReport()
    seen: dict[str, Rep] = {}

    for r in raw_reps:
        rid = normalize_id(r.get("id"))
        if not rid:
            report.rejected_reps.append((str(r.get("id")), "missing or empty id"))
            continue
        # TODO Teammate 1: replace this naive first-wins rule with a
        # documented merge strategy. Log every action in `report`.
        if rid in seen:
            report.deduped.append((rid, str(r.get("id"))))
            continue

        infl_raw = r.get("influence")
        infl = safe_float(infl_raw)
        if infl is None:
            # TODO: decide - drop the rep, or impute (mean? 50?). Document.
            infl = 0.0
            report.clamped_values.append((rid, "influence", "null -> 0"))
        elif infl < 0 or infl > 100:
            report.clamped_values.append((rid, "influence", f"{infl} -> clamped"))
            infl = max(0.0, min(100.0, infl))

        seen[rid] = Rep(
            id=rid,
            name=str(r.get("name", "")),
            faction=str(r.get("faction", "")),
            influence=infl,
            raw=r,
        )

    return list(seen.values()), report


# ---------------------------------------------------------------------------
# YOUR WORK - proposals
# ---------------------------------------------------------------------------

def clean_proposals(
    raw_proposals: list[dict],
    valid_rep_ids: set[str],
) -> tuple[list[Proposal], DataQualityReport]:
    """
    Turn the raw proposals list into clean Proposal objects.

    Invariants:
        - every Proposal.id is normalized
        - every Proposal.sponsor is normalized AND in valid_rep_ids
          (drop any proposal whose sponsor is a ghost)
        - every Proposal.priority is a float
        - duplicate proposal ids deduped (document your rule)

    Examples in the dataset:
        - prop_003 appears twice: priority 9.5 vs 7. Pick one, document.
        - prop_005 sponsored by rep_099 which doesn't exist -> drop.

    Suggested rule (you can change): for duplicates, keep the one with
    HIGHEST priority (assume revisions are softening, original is the
    real intent). Or keep first. Pick one, document, move on.
    """
    report = DataQualityReport()
    seen: dict[str, Proposal] = {}

    for p in raw_proposals:
        pid = normalize_id(p.get("id"))
        sponsor = normalize_id(p.get("sponsor"))
        if not pid:
            report.rejected_proposals.append((str(p.get("id")), "missing id"))
            continue
        if sponsor not in valid_rep_ids:
            report.rejected_proposals.append((pid, f"ghost sponsor {sponsor}"))
            continue

        priority = safe_float(p.get("priority"))
        if priority is None:
            report.rejected_proposals.append((pid, "non-numeric priority"))
            continue

        # TODO Teammate 1: replace this with your documented dedup rule.
        if pid in seen:
            report.deduped.append((pid, f"dup priority {priority}"))
            continue

        seen[pid] = Proposal(id=pid, title=str(p.get("title", "")),
                             sponsor=sponsor, priority=priority)

    return list(seen.values()), report


# ---------------------------------------------------------------------------
# orchestrator - combines your work with Teammate 2's
# ---------------------------------------------------------------------------

def _merge_reports(*reports: DataQualityReport) -> DataQualityReport:
    out = DataQualityReport()
    for r in reports:
        out.rejected_reps.extend(r.rejected_reps)
        out.rejected_proposals.extend(r.rejected_proposals)
        out.rejected_objections.extend(r.rejected_objections)
        out.rejected_edges.extend(r.rejected_edges)
        out.normalized_ids.update(r.normalized_ids)
        out.deduped.extend(r.deduped)
        out.clamped_values.extend(r.clamped_values)
    return out


def load_clean(data_dir: Path = DATA_DIR) -> CleanedData:
    """
    End-to-end: parse + clean + assemble. Track B consumes the result and
    is allowed to assume every invariant in ASSIGNMENTS.md.

    Pipeline:
        load_raw -> clean_reps -> clean_proposals
                                -> clean_objections (Teammate 2)
                                -> clean_edges      (Teammate 2)
        merge reports -> CleanedData
    """
    raw = load_raw(data_dir)

    reps, r_rep = clean_reps(raw["reps"])
    rep_ids = {r.id for r in reps}

    proposals, r_prop = clean_proposals(raw["proposals"], rep_ids)
    prop_ids = {p.id for p in proposals}

    objections, r_obj = clean_objections(raw["objections"], rep_ids, prop_ids)
    edges, r_edge = clean_edges(raw["csv_path"], rep_ids)

    return CleanedData(
        reps=reps,
        proposals=proposals,
        objections=objections,
        edges=edges,
        quality_report=_merge_reports(r_rep, r_prop, r_obj, r_edge),
    )
