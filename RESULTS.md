# Results - Phantom Consensus on Sample Data

This file documents the engine's behaviour on the provided sample data
in `data/raw/`. All numbers come from `output/trace.json` produced by
`python consensus_engine.py`.

## 1. Headline output

```
output/result.json
{
  "final_agreement": {
    "proposals":       ["prop_003", "prop_002"],
    "supporting_reps": ["rep_004",  "rep_003"]
  },
  "alliances": [["rep_001", "rep_004"]]
}
```

| Metric                  | Value |
| ----------------------- | ----- |
| Total reps loaded       | 6     |
| Reps accepted           | 4     |
| Reps rejected           | 2     |
| Supporters chosen       | 2     |
| Alliances detected      | 1     |
| Total proposals loaded  | 4 (5 raw, 1 ghost-sponsored) |
| Proposals selected      | 2     |
| Proposals rejected      | 1     |

## 2. Why each rep landed where they did

| id      | status          | influence | betrayal_risk | loyalty | reason                         |
| ------- | --------------- | --------- | ------------- | ------- | ------------------------------ |
| rep_001 | alliance_only   | 85.0      | 0.494         | 0.95    | borderline risk - too close to TAU_BETRAY for support, but reciprocal alliance with rep_004 holds |
| rep_002 | unaligned       | 70.0      | 0.231         | 0.75    | clean, but no top-7 supporter score, no reciprocal alliance |
| rep_003 | supporter       | 95.0      | 0.389         | 1.00    | high influence, perfect loyalty, no objection conflict      |
| rep_004 | supporter       | 83.1      | 0.179         | 0.98    | low betrayal, mean-imputed influence, top supporter score   |
| rep_005 | rejected        | 100.0     | **0.910**     | 0.85    | Trojan Horse (`betrayal=0.91 >= 0.5`)                       |
| rep_006 | rejected        | 92.0      | **0.764**     | 1.00    | Trojan Horse (`betrayal=0.76 >= 0.5`)                       |

`rep_001`'s `personal_betrayal_risk = 0.494` is the trust-weighted
formula doing its job: the raw max of their outgoing betrayal is high
(0.6 toward `rep_005`), but `rep_005` is someone they don't trust much,
so the trust factor `(0.7 + 0.3 * 0.62) = 0.886` brings the score down
to 0.494 - just below TAU_BETRAY. Without trust-weighting `rep_001`
would be a false-positive Trojan.

## 3. Why each proposal landed where it did

| id        | status   | priority | adj_viability | reason                                        |
| --------- | -------- | -------- | ------------- | --------------------------------------------- |
| prop_001  | unaligned| 8.0      | 7.78          | viable but not picked because the chosen pair already saturates supporters; budget allows but stability score lower |
| prop_002  | selected | 10.0     | 10.35         | top adj_viability, sponsor credibility 0.95   |
| prop_003  | selected | 9.5      | 10.64         | best adj_viability, distinct sponsor          |
| prop_004  | rejected | 10.0     | 7.56          | sponsor (rep_006) rejected as Trojan          |
| prop_005  | dropped  | -        | -             | ghost sponsor `rep_099` (in DataQualityReport)|

## 4. Alliance: rep_001 <-> rep_004

```
rel(rep_001 -> rep_004) = trust * (1 - betrayal) = 0.92 * (1 - 0.05) = 0.874
rel(rep_004 -> rep_001) = trust * (1 - betrayal) = 0.95 * (1 - 0.02) = 0.931
min(0.874, 0.931) = 0.874  >= TAU_ALLIANCE = 0.50   PASS
rivalry(rep_001 -> rep_004) = 5
rivalry(rep_004 -> rep_001) = 3
both < TAU_RIVALRY = 50                            PASS
```

`rep_005 <-> rep_006` does not become an alliance: both ends are
rejected as Trojans before alliance detection runs.

## 5. Data Quality Report

The cleaner caught and reported every messy input.

| Category              | Count | Examples                                                          |
| --------------------- | ----- | ----------------------------------------------------------------- |
| rejected_proposals    | 1     | `prop_005` ghost sponsor `rep_099`                                |
| rejected_objections   | 3     | negative severity `-3.0`, non-numeric `None`, ghost rep `rep_099` |
| rejected_edges        | 1     | row 13 `rep_002 -> rep_003` missing trust                         |
| deduped               | 5     | `REP_001` + `rep_001` collapsed; `prop_003` revision kept         |
| clamped_values        | 4     | `rep_004` null influence -> mean (83.14); `rep_005` 150 -> 100    |

Everything that left the cleaner has a row in `DataQualityReport`. This
is what the dashboard's "Data Quality" tab renders.

## 6. Hidden-scenario fixtures

`tests/_make_fixtures.py` writes 18 minimal-but-decisive fixtures, each
a folder under `tests/fixtures/`. Running `pytest tests/` produces:

```
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
================================== 18 passed ==================================
```

Each `expected.json` asserts at least one of:
`proposals_must_include` / `proposals_must_exclude` /
`supporters_must_include` / `supporters_must_exclude` /
`alliances_must_include` / `alliances_must_be_empty`.

## 7. Performance

On the sample data:

```
8-stage pipeline end-to-end: < 50 ms
fixture suite (18 scenarios): ~ 1 s
```

The exhaustive Pareto search over proposal subsets is bounded by
`K_MAX_PROPOSALS=5`, so worst-case complexity is `C(P, 5) * R` where P
is the number of viable proposals after the controversy filter. For
P=30 this is 142,506 subsets - hundreds of milliseconds, comfortably
inside the 60 s budget. Larger P would call for a beam search; the hook
is `select_proposals` and the change is local.
