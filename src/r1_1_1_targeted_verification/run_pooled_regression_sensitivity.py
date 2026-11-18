"""
RR ScoutIQ - Milestone R1.1.1 Pooled Regression Sensitivity Pipeline Runner
Executes Investigations 1 through 4, persists all 4 required CSV deliverables,
and cryptographically verifies canonical baseline immutability before and after.
"""

from pathlib import Path
import shutil
import time
import pandas as pd

from src.m5_enrichment.canonical_integrity_audit import compute_sha256
from src.r1_1_1_targeted_verification.pooled_regression_sensitivity import (
    prepare_exact_six_features,
    run_investigation_1,
    run_investigation_2,
    run_investigation_3,
    run_investigation_4,
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


def verify_canonical_hashes(stage: str):
    print(f"\n[{stage}] Verifying all 13 canonical dataset hashes...")
    for path, expected in CANONICAL_BASELINE.items():
        computed = compute_sha256(path)
        assert computed == expected, f"HASH MISMATCH on {path}!"
    print(f"[{stage}] 100% Bitwise Match confirmed on all 13 canonical files.")


def main():
    t0 = time.time()
    print("=" * 80)
    print("RR ScoutIQ — Milestone R1.1.1: Pooled Regression Sensitivity Pipeline")
    print("=" * 80)

    # 1. Pre-execution hash check
    verify_canonical_hashes("PRE-EXECUTION")

    project_root = Path(__file__).resolve().parents[2]
    out_dir = project_root / "research" / "R1_1_1_TARGETED_VERIFICATION"
    out_dir.mkdir(parents=True, exist_ok=True)

    match_state_path = project_root / "data" / "processed" / "m5_3" / "match_state_full.csv"
    print(f"\nLoading match state dataset: {match_state_path}")
    df_state = pd.read_csv(match_state_path, low_memory=False)

    print("\nPreparing exact-six features and filtering valid legal deliveries...")
    exact_6 = prepare_exact_six_features(df_state)
    print(f"Exact-6 observations: {len(exact_6):,} (Setting: {(exact_6['pre_innings_type'] == 'Setting').sum():,}, Chase: {(exact_6['pre_innings_type'] == 'Chase').sum():,})")

    # Investigation 1
    print("\n--- [1/4] Executing Investigation 1: Setting vs Chasing Regression ---")
    df_inn = run_investigation_1(exact_6)
    csv_1 = out_dir / "innings_specific_regression.csv"
    df_inn.to_csv(csv_1, index=False)
    shutil.copyfile(csv_1, project_root / "innings_specific_regression.csv")
    print(f"Persisted: {csv_1} ({len(df_inn)} rows)")

    # Investigation 2
    print("\n--- [2/4] Executing Investigation 2: Pooled Model Interaction (DLI x Chase) ---")
    df_int = run_investigation_2(exact_6)
    csv_2 = out_dir / "pooled_interaction_regression.csv"
    df_int.to_csv(csv_2, index=False)
    shutil.copyfile(csv_2, project_root / "pooled_interaction_regression.csv")
    print(f"Persisted: {csv_2} ({len(df_int)} rows)")

    # Investigation 3
    print("\n--- [3/4] Executing Investigation 3: Early CRR Imputation Sensitivity ---")
    df_crr = run_investigation_3(exact_6)
    csv_3 = out_dir / "early_crr_sensitivity.csv"
    df_crr.to_csv(csv_3, index=False)
    shutil.copyfile(csv_3, project_root / "early_crr_sensitivity.csv")
    print(f"Persisted: {csv_3} ({len(df_crr)} rows)")

    # Investigation 4
    print("\n--- [4/4] Executing Investigation 4: Collinearity and Conditioning Diagnostics ---")
    df_vif, corr_df, meta = run_investigation_4(exact_6)
    csv_4 = out_dir / "regression_conditioning_diagnostics.csv"
    df_vif.to_csv(csv_4, index=False)
    shutil.copyfile(csv_4, project_root / "regression_conditioning_diagnostics.csv")
    print(f"Persisted: {csv_4} ({len(df_vif)} rows)")
    print(f"  Unscaled Condition Number : {meta['condition_number_unscaled']}")
    print(f"  Scaled Condition Number   : {meta['condition_number_scaled']}")
    print(f"  Scaling Invariance Diff   : {meta['numerical_invariance_dli_diff']:.2e}")

    # Post-execution hash check
    verify_canonical_hashes("POST-EXECUTION")

    elapsed = round(time.time() - t0, 2)
    print(f"\nAll sensitivity checks completed successfully in {elapsed}s.")
    print("=" * 80)


if __name__ == "__main__":
    main()
