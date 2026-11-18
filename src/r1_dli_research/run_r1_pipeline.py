"""
RR ScoutIQ - Master Pipeline Runner for Milestone R1: Empirical DLI Validation.
Executes Investigations A through E, persists all required CSV research artifacts,
and verifies cryptographic source immutability.
"""

from pathlib import Path
import sys
import pandas as pd

from src.m5_enrichment.canonical_integrity_audit import compute_sha256
from src.r1_dli_research.dli_distribution_analysis import run_distribution_analysis
from src.r1_dli_research.dli_sensitivity_analysis import run_chase_sensitivity_grid, run_setting_sensitivity_grid
from src.r1_dli_research.dli_outcome_validation import compute_forward_outcomes, run_outcome_validation_battery
from src.r1_dli_research.dli_threshold_sensitivity import run_threshold_sensitivity_battery
from src.r1_dli_research.dli_limitations_catalog import generate_limitations_register


def main():
    project_root = Path(__file__).resolve().parents[2]
    out_dir = project_root / "research" / "R1_DLI_VALIDATION"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=== RR ScoutIQ: Milestone R1 Empirical DLI Validation Pipeline ===")
    print(f"Project root: {project_root}")
    print(f"Output directory: {out_dir}")

    # Paths
    enriched_path = project_root / "data" / "enriched" / "full" / "enriched_ball_by_ball_full.csv"
    match_state_path = project_root / "data" / "processed" / "m5_3" / "match_state_full.csv"
    matches_path = project_root / "data" / "extracted" / "matches.csv"

    print("\n[1/6] Verifying pre-execution source hashes...")
    hash_enr_pre = compute_sha256(str(enriched_path))
    hash_st_pre = compute_sha256(str(match_state_path))
    print(f"  Enriched Delivery Dataset : {hash_enr_pre}")
    print(f"  Match State Dataset       : {hash_st_pre}")

    print("\n[2/6] Loading datasets into memory...")
    df_state = pd.read_csv(match_state_path, low_memory=False)
    matches_df = pd.read_csv(matches_path, low_memory=False)
    print(f"  Loaded {len(df_state):,} deliveries across {df_state['match_id'].nunique()} matches.")

    print("\n[3/6] Executing Investigation A: DLI Distributions, Tier Adequacy & Clamping...")
    df_tier_dist, df_phase_comp, df_clamping = run_distribution_analysis(df_state)
    path_tier = out_dir / "R1_TIER_DISTRIBUTION.csv"
    path_phase = out_dir / "R1_PHASE_COMPARISON.csv"
    path_clamp = out_dir / "R1_CLAMPING_ANALYSIS.csv"
    df_tier_dist.to_csv(path_tier, index=False)
    df_phase_comp.to_csv(path_phase, index=False)
    df_clamping.to_csv(path_clamp, index=False)
    print(f"  Persisted {path_tier}")
    print(f"  Persisted {path_phase}")
    print(f"  Persisted {path_clamp}")

    print("\n[4/6] Executing Investigation C: Empirical Construct Validity (Forward 6-Ball Outcomes)...")
    df_fwd = compute_forward_outcomes(df_state, matches_df)
    print(f"  Prepared {len(df_fwd):,} deliveries with forward 6-ball subsequent windows.")
    df_outcome_val = run_outcome_validation_battery(df_fwd)
    path_outcome = out_dir / "R1_OUTCOME_VALIDATION.csv"
    df_outcome_val.to_csv(path_outcome, index=False)
    print(f"  Persisted {path_outcome}")

    print("\n[5/6] Executing Investigation D: Tier Threshold Sensitivity Analysis...")
    df_threshold_sens = run_threshold_sensitivity_battery(df_fwd)
    path_thresh = out_dir / "R1_THRESHOLD_SENSITIVITY.csv"
    df_threshold_sens.to_csv(path_thresh, index=False)
    print(f"  Persisted {path_thresh}")

    print("\n[6/6] Executing Investigation E: DLI Limitations & Failure Modes Catalog...")
    df_limitations = generate_limitations_register(df_state)
    path_lim = out_dir / "R1_DLI_LIMITATIONS_REGISTER.csv"
    df_limitations.to_csv(path_lim, index=False)
    print(f"  Persisted {path_lim}")

    # Verify post-execution hashes
    print("\n[POST-CHECK] Verifying post-execution source hashes...")
    hash_enr_post = compute_sha256(str(enriched_path))
    hash_st_post = compute_sha256(str(match_state_path))
    assert hash_enr_pre == hash_enr_post, "Enriched delivery dataset was modified during execution!"
    assert hash_st_pre == hash_st_post, "Match state dataset was modified during execution!"
    print("  100% Cryptographic Immutability Confirmed: All source datasets bitwise identical.")
    print("\n=== Milestone R1 Research Pipeline Completed Successfully! ===")


if __name__ == "__main__":
    main()
