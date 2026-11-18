"""
RR ScoutIQ - Module M5.3: Match-State Pipeline Orchestrator
===========================================================

Orchestrator pipeline for Milestone M5.3 Full-Scale Match-State Reconstruction.
Coordinates:
1. Input ingestion & cryptographic verification of enriched dataset and metadata.
2. Causal pre-delivery state reconstruction (179,837 deliveries, 776 matches).
3. Field-level and invariant cricket validation (12 invariant checks).
4. Generation of all four standardized M5.3 artifacts:
   - data/processed/m5_3/match_state_full.csv
   - data/processed/m5_3/match_state_validation_summary.csv
   - data/processed/m5_3/match_state_exclusion_register.csv
   - data/processed/m5_3/match_state_match_summary.csv

Evidence Level: IMPLEMENTATION CORRECTNESS & REPRODUCIBILITY
"""

import hashlib
import os
import sys
import time
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
from src.m5_state.match_state_engine import MatchStateEngine
from src.m5_state.match_state_validator import MatchStateValidator


BASE_DIR = os.path.abspath(".")
ENRICHED_INPUT_PATH = os.path.join(BASE_DIR, "data", "enriched", "full", "enriched_ball_by_ball_full.csv")
MATCHES_METADATA_PATH = os.path.join(BASE_DIR, "data", "extracted", "matches.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "processed", "m5_3")

OUTPUT_STATE_PATH = os.path.join(OUTPUT_DIR, "match_state_full.csv")
OUTPUT_VAL_PATH = os.path.join(OUTPUT_DIR, "match_state_validation_summary.csv")
OUTPUT_EXCL_PATH = os.path.join(OUTPUT_DIR, "match_state_exclusion_register.csv")
OUTPUT_SUMMARY_PATH = os.path.join(OUTPUT_DIR, "match_state_match_summary.csv")


def compute_sha256(filepath: str) -> str:
    """Computes SHA-256 hash of a file on disk."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


class MatchStatePipeline:
    """
    Executes the complete M5.3 Full-Scale Match-State Reconstruction pipeline.
    """

    def __init__(
        self,
        input_csv_path: str = ENRICHED_INPUT_PATH,
        matches_csv_path: str = MATCHES_METADATA_PATH,
        output_dir: str = OUTPUT_DIR
    ):
        self.input_csv_path = input_csv_path
        self.matches_csv_path = matches_csv_path
        self.output_dir = output_dir

    def run_pipeline(self) -> Dict[str, Any]:
        """
        Executes end-to-end match state reconstruction, validation, and export.
        """
        t0 = time.time()
        print("=" * 80)
        print("RR ScoutIQ — Milestone M5.3 Full-Scale Match-State Pipeline")
        print("=" * 80)

        os.makedirs(self.output_dir, exist_ok=True)

        # 1. Ingestion
        print(f"\n1. Ingesting input datasets...")
        print(f"   Enriched deliveries: {self.input_csv_path}")
        deliveries_df = pd.read_csv(self.input_csv_path)
        input_hash = compute_sha256(self.input_csv_path)
        print(f"   Input deliveries loaded: {len(deliveries_df):,} rows | SHA-256: {input_hash}")

        print(f"   Matches metadata: {self.matches_csv_path}")
        matches_df = pd.read_csv(self.matches_csv_path)
        matches_hash = compute_sha256(self.matches_csv_path)
        print(f"   Matches metadata loaded: {len(matches_df):,} rows | SHA-256: {matches_hash}")

        # 2. Match State Reconstruction
        print(f"\n2. Executing pre-delivery match state reconstruction...")
        engine = MatchStateEngine(matches_df=matches_df)
        state_df = engine.reconstruct_match_state(deliveries_df)
        print(f"   Reconstruction complete: {len(state_df):,} deliveries processed across {state_df['match_id'].nunique()} matches.")

        # 3. Validation
        print(f"\n3. Running 12-point invariant validation suite...")
        validator = MatchStateValidator(state_df=state_df, matches_df=matches_df)
        val_summary, all_passed = validator.validate_all()
        for _, row in val_summary.iterrows():
            print(f"   [{row['status']}] {row['check_id']}: {row['description']} ({row['details']})")

        if not all_passed:
            raise RuntimeError("Match-state reconstruction validation FAILED one or more critical checks.")

        # 4. Generate Exclusion Register
        print(f"\n4. Generating exclusion register...")
        excl_df = state_df[~state_df["is_dli_valid"] | state_df["is_super_over"]][[
            "match_id", "innings", "overid", "over_ball_num", "innings_ball_num",
            "is_shortened_match", "is_dls_match", "is_super_over",
            "dli_exclusion_reason", "pre_match_phase", "pre_dli", "pre_pressure_tier"
        ]].copy()
        print(f"   Exclusion register entries: {len(excl_df):,} deliveries.")

        # 5. Generate Match-Level Summary
        print(f"\n5. Generating match-level summary...")
        match_summaries = []
        for mid, grp in state_df.groupby("match_id"):
            inn1 = grp[grp["innings"] == 1]
            inn2 = grp[grp["innings"] == 2]
            so = grp[grp["innings"] > 2]
            
            inn1_score = inn1["ext_delivery_total_runs"].sum() if len(inn1) > 0 else 0
            inn1_wkts = inn1["is_wicket"].sum() if len(inn1) > 0 else 0
            inn2_score = inn2["ext_delivery_total_runs"].sum() if len(inn2) > 0 else 0
            inn2_wkts = inn2["is_wicket"].sum() if len(inn2) > 0 else 0
            
            match_summaries.append({
                "match_id": int(mid),
                "total_deliveries": len(grp),
                "total_legal_balls": int(grp["ext_is_legal_delivery"].sum()),
                "inn1_deliveries": len(inn1),
                "inn1_score": int(inn1_score),
                "inn1_wickets": int(inn1_wkts),
                "inn2_deliveries": len(inn2),
                "inn2_score": int(inn2_score),
                "inn2_wickets": int(inn2_wkts),
                "has_super_over": len(so) > 0,
                "super_over_deliveries": len(so),
                "is_shortened": bool(grp["is_shortened_match"].iloc[0]),
                "is_dls": bool(grp["is_dls_match"].iloc[0]),
                "chase_target": float(inn2["pre_target"].iloc[0]) if len(inn2) > 0 and pd.notna(inn2["pre_target"].iloc[0]) else np.nan,
                "dli_mean": float(grp["pre_dli"].mean()),
                "dli_valid_deliveries": int(grp["is_dli_valid"].sum()),
                "dli_excluded_deliveries": int((~grp["is_dli_valid"]).sum())
            })
        match_summary_df = pd.DataFrame(match_summaries)
        print(f"   Match summary generated: {len(match_summary_df):,} matches accounted for.")

        # 6. Artifact Export
        print(f"\n6. Exporting processed artifacts to {self.output_dir}...")
        state_df.to_csv(OUTPUT_STATE_PATH, index=False)
        output_state_hash = compute_sha256(OUTPUT_STATE_PATH)
        output_state_size = os.path.getsize(OUTPUT_STATE_PATH)
        print(f"   [CREATED] match_state_full.csv ({output_state_size:,} bytes | SHA-256: {output_state_hash})")

        val_summary.to_csv(OUTPUT_VAL_PATH, index=False)
        output_val_hash = compute_sha256(OUTPUT_VAL_PATH)
        print(f"   [CREATED] match_state_validation_summary.csv | SHA-256: {output_val_hash}")

        excl_df.to_csv(OUTPUT_EXCL_PATH, index=False)
        output_excl_hash = compute_sha256(OUTPUT_EXCL_PATH)
        print(f"   [CREATED] match_state_exclusion_register.csv | SHA-256: {output_excl_hash}")

        match_summary_df.to_csv(OUTPUT_SUMMARY_PATH, index=False)
        output_summary_hash = compute_sha256(OUTPUT_SUMMARY_PATH)
        print(f"   [CREATED] match_state_match_summary.csv | SHA-256: {output_summary_hash}")

        elapsed = time.time() - t0
        print(f"\n>>> Milestone M5.3 Pipeline Successfully Completed in {elapsed:.2f} seconds <<<")

        # Distribution breakdown
        tier_counts = state_df["pre_pressure_tier"].value_counts().to_dict()
        phase_counts = state_df["pre_match_phase"].value_counts().to_dict()

        return {
            "status": "COMPLETED",
            "elapsed_seconds": elapsed,
            "input_hash": input_hash,
            "output_state_hash": output_state_hash,
            "output_val_hash": output_val_hash,
            "output_excl_hash": output_excl_hash,
            "output_summary_hash": output_summary_hash,
            "total_deliveries": len(state_df),
            "total_matches": state_df["match_id"].nunique(),
            "tier_counts": tier_counts,
            "phase_counts": phase_counts,
            "all_validation_passed": all_passed
        }


if __name__ == "__main__":
    pipeline = MatchStatePipeline()
    res = pipeline.run_pipeline()
