# Scenario Fixtures (Track C)

One folder per hidden scenario. Each folder is self-contained:

```
tests/fixtures/<scenario>/
    representatives.json
    proposals.json
    objections.json
    relations.csv
    expected.json
```

`expected.json` schema:

```json
{
  "proposals_must_include":   ["prop_002"],
  "proposals_must_exclude":   ["prop_004"],
  "supporters_must_include":  ["rep_001"],
  "supporters_must_exclude":  ["rep_006"],
  "alliances_must_include":   [["rep_001", "rep_004"]],
  "alliances_must_be_empty":  false
}
```

All keys optional. Use only what you need for that scenario.

## The 18 scenarios to build (folder name suggestions)

1. `01_trojan_horse`             - high-influence rep with betrayal_prob=0.95
2. `02_poison_pill`              - priority-10 proposal with universal severe objections
3. `03_false_friend`             - asymmetric trust pair
4. `04_clear_alliance`           - mutual high-trust low-betrayal pair
5. `05_faction_war`              - two competing proposals, pick least-objected
6. `06_priority_vs_objection`    - high-priority but high-objection proposal loses
7. `07_supporter_coherence`      - objector must not appear as supporter
8. `08_faction_infiltrator`      - same-faction rep with high in-faction betrayal
9. `09_cascading_betrayal`       - A trusts B trusts C; C is a backstabber
10. `10_alliance_hack`           - stable alliance survives a disruptor
11. `11_complete_rivalry`        - everyone is rival; alliances must be empty
12. `12_ghost_sponsor`           - proposal with non-existent sponsor dropped
13. `13_minimum_viable`          - 1 valid rep, 1 valid proposal
14. `14_id_normalization`        - mixed-case + whitespace IDs across files
15. `15_duplicate_proposals`     - same proposal twice with conflicting data
16. `16_null_influence`          - rep with influence=null doesn't crash
17. `17_scale_correctness`       - 50 reps, 30 proposals; correct decisions
18. `18_dirty_csv`               - bad CSV rows; good rows still loaded

Build the smallest dataset that proves the point. 3 reps + 2 proposals is enough for most.
