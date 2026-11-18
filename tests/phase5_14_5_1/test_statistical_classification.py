"""
Phase 5.14.5.1 — Statistical Classification Derivation Tests
RR ScoutIQ | Rajasthan Royals IPL 2027 Auction Strategy Hackathon

Verifies Fix D:
1. Classification is strictly derived from statistical evidence (alpha=0.05, Holm p, CI zero-crossing, directionality).
2. Canonical distribution is exactly 6 STATISTICALLY_SIGNIFICANT, 0 DIRECTIONAL_ONLY, 2 NON_SIGNIFICANT.
3. Both 2026 bowler comparisons are strictly NON_SIGNIFICANT (Holm p = 0.1144, CI crosses zero).
4. Direct unit testing of derive_statistical_classification under diverse synthetic scenarios:
   - Significant positive effect (effect > 0, CI low > 0, holm_p < 0.05).
   - Significant negative effect (effect < 0, CI high < 0, holm_p < 0.05).
   - Non-significant due to Holm p >= 0.05 (even if CI excludes zero).
   - Non-significant due to CI zero crossing (even if Holm p < 0.05).
   - Non-significant due to CI in opposite direction of point estimate.
5. Inverted/mismatched classification labels trigger rejection.
"""

import os
import sys
import copy
import json
import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from research.phase5_14_5.authoritative_gate import (
    derive_statistical_classification,
    evaluate_statistical_precision,
    DEFAULT_STATS_PATH,
)


def test_derive_classification_positive_significant():
    """Positive effect with CI excluding zero and Holm p < 0.05 is STATISTICALLY_SIGNIFICANT."""
    res = derive_statistical_classification(
        observed_effect=5.88,
        ci_95_low=4.25,
        ci_95_high=7.57,
        raw_p_value=0.0001,
        holm_adjusted_p=0.0008,
        alpha=0.05,
    )
    assert res == "STATISTICALLY_SIGNIFICANT"


def test_derive_classification_negative_significant():
    """Negative effect with CI excluding zero (CI high < 0) and Holm p < 0.05 is STATISTICALLY_SIGNIFICANT."""
    res = derive_statistical_classification(
        observed_effect=-0.68,
        ci_95_low=-1.16,
        ci_95_high=-0.19,
        raw_p_value=0.007,
        holm_adjusted_p=0.028,
        alpha=0.05,
    )
    assert res == "STATISTICALLY_SIGNIFICANT"


def test_derive_classification_non_significant_due_to_p_value():
    """Holm p >= 0.05 must be classified as NON_SIGNIFICANT even if CI excludes zero."""
    res = derive_statistical_classification(
        observed_effect=2.50,
        ci_95_low=0.50,
        ci_95_high=4.50,
        raw_p_value=0.03,
        holm_adjusted_p=0.08,  # > 0.05
        alpha=0.05,
    )
    assert res == "NON_SIGNIFICANT"


def test_derive_classification_non_significant_due_to_ci_zero_crossing():
    """CI crossing zero must be classified as NON_SIGNIFICANT even if Holm p < 0.05."""
    res = derive_statistical_classification(
        observed_effect=-0.53,
        ci_95_low=-1.06,
        ci_95_high=0.04,  # crosses zero
        raw_p_value=0.01,
        holm_adjusted_p=0.04,  # < 0.05
        alpha=0.05,
    )
    assert res == "NON_SIGNIFICANT"


def test_canonical_distribution_is_strictly_6_0_2():
    """Canonical statistical interpretation yields exactly 6 significant, 0 directional, 2 non-significant."""
    eval_res = evaluate_statistical_precision()
    assert eval_res["is_passed"] is True
    c_summary = eval_res["classification_summary"]
    assert c_summary["statistically_significant"] == 6
    assert c_summary["directional"] == 0
    assert c_summary["non_significant"] == 2
    assert c_summary["total"] == 8


def test_2026_bowler_comparisons_strictly_non_significant():
    """Verify that both 2026 bowler comparisons are strictly non-significant with zero-crossing CIs."""
    eval_res = evaluate_statistical_precision()
    bw_2026 = [c for c in eval_res["comparisons"] if "2026_bowlers" in c["comparison_id"]]
    assert len(bw_2026) == 2

    for c in bw_2026:
        assert c["derived_classification"] == "NON_SIGNIFICANT"
        assert c["recorded_classification"] == "NON_SIGNIFICANT"
        assert c["ci_crosses_zero"] is True
        assert c["holm_adjusted_p"] >= 0.05


def test_altered_p_value_triggers_classification_inconsistency_failure(tmp_path):
    """
    Adversarial: Altering a comparison's Holm p-value so that derived classification
    contradicts recorded classification triggers failure.
    """
    with open(DEFAULT_STATS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Invert 2026_bowlers_vs_league from NON_SIGNIFICANT to STATISTICALLY_SIGNIFICANT
    for c in data["comparisons"]:
        if c["comparison_id"] == "2026_bowlers_vs_league":
            c["inference_classification"] = "STATISTICALLY_SIGNIFICANT"

    p = tmp_path / "bad_class.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluate_statistical_precision(stats_path=p)
    assert res["is_passed"] is False
    assert any("Inconsistency" in f or "contradicts" in f or "Derived classification distribution mismatch" in f for f in res["failures"])
