"""
RR ScoutIQ - Master Pipeline Runner for Milestone R1.1: Independent Methodological Audit.
Executes Investigations 1 through 6, produces all required CSV deliverables,
and cryptographically validates canonical dataset immutability.
"""

from pathlib import Path
import sys
import pandas as pd

from src.m5_enrichment.canonical_integrity_audit import compute_sha256
from src.r1_dli_research.dli_outcome_validation import compute_forward_outcomes
from src.r1_1_methodology_audit.chase_baseline_comparison import run_chase_baseline_comparison
from src.r1_1_methodology_audit.forward_outcome_audit import run_forward_outcome_audit
from src.r1_1_methodology_audit.setting_dli_audit import analyze_setting_dli_components
from src.r1_1_methodology_audit.tier_distribution_reconciliation import reconcile_tier_populations
from src.r1_1_methodology_audit.threshold_significance_audit import run_threshold_significance_audit
from src.r1_1_methodology_audit.clamping_and_venue_audit import run_clamping_and_venue_audit


def main():
    project_root = Path(__file__).resolve().parents[2]
    out_dir = project_root / "research" / "R1_1_METHODOLOGY_AUDIT"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=== RR ScoutIQ: Milestone R1.1 Independent Methodological Audit Pipeline ===")
    print(f"Project root: {project_root}")
    print(f"Output directory: {out_dir}")

    # Paths
    enriched_path = project_root / "data" / "enriched" / "full" / "enriched_ball_by_ball_full.csv"
    match_state_path = project_root / "data" / "processed" / "m5_3" / "match_state_full.csv"
    matches_path = project_root / "data" / "extracted" / "matches.csv"

    print("\n[1/7] Verifying pre-execution source hashes...")
    hash_enr_pre = compute_sha256(str(enriched_path))
    hash_st_pre = compute_sha256(str(match_state_path))
    print(f"  Enriched Delivery Dataset : {hash_enr_pre}")
    print(f"  Match State Dataset       : {hash_st_pre}")

    print("\n[2/7] Loading datasets...")
    df_state = pd.read_csv(match_state_path, low_memory=False)
    matches_df = pd.read_csv(matches_path, low_memory=False)
    print(f"  Loaded {len(df_state):,} deliveries across {df_state['match_id'].nunique()} matches.")

    print("\n[3/7] Executing Investigation 1: Chase Win-Rate Construct Validity & Baseline Comparison...")
    df_baseline = run_chase_baseline_comparison(df_state, matches_df)
    p_baseline = out_dir / "R1_1_BASELINE_MODEL_COMPARISON.csv"
    df_baseline.to_csv(p_baseline, index=False)
    print(f"  Persisted {p_baseline}")

    print("\n[4/7] Executing Investigation 2: Forward Outcome Validation & Incremental Explanatory Power...")
    df_outcomes, df_increm = run_forward_outcome_audit(df_state)
    p_outcomes = out_dir / "R1_1_FORWARD_OUTCOME_ANALYSIS.csv"
    df_outcomes.to_csv(p_outcomes, index=False)
    print(f"  Persisted {p_outcomes}")

    print("\n[5/7] Executing Investigation 3: Setting DLI Progression, Over 1 & Scarcity Audit...")
    df_prog, df_over1, df_clamp = analyze_setting_dli_components(df_state)
    # Combine setting analysis into single comprehensive table
    df_setting_combined = pd.concat([df_prog, df_over1, df_clamp], axis=0, ignore_index=True)
    p_setting = out_dir / "R1_1_SETTING_DLI_ANALYSIS.csv"
    df_setting_combined.to_csv(p_setting, index=False)
    print(f"  Persisted {p_setting}")

    print("\n[6/7] Executing Investigation 4: Tier Distribution Reconciliation...")
    df_fwd_filter = compute_forward_outcomes(df_state, matches_df)
    df_reconcile = reconcile_tier_populations(df_state, df_fwd_filter)
    p_reconcile = out_dir / "R1_1_TIER_RECONCILIATION.csv"
    df_reconcile.to_csv(p_reconcile, index=False)
    print(f"  Persisted {p_reconcile}")

    print("\n[7/7] Executing Investigations 5 & 6: Threshold Significance & Venue Clamping...")
    df_sig = run_threshold_significance_audit(df_fwd_filter)
    p_sig = out_dir / "R1_1_THRESHOLD_SIGNIFICANCE.csv"
    df_sig.to_csv(p_sig, index=False)
    print(f"  Persisted {p_sig}")

    df_venue = run_clamping_and_venue_audit(df_state, matches_df)
    p_venue = out_dir / "R1_1_CLAMPING_AND_VENUE_ANALYSIS.csv"
    df_venue.to_csv(p_venue, index=False)
    print(f"  Persisted {p_venue}")

    # Post-execution verification
    print("\n[POST-CHECK] Verifying post-execution source hashes...")
    hash_enr_post = compute_sha256(str(enriched_path))
    hash_st_post = compute_sha256(str(match_state_path))
    assert hash_enr_pre == hash_enr_post, "Enriched dataset was altered during audit!"
    assert hash_st_pre == hash_st_post, "Match state dataset was altered during audit!"
    print("  100% Cryptographic Immutability Confirmed: All source datasets bitwise identical.")
    print("\n=== Milestone R1.1 Methodological Audit Pipeline Completed Successfully! ===")


if __name__ == "__main__":
    main()
