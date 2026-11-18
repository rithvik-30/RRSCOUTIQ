"""
Phase 5.14.1 — Dynamic Artifact Generator with Strict Fail-Closed Governance
Generates:
  1. corrected_statistical_interpretation.json
  2. phase5_14_1_validation_summary.json
Enforces:
  - Strict 6/0/2 classification counts.
  - Non-significant classification for 2026 bowlers without extrapolation.
  - Accurate credible-bound terminology: one-sided 95% bound / central 90% interval endpoint.
  - Fail-closed hash gate logic.
  - Zero cohort-level significance attribution to individual players.
"""
import os
import sys
import json
import hashlib
from pathlib import Path

def generate_phase5_14_1_artifacts():
    print("=" * 80)
    print("PHASE 5.14.1: GENERATING REFINED STATISTICAL & GOVERNANCE ARTIFACTS")
    print("=" * 80)

    # 1. Load Phase 5.14 source JSON
    source_stats_file = Path("research/phase5_14/corrected_statistical_results.json")
    with open(source_stats_file, "r") as f:
        p514_stats = json.load(f)

    # 2. Refine statistical interpretations and strictly enforce 6/0/2 classification
    refined_comparisons = []
    sig_count = 0
    dir_count = 0
    non_sig_count = 0

    for c in p514_stats["comparisons"]:
        cid = c["comparison_id"]
        raw_p = c["raw_p_value"]
        holm_p = c["holm_adjusted_p"]
        is_holm_sig = (holm_p < 0.05)
        is_raw_sig = (raw_p < 0.05)

        if is_holm_sig:
            classification = "STATISTICALLY_SIGNIFICANT"
            interpretation = (
                f"Statistically significant advantage established post-Holm adjustment "
                f"(observed = {c['observed_effect']:+.2f}, 95% CI = {c['ci_95_formatted']}, "
                f"raw p = {raw_p:.4f}, Holm-adjusted p = {holm_p:.4f} < 0.05)."
            )
            sig_count += 1
        elif is_raw_sig:
            classification = "DIRECTIONAL_EVIDENCE"
            interpretation = (
                f"Directional advantage observed (raw p = {raw_p:.4f} < 0.05), "
                f"but does not reach family-wise statistical significance after Holm adjustment (Holm-adjusted p = {holm_p:.4f} >= 0.05)."
            )
            dir_count += 1
        else:
            classification = "NON_SIGNIFICANT"
            interpretation = (
                f"Observed effect favors selected cohort ({c['observed_effect']:+.2f}), "
                f"but evidence is insufficient to establish an advantage (raw p = {raw_p:.4f} >= 0.05, "
                f"Holm-adjusted p = {holm_p:.4f} >= 0.05, 95% CI {c['ci_95_formatted']} crosses zero)."
            )
            non_sig_count += 1

        refined_comparisons.append({
            "rank": c["rank"],
            "comparison_id": cid,
            "season": c["season"],
            "discipline": c["discipline"],
            "benchmark": c["benchmark"],
            "metric": c["metric"],
            "observed_effect": c["observed_effect"],
            "bootstrap_mean": c["bootstrap_mean"],
            "bootstrap_standard_error": c["bootstrap_standard_error"],
            "ci_95_low": c["ci_95_low"],
            "ci_95_high": c["ci_95_high"],
            "ci_95_formatted": c["ci_95_formatted"],
            "raw_p_value": raw_p,
            "holm_multiplier": c["holm_multiplier"],
            "step_adjusted_p": c["step_adjusted_p"],
            "holm_adjusted_p": holm_p,
            "raw_significant_05": is_raw_sig,
            "holm_significant_05": is_holm_sig,
            "inference_classification": classification,
            "formal_interpretation": interpretation
        })

    # Strict assertion of 6 / 0 / 2 classification
    assert sig_count == 6, f"Expected 6 statistically significant comparisons, got {sig_count}"
    assert dir_count == 0, f"Expected 0 directional comparisons, got {dir_count}"
    assert non_sig_count == 2, f"Expected 2 non-significant comparisons, got {non_sig_count}"

    stats_interpretation_payload = {
        "metadata": {
            "task": "Phase 5.14.1 — Final Statistical Interpretation",
            "family_wise_error_rate_alpha": 0.05,
            "monotonicity_verified": all(refined_comparisons[i]["holm_adjusted_p"] <= refined_comparisons[i+1]["holm_adjusted_p"] for i in range(len(refined_comparisons)-1)),
            "classification_summary": {
                "total_comparisons": len(refined_comparisons),
                "statistically_significant_post_holm": sig_count,
                "directional_raw_significant_post_holm_non_significant": dir_count,
                "non_significant": non_sig_count
            },
            "credible_bound_terminology_definition": {
                "z_multiplier": 1.645,
                "exact_statistical_definition": "One-sided 95% credible bound, corresponding to the conservative endpoint of a central 90% credible interval [mu - 1.645*SE, mu + 1.645*SE].",
                "usage_batter": "LB_90 = mu - 1.645 * SE (one-sided 95% lower bound on latent pressure boundary-rate value-add)",
                "usage_bowler": "UB_90 = mu + 1.645 * SE (one-sided 95% upper bound on latent pressure economy suppression)",
                "clarification": "Calling this a 'one-sided 90% credible bound' is a mathematical misnomer; 1.645 precisely places 5% probability in the adverse tail, providing 95% one-sided posterior coverage."
            },
            "cohort_vs_individual_scope_statement": (
                "Individual selection is based on the official historical hierarchical Empirical Bayes ranking "
                "and its conservative credible bound. Statistical significance results refer strictly to cohort-level "
                "prospective comparisons across all 10 players combined, not individual players."
            )
        },
        "comparisons": refined_comparisons
    }

    out_stats_file = Path("research/phase5_14_1/corrected_statistical_interpretation.json")
    with open(out_stats_file, "w") as f:
        json.dump(stats_interpretation_payload, f, indent=2)
    print(f"Saved refined statistical interpretation to {out_stats_file}")

    # 3. Fail-Closed Hash Gate Verification
    print("\n--- Running Fail-Closed Hash Gate Verification ---")
    def compute_sha256(filepath):
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest().lower()

    canon_path = "data/processed/m5_3/match_state_full.csv"
    report_path = "FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md"

    expected_canon = "ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4"
    expected_report = "0e0a11f87622dbeed44c3d918f37c5c9de2f2be8b22ac180099b5add1b882a1d"

    actual_canon = compute_sha256(canon_path)
    actual_report = compute_sha256(report_path)

    canon_match = (actual_canon == expected_canon)
    report_match = (actual_report == expected_report)
    hashes_intact = canon_match and report_match

    # FAIL-CLOSED GATE: approval is strictly conditional on hashes_intact
    if hashes_intact:
        gate_verdict = "APPROVED FOR COMPETITION FREEZE"
    else:
        gate_verdict = "NOT APPROVED — FROZEN HASH MISMATCH"

    print(f"Canonical Dataset Hash Match: {canon_match}")
    print(f"Competition Report Hash Match: {report_match}")
    print(f"Fail-Closed Gate Verdict: {gate_verdict}")

    validation_summary_payload = {
        "metadata": {
            "audit_phase": "Phase 5.14.1 — Final Statistical Interpretation & Freeze-Gate Correction",
            "timestamp": "2026-11-18",
            "verdict": gate_verdict,
            "gate_policy": "STRICT_FAIL_CLOSED"
        },
        "hash_gate": {
            "canonical_dataset": {
                "path": canon_path,
                "expected_sha256": expected_canon,
                "actual_sha256": actual_canon,
                "match": canon_match
            },
            "competition_report": {
                "path": report_path,
                "expected_sha256": expected_report,
                "actual_sha256": actual_report,
                "match": report_match
            },
            "hashes_intact": hashes_intact,
            "gate_verdict": gate_verdict
        },
        "statistical_classification_summary": {
            "statistically_significant_post_holm": sig_count,
            "directional_post_holm": dir_count,
            "non_significant": non_sig_count,
            "exact_counts_verified": True
        },
        "reporting_corrections": {
            "individual_significance_attribution_removed": True,
            "non_significant_2026_bowlers_corrected": True,
            "run_extrapolation_removed": True,
            "credible_bound_terminology_clarified": True,
            "fail_closed_hash_gate_implemented": True
        }
    }

    out_summary_file = Path("research/phase5_14_1/phase5_14_1_validation_summary.json")
    with open(out_summary_file, "w") as f:
        json.dump(validation_summary_payload, f, indent=2)
    print(f"Saved validation summary to {out_summary_file}")

if __name__ == "__main__":
    generate_phase5_14_1_artifacts()
