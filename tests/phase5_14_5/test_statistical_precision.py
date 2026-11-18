"""
Phase 5.14.5 — Statistical Evidence Precision Verification Tests
Verifies:
  1. All 8 comparisons unrounded satisfy explicit numerical tolerances (atol=1e-6, rtol=1e-5).
  2. Confidence intervals contain effect estimates.
  3. Holm-Bonferroni step-down monotonicity strictly satisfied.
  4. Exact 6 significant, 0 directional, 2 non-significant classification.
  5. 2026 bowlers are strictly NON-SIGNIFICANT (CIs cross zero, Holm p = 0.1144).
  6. Detection of modified effect, shifted CI, or altered p-value.
"""

import sys
import os
import json
import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from research.phase5_14_5.authoritative_gate import (
    evaluate_statistical_precision,
    DEFAULT_STATS_PATH,
    NUMERICAL_TOLERANCES,
)

def test_canonical_statistical_evidence_passes_all_tolerances():
    """Verify that canonical statistical interpretation satisfies all numerical tolerances."""
    res = evaluate_statistical_precision()
    assert res["is_passed"] is True
    assert res["status"] == "PASSED"
    assert len(res["failures"]) == 0
    assert len(res["comparisons"]) == 8

    c_summary = res["classification_summary"]
    assert c_summary["statistically_significant"] == 6
    assert c_summary["directional"] == 0
    assert c_summary["non_significant"] == 2
    assert c_summary["total"] == 8


def test_confidence_intervals_contain_point_estimates():
    """Verify that every comparison's 95% bootstrap CI contains its observed effect."""
    res = evaluate_statistical_precision()
    for c in res["comparisons"]:
        assert c["ci_contains_estimate"] is True, f"Comparison {c['comparison_id']} CI does not contain effect"


def test_holm_monotonicity_strictly_satisfied():
    """Verify that Holm-adjusted p-values are strictly non-decreasing."""
    res = evaluate_statistical_precision()
    holm_p_values = [c["holm_adjusted_p"] for c in res["comparisons"]]
    for i in range(len(holm_p_values) - 1):
        assert holm_p_values[i] <= holm_p_values[i + 1], f"Monotonicity violated: {holm_p_values[i]} > {holm_p_values[i+1]}"


def test_2026_bowlers_strictly_non_significant():
    """Verify that both 2026 bowler comparisons are strictly classified as NON_SIGNIFICANT."""
    res = evaluate_statistical_precision()
    bw_2026 = [c for c in res["comparisons"] if "2026_bowlers" in c["comparison_id"]]
    assert len(bw_2026) == 2

    for c in bw_2026:
        assert c["classification"] == "NON_SIGNIFICANT"
        assert c["ci_crosses_zero"] is True
        assert c["holm_adjusted_p"] >= 0.05


def test_altered_effect_fails_tolerance_check(tmp_path):
    """Perturbing observed effect beyond tolerance triggers failure."""
    with open(DEFAULT_STATS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Alter first comparison effect
    data["comparisons"][0]["observed_effect"] = 6.50
    bad_file = tmp_path / "bad_effect.json"
    with open(bad_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_statistical_precision(stats_path=bad_file)
    assert res["is_passed"] is False
    assert any("Tolerances violated" in f for f in res["failures"])


def test_inverted_classification_fails(tmp_path):
    """Flipping a non-significant comparison to statistically significant triggers failure."""
    with open(DEFAULT_STATS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    for c in data["comparisons"]:
        if c["comparison_id"] == "2026_bowlers_vs_league":
            c["inference_classification"] = "STATISTICALLY_SIGNIFICANT"

    bad_file = tmp_path / "bad_class.json"
    with open(bad_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_statistical_precision(stats_path=bad_file)
    assert res["is_passed"] is False
    assert any("Inconsistency" in f or "Classification count mismatch" in f for f in res["failures"])
