"""
Audit script for Task 3: Statistical Reconciliation
Compares confidence intervals, effect sizes, standard errors, and p-values
across Phase 5.12 JSON, Phase 5.13 bootstrap JSON, Phase 5.13 Holm JSON,
and Phase 5.13 Markdown reports.
"""
import json
import re

def audit_stats():
    with open("research/phase5_12/corrected_bootstrap_results.json", "r") as f:
        p512_json = json.load(f)
    
    with open("research/phase5_13/independently_verified_bootstrap.json", "r") as f:
        p513_boot_json = json.load(f)
        
    with open("research/phase5_13/holm_adjusted_results.json", "r") as f:
        p513_holm_json = json.load(f)
        
    with open("research/phase5_13/PHASE_5_13_FINAL_VERIFICATION.md", "r") as f:
        verif_md = f.read()
        
    with open("research/phase5_13/PHASE_5_13_EXECUTIVE_VERDICT.md", "r") as f:
        verd_md = f.read()

    print("=== PHASE 5.13 BOOTSTRAP JSON ===")
    p513_boot_map = {c["id"]: c for c in p513_boot_json["comparisons"]}
    for cid, c in p513_boot_map.items():
        print(f"{cid:<32}: obs={c['observed_diff']:+.2f}, SE={c['standard_error']:.3f}, 95% CI=[{c['ci_95_low']:+.2f}, {c['ci_95_high']:+.2f}], p={c['p_value_two_sided']:.4f}")

    print("\n=== PHASE 5.13 HOLM JSON ===")
    p513_holm_map = {c["comparison_id"]: c for c in p513_holm_json["ranked_comparisons"]}
    for cid, c in p513_holm_map.items():
        print(f"{cid:<32}: rank={c['rank']}, k={c['multiplier']}, raw_p={c['raw_p_value']:.4f}, holm_p={c['holm_adjusted_p']:.4f}, 95% CI=[{c['ci_95'][0]:+.2f}, {c['ci_95'][1]:+.2f}]")

    print("\n=== PHASE 5.12 JSON ===")
    # Print Phase 5.12 2025 and 2026 comparisons
    for s_key in ["season_2025", "season_2026"]:
        s_data = p512_json.get(s_key, {})
        for comp_name, comp_data in s_data.items():
            if isinstance(comp_data, dict) and "observed_difference" in comp_data:
                print(f"{s_key} {comp_name:<25}: obs={comp_data['observed_difference']:+.2f}, 95% CI=[{comp_data['ci_95'][0]:+.2f}, {comp_data['ci_95'][1]:+.2f}], p={comp_data['two_sided_p_value']:.4f}")

    print("\n=== CHECKING EXECUTIVE VERDICT TEXT FOR CIs ===")
    # Search for CIs in executive verdict
    ci_matches = re.findall(r"(\+?-?\d+\.?\d* pp|\+?-?\d+\.?\d* RPO) \(95% CI: \[([^\]]+)\]", verd_md)
    for effect, ci in ci_matches:
        print(f"  Verdict text: effect={effect}, CI=[{ci}]")

if __name__ == "__main__":
    audit_stats()
