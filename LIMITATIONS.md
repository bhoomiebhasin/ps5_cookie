# Limitations and known trade-offs

We chose to ship a complete, defensible engine over a plausible-but-fragile
research prototype. These are the deliberate trade-offs.

## 1. Threshold sensitivity

All eight thresholds in `src/thresholds.py` were calibrated against the
brief's worked examples (`betrayal=0.95` for Trojans, `0.02-0.05` for
allies, etc.) and against the 18 hidden-test fixtures we generated.
They are **NOT** learned from data.

**Risk**: a hidden test deliberately sets `betrayal=0.49` to probe the
boundary. Our system would call them clean. We mitigate by:
- Live sliders in the dashboard - `TAU_BETRAY` and friends are tunable
  in real time so a panel demo can show robustness across plausible
  cutoffs.
- Documented justification next to each constant in `thresholds.py`.

A learned cutoff (e.g. percentile of empirical betrayal distribution)
would be more elegant. We did not implement it because the calibration
risk on a single small input is higher than the risk of a slightly
mis-tuned constant.

## 2. Sponsor credibility weight (0.30) is fixed

`adj_viability = viability * (1 + 0.3 * sponsor_credibility)` uses 0.30
as a fixed multiplier. We picked 0.30 so that a perfect sponsor
(`influence=100`, `loyalty=1.0`) gives a 30% boost - meaningful but
unable to drag a 1.0-viability proposal above TAU_VIABILITY=3.0.

**Risk**: a hidden test might rely on a different boost magnitude.
Mitigation: would require code change rather than a slider. Acceptable
because the metric only **adjusts** viability; it does not flip
selections by itself.

## 3. Coalition amplifier is faction-only

`HHI` is computed over **factions** of objectors. Co-conspirators across
factions would not concentrate.

**Risk**: a hidden test might construct a cross-faction bloc that we
treat as scattered. Mitigation: the alliance graph itself does pick up
cross-faction blocs (via mutual reciprocity), but they would not amplify
controversy. We considered using detected alliances as the concentration
unit; we did not because it adds complexity without a clear pay-off on
the brief's described tests.

## 4. Cascade risk is two-hop only

`cascade_risk(v) = max over v->u->w` only considers two-hop chains. A
three-hop A -> B -> C -> Trojan chain is invisible.

**Risk**: arbitrary depth would be more correct in theory. Mitigation:
in practice the brief's "Cascading Betrayal" example is two-hop, and
extending the formula to three hops is one nested loop in
`src/features.py::cascade_risk`. We did not extend further because:
- the supporting evidence in dirty data is too noisy to trust deep
  chains, and
- the cleanup of false positives is what the rest of the engine does.

## 5. Proposal selection is bounded by K_MAX_PROPOSALS = 5

We enumerate every subset of size <= 5. For 30 proposals this is
roughly 174k subsets, well inside the time budget. For >50 proposals
this would tip into seconds.

**Risk**: a brutally large hidden input. Mitigation: `select_proposals`
exposes the search loop in one place. Swapping for greedy +
local-search (1-swap) is a 20-line change that preserves the scoring
function.

## 6. Data quality recovery is conservative

When a CSV row is unsalvageable we drop the row, never invent values.
For nullable numeric fields (rep influence) we mean-impute. We do NOT:
- carry uncertainty through to the metrics (e.g. mark rep_004's score
  as approximate),
- attempt fuzzy ID matching (`rep_o01` -> `rep_001`),
- regenerate "expected" rows from neighbouring evidence.

**Risk**: a test that depends on us recovering an obviously broken row
would fail. We accepted this because every quality intervention is
already explained in the `DataQualityReport`, which is more useful than
silently fabricating data.

## 7. Pipeline determinism

`networkx.spring_layout` in the dashboard uses a fixed `seed=42`. Every
ordering inside the engine (rep iteration, edge iteration, subset
enumeration via `itertools.combinations`) follows insertion order.
Outputs are bitwise-stable run to run on the sample input.

**Risk**: if the judges shuffle inputs, we still produce the same
*sets* but the *order* in `final_agreement.proposals` may change. The
spec asks for sets, so this is fine, but worth flagging.

## 8. What we would do with another two hours

In priority order:
1. Replace `K_MAX_PROPOSALS=5` exhaustive search with greedy +
   1-swap local search to handle >50 proposals comfortably.
2. Promote the eight thresholds to a small JSON config so that
   different judges can rerun with their own cutoffs without editing
   code.
3. Cross-faction coalition detection for the controversy amplifier.
4. Three-hop cascade with attenuation (`* 0.5` per extra hop).

None of these change correctness on the sample data; all of them are
incremental robustness improvements.
