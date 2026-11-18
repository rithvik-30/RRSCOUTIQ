"""
Phase 5.14.5.1 — Bootstrap Numerical Evidence Verification Tests
RR ScoutIQ | Rajasthan Royals IPL 2027 Auction Strategy Hackathon

Verifies Fix C:
1. Canonical baseline passes all 8 comparisons across all 7 numerical fields with atol=1e-6, rtol=1e-5.
2. Individual adversarial tests that modify ONLY:
   - Bootstrap mean.
   - Bootstrap standard error.
   - Observed effect estimate.
   - CI lower endpoint.
   - CI upper endpoint.
   - Raw p-value.
   - Holm-adjusted p-value.
3. Verifies that every field evaluation record contains:
   - Expected value.
   - Actual value.
   - Absolute difference.
   - Relative difference.
   - Applied atol and rtol.
   - Pass/fail status.
"""

import os
import sys
import copy
import json
import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from research.phase5_14_5.authoritative_gate import (
    evaluate_statistical_precision,
    DEFAULT_STATS_PATH,
    NUMERICAL_TOLERANCES,
)


@pytest.fixture
def canonical_stats_data():
    with open(DEFAULT_STATS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_canonical_statistical_evidence_full_records_pass():
    """Verify that canonical baseline satisfies all tolerances and records granular fields."""
    res = evaluate_statistical_precision()
    assert res["is_passed"] is True
    assert res["status"] == "PASSED"
    assert len(res["failures"]) == 0
    assert len(res["comparisons"]) == 8

    for c in res["comparisons"]:
        assert c["all_tolerances_satisfied"] is True
        f_evals = c["field_evaluations"]

        # Ensure all 7 numerical fields are verified and recorded
        expected_fields = [
            "observed_effect",
            "bootstrap_mean",
            "bootstrap_standard_error",
            "ci_95_low",
            "ci_95_high",
            "raw_p_value",
            "holm_adjusted_p",
        ]
        for fld in expected_fields:
            assert fld in f_evals, f"Field {fld} missing from comparison {c['comparison_id']}"
            f_rec = f_evals[fld]
            assert "expected_value" in f_rec
            assert "actual_value" in f_rec
            assert "absolute_difference" in f_rec
            assert "relative_difference" in f_rec
            assert "applied_atol" in f_rec
            assert "applied_rtol" in f_rec
            assert f_rec["pass_fail_status"] == "PASSED"
            assert f_rec["applied_atol"] == 1e-6
            assert f_rec["applied_rtol"] == 1e-5


def test_perturb_bootstrap_mean_only_fails(tmp_path, canonical_stats_data):
    """Adversarial: Modifying ONLY bootstrap_mean beyond tolerance triggers failure."""
    data = copy.deepcopy(canonical_stats_data)
    # Target 2025_batters_vs_league: expected bootstrap_mean ~ 5.873077
    orig = data["comparisons"][0]["bootstrap_mean"]
    data["comparisons"][0]["bootstrap_mean"] = orig + 0.05

    p = tmp_path / "bad_boot_mean.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_statistical_precision(stats_path=p)
    assert res["is_passed"] is False
    assert any("field 'bootstrap_mean'" in f and "Tolerances violated" in f for f in res["failures"])


def test_perturb_bootstrap_standard_error_only_fails(tmp_path, canonical_stats_data):
    """Adversarial: Modifying ONLY bootstrap_standard_error beyond tolerance triggers failure."""
    data = copy.deepcopy(canonical_stats_data)
    # Target 2025_batters_vs_non_selected: expected se ~ 0.991038
    orig = data["comparisons"][1]["bootstrap_standard_error"]
    data["comparisons"][1]["bootstrap_standard_error"] = orig + 0.02

    p = tmp_path / "bad_se.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_statistical_precision(stats_path=p)
    assert res["is_passed"] is False
    assert any("field 'bootstrap_standard_error'" in f and "Tolerances violated" in f for f in res["failures"])


def test_perturb_observed_effect_only_fails(tmp_path, canonical_stats_data):
    """Adversarial: Modifying ONLY observed_effect beyond tolerance triggers failure."""
    data = copy.deepcopy(canonical_stats_data)
    orig = data["comparisons"][2]["observed_effect"]
    data["comparisons"][2]["observed_effect"] = orig + 0.05

    p = tmp_path / "bad_effect.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_statistical_precision(stats_path=p)
    assert res["is_passed"] is False
    assert any("field 'observed_effect'" in f and "Tolerances violated" in f for f in res["failures"])


def test_perturb_ci_lower_endpoint_only_fails(tmp_path, canonical_stats_data):
    """Adversarial: Modifying ONLY ci_95_low beyond tolerance triggers failure."""
    data = copy.deepcopy(canonical_stats_data)
    orig = data["comparisons"][3]["ci_95_low"]
    data["comparisons"][3]["ci_95_low"] = orig - 0.10

    p = tmp_path / "bad_ci_low.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_statistical_precision(stats_path=p)
    assert res["is_passed"] is False
    assert any("field 'ci_95_low'" in f and "Tolerances violated" in f for f in res["failures"])


def test_perturb_ci_upper_endpoint_only_fails(tmp_path, canonical_stats_data):
    """Adversarial: Modifying ONLY ci_95_high beyond tolerance triggers failure."""
    data = copy.deepcopy(canonical_stats_data)
    orig = data["comparisons"][4]["ci_95_high"]
    data["comparisons"][4]["ci_95_high"] = orig + 0.10

    p = tmp_path / "bad_ci_high.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_statistical_precision(stats_path=p)
    assert res["is_passed"] is False
    assert any("field 'ci_95_high'" in f and "Tolerances violated" in f for f in res["failures"])


def test_perturb_raw_p_value_only_fails(tmp_path, canonical_stats_data):
    """Adversarial: Modifying ONLY raw_p_value beyond tolerance triggers failure."""
    data = copy.deepcopy(canonical_stats_data)
    orig = data["comparisons"][5]["raw_p_value"]
    data["comparisons"][5]["raw_p_value"] = orig + 0.005

    p = tmp_path / "bad_raw_p.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_statistical_precision(stats_path=p)
    assert res["is_passed"] is False
    assert any("field 'raw_p_value'" in f and "Tolerances violated" in f for f in res["failures"])


def test_perturb_holm_adjusted_p_only_fails(tmp_path, canonical_stats_data):
    """Adversarial: Modifying ONLY holm_adjusted_p beyond tolerance triggers failure."""
    data = copy.deepcopy(canonical_stats_data)
    orig = data["comparisons"][6]["holm_adjusted_p"]
    data["comparisons"][6]["holm_adjusted_p"] = orig + 0.01

    p = tmp_path / "bad_holm_p.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_statistical_precision(stats_path=p)
    assert res["is_passed"] is False
    assert any("field 'holm_adjusted_p'" in f and "Tolerances violated" in f for f in res["failures"])
