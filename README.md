# Phantom Consensus

## Team Information
- **Team Name**: ps5_cookie
- **Year**: 2026
- **All-Female Team**: No

## Architecture Overview

#### Describe your approach here. Keep it short and clear.

- How did you approach cleaning the raw data, including handling missing values, inconsistent formats, and outliers?
- What logic did you use to detect underlying alliances and evaluate the impact of asymmetric trust and betrayal probabilities?
- How did you prioritize proposals given varying objection severities and differing levels of influence among objectors?
- Describe the strategy used by your consensus engine to maintain a stable agreement while avoiding "Trojan Horse" candidates and "Poison Pill" proposals.

---

### TL;DR

A strategic political advisor that ingests four dirty data files and returns
the largest set of compatible proposals a stable, non-treacherous coalition
can support, plus the bidirectional alliances that survive scrutiny - and
**explains every decision** through a structured `DecisionTrace`.

- 8-stage pipeline (load -> clean -> features -> graph -> filter -> alliances
  -> proposals -> supporters), all under 50 ms on the sample data.
- Five S-tier algorithmic differentiators (full derivations in
  [`APPROACH.md`](APPROACH.md)).
- **19/19 green** scenario fixtures in `tests/fixtures/` (the 18 hidden-test
  scenarios from the brief + a "mass rejection" graceful-degradation stress
  test) under `python -m pytest tests/`.
- Streamlit dashboard with a live dataset picker (competition data + every
  fixture), six analytical panels, and live threshold sliders.

### One-paragraph answers to the four questions above

**Data cleaning.** `src/loader.py` handles representatives and proposals;
`src/cleaner.py` handles objections and edges. IDs are normalised
(lowercase + strip), missing influence is mean-imputed, out-of-range
numerics are clamped (e.g. `betrayal_prob = 1.5 -> 1.0`), ghost references
to non-existent reps/proposals are dropped, duplicates are merged by
*max severity* / *latest interaction* / *max influence*, and string-form
severities and rivalry words ("high", "moderate") are mapped via
`SEVERITY_WORD_MAP` and `RIVALRY_WORD_MAP`. **Every** dropped, deduped or
clamped record lands in `DataQualityReport` with a reason.

**Alliance detection.** Multiplicative
`relationship_score = (trust/100) * (1 - betrayal_prob)` with a strict
*bidirectional reciprocity* gate
`min(score_AB, score_BA) >= TAU_ALLIANCE`, plus
`rivalry < TAU_RIVALRY` both ways. This catches False-Friend asymmetry (one
direction shows high trust, the other is hostile) without flagging it as
an alliance, and resists single-side noise.

**Proposal prioritisation.**
`viability = priority * (1 - controversy)` is the canonical baseline, then
*coalition-amplified*: a Herfindahl-Hirschman Index over the factions of
objectors multiplies controversy by `1 + 0.5 * HHI` so a unified bloc at
severity 10 outweighs scattered grumbling. *Sponsor credibility*
(`influence * faction_loyalty`) gives a small viability bonus and is
hard-zeroed when the sponsor is a rejected Trojan, killing the proposal.

**Stable consensus.** Reps are filtered by trust-weighted
`personal_betrayal_risk >= TAU_BETRAY` (Trojan Horse),
`faction_loyalty < TAU_LOYALTY` (Faction Infiltrator), and
`cascade_risk >= TAU_CASCADE` through accepted intermediates ending in a
Trojan endpoint. Proposal selection is an exhaustive Pareto-optimal
search over subsets up to size 5, with a stability bias
(`+ 1.5 * coherent_supporter_count`, plus `-8` if a majority of accepted
reps are blocked) - this **refuses a +1 viability gain that would halve
support**, killing Poison Pill proposals.

### Pipeline

```
raw files
   |
   v
[1] load_raw      JSON / CSV parsers, robust to dirty input
[2] cleaner       per-file rules + DataQualityReport
[3] features      relationship_score, objection_weight, controversy
[4] graph         TrustGraph (in/out adjacency for O(1) neighbour lookups)
[5] strategy      filter_reps    (Trojans / Infiltrators / Cascade-risk)
                  detect_alliances (bidirectional reciprocity + low rivalry)
                  score_proposals  (coalition + sponsor adjustments)
                  select_proposals (Pareto-optimal exhaustive search)
                  select_supporters(Coherence + Cascade + multiplicative score)
[6] consensus     orchestrates [3]-[5], enriches RepTrace with status
[7] consensus_engine.py
                  writes output/result.json + output/trace.json
[8] tests + dashboard
```

### Repository layout

```
ps5_cookie/
  consensus_engine.py            entry point - python consensus_engine.py
  src/
    schema.py                    @dataclasses (frozen contract between layers)
    thresholds.py                eight tunable constants, each with a docstring
    _helpers.py                  normalize_id, safe_float (shared utilities)
    loader.py                    representatives + proposals cleaning
    cleaner.py                   objections + edges cleaning
    features.py                  relationship_score, controversy,
                                 personal_betrayal_risk (trust-weighted),
                                 faction_loyalty, cascade_risk
    graph.py                     TrustGraph (out_edges + in_edges adjacency)
    strategy.py                  the five S-tier differentiators live here
    consensus.py                 8-stage orchestrator
  tests/
    test_scenarios.py            generic fixture runner
    _make_fixtures.py            generator for all 18 fixtures
    fixtures/01..18/             one folder per hidden-test scenario
  dashboard/
    app.py                       Streamlit dashboard - 6 panels + dataset picker
  data/raw/                      sample input data
  output/                        result.json + trace.json
  APPROACH.md                    architecture + the five S-tier differentiators
  RESULTS.md                     sample-data behaviour with concrete numbers
  LIMITATIONS.md                 honest trade-offs and what we'd improve
```

### Five S-tier differentiators (full derivations: `APPROACH.md`)

| # | Name                                | Where                       | Why it matters                                                                  |
| - | ----------------------------------- | --------------------------- | ------------------------------------------------------------------------------- |
| 1 | Trust-weighted personal betrayal    | `features.py`               | Stops false-positive Trojans triggered by betraying a known enemy               |
| 2 | Coalition-aware controversy (HHI)   | `strategy.py::score_proposals` | A unified faction bloc weighs more than the same severity scattered randomly  |
| 3 | Sponsor credibility bonus           | `strategy.py::score_proposals` | A Trojan-sponsored proposal is hard-zeroed regardless of its raw priority    |
| 4 | Stability-aware Pareto selection    | `strategy.py::select_proposals` | Refuses +1 viability if it halves support; kills Poison Pills                |
| 5 | Multiplicative supporter score + cascade-through-accepted | `strategy.py::select_supporters` | High influence cannot drown out high betrayal risk; cascades fire only through real threats |

### Threshold map

All eight thresholds carry justification docstrings in
[`src/thresholds.py`](src/thresholds.py) and are exposed as **live sliders**
in the dashboard sidebar.

| Constant         | Value | Rationale                                                    |
| ---------------- | ----- | ------------------------------------------------------------ |
| TAU_BETRAY       | 0.50  | Trojan ~ 0.95, ally ~ 0.02-0.05 -> 0.5 separates them cleanly |
| TAU_ALLIANCE     | 0.50  | both directions must be >= 50% reliable                      |
| TAU_RIVALRY      | 50    | midpoint of 0-100; above = adversarial                       |
| TAU_LOYALTY      | 0.60  | mean in-faction betrayal must stay below 0.4                 |
| TAU_CASCADE      | 0.40  | two-hop trust * Trojan-betrayal cap                          |
| TAU_VIABILITY    | 3.00  | priority * (1 - controversy) cutoff for selection eligibility|
| TAU_OBJ_BLOCK    | 5.00  | severity below 5 = critique; >= 5 = blocking                 |
| TAU_BUDGET       | 30.0  | cumulative objection_weight cap across all selected proposals|

### Testing

We exercise the engine against **all 18 hidden-test scenarios from the
brief** plus a graceful-degradation stress test (`19_mass_rejection`),
all locally reproducible as fixtures under `tests/fixtures/`. The runner
is generic (`tests/test_scenarios.py`) and discovers fixtures by
directory.

```
$ python -m pytest tests/ -v
tests/test_scenarios.py::test_scenario[01_trojan_horse]            PASSED
tests/test_scenarios.py::test_scenario[02_poison_pill]             PASSED
tests/test_scenarios.py::test_scenario[03_false_friend]            PASSED
tests/test_scenarios.py::test_scenario[04_clear_alliance]          PASSED
tests/test_scenarios.py::test_scenario[05_faction_war]             PASSED
tests/test_scenarios.py::test_scenario[06_priority_vs_objection]   PASSED
tests/test_scenarios.py::test_scenario[07_supporter_coherence]     PASSED
tests/test_scenarios.py::test_scenario[08_faction_infiltrator]     PASSED
tests/test_scenarios.py::test_scenario[09_cascading_betrayal]      PASSED
tests/test_scenarios.py::test_scenario[10_alliance_hack]           PASSED
tests/test_scenarios.py::test_scenario[11_complete_rivalry]        PASSED
tests/test_scenarios.py::test_scenario[12_ghost_sponsor]           PASSED
tests/test_scenarios.py::test_scenario[13_minimum_viable]          PASSED
tests/test_scenarios.py::test_scenario[14_id_normalization]        PASSED
tests/test_scenarios.py::test_scenario[15_duplicate_proposals]     PASSED
tests/test_scenarios.py::test_scenario[16_null_influence]          PASSED
tests/test_scenarios.py::test_scenario[17_scale_correctness]       PASSED
tests/test_scenarios.py::test_scenario[18_dirty_csv]               PASSED
tests/test_scenarios.py::test_scenario[19_mass_rejection]          PASSED
================================== 19 passed ==================================
```

### Dashboard

```
streamlit run dashboard/app.py
```

Six analytical panels plus a sidebar with a **dataset picker** (competition
data and every fixture) and **live threshold sliders** that recompute the
entire pipeline on change. When a fixture is selected, an "expected vs.
actual" table renders inline so judges can visually confirm each
hidden-test behaviour without reading code.

| Panel                  | What it shows                                              |
| ---------------------- | ---------------------------------------------------------- |
| Final Agreement        | selected proposals + supporters + detected alliances       |
| Decision Trace         | per-rep and per-proposal metrics, statuses, and rejections |
| Alliance Graph         | networkx + plotly, faction-coloured, alliances highlighted |
| Trust Matrix Heatmap   | reps x reps; asymmetry visible (False-Friend signature)    |
| Proposal Viability     | priority vs adj_viability bars with TAU_VIABILITY guideline|
| Data Quality Report    | rejected / deduped / clamped records across six tabs       |

### Reproducing

```
python -m pip install -r requirements.txt
python consensus_engine.py            # writes output/result.json + trace.json
python -m pytest tests/ -v             # 18 hidden-scenario fixtures
streamlit run dashboard/app.py         # interactive dashboard
```

### Code-quality signals

- Type-hinted Python 3.10+ throughout (`from __future__ import annotations`).
- `@dataclass` schema (`src/schema.py`) is the **frozen contract** between
  the data layer and the strategy layer, preventing interface drift.
- Every threshold carries a justification docstring in `src/thresholds.py`.
- Every cleaning rule logs its decision into `DataQualityReport`.
- `_helpers.py` exists specifically to break a circular import between
  `loader.py` and `cleaner.py` - we noticed and fixed it.
- 19 fixtures plus a generator (`tests/_make_fixtures.py`); regenerating is
  one command.
- Dashboard handles failure paths (`pipeline_error` -> `st.error` + `st.stop`).

### Documentation

- [`APPROACH.md`](APPROACH.md) - architecture + full derivations of the five
  S-tier differentiators with formulas, plus a hidden-test mapping table.
- [`RESULTS.md`](RESULTS.md) - concrete sample-data outcomes with numbers
  pulled from `output/trace.json`.
- [`LIMITATIONS.md`](LIMITATIONS.md) - honest trade-offs (threshold
  sensitivity, two-hop cascade horizon, K=5 cap on proposal subsets) and
  what we'd improve with another two hours.

**Note:** Please do not change the format or spelling of anything in this README. The fields are extracted using a script, so any changes to the structure or formatting may break the extraction process.
