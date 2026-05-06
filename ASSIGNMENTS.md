# Track Assignments — Phantom Consensus

**Total time budget: 4 hours.** First 15 minutes are this scaffold (already done by Anirudh).
Hours 1–4 each person works only in their owned files. No merge conflicts possible if you stay in your lane.

## Track A — Data Engineer

**Owns these files:**
- `src/loader.py`
- `src/cleaner.py`
- (read-only) `src/schema.py`, `src/thresholds.py`

**Your job:** turn the messy files in `data/raw/` into clean typed `CleanedData`. Issues 1–9, 18, 20.

**Acceptance criteria:**
- `load_clean()` returns a `CleanedData` object that satisfies these invariants:
  - All `rep.id` are lowercased and stripped (`REP_001` and ` rep_001` both → `rep_001`).
  - No two reps share an `id`. Duplicates merged with documented rule.
  - All `rep.influence` are floats in `[0, 100]`. Nulls dropped or imputed (document which).
  - All `proposal.priority` are floats. Duplicate proposals deduped by id.
  - Proposals with non-existent sponsors are dropped.
  - Objections referencing missing reps or proposals are dropped.
  - All `objection.severity` are floats in `[0, 10]`. Strings like `"high"` mapped or dropped.
  - All `edge.trust` ∈ `[0, 100]`, `edge.rivalry` ∈ `[0, 100]`, `edge.betrayal_prob` ∈ `[0, 1]`.
  - Bad CSV rows skipped without losing good rows.
- `quality_report` is populated with every action you took.

## Track B — Strategy Engineer

**Owns these files:**
- `src/features.py`
- `src/graph.py`
- `src/strategy.py`
- `src/consensus.py`
- (read-only) `src/schema.py`, `src/thresholds.py`

**Your job:** turn `CleanedData` into the final agreement + alliances + decision trace. Issues 10–17, 19.

**Acceptance criteria:**
- All eight metric functions in `features.py` implemented per their docstrings.
- `filter_reps`, `detect_alliances`, `score_proposals`, `select_proposals`, `select_supporters` all populated.
- `run_consensus()` in `consensus.py` ties it together end-to-end.
- Output passes Track C's 18 scenario tests.

## Track C — Quality + Dashboard + Docs

**Owns these files:**
- `tests/test_scenarios.py`
- `tests/fixtures/*` (create one folder per scenario)
- `dashboard/app.py`
- `APPROACH.md`, `RESULTS.md`, `LIMITATIONS.md`
- `README.md` (only the team-info bracket fields — keep format)

**Your job:** validate Track B's output against all 18 hidden scenarios, build the tiebreaker dashboard, write the three docs.

**Acceptance criteria:**
- 18 fixture folders under `tests/fixtures/`, one per hidden scenario, each with the four input files + an `expected.json` describing the right answer.
- `pytest tests/` runs all 18 against `consensus_engine.py`.
- Streamlit dashboard with at minimum: alliance graph, trust matrix, decision-trace table, viability bar chart.
- Docs follow the format mandated by the README.

## Sync rule

If anything is ambiguous, post in the group chat. Don't burn 15 minutes solo.
