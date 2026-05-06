"""
OWNER: Track C (Quality)

The 18 hidden scenarios as local fixtures. Each fixture lives in
tests/fixtures/<scenario_name>/ and contains:
  - representatives.json
  - proposals.json
  - objections.json
  - relations.csv
  - expected.json   (your assertion target)

Run with:  pytest tests/

Track C: build out each fixture with the smallest possible 4-file dataset
that exercises the scenario, plus an `expected.json` describing the right
answer. The test loader below will iterate them automatically.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.consensus import run_consensus
from src.loader import load_clean

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _list_scenarios() -> list[Path]:
    if not FIXTURES_DIR.exists():
        return []
    return [p for p in FIXTURES_DIR.iterdir() if p.is_dir()]


@pytest.mark.parametrize("scenario_dir", _list_scenarios(),
                         ids=lambda p: p.name)
def test_scenario(scenario_dir: Path) -> None:
    """
    Generic runner. Each fixture's expected.json may declare any subset of:
        {
          "proposals_must_include": ["prop_xx"],
          "proposals_must_exclude": ["prop_yy"],
          "supporters_must_include": ["rep_xx"],
          "supporters_must_exclude": ["rep_yy"],
          "alliances_must_include": [["rep_a", "rep_b"]],
          "alliances_must_be_empty": true
        }
    """
    expected_path = scenario_dir / "expected.json"
    if not expected_path.exists():
        pytest.skip(f"{scenario_dir.name} has no expected.json yet")

    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    data = load_clean(scenario_dir)
    result = run_consensus(data)

    props = set(result.final_agreement.get("proposals", []))
    sups = set(result.final_agreement.get("supporting_reps", []))
    alliances = {tuple(sorted(a)) for a in result.alliances}

    for must in expected.get("proposals_must_include", []):
        assert must in props, f"missing required proposal {must}"
    for must_not in expected.get("proposals_must_exclude", []):
        assert must_not not in props, f"forbidden proposal {must_not} present"
    for must in expected.get("supporters_must_include", []):
        assert must in sups, f"missing required supporter {must}"
    for must_not in expected.get("supporters_must_exclude", []):
        assert must_not not in sups, f"forbidden supporter {must_not} present"
    for pair in expected.get("alliances_must_include", []):
        assert tuple(sorted(pair)) in alliances, f"missing alliance {pair}"
    if expected.get("alliances_must_be_empty"):
        assert not alliances, f"expected no alliances, got {alliances}"
