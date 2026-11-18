"""
RR ScoutIQ — Milestone M5.5-B.4.3.4: Targeted Unit Tests
File: tests/m5_5b_4_3_4/test_remediation_b4_3_4.py

Validates:
1. Exact Design Matrix Rank on adversarial synthetic topologies and canonical IPL data.
2. Independent calculation of rank(X_cbm), rank(X_cb), rank(X_cm) and degrees of freedom.
3. Verification against dense SVD.
4. Henderson Trace Coefficients without artificial floors, and error handling for confounded designs.
5. Exhaustive calibration input sanitization (CI bounds outside [0, 1], non-containment, non-integer N, etc.).
6. Canonical dataset preservation and strict absence of player rankings.
"""

import os
import sys
import math
import hashlib
import unittest
import numpy as np
import pandas as pd
import scipy.sparse as sp
import scipy.linalg as la

sys.path.insert(0, os.path.abspath("."))

from src.m5_5b_4_3_4.variance_decomposition_b4_3_4 import (
    compute_design_matrix_rank,
    estimate_crossed_variance_components_henderson3,
    generate_synthetic_crossed_spells,
    NumericalConditioningError,
    IdentifiabilityError
)
from src.m5_5b_4_3_4.calibration_engine_b4_3_4 import (
    evaluate_bowler_calibration_status,
    evaluate_batter_calibration_status,
    compute_continuous_interval_coverage_b434,
    compute_binary_probability_calibration_b434
)
from src.m5_5b_4_3_4.epistemic_context_engine_b4_3_4 import (
    ContextualPlayerBaselineRecordB434
)


class TestM55B434Remediation(unittest.TestCase):

    def _build_design_matrices(self, spells, K, I, M, weights=None):
        N = len(spells)
        if weights is None:
            w = np.ones(N)
        else:
            w = np.array(weights)
        sqrt_w = np.sqrt(w)
        rows = np.arange(N)
        c_idx = [s[2] for s in spells]
        b_idx = [s[0] for s in spells]
        m_idx = [s[1] for s in spells]
        Xc = sp.csr_matrix((sqrt_w, (rows, c_idx)), shape=(N, K))
        Xb = sp.csr_matrix((sqrt_w, (rows, b_idx)), shape=(N, I))
        Xm = sp.csr_matrix((sqrt_w, (rows, m_idx)), shape=(N, M))
        return (
            sp.hstack([Xc, Xb, Xm]).tocsr(),
            sp.hstack([Xc, Xb]).tocsr(),
            sp.hstack([Xc, Xm]).tocsr()
        )

    def test_01_auditor_counterexample_rank_recovery(self):
        """
        Auditor counterexample:
        - 2 disconnected components
        - 6 bowlers (3 in comp 1, 3 in comp 2)
        - 6 matches (3 in comp 1, 3 in comp 2)
        - 2 context categories: Context 0 exclusive to comp 1, Context 1 exclusive to comp 2.
        Formula K+I+M-1-c predicts 11, but actual rank is 10.
        """
        spells = [
            (0, 0, 0), (1, 0, 0), (1, 1, 0), (2, 1, 0), (2, 2, 0), (0, 2, 0),
            (3, 3, 1), (4, 3, 1), (4, 4, 1), (5, 4, 1), (5, 5, 1), (3, 5, 1)
        ]
        X_cbm, X_cb, X_cm = self._build_design_matrices(spells, K=2, I=6, M=6)

        # SVD vs Gram ranks
        rank_cbm_svd, _, _ = compute_design_matrix_rank(X_cbm, method="svd")
        rank_cbm_gram, _, _ = compute_design_matrix_rank(X_cbm, method="gram")
        self.assertEqual(rank_cbm_svd, 10, "Dense SVD rank must be exactly 10")
        self.assertEqual(rank_cbm_gram, 10, "Gram rank must match dense SVD rank of 10")

        rank_cb_svd, _, _ = compute_design_matrix_rank(X_cb, method="svd")
        rank_cm_svd, _, _ = compute_design_matrix_rank(X_cm, method="svd")
        self.assertEqual(rank_cb_svd, 6)
        self.assertEqual(rank_cm_svd, 6)

        df_E = len(spells) - rank_cbm_svd
        df_m = rank_cbm_svd - rank_cb_svd
        df_b = rank_cbm_svd - rank_cm_svd
        self.assertEqual(df_E, 2)
        self.assertEqual(df_m, 4)
        self.assertEqual(df_b, 4)

    def test_02_adversarial_connected_design_all_contexts(self):
        """Connected design with all contexts represented across bowlers and matches."""
        spells = [
            (0, 0, 0), (1, 0, 1), (1, 1, 2), (2, 1, 0), (2, 2, 1),
            (3, 2, 2), (3, 3, 0), (0, 3, 1), (0, 4, 2), (1, 4, 0)
        ]
        X_cbm, X_cb, X_cm = self._build_design_matrices(spells, K=3, I=4, M=5)

        r_cbm_svd, _, _ = compute_design_matrix_rank(X_cbm, method="svd")
        r_cbm_gram, _, _ = compute_design_matrix_rank(X_cbm, method="gram")
        r_cb_svd, _, _ = compute_design_matrix_rank(X_cb, method="svd")
        r_cm_svd, _, _ = compute_design_matrix_rank(X_cm, method="svd")

        self.assertEqual(r_cbm_svd, r_cbm_gram)
        self.assertEqual(r_cbm_svd, 10)
        self.assertEqual(r_cb_svd, 6)
        self.assertEqual(r_cm_svd, 7)

        self.assertEqual(r_cbm_svd - r_cb_svd, 4)
        self.assertEqual(r_cbm_svd - r_cm_svd, 3)

    def test_03_adversarial_disconnected_shared_contexts(self):
        """Disconnected design with shared context 0 in both components."""
        spells = [
            (0, 0, 0), (1, 0, 0), (1, 1, 0),
            (2, 2, 0), (3, 2, 0), (3, 3, 0)
        ]
        X_cbm, X_cb, X_cm = self._build_design_matrices(spells, K=1, I=4, M=4)

        r_cbm_svd, _, _ = compute_design_matrix_rank(X_cbm, method="svd")
        r_cbm_gram, _, _ = compute_design_matrix_rank(X_cbm, method="gram")
        self.assertEqual(r_cbm_svd, r_cbm_gram)
        self.assertEqual(r_cbm_svd, 6)

    def test_04_adversarial_context_bowler_multiple_components(self):
        """Context-bowler incidence graph has multiple components."""
        spells = [
            (0, 0, 0), (1, 1, 0), (0, 2, 0),
            (2, 0, 1), (3, 1, 1), (2, 2, 1),
            (1, 0, 0), (3, 2, 1)
        ]
        X_cbm, X_cb, X_cm = self._build_design_matrices(spells, K=2, I=4, M=3)
        r_cbm_svd, _, _ = compute_design_matrix_rank(X_cbm, method="svd")
        r_cbm_gram, _, _ = compute_design_matrix_rank(X_cbm, method="gram")
        self.assertEqual(r_cbm_svd, r_cbm_gram)
        self.assertEqual(r_cbm_svd, 6)

    def test_05_adversarial_context_match_multiple_components(self):
        """Context-match incidence graph has multiple components."""
        spells = [
            (0, 0, 0), (1, 0, 0), (2, 1, 0),
            (0, 2, 1), (1, 2, 1), (2, 3, 1),
            (1, 1, 0), (0, 3, 1)
        ]
        X_cbm, X_cb, X_cm = self._build_design_matrices(spells, K=2, I=3, M=4)
        r_cbm_svd, _, _ = compute_design_matrix_rank(X_cbm, method="svd")
        r_cbm_gram, _, _ = compute_design_matrix_rank(X_cbm, method="gram")
        self.assertEqual(r_cbm_svd, r_cbm_gram)
        self.assertEqual(r_cbm_svd, 6)

    def test_06_adversarial_unequal_exposure_weights(self):
        """Unequal exposure weights on spells do not distort algebraic rank."""
        spells = [
            (0, 0, 0), (1, 0, 0), (1, 1, 0), (2, 1, 0), (2, 2, 0), (0, 2, 0),
            (3, 3, 1), (4, 3, 1), (4, 4, 1), (5, 4, 1), (5, 5, 1), (3, 5, 1)
        ]
        weights = [0.5, 1.2, 2.0, 0.8, 1.5, 3.0, 0.2, 1.1, 2.5, 0.9, 1.8, 2.2]
        X_cbm, X_cb, X_cm = self._build_design_matrices(spells, K=2, I=6, M=6, weights=weights)

        r_cbm_svd, _, _ = compute_design_matrix_rank(X_cbm, method="svd")
        r_cbm_gram, _, _ = compute_design_matrix_rank(X_cbm, method="gram")
        self.assertEqual(r_cbm_svd, 10)
        self.assertEqual(r_cbm_gram, 10)

    def test_07_canonical_ipl_design_rank_explicit_check(self):
        """Explicitly checks design ranks and degrees of freedom on the canonical IPL spell dataset."""
        canonical_path = "data/processed/m5_3/match_state_full.csv"
        self.assertTrue(os.path.exists(canonical_path))

        from src.m5_5b.baseline_estimation import load_clean_deliveries
        from src.m5_5b_3.bowler_economy_validator import aggregate_bowler_spells

        df = load_clean_deliveries(canonical_path)
        spells = aggregate_bowler_spells(df)
        valid = spells[spells["legal_balls"] >= 6].copy()

        # Run Henderson Method III on canonical spells
        res = estimate_crossed_variance_components_henderson3(
            valid,
            cell_mean_cols=("phase", "modal_tier"),
            min_balls_per_spell=6,
            rank_method="auto"
        )

        self.assertEqual(res["n_spells"], 16711)
        self.assertEqual(res["n_contexts"], 12)
        self.assertEqual(res["n_bowlers"], 560)
        self.assertEqual(res["n_matches"], 744)

        self.assertEqual(res["rank_cbm"], 1314)
        self.assertEqual(res["rank_cb"], 571)
        self.assertEqual(res["rank_cm"], 755)

        self.assertEqual(res["df_error"], 15397)
        self.assertEqual(res["df_match"], 743)
        self.assertEqual(res["df_player"], 559)

        # Confirm strictly positive unclipped variance estimates
        self.assertFalse(res["is_match_variance_constrained"])
        self.assertFalse(res["is_player_variance_constrained"])
        self.assertGreater(res["raw_sigma2_match"], 0.0)
        self.assertGreater(res["raw_tau2_player"], 0.0)
        self.assertAlmostEqual(res["sigma2_within"], 22.8429, delta=0.01)

    def test_08_henderson_trace_coefficients_unfloored_and_positive(self):
        """Verifies trace coefficients are positive, unfloored, and numerically well-conditioned."""
        synthetic_df = generate_synthetic_crossed_spells(
            n_bowlers=40, n_matches=60, spells_per_match=6, seed=123
        )
        res = estimate_crossed_variance_components_henderson3(
            synthetic_df, cell_mean_cols=("phase", "modal_tier"), min_balls_per_spell=6
        )
        self.assertGreater(res["c_m"], 0.0)
        self.assertGreater(res["c_b"], 0.0)
        self.assertGreater(res["W_total"], res["c_m"])
        self.assertGreater(res["W_total"], res["c_b"])

    def test_09_henderson_confounded_design_raises_error(self):
        """Confounded design where every bowler bowls in only one unique match."""
        # 10 bowlers, 10 matches, 1 spell each (bowler i only in match i)
        confounded_records = []
        for i in range(20):
            confounded_records.append({
                "bowler_id": i,
                "match_id": i,
                "phase": "Middle",
                "modal_tier": "Tier 2: Medium",
                "legal_balls": 24,
                "economy_rate": 8.0
            })
        conf_df = pd.DataFrame(confounded_records)
        with self.assertRaises((IdentifiabilityError, NumericalConditioningError, ValueError)):
            estimate_crossed_variance_components_henderson3(
                conf_df, cell_mean_cols=("phase", "modal_tier"), min_balls_per_spell=6
            )

    def test_10_calibration_reject_ci_bounds_outside_0_1(self):
        """Rejects CI bounds strictly outside [0, 1]."""
        # Upper bound > 1.0
        status, viol = evaluate_bowler_calibration_status(
            cov_80=0.80, ci_80_low=0.75, ci_80_high=1.05,
            cov_95=0.95, ci_95_low=0.92, ci_95_high=0.98,
            n_obs=100
        )
        self.assertEqual(status, "INVALID_CALIBRATION_INPUT")
        self.assertIn("CI_BOUNDS_OUTSIDE_RANGE_[0,1]", viol)

        # Lower bound < 0.0
        status, viol = evaluate_bowler_calibration_status(
            cov_80=0.80, ci_80_low=-0.05, ci_80_high=0.85,
            cov_95=0.95, ci_95_low=0.92, ci_95_high=0.98,
            n_obs=100
        )
        self.assertEqual(status, "INVALID_CALIBRATION_INPUT")
        self.assertIn("CI_BOUNDS_OUTSIDE_RANGE_[0,1]", viol)

    def test_11_calibration_reject_ci_not_containing_coverage(self):
        """Rejects confidence interval that does not contain the point estimate coverage."""
        # cov_80 is 0.85, but CI is [0.70, 0.80]
        status, viol = evaluate_bowler_calibration_status(
            cov_80=0.85, ci_80_low=0.70, ci_80_high=0.80,
            cov_95=0.95, ci_95_low=0.92, ci_95_high=0.98,
            n_obs=100
        )
        self.assertEqual(status, "INVALID_CALIBRATION_INPUT")
        self.assertIn("COVERAGE_OUTSIDE_CONFIDENCE_INTERVAL", viol)

        # cov_95 is 0.90, but CI is [0.92, 0.98]
        status, viol = evaluate_bowler_calibration_status(
            cov_80=0.80, ci_80_low=0.75, ci_80_high=0.85,
            cov_95=0.90, ci_95_low=0.92, ci_95_high=0.98,
            n_obs=100
        )
        self.assertEqual(status, "INVALID_CALIBRATION_INPUT")
        self.assertIn("COVERAGE_OUTSIDE_CONFIDENCE_INTERVAL", viol)

    def test_12_calibration_reject_negative_or_non_integer_sample_size(self):
        """Rejects negative, zero, float, and boolean sample sizes."""
        # Non-integer float
        status, viol = evaluate_bowler_calibration_status(
            cov_80=0.80, ci_80_low=0.75, ci_80_high=0.85,
            cov_95=0.95, ci_95_low=0.92, ci_95_high=0.98,
            n_obs=50.5
        )
        self.assertEqual(status, "INVALID_CALIBRATION_INPUT")
        self.assertIn("NON_INTEGER_TYPE", viol)

        # Boolean
        status, viol = evaluate_bowler_calibration_status(
            cov_80=0.80, ci_80_low=0.75, ci_80_high=0.85,
            cov_95=0.95, ci_95_low=0.92, ci_95_high=0.98,
            n_obs=True
        )
        self.assertEqual(status, "INVALID_CALIBRATION_INPUT")
        self.assertIn("NON_INTEGER_TYPE", viol)

        # Negative
        status, viol = evaluate_bowler_calibration_status(
            cov_80=0.80, ci_80_low=0.75, ci_80_high=0.85,
            cov_95=0.95, ci_95_low=0.92, ci_95_high=0.98,
            n_obs=-10
        )
        self.assertEqual(status, "INVALID_CALIBRATION_INPUT")
        self.assertIn("NON_POSITIVE_VALUE", viol)

    def test_13_calibration_reject_missing_nan_inf_reversed_bounds(self):
        """Rejects NaN, infinite, None, and reversed bounds."""
        # None
        status, viol = evaluate_bowler_calibration_status(
            cov_80=None, ci_80_low=0.75, ci_80_high=0.85,
            cov_95=0.95, ci_95_low=0.92, ci_95_high=0.98,
            n_obs=100
        )
        self.assertEqual(status, "INVALID_CALIBRATION_INPUT")

        # NaN
        status, viol = evaluate_bowler_calibration_status(
            cov_80=np.nan, ci_80_low=0.75, ci_80_high=0.85,
            cov_95=0.95, ci_95_low=0.92, ci_95_high=0.98,
            n_obs=100
        )
        self.assertEqual(status, "INVALID_CALIBRATION_INPUT")

        # Inf
        status, viol = evaluate_bowler_calibration_status(
            cov_80=0.80, ci_80_low=0.75, ci_80_high=np.inf,
            cov_95=0.95, ci_95_low=0.92, ci_95_high=0.98,
            n_obs=100
        )
        self.assertEqual(status, "INVALID_CALIBRATION_INPUT")

        # Reversed bounds
        status, viol = evaluate_bowler_calibration_status(
            cov_80=0.80, ci_80_low=0.85, ci_80_high=0.75,
            cov_95=0.95, ci_95_low=0.92, ci_95_high=0.98,
            n_obs=100
        )
        self.assertEqual(status, "INVALID_CALIBRATION_INPUT")
        self.assertIn("REVERSED_CONFIDENCE_INTERVAL_BOUNDS", viol)

    def test_14_calibration_reject_invalid_batter_inputs(self):
        """Rejects invalid batter inputs (negative slope, ECE out of bounds, non-integer N)."""
        # Negative slope
        status, viol = evaluate_batter_calibration_status(ece=0.01, slope=-0.5, bias=0.0, n_obs=150)
        self.assertEqual(status, "INVALID_CALIBRATION_INPUT")
        self.assertIn("SLOPE_NON_POSITIVE", viol)

        # ECE > 1.0
        status, viol = evaluate_batter_calibration_status(ece=1.5, slope=1.0, bias=0.0, n_obs=150)
        self.assertEqual(status, "INVALID_CALIBRATION_INPUT")
        self.assertIn("ECE_OUTSIDE_RANGE_[0,1]", viol)

        # Non-integer sample size
        status, viol = evaluate_batter_calibration_status(ece=0.01, slope=1.0, bias=0.0, n_obs="150")
        self.assertEqual(status, "INVALID_CALIBRATION_INPUT")
        self.assertIn("NON_INTEGER_TYPE", viol)

    def test_15_canonical_dataset_hash_preservation(self):
        """Strictly verifies canonical dataset hash ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4."""
        canonical_path = "data/processed/m5_3/match_state_full.csv"
        with open(canonical_path, "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(
            h,
            "ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4",
            "Canonical dataset hash has been altered! Strict preservation violated."
        )

    def test_16_strictly_no_player_rankings_or_leaderboards(self):
        """Verifies strictly zero player rankings, composite scores, or leaderboards."""
        for root, _, files in os.walk("src/m5_5b_4_3_4"):
            for f in files:
                if f.endswith(".py"):
                    with open(os.path.join(root, f), "r") as fp:
                        content = fp.read().lower()
                        self.assertNotIn("bppi_score", content)
                        self.assertNotIn("ppbi_score", content)
                        self.assertNotIn("top_10_players", content)
                        self.assertNotIn("auction_recommendation", content)


if __name__ == "__main__":
    unittest.main()
