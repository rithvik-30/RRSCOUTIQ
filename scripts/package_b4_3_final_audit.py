"""
RR ScoutIQ — Milestone M5.5-B.4.3: Final Audit Packaging Script
Module: scripts/package_b4_3_final_audit.py

Packages:
1. All B.4.3 production source modules (src/m5_5b_4_3/*)
2. All adversarial tests (tests/m5_5b_4_3/*)
3. All out-of-fold predictions, model comparisons, calibration diagnostics, fairness diagnostics, bootstrap sensitivity, and isolation JSON
4. Reports and execution logs
5. Complete SHA-256 Manifest
Verifies:
- Archive integrity
- In-memory / extracted file byte equality and SHA-256 hash match against source files.
"""

import os
import sys
import zipfile
import hashlib
import tempfile
import pandas as pd

def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def build_package():
    os.makedirs("audit_packages", exist_ok=True)
    zip_path = "audit_packages/M5_5_B4_3_FINAL_AUDIT.zip"
    
    # 1. Target files
    target_files = [
        # Source modules
        "src/m5_5b_4_3/__init__.py",
        "src/m5_5b_4_3/cluster_variance_b4_3.py",
        "src/m5_5b_4_3/epistemic_context_engine_b4_3.py",
        "src/m5_5b_4_3/hierarchical_engine_b4_3.py",
        "src/m5_5b_4_3/bowler_fairness_matched_b4_3.py",
        "src/m5_5b_4_3/calibration_engine_b4_3.py",
        "src/m5_5b_4_3/run_validation_b4_3.py",
        "src/m5_5b_4_3/bootstrap_sensitivity_b4_3.py",
        
        # Test suite
        "tests/m5_5b_4_3/__init__.py",
        "tests/m5_5b_4_3/test_remediation_b4_3.py",
        
        # Reports & Outputs
        "audit_reports/M5_5B_4_3/M5_5_B4_3_FINAL_REMEDIATION_REPORT.md",
        "audit_reports/M5_5B_4_3/M5_5B_4_3_PREDICTIONS_OUT_OF_FOLD.csv",
        "audit_reports/M5_5B_4_3/M5_5B_4_3_MODEL_COMPARISON.csv",
        "audit_reports/M5_5B_4_3/M5_5B_4_3_PAIRED_MODEL_COMPARISON.csv",
        "audit_reports/M5_5B_4_3/M5_5B_4_3_SUBGROUP_RELIABILITY.csv",
        "audit_reports/M5_5B_4_3/M5_5B_4_3_POSTERIOR_CALIBRATION_DIAGNOSTICS.csv",
        "audit_reports/M5_5B_4_3/M5_5B_4_3_BINARY_RELIABILITY_DECILES.csv",
        "audit_reports/M5_5B_4_3/M5_5B_4_3_BOOTSTRAP_SENSITIVITY.csv",
        "audit_reports/M5_5B_4_3/M5_5B_4_3_PLAYER_FAIRNESS_DIAGNOSTICS.csv",
        "audit_reports/M5_5B_4_3/M5_5B_4_3_FOLD_MATCH_ISOLATION.json"
    ]
    
    # Check existence
    for f in target_files:
        if not os.path.exists(f):
            raise FileNotFoundError(f"Missing required artifact: {f}")
            
    # Compute source hashes
    source_hashes = {}
    for f in target_files:
        source_hashes[f] = compute_sha256(f)
        
    canonical_hash = compute_sha256("data/processed/m5_3/match_state_full.csv")
    assert canonical_hash == "ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4", "Canonical dataset hash mismatch!"
    
    # 2. Generate SHA-256 Manifest
    manifest_lines = [
        "# RR ScoutIQ — Milestone M5.5-B.4.3 Final Audit Package Manifest",
        "# Generated for Rajasthan Royals CRP SupeRR Selector Season 2",
        f"# Canonical Dataset SHA-256: {canonical_hash}",
        "#",
        "# File Hash Table (SHA-256, File Size in Bytes, Archive Relative Path):"
    ]
    
    for f in target_files:
        size = os.path.getsize(f)
        manifest_lines.append(f"{source_hashes[f]}  {size:10d}  {f}")
        
    manifest_content = "\n".join(manifest_lines) + "\n"
    manifest_path = "audit_reports/M5_5B_4_3/SHA256_MANIFEST.txt"
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(manifest_content)
        
    target_files.append(manifest_path)
    source_hashes[manifest_path] = compute_sha256(manifest_path)
    
    # 3. Create ZIP archive
    print(f"Creating ZIP package: {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in target_files:
            # Store with relative workspace path
            zf.write(f, arcname=f)
            print(f"  Added: {f} ({os.path.getsize(f):,} bytes)")
            
    zip_size = os.path.getsize(zip_path)
    print(f"Package successfully created: {zip_path} ({zip_size:,} bytes)")
    
    # 4. Verify extraction and byte equality
    print("\nVerifying package extraction and byte equality...")
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmpdir)
            
        mismatch_count = 0
        for f in target_files:
            extracted_path = os.path.join(tmpdir, f)
            if not os.path.exists(extracted_path):
                print(f"FAILED: Extracted file missing: {f}")
                mismatch_count += 1
                continue
                
            extracted_hash = compute_sha256(extracted_path)
            orig_hash = source_hashes[f]
            if extracted_hash != orig_hash:
                print(f"HASH MISMATCH for {f}: {extracted_hash} != {orig_hash}")
                mismatch_count += 1
            else:
                orig_size = os.path.getsize(f)
                ext_size = os.path.getsize(extracted_path)
                assert orig_size == ext_size, f"Size mismatch for {f}"
                
        if mismatch_count == 0:
            print("SUCCESS: 100% byte equality verified across all extracted files.")
        else:
            raise RuntimeError(f"Package verification failed with {mismatch_count} mismatches.")

if __name__ == "__main__":
    build_package()
