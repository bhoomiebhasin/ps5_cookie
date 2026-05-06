"""
OWNER: Teammate 2 (Data - Objections + Edges)

Responsibilities:
- clean objections: normalize ids, coerce severity, reject ghost references,
  dedup with documented merge rule
- clean edges (CSV): parse with bad-row tolerance, clamp ranges, reject
  ghosts, dedup with documented merge rule using last_interaction

You consume `valid_rep_ids` and `valid_prop_ids` from Teammate 1's clean
output, so ghost-reference checks are O(1) set membership.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from src._helpers import normalize_id, safe_float
from src.schema import DataQualityReport, Edge, Objection


# ---------------------------------------------------------------------------
# Word-to-number maps for string severities / rivalries
# ---------------------------------------------------------------------------

SEVERITY_WORD_MAP: dict[str, float] = {
    "low": 2.0,
    "moderate": 5.0,
    "medium": 5.0,
    "high": 8.0,
    "critical": 10.0,
    "severe": 9.0,
    "minor": 2.0,
    "trivial": 1.0,
}

RIVALRY_WORD_MAP: dict[str, float] = {
    "low": 20.0,
    "moderate": 50.0,
    "medium": 50.0,
    "high": 80.0,
    "extreme": 95.0,
    "minor": 15.0,
}


def _coerce_with_word_map(
    raw: object, word_map: dict[str, float]
) -> float | None:
    """Numeric first, then word-map fallback. None on failure."""
    n = safe_float(raw)
    if n is not None:
        return n
    if isinstance(raw, str):
        return word_map.get(raw.strip().lower())
    return None


# ---------------------------------------------------------------------------
# Objections
# ---------------------------------------------------------------------------

def clean_objections(
    raw_objections: list[dict],
    valid_rep_ids: set[str],
    valid_prop_ids: set[str],
) -> tuple[list[Objection], DataQualityReport]:
    """
    Invariants guaranteed:
        - obj.rep_id is normalized AND in valid_rep_ids
        - obj.proposal_id is normalized AND in valid_prop_ids
        - obj.severity is a float in [0, 10]
            * 8                -> 8.0
            * "high"           -> 8.0 via SEVERITY_WORD_MAP
            * null             -> dropped (no signal)
            * negative numbers -> dropped (clearly bad data, not "low")
            * > 10             -> clamped to 10.0
        - duplicate (rep_id, proposal_id) entries deduped

    Severity dedup rule (KEEP MAX):
        Multiple records of the same rep objecting to the same proposal
        are merged by taking the highest severity. Rationale: a rep
        objecting twice with severity 6 then 8 represents an
        escalation; their strongest expressed concern is what matters
        for the engine.

    Negative severity rule (DROP, don't clamp):
        A severity like -3 is unambiguously a data error, not "very
        low concern". Clamping to 0 would silently turn a bug into a
        zero-weight no-op; dropping with a logged reason is more honest.
    """
    report = DataQualityReport()
    by_key: dict[tuple[str, str], Objection] = {}

    for o in raw_objections:
        rid = normalize_id(o.get("rep_id"))
        pid = normalize_id(o.get("proposal_id"))

        if rid not in valid_rep_ids:
            report.rejected_objections.append(
                (f"{rid}->{pid}", f"ghost rep {rid!r}")
            )
            continue
        if pid not in valid_prop_ids:
            report.rejected_objections.append(
                (f"{rid}->{pid}", f"ghost prop {pid!r}")
            )
            continue

        sev_raw = o.get("severity")
        sev = _coerce_with_word_map(sev_raw, SEVERITY_WORD_MAP)
        if sev is None:
            report.rejected_objections.append(
                (f"{rid}->{pid}", f"non-numeric severity {sev_raw!r}")
            )
            continue
        if sev < 0:
            report.rejected_objections.append(
                (f"{rid}->{pid}", f"negative severity {sev} (dropped)")
            )
            continue
        if sev > 10:
            report.clamped_values.append(
                (f"{rid}->{pid}", "severity", f"{sev} -> 10")
            )
            sev = 10.0

        key = (rid, pid)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = Objection(
                rep_id=rid, proposal_id=pid, severity=sev,
                reason=o.get("reason"),
            )
        else:
            # KEEP MAX rule
            if sev > existing.severity:
                report.deduped.append(
                    (f"{rid}->{pid}",
                     f"escalated severity {existing.severity} -> {sev}")
                )
                by_key[key] = Objection(
                    rep_id=rid, proposal_id=pid, severity=sev,
                    reason=o.get("reason") or existing.reason,
                )
            else:
                report.deduped.append(
                    (f"{rid}->{pid}",
                     f"kept severity {existing.severity}, ignored {sev}")
                )

    return list(by_key.values()), report


# ---------------------------------------------------------------------------
# Edges (CSV)
# ---------------------------------------------------------------------------

def _parse_date(raw: object) -> datetime | None:
    """ISO date parser. Returns None if parsing fails."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).strip())
    except (ValueError, TypeError):
        return None


def clean_edges(
    csv_path: Path,
    valid_rep_ids: set[str],
) -> tuple[list[Edge], DataQualityReport]:
    """
    Parse relations.csv with bad-row tolerance. ONE bad row must NOT
    lose other rows.

    Invariants guaranteed:
        - edge.from_id and edge.to_id normalized AND in valid_rep_ids
        - edge.trust         in [0, 100]
        - edge.rivalry       in [0, 100]
        - edge.betrayal_prob in [0, 1]
        - duplicate (from, to) edges deduped via last_interaction

    Field-level rules:
        trust:
            empty string / null -> ROW DROPPED. Trust is the load-bearing
            field; without it we can't compute relationship_score.
            out-of-range -> clamped.
        rivalry:
            empty / null -> defaulted to 0 (neutral; the rep simply hasn't
            registered rivalry). Logged.
            string like "high" -> mapped via RIVALRY_WORD_MAP. Logged.
            unmappable string -> defaulted to 0 with a clamped_values entry.
            out-of-range -> clamped.
        betrayal_prob:
            empty / null -> ROW DROPPED. As critical as trust.
            > 1 (e.g. 1.5) -> clamped to 1.0. Logged.
            < 0            -> clamped to 0.0. Logged.

    Edge dedup rule (KEEP MOST RECENT by last_interaction):
        When the same (from, to) pair appears twice, the row with the
        more recent `last_interaction` wins (people change their minds;
        recency matters more than first-impression). Ties go to the
        first-seen row for determinism. Rows without a parseable date
        are treated as oldest.
    """
    report = DataQualityReport()
    by_key: dict[tuple[str, str], tuple[Edge, datetime | None]] = {}

    try:
        f = open(csv_path, "r", encoding="utf-8", newline="")
    except FileNotFoundError:
        report.rejected_edges.append((str(csv_path), "file not found"))
        return [], report

    with f:
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

                # trust - load-bearing, drop row if missing
                trust = safe_float(row.get("trust"))
                if trust is None:
                    report.rejected_edges.append(
                        (f"row {row_num}: {src}->{dst}",
                         f"missing trust ({row.get('trust')!r})")
                    )
                    continue
                if trust < 0 or trust > 100:
                    clamped = max(0.0, min(100.0, trust))
                    report.clamped_values.append(
                        (f"{src}->{dst}", "trust", f"{trust} -> {clamped}")
                    )
                    trust = clamped

                # rivalry - tolerant, default to 0 with logging
                rivalry_raw = row.get("rivalry")
                rivalry = _coerce_with_word_map(rivalry_raw, RIVALRY_WORD_MAP)
                if rivalry is None:
                    report.clamped_values.append(
                        (f"{src}->{dst}", "rivalry",
                         f"{rivalry_raw!r} -> 0 (unparseable)")
                    )
                    rivalry = 0.0
                elif isinstance(rivalry_raw, str) and not _is_numeric_string(rivalry_raw):
                    report.clamped_values.append(
                        (f"{src}->{dst}", "rivalry",
                         f"{rivalry_raw!r} -> {rivalry} (mapped)")
                    )
                if rivalry < 0 or rivalry > 100:
                    clamped = max(0.0, min(100.0, rivalry))
                    report.clamped_values.append(
                        (f"{src}->{dst}", "rivalry", f"{rivalry} -> {clamped}")
                    )
                    rivalry = clamped

                # betrayal_prob - load-bearing, drop row if missing
                betrayal = safe_float(row.get("betrayal_prob"))
                if betrayal is None:
                    report.rejected_edges.append(
                        (f"row {row_num}: {src}->{dst}",
                         f"missing betrayal_prob ({row.get('betrayal_prob')!r})")
                    )
                    continue
                if betrayal < 0 or betrayal > 1:
                    clamped = max(0.0, min(1.0, betrayal))
                    report.clamped_values.append(
                        (f"{src}->{dst}", "betrayal_prob",
                         f"{betrayal} -> {clamped}")
                    )
                    betrayal = clamped

                edge = Edge(src, dst, trust, rivalry, betrayal)
                date = _parse_date(row.get("last_interaction"))

                key = (src, dst)
                existing = by_key.get(key)
                if existing is None:
                    by_key[key] = (edge, date)
                else:
                    prev_edge, prev_date = existing
                    if date is not None and (
                        prev_date is None or date > prev_date
                    ):
                        report.deduped.append(
                            (f"{src}->{dst}",
                             f"newer last_interaction wins ({date.date()})")
                        )
                        by_key[key] = (edge, date)
                    else:
                        report.deduped.append(
                            (f"{src}->{dst}", "older or duplicate row dropped")
                        )
            except Exception as e:
                report.rejected_edges.append(
                    (f"row {row_num}", f"parse error: {e}")
                )

    return [edge for edge, _ in by_key.values()], report


def _is_numeric_string(s: str) -> bool:
    """True if `s` parses as a number (used to distinguish '85' from 'high')."""
    try:
        float(s.strip())
        return True
    except (ValueError, TypeError):
        return False
