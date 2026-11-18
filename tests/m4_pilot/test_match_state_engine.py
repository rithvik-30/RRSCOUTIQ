"""
RR ScoutIQ - Unit Tests for Module M4.2 (Pre-Delivery Match-State Engine)
=========================================================================

Evidence Level: IMPLEMENTATION CORRECTNESS
Validates complete scorecard match-state reconstruction strictly PRIOR to each delivery.
Includes causal perturbation invariance tests, accounting rules, edge-case handling,
and boundary condition tests.
"""

import unittest
import math
import numpy as np
import pandas as pd
from src.m4_pilot.input_validation import load_and_validate_pilot_data
from src.m4_pilot.match_state_engine import (
    reconstruct_pre_delivery_match_state,
    determine_match_phase,
    compute_phi_setting,
    compute_dli_chase,
    compute_dli_setting,
    classify_pressure_tier,
    SUPER_OVER_FIXED_DLI,
    DLI_CHASE_MIN,
    DLI_CHASE_MAX,
    DLI_SETTING_MIN,
    DLI_SETTING_MAX
)


class TestMatchStateEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Loads validated pilot delivery data and match metadata once for test suite."""
        cls.deliveries_df, cls.val_report = load_and_validate_pilot_data()
        cls.matches_df = pd.read_csv("data/extracted/matches.csv")
        cls.state_df = reconstruct_pre_delivery_match_state(cls.deliveries_df, cls.matches_df)

    def test_01_output_shape_and_row_count(self):
        """Verifies output row count matches exactly 1,994 deliveries without duplication."""
        self.assertEqual(len(self.state_df), 1994)
        self.assertEqual(self.state_df["match_id"].nunique(), 8)
        dups = self.state_df.duplicated(subset=["match_id", "innings", "overid", "over_ball_num"]).sum()
        self.assertEqual(dups, 0)

    def test_02_initial_innings_state(self):
        """Verifies that the very first delivery of every innings starts at score=0, wickets=0, legal_balls=0."""
        # Use nth(0) to get the actual first delivery row (first() skips NaNs in pandas)
        first_deliveries = self.state_df.groupby(["match_id", "innings"]).nth(0).reset_index()
        self.assertEqual(len(first_deliveries), 20)  # 8 matches * 2 regulation + 4 super overs = 20 innings
        for _, row in first_deliveries.iterrows():
            self.assertEqual(row["pre_score"], 0, f"Match {row['match_id']} Inn {row['innings']} initial score non-zero")
            self.assertEqual(row["pre_wickets_lost"], 0, f"Match {row['match_id']} Inn {row['innings']} initial wickets non-zero")
            self.assertEqual(row["pre_legal_balls_bowled"], 0, f"Match {row['match_id']} Inn {row['innings']} initial legal balls non-zero")
            self.assertEqual(row["pre_wickets_in_hand"], 10)
            self.assertTrue(pd.isna(row["pre_crr"]))

    def test_03_score_progression_monotonicity(self):
        """Verifies cumulative score never decreases within any innings."""
        for (mid, inn), grp in self.state_df.groupby(["match_id", "innings"]):
            scores = grp["pre_score"].values
            diffs = np.diff(scores)
            self.assertTrue(np.all(diffs >= 0), f"Decreasing pre_score detected in Match {mid} Inn {inn}")

    def test_04_wicket_progression_monotonicity(self):
        """Verifies cumulative wickets lost never decreases within any innings."""
        for (mid, inn), grp in self.state_df.groupby(["match_id", "innings"]):
            wkts = grp["pre_wickets_lost"].values
            diffs = np.diff(wkts)
            self.assertTrue(np.all(diffs >= 0), f"Decreasing pre_wickets_lost detected in Match {mid} Inn {inn}")
            self.assertTrue(np.all(wkts <= 10))

    def test_05_legal_ball_progression(self):
        """Verifies legal balls bowled increments by 1 on legal deliveries and 0 on illegal deliveries."""
        for (mid, inn), grp in self.state_df.groupby(["match_id", "innings"]):
            legal_bowled = grp["pre_legal_balls_bowled"].values
            is_legal = grp["ext_is_legal_delivery"].values
            for i in range(len(grp) - 1):
                expected_next = legal_bowled[i] + (1 if is_legal[i] else 0)
                self.assertEqual(legal_bowled[i + 1], expected_next, f"Legal ball increment mismatch at Match {mid} Inn {inn} ball {i}")

    def test_06_wide_and_noball_handling(self):
        """Verifies wides and no-balls do not advance pre_legal_balls_bowled."""
        wide_rows = self.state_df[self.state_df["ext_is_wide"] == True]
        noball_rows = self.state_df[self.state_df["ext_is_noball"] == True]
        self.assertEqual(len(wide_rows), 65)
        self.assertEqual(len(noball_rows), 13)

        for idx in wide_rows.index:
            if idx + 1 < len(self.state_df) and self.state_df.loc[idx, "match_id"] == self.state_df.loc[idx + 1, "match_id"]:
                if self.state_df.loc[idx, "innings"] == self.state_df.loc[idx + 1, "innings"]:
                    self.assertEqual(
                        self.state_df.loc[idx, "pre_legal_balls_bowled"],
                        self.state_df.loc[idx + 1, "pre_legal_balls_bowled"]
                    )

    def test_07_byes_and_legbyes_advance_legal_balls(self):
        """Verifies byes and leg-byes count as legal deliveries and advance pre_legal_balls_bowled."""
        bye_rows = self.state_df[self.state_df["extras_type"].isin(["byes", "legbyes"])]
        self.assertEqual(len(bye_rows), 23)
        for idx in bye_rows.index:
            self.assertTrue(self.state_df.loc[idx, "ext_is_legal_delivery"])
            if idx + 1 < len(self.state_df) and self.state_df.loc[idx, "match_id"] == self.state_df.loc[idx + 1, "match_id"]:
                if self.state_df.loc[idx, "innings"] == self.state_df.loc[idx + 1, "innings"]:
                    self.assertEqual(
                        self.state_df.loc[idx + 1, "pre_legal_balls_bowled"],
                        self.state_df.loc[idx, "pre_legal_balls_bowled"] + 1
                    )

    def test_08_run_out_advances_team_wickets_not_bowler_wickets(self):
        """Verifies run outs increment pre_wickets_lost but are not credited to bowler."""
        runout_rows = self.state_df[self.state_df["dismissal_type"] == "RunOut"]
        self.assertEqual(len(runout_rows), 9)
        for idx in runout_rows.index:
            self.assertTrue(self.state_df.loc[idx, "is_wicket"])
            self.assertFalse(self.state_df.loc[idx, "ext_is_bowler_wicket"])
            if idx + 1 < len(self.state_df) and self.state_df.loc[idx, "match_id"] == self.state_df.loc[idx + 1, "match_id"]:
                if self.state_df.loc[idx, "innings"] == self.state_df.loc[idx + 1, "innings"]:
                    self.assertEqual(
                        self.state_df.loc[idx + 1, "pre_wickets_lost"],
                        self.state_df.loc[idx, "pre_wickets_lost"] + 1
                    )

    def test_09_retired_hurt_does_not_increment_wickets(self):
        """Verifies retired hurt (Sanju Samson, Match 40725) does NOT increment team wickets."""
        ret_hurt_row = self.state_df[self.state_df["ext_is_retired_hurt"] == True]
        self.assertEqual(len(ret_hurt_row), 1)
        idx = ret_hurt_row.index[0]
        self.assertFalse(ret_hurt_row["is_wicket"].iloc[0])
        # Verify next delivery's pre_wickets_lost is identical to current
        self.assertEqual(
            self.state_df.loc[idx + 1, "pre_wickets_lost"],
            self.state_df.loc[idx, "pre_wickets_lost"]
        )

    def test_10_retired_out_increments_team_wickets(self):
        """Verifies retired out (Match 14113) increments team wickets but not bowler wickets."""
        ret_out_row = self.state_df[self.state_df["ext_is_retired_out"] == True]
        self.assertEqual(len(ret_out_row), 1)
        idx = ret_out_row.index[0]
        self.assertTrue(ret_out_row["is_wicket"].iloc[0])
        self.assertFalse(ret_out_row["ext_is_bowler_wicket"].iloc[0])
        self.assertEqual(
            self.state_df.loc[idx + 1, "pre_wickets_lost"],
            self.state_df.loc[idx, "pre_wickets_lost"] + 1
        )

    def test_11_super_over_separation_and_fixed_dli(self):
        """Verifies Super Overs are isolated into Innings 3 & 4 with fixed DLI = 3.50."""
        so_rows = self.state_df[self.state_df["is_super_over"] == True]
        self.assertEqual(len(so_rows), 15)  # 5 in Match 34429, 10 in Match 40725
        self.assertTrue(np.all(so_rows["pre_dli"] == SUPER_OVER_FIXED_DLI))
        self.assertTrue(np.all(so_rows["pre_pressure_tier"] == "Tier 4: Extreme"))
        self.assertTrue(np.all(so_rows["pre_match_phase"] == "Super Over"))
        # Verify initial balls start at 0
        for (mid, inn), grp in so_rows.groupby(["match_id", "innings"]):
            self.assertEqual(grp["pre_score"].iloc[0], 0)
            self.assertEqual(grp["pre_legal_balls_bowled"].iloc[0], 0)

    def test_12_chase_target_and_rrr_accounting(self):
        """Verifies chase targets equal Innings 1 total + 1, and RRR calculates correctly."""
        inn2_rows = self.state_df[self.state_df["innings"] == 2]
        expected_targets = {
            13513: 225, 14094: 132, 14113: 166, 20181: 179,
            30058: 209, 34429: 138, 40037: 166, 40725: 189
        }
        for mid, target in expected_targets.items():
            m_inn2 = inn2_rows[inn2_rows["match_id"] == mid]
            self.assertTrue(np.all(m_inn2["pre_target"] == target))
            first_row = m_inn2.iloc[0]
            self.assertEqual(first_row["pre_runs_required"], target)
            self.assertAlmostEqual(first_row["pre_rrr"], target / 20.0, places=4)

    def test_13_innings_phase_boundaries(self):
        """Verifies phase definitions: Powerplay (overs 1-6), Middle (7-15), Death (16-20)."""
        reg_rows = self.state_df[self.state_df["is_super_over"] == False]
        pp_rows = reg_rows[reg_rows["overid"] <= 6]
        mid_rows = reg_rows[(reg_rows["overid"] >= 7) & (reg_rows["overid"] <= 15)]
        death_rows = reg_rows[reg_rows["overid"] >= 16]

        self.assertTrue(np.all(pp_rows["pre_match_phase"] == "Powerplay"))
        self.assertTrue(np.all(mid_rows["pre_match_phase"] == "Middle"))
        self.assertTrue(np.all(death_rows["pre_match_phase"] == "Death"))

    def test_14_dli_clamping_bounds(self):
        """Verifies DLI never violates approved M3 mathematical clamping bounds."""
        chase_dli = self.state_df[(self.state_df["innings"] == 2) & (self.state_df["is_dli_valid"] == True)]["pre_dli"]
        setting_dli = self.state_df[(self.state_df["innings"] == 1) & (self.state_df["is_dli_valid"] == True)]["pre_dli"]

        self.assertTrue(np.all(chase_dli >= DLI_CHASE_MIN))
        self.assertTrue(np.all(chase_dli <= DLI_CHASE_MAX))
        self.assertTrue(np.all(setting_dli >= DLI_SETTING_MIN))
        self.assertTrue(np.all(setting_dli <= DLI_SETTING_MAX))

    def test_15_match_20181_canonical_attribution(self):
        """Verifies canonical handling of Match 20181 Over 9 balls 4 & 5."""
        m_20181_inn2 = self.state_df[(self.state_df["match_id"] == 20181) & (self.state_df["innings"] == 2)]
        o9 = m_20181_inn2[m_20181_inn2["overid"] == 9].reset_index(drop=True)
        # Check pre_score progression
        # Ball 1 starts at 82
        self.assertEqual(o9.loc[0, "pre_score"], 82)
        # Ball 4 starts at 84 (after 1+1+0)
        self.assertEqual(o9.loc[3, "pre_score"], 84)
        # Ball 4 delivers 2 runs (canonical ext_delivery_total_runs) -> Ball 5 starts at 86
        self.assertEqual(o9.loc[4, "pre_score"], 86)
        # Ball 5 delivers 1 run -> Ball 6 starts at 87
        self.assertEqual(o9.loc[5, "pre_score"], 87)
        # Over 10 Ball 1 starts at 89 (after 87 + 2)
        o10_b1 = m_20181_inn2[(m_20181_inn2["overid"] == 10) & (m_20181_inn2["over_ball_num"] == 1)].iloc[0]
        self.assertEqual(o10_b1["pre_score"], 89)

    def test_16_causal_perturbation_invariance_current_delivery(self):
        """
        CRITICAL CAUSAL ISOLATION TEST A:
        Perturbing the outcome of delivery t MUST leave its own pre-delivery state strictly identical.
        """
        corrupted_df = self.deliveries_df.copy()
        test_idx = 100
        # Save baseline pre-delivery state of delivery t
        baseline_pre_score = self.state_df.loc[test_idx, "pre_score"]
        baseline_pre_wkts = self.state_df.loc[test_idx, "pre_wickets_lost"]
        baseline_pre_legal = self.state_df.loc[test_idx, "pre_legal_balls_bowled"]
        baseline_pre_dli = self.state_df.loc[test_idx, "pre_dli"]

        # Heavily perturb current delivery outcome
        corrupted_df.loc[test_idx, "ext_delivery_total_runs"] += 6
        corrupted_df.loc[test_idx, "is_wicket"] = True
        corrupted_df.loc[test_idx, "ext_is_legal_delivery"] = False

        perturbed_state_df = reconstruct_pre_delivery_match_state(corrupted_df, self.matches_df)

        # Assert delivery t's pre-state is 100% identical
        self.assertEqual(perturbed_state_df.loc[test_idx, "pre_score"], baseline_pre_score)
        self.assertEqual(perturbed_state_df.loc[test_idx, "pre_wickets_lost"], baseline_pre_wkts)
        self.assertEqual(perturbed_state_df.loc[test_idx, "pre_legal_balls_bowled"], baseline_pre_legal)
        self.assertEqual(perturbed_state_df.loc[test_idx, "pre_dli"], baseline_pre_dli)

    def test_17_causal_lag_incorporation_next_delivery(self):
        """
        CRITICAL CAUSAL ISOLATION TEST B:
        Perturbing delivery t MUST update the pre-delivery state of delivery t+1.
        """
        corrupted_df = self.deliveries_df.copy()
        test_idx = 100
        # Ensure test_idx and test_idx + 1 belong to the same innings
        self.assertEqual(corrupted_df.loc[test_idx, "innings"], corrupted_df.loc[test_idx + 1, "innings"])

        baseline_next_score = self.state_df.loc[test_idx + 1, "pre_score"]
        baseline_next_wkts = self.state_df.loc[test_idx + 1, "pre_wickets_lost"]

        # Add 4 runs and 1 wicket to delivery t
        corrupted_df.loc[test_idx, "ext_delivery_total_runs"] += 4
        corrupted_df.loc[test_idx, "is_wicket"] = True

        perturbed_state_df = reconstruct_pre_delivery_match_state(corrupted_df, self.matches_df)

        # Assert delivery t+1 incorporates exactly +4 runs and +1 wicket
        self.assertEqual(perturbed_state_df.loc[test_idx + 1, "pre_score"], baseline_next_score + 4)
        self.assertEqual(perturbed_state_df.loc[test_idx + 1, "pre_wickets_lost"], baseline_next_wkts + 1)

    def test_18_future_outcome_invariance(self):
        """
        CRITICAL CAUSAL ISOLATION TEST C:
        Changing an outcome in future delivery t+k MUST NOT alter pre-delivery states for any delivery <= t.
        """
        corrupted_df = self.deliveries_df.copy()
        target_delivery = 50
        future_delivery = 150

        baseline_states = self.state_df.loc[:target_delivery, ["pre_score", "pre_wickets_lost", "pre_dli"]].copy()

        # Massively perturb future delivery 150
        corrupted_df.loc[future_delivery, "ext_delivery_total_runs"] = 99
        corrupted_df.loc[future_delivery, "is_wicket"] = True

        perturbed_state_df = reconstruct_pre_delivery_match_state(corrupted_df, self.matches_df)
        rechecked_states = perturbed_state_df.loc[:target_delivery, ["pre_score", "pre_wickets_lost", "pre_dli"]]

        pd.testing.assert_frame_equal(baseline_states, rechecked_states)

    def test_19_dls_curtailment_exclusion_behavior(self):
        """Verifies synthetic DLS revised target correctly tags DLI_VALID = False and records exclusion reason."""
        synthetic_matches = self.matches_df.copy()
        # Mark match 20181 as DLS rain-affected with revised target 150
        idx_20181 = synthetic_matches[synthetic_matches["match_id"] == 20181].index[0]
        synthetic_matches.loc[idx_20181, "revised_target"] = 150.0

        dls_state_df = reconstruct_pre_delivery_match_state(self.deliveries_df, synthetic_matches)
        m_20181_inn2 = dls_state_df[(dls_state_df["match_id"] == 20181) & (dls_state_df["innings"] == 2)]

        self.assertTrue(np.all(m_20181_inn2["is_dli_valid"] == False))
        self.assertTrue(all("DLS Revised Target" in reason for reason in m_20181_inn2["dli_exclusion_reason"]))

    def test_20_shortened_match_exclusion_behavior(self):
        """Verifies synthetic shortened match correctly tags DLI_VALID = False and records exclusion reason."""
        synthetic_matches = self.matches_df.copy()
        idx_14094 = synthetic_matches[synthetic_matches["match_id"] == 14094].index[0]
        synthetic_matches.loc[idx_14094, "second_inn_revised_overs"] = 15.0

        short_state_df = reconstruct_pre_delivery_match_state(self.deliveries_df, synthetic_matches)
        m_14094 = short_state_df[short_state_df["match_id"] == 14094]

        self.assertTrue(np.all(m_14094["is_dli_valid"] == False))
        self.assertTrue(all("Shortened Match" in reason for reason in m_14094["dli_exclusion_reason"]))

    def test_21_exact_pressure_tier_boundaries(self):
        """
        Verifies exact numerical boundary behavior for the approved M3 recalibrated tiers:
        Tier 1: DLI < 0.90
        Tier 2: 0.90 <= DLI < 1.35
        Tier 3: 1.35 <= DLI < 2.25
        Tier 4: DLI >= 2.25
        """
        # Exact boundary tests specified in directive:
        self.assertEqual(classify_pressure_tier(0.899999), "Tier 1: Low")
        self.assertEqual(classify_pressure_tier(0.90), "Tier 2: Medium")
        self.assertEqual(classify_pressure_tier(1.349999), "Tier 2: Medium")
        self.assertEqual(classify_pressure_tier(1.35), "Tier 3: High")
        self.assertEqual(classify_pressure_tier(2.249999), "Tier 3: High")
        self.assertEqual(classify_pressure_tier(2.25), "Tier 4: Extreme")

        # Additional edge cases:
        self.assertEqual(classify_pressure_tier(0.10), "Tier 1: Low")
        self.assertEqual(classify_pressure_tier(5.00), "Tier 4: Extreme")

    def test_22_early_innings_undefined_crr_behavior(self):
        """
        Verifies that during early overs (legal balls < 6):
        1. pre_crr is explicitly NaN / pd.isna().
        2. Setting DLI evaluates deterministically without stagnation penalty (stag = 0).
        3. Setting DLI is strictly non-zero and equals Phi(t) * (10 / (w_in_hand + 1))^0.60.
        4. Stagnation penalty activates on legal ball 6 if CRR < par CRR.
        """
        inn1_sample = self.state_df[(self.state_df["match_id"] == 13513) & (self.state_df["innings"] == 1)]
        first_6 = inn1_sample.iloc[:6]

        # Verify pre_crr is NaN for all balls before legal ball 6
        self.assertTrue(first_6["pre_crr"].isna().all())

        # Verify exact DLI formula for t < 6: DLI == Phi(t) * (10 / 11)^0.60
        for idx, row in first_6.iterrows():
            t = int(row["pre_legal_balls_bowled"])
            expected_phi = 0.80 + 0.70 * ((t / 120.0) ** 1.20)
            expected_dli = expected_phi * ((10.0 / 11.0) ** 0.60)
            self.assertAlmostEqual(row["pre_dli"], expected_dli, places=6)

        # Verify legal ball 6 activates CRR
        ball_7 = inn1_sample.iloc[6]
        self.assertEqual(ball_7["pre_legal_balls_bowled"], 6)
        self.assertFalse(pd.isna(ball_7["pre_crr"]))
        self.assertAlmostEqual(ball_7["pre_crr"], 3.0, places=4)
        # CRR 3.0 < 8.15 activates stagnation penalty (stag = (8.15 - 3.0) / 6.0)
        expected_phi_6 = 0.80 + 0.70 * ((6.0 / 120.0) ** 1.20)
        expected_stag = (8.15 - 3.0) / 6.0
        expected_dli_6 = expected_phi_6 * ((10.0 / 11.0) ** 0.60) * math.sqrt(1.0 + expected_stag)
        self.assertAlmostEqual(ball_7["pre_dli"], expected_dli_6, places=5)


if __name__ == "__main__":
    unittest.main()
