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

The pipeline runs in eight stages: load -> clean -> features -> trust graph -> rep filter -> alliance detection -> proposal scoring + selection -> supporter selection. Every decision is recorded in `output/trace.json` and surfaced in the Streamlit dashboard.

**Data cleaning** lives in `src/loader.py` (reps, proposals) and `src/cleaner.py` (objections, edges). IDs are normalised (lowercase + strip), missing influence is mean-imputed, out-of-range numerics are clamped, ghost references are dropped, duplicates are merged by max severity / latest interaction / max influence. Every dropped or clamped value is reported in `DataQualityReport`.

**Alliance detection** uses a multiplicative `relationship_score = (trust/100) * (1 - betrayal_prob)` and requires `min(score_AB, score_BA) >= TAU_ALLIANCE` plus low rivalry both ways. This catches False-Friend asymmetry (one direction high trust, the other high betrayal) without misclassifying it as alliance.

**Proposal prioritisation** combines `priority * (1 - controversy)` with a coalition amplifier (Herfindahl-Hirschman Index over the factions of objectors) so a unified bloc shouting at severity 10 outweighs scattered grumbling. Sponsor credibility (`influence * faction_loyalty`) gives a small viability bonus and is hard-zeroed when the sponsor is rejected.

**Stable consensus**: reps with `personal_betrayal_risk >= TAU_BETRAY` are removed as Trojan Horses (the risk is trust-weighted to avoid penalising betrayal of known enemies). Faction Infiltrators are caught by `faction_loyalty < TAU_LOYALTY`. Proposal selection is an exhaustive Pareto-optimal search over subsets up to size 5 with a stability bias (`+ 1.5 * coherent_supporter_count`, plus a hard penalty if a majority of accepted reps are blocked) - this refuses a +1 viability gain that would halve support, killing Poison Pill proposals.

Full documentation: see `APPROACH.md` (architecture + the five S-tier differentiators), `RESULTS.md` (sample-data behaviour with numbers), and `LIMITATIONS.md` (honest trade-offs).

**Note:** Please do not change the format or spelling of anything in this README. The fields are extracted using a script, so any changes to the structure or formatting may break the extraction process.
