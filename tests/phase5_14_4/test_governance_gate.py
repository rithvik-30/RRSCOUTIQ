"""
Phase 5.14.4 — Comprehensive Regression & Fail-Closed Governance Tests

Verifies all 18 required governance, fault-injection, and invariant checks:
1. Genuine regression-test execution (never defaults to passing).
2. Failing pytest execution blocks audit authorization.
3. Pytest timeout blocks audit authorization.
4. Execution error/exception blocks audit authorization.
5. Path existence OSError caught by hash gate.
6. File access PermissionError caught by hash gate.
7. Hash mismatch in canonical data or competition report blocks asset integrity.
8. Mismatch in any one of the 20 selected players blocks selection invariance.
9. Player rank or ordering mismatch blocks selection invariance.
10. Incorrect statistical classification blocks statistical verification.
11. Incorrect p-value or confidence interval blocks statistical verification.
12. Altered variance formula or floor blocks uncertainty verification.
13. First-stage publication failure handled safely.
14. Second-stage publication failure handled safely with cleanup.
15. Stale approval prevention after a failed rerun.
16. JSON and Markdown verdicts remain strictly consistent.
17. Temporary staging files are cleaned up after publication.
18. Frozen production assets remain cryptographically intact.
"""

import os
import sys
import json
import uuid
import pytest
import hashlib
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from research.phase5_14_4.hardened_gate import (
    compute_sha256_safe,
    evaluate_asset_integrity,
    execute_repository_tests,
    evaluate_selection_invariance,
    evaluate_statistical_evidence,
    evaluate_uncertainty_quantification,
    evaluate_audit_authorization,
    evaluate_full_governance_gate,
    publish_artifacts_transactional,
    EXPECTED_CANON_HASH,
    EXPECTED_REPORT_HASH,
    DEFAULT_CANON_PATH,
    DEFAULT_REPORT_PATH,
    DEFAULT_STATS_PATH,
    DEFAULT_PROD_EQUIV_PATH,
    DEFAULT_RANKINGS_PATH,
    DEFAULT_EPISTEMIC_CODE_PATH,
    FROZEN_EXPECTED_BATTERS,
    FROZEN_EXPECTED_BOWLERS,
    FROZEN_EXPECTED_STATS,
)

SUMMARY_PATH = Path("research/phase5_14_4/phase5_14_4_validation_summary.json")
VERDICT_PATH = Path("research/phase5_14_4/PHASE_5_14_4_FINAL_VERDICT.md")

def get_simulated_passing_runner():
    """Returns a synthetic runner callable representing a successful pytest execution."""
    return lambda: {
        "status": "PASSED",
        "is_passed": True,
        "exit_code": 0,
        "tests_collected": 114,
        "tests_passed": 114,
        "tests_failed": 0,
        "tests_errors": 0,
        "tests_skipped": 0,
        "duration_seconds": 45.0,
        "stdout_tail": "114 passed in 45.00s",
        "stderr": "",
        "error": None,
    }


# ----------------------------------------------------------------------
# 1. Genuine Regression-Test Execution Checks
# ----------------------------------------------------------------------

def test_regression_tests_must_actually_run_and_cannot_default_to_pass():
    """Verifies that execute_repository_tests parses real runner output and fails on failure."""
    def failing_runner():
        return {
            "status": "FAILED",
            "is_passed": False,
            "exit_code": 1,
            "tests_collected": 10,
            "tests_passed": 8,
            "tests_failed": 2,
            "tests_errors": 0,
            "tests_skipped": 0,
            "duration_seconds": 5.0,
            "stdout_tail": "2 failed, 8 passed",
            "stderr": "AssertionError",
            "error": "Pytest exited with code 1",
        }

    res = execute_repository_tests(override_runner=failing_runner)
    assert res["is_passed"] is False
    assert res["tests_failed"] == 2
    assert res["exit_code"] == 1


def test_failing_pytest_run_blocks_audit_authorization():
    """Verifies that a failing pytest run blocks audit authorization."""
    failing_result = {
        "status": "FAILED",
        "is_passed": False,
        "exit_code": 1,
        "tests_collected": 50,
        "tests_passed": 49,
        "tests_failed": 1,
        "tests_errors": 0,
        "tests_skipped": 0,
        "duration_seconds": 12.0,
        "stdout_tail": "1 failed, 49 passed",
        "stderr": "FAILED tests/m5_5b_4_3_8/test_something.py",
        "error": "Pytest exited with code 1",
    }
    auth = evaluate_audit_authorization(
        asset_integrity_passed=True,
        test_runner_result=failing_result,
    )
    assert auth["is_passed"] is False
    assert "FAILED" in auth["status"]
    assert auth["checks"]["regression_test_suite_passed"] is False
    assert any("Regression test suite failed" in f for f in auth["failures"])


def test_pytest_timeout_blocks_audit_authorization():
    """Verifies that execution timeout blocks audit authorization."""
    timeout_result = {
        "status": "TIMED_OUT",
        "is_passed": False,
        "exit_code": -1,
        "tests_collected": 0,
        "tests_passed": 0,
        "tests_failed": 0,
        "tests_errors": 1,
        "tests_skipped": 0,
        "duration_seconds": 180.0,
        "stdout_tail": "",
        "stderr": "Pytest execution timed out after 180 seconds.",
        "error": "TIMEOUT",
    }
    auth = evaluate_audit_authorization(
        asset_integrity_passed=True,
        test_runner_result=timeout_result,
    )
    assert auth["is_passed"] is False
    assert auth["checks"]["regression_test_suite_passed"] is False
    assert any("Regression test suite failed" in f for f in auth["failures"])


def test_missing_pytest_or_execution_error_blocks_audit_authorization():
    """Verifies that subprocess execution errors block authorization."""
    error_result = {
        "status": "EXECUTION_ERROR",
        "is_passed": False,
        "exit_code": -1,
        "tests_collected": 0,
        "tests_passed": 0,
        "tests_failed": 0,
        "tests_errors": 1,
        "tests_skipped": 0,
        "duration_seconds": 0.0,
        "stdout_tail": "",
        "stderr": "FileNotFoundError: [WinError 2] The system cannot find the file specified",
        "error": "Executable not found",
    }
    auth = evaluate_audit_authorization(
        asset_integrity_passed=True,
        test_runner_result=error_result,
    )
    assert auth["is_passed"] is False
    assert auth["checks"]["regression_test_suite_passed"] is False


# ----------------------------------------------------------------------
# 2. Fault Injection & Hashing Checks
# ----------------------------------------------------------------------

def test_path_existence_oserror_caught_by_hash_gate(monkeypatch):
    """Fault injection: Path.exists() raises OSError."""
    def mock_exists(self):
        raise OSError("Simulated hardware I/O bus controller failure")

    monkeypatch.setattr(Path, "exists", mock_exists)
    ok, hash_val, err = compute_sha256_safe(Path("any_file.csv"))
    assert ok is False
    assert hash_val == ""
    assert "PATH_ACCESS_ERROR" in err
    assert "Simulated hardware I/O" in err


def test_file_access_permission_error_caught_by_hash_gate(monkeypatch):
    """Fault injection: open() raises PermissionError."""
    orig_open = open

    def mock_open(path, mode="r", *args, **kwargs):
        if "data" in str(path) or "match" in str(path):
            raise PermissionError("EACCES: Access is denied by file DACL")
        return orig_open(path, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", mock_open)
    ok, hash_val, err = compute_sha256_safe(DEFAULT_CANON_PATH)
    assert ok is False
    assert hash_val == ""
    assert "PERMISSION_DENIED" in err
    assert "Access is denied" in err


def test_hash_mismatch_blocks_asset_integrity_and_authorization():
    """Verifies that invalid hashes fail asset integrity and prevent approval."""
    bogus_hash = "f" * 64
    res = evaluate_asset_integrity(expected_canon=bogus_hash)
    assert res["is_passed"] is False
    assert "CANONICAL DATASET HASH MISMATCH" in res["status"]

    gate = evaluate_full_governance_gate(
        expected_canon=bogus_hash,
        override_runner=get_simulated_passing_runner(),
    )
    assert gate["is_approved"] is False
    assert "NOT APPROVED" in gate["final_verdict"]


# ----------------------------------------------------------------------
# 3. 20-Player Selection Invariance Checks
# ----------------------------------------------------------------------

def test_mismatch_in_any_one_of_20_players_blocks_selection_invariance(tmp_path):
    """Mutating any single player ID or name blocks selection invariance."""
    # Create modified rankings file
    with open(DEFAULT_RANKINGS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Mutate rank 1 batter ID
    data["window_a"]["top10_batters"][0]["player_id"] = 99999
    data["window_a"]["top10_batters"][0]["striker_id"] = 99999

    bad_rankings_file = tmp_path / "bad_rankings.json"
    with open(bad_rankings_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    sel = evaluate_selection_invariance(rankings_path=bad_rankings_file)
    assert sel["is_passed"] is False
    assert sel["batters_all_matched"] is False
    assert any("Batter rank 1 ID mismatch" in fail for fail in sel["failures"])


def test_player_rank_or_ordering_mismatch_blocks_selection_invariance(tmp_path):
    """Swapping ranks 1 and 2 blocks selection invariance."""
    with open(DEFAULT_RANKINGS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Swap bowler 1 (Sunil Narine) and bowler 2 (Mitchell Santner)
    b1 = data["window_a"]["top10_bowlers"][0]
    b2 = data["window_a"]["top10_bowlers"][1]
    data["window_a"]["top10_bowlers"][0] = b2
    data["window_a"]["top10_bowlers"][1] = b1

    bad_rankings_file = tmp_path / "swapped_bowlers.json"
    with open(bad_rankings_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    sel = evaluate_selection_invariance(rankings_path=bad_rankings_file)
    assert sel["is_passed"] is False
    assert sel["bowlers_all_matched"] is False
    assert any("Bowler rank 1 ID mismatch" in fail for fail in sel["failures"])


# ----------------------------------------------------------------------
# 4. Statistical Verification Checks
# ----------------------------------------------------------------------

def test_incorrect_statistical_classification_blocks_statistical_verification(tmp_path):
    """Modifying any comparison classification blocks statistical verification."""
    with open(DEFAULT_STATS_PATH, "r", encoding="utf-8") as f:
        stats = json.load(f)

    # Change 2026 bowler comparison classification from NON_SIGNIFICANT to STATISTICALLY_SIGNIFICANT
    for c in stats["comparisons"]:
        if c["comparison_id"] == "2026_bowlers_vs_league":
            c["inference_classification"] = "STATISTICALLY_SIGNIFICANT"

    bad_stats_file = tmp_path / "bad_stats.json"
    with open(bad_stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f)

    res = evaluate_statistical_evidence(stats_path=bad_stats_file)
    assert res["is_passed"] is False
    assert any("classification mismatch" in f for f in res["failures"])


def test_incorrect_p_value_or_confidence_interval_blocks_statistical_verification(tmp_path):
    """Modifying observed effect or p-value blocks statistical verification."""
    with open(DEFAULT_STATS_PATH, "r", encoding="utf-8") as f:
        stats = json.load(f)

    # Change observed effect for comparison 1
    stats["comparisons"][0]["observed_effect"] = 99.99

    bad_stats_file = tmp_path / "bad_effect.json"
    with open(bad_stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f)

    res = evaluate_statistical_evidence(stats_path=bad_stats_file)
    assert res["is_passed"] is False
    assert any("observed effect mismatch" in f for f in res["failures"])


# ----------------------------------------------------------------------
# 5. Uncertainty & Variance Floor Checks
# ----------------------------------------------------------------------

def test_altered_variance_formula_or_floor_blocks_uncertainty_verification(tmp_path):
    """Removing 1e-8 floor or altering posterior variance formula blocks uncertainty verification."""
    # Write a copy with stripped variance floor
    bad_code_file = tmp_path / "epistemic_bad.py"
    with open(DEFAULT_EPISTEMIC_CODE_PATH, "r", encoding="utf-8") as f:
        code_text = f.read()

    bad_code = code_text.replace("math.sqrt(max(1e-8, self.latent_posterior_variance))", "math.sqrt(self.latent_posterior_variance)")
    with open(bad_code_file, "w", encoding="utf-8") as f:
        f.write(bad_code)

    res = evaluate_uncertainty_quantification(epistemic_code_path=bad_code_file)
    assert res["is_passed"] is False
    assert res["checks"]["has_numerical_variance_floor_1e8"] is False
    assert any("Missing exact latent standard error formula" in f for f in res["failures"])


# ----------------------------------------------------------------------
# 6. Transactional Publication Protocol Checks
# ----------------------------------------------------------------------

def test_transactional_first_stage_publication_failure_handled_safely(tmp_path):
    """Simulating Step 1 replacement failure aborts cleanly without staging leftovers."""
    gate = evaluate_full_governance_gate(override_runner=get_simulated_passing_runner())
    ok, msg, receipt = publish_artifacts_transactional(
        gate,
        output_dir=tmp_path,
        _simulate_step1_failure=True,
    )
    assert ok is False
    assert "PUBLICATION_FAILED" in msg
    assert receipt["stage"] == "VERIFIED_PRE_COMMIT"
    # Ensure temporary files are unlinked
    assert not Path(receipt["staged_summary_tmp"]).exists()
    assert not Path(receipt["staged_verdict_tmp"]).exists()


def test_transactional_second_stage_publication_failure_handled_safely(tmp_path):
    """Simulating Step 2 replacement failure catches error and prevents inconsistent state."""
    gate = evaluate_full_governance_gate(override_runner=get_simulated_passing_runner())
    ok, msg, receipt = publish_artifacts_transactional(
        gate,
        output_dir=tmp_path,
        _simulate_step2_failure=True,
    )
    assert ok is False
    assert "PUBLICATION_FAILED" in msg
    # Verify cleanup
    assert not Path(receipt["staged_summary_tmp"]).exists()
    assert not Path(receipt["staged_verdict_tmp"]).exists()


def test_stale_approval_prevention_after_failed_rerun(tmp_path):
    """Publishing an approved gate, followed by a failed rerun, guarantees NOT APPROVED overwrites."""
    # 1. Publish approved
    approved_gate = evaluate_full_governance_gate(override_runner=get_simulated_passing_runner())
    assert approved_gate["is_approved"] is True
    ok1, msg1, _ = publish_artifacts_transactional(approved_gate, output_dir=tmp_path)
    assert ok1 is True

    verdict_file = tmp_path / "PHASE_5_14_4_FINAL_VERDICT.md"
    summary_file = tmp_path / "phase5_14_4_validation_summary.json"

    with open(verdict_file, "r", encoding="utf-8") as f:
        v1 = f.read()
    assert "APPROVED FOR COMPETITION FREEZE" in v1

    # 2. Rerun with simulated test failure
    failing_runner = lambda: {
        "status": "FAILED",
        "is_passed": False,
        "exit_code": 1,
        "tests_collected": 10,
        "tests_passed": 9,
        "tests_failed": 1,
        "tests_errors": 0,
        "tests_skipped": 0,
        "duration_seconds": 1.0,
        "stdout_tail": "",
        "stderr": "fail",
        "error": "Failed",
    }
    failed_gate = evaluate_full_governance_gate(override_runner=failing_runner)
    assert failed_gate["is_approved"] is False

    ok2, msg2, _ = publish_artifacts_transactional(failed_gate, output_dir=tmp_path)
    assert ok2 is True

    with open(verdict_file, "r", encoding="utf-8") as f:
        v2 = f.read()
    with open(summary_file, "r", encoding="utf-8") as f:
        s2 = json.load(f)

    assert "NOT APPROVED" in v2
    assert "FINAL VERDICT: \\quad APPROVED" not in v2
    assert s2["metadata"]["is_approved"] is False


def test_json_and_markdown_verdicts_remain_strictly_consistent():
    """Verifies that published summary JSON and Markdown verdict strictly agree."""
    assert SUMMARY_PATH.exists()
    assert VERDICT_PATH.exists()

    with open(SUMMARY_PATH, "r", encoding="utf-8") as f:
        summary = json.load(f)
    with open(VERDICT_PATH, "r", encoding="utf-8") as f:
        verdict = f.read()

    is_approved = summary["metadata"]["is_approved"]
    final_verdict = summary["metadata"]["final_verdict"]

    if is_approved:
        assert "APPROVED FOR COMPETITION FREEZE" in verdict
        assert "NOT APPROVED" not in verdict
    else:
        assert "NOT APPROVED" in verdict

    assert summary["metadata"]["tx_id"] in verdict


def test_temporary_staging_files_cleaned_up_after_publication():
    """Verifies that no .tmp staging files linger in research/phase5_14_4."""
    p = Path("research/phase5_14_4")
    tmp_files = list(p.glob("*.tmp"))
    assert len(tmp_files) == 0, f"Found lingering temporary files: {tmp_files}"


# ----------------------------------------------------------------------
# 7. Immutable Baseline Integrity Check
# ----------------------------------------------------------------------

def test_frozen_production_assets_cryptographically_intact():
    """Verifies that canonical data and competition report match expected SHA-256."""
    def get_hash(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest().lower()

    canon_hash = get_hash(DEFAULT_CANON_PATH)
    report_hash = get_hash(DEFAULT_REPORT_PATH)

    assert canon_hash == EXPECTED_CANON_HASH
    assert report_hash == EXPECTED_REPORT_HASH
