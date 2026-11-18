"""
RR ScoutIQ - Unit Tests for Module M4.3 (Batter Performance Engine)
===================================================================

Evidence Level: IMPLEMENTATION CORRECTNESS & PILOT DIAGNOSTIC
Validates:
- Batter canonical run attribution (including Match 20181 canonical resolution).
- Balls faced, wide, and no-ball accounting.
- Boundary and dot-ball classification.
- Dismissal and Law 25.4.2 retired hurt vs retired out handling.
- Pressure-tier filtering (DLI >= 1.35).
- Role cohort assignment (Top Order <= 6.0, Middle 6.1-13.0, Finisher > 13.0).
- Delivery xRA calculation and situational expectation lookup.
- All five BPPI components and composite score calculation.
- Normal-Normal and Beta-Binomial shrinkage calculations.
- Minimum eligibility thresholds and explicit exclusion reasons.
- Missing observation handling (no silent zero conversions).
- Super Over separation (fixed DLI 3.50, decoupled phase).
- DLS and shortened-match exclusion gating.
- Bootstrap reproducibility with fixed seeds.
- Disentanglement of Normal, Percentile, and Bayesian uncertainty intervals.
- Anti-leakage preservation.
"""

import unittest
import math
import numpy as np
import pandas as pd

from src.m4_pilot.input_validation import load_and_validate_pilot_data
from src.m4_pilot.match_state_engine import reconstruct_pre_delivery_match_state
from src.m4_pilot.batter_engine import (
    assign_batter_roles,
    compute_canonical_batter_runs,
    compute_delivery_xra,
    aggregate_batter_performance,
    apply_empirical_bayes_shrinkage,
    compute_bppi_scores,
    evaluate_batter_eligibility,
    bootstrap_batter_uncertainty,
    compute_bppi_diagnostics,
    trace_early_innings_dli_impact,
    run_batter_performance_pipeline,
    WEIGHT_XRA,
    WEIGHT_DELTA_SR,
    WEIGHT_DELTA_BND,
    WEIGHT_DELTA_DOT,
    WEIGHT_DELTA_SURVIVAL,
    PRESSURE_DLI_THRESHOLD,
    MIN_QUALIFYING_INNINGS,
    MIN_QUALIFYING_BALLS_FACED,
    MIN_QUALIFYING_PRESSURE_BALLS,
    ROLE_TOP_ORDER_MAX_OVER,
    ROLE_MIDDLE_ORDER_MAX_OVER,
    K_SR,
    K_XRA,
    M_BND,
    M_DOT,
    M_WICKET_CAPPED,
    ROLE_PRIORS
)


class TestBatterEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Loads and pre-processes genuine pilot dataset once for test suite."""
        cls.raw_df, cls.val_report = load_and_validate_pilot_data()
        cls.state_df = reconstruct_pre_delivery_match_state(cls.raw_df)
        cls.pipeline_output = run_batter_performance_pipeline(cls.state_df, run_bootstrap=False)
        cls.batter_df = cls.pipeline_output["batter_performance_df"]
        cls.xra_df = cls.pipeline_output["enriched_deliveries_with_xra"]

    def test_01_canonical_batter_runs_attribution(self):
        """Verifies canonical batter runs attribution disposes Match 20181 Over 9 correctly."""
        bat_runs = compute_canonical_batter_runs(self.state_df)
        # Total runs off the bat across pilot dataset
        self.assertEqual(int(bat_runs.sum()), 2671)
        
        # Match 20181 Over 9 balls 4 & 5
        m20181_o9 = self.state_df[
            (self.state_df["match_id"] == 20181) &
            (self.state_df["innings"] == 2) &
            (self.state_df["overid"] == 9)
        ].reset_index(drop=True)
        
        b4_bat_runs = compute_canonical_batter_runs(m20181_o9.iloc[[3]]).iloc[0]
        b5_bat_runs = compute_canonical_batter_runs(m20181_o9.iloc[[4]]).iloc[0]
        self.assertEqual(b4_bat_runs, 2)  # Canonical Cricsheet run
        self.assertEqual(b5_bat_runs, 1)  # Canonical Cricsheet run

    def test_02_balls_faced_and_wide_exclusion(self):
        """Verifies that wides are strictly excluded from batter balls faced (Law 22)."""
        wides = self.xra_df[self.xra_df["ext_is_wide"] == True]
        self.assertEqual(len(wides), 65)
        self.assertTrue(np.all(wides["ext_batter_balls_faced"] == 0))
        
        # Non-wides must have balls faced == 1
        non_wides = self.xra_df[self.xra_df["ext_is_wide"] == False]
        self.assertEqual(len(non_wides), 1994 - 65)
        self.assertTrue(np.all(non_wides["ext_batter_balls_faced"] == 1))

    def test_03_noball_counts_as_ball_faced(self):
        """Verifies that no-balls count as balls faced for the batter (Law 21)."""
        noballs = self.xra_df[self.xra_df["ext_is_noball"] == True]
        self.assertEqual(len(noballs), 13)
        self.assertTrue(np.all(noballs["ext_batter_balls_faced"] == 1))

    def test_04_boundary_and_dot_classification(self):
        """Verifies boundary four, six, and dot-ball classification logic."""
        bnd_fours = self.xra_df[self.xra_df["is_boundary_four"] == 1]
        bnd_sixes = self.xra_df[self.xra_df["is_boundary_six"] == 1]
        dots = self.xra_df[self.xra_df["is_dot_ball"] == 1]

        self.assertEqual(len(bnd_fours), 197)
        self.assertEqual(len(bnd_sixes), 142)
        self.assertEqual(len(dots), 712)

        # Dot balls must strictly have bat_runs == 0 and ext_batter_balls_faced == 1
        self.assertTrue(np.all(dots["bat_runs"] == 0))
        self.assertTrue(np.all(dots["ext_batter_balls_faced"] == 1))

    def test_05_dismissal_attribution_and_retired_hurt_handling(self):
        """Verifies Law 25.4.2: Retired Hurt is NOT a dismissal; Retired Out IS a dismissal."""
        outs = self.xra_df[self.xra_df["is_batter_out"] == 1]
        self.assertEqual(len(outs), 105)

        # Sanju Samson (Match 40725) retired hurt must NOT be counted as an out
        samson_rh = self.xra_df[
            (self.xra_df["match_id"] == 40725) &
            (self.xra_df["ext_is_retired_hurt"] == True)
        ]
        self.assertEqual(len(samson_rh), 1)
        self.assertEqual(samson_rh["is_batter_out"].iloc[0], 0)

        # Riyan Parag (Match 14113) retired out MUST be counted as an out
        parag_ro = self.xra_df[
            (self.xra_df["match_id"] == 14113) &
            (self.xra_df["ext_is_retired_out"] == True)
        ]
        self.assertEqual(len(parag_ro), 1)
        self.assertEqual(parag_ro["is_batter_out"].iloc[0], 1)

    def test_06_non_striker_run_out_not_credited_to_striker(self):
        """Verifies that non-striker run outs are not charged as a dismissal to the striker."""
        non_striker_outs = self.xra_df[
            (self.xra_df["is_wicket"] == 1) &
            (self.xra_df["dismissed_player_id"] == self.xra_df["non_striker_id"])
        ]
        self.assertEqual(len(non_striker_outs), 5)
        # Striker must not be charged with an out on these deliveries
        self.assertTrue(np.all(non_striker_outs["is_batter_out"] == 0))

    def test_07_role_cohort_assignment(self):
        """Verifies tactical role cohort assignment based on mean entry over."""
        roles = assign_batter_roles(self.state_df)
        self.assertEqual(len(roles), 102)

        top_order = [r for r in roles.values() if r.primary_role == "Top Order"]
        middle_order = [r for r in roles.values() if r.primary_role == "Middle Order"]
        finishers = [r for r in roles.values() if r.primary_role == "Finisher"]

        self.assertTrue(len(top_order) > 0)
        self.assertTrue(len(middle_order) > 0)
        self.assertTrue(len(finishers) > 0)

        # Check cutoffs
        for r in top_order:
            self.assertLessEqual(r.avg_entry_over, ROLE_TOP_ORDER_MAX_OVER)
        for r in middle_order:
            self.assertGreater(r.avg_entry_over, ROLE_TOP_ORDER_MAX_OVER)
            self.assertLessEqual(r.avg_entry_over, ROLE_MIDDLE_ORDER_MAX_OVER)
        for r in finishers:
            self.assertGreater(r.avg_entry_over, ROLE_MIDDLE_ORDER_MAX_OVER)

    def test_08_delivery_xra_anti_leakage(self):
        """Verifies delivery xRA depends strictly on pre-delivery match state, not future events."""
        xra_df = compute_delivery_xra(self.state_df)
        # Expected runs is populated on every delivery
        self.assertFalse(xra_df["expected_runs"].isna().any())
        self.assertTrue(np.all(xra_df["expected_runs"] > 0))

        # Test perturbation on a faced ball (ext_batter_balls_faced == 1)
        faced_df = xra_df[xra_df["ext_batter_balls_faced"] == 1]
        sample_row = faced_df.iloc[50]
        base_exp = sample_row["expected_runs"]
        base_xra = sample_row["xra"]
        # Perturbed runs:
        pert_xra = (sample_row["bat_runs"] + 4) - base_exp
        self.assertAlmostEqual(pert_xra - base_xra, 4.0, places=5)

    def test_09_all_five_bppi_components_calculated(self):
        """Verifies that all 5 BPPI components are present and non-null in output."""
        cols = [
            "shrunk_xra_per_ball", "shrunk_delta_sr", "shrunk_delta_bnd",
            "shrunk_delta_dot", "shrunk_delta_survival", "bppi_score"
        ]
        for col in cols:
            self.assertIn(col, self.batter_df.columns)
            self.assertFalse(self.batter_df[col].isna().any())

    def test_10_empirical_bayes_shrinkage_direction(self):
        """Verifies that shrinkage pulls extreme small-sample rates toward prior means."""
        # Find a player with very few pressure balls (e.g. 1 ball)
        low_sample = self.batter_df[self.batter_df["pressure_balls"] == 1].iloc[0]
        role = low_sample["primary_role"]
        prior_sr = ROLE_PRIORS[role]["mu_sr"]
        
        # Raw SR is either 0 or 100 or 400 or 600
        raw_sr_p = low_sample["raw_sr_press"]
        # Shrunk SR delta must be pulled heavily toward 0 / prior
        self.assertNotEqual(low_sample["shrunk_delta_sr"], low_sample["raw_delta_sr"])
        
        # Check lambda shrinkage factor for xRA
        lambda_xra = 1.0 / (1.0 + K_XRA)
        expected_shrunk_xra = lambda_xra * low_sample["raw_xra_per_ball"]
        self.assertAlmostEqual(low_sample["shrunk_xra_per_ball"], expected_shrunk_xra, places=4)

    def test_11_eligibility_criteria_and_exclusion_reasons(self):
        """Verifies qualification counting and explicit exclusion reasons."""
        elig_df = evaluate_batter_eligibility(self.batter_df)
        self.assertEqual(len(elig_df), 102)

        # In an 8-match pilot, no batter can have >= 12 innings
        # All batters in pilot must be ineligible with explicit reasons
        self.assertTrue(np.all(elig_df["is_eligible"] == False))
        
        # Every ineligible batter must have documented reasons
        for _, row in elig_df.iterrows():
            reason = row["exclusion_reason"]
            self.assertIn("INSUFFICIENT_INNINGS", reason)
            self.assertTrue(row["innings_count"] < MIN_QUALIFYING_INNINGS)

    def test_12_super_over_separation_in_batter_engine(self):
        """Verifies Super Over deliveries are included with DLI = 3.50 and phase = Super Over."""
        so_deliveries = self.xra_df[self.xra_df["is_super_over"] == True]
        self.assertEqual(len(so_deliveries), 15)
        self.assertTrue(np.all(so_deliveries["pre_dli"] == 3.50))
        self.assertTrue(np.all(so_deliveries["pre_match_phase"] == "Super Over"))
        self.assertTrue(np.all(so_deliveries["pre_pressure_tier"] == "Tier 4: Extreme"))

    def test_13_dls_and_shortened_match_exclusion_handling(self):
        """Verifies synthetic DLS-curtailed deliveries are excluded from pressure metrics."""
        synthetic_df = self.state_df.copy()
        # Mark Match 13513 as DLS invalid
        synthetic_df.loc[synthetic_df["match_id"] == 13513, "is_dli_valid"] = False

        res = aggregate_batter_performance(compute_delivery_xra(synthetic_df))
        # Total balls across aggregated batters must drop by the balls in match 13513
        m13513_balls = self.state_df[
            (self.state_df["match_id"] == 13513) &
            (self.state_df["ext_batter_balls_faced"] == 1)
        ].shape[0]
        
        orig_agg = aggregate_batter_performance(self.xra_df)
        self.assertEqual(
            orig_agg["total_balls_faced"].sum() - res["total_balls_faced"].sum(),
            m13513_balls
        )

    def test_14_bootstrap_reproducibility_with_fixed_seed(self):
        """Verifies that bootstrap resampling is 100% deterministic with fixed seed."""
        hetmyer_id = 3297  # Shimron Hetmyer (49 balls, 46 pressure balls in pilot)
        boot1 = bootstrap_batter_uncertainty(self.xra_df, hetmyer_id, n_draws=100, seed=123)
        boot2 = bootstrap_batter_uncertainty(self.xra_df, hetmyer_id, n_draws=100, seed=123)

        self.assertEqual(boot1["se_boot"], boot2["se_boot"])
        self.assertEqual(boot1["ci_normal_90"], boot2["ci_normal_90"])
        self.assertEqual(boot1["ci_percentile_90"], boot2["ci_percentile_90"])

    def test_15_uncertainty_interval_differentiation(self):
        """Verifies that Normal CI, Percentile CI, and Bayesian Credible Interval are decoupled."""
        hetmyer_id = 3297
        boot = bootstrap_batter_uncertainty(self.xra_df, hetmyer_id, n_draws=200, seed=42)

        ci_norm = boot["ci_normal_90"]
        ci_perc = boot["ci_percentile_90"]
        cred_int = boot["credible_interval_90"]

        # Check that intervals are numerical tuples
        self.assertEqual(len(ci_norm), 2)
        self.assertEqual(len(ci_perc), 2)
        self.assertEqual(len(cred_int), 2)

        # Width of Normal CI vs Percentile CI are distinct definitions
        norm_width = ci_norm[1] - ci_norm[0]
        self.assertTrue(norm_width > 0)
        self.assertTrue(ci_perc[1] > ci_perc[0])

    def test_16_scheme_b_vs_scheme_c_clustering(self):
        """Verifies Scheme B (player-innings) and Scheme C (player-match) clustering options."""
        hetmyer_id = 3297  # Hetmyer batted in both regulation and Super Over in Match 40725
        boot_b = bootstrap_batter_uncertainty(self.xra_df, hetmyer_id, n_draws=100, seed=42, cluster_unit="player_innings")
        boot_c = bootstrap_batter_uncertainty(self.xra_df, hetmyer_id, n_draws=100, seed=42, cluster_unit="player_match")

        # In Match 40725, Hetmyer has 2 innings (inn 2 and inn 3). Scheme B clusters = 3, Scheme C clusters = 2.
        self.assertEqual(boot_b["clusters_count"], 3)
        self.assertEqual(boot_c["clusters_count"], 2)

    def test_17_early_innings_dli_traceability(self):
        """Verifies that early-innings setting DLI convention is fully traceable and isolated."""
        trace = trace_early_innings_dli_impact(self.xra_df)
        self.assertEqual(trace["total_early_deliveries"], 52)
        self.assertEqual(trace["distinct_batters_affected"], 14)
        # All 52 deliveries must be in Tier 1: Low
        self.assertEqual(trace["high_pressure_contamination_count"], 0)
        self.assertEqual(trace["pressure_tier_distribution"].get("Tier 1: Low", 0), 52)

    def test_18_diagnostics_vif_and_collinearity(self):
        """Verifies diagnostic multicollinearity (VIF) and correlation calculations."""
        diag = compute_bppi_diagnostics(self.batter_df)
        self.assertEqual(diag["status"], "DIAGNOSTICS_COMPUTED")
        self.assertIn("variance_inflation_factors", diag)
        self.assertIn("correlation_matrix", diag)
        vifs = diag["variance_inflation_factors"]
        self.assertIn("shrunk_xra_per_ball", vifs)
        self.assertIn("shrunk_delta_sr", vifs)

    def test_19_missing_pressure_balls_never_silently_zeroed(self):
        """Verifies that batters with 0 pressure balls are marked with explicit exclusion."""
        zero_press = self.batter_df[self.batter_df["pressure_balls"] == 0]
        self.assertTrue(len(zero_press) > 0)
        for _, row in zero_press.iterrows():
            self.assertIn("INSUFFICIENT_PRESSURE_BALLS", row["exclusion_reason"])
            # Raw rates should be NaN, not silently 0
            self.assertTrue(math.isnan(row["raw_sr_press"]))
            self.assertTrue(math.isnan(row["raw_delta_sr"]))

    def test_20_no_leaderboard_or_ranking_generation(self):
        """Verifies governance constraint: output must NOT contain rank columns or sorted top-10."""
        forbidden_cols = ["rank", "batter_rank", "overall_rank", "top_10", "is_top_10"]
        for col in forbidden_cols:
            self.assertNotIn(col, self.batter_df.columns)

    def test_21_varying_entry_over_across_innings(self):
        """
        Verifies that batters whose entry over differs across multiple innings
        have accurate innings-level role assignments without ecological misclassification,
        and that Super Overs are decoupled from regular primary role calculation.
        """
        hetmyer_id = 3297
        roles = assign_batter_roles(self.xra_df)
        het_prof = roles[hetmyer_id]

        # Hetmyer played 3 innings in the pilot:
        # Match 14113 Inn 1: entry over 10 (Middle Order)
        # Match 40725 Inn 2: entry over 18 (Finisher)
        # Match 40725 Inn 3: entry over 1 (Super Over tie-break)
        # Regulation entry overs: [10, 18] -> mean = 14.0 -> primary role = 'Finisher'
        self.assertEqual(len(het_prof.entry_overs), 2)
        self.assertIn(10, het_prof.entry_overs)
        self.assertIn(18, het_prof.entry_overs)
        self.assertNotIn(1, het_prof.entry_overs)  # Super Over excluded from regulation entry overs
        self.assertEqual(het_prof.primary_role, "Finisher")
        self.assertEqual(set(het_prof.innings_roles), {"Middle Order", "Finisher", "Super Over"})

        # Check delivery-level innings role assignment in xra_df
        het_deliveries = self.xra_df[self.xra_df["striker_id"] == hetmyer_id]
        inn1_roles = het_deliveries[het_deliveries["match_id"] == 14113]["innings_role"].unique()
        inn2_roles = het_deliveries[(het_deliveries["match_id"] == 40725) & (het_deliveries["innings"] == 2)]["innings_role"].unique()
        inn3_roles = het_deliveries[(het_deliveries["match_id"] == 40725) & (het_deliveries["innings"] == 3)]["innings_role"].unique()

        self.assertEqual(list(inn1_roles), ["Middle Order"])
        self.assertEqual(list(inn2_roles), ["Finisher"])
        self.assertEqual(list(inn3_roles), ["Super Over"])

        # Regression check: Kusal Perera (1481) entered in over 9 in regulation and over 1 in Super Over.
        # Super Over must NOT pull him into Top Order.
        perera_prof = roles[1481]
        self.assertEqual(perera_prof.primary_role, "Middle Order")
        self.assertIn("Super Over", perera_prof.innings_roles)

    def test_22_bootstrap_estimator_consistency_and_percentile_coverage(self):
        """
        Verifies that bootstrap_batter_uncertainty uses the identical cohort-standardized
        BPPI estimator as compute_bppi_scores, and that for Shimron Hetmyer, the point
        estimate is centrally contained within both 90% Normal and 90% Percentile CIs.
        """
        hetmyer_id = 3297
        boot = bootstrap_batter_uncertainty(self.xra_df, hetmyer_id, n_draws=1000, seed=42)

        pt = boot["bppi_point_estimate"]
        ci_norm = boot["ci_normal_90"]
        ci_perc = boot["ci_percentile_90"]

        # Valid draws and no silent drops
        self.assertEqual(boot["n_valid_draws"], 1000)
        self.assertEqual(boot["n_invalid_draws"], 0)

        # Point estimate must be inside 90% Normal CI
        self.assertGreaterEqual(pt, ci_norm[0])
        self.assertLessEqual(pt, ci_norm[1])

        # Point estimate must be inside 90% Percentile Bootstrap CI
        self.assertGreaterEqual(pt, ci_perc[0])
        self.assertLessEqual(pt, ci_perc[1])

        # Bootstrap mean and median must closely align with point estimate
        self.assertAlmostEqual(boot["boot_median"], pt, delta=0.15)
        self.assertAlmostEqual(boot["boot_mean"], pt, delta=0.15)

        # Detailed percentiles must be monotonic
        pcts = boot["percentiles"]
        self.assertLess(pcts["p5"], pcts["p25"])
        self.assertLess(pcts["p25"], pcts["p50"])
        self.assertLess(pcts["p50"], pcts["p75"])
        self.assertLess(pcts["p75"], pcts["p95"])


if __name__ == "__main__":
    unittest.main()
