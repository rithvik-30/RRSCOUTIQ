"""
RR ScoutIQ — Milestone M5.2.1 Independent Event-Level Reconciliation
Module: src/m5_enrichment/independent_event_reconciliation.py

Independently reconciles every delivery in data/enriched/full/enriched_ball_by_ball_full.csv
against:
1. data/extracted/ball_by_ball.csv (original immutable local source)
2. data/external/cricsheet/downloads/ (original Cricsheet JSON archives)
3. data/enriched/m5_match_coverage_audit.csv
4. data/enriched/m5_player_crosswalk_audit.csv

Reports:
- Internal consistency (enriched fields vs Cricsheet JSON)
- Non-destructive preservation (local columns in enriched vs raw ball_by_ball.csv)
- Source-to-source semantic agreement and divergences (local provider vs Cricsheet)
"""

import os
import sys
import json
import zipfile
import time
from typing import Dict, Any, List, Tuple
import pandas as pd

sys.path.insert(0, os.path.abspath("."))

from src.m5_enrichment.delivery_alignment import DeliveryAlignmentEngine

BASE_DIR = os.path.abspath(".")
DATA_EXTRACTED = os.path.join(BASE_DIR, "data", "extracted")
CRICSHEET_DIR = os.path.join(BASE_DIR, "data", "external", "cricsheet", "downloads")
ENRICHED_FULL_DIR = os.path.join(BASE_DIR, "data", "enriched", "full")
ENRICHED_BBB_PATH = os.path.join(ENRICHED_FULL_DIR, "enriched_ball_by_ball_full.csv")
AUDIT_CSV = os.path.join(BASE_DIR, "data", "enriched", "m5_match_coverage_audit.csv")


class IndependentEventReconciliation:
    """Performs strict independent event-level reconciliation across all 179,837 deliveries."""

    def __init__(self):
        self.audit_df = pd.read_csv(AUDIT_CSV)
        self.eligible_matches = self.audit_df[
            (self.audit_df["processing_status"] == "MATCHED_AND_VALIDATED") |
            ((self.audit_df["processing_status"] == "MATCHED_WITH_WARNINGS") &
             (self.audit_df["warning_disposition"].isin(["SAFE_REGULATION_ONLY", "SAFE_MINOR_OMISSION"])))
        ]

    def run_reconciliation(self) -> Dict[str, Any]:
        t0 = time.time()
        print("=== Starting M5.2.1 Independent Event-Level Reconciliation ===", flush=True)

        print(f"Loading enriched deliveries: {ENRICHED_BBB_PATH}...", flush=True)
        enr_df = pd.read_csv(ENRICHED_BBB_PATH)
        print(f"Loaded {len(enr_df)} enriched deliveries.", flush=True)

        eligible_mids = set(self.eligible_matches["local_match_id"])
        print("Loading raw ball_by_ball.csv for eligible matches...", flush=True)
        raw_chunks = []
        for c in pd.read_csv(os.path.join(DATA_EXTRACTED, "ball_by_ball.csv"), chunksize=50000):
            sub = c[c["match_id"].isin(eligible_mids)]
            if not sub.empty:
                raw_chunks.append(sub)
        raw_df = pd.concat(raw_chunks, ignore_index=True)
        print(f"Loaded {len(raw_df)} raw local deliveries.", flush=True)

        # 1. Non-destructive local column preservation check
        print("\nVerifying 100% preservation of raw local columns in enriched dataset...", flush=True)
        raw_sorted = raw_df.sort_values(by=["match_id", "innings", "overid", "over_ball_num"]).reset_index(drop=True)
        enr_sorted = enr_df.sort_values(by=["match_id", "innings", "overid", "over_ball_num"]).reset_index(drop=True)

        col_preservation_failures = {}
        for col in raw_df.columns:
            raw_series = raw_sorted[col]
            enr_series = enr_sorted[col]
            # Compare accounting for NaN equality
            eq = (raw_series == enr_series) | (raw_series.isna() & enr_series.isna())
            mismatches = (~eq).sum()
            if mismatches > 0:
                col_preservation_failures[col] = mismatches

        print(f"Original column preservation: {len(raw_df.columns) - len(col_preservation_failures)}/{len(raw_df.columns)} columns bitwise identical.", flush=True)
        if col_preservation_failures:
            print(f"Mismatches detected: {col_preservation_failures}", flush=True)

        # 2. Cricsheet direct reconciliation ball-by-ball
        print("\nIndependently comparing enriched fields against raw Cricsheet JSON archives...", flush=True)
        z_ipl = zipfile.ZipFile(os.path.join(CRICSHEET_DIR, "ipl_json.zip"), "r")
        z_t20 = zipfile.ZipFile(os.path.join(CRICSHEET_DIR, "t20s_male_json.zip"), "r")

        enr_by_match = dict(tuple(enr_df.groupby("match_id")))

        total_deliveries_checked = 0
        cric_internal_mismatches = 0
        mismatch_breakdown = {
            "batter_runs": 0,
            "extra_runs": 0,
            "total_runs": 0,
            "wide_flag": 0,
            "noball_flag": 0,
            "legal_flag": 0,
            "wicket_flag": 0,
            "dismissal_kind": 0,
            "dismissed_player": 0
        }

        # Source-to-source agreement tracking (Local vs Cricsheet)
        source_comparison = {
            "local_runs_eq_cric_batter_runs": 0,
            "local_runs_eq_cric_total_runs": 0,
            "local_wkt_eq_cric_wkt": 0,
            "local_wide_eq_cric_wide": 0,
            "local_noball_eq_cric_noball": 0
        }

        for idx, (_, mrow) in enumerate(self.eligible_matches.iterrows(), start=1):
            mid = int(mrow["local_match_id"])
            carch = mrow["cricsheet_archive"]
            cfile = mrow["cricsheet_file"]
            warn_disp = mrow["warning_disposition"]

            z = z_ipl if carch == "ipl_json.zip" else z_t20
            cdata = json.loads(z.read(cfile).decode("utf-8"))

            m_enr = enr_by_match[mid].sort_values(by=["innings", "overid", "over_ball_num"]).reset_index(drop=True)

            aligned_pairs = DeliveryAlignmentEngine.align_match_deliveries(
                local_match_id=mid,
                cdata=cdata,
                local_df=m_enr,
                warning_disposition=warn_disp
            )

            for l_row, c_del, meta in aligned_pairs:
                total_deliveries_checked += 1
                c_runs = c_del.get("runs", {})
                c_extras = c_del.get("extras", {})
                c_wickets = c_del.get("wickets", [])

                c_bat_runs = c_runs.get("batter", 0)
                c_ext_runs = c_runs.get("extras", 0)
                c_tot_runs = c_runs.get("total", 0)
                c_is_wide = ("wides" in c_extras)
                c_is_nb = ("noballs" in c_extras)
                c_is_legal = (not c_is_wide and not c_is_nb)

                # Check enriched vs cricsheet
                if l_row["ext_batter_runs"] != c_bat_runs:
                    mismatch_breakdown["batter_runs"] += 1
                    cric_internal_mismatches += 1
                if l_row["ext_extra_runs"] != c_ext_runs:
                    mismatch_breakdown["extra_runs"] += 1
                    cric_internal_mismatches += 1
                if l_row["ext_delivery_total_runs"] != c_tot_runs:
                    mismatch_breakdown["total_runs"] += 1
                    cric_internal_mismatches += 1
                if l_row["ext_is_wide"] != c_is_wide:
                    mismatch_breakdown["wide_flag"] += 1
                    cric_internal_mismatches += 1
                if l_row["ext_is_noball"] != c_is_nb:
                    mismatch_breakdown["noball_flag"] += 1
                    cric_internal_mismatches += 1
                if l_row["ext_is_legal_delivery"] != c_is_legal:
                    mismatch_breakdown["legal_flag"] += 1
                    cric_internal_mismatches += 1

                # Wickets check
                expected_wkt = False
                expected_kind = None
                expected_out_player = None
                if c_wickets:
                    w = c_wickets[0]
                    kind = str(w.get("kind", "")).lower()
                    expected_out_player = w.get("player_out")
                    expected_kind = kind
                    if kind != "retired hurt":
                        expected_wkt = True
                    else:
                        expected_wkt = False

                if l_row["ext_is_wicket"] != expected_wkt:
                    mismatch_breakdown["wicket_flag"] += 1
                    cric_internal_mismatches += 1
                if str(l_row["ext_dismissal_kind"]).lower() != str(expected_kind).lower() and not (pd.isna(l_row["ext_dismissal_kind"]) and expected_kind is None):
                    mismatch_breakdown["dismissal_kind"] += 1
                    cric_internal_mismatches += 1
                if str(l_row["ext_dismissed_player_name"]) != str(expected_out_player) and not (pd.isna(l_row["ext_dismissed_player_name"]) and expected_out_player is None):
                    mismatch_breakdown["dismissed_player"] += 1
                    cric_internal_mismatches += 1

                # Source-to-source comparison (Local vs Cricsheet)
                loc_runs = l_row["runs"]
                if loc_runs == c_bat_runs:
                    source_comparison["local_runs_eq_cric_batter_runs"] += 1
                if loc_runs == c_tot_runs:
                    source_comparison["local_runs_eq_cric_total_runs"] += 1

                loc_wkt = bool(l_row["is_wicket"])
                if loc_wkt == expected_wkt:
                    source_comparison["local_wkt_eq_cric_wkt"] += 1

                loc_wide = (str(l_row["extras_type"]).lower() == "wide")
                if loc_wide == c_is_wide:
                    source_comparison["local_wide_eq_cric_wide"] += 1

                loc_nb = (str(l_row["extras_type"]).lower() in ["noball", "overstep"])
                if loc_nb == c_is_nb:
                    source_comparison["local_noball_eq_cric_noball"] += 1

        z_ipl.close()
        z_t20.close()

        print(f"\nReconciliation completed across {total_deliveries_checked:,} deliveries in {time.time() - t0:.2f}s.", flush=True)
        print(f"Cricsheet-to-Enriched Internal Mismatches: {cric_internal_mismatches}", flush=True)
        print(f"Mismatch Breakdown: {mismatch_breakdown}", flush=True)
        print(f"Source-to-Source Comparison: {source_comparison}", flush=True)

        return {
            "total_deliveries_checked": total_deliveries_checked,
            "col_preservation_failures": col_preservation_failures,
            "cric_internal_mismatches": cric_internal_mismatches,
            "mismatch_breakdown": mismatch_breakdown,
            "source_comparison": source_comparison
        }


if __name__ == "__main__":
    recon = IndependentEventReconciliation()
    recon.run_reconciliation()
