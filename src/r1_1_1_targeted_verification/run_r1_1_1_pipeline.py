"""
RR ScoutIQ - Master Pipeline Runner for Milestone R1.1.1: Targeted Statistical Verification.
Executes Investigations 1 through 4, persists all required CSV deliverables,
and cryptographically verifies canonical dataset immutability.
"""

from pathlib import Path
import sys
import pandas as pd

from src.m5_enrichment.canonical_integrity_audit import compute_sha256
from src.r1_1_1_targeted_verification.window_length_audit import audit_window_lengths
from src.r1_1_1_targeted_verification.setting_model_comparison import run_setting_model_comparison
from src.r1_1_1_targeted_verification.clustered_regression_audit import run_clustered_regression_audit
from src.r1_1_1_targeted_verification.threshold_robustness_audit import evaluate_threshold_robustness


def main():
    project_root = Path(__file__).resolve().parents[2]
    out_dir = project_root / "research" / "R1_1_1_TARGETED_VERIFICATION"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=== RR ScoutIQ: Milestone R1.1.1 Targeted Statistical Verification Pipeline ===")
    print(f"Project root: {project_root}")
    print(f"Output directory: {out_dir}")

    # Paths
    enriched_path = project_root / "data" / "enriched" / "full" / "enriched_ball_by_ball_full.csv"
    match_state_path = project_root / "data" / "processed" / "m5_3" / "match_state_full.csv"

    print("\n[1/5] Verifying pre-execution source hashes...")
    hash_enr_pre = compute_sha256(str(enriched_path))
    hash_st_pre = compute_sha256(str(match_state_path))
    print(f"  Enriched Delivery Dataset : {hash_enr_pre}")
    print(f"  Match State Dataset       : {hash_st_pre}")

    print("\n[2/5] Loading datasets...")
    df_state = pd.read_csv(match_state_path, low_memory=False)
    print(f"  Loaded {len(df_state):,} deliveries across {df_state['match_id'].nunique()} matches.")

    print("\n[3/5] Executing Investigation 1: Forward Window Length & Exactness Audit...")
    df_window_audit, valid_legal = audit_window_lengths(df_state)
    p_window = out_dir / "R1_1_1_WINDOW_LENGTH_AUDIT.csv"
    df_window_audit.to_csv(p_window, index=False)
    print(f"  Persisted {p_window}")

    print("\n[4/5] Executing Investigation 2: Setting DLI Independent Model Comparison...")
    df_setting_comp = run_setting_model_comparison(valid_legal)
    p_setting = out_dir / "R1_1_1_SETTING_MODEL_COMPARISON.csv"
    df_setting_comp.to_csv(p_setting, index=False)
    print(f"  Persisted {p_setting}")

    print("\n[5/5] Executing Investigations 3 & 4: Clustered Regression & Threshold Robustness...")
    df_clustered_reg = run_clustered_regression_audit(valid_legal)
    p_reg = out_dir / "R1_1_1_CLUSTERED_REGRESSION_AUDIT.csv"
    df_clustered_reg.to_csv(p_reg, index=False)
    print(f"  Persisted {p_reg}")

    df_threshold = evaluate_threshold_robustness(valid_legal)
    p_thresh = out_dir / "R1_1_1_THRESHOLD_ROBUSTNESS.csv"
    df_threshold.to_csv(p_thresh, index=False)
    print(f"  Persisted {p_thresh}")

    # Post-execution verification
    print("\n[POST-CHECK] Verifying post-execution source hashes...")
    hash_enr_post = compute_sha256(str(enriched_path))
    hash_st_post = compute_sha256(str(match_state_path))
    assert hash_enr_pre == hash_enr_post, "Enriched dataset was altered during audit!"
    assert hash_st_pre == hash_st_post, "Match state dataset was altered during audit!"
    print("  100% Cryptographic Immutability Confirmed: All source datasets bitwise identical.")
    print("\n=== Milestone R1.1.1 Targeted Verification Pipeline Completed Successfully! ===")


if __name__ == "__main__":
    main()
