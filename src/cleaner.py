"""
OWNER: Teammate 2 (Data - Objections + Edges)

Responsibilities:
- clean objections: normalize ids, coerce severity, reject ghost references
- clean edges (CSV): parse with bad-row tolerance, clamp ranges, reject ghosts

You consume `valid_rep_ids` and `valid_prop_ids` from Teammate 1's clean
output, so your ghost-reference checks are just set membership.

Teammate 1 imports your two functions from `src.cleaner` in `src.loader`.
You should NOT need to touch loader.py.
"""

from __future__ import annotations

import csv
from pathlib import Path

from src._helpers import normalize_id, safe_float
from src.schema import DataQualityReport, Edge, Objection


# ---------------------------------------------------------------------------
# YOUR WORK - objections
# ---------------------------------------------------------------------------

# Used to coerce string severities like "high" / "low" / "moderate" into a
# numeric scale. Add more mappings as you find them in the data.
SEVERITY_WORD_MAP: dict[str, float] = {
    "low": 2.0,
    "moderate": 5.0,
    "medium": 5.0,
    "high": 8.0,
    "critical": 10.0,
}


def clean_objections(
    raw_objections: list[dict],
    valid_rep_ids: set[str],
    valid_prop_ids: set[str],
) -> tuple[list[Objection], DataQualityReport]:
    """
    Invariants you must guarantee:
        - obj.rep_id is normalized AND in valid_rep_ids
        - obj.proposal_id is normalized AND in valid_prop_ids
        - obj.severity is a float in [0, 10]
            * 8                -> 8.0
            * "high"           -> map via SEVERITY_WORD_MAP, or drop
            * null             -> drop
            * -3               -> clamp to 0 OR drop (decide and document)
        - duplicate (rep_id, proposal_id, severity) entries deduped

    Examples in the dataset:
        - {"rep_id":"rep_001","proposal_id":"prop_002","severity":"high"} -> map "high"
        - severity: -3                                                    -> clamp/drop
        - severity: null                                                  -> drop
        - rep_id: rep_099 (ghost)                                         -> drop
        - duplicate "rep_003 -> prop_001" with different severities       -> dedup
    """
    report = DataQualityReport()
    out: list[Objection] = []
    seen: set[tuple[str, str]] = set()

    for o in raw_objections:
        rid = normalize_id(o.get("rep_id"))
        pid = normalize_id(o.get("proposal_id"))

        if rid not in valid_rep_ids:
            report.rejected_objections.append((f"{rid}->{pid}", f"ghost rep {rid}"))
            continue
        if pid not in valid_prop_ids:
            report.rejected_objections.append((f"{rid}->{pid}", f"ghost prop {pid}"))
            continue

        sev_raw = o.get("severity")
        sev = safe_float(sev_raw)
        if sev is None:
            # try the word map
            if isinstance(sev_raw, str):
                sev = SEVERITY_WORD_MAP.get(sev_raw.strip().lower())
            if sev is None:
                report.rejected_objections.append(
                    (f"{rid}->{pid}", f"non-numeric severity {sev_raw!r}")
                )
                continue

        if sev < 0 or sev > 10:
            report.clamped_values.append((f"{rid}->{pid}", "severity", f"{sev} -> clamped"))
            sev = max(0.0, min(10.0, sev))

        # TODO Teammate 2: decide your dedup rule (keep first / max severity
        # / sum severities). Document it in this docstring.
        key = (rid, pid)
        if key in seen:
            report.deduped.append((f"{rid}->{pid}", "duplicate objection"))
            continue
        seen.add(key)

        out.append(Objection(rep_id=rid, proposal_id=pid, severity=sev,
                             reason=o.get("reason")))

    return out, report


# ---------------------------------------------------------------------------
# YOUR WORK - edges (CSV)
# ---------------------------------------------------------------------------

def clean_edges(
    csv_path: Path,
    valid_rep_ids: set[str],
) -> tuple[list[Edge], DataQualityReport]:
    """
    Parse relations.csv with bad-row tolerance. ONE bad row must NOT cause
    good rows to be lost.

    Invariants:
        - edge.from_id and edge.to_id are normalized AND in valid_rep_ids
        - edge.trust         in [0, 100]   ("" / null -> drop OR default? Document.)
        - edge.rivalry       in [0, 100]   ("high" -> map or drop)
        - edge.betrayal_prob in [0, 1]     (1.5 -> clamp to 1.0)
        - duplicate (from, to) edges deduped (document rule: keep first?
          most recent by last_interaction?)

    Examples in the dataset:
        - row with rivalry="high"             -> needs handling
        - row with trust=""                   -> needs handling
        - row with betrayal_prob=1.5          -> clamp
        - exact duplicate row                 -> dedup
        - rep_099 endpoint                    -> drop (ghost)
    """
    report = DataQualityReport()
    out: list[Edge] = []
    seen: set[tuple[str, str]] = set()

    try:
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):
                try:
                    src = normalize_id(row.get("from"))
                    dst = normalize_id(row.get("to"))
                    if src not in valid_rep_ids or dst not in valid_rep_ids:
                        report.rejected_edges.append(
                            (f"row {row_num}: {src}->{dst}", "ghost endpoint")
                        )
                        continue

                    trust = safe_float(row.get("trust"))
                    if trust is None:
                        report.rejected_edges.append(
                            (f"row {row_num}: {src}->{dst}", "non-numeric trust")
                        )
                        continue
                    if trust < 0 or trust > 100:
                        report.clamped_values.append(
                            (f"{src}->{dst}", "trust", f"{trust} -> clamped")
                        )
                        trust = max(0.0, min(100.0, trust))

                    rivalry = safe_float(row.get("rivalry"))
                    if rivalry is None:
                        # TODO Teammate 2: decide policy ('high' -> 80? skip row?)
                        rivalry = 0.0
                        report.clamped_values.append(
                            (f"{src}->{dst}", "rivalry",
                             f"{row.get('rivalry')!r} -> 0")
                        )
                    if rivalry < 0 or rivalry > 100:
                        rivalry = max(0.0, min(100.0, rivalry))

                    betrayal = safe_float(row.get("betrayal_prob"))
                    if betrayal is None:
                        report.rejected_edges.append(
                            (f"row {row_num}: {src}->{dst}", "non-numeric betrayal")
                        )
                        continue
                    if betrayal < 0 or betrayal > 1:
                        report.clamped_values.append(
                            (f"{src}->{dst}", "betrayal_prob",
                             f"{betrayal} -> clamped")
                        )
                        betrayal = max(0.0, min(1.0, betrayal))

                    key = (src, dst)
                    if key in seen:
                        report.deduped.append(
                            (f"{src}->{dst}", "duplicate edge")
                        )
                        continue
                    seen.add(key)

                    out.append(Edge(src, dst, trust, rivalry, betrayal))
                except Exception as e:
                    report.rejected_edges.append(
                        (f"row {row_num}", f"parse error: {e}")
                    )
    except FileNotFoundError:
        report.rejected_edges.append((str(csv_path), "file not found"))

    return out, report
