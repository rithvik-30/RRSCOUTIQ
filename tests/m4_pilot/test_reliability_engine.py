"""
RR ScoutIQ - Unit Test Suite: Module M4.5 Reliability & Ranking Engine
======================================================================
Comprehensive verification of player reliability assessment, provisional eligibility
evaluations, explainable 4-tier reliability classifications, role-aware ranking dossiers,
deterministic tie-breaking, uncertainty simulations, and governance constraints.
"""

import unittest
import math
import numpy as np
import pandas as pd

from src.m4_pilot.input_validation import load_and_validate_pilot_data
from src.m4_pilot.match_state_engine import reconstruct_pre_delivery_match_state
from src.m4_pilot.batter_engine import run_batter_performance_pipeline
from src.m4_pilot.bowler_engine import run_bowler_performance_pipeline
from src.m4_pilot.reliability_engine import (
    ReliabilityTier,
    PlayerReliabilityAssessment,
    RoleRankingDossier,
    evaluate_player_eligibility,
    classify_reliability_tier,
    compute_batter_attribution,
    compute_bowler_attribution,
    assess_batter_reliability,
    assess_bowler_reliability,
    generate_role_rankings,
    simulate_ranking_stability_across_draws,
    run_reliability_ranking_pipeline,
    BATTER_MIN_INNINGS,
    BATTER_MIN_BALLS_FACED,
    BATTER_MIN_PRESSURE_BALLS,
    BOWLER_MIN_INNINGS,
    BOWLER_MIN_LEGAL_BALLS,
    BOWLER_MIN_PRESSURE_LEGAL_BALLS,
    RELIABILITY_HIGH_CONF_PRESS_BALLS_BATTER,
    RELIABILITY_HIGH_CONF_PRESS_BALLS_BOWLER,
    RELIABILITY_HIGH_CONF_MIN_CLUSTERS,
    RELIABILITY_HIGH_CONF_MAX_SE
)


class TestReliabilityEngine(unittest.TestCase):
    """Test suite for Module M4.5 Reliability & Ranking Engine."""

    @classmethod
    def setUpClass(cls):
        """Loads and pre-processes genuine pilot dataset once for test suite."""
        cls.raw_df, cls.val_report = load_and_validate_pilot_data()
        cls.state_df = reconstruct_pre_delivery_match_state(cls.raw_df)
        cls.b_results = run_batter_performance_pipeline(cls.state_df, run_bootstrap=False)
        cls.bw_results = run_bowler_performance_pipeline(cls.state_df, run_bootstrap=False)
        cls.batter_df = cls.b_results["batter_performance_df"]
        cls.bowler_df = cls.bw_results["bowler_performance_df"]

    # -----------------------------------------------------------------------
    # 1. Eligibility Boundary Tests
    # -----------------------------------------------------------------------

    def test_01_batter_eligibility_boundary_exact_cutoffs(self):
        """Verifies exact numerical boundary conditions for provisional batter eligibility."""
        # 1 below cutoffs
        ok, reasons = evaluate_player_eligibility("batter", 11, 120, 36)
        self.assertFalse(ok)
        self.assertTrue(any("INSUFFICIENT_INNINGS" in r for r in reasons))

        ok, reasons = evaluate_player_eligibility("batter", 12, 119, 36)
        self.assertFalse(ok)
        self.assertTrue(any("INSUFFICIENT_BALLS_FACED" in r for r in reasons))

        ok, reasons = evaluate_player_eligibility("batter", 12, 120, 35)
        self.assertFalse(ok)
        self.assertTrue(any("INSUFFICIENT_PRESSURE_BALLS" in r for r in reasons))

        # Exact match of all three criteria
        ok, reasons = evaluate_player_eligibility("batter", 12, 120, 36)
        self.assertTrue(ok)
        self.assertEqual(len(reasons), 0)

        # Well above cutoffs
        ok, reasons = evaluate_player_eligibility("batter", 20, 300, 100)
        self.assertTrue(ok)
        self.assertEqual(len(reasons), 0)

    def test_02_bowler_eligibility_boundary_exact_cutoffs(self):
        """Verifies exact numerical boundary conditions for provisional bowler eligibility."""
        # 1 below cutoffs
        ok, reasons = evaluate_player_eligibility("bowler", 11, 144, 42)
        self.assertFalse(ok)
        self.assertTrue(any("INSUFFICIENT_INNINGS" in r for r in reasons))

        ok, reasons = evaluate_player_eligibility("bowler", 12, 143, 42)
        self.assertFalse(ok)
        self.assertTrue(any("INSUFFICIENT_LEGAL_BALLS" in r for r in reasons))

        ok, reasons = evaluate_player_eligibility("bowler", 12, 144, 41)
        self.assertFalse(ok)
        self.assertTrue(any("INSUFFICIENT_PRESSURE_LEGAL_BALLS" in r for r in reasons))

        # Exact match of all three criteria
        ok, reasons = evaluate_player_eligibility("bowler", 12, 144, 42)
        self.assertTrue(ok)
        self.assertEqual(len(reasons), 0)

        # Well above cutoffs
        ok, reasons = evaluate_player_eligibility("bowler", 25, 400, 120)
        self.assertTrue(ok)
        self.assertEqual(len(reasons), 0)

    # -----------------------------------------------------------------------
    # 2. Missing & Corrupted Data Handling
    # -----------------------------------------------------------------------

    def test_03_missing_data_never_silently_zeroed(self):
        """Verifies that missing or invalid player data produces UNRESOLVED tier and explicit flags."""
        ok, reasons = evaluate_player_eligibility("batter", 15, 200, 50, has_valid_data=False)
        self.assertFalse(ok)
        self.assertIn("UNRESOLVED_OR_CORRUPTED_DATA", reasons)

        tier, note = classify_reliability_tier(
            is_eligible=True,
            has_valid_data=False,
            pressure_balls=50,
            cluster_count=10,
            bootstrap_se=0.20,
            player_type="batter"
        )
        self.assertEqual(tier, ReliabilityTier.UNRESOLVED_DATA_INCOMPLETE)

    def test_04_zero_pressure_exposure_handling(self):
        """Verifies that players with zero pressure exposure are flagged with insufficient pressure."""
        ok, reasons = evaluate_player_eligibility("batter", 14, 250, 0)
        self.assertFalse(ok)
        self.assertTrue(any("INSUFFICIENT_PRESSURE_BALLS (0 < 36)" in r for r in reasons))

        ok_bw, reasons_bw = evaluate_player_eligibility("bowler", 14, 250, 0)
        self.assertFalse(ok_bw)
        self.assertTrue(any("INSUFFICIENT_PRESSURE_LEGAL_BALLS (0 < 42)" in r for r in reasons_bw))

    # -----------------------------------------------------------------------
    # 3. Explainable 4-Tier Classification Tests
    # -----------------------------------------------------------------------

    def test_05_reliability_tier_distinction_high_vs_moderate_confidence(self):
        """Verifies distinction between High Confidence and Moderate Confidence tiers for eligible players."""
        # Batter: Meets eligibility, but small pressure sample (40 < 72) -> MODERATE
        tier_mod, _ = classify_reliability_tier(
            is_eligible=True,
            has_valid_data=True,
            pressure_balls=40,
            cluster_count=12,
            bootstrap_se=0.25,
            player_type="batter"
        )
        self.assertEqual(tier_mod, ReliabilityTier.ELIGIBLE_MODERATE_CONFIDENCE)

        # Batter: High pressure sample (80 >= 72), high clusters (10 >= 8), low SE (0.22 <= 0.35) -> HIGH
        tier_high, _ = classify_reliability_tier(
            is_eligible=True,
            has_valid_data=True,
            pressure_balls=80,
            cluster_count=10,
            bootstrap_se=0.22,
            player_type="batter"
        )
        self.assertEqual(tier_high, ReliabilityTier.ELIGIBLE_HIGH_CONFIDENCE)

        # Batter: High pressure balls but high SE (0.42 > 0.35) -> MODERATE
        tier_mod_se, _ = classify_reliability_tier(
            is_eligible=True,
            has_valid_data=True,
            pressure_balls=100,
            cluster_count=14,
            bootstrap_se=0.42,
            player_type="batter"
        )
        self.assertEqual(tier_mod_se, ReliabilityTier.ELIGIBLE_MODERATE_CONFIDENCE)

    def test_06_ineligible_tier_classification(self):
        """Verifies that failing eligibility always yields INELIGIBLE_INSUFFICIENT_SAMPLE tier."""
        tier, note = classify_reliability_tier(
            is_eligible=False,
            has_valid_data=True,
            pressure_balls=20,
            cluster_count=2,
            bootstrap_se=0.30,
            player_type="batter"
        )
        self.assertEqual(tier, ReliabilityTier.INELIGIBLE_INSUFFICIENT_SAMPLE)
        self.assertIn("Fails one or more provisional eligibility criteria", note)

    # -----------------------------------------------------------------------
    # 4. Decoupling Performance Score from Reliability
    # -----------------------------------------------------------------------

    def test_07_decoupling_high_score_from_reliability(self):
        """Verifies that a player with a massive score on tiny sample receives INELIGIBLE tier."""
        dummy_row = pd.Series({
            "striker_id": 99999,
            "striker_name": "Spectacular Fluke",
            "primary_role": "Finisher",
            "innings_count": 1,
            "total_balls_faced": 10,
            "pressure_balls": 10,
            "bppi_score": 3.85,  # extreme high score
            "z_xra": 3.5,
            "z_delta_sr": 3.2,
            "z_delta_bnd": 2.8,
            "z_delta_dot": 2.5,
            "z_delta_survival": 1.0
        })

        assessment = assess_batter_reliability(dummy_row)
        self.assertEqual(assessment.point_score, 3.85)
        self.assertFalse(assessment.is_eligible)
        self.assertEqual(assessment.reliability_tier, ReliabilityTier.INELIGIBLE_INSUFFICIENT_SAMPLE)
        self.assertEqual(len(assessment.exclusion_reasons), 3)

    # -----------------------------------------------------------------------
    # 5. Explainability Attribution Tests
    # -----------------------------------------------------------------------

    def test_08_batter_performance_attribution(self):
        """Verifies explainable positive and negative performance drivers for batters."""
        row = pd.Series({
            "z_xra": 1.5,
            "z_delta_sr": -0.8,
            "z_delta_bnd": 0.9,
            "z_delta_dot": -0.6,
            "z_delta_survival": 0.0
        })
        pos, neg = compute_batter_attribution(row)
        self.assertTrue(any("Expected Runs Added" in p for p in pos))
        self.assertTrue(any("Boundary Execution" in p for p in pos))
        self.assertTrue(any("Pressure Strike Rate" in n for n in neg))
        self.assertTrue(any("Dot Avoidance" in n for n in neg))

    def test_09_bowler_performance_attribution(self):
        """Verifies explainable positive and negative performance drivers for bowlers."""
        row = pd.Series({
            "z_xrs": 1.2,
            "z_delta_econ": -0.5,
            "z_delta_wkt": 1.8,
            "z_delta_dot": 0.0,
            "z_delta_bnd_con": -1.1
        })
        pos, neg = compute_bowler_attribution(row)
        self.assertTrue(any("Expected Runs Saved" in p for p in pos))
        self.assertTrue(any("Wicket Taking" in p for p in pos))
        self.assertTrue(any("Economy Containment" in n for n in neg))
        self.assertTrue(any("Boundary Suppression" in n for n in neg))

    # -----------------------------------------------------------------------
    # 6. Role-Aware Ranking Framework Tests
    # -----------------------------------------------------------------------

    def test_10_role_aware_ranking_segregation(self):
        """Verifies that rankings are constructed independently per role cohort."""
        p1 = PlayerReliabilityAssessment(
            player_id=1, player_name="P1", player_type="batter", primary_role="Top Order",
            innings_count=15, total_balls=200, pressure_balls=60, pressure_innings_count=15,
            cluster_count=15, is_eligible=True, exclusion_reasons=[],
            reliability_tier=ReliabilityTier.ELIGIBLE_MODERATE_CONFIDENCE,
            point_score=1.2, bootstrap_se=0.2, ci_percentile_90=(0.8, 1.5),
            ci_normal_90=(0.8, 1.5), credible_interval_90=(0.9, 1.4),
            attribution_positives=[], attribution_negatives=[],
            sample_summary="test", reliability_note="test"
        )
        p2 = PlayerReliabilityAssessment(
            player_id=2, player_name="P2", player_type="batter", primary_role="Finisher",
            innings_count=15, total_balls=150, pressure_balls=80, pressure_innings_count=15,
            cluster_count=15, is_eligible=True, exclusion_reasons=[],
            reliability_tier=ReliabilityTier.ELIGIBLE_HIGH_CONFIDENCE,
            point_score=1.8, bootstrap_se=0.15, ci_percentile_90=(1.5, 2.1),
            ci_normal_90=(1.5, 2.1), credible_interval_90=(1.6, 2.0),
            attribution_positives=[], attribution_negatives=[],
            sample_summary="test", reliability_note="test"
        )

        dossiers = generate_role_rankings([p1, p2], ranking_metric="point_score")
        self.assertIn("Top Order", dossiers)
        self.assertIn("Finisher", dossiers)
        self.assertEqual(len(dossiers["Top Order"].ranked_players), 1)
        self.assertEqual(dossiers["Top Order"].ranked_players[0]["player_id"], 1)
        self.assertEqual(dossiers["Top Order"].ranked_players[0]["rank"], 1)
        self.assertEqual(len(dossiers["Finisher"].ranked_players), 1)
        self.assertEqual(dossiers["Finisher"].ranked_players[0]["player_id"], 2)
        self.assertEqual(dossiers["Finisher"].ranked_players[0]["rank"], 1)

    def test_11_ineligible_player_exclusion_from_official_rankings(self):
        """Verifies that ineligible players are strictly excluded from ranked_players."""
        p_ineligible = PlayerReliabilityAssessment(
            player_id=99, player_name="Unqualified", player_type="batter", primary_role="Finisher",
            innings_count=2, total_balls=20, pressure_balls=10, pressure_innings_count=2,
            cluster_count=2, is_eligible=False, exclusion_reasons=["INSUFFICIENT_INNINGS"],
            reliability_tier=ReliabilityTier.INELIGIBLE_INSUFFICIENT_SAMPLE,
            point_score=2.5, bootstrap_se=0.8, ci_percentile_90=(1.0, 3.5),
            ci_normal_90=(1.0, 3.5), credible_interval_90=(1.5, 3.0),
            attribution_positives=[], attribution_negatives=[],
            sample_summary="test", reliability_note="test"
        )

        dossiers = generate_role_rankings([p_ineligible], allow_ineligible=False)
        finisher_dossier = dossiers["Finisher"]
        self.assertEqual(len(finisher_dossier.ranked_players), 0)
        self.assertEqual(len(finisher_dossier.ineligible_players), 1)
        self.assertEqual(finisher_dossier.ineligible_players[0]["player_id"], 99)

    def test_12_ranking_ties_deterministic_resolution(self):
        """Verifies that ties in score are broken deterministically by sample depth and player_id."""
        p1 = PlayerReliabilityAssessment(
            player_id=10, player_name="Tie A", player_type="batter", primary_role="Top Order",
            innings_count=15, total_balls=200, pressure_balls=50, pressure_innings_count=15,
            cluster_count=15, is_eligible=True, exclusion_reasons=[],
            reliability_tier=ReliabilityTier.ELIGIBLE_MODERATE_CONFIDENCE,
            point_score=1.50, bootstrap_se=0.2, ci_percentile_90=(1.1, 1.8),
            ci_normal_90=(1.1, 1.8), credible_interval_90=(1.2, 1.7),
            attribution_positives=[], attribution_negatives=[],
            sample_summary="test", reliability_note="test"
        )
        p2 = PlayerReliabilityAssessment(
            player_id=20, player_name="Tie B", player_type="batter", primary_role="Top Order",
            innings_count=15, total_balls=220, pressure_balls=65, pressure_innings_count=15,
            cluster_count=15, is_eligible=True, exclusion_reasons=[],
            reliability_tier=ReliabilityTier.ELIGIBLE_MODERATE_CONFIDENCE,
            point_score=1.50, bootstrap_se=0.2, ci_percentile_90=(1.1, 1.8),
            ci_normal_90=(1.1, 1.8), credible_interval_90=(1.2, 1.7),
            attribution_positives=[], attribution_negatives=[],
            sample_summary="test", reliability_note="test"
        )

        dossiers = generate_role_rankings([p1, p2], ranking_metric="point_score")
        ranked = dossiers["Top Order"].ranked_players
        # p2 has more pressure balls (65 > 50), so p2 should be rank 1
        self.assertEqual(ranked[0]["player_id"], 20)
        self.assertEqual(ranked[0]["rank"], 1)
        self.assertEqual(ranked[1]["player_id"], 10)
        self.assertEqual(ranked[1]["rank"], 2)

    def test_13_conservative_lower_bound_ranking_metric(self):
        """Verifies that lower_bound_90 ranking penalizes high uncertainty."""
        # Player A: Modest score (+1.2), high certainty (SE=0.1, 5% percentile = +1.0)
        pA = PlayerReliabilityAssessment(
            player_id=1, player_name="Consistent", player_type="bowler", primary_role="Death Specialist",
            innings_count=15, total_balls=200, pressure_balls=80, pressure_innings_count=15,
            cluster_count=15, is_eligible=True, exclusion_reasons=[],
            reliability_tier=ReliabilityTier.ELIGIBLE_HIGH_CONFIDENCE,
            point_score=1.20, bootstrap_se=0.10, ci_percentile_90=(1.00, 1.35),
            ci_normal_90=(1.00, 1.35), credible_interval_90=(1.05, 1.30),
            attribution_positives=[], attribution_negatives=[],
            sample_summary="test", reliability_note="test"
        )
        # Player B: Higher point score (+1.40), but huge uncertainty (SE=0.50, 5% percentile = +0.55)
        pB = PlayerReliabilityAssessment(
            player_id=2, player_name="Volatile", player_type="bowler", primary_role="Death Specialist",
            innings_count=15, total_balls=200, pressure_balls=50, pressure_innings_count=15,
            cluster_count=15, is_eligible=True, exclusion_reasons=[],
            reliability_tier=ReliabilityTier.ELIGIBLE_MODERATE_CONFIDENCE,
            point_score=1.40, bootstrap_se=0.50, ci_percentile_90=(0.55, 2.20),
            ci_normal_90=(0.55, 2.20), credible_interval_90=(0.80, 2.00),
            attribution_positives=[], attribution_negatives=[],
            sample_summary="test", reliability_note="test"
        )

        # Under point_score: Player B (1.40) beats Player A (1.20)
        d_point = generate_role_rankings([pA, pB], ranking_metric="point_score")
        self.assertEqual(d_point["Death Specialist"].ranked_players[0]["player_id"], 2)

        # Under lower_bound_90: Player A (+1.00) beats Player B (+0.55)
        d_lower = generate_role_rankings([pA, pB], ranking_metric="lower_bound_90")
        self.assertEqual(d_lower["Death Specialist"].ranked_players[0]["player_id"], 1)

    # -----------------------------------------------------------------------
    # 7. Uncertainty & Stability Simulation Tests
    # -----------------------------------------------------------------------

    def test_14_ranking_stability_simulation_reproducibility(self):
        """Verifies that rank stability simulation across draws computes valid distributions."""
        # Use 100 draws to satisfy min_required_draws
        d101 = [1.2, 1.3, 1.1, 1.25, 1.4] * 20
        d102 = [0.8, 0.9, 0.7, 0.85, 0.75] * 20
        d103 = [1.5, 1.4, 1.6, 1.55, 1.45] * 20
        draws = {101: d101, 102: d102, 103: d103}
        roles = {101: "Finisher", 102: "Finisher", 103: "Finisher"}

        stability = simulate_ranking_stability_across_draws(draws, roles, min_required_draws=100)
        # Player 103 always has highest score in each draw -> Rank 1
        self.assertEqual(stability[103]["median_rank"], 1)
        self.assertEqual(stability[103]["prob_top_3"], 1.0)
        self.assertEqual(stability[103]["prob_top_10"], 1.0)

        # Player 102 always has lowest score -> Rank 3
        self.assertEqual(stability[102]["median_rank"], 3)

        # Player 101 always in middle -> Rank 2
        self.assertEqual(stability[101]["median_rank"], 2)

    def test_21_lower_bound_90_unavailability_when_bootstrap_missing(self):
        """Verifies lower_bound_90 is marked UNAVAILABLE and NOT silently approximated when bootstrap missing."""
        p_no_boot = PlayerReliabilityAssessment(
            player_id=999, player_name="No Boot", player_type="batter", primary_role="Finisher",
            innings_count=15, total_balls=200, pressure_balls=60, pressure_innings_count=15,
            cluster_count=15, is_eligible=True, exclusion_reasons=[],
            reliability_tier=ReliabilityTier.ELIGIBLE_MODERATE_CONFIDENCE,
            point_score=1.50, bootstrap_se=np.nan, ci_percentile_90=(np.nan, np.nan),
            ci_normal_90=(np.nan, np.nan), credible_interval_90=(np.nan, np.nan),
            attribution_positives=[], attribution_negatives=[],
            sample_summary="test", reliability_note="test"
        )
        dossiers = generate_role_rankings([p_no_boot], ranking_metric="lower_bound_90")
        record = dossiers["Finisher"].ranked_players[0]
        self.assertTrue(math.isnan(record["lower_bound_90"]))
        self.assertEqual(record["lower_bound_status"], "UNAVAILABLE_INSUFFICIENT_BOOTSTRAP_DRAWS")

    def test_22_ranking_stability_ineligible_exclusion_and_insufficient_draws(self):
        """Verifies ranking stability properly excludes ineligible players and flags insufficient draws."""
        draws = {
            1: [1.0] * 100,
            2: [0.5] * 50,    # insufficient draws (< 100)
            3: [1.2] * 100    # ineligible
        }
        roles = {1: "Top Order", 2: "Top Order", 3: "Top Order"}
        elig = {1: True, 2: True, 3: False}

        stability = simulate_ranking_stability_across_draws(
            draws, roles, player_eligibility_dict=elig, min_required_draws=100
        )
        self.assertEqual(stability[3]["status"], "EXCLUDED_INELIGIBLE")
        self.assertTrue(math.isnan(stability[3]["median_rank"]))

        self.assertEqual(stability[2]["status"], "UNAVAILABLE_INSUFFICIENT_DRAWS")
        self.assertTrue(math.isnan(stability[2]["median_rank"]))

        self.assertEqual(stability[1]["status"], "SINGLE_PLAYER_COHORT")
        self.assertEqual(stability[1]["median_rank"], 1)

    # -----------------------------------------------------------------------
    # 8. Full Pipeline Integration on Pilot Data
    # -----------------------------------------------------------------------

    def test_15_pilot_pipeline_execution_and_tier_tally(self):
        """Verifies end-to-end execution of M4.5 on genuine pilot data."""
        results = run_reliability_ranking_pipeline(
            batter_df=self.batter_df,
            bowler_df=self.bowler_df
        )

        self.assertEqual(results["status"], "RELIABILITY_AND_RANKING_COMPLETE")
        self.assertEqual(results["total_batters_evaluated"], 102)
        self.assertEqual(results["total_bowlers_evaluated"], 74)

        # In 8-match pilot, 0 batters and 0 bowlers meet the 12-innings threshold
        self.assertEqual(results["eligible_batters_count"], 0)
        self.assertEqual(results["eligible_bowlers_count"], 0)

        # All 102 batters and 74 bowlers classify into INELIGIBLE_INSUFFICIENT_SAMPLE
        b_tiers = results["batter_tier_counts"]
        bw_tiers = results["bowler_tier_counts"]
        self.assertEqual(b_tiers[ReliabilityTier.INELIGIBLE_INSUFFICIENT_SAMPLE.value], 102)
        self.assertEqual(bw_tiers[ReliabilityTier.INELIGIBLE_INSUFFICIENT_SAMPLE.value], 74)

        # Official rankings must have 0 ranked players by default
        for role, dossier in results["batter_role_rankings"]["point_score"].items():
            self.assertEqual(len(dossier.ranked_players), 0)
            self.assertGreater(len(dossier.ineligible_players), 0)

        for role, dossier in results["bowler_role_rankings"]["point_score"].items():
            self.assertEqual(len(dossier.ranked_players), 0)
            self.assertGreater(len(dossier.ineligible_players), 0)

    def test_16_exploratory_ranking_mode_for_pilot_verification(self):
        """Verifies that exploratory ranking mode can rank pilot players for validation only."""
        results = run_reliability_ranking_pipeline(
            batter_df=self.batter_df,
            bowler_df=self.bowler_df,
            allow_pilot_ineligible_ranking=True
        )

        # Under exploratory validation mode, each role should have ranked records
        b_ranks = results["batter_role_rankings"]["point_score"]
        self.assertIn("Top Order", b_ranks)
        self.assertIn("Middle Order", b_ranks)
        self.assertIn("Finisher", b_ranks)
        self.assertGreater(len(b_ranks["Finisher"].ranked_players), 0)
        self.assertEqual(b_ranks["Finisher"].ranked_players[0]["rank"], 1)

    # -----------------------------------------------------------------------
    # 9. Governance Constraints Assertions
    # -----------------------------------------------------------------------

    def test_17_no_global_leaderboard_or_cross_role_ranking(self):
        """Verifies governance constraint: engine does not produce a unified unsegregated top-10 list."""
        results = run_reliability_ranking_pipeline(
            batter_df=self.batter_df,
            bowler_df=self.bowler_df
        )

        self.assertNotIn("global_top_10", results)
        self.assertNotIn("unified_leaderboard", results)
        self.assertIn("batter_role_rankings", results)
        self.assertIn("bowler_role_rankings", results)

    def test_18_duplicate_player_records_handling(self):
        """Verifies duplicate player assessments do not crash ranking generation."""
        dummy_row = pd.Series({
            "striker_id": 555,
            "striker_name": "Duplicated Batter",
            "primary_role": "Middle Order",
            "innings_count": 15,
            "total_balls_faced": 200,
            "pressure_balls": 50,
            "bppi_score": 1.1,
            "z_xra": 1.0,
            "z_delta_sr": 1.0,
            "z_delta_bnd": 1.0,
            "z_delta_dot": 1.0,
            "z_delta_survival": 1.0
        })
        a1 = assess_batter_reliability(dummy_row)
        a2 = assess_batter_reliability(dummy_row)

        dossiers = generate_role_rankings([a1, a2], ranking_metric="point_score")
        self.assertEqual(len(dossiers["Middle Order"].ranked_players), 2)
        self.assertEqual(dossiers["Middle Order"].ranked_players[0]["player_id"], 555)

    def test_19_empty_cohort_handling(self):
        """Verifies that an empty cohort list generates valid empty dossier without errors."""
        dossiers = generate_role_rankings([])
        self.assertEqual(len(dossiers), 0)

    def test_20_uncertainty_interval_differentiation_preserved(self):
        """Verifies that Normal CI, Percentile CI, and Bayesian Credible Interval remain mathematically decoupled."""
        dummy_row = pd.Series({
            "striker_id": 777,
            "striker_name": "Test Decoupling",
            "primary_role": "Finisher",
            "innings_count": 15,
            "total_balls_faced": 200,
            "pressure_balls": 50,
            "bppi_score": 1.25,
            "z_xra": 1.0, "z_delta_sr": 1.0, "z_delta_bnd": 1.0, "z_delta_dot": 1.0, "z_delta_survival": 1.0
        })
        boot_mock = {
            "striker_id": 777,
            "se_boot": 0.25,
            "ci_percentile_90": (0.75, 1.85),  # skewed
            "ci_normal_90": (0.84, 1.66),      # symmetric: 1.25 +/- 1.645*0.25
            "credible_interval_90": (0.95, 1.55), # shrunk
            "clusters_count": 15
        }
        assessment = assess_batter_reliability(dummy_row, boot_mock)
        self.assertNotEqual(assessment.ci_percentile_90, assessment.ci_normal_90)
        self.assertNotEqual(assessment.ci_percentile_90, assessment.credible_interval_90)


    def test_23_missing_or_non_finite_se_cannot_qualify_high_confidence(self):
        """Verifies missing, NaN, infinite, or zero SE cannot qualify a player for HIGH_CONFIDENCE."""
        # Case A: NaN SE
        tier, note = classify_reliability_tier(
            is_eligible=True, has_valid_data=True, pressure_balls=100, cluster_count=12,
            bootstrap_se=float("nan"), player_type="batter"
        )
        self.assertEqual(tier, ReliabilityTier.ELIGIBLE_MODERATE_CONFIDENCE)
        self.assertIn("bootstrap uncertainty uncomputed or non-finite", note)

        # Case B: Infinite SE
        tier, note = classify_reliability_tier(
            is_eligible=True, has_valid_data=True, pressure_balls=100, cluster_count=12,
            bootstrap_se=float("inf"), player_type="batter"
        )
        self.assertEqual(tier, ReliabilityTier.ELIGIBLE_MODERATE_CONFIDENCE)
        self.assertIn("bootstrap uncertainty uncomputed or non-finite", note)

        # Case C: Zero SE (uninformative)
        tier, note = classify_reliability_tier(
            is_eligible=True, has_valid_data=True, pressure_balls=100, cluster_count=12,
            bootstrap_se=0.0, player_type="batter"
        )
        self.assertEqual(tier, ReliabilityTier.ELIGIBLE_MODERATE_CONFIDENCE)
        self.assertIn("bootstrap uncertainty uncomputed or non-finite", note)

        # Case D: Valid positive SE <= 0.35 with >= 8 clusters and >= 72 balls
        tier, note = classify_reliability_tier(
            is_eligible=True, has_valid_data=True, pressure_balls=100, cluster_count=12,
            bootstrap_se=0.25, player_type="batter"
        )
        self.assertEqual(tier, ReliabilityTier.ELIGIBLE_HIGH_CONFIDENCE)
        self.assertIn("certified narrow estimation uncertainty", note)


if __name__ == "__main__":
    unittest.main()

