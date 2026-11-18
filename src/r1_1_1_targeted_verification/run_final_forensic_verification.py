"""
RR ScoutIQ - Milestone R1.1.1 Final Forensic Verification Pipeline Runner
Executes Investigations A through D, validates all 13 canonical hashes before and after,
and saves the 4 required CSV deliverables into research/R1_1_1_TARGETED_VERIFICATION/.
"""

import hashlib
from pathlib import Path
import time
import pandas as pd

from src.r1_1_1_targeted_verification.forensic_verification_engine import (
    run_investigation_a,
    run_investigation_b,
    run_investigation_c,
    run_investigation_d,
)

CANONICAL_BASELINE = {
    "data/data_pack.zip.zip": "788f681b538ba95fb61bcaba7b7280e59a7789d043e7964ac3472c3d08291853",
    "data/extracted/ball_by_ball.csv": "a3926f49d2c684dca2a5d2de535a02c5ee46ea654ca1e79dd31c69e7544e9889",
    "data/extracted/matches.csv": "bb100ab84b8b9a15160c1f2315cf675210131a30e779ec5079fd5403dcf56eef",
    "data/extracted/competitions.csv": "507ceb7189f972d4e4f299ddcfc97f3c3247af1913f6291106f161fa8353fd9b",
    "data/extracted/teams.csv": "a65e5922a9b3bf49247b24fc9471782e700efb31f8dcc5042923238b87c50a5d",
    "data/extracted/playing_eleven.csv": "7517c73722a28d5d61c808ccf0cbed315a8780586d02e946eb9a7f5daf011c27",
    "data/extracted/competition_team_player_mapping.csv": "1ded4e42a933618572d6e2c3a521c3257eb1844fab4456d567d77cbb2d3bbb12",
    "data/enriched/pilot/enriched_ball_by_ball_pilot.csv": "a71f3ca75d3ba7aab60b797f78726f7d19551bde1221a3c97ed342c7fb0f9878",
    "data/enriched/full/enriched_ball_by_ball_full.csv": "d246bcfa5d7b223be1888e5cfb5b734047c6387539e05aaf7af5bd28edd2e8df",
    "data/processed/m5_3/match_state_full.csv": "ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4",
    "data/processed/m5_3/match_state_validation_summary.csv": "e7998fd4f81a292585e6c23d85136a83996d9c51e5333865a6aa57a71cb6df71",
    "data/processed/m5_3/match_state_exclusion_register.csv": "a193bfec188f5d2e59133dd69c60cefde9144f3a7e3a67fdfdfee6a3d6c47cf0",
    "data/processed/m5_3/match_state_match_summary.csv": "9b9249dbbde001689b74eb3d49d041d58ee5ffa94d8f77a132d03c022c4e39f6",
}


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def verify_canonical_hashes(stage: str):
    print(f"\n[{stage}] Cryptographic verification of all 13 canonical files...")
    for rel_path, expected in CANONICAL_BASELINE.items():
        digest = sha256_file(rel_path)
        assert digest == expected, f"HASH MISMATCH on {rel_path}! Expected: {expected}, Got: {digest}"
    print(f"[{stage}] 100% Bitwise Match on all 13 canonical datasets.")


def main():
    t0 = time.time()
    print("=" * 80)
    print("RR ScoutIQ — Milestone R1.1.1 Final Forensic Verification Pipeline")
    print("=" * 80)

    # 1. Pre-execution hash check
    verify_canonical_hashes("PRE-EXECUTION")

    project_root = Path(__file__).resolve().parents[2]
    out_dir = project_root / "research" / "R1_1_1_TARGETED_VERIFICATION"
    out_dir.mkdir(parents=True, exist_ok=True)

    match_state_path = project_root / "data" / "processed" / "m5_3" / "match_state_full.csv"
    print(f"\nLoading match state dataset: {match_state_path}")
    df_state = pd.read_csv(match_state_path, low_memory=False)
    print(f"Loaded {len(df_state):,} deliveries across {df_state['match_id'].nunique()} matches.")

    # Investigation A
    print("\n--- Executing Investigation A: Exact-Six Window Independent Reproduction ---")
    df_exact_six, valid_legal = run_investigation_a(df_state)
    csv_a = out_dir / "exact_six_independent_reproduction.csv"
    df_exact_six.to_csv(csv_a, index=False)
    print(f"Persisted: {csv_a} ({len(df_exact_six)} rows)")

    # Investigation B
    print("\n--- Executing Investigation B: Complete Setting DLI Model Comparison ---")
    df_setting_comp = run_investigation_b(valid_legal)
    csv_b = out_dir / "setting_model_complete_comparison.csv"
    df_setting_comp.to_csv(csv_b, index=False)
    print(f"Persisted: {csv_b} ({len(df_setting_comp)} rows)")

    # Investigation C
    print("\n--- Executing Investigation C: Independently Audit Clustered Regression ---")
    df_clustered_cov = run_investigation_c(valid_legal)
    csv_c = out_dir / "clustered_covariance_reproduction.csv"
    df_clustered_cov.to_csv(csv_c, index=False)
    print(f"Persisted: {csv_c} ({len(df_clustered_cov)} rows)")

    # Investigation D
    print("\n--- Executing Investigation D: Threshold Adjacent-Tier Uncertainty ---")
    df_threshold_unc = run_investigation_d(valid_legal, n_boot=1000, random_seed=42)
    csv_d = out_dir / "threshold_adjacent_tier_uncertainty.csv"
    df_threshold_unc.to_csv(csv_d, index=False)
    print(f"Persisted: {csv_d} ({len(df_threshold_unc)} rows)")

    # Post-execution hash check
    verify_canonical_hashes("POST-EXECUTION")

    elapsed = round(time.time() - t0, 2)
    print(f"\nAll 4 investigations completed in {elapsed}s.")
    print("=" * 80)


if __name__ == "__main__":
    main()
