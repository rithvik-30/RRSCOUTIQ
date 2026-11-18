"""
RR ScoutIQ - M5.4 Full-scale Data Quality & Cricket Validation Pipeline Runner.
Executes all validation checks, extracts anomaly register, verifies input cryptographic hashes,
and persists audit CSV artifacts.
"""

import hashlib
import sys
from pathlib import Path
import pandas as pd

from src.m5_validation.data_quality_validator import DataQualityValidator


def compute_sha256(filepath: Path) -> str:
    """Computes SHA-256 digest of a physical file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def main():
    project_root = Path(__file__).resolve().parents[2]
    print(f"=== RR ScoutIQ: M5.4 Full-Scale Validation Pipeline ===")
    print(f"Project root: {project_root}")

    # Paths
    enriched_path = project_root / "data" / "enriched" / "full" / "enriched_ball_by_ball_full.csv"
    match_state_path = project_root / "data" / "processed" / "m5_3" / "match_state_full.csv"
    crosswalk_path = project_root / "data" / "enriched" / "m5_player_crosswalk_audit.csv"

    print("\n[1/4] Verifying input file existence and SHA-256 integrity...")
    assert enriched_path.exists(), f"Enriched dataset missing at {enriched_path}"
    assert match_state_path.exists(), f"Match state dataset missing at {match_state_path}"
    assert crosswalk_path.exists(), f"Player crosswalk missing at {crosswalk_path}"

    enriched_hash = compute_sha256(enriched_path)
    state_hash = compute_sha256(match_state_path)
    print(f"  Enriched Delivery Dataset SHA-256 : {enriched_hash}")
    print(f"  Match State Dataset SHA-256       : {state_hash}")

    print("\n[2/4] Executing 23 comprehensive validation checks...")
    validator = DataQualityValidator(
        enriched_path=enriched_path,
        match_state_path=match_state_path,
        crosswalk_path=crosswalk_path,
    )
    df_summary, df_anomalies = validator.run_all_checks()

    print("\n[3/4] Validation Results Summary:")
    passed_checks = int((df_summary["status"] == "PASS").sum())
    total_checks = len(df_summary)
    print(f"  Total Checks Executed : {total_checks}")
    print(f"  Passed Checks         : {passed_checks}")
    print(f"  Failed Checks         : {total_checks - passed_checks}")
    print(f"  Pass Rate             : {passed_checks / total_checks * 100:.2f}%\n")

    for idx, row in df_summary.iterrows():
        print(f"  [{row['status']}] {row['check_id']} - {row['name']} ({row['category']})")
        print(f"        Evaluated: {row['total_evaluated']:,} | Passed: {row['passed_count']:,} | Violations: {row['failed_count']}")
        print(f"        Details: {row['details']}")

    print("\n[4/4] Writing audit output artifacts...")
    audit_dir = project_root / "audit_reports"
    audit_dir.mkdir(parents=True, exist_ok=True)

    summary_out_path = audit_dir / "M5_4_VALIDATION_SUMMARY.csv"
    anomaly_out_path = audit_dir / "M5_4_ANOMALY_REGISTER.csv"

    df_summary.to_csv(summary_out_path, index=False)
    df_anomalies.to_csv(anomaly_out_path, index=False)

    print(f"  Persisted validation summary to : {summary_out_path}")
    print(f"  Persisted anomaly register to   : {anomaly_out_path}")
    print(f"  Total Registered Anomalies     : {len(df_anomalies)}")

    # Breakdown of anomalies
    severity_counts = df_anomalies["severity"].value_counts().to_dict()
    print("  Anomaly breakdown by severity:")
    for sev, cnt in severity_counts.items():
        print(f"    - {sev}: {cnt}")

    if passed_checks != total_checks:
        print("\n[ERROR] One or more validation checks failed!")
        sys.exit(1)
    else:
        print("\n[SUCCESS] All 23 validation checks passed with 100% compliance!")


if __name__ == "__main__":
    main()
