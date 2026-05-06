# Track Assignments — Phantom Consensus

**Total time budget: 4 hours.**
**Scaffold and split done by Anirudh (already pushed). Read your section,
stay in your owned files.**

```
Anirudh    -> Strategy   (src/features.py, src/graph.py, src/strategy.py)
Teammate 1 -> Data half A (src/loader.py: clean_reps + clean_proposals)
Teammate 2 -> Data half B (src/cleaner.py: clean_objections + clean_edges)

Tests + dashboard + docs done by Anirudh in the final hour.
```

No merge conflicts possible if everyone stays in their lane.
Shared utilities live in `src/_helpers.py` — extend only by chat agreement.

---

## Anirudh — Strategy

**Owns:** `src/features.py`, `src/graph.py`, `src/strategy.py`, `src/consensus.py`
**Read-only:** `src/schema.py`, `src/thresholds.py`, both data files

### What you build (~3 hours of focused work)

1. **`src/features.py`** — 8 metric functions. Each docstring already has the formula.
2. **`src/graph.py`** — `build_graph(edges)` returns a `TrustGraph` with adjacency dicts.
3. **`src/strategy.py`** — 5 decision functions (filter_reps, detect_alliances, score_proposals, select_proposals, select_supporters).
4. **`src/consensus.py`** — already wired. Just verify it runs end-to-end.

### Tests it kills (11 of 18 hidden scenarios)
Trojan Horse, Poison Pill, False Friend, Clear Alliance, Faction War,
Priority vs Objection, Supporter Coherence, Faction Infiltrator,
Cascading Betrayal, Alliance Hack, Complete Rivalry.

---

## Teammate 1 — Data half A (Reps + Proposals)

**Owns:** `src/loader.py` (functions `clean_reps`, `clean_proposals`, `load_clean`)
**Read-only:** everything else.

### What you build (~1.5 hours)

`src/loader.py` already has working stubs for both functions. Your job is to
**upgrade them to competition quality.** TODO comments mark every place you
need to make a decision.

#### `clean_reps(raw_reps)` — invariants to enforce
- Every `Rep.id` is normalized (`normalize_id` from `_helpers.py` already does this).
- **No duplicate ids.** Document your merge rule in the docstring. The
  dataset has `REP_001` (influence 80) AND `rep_001` (influence 85) AND
  ` rep_004` (influence 60) AND `rep_004` (influence null). Pick a rule
  (keep first / keep highest influence / merge fields by averaging) and
  defend it in one sentence.
- Every `Rep.influence` is a float in `[0, 100]`.
  - `"70"` → 70.0
  - `null` → drop the rep OR impute (50? mean? document which)
  - `150`  → clamp to 100
- Drop reps with empty/missing id.
- Log every action in `report` (deduped, clamped_values, rejected_reps).

#### `clean_proposals(raw_proposals, valid_rep_ids)` — invariants
- Every `Proposal.id` is normalized.
- Every `Proposal.sponsor` is normalized AND in `valid_rep_ids`. Drop ghosts.
  - Sample data: `prop_005` is sponsored by `rep_099` which doesn't exist.
- Every `Proposal.priority` is a float.
- Duplicate proposal ids deduped. Sample data: `prop_003` appears twice
  with priorities 9.5 and 7. **Document your rule** (highest priority? first
  occurrence? most recent? Pick one).

### Tests you kill (3 of 18)
Ghost Sponsor, ID Normalization, Duplicate Proposals (partial — Teammate 2
also handles edge dedup).

### How to verify
Run `python consensus_engine.py` after every change. Then run
`streamlit run dashboard/app.py` to see the Data Quality counters update.

---

## Teammate 2 — Data half B (Objections + Edges)

**Owns:** `src/cleaner.py` (functions `clean_objections`, `clean_edges`)
**Read-only:** everything else.

### What you build (~1.5 hours)

`src/cleaner.py` already has working stubs. Same rule: upgrade to
competition quality, follow the TODO markers, document every decision.

#### `clean_objections(raw_objections, valid_rep_ids, valid_prop_ids)` — invariants
- `obj.rep_id` normalized AND in `valid_rep_ids`.
- `obj.proposal_id` normalized AND in `valid_prop_ids`.
- `obj.severity` is a float in `[0, 10]`.
  - `8` → 8.0
  - `"high"` → use `SEVERITY_WORD_MAP` (already provided) or drop
  - `null` → drop
  - `-3` → clamp to 0 OR drop (decide and document)
- Duplicate `(rep_id, proposal_id)` entries deduped. Sample data:
  `rep_003 -> prop_001` appears twice with severity 8 and 6. Pick a rule
  (max? sum? first?) and document.

#### `clean_edges(csv_path, valid_rep_ids)` — invariants
- `edge.from_id` and `edge.to_id` normalized AND in `valid_rep_ids`.
- `edge.trust` in `[0, 100]`. Empty string → drop OR default (document).
- `edge.rivalry` in `[0, 100]`. Sample data has `rivalry: "high"` — map to
  a number (80?) or skip the row, your call.
- `edge.betrayal_prob` in `[0, 1]`. Sample data has `1.5` — clamp to 1.0.
- **Bad rows must NOT cause loss of good rows.** The CSV parser is wrapped
  in try/except per-row; keep it that way.
- Duplicate `(from, to)` edges deduped. Sample data has an exact-duplicate
  last row.

### Tests you kill (3 of 18)
Null Influence (partial — works with Teammate 1's clean_reps), Dirty CSV,
parts of Scale Correctness (good rows preserved at scale).

### How to verify
Run `python consensus_engine.py` after every change. The data summary in
`dashboard/app.py` shows your edge count and rejection log.

---

## Shared sync rules

- **Stuck >15 minutes?** Post in chat. We have 4 hours total.
- **Don't touch `_helpers.py` without telling the other data person.**
- **Don't touch `schema.py` or `thresholds.py`** — they're frozen contracts.
- **Run `python consensus_engine.py`** after every change. It NEVER crashes
  thanks to the baseline fallback, so a green run means your code at least
  loads.
- **The 18 scenario fixtures and the dashboard polish are Anirudh's final-
  hour job** — don't worry about tests/ or dashboard/ unless asked.
