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

    Invariants guaranteed:
        - every Rep.id is normalized (lowercase + stripped)
        - no two Reps share an id
        - every Rep.influence is a float in [0, 100]
            * "70"  -> 70.0
            * null  -> imputed with the mean of all other valid influences
            * 150   -> clamped to 100.0
        - rep is dropped if id is empty/missing

    Dedup rule (KEEP HIGHEST INFLUENCE):
        When two raw records normalize to the same id (e.g. "REP_001" and
        "rep_001"), we keep whichever has the higher influence value and
        discard the other. Rationale: the higher value reflects the more
        capable/recently-updated record; keeping the lower would under-weight
        that representative in scoring.
        Example outcomes on sample data:
            - "REP_001" (80) vs "rep_001" (85) -> keep rep_001 (85)
            - " rep_004" (60) vs "rep_004" (null->imputed) -> keep rep_004 (60)

    Null influence rule (MEAN IMPUTATION):
        Rather than dropping the rep or assigning an arbitrary constant, we
        impute using the mean of all other reps' valid, clamped influences.
        This is statistically neutral and avoids biasing the rep toward
        either extreme. The imputed value is logged in report.clamped_values.
    """
    report = DataQualityReport()

    # --- Pass 1: collect all valid (non-null) clamped influence values
    #     so we can compute the mean for null imputation.
    valid_influences: list[float] = []
    for r in raw_reps:
        rid = normalize_id(r.get("id"))
        if not rid:
            continue
        infl = safe_float(r.get("influence"))
        if infl is not None:
            valid_influences.append(max(0.0, min(100.0, infl)))
    mean_influence = (sum(valid_influences) / len(valid_influences)
                      if valid_influences else 50.0)

    # --- Pass 2: build clean Rep objects, enforcing all invariants.
    seen: dict[str, Rep] = {}

    for r in raw_reps:
        rid = normalize_id(r.get("id"))
        if not rid:
            report.rejected_reps.append((str(r.get("id")), "missing or empty id"))
            continue

        infl_raw = r.get("influence")
        infl = safe_float(infl_raw)
        if infl is None:
            infl = round(mean_influence, 2)
            report.clamped_values.append(
                (rid, "influence", f"null -> mean imputed {infl}")
            )
        elif infl < 0 or infl > 100:
            clamped = max(0.0, min(100.0, infl))
            report.clamped_values.append(
                (rid, "influence", f"{infl} -> clamped to {clamped}")
            )
            infl = clamped

        if rid in seen:
            existing = seen[rid]
            if infl > existing.influence:
                # Incoming record has higher influence — it wins.
                report.deduped.append(
                    (rid, f"replaced influence {existing.influence} with {infl} "
                          f"(raw id: {str(r.get('id'))}")
                )
                seen[rid] = Rep(
                    id=rid,
                    name=str(r.get("name", existing.name)),
                    faction=str(r.get("faction", existing.faction)),
                    influence=infl,
                    raw=r,
                )
            else:
                # Existing record wins; log the incoming duplicate.
                report.deduped.append(
                    (rid, f"kept influence {existing.influence}, discarded {infl} "
                          f"(raw id: {str(r.get('id'))}")
                )
        else:
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

    Invariants guaranteed:
        - every Proposal.id is normalized
        - every Proposal.sponsor is normalized AND in valid_rep_ids
          (proposals with ghost sponsors are dropped)
        - every Proposal.priority is a float
        - duplicate proposal ids deduped

    Dedup rule (KEEP HIGHEST PRIORITY):
        When two records share the same proposal id, we keep the one with
        the higher priority value and discard the lower. Rationale: the
        original submission typically carries the strongest mandate;
        later revisions that lower the priority number should not override
        the original intent. This also naturally surfaces the most urgent
        proposals to the scoring stage.
        Example on sample data:
            - prop_003 priority 9.5 vs 7 -> keep 9.5, discard 7.

    Ghost sponsor rule:
        Any proposal whose sponsor id (after normalization) is not in
        valid_rep_ids is silently dropped and logged in
        report.rejected_proposals.
        Example: prop_005 sponsored by rep_099 -> dropped.
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
            report.rejected_proposals.append((pid, f"ghost sponsor: {sponsor!r}"))
            continue

        priority = safe_float(p.get("priority"))
        if priority is None:
            report.rejected_proposals.append((pid, "non-numeric priority"))
            continue

        if pid in seen:
            existing = seen[pid]
            if priority > existing.priority:
                # Incoming has higher priority — it wins.
                report.deduped.append(
                    (pid, f"replaced priority {existing.priority} with {priority} "
                          f"(title: {str(p.get('title', ''))}")
                )
                seen[pid] = Proposal(
                    id=pid,
                    title=str(p.get("title", existing.title)),
                    sponsor=sponsor,
                    priority=priority,
                )
            else:
                # Existing wins; log the incoming lower-priority duplicate.
                report.deduped.append(
                    (pid, f"kept priority {existing.priority}, discarded {priority} "
                          f"(title: {str(p.get('title', ''))}")
                )
        else:
            seen[pid] = Proposal(
                id=pid,
                title=str(p.get("title", "")),
                sponsor=sponsor,
                priority=priority,
            )

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
