"""
Phase 5.14.5 — Subprocess Runner and Pytest Parser Tests
Verifies:
  1. Valid pytest execution with a complete, parseable summary.
  2. Nonzero process exit code.
  3. Missing pytest executable (FileNotFoundError).
  4. Subprocess timeout (subprocess.TimeoutExpired).
  5. Malformed pytest output (missing summary line).
  6. Empty output.
  7. Output containing a misleading partial passing count with nonzero exit code.
  8. Output containing failures or errors.
  9. Output with skipped tests (policy enforcement).
  10. Inconsistent reported totals (collected != sum of parts).
  11. Real execution through python subprocess.
"""

import os
import sys
import subprocess
import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from research.phase5_14_5.authoritative_gate import (
    parse_pytest_terminal_output,
    execute_repository_tests,
)

def test_valid_pytest_complete_summary_parsed():
    stdout = """
============================= test session starts =============================
collected 114 items

tests/m5_5b_4_3_8/test_context.py ......................... [ 21%]
........................................................................ [ 85%]
..................                                                       [100%]
============================= 114 passed in 45.41s =============================
"""
    res = parse_pytest_terminal_output(stdout=stdout, stderr="", exit_code=0)
    assert res["is_passed"] is True
    assert res["status"] == "PASSED"
    assert res["tests_collected"] == 114
    assert res["tests_passed"] == 114
    assert res["tests_failed"] == 0
    assert res["tests_errors"] == 0
    assert res["tests_skipped"] == 0
    assert res["duration_seconds"] == 45.41


def test_nonzero_process_exit_code_fails():
    stdout = "10 passed, 2 failed in 5.20s"
    res = parse_pytest_terminal_output(stdout=stdout, stderr="AssertionError", exit_code=1)
    assert res["is_passed"] is False
    assert res["exit_code"] == 1
    assert res["tests_failed"] == 2
    assert "Non-zero exit code" in res["error"]


def test_missing_pytest_executable_handled(monkeypatch):
    def mock_run(*args, **kwargs):
        raise FileNotFoundError("[WinError 2] The system cannot find the file specified")

    monkeypatch.setattr(subprocess, "run", mock_run)
    res = execute_repository_tests()
    assert res["is_passed"] is False
    assert res["status"] == "EXECUTABLE_NOT_FOUND"
    assert res["tests_errors"] == 1


def test_subprocess_timeout_handled(monkeypatch):
    def mock_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=180)

    monkeypatch.setattr(subprocess, "run", mock_run)
    res = execute_repository_tests(timeout_seconds=180)
    assert res["is_passed"] is False
    assert res["status"] == "TIMED_OUT"
    assert res["tests_errors"] == 1


def test_malformed_pytest_output_fails():
    stdout = "Running tests...\nDone with some items."
    res = parse_pytest_terminal_output(stdout=stdout, stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert "MALFORMED OUTPUT" in res["status"]
    assert res["parse_success"] is False


def test_empty_output_fails():
    res = parse_pytest_terminal_output(stdout="", stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert "EMPTY OUTPUT" in res["status"]


def test_misleading_partial_passing_count_fails():
    stdout = "10 passed in 2.0s\nProcess crashed with exit code 2"
    res = parse_pytest_terminal_output(stdout=stdout, stderr="Segmentation fault", exit_code=2)
    assert res["is_passed"] is False
    assert "Non-zero exit code" in res["error"]


def test_failures_or_errors_in_output_fails():
    stdout = "95 passed, 1 failed, 1 error in 32.10s"
    res = parse_pytest_terminal_output(stdout=stdout, stderr="", exit_code=1)
    assert res["is_passed"] is False
    assert res["tests_failed"] == 1
    assert res["tests_errors"] == 1
    assert res["tests_passed"] == 95


def test_skipped_tests_policy_enforcement():
    stdout = "100 passed, 2 skipped in 10.0s"
    # When allow_skipped is True (default)
    res_allowed = parse_pytest_terminal_output(stdout=stdout, stderr="", exit_code=0, allow_skipped=True)
    assert res_allowed["is_passed"] is True
    assert res_allowed["tests_skipped"] == 2

    # When allow_skipped is False
    res_disallowed = parse_pytest_terminal_output(stdout=stdout, stderr="", exit_code=0, allow_skipped=False)
    assert res_disallowed["is_passed"] is False
    assert "skipped tests not permitted" in res_disallowed["error"]


def test_inconsistent_reported_totals_fails():
    # Pytest reported collected 50, but parsed sum is 40
    stdout = "collected 50 items\n40 passed in 10.0s"
    res = parse_pytest_terminal_output(stdout=stdout, stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert "INCONSISTENT REPORTED TOTALS" in res["status"]
    assert res["tests_collected"] == 50


def test_real_subprocess_execution_with_python():
    """Execute a real subprocess targeting a minimal test command to verify end-to-end piping."""
    cmd = [sys.executable, "-m", "pytest", "--version"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert proc.returncode == 0
    assert "pytest" in (proc.stdout + proc.stderr).lower()
