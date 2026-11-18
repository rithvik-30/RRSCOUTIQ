"""
RR ScoutIQ — Milestone M5.2 Full-Dataset Cricket Validation
Module: src/m5_enrichment/enrichment_validation.py

Performs comprehensive, field-level and cricket-event validation across
the entire enriched full dataset (179,837 deliveries, 776 matches).
Produces:
data/enriched/full/enrichment_validation_summary.csv
"""

import os
import sys
from typing import Dict, Any, List, Tuple
import pandas as pd

sys.path.insert(0, os.path.abspath("."))

from src.m5_enrichment.delivery_alignment import QUARANTINED_MATCH_IDS

BASE_DIR = os.path.abspath(".")
ENRICHED_FULL_DIR = os.path.join(BASE_DIR, "data", "enriched", "full")
ENRICHED_BBB_PATH = os.path.join(ENRICHED_FULL_DIR, "enriched_ball_by_ball_full.csv")
MANIFEST_PATH = os.path.join(ENRICHED_FULL_DIR, "match_enrichment_manifest.csv")
VALIDATION_SUMMARY_PATH = os.path.join(ENRICHED_FULL_DIR, "enrichment_validation_summary.csv")

BOWLER_CREDIT_DISMISSALS = {
    "bowled",
    "caught",
    "caught and bowled",
    "lbw",
    "stumped",
    "hit wicket"
}


class FullDatasetEnrichmentValidator:
    """Comprehensive validator for the M5.2 enriched full dataset."""

    def __init__(
        self,
        enriched_bbb_path: str = ENRICHED_BBB_PATH,
        manifest_path: str = MANIFEST_PATH,
        summary_path: str = VALIDATION_SUMMARY_PATH
    ):
        self.enriched_bbb_path = enriched_bbb_path
        self.manifest_path = manifest_path
        self.summary_path = summary_path

    def run_validation(self) -> Tuple[pd.DataFrame, bool]:
        """Runs all validation batteries and generates summary CSV."""
        print("=== Running M5.2 Full-Dataset Cricket Validation ===", flush=True)
        print(f"Loading enriched delivery dataset: {self.enriched_bbb_path}...", flush=True)
        df = pd.read_csv(self.enriched_bbb_path)
        print(f"Loaded {len(df)} deliveries. Loading manifest: {self.manifest_path}...", flush=True)
        manifest = pd.read_csv(self.manifest_path)
        print(f"Loaded {len(manifest)} manifest records.", flush=True)

        results: List[Dict[str, Any]] = []

        # -------------------------------------------------------------
        # BATTERY 1: DELIVERY CONSERVATION & SCOPE
        # -------------------------------------------------------------
        # 1.1 Total delivery conservation
        total_deliveries = len(df)
        self._record_check(
            results, "SCOPE_AND_ALIGNMENT", "Total Delivery Count Conservation",
            total=total_deliveries, passed=(total_deliveries == 179837),
            expected="179,837 deliveries", actual=f"{total_deliveries:,} deliveries"
        )

        # 1.2 Total match count in delivery dataset
        unique_matches = df["match_id"].nunique()
        self._record_check(
            results, "SCOPE_AND_ALIGNMENT", "Enriched Unique Match Count",
            total=unique_matches, passed=(unique_matches == 776),
            expected="776 matches", actual=f"{unique_matches} matches"
        )

        # 1.3 Total manifest matches
        manifest_matches = len(manifest)
        self._record_check(
            results, "SCOPE_AND_ALIGNMENT", "Total Match Manifest Accounting",
            total=manifest_matches, passed=(manifest_matches == 883),
            expected="883 matches", actual=f"{manifest_matches} matches"
        )

        # 1.4 Quarantined matches exclusion safeguard
        quarantined_in_data = set(df["match_id"]).intersection(QUARANTINED_MATCH_IDS)
        self._record_check(
            results, "SCOPE_AND_ALIGNMENT", "Quarantined Match Exclusion Safeguard",
            total=len(QUARANTINED_MATCH_IDS), passed=(len(quarantined_in_data) == 0),
            expected="0 quarantined matches in data",
            actual=f"{len(quarantined_in_data)} quarantined matches found ({quarantined_in_data})"
        )

        # 1.5 Duplicate delivery keys check
        dup_keys = df.duplicated(subset=["match_id", "innings", "overid", "over_ball_num"]).sum()
        self._record_check(
            results, "SCOPE_AND_ALIGNMENT", "Local Delivery Uniqueness (No Duplicates)",
            total=total_deliveries, passed=(dup_keys == 0),
            expected="0 duplicates", actual=f"{dup_keys} duplicates"
        )

        # -------------------------------------------------------------
        # BATTERY 2: SPECIAL MATCH CONFORMANCE
        # -------------------------------------------------------------
        # 2.1 Match 13613 (SRH vs DC 2021) regulation only
        m13613 = df[df["match_id"] == 13613]
        m13613_so = (m13613["ext_is_super_over"] == True).sum()
        self._record_check(
            results, "SPECIAL_MATCHES", "Match 13613 Regulation-Only Conformance",
            total=len(m13613), passed=(len(m13613) == 246 and m13613_so == 0),
            expected="246 balls, 0 Super Over balls",
            actual=f"{len(m13613)} balls, {m13613_so} Super Over balls"
        )

        # 2.2 Match 21176 (IND vs AFG 2024) regulation only
        m21176 = df[df["match_id"] == 21176]
        m21176_so = (m21176["ext_is_super_over"] == True).sum()
        self._record_check(
            results, "SPECIAL_MATCHES", "Match 21176 Regulation-Only Conformance",
            total=len(m21176), passed=(len(m21176) == 252 and m21176_so == 0),
            expected="252 balls, 0 Super Over balls",
            actual=f"{len(m21176)} balls, {m21176_so} Super Over balls"
        )

        # 2.3 Match 14130 (LSG vs MI 2022) minor omission alignment
        m14130 = df[df["match_id"] == 14130]
        self._record_check(
            results, "SPECIAL_MATCHES", "Match 14130 Minor Omission Full Alignment",
            total=len(m14130), passed=(len(m14130) == 251),
            expected="251 balls", actual=f"{len(m14130)} balls"
        )

        # 2.4 Match 14164 (SRH vs PBKS 2022) minor omission alignment
        m14164 = df[df["match_id"] == 14164]
        self._record_check(
            results, "SPECIAL_MATCHES", "Match 14164 Minor Omission Full Alignment",
            total=len(m14164), passed=(len(m14164) == 219),
            expected="219 balls", actual=f"{len(m14164)} balls"
        )

        # -------------------------------------------------------------
        # BATTERY 3: PLAYER RESOLUTION COVERAGE
        # -------------------------------------------------------------
        # 3.1 Striker Cricsheet resolution
        striker_resolved = df["ext_striker_cricsheet_id"].notna().sum()
        self._record_check(
            results, "PLAYER_RESOLUTION", "Striker Cricsheet ID Resolution",
            total=total_deliveries, passed=(striker_resolved == total_deliveries),
            expected="100.0% resolved", actual=f"{striker_resolved}/{total_deliveries} ({striker_resolved/total_deliveries*100:.2f}%)"
        )

        # 3.2 Bowler Cricsheet resolution
        bowler_resolved = df["ext_bowler_cricsheet_id"].notna().sum()
        self._record_check(
            results, "PLAYER_RESOLUTION", "Bowler Cricsheet ID Resolution",
            total=total_deliveries, passed=(bowler_resolved == total_deliveries),
            expected="100.0% resolved", actual=f"{bowler_resolved}/{total_deliveries} ({bowler_resolved/total_deliveries*100:.2f}%)"
        )

        # 3.3 Non-striker Cricsheet resolution
        non_striker_resolved = df["ext_non_striker_cricsheet_id"].notna().sum()
        self._record_check(
            results, "PLAYER_RESOLUTION", "Non-Striker Cricsheet ID Resolution",
            total=total_deliveries, passed=(non_striker_resolved == total_deliveries),
            expected="100.0% resolved", actual=f"{non_striker_resolved}/{total_deliveries} ({non_striker_resolved/total_deliveries*100:.2f}%)"
        )

        # -------------------------------------------------------------
        # BATTERY 4: SCORING & EXTRAS CONSISTENCY
        # -------------------------------------------------------------
        # 4.1 Additive sum: total_runs == batter_runs + extra_runs
        sum_mismatch = (df["ext_delivery_total_runs"] != (df["ext_batter_runs"] + df["ext_extra_runs"])).sum()
        self._record_check(
            results, "SCORING_AND_EXTRAS", "Delivery Total Runs Additive Identity",
            total=total_deliveries, passed=(sum_mismatch == 0),
            expected="0 mismatches", actual=f"{sum_mismatch} mismatches"
        )

        # 4.2 Extras decomposition: extra_runs == wides + noballs + byes + legbyes + penalty
        extras_components_sum = (
            df["ext_wide_runs"] + df["ext_noball_runs"] +
            df["ext_bye_runs"] + df["ext_legbye_runs"] + df["ext_penalty_runs"]
        )
        extras_mismatch = (df["ext_extra_runs"] != extras_components_sum).sum()
        self._record_check(
            results, "SCORING_AND_EXTRAS", "Extras Component Additive Decomposition",
            total=total_deliveries, passed=(extras_mismatch == 0),
            expected="0 mismatches", actual=f"{extras_mismatch} mismatches"
        )

        # 4.3 Legal delivery classification: is_legal == (not wide and not noball)
        legal_calc = (~df["ext_is_wide"]) & (~df["ext_is_noball"])
        legal_mismatch = (df["ext_is_legal_delivery"] != legal_calc).sum()
        self._record_check(
            results, "SCORING_AND_EXTRAS", "Legal Delivery Classification (No wide & No no-ball)",
            total=total_deliveries, passed=(legal_mismatch == 0),
            expected="0 mismatches", actual=f"{legal_mismatch} mismatches"
        )

        # 4.4 Batter balls faced: balls_faced == (0 if wide else 1)
        bf_calc = df["ext_is_wide"].map({True: 0, False: 1})
        bf_mismatch = (df["ext_batter_balls_faced"] != bf_calc).sum()
        self._record_check(
            results, "SCORING_AND_EXTRAS", "Batter Balls Faced Accounting (MCC Law)",
            total=total_deliveries, passed=(bf_mismatch == 0),
            expected="0 mismatches", actual=f"{bf_mismatch} mismatches"
        )

        # 4.5 Bowler debit runs: bowler_debit == batter_runs + wide_runs + noball_runs
        debit_calc = df["ext_batter_runs"] + df["ext_wide_runs"] + df["ext_noball_runs"]
        debit_mismatch = (df["ext_bowler_debit_runs"] != debit_calc).sum()
        self._record_check(
            results, "SCORING_AND_EXTRAS", "Bowler Runs Conceded Debit (MCC Law 18.10.3)",
            total=total_deliveries, passed=(debit_mismatch == 0),
            expected="0 mismatches", actual=f"{debit_mismatch} mismatches"
        )

        # 4.6 Boundary classification
        four_mismatch = (df["ext_is_four"] != (df["ext_batter_runs"] == 4)).sum()
        six_mismatch = (df["ext_is_six"] != (df["ext_batter_runs"] == 6)).sum()
        self._record_check(
            results, "SCORING_AND_EXTRAS", "Boundary Four and Six Identification",
            total=total_deliveries, passed=(four_mismatch == 0 and six_mismatch == 0),
            expected="0 boundary mismatches", actual=f"{four_mismatch} four-mismatches, {six_mismatch} six-mismatches"
        )

        # -------------------------------------------------------------
        # BATTERY 5: WICKET & DISMISSAL RULES
        # -------------------------------------------------------------
        # 5.1 Retired Hurt is NOT a wicket
        ret_hurt_df = df[df["ext_is_retired_hurt"] == True]
        ret_hurt_wkt = (ret_hurt_df["ext_is_wicket"] == True).sum()
        ret_hurt_bwkt = (ret_hurt_df["ext_is_bowler_wicket"] == True).sum()
        self._record_check(
            results, "DISMISSALS_AND_WICKETS", "Retired Hurt Exclusion (Not a Wicket)",
            total=len(ret_hurt_df), passed=(ret_hurt_wkt == 0 and ret_hurt_bwkt == 0),
            expected="0 wickets, 0 bowler wickets",
            actual=f"{len(ret_hurt_df)} retired hurt events: {ret_hurt_wkt} wickets, {ret_hurt_bwkt} bowler wickets"
        )

        # 5.2 Retired Out is a wicket, but NOT credited to bowler
        ret_out_df = df[df["ext_is_retired_out"] == True]
        ret_out_wkt = (ret_out_df["ext_is_wicket"] == True).sum()
        ret_out_bwkt = (ret_out_df["ext_is_bowler_wicket"] == True).sum()
        self._record_check(
            results, "DISMISSALS_AND_WICKETS", "Retired Out Classification (Team Wicket, No Bowler Credit)",
            total=len(ret_out_df), passed=(ret_out_wkt == len(ret_out_df) and ret_out_bwkt == 0),
            expected=f"{len(ret_out_df)} team wickets, 0 bowler wickets",
            actual=f"{ret_out_wkt} team wickets, {ret_out_bwkt} bowler wickets"
        )

        # 5.3 Bowler credited dismissals (Bowled, Caught, LBW, Stumped, Hit Wicket)
        wkt_df = df[df["ext_is_wicket"] == True]
        credited_df = wkt_df[wkt_df["ext_is_bowler_wicket"] == True]
        invalid_kinds = credited_df[~credited_df["ext_dismissal_kind"].isin(BOWLER_CREDIT_DISMISSALS)]
        self._record_check(
            results, "DISMISSALS_AND_WICKETS", "Bowler Credit Dismissal Attribution",
            total=len(credited_df), passed=(len(invalid_kinds) == 0),
            expected="All credited wickets in MCC approved kinds",
            actual=f"{len(credited_df)} credited wickets, {len(invalid_kinds)} invalid kinds"
        )

        # 5.4 Non-credited dismissals (Run Out, Obstructing Field, etc.)
        non_credited_df = wkt_df[wkt_df["ext_is_bowler_wicket"] == False]
        leaked_credited = non_credited_df[non_credited_df["ext_dismissal_kind"].isin(BOWLER_CREDIT_DISMISSALS)]
        self._record_check(
            results, "DISMISSALS_AND_WICKETS", "Non-Credited Dismissal Attribution (Run Out, etc.)",
            total=len(non_credited_df), passed=(len(leaked_credited) == 0),
            expected="0 bowler credit leaks into non-credited dismissals",
            actual=f"{len(non_credited_df)} non-credited dismissals, {len(leaked_credited)} leaked"
        )

        # 5.5 Dismissed player name presence on wickets
        missing_dismissed_name = wkt_df["ext_dismissed_player_name"].isna().sum()
        self._record_check(
            results, "DISMISSALS_AND_WICKETS", "Dismissed Player Name Presence",
            total=len(wkt_df), passed=(missing_dismissed_name == 0),
            expected="0 missing names on wickets",
            actual=f"{missing_dismissed_name} missing names out of {len(wkt_df)} wickets"
        )

        summary_df = pd.DataFrame(results)
        summary_df.to_csv(self.summary_path, index=False)
        print(f"Validation complete. Saved summary to: {self.summary_path}", flush=True)

        all_passed = summary_df["status"].isin(["PASSED"]).all()
        print(f"Overall Validation Result: {'ALL PASS' if all_passed else 'FAILURES DETECTED'}", flush=True)
        return summary_df, all_passed

    @staticmethod
    def _record_check(
        results: List[Dict[str, Any]],
        category: str,
        check_name: str,
        total: int,
        passed: bool,
        expected: str,
        actual: str
    ):
        results.append({
            "category": category,
            "check_name": check_name,
            "total_records_tested": total,
            "status": "PASSED" if passed else "FAILED",
            "expected_criteria": expected,
            "actual_outcome": actual
        })


def run_full_dataset_enrichment_validation() -> Tuple[pd.DataFrame, bool]:
    """Helper entry point for CLI or test runners."""
    validator = FullDatasetEnrichmentValidator()
    return validator.run_validation()


if __name__ == "__main__":
    run_full_dataset_enrichment_validation()
