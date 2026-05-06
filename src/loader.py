"""
OWNER: Track A (Data Engineer)

This file is a minimal-but-working stub so the pipeline runs end-to-end from
minute 1. Track A REPLACES the body of `load_clean()` with proper parsing,
ID normalization, type coercion, deduping, ghost-reference rejection, and
quality reporting.

Scope (Issues 1-9, 18, 20):
- read 4 files in data/raw/
- normalize ids (lowercase + strip whitespace)
- coerce influence/severity/priority to float, clamp ranges
- drop / merge duplicates with documented rule
- drop ghost-references
- populate DataQualityReport with every action taken

The contract: this function returns a CleanedData. Track B reads from there
and is allowed to assume every invariant in ASSIGNMENTS.md.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from src.schema import (
    CleanedData,
    DataQualityReport,
    Edge,
    Objection,
    Proposal,
    Rep,
)


DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def _normalize_id(raw: object) -> str:
    """Lowercase + strip. TODO Track A: extend if other irregularities surface."""
    if raw is None:
        return ""
    return str(raw).strip().lower()


def _safe_float(value: object, default: float = 0.0) -> float:
    """Best-effort float coercion. TODO Track A: replace with proper handling
    that logs into DataQualityReport.clamped_values."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return default


def load_clean(data_dir: Path = DATA_DIR) -> CleanedData:
    """
    Minimal pass-through loader. Produces *something* valid so the pipeline
    runs, but is NOT competition-quality. Track A rewrites this body.
    """
    report = DataQualityReport()

    # representatives
    with open(data_dir / "representatives.json", "r", encoding="utf-8") as f:
        raw_reps = json.load(f)
    reps_by_id: dict[str, Rep] = {}
    for r in raw_reps:
        rid = _normalize_id(r.get("id"))
        if not rid:
            report.rejected_reps.append((str(r.get("id")), "missing id"))
            continue
        if rid in reps_by_id:
            report.deduped.append((rid, str(r.get("id"))))
            continue
        infl = _safe_float(r.get("influence"), default=0.0)
        infl = max(0.0, min(100.0, infl))
        reps_by_id[rid] = Rep(
            id=rid,
            name=r.get("name", ""),
            faction=r.get("faction", ""),
            influence=infl,
            raw=r,
        )

    # proposals
    with open(data_dir / "proposals.json", "r", encoding="utf-8") as f:
        raw_props = json.load(f)
    props_by_id: dict[str, Proposal] = {}
    for p in raw_props:
        pid = _normalize_id(p.get("id"))
        sponsor = _normalize_id(p.get("sponsor"))
        if not pid:
            report.rejected_proposals.append((str(p.get("id")), "missing id"))
            continue
        if sponsor not in reps_by_id:
            report.rejected_proposals.append((pid, f"ghost sponsor {sponsor}"))
            continue
        if pid in props_by_id:
            report.deduped.append((pid, "duplicate proposal"))
            continue
        props_by_id[pid] = Proposal(
            id=pid,
            title=p.get("title", ""),
            sponsor=sponsor,
            priority=_safe_float(p.get("priority"), default=0.0),
        )

    # objections
    with open(data_dir / "objections.json", "r", encoding="utf-8") as f:
        raw_objs = json.load(f)
    objections: list[Objection] = []
    for o in raw_objs:
        rid = _normalize_id(o.get("rep_id"))
        pid = _normalize_id(o.get("proposal_id"))
        if rid not in reps_by_id:
            report.rejected_objections.append((f"{rid}->{pid}", "ghost rep"))
            continue
        if pid not in props_by_id:
            report.rejected_objections.append((f"{rid}->{pid}", "ghost proposal"))
            continue
        sev = _safe_float(o.get("severity"), default=0.0)
        sev = max(0.0, min(10.0, sev))
        objections.append(
            Objection(rep_id=rid, proposal_id=pid, severity=sev, reason=o.get("reason"))
        )

    # relations
    edges: list[Edge] = []
    with open(data_dir / "relations.csv", "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                src = _normalize_id(row.get("from"))
                dst = _normalize_id(row.get("to"))
                if src not in reps_by_id or dst not in reps_by_id:
                    report.rejected_edges.append((f"{src}->{dst}", "ghost endpoint"))
                    continue
                trust = max(0.0, min(100.0, _safe_float(row.get("trust"), 0.0)))
                rivalry = max(0.0, min(100.0, _safe_float(row.get("rivalry"), 0.0)))
                betrayal = max(0.0, min(1.0, _safe_float(row.get("betrayal_prob"), 0.0)))
                edges.append(Edge(src, dst, trust, rivalry, betrayal))
            except Exception as e:
                report.rejected_edges.append((str(row), f"parse error: {e}"))

    return CleanedData(
        reps=list(reps_by_id.values()),
        proposals=list(props_by_id.values()),
        objections=objections,
        edges=edges,
        quality_report=report,
    )
