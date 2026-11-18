"""
Package manifest and create audit_packages/M5_5_B4_3_8_FINAL.zip
"""

import os
import json
import hashlib
import zipfile
from datetime import datetime

def sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def main():
    manifest = {
        "milestone": "M5.5-B.4.3.8",
        "timestamp": datetime.now().isoformat(),
        "canonical_dataset": {
            "path": "data/processed/m5_3/match_state_full.csv",
            "sha256": sha256_file("data/processed/m5_3/match_state_full.csv")
        },
        "enriched_crosswalk": {
            "path": "data/enriched/player_crosswalk_m5_5.csv",
            "sha256": sha256_file("data/enriched/player_crosswalk_m5_5.csv")
        },
        "src_files": {},
        "test_files": {},
        "audit_reports": {}
    }

    for root, _, files in os.walk("src/m5_5b_4_3_8"):
        if "__pycache__" in root:
            continue
        for f in sorted(files):
            p = os.path.join(root, f)
            manifest["src_files"][p.replace("\\", "/")] = sha256_file(p)

    for root, _, files in os.walk("tests/m5_5b_4_3_8"):
        if "__pycache__" in root:
            continue
        for f in sorted(files):
            p = os.path.join(root, f)
            manifest["test_files"][p.replace("\\", "/")] = sha256_file(p)

    for root, _, files in os.walk("audit_reports/M5_5B_4_3_8"):
        for f in sorted(files):
            if f == "REPRODUCIBILITY_MANIFEST.json":
                continue
            p = os.path.join(root, f)
            manifest["audit_reports"][p.replace("\\", "/")] = sha256_file(p)

    manifest_path = "audit_reports/M5_5B_4_3_8/REPRODUCIBILITY_MANIFEST.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    n_src = len(manifest["src_files"])
    n_test = len(manifest["test_files"])
    n_rep = len(manifest["audit_reports"])
    print(f"Saved manifest: {n_src} src files, {n_test} test files, {n_rep} audit reports")

    # Package archive
    os.makedirs("audit_packages", exist_ok=True)
    zip_path = "audit_packages/M5_5_B4_3_8_FINAL.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for cat in ["src_files", "test_files", "audit_reports"]:
            for rel_p in manifest[cat].keys():
                z.write(rel_p)
        z.write(manifest_path)
        z.write("data/enriched/player_crosswalk_m5_5.csv")

    zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    zip_sha = sha256_file(zip_path)
    print(f"Created archive {zip_path}: {zip_size_mb:.2f} MB, SHA-256: {zip_sha}")

    # Verify archive integrity
    print("Testing archive extraction in memory...")
    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        bad_file = z.testzip()
        assert bad_file is None, f"Corrupted file in zip: {bad_file}"
        print(f"Archive verified: {len(names)} files successfully tested (0 corruption).")

if __name__ == "__main__":
    main()
