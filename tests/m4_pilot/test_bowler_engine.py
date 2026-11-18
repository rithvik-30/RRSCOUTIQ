"""
RR ScoutIQ - Unit Tests for Module M4.4 (Bowler Performance Engine)
===================================================================

Evidence Level: IMPLEMENTATION CORRECTNESS & PILOT DIAGNOSTIC
Validates:
- Bowler debit runs attribution (strictly charges ext_bowler_debit_runs, excluding byes/leg-byes).
- Legal delivery accounting (wides and no-balls are illegal; byes and leg-byes are legal).
- Wicket attribution (credits direct modes: Bowled, Caught, LBW, Stumped, Hit Wicket; excludes Run Out, Retired Out, Retired Hurt).
- Boundary concession and dot-ball classification.
- Pressure-tier filtering (DLI >= 1.35).
- Bowling role classification (Powerplay Specialist >= 40%, Death Specialist >= 30%, Middle Enforcer remainder).
- Multi-role overlap resolution (workload dominance).
- Delivery xRS calculation and situational expectation lookup.
- All five PPBI components and composite score calculation.
- Normal-Normal and Beta-Binomial shrinkage calculations.
- Minimum eligibility thresholds (>=12 inn, >=144 legal balls, >=42 pressure balls) and explicit exclusion reasons.
- Missing observation handling (no silent zero conversions).
- Super Over separation (fixed DLI 3.50, decoupled phase, excluded from regulation role split).
- DLS and shortened-match exclusion gating.
- Bootstrap reproducibility with fixed seeds (Scheme B player-innings).
- Disentanglement of Normal, Percentile, and Bayesian uncertainty intervals.
- Anti-leakage preservation.
"""

import unittest
import math
import numpy as np
import pandas as pd

from src.m4_pilot.input_validation import load_and_validate_pilot_data
from src.m4_pilot.match_state_engine import reconstruct_pre_delivery_match_state
from src.m4_pilot.bowler_engine import (
    assign_bowler_roles,
    compute_delivery_xrs,
    aggregate_bowler_performance,
    apply_empirical_bayes_shrinkage,
    compute_ppbi_scores,
    evaluate_bowler_eligibility,
    bootstrap_bowler_uncertainty,
    compute_ppbi_diagnostics,
    trace_early_innings_dli_impact,
    run_bowler_performance_pipeline,
    ROLE_PRIORS,
    EMPIRICAL_RUN_EXPECTATIONS,
    WEIGHT_XRS,
    WEIGHT_DELTA_ECON,
    WEIGHT_DELTA_WKT,
    WEIGHT_DELTA_DOT,
    WEIGHT_DELTA_BND_CON,
    PRESSURE_DLI_THRESHOLD,
    MIN_QUALIFYING_INNINGS,
    MIN_QUALIFYING_LEGAL_BALLS,
    MIN_QUALIFYING_PRESSURE_BALLS
)


class TestBowlerEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Loads and pre-processes genuine pilot dataset once for test suite."""
        cls.raw_df, cls.val_report = load_and_validate_pilot_data()
        cls.state_df = reconstruct_pre_delivery_match_state(cls.raw_df)
        cls.pipeline_output = run_bowler_performance_pipeline(cls.state_df, run_bootstrap=False)
        cls.bowler_df = cls.pipeline_output["bowler_performance_df"]
        cls.xrs_df = cls.pipeline_output["enriched_deliveries_with_xrs"]

    def test_01_bowler_debit_runs_accounting(self):
        """Verifies bowler runs debit uses ext_bowler_debit_runs and excludes byes/legbyes/penalties."""
        # Total bowler debit runs across pilot
        total_bowler_debit = self.xrs_df["ext_bowler_debit_runs"].sum()
        total_innings_runs = self.xrs_df["ext_delivery_total_runs"].sum()
        total_byes = self.xrs_df["ext_bye_runs"].sum()
        total_legbyes = self.xrs_df["ext_legbye_runs"].sum()

        self.assertEqual(int(total_bowler_debit), 2767)
        self.assertEqual(int(total_innings_runs), 2802)
        # Difference must equal uncharged extras (byes + legbyes)
        self.assertEqual(int(total_innings_runs - total_bowler_debit), int(total_byes + total_legbyes))

    def test_02_legal_delivery_accounting(self):
        """Verifies that wides and no-balls are illegal, while byes and legbyes are legal."""
        legal_balls = self.xrs_df[self.xrs_df["ext_is_legal_delivery"] == True]
        illegal_balls = self.xrs_df[self.xrs_df["ext_is_legal_delivery"] == False]

        self.assertEqual(len(legal_balls), 1916)
        self.assertEqual(len(illegal_balls), 78)  # 65 wides + 13 no-balls

        # Wides and no-balls must be in illegal balls
        self.assertTrue((illegal_balls["ext_is_wide"] | illegal_balls["ext_is_noball"]).all())
        # Legal balls must have zero wides and no-balls
        self.assertTrue((~legal_balls["ext_is_wide"] & ~legal_balls["ext_is_noball"]).all())

    def test_03_wicket_attribution_direct_modes_only(self):
        """Verifies bowler credit applies strictly to direct dismissals (Bowled, Caught, LBW, Stumped, Hit Wicket)."""
        # Bowler wickets
        bowler_wkts = self.xrs_df[self.xrs_df["is_bowler_wicket_final"] == 1]
        self.assertEqual(len(bowler_wkts), 100)

        # Check dismissal modes credited
        credited_types = set(bowler_wkts["dismissal_type"].unique())
        self.assertTrue(credited_types.issubset({"Bowled", "Caught", "LBW", "Stump", "Stumped", "Hit Wicket"}))

        # Run outs must NOT be credited to the bowler
        run_outs = self.xrs_df[self.xrs_df["dismissal_type"] == "RunOut"]
        self.assertEqual(len(run_outs), 9)
        self.assertEqual(int(run_outs["is_bowler_wicket_final"].sum()), 0)

        # Retired Out must NOT be credited to the bowler
        ret_out = self.xrs_df[self.xrs_df["dismissal_type"] == "Retire Out"]
        self.assertEqual(len(ret_out), 1)
        self.assertEqual(int(ret_out["is_bowler_wicket_final"].sum()), 0)

    def test_04_retired_hurt_not_a_wicket(self):
        """Verifies Law 25.4.2: Retired Hurt is NOT a wicket and never credited to bowler."""
        ret_hurt = self.xrs_df[self.xrs_df["ext_is_retired_hurt"] == True]
        self.assertEqual(len(ret_hurt), 1)  # Sanju Samson, Match 40725
        self.assertEqual(int(ret_hurt["is_bowler_wicket_final"].sum()), 0)

    def test_05_boundary_concession_and_dot_ball_classification(self):
        """Verifies dot-ball (0 bowler debit runs on legal ball) and boundary concession classification."""
        legal_df = self.xrs_df[self.xrs_df["ext_is_legal_delivery"] == True]

        # Dots
        dots = legal_df[legal_df["is_bowler_dot"] == 1]
        self.assertEqual(len(dots), 705)
        self.assertTrue((dots["ext_bowler_debit_runs"] == 0).all())

        # Boundaries conceded (4s and 6s)
        bnds = legal_df[legal_df["is_boundary_conceded"] == 1]
        self.assertEqual(len(bnds), 335)  # 195 fours + 140 sixes

    def test_06_role_cohort_assignment_and_super_over_isolation(self):
        """Verifies bowling role classification on regulation overs and Super Over isolation."""
        roles = assign_bowler_roles(self.state_df)
        self.assertEqual(len(roles), 74)

        # Starc: 24 PP, 0 Mid, 24 Death in regulation -> PP 50%, Death 50%
        # Super Over (5 balls) must NOT count toward PP or Death workload!
        starc = roles[829]
        self.assertEqual(starc.powerplay_balls, 24)
        self.assertEqual(starc.death_balls, 24)
        self.assertEqual(starc.total_legal_balls, 48)  # Exactly 48 regulation balls
        self.assertEqual(starc.primary_role, "Powerplay Specialist")  # Tie-break dominance PP >= Death

        # Varun Chakravarthy: 12 PP, 48 Mid, 12 Death -> Middle Enforcer
        vc = roles[6256]
        self.assertEqual(vc.middle_balls, 48)
        self.assertEqual(vc.primary_role, "Middle Enforcer")

        # Jason Holder: 18 PP, 12 Mid, 18 Death -> PP 37.5%, Death 37.5% -> Death Specialist (Death >= 30%)
        jh = roles[2633]
        self.assertEqual(jh.primary_role, "Death Specialist")

    def test_07_delivery_xrs_anti_leakage(self):
        """Verifies delivery xRS depends strictly on pre-delivery match state, not future outcomes."""
        legal_delivs = self.state_df[self.state_df["ext_is_legal_delivery"] == True]
        sample_deliv = legal_delivs.iloc[[0]].copy()
        xrs_orig = compute_delivery_xrs(sample_deliv).iloc[0]["xrs"]

        # Perturb current delivery outcome (e.g. add 6 runs conceded)
        perturbed_deliv = sample_deliv.copy()
        perturbed_deliv["ext_bowler_debit_runs"] = sample_deliv["ext_bowler_debit_runs"].iloc[0] + 6
        xrs_perturbed = compute_delivery_xrs(perturbed_deliv).iloc[0]["xrs"]

        # Expected runs conceded must remain invariant
        self.assertEqual(
            compute_delivery_xrs(sample_deliv).iloc[0]["expected_runs_conceded"],
            compute_delivery_xrs(perturbed_deliv).iloc[0]["expected_runs_conceded"]
        )
        # xRS differs by exactly 6 runs conceded
        self.assertAlmostEqual(xrs_orig - xrs_perturbed, 6.0, places=4)

    def test_08_all_five_ppbi_components_calculated(self):
        """Verifies that all 5 PPBI components are present and non-null in output."""
        expected_cols = [
            "shrunk_xrs_per_ball",
            "shrunk_delta_econ",
            "shrunk_delta_wkt",
            "shrunk_delta_dot",
            "shrunk_delta_bnd_con",
            "z_xrs",
            "z_delta_econ",
            "z_delta_wkt",
            "z_delta_dot",
            "z_delta_bnd_con",
            "ppbi_score"
        ]
        for col in expected_cols:
            self.assertIn(col, self.bowler_df.columns)
            self.assertEqual(self.bowler_df[col].isna().sum(), 0)

    def test_09_empirical_bayes_shrinkage_direction(self):
        """Verifies that shrinkage pulls extreme small-sample rates toward prior means."""
        # Bowler with very few pressure balls (e.g. 6 balls)
        small_sample_b = self.bowler_df[self.bowler_df["pressure_legal_balls"] == 6].iloc[0]
        # xRS shrunk must be closer to 0 than raw xRS
        self.assertLess(abs(small_sample_b["shrunk_xrs_per_ball"]), abs(small_sample_b["raw_xrs_per_ball"]))

    def test_10_sign_conventions_mathematically_positive_good(self):
        """Verifies that positive PPBI components strictly represent better bowling performance."""
        # Higher runs saved -> positive z_xrs
        # Better economy containment (lower pressure economy) -> positive z_delta_econ
        # Higher wicket breakthrough -> positive z_delta_wkt
        # More dots forced -> positive z_delta_dot
        # Fewer boundaries conceded -> positive z_delta_bnd_con
        top_bowler = self.bowler_df[self.bowler_df["bowler_id"] == 781].iloc[0]  # Sunil Narine
        self.assertGreater(top_bowler["shrunk_xrs_per_ball"], 0.0)  # Saved runs
        self.assertGreater(top_bowler["shrunk_delta_bnd_con"], 0.0)  # Restricted boundaries (0 boundaries)

    def test_11_eligibility_criteria_and_exclusion_reasons(self):
        """Verifies qualification counting and explicit exclusion reasons for all unqualified bowlers."""
        self.assertIn("is_eligible", self.bowler_df.columns)
        self.assertIn("exclusion_reason", self.bowler_df.columns)

        # In 8-match pilot, no bowler has >=12 innings
        self.assertEqual(self.bowler_df["is_eligible"].sum(), 0)
        for _, row in self.bowler_df.iterrows():
            self.assertFalse(row["is_eligible"])
            self.assertIn("INSUFFICIENT_INNINGS", row["exclusion_reason"])

    def test_12_super_over_separation_in_bowler_engine(self):
        """Verifies Super Over deliveries are included with DLI = 3.50 and phase = Super Over."""
        so_delivs = self.xrs_df[self.xrs_df["is_super_over"] == True]
        self.assertEqual(len(so_delivs), 15)  # Matches 40725 and 34429 Super Overs (Innings 3 & 4)
        self.assertTrue((so_delivs["pre_dli"] == 3.50).all())
        self.assertTrue((so_delivs["pre_match_phase"] == "Super Over").all())

    def test_13_dls_and_shortened_match_exclusion_handling(self):
        """Verifies synthetic DLS-curtailed deliveries are excluded from pressure metrics."""
        synthetic_dls_df = self.state_df.copy()
        synthetic_dls_df.loc[synthetic_dls_df["match_id"] == 14094, "is_dls_curtailed"] = True
        synthetic_dls_df.loc[synthetic_dls_df["match_id"] == 14094, "is_dli_valid"] = False

        res = run_bowler_performance_pipeline(synthetic_dls_df)
        b_df = res["bowler_performance_df"]

        # Bowlers from match 14094 should have 0 pressure balls from that match
        vc = b_df[b_df["bowler_id"] == 6256].iloc[0]
        # Normally VC has 45 pressure balls (12 in 14094, 21 in 30058, 12 in 40037)
        # When 14094 is excluded, he must have 45 - 12 = 33 pressure balls
        self.assertEqual(vc["pressure_legal_balls"], 33)

    def test_14_bootstrap_reproducibility_with_fixed_seed(self):
        """Verifies that bootstrap resampling is 100% deterministic with fixed seed."""
        b1 = bootstrap_bowler_uncertainty(self.xrs_df, target_bowler_id=6256, n_draws=100, seed=42)
        b2 = bootstrap_bowler_uncertainty(self.xrs_df, target_bowler_id=6256, n_draws=100, seed=42)
        self.assertEqual(b1["ppbi_point_estimate"], b2["ppbi_point_estimate"])
        self.assertEqual(b1["se_boot"], b2["se_boot"])
        self.assertEqual(b1["percentiles"], b2["percentiles"])

    def test_15_uncertainty_interval_differentiation(self):
        """Verifies that Normal CI, Percentile CI, and Bayesian Credible Interval are decoupled."""
        b = bootstrap_bowler_uncertainty(self.xrs_df, target_bowler_id=6256, n_draws=200, seed=42)
        ci_norm = b["ci_normal_90"]
        ci_perc = b["ci_percentile_90"]
        ci_bayes = b["credible_interval_90"]

        self.assertIsInstance(ci_norm, tuple)
        self.assertIsInstance(ci_perc, tuple)
        self.assertIsInstance(ci_bayes, tuple)
        # Bayesian credible interval width reflects prior tau shrinkage
        self.assertNotEqual(ci_norm, ci_bayes)

    def test_16_scheme_b_vs_scheme_c_clustering(self):
        """Verifies Scheme B (player-innings) and Scheme C (player-match) clustering options."""
        b_scheme_b = bootstrap_bowler_uncertainty(self.xrs_df, target_bowler_id=829, n_draws=100, seed=42, cluster_unit="player_innings")
        b_scheme_c = bootstrap_bowler_uncertainty(self.xrs_df, target_bowler_id=829, n_draws=100, seed=42, cluster_unit="player_match")

        # Starc played Match 40725 regulation (inn 2) AND super over (inn 3)
        # Scheme B has 3 clusters (Match 30058 inn 2, Match 40725 inn 2, Match 40725 inn 3)
        # Scheme C has 2 clusters (Match 30058, Match 40725)
        self.assertEqual(b_scheme_b["clusters_count"], 3)
        self.assertEqual(b_scheme_c["clusters_count"], 2)

    def test_17_early_innings_dli_traceability(self):
        """Verifies that early-innings setting DLI convention is fully traceable and isolated."""
        trace = trace_early_innings_dli_impact(self.xrs_df)
        self.assertEqual(trace["status"], "EARLY_DLI_TRACED")
        self.assertEqual(trace["total_early_setting_deliveries"], 48)  # Exactly 48 legal deliveries
        self.assertEqual(trace["high_pressure_contamination_count"], 0)
        self.assertTrue(trace["is_cleanly_isolated"])

    def test_18_diagnostics_vif_and_collinearity(self):
        """Verifies diagnostic multicollinearity (VIF) and correlation calculations."""
        diag = compute_ppbi_diagnostics(self.bowler_df)
        self.assertEqual(diag["status"], "DIAGNOSTICS_COMPUTED")
        vifs = diag["variance_inflation_factors"]
        # All VIFs should be non-null and finite
        for col, vif in vifs.items():
            self.assertTrue(pd.notna(vif))
            self.assertGreater(vif, 0.0)

    def test_19_missing_pressure_balls_never_silently_zeroed(self):
        """Verifies that bowlers with 0 pressure balls are marked with explicit exclusion."""
        zero_press = self.bowler_df[self.bowler_df["pressure_legal_balls"] == 0]
        self.assertGreater(len(zero_press), 0)
        for _, row in zero_press.iterrows():
            self.assertFalse(row["is_eligible"])
            self.assertIn("INSUFFICIENT_PRESSURE_BALLS (0/42)", row["exclusion_reason"])

    def test_20_no_leaderboard_or_ranking_generation(self):
        """Verifies governance constraint: output must NOT contain rank columns or sorted top-10."""
        for forbidden in ["rank", "ppbi_rank", "overall_rank", "top_10", "is_top_10"]:
            self.assertNotIn(forbidden, self.bowler_df.columns)
        # Raw index must match original bowler_id order, not sorted by ppbi_score
        is_sorted = self.bowler_df["ppbi_score"].is_monotonic_decreasing
        self.assertFalse(is_sorted)

    def test_21_starc_super_over_wicket_and_role_decoupling(self):
        """Verifies Mitchell Starc's role is based strictly on regulation innings and Super Over is decoupled."""
        starc = self.bowler_df[self.bowler_df["bowler_id"] == 829].iloc[0]
        # In regulation, Starc bowled 24 PP and 24 Death (48 total) -> PP Specialist (dominant)
        self.assertEqual(starc["primary_role"], "Powerplay Specialist")
        # In full match state including Super Over, Starc bowled 53 legal balls
        self.assertEqual(starc["total_legal_balls"], 53)

    def test_22_bootstrap_estimator_consistency(self):
        """Verifies that bootstrap_bowler_uncertainty uses identical cohort-standardized estimator."""
        boot = bootstrap_bowler_uncertainty(self.xrs_df, target_bowler_id=6256, n_draws=50, seed=42)
        # Point estimate must be non-null and match baseline
        pt = self.bowler_df[self.bowler_df["bowler_id"] == 6256]["ppbi_score"].iloc[0]
        self.assertAlmostEqual(boot["ppbi_point_estimate"], pt, places=3)


if __name__ == "__main__":
    unittest.main()
