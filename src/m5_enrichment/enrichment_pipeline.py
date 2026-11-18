"""
RR ScoutIQ — Milestone M5.2 Full-Dataset Hybrid Enrichment Pipeline
Module: src/m5_enrichment/enrichment_pipeline.py

Executes reproducible, delivery-level hybrid enrichment across all 776 approved
eligible matches (179,837 deliveries).
Preserves all original columns intact and appends explicit ext_ enriched attributes.
Produces:
1. data/enriched/full/enriched_ball_by_ball_full.csv (179,837 rows)
2. data/enriched/full/match_enrichment_manifest.csv (883 rows)
"""

import os
import sys
import json
import zipfile
import time
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

sys.path.insert(0, os.path.abspath("."))

from src.m5_enrichment.delivery_alignment import (
    DeliveryAlignmentEngine,
    QuarantinedMatchError,
    QUARANTINED_MATCH_IDS
)

BASE_DIR = os.path.abspath(".")
DATA_EXTRACTED = os.path.join(BASE_DIR, "data", "extracted")
CRICSHEET_DIR = os.path.join(BASE_DIR, "data", "external", "cricsheet", "downloads")
ENRICHED_FULL_DIR = os.path.join(BASE_DIR, "data", "enriched", "full")
AUDIT_CSV = os.path.join(BASE_DIR, "data", "enriched", "m5_match_coverage_audit.csv")
PLAYER_CW_CSV = os.path.join(BASE_DIR, "data", "enriched", "m5_player_crosswalk_audit.csv")

BOWLER_CREDIT_DISMISSALS = {
    "bowled",
    "caught",
    "caught and bowled",
    "lbw",
    "stumped",
    "hit wicket"
}


class FullDatasetEnrichmentPipeline:
    """Orchestrates the delivery-level hybrid enrichment for all eligible matches."""

    def __init__(
        self,
        audit_csv_path: str = AUDIT_CSV,
        player_cw_path: str = PLAYER_CW_CSV,
        output_dir: str = ENRICHED_FULL_DIR
    ):
        self.audit_csv_path = audit_csv_path
        self.player_cw_path = player_cw_path
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        self.audit_df = pd.read_csv(self.audit_csv_path)
        self.player_cw_df = pd.read_csv(self.player_cw_path)
        
        # Build fast player lookup
        self.player_lookup: Dict[int, Dict[str, Any]] = {}
        for _, r in self.player_cw_df.iterrows():
            pid = int(r["local_player_id"])
            self.player_lookup[pid] = {
                "cricsheet_name": r["cricsheet_name"] if pd.notna(r["cricsheet_name"]) else None,
                "cricsheet_id": r["cricsheet_id"] if pd.notna(r["cricsheet_id"]) else None,
                "status": r["status"]
            }

    def get_approved_eligible_matches(self) -> pd.DataFrame:
        """Returns the exactly approved 776 eligible matches."""
        eligible = self.audit_df[
            (self.audit_df["processing_status"] == "MATCHED_AND_VALIDATED") |
            ((self.audit_df["processing_status"] == "MATCHED_WITH_WARNINGS") &
             (self.audit_df["warning_disposition"].isin(["SAFE_REGULATION_ONLY", "SAFE_MINOR_OMISSION"])))
        ].copy()
        
        # Guard: assert exact approved counts
        if len(eligible) != 776:
            raise ValueError(f"Approved eligible match count mismatch: {len(eligible)} != 776")
        if eligible["local_delivery_count"].sum() != 179837:
            raise ValueError(f"Approved eligible delivery count mismatch: {eligible['local_delivery_count'].sum()} != 179837")
            
        return eligible

    def execute_enrichment(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Executes hybrid enrichment for all 776 approved matches.
        Returns: (enriched_bbb_df, manifest_df)
        """
        t0 = time.time()
        print("=== Starting M5.2 Full-Dataset Hybrid Enrichment Pipeline ===")
        eligible_matches = self.get_approved_eligible_matches()
        eligible_mids = set(eligible_matches["local_match_id"])
        print(f"Approved scope: {len(eligible_matches)} matches, {eligible_matches['local_delivery_count'].sum()} deliveries.")

        # Open Cricsheet zip files once for optimal performance
        ipl_zip_path = os.path.join(CRICSHEET_DIR, "ipl_json.zip")
        t20_zip_path = os.path.join(CRICSHEET_DIR, "t20s_male_json.zip")
        z_ipl = zipfile.ZipFile(ipl_zip_path, "r")
        z_t20 = zipfile.ZipFile(t20_zip_path, "r")

        # Load local deliveries for eligible matches only
        print("Loading local delivery records for eligible matches...", flush=True)
        bbb_path = os.path.join(DATA_EXTRACTED, "ball_by_ball.csv")
        chunks = []
        for c in pd.read_csv(bbb_path, chunksize=50000):
            sub = c[c["match_id"].isin(eligible_mids)]
            if not sub.empty:
                chunks.append(sub)
        local_bbb = pd.concat(chunks, ignore_index=True)
        print(f"Loaded {len(local_bbb)} local deliveries. Indexing by match_id...", flush=True)
        if len(local_bbb) != 179837:
            raise ValueError(f"Local deliveries count ({len(local_bbb)}) does not equal approved 179837.")

        local_bbb_by_match = dict(tuple(local_bbb.groupby("match_id")))
        print(f"Indexed {len(local_bbb_by_match)} match delivery groups.", flush=True)

        enriched_deliveries: List[Dict[str, Any]] = []
        manifest_records: List[Dict[str, Any]] = []

        # Process eligible matches
        total_eligible = len(eligible_matches)
        for idx, (_, mrow) in enumerate(eligible_matches.iterrows(), start=1):
            mid = int(mrow["local_match_id"])
            cid = mrow["cricsheet_match_id"]
            cfile = mrow["cricsheet_file"]
            carch = mrow["cricsheet_archive"]
            warn_disp = mrow["warning_disposition"]
            orig_cnt = int(mrow["local_delivery_count"])

            if idx % 100 == 0 or idx == total_eligible:
                print(f"Processing match {idx}/{total_eligible} (Match ID: {mid})...", flush=True)

            # Read Cricsheet JSON
            z = z_ipl if carch == "ipl_json.zip" else z_t20
            cdata = json.loads(z.read(cfile).decode("utf-8"))
            cinfo = cdata.get("info", {})
            comp_name = cinfo.get("event", {}).get("name", "")
            match_format = cinfo.get("match_type", "")
            cric_registry = cinfo.get("registry", {}).get("people", {})

            # Align deliveries using pre-indexed match dataframe
            local_m_df = local_bbb_by_match[mid]
            aligned_pairs = DeliveryAlignmentEngine.align_match_deliveries(
                local_match_id=mid,
                cdata=cdata,
                local_df=local_m_df,
                warning_disposition=warn_disp
            )

            if len(aligned_pairs) != orig_cnt:
                raise ValueError(f"Match {mid}: aligned {len(aligned_pairs)} != original {orig_cnt}")

            # Determine analytical scope
            if warn_disp == "SAFE_REGULATION_ONLY":
                ana_scope = "REGULATION_ONLY"
            elif warn_disp == "SAFE_MINOR_OMISSION":
                ana_scope = "SAFE_FULL_ALIGNMENT"
            else:
                ana_scope = "FULL_MATCH"

            # Enrich each delivery
            for l_series, c_del, meta in aligned_pairs:
                enr_row = self._enrich_single_delivery(
                    l_series=l_series,
                    c_del=c_del,
                    meta=meta,
                    cid=cid,
                    carch=carch,
                    cfile=cfile,
                    comp_name=comp_name,
                    match_format=match_format,
                    cric_registry=cric_registry
                )
                enriched_deliveries.append(enr_row)

            manifest_records.append({
                "local_match_id": mid,
                "cricsheet_match_id": cid,
                "processing_status": "ENRICHED_AND_VALIDATED",
                "original_delivery_count": orig_cnt,
                "enriched_delivery_count": len(aligned_pairs),
                "unmatched_delivery_count": 0,
                "validation_status": "PASSED",
                "exclusion_or_warning_reason": warn_disp if pd.notna(warn_disp) else "NONE",
                "analytical_scope": ana_scope
            })

        z_ipl.close()
        z_t20.close()

        # Add all 107 excluded matches to manifest for 100% full match accounting
        excluded_df = self.audit_df[~self.audit_df["local_match_id"].isin(eligible_mids)]
        for _, xrow in excluded_df.iterrows():
            xmid = int(xrow["local_match_id"])
            xstatus = xrow["processing_status"]
            xwarn = xrow["warning_disposition"]
            xorig_cnt = int(xrow["local_delivery_count"])

            if xwarn == "QUARANTINED_INCOMPATIBLE":
                xscope = "EXCLUDED_QUARANTINE"
                xreason = "QUARANTINED_INCOMPATIBLE"
            elif xstatus == "EXCLUDED_POLICY_WITHHELD":
                xscope = "EXCLUDED_POLICY"
                xreason = "CRICSHEET_EDITORIAL_POLICY_WITHHELD"
            elif xstatus == "EXCLUDED_UNPLAYED":
                xscope = "EXCLUDED_UNPLAYED"
                xreason = "MATCH_ABANDONED_WITHOUT_BALLS"
            else:
                xscope = "EXCLUDED_UNRESOLVED"
                xreason = "DEVELOPMENTAL_NON_SENIOR_TOURNAMENT"

            manifest_records.append({
                "local_match_id": xmid,
                "cricsheet_match_id": xrow["cricsheet_match_id"] if pd.notna(xrow["cricsheet_match_id"]) else None,
                "processing_status": xstatus,
                "original_delivery_count": xorig_cnt,
                "enriched_delivery_count": 0,
                "unmatched_delivery_count": xorig_cnt,
                "validation_status": "EXCLUDED",
                "exclusion_or_warning_reason": xreason,
                "analytical_scope": xscope
            })

        enriched_df = pd.DataFrame(enriched_deliveries)
        manifest_df = pd.DataFrame(manifest_records).sort_values(by="local_match_id").reset_index(drop=True)

        print(f"Enrichment completed in {time.time() - t0:.2f}s.")
        print(f"Total deliveries enriched: {len(enriched_df)}.")
        print(f"Total manifest match records: {len(manifest_df)}.")

        # Save outputs
        out_bbb_path = os.path.join(self.output_dir, "enriched_ball_by_ball_full.csv")
        out_man_path = os.path.join(self.output_dir, "match_enrichment_manifest.csv")
        enriched_df.to_csv(out_bbb_path, index=False)
        manifest_df.to_csv(out_man_path, index=False)
        print(f"Saved: {out_bbb_path}")
        print(f"Saved: {out_man_path}")

        return enriched_df, manifest_df

    def _enrich_single_delivery(
        self,
        l_series: pd.Series,
        c_del: Dict[str, Any],
        meta: Dict[str, Any],
        cid: Any,
        carch: str,
        cfile: str,
        comp_name: str,
        match_format: str,
        cric_registry: Dict[str, str]
    ) -> Dict[str, Any]:
        """Maps a single local delivery and Cricsheet delivery tuple into enriched schema."""
        row_dict = l_series.to_dict()

        c_runs = c_del.get("runs", {})
        c_extras = c_del.get("extras", {})
        c_wickets = c_del.get("wickets", [])

        # Runs breakdown
        batter_runs = int(c_runs.get("batter", 0))
        extra_runs = int(c_runs.get("extras", 0))
        delivery_total = int(c_runs.get("total", 0))

        # Extras breakdown
        is_wide = "wides" in c_extras
        wide_runs = int(c_extras.get("wides", 0))
        is_noball = "noballs" in c_extras
        noball_runs = int(c_extras.get("noballs", 0))
        is_bye = "byes" in c_extras
        bye_runs = int(c_extras.get("byes", 0))
        is_legbye = "legbyes" in c_extras
        legbye_runs = int(c_extras.get("legbyes", 0))
        is_penalty = "penalty" in c_extras
        penalty_runs = int(c_extras.get("penalty", 0))
        extras_type_list = list(c_extras.keys())
        extras_type_str = ",".join(extras_type_list) if extras_type_list else None

        # Legal delivery & MCC Bowler debit
        is_legal = (not is_wide and not is_noball)
        batter_balls_faced = 1 if not is_wide else 0
        bowler_debit = batter_runs + wide_runs + noball_runs  # MCC Law 18.10.3

        # Boundaries
        is_four = (batter_runs == 4)
        is_six = (batter_runs == 6)

        # Wickets & Dismissals
        is_wicket = False
        dismissal_kind = None
        dismissed_name = None
        dismissed_cid = None
        is_bowler_wkt = False
        is_ret_hurt = False
        is_ret_out = False

        if c_wickets:
            w_first = c_wickets[0]
            dismissal_kind = str(w_first.get("kind", "")).lower()
            dismissed_name = w_first.get("player_out")
            dismissed_cid = cric_registry.get(dismissed_name) if dismissed_name else None

            if dismissal_kind == "retired hurt":
                is_wicket = False
                is_ret_hurt = True
            elif dismissal_kind == "retired out":
                is_wicket = True
                is_ret_out = True
                is_bowler_wkt = False
            else:
                is_wicket = True
                if dismissal_kind in BOWLER_CREDIT_DISMISSALS:
                    is_bowler_wkt = True
                else:
                    is_bowler_wkt = False

        # Player lookups from crosswalk
        striker_pid = int(l_series["striker_id"]) if pd.notna(l_series["striker_id"]) else None
        bowler_pid = int(l_series["bowler_id"]) if pd.notna(l_series["bowler_id"]) else None
        non_striker_pid = int(l_series["non_striker_id"]) if pd.notna(l_series["non_striker_id"]) else None
        dismissed_pid = int(l_series["dismissed_player_id"]) if pd.notna(l_series.get("dismissed_player_id")) and l_series.get("dismissed_player_id") > 0 else None

        s_info = self.player_lookup.get(striker_pid, {})
        b_info = self.player_lookup.get(bowler_pid, {})
        ns_info = self.player_lookup.get(non_striker_pid, {})
        d_info = self.player_lookup.get(dismissed_pid, {}) if dismissed_pid else {}

        # Appending explicit ext_ prefixed columns
        row_dict["ext_cricsheet_match_id"] = cid
        row_dict["ext_cricsheet_archive"] = carch
        row_dict["ext_cricsheet_file"] = cfile
        row_dict["ext_cricsheet_competition_name"] = comp_name
        row_dict["ext_match_format"] = match_format
        row_dict["ext_innings"] = int(l_series["innings"])
        row_dict["ext_is_super_over"] = meta["is_super_over"]
        row_dict["ext_cricsheet_delivery_index"] = meta["cricsheet_delivery_index"]

        # Players
        row_dict["ext_striker_name"] = s_info.get("cricsheet_name") or c_del.get("batter")
        row_dict["ext_striker_cricsheet_id"] = s_info.get("cricsheet_id") or cric_registry.get(c_del.get("batter"))
        row_dict["ext_non_striker_name"] = ns_info.get("cricsheet_name") or c_del.get("non_striker")
        row_dict["ext_non_striker_cricsheet_id"] = ns_info.get("cricsheet_id") or cric_registry.get(c_del.get("non_striker"))
        row_dict["ext_bowler_name"] = b_info.get("cricsheet_name") or c_del.get("bowler")
        row_dict["ext_bowler_cricsheet_id"] = b_info.get("cricsheet_id") or cric_registry.get(c_del.get("bowler"))

        # Dismissed player
        row_dict["ext_dismissed_player_name"] = dismissed_name
        row_dict["ext_dismissed_player_cricsheet_id"] = dismissed_cid or d_info.get("cricsheet_id")
        row_dict["ext_dismissed_player_local_id"] = dismissed_pid

        # Scoring & Extras
        row_dict["ext_batter_runs"] = batter_runs
        row_dict["ext_extra_runs"] = extra_runs
        row_dict["ext_extras_type"] = extras_type_str
        row_dict["ext_delivery_total_runs"] = delivery_total
        row_dict["ext_is_wide"] = is_wide
        row_dict["ext_wide_runs"] = wide_runs
        row_dict["ext_is_noball"] = is_noball
        row_dict["ext_noball_runs"] = noball_runs
        row_dict["ext_is_bye"] = is_bye
        row_dict["ext_bye_runs"] = bye_runs
        row_dict["ext_is_legbye"] = is_legbye
        row_dict["ext_legbye_runs"] = legbye_runs
        row_dict["ext_is_penalty"] = is_penalty
        row_dict["ext_penalty_runs"] = penalty_runs

        # Bowling debit & legal balls
        row_dict["ext_is_legal_delivery"] = is_legal
        row_dict["ext_batter_balls_faced"] = batter_balls_faced
        row_dict["ext_bowler_debit_runs"] = bowler_debit
        row_dict["ext_is_four"] = is_four
        row_dict["ext_is_six"] = is_six

        # Wickets
        row_dict["ext_is_wicket"] = is_wicket
        row_dict["ext_dismissal_kind"] = dismissal_kind
        row_dict["ext_is_bowler_wicket"] = is_bowler_wkt
        row_dict["ext_is_retired_hurt"] = is_ret_hurt
        row_dict["ext_is_retired_out"] = is_ret_out

        # Metadata & Provenance
        row_dict["ext_alignment_strategy"] = meta["alignment_strategy"]
        row_dict["ext_provenance"] = f"Cricsheet {carch} {cfile}"

        return row_dict


def run_full_dataset_enrichment_pipeline() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Helper entry point for CLI or test runners."""
    pipeline = FullDatasetEnrichmentPipeline()
    return pipeline.execute_enrichment()


if __name__ == "__main__":
    run_full_dataset_enrichment_pipeline()
