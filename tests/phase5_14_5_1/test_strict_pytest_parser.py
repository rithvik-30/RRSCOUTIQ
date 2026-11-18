"""
Phase 5.14.5.1 — Strict Pytest Terminal Summary Parser Adversarial Tests
RR ScoutIQ | Rajasthan Royals IPL 2027 Auction Strategy Hackathon

Verifies Fix A:
1. Rejects bare passing-count substrings ("1 passed" without a genuine summary).
2. Rejects ordinary log lines containing "1 passed" or "2 passed".
3. Rejects empty stdout.
4. Rejects malformed summary lines.
5. Rejects truncated summary lines.
6. Rejects summary lines missing duration.
7. Rejects duplicate conflicting summary lines in terminal output.
8. Rejects nonzero exit code despite an apparent passing summary line.
9. Accepts valid complete pytest summary output with duration.
10. Accepts valid complete pytest summary output containing skipped tests under permissive policy.
11. Rejects skipped tests when strict policy is enforced (allow_skipped=False).
12. Rejects inconsistent totals (reported collected != sum of execution outcomes).
13. Distinguishes real terminal summaries from arbitrary prose.
"""

import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from research.phase5_14_5.authoritative_gate import parse_pytest_terminal_output


def test_bare_passed_substring_fails():
    """Adversarial: '1 passed' without summary markers or duration must fail closed."""
    res = parse_pytest_terminal_output(stdout="1 passed", stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert res["parse_success"] is False
    assert "MALFORMED OUTPUT" in res["status"]
    assert "does not contain a recognizable" in res["error"].lower()


def test_logging_prose_containing_passed_fails():
    """Adversarial: ordinary logging prose containing '1 passed' or '3 passed' must not be parsed as summary."""
    prose = """
    2026-11-18 14:22:01,123 [INFO] worker-1: Processing test batch...
    2026-11-18 14:22:02,456 [INFO] worker-1: Verified item: 1 passed sanity check.
    2026-11-18 14:22:03,789 [INFO] worker-1: Finished batch execution.
    """
    res = parse_pytest_terminal_output(stdout=prose, stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert res["parse_success"] is False
    assert "MALFORMED OUTPUT" in res["status"]


def test_empty_stdout_fails():
    """Empty stdout must fail closed."""
    res = parse_pytest_terminal_output(stdout="", stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert res["parse_success"] is False
    assert res["status"] == "FAILED — EMPTY OUTPUT"


def test_whitespace_only_stdout_fails():
    """Whitespace-only stdout must fail closed."""
    res = parse_pytest_terminal_output(stdout="   \n  \t  \n  ", stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert res["parse_success"] is False
    assert res["status"] == "FAILED — EMPTY OUTPUT"


def test_truncated_summary_fails():
    """Summary line cut off before completion or duration must fail closed."""
    truncated = "=== 132 passed"
    res = parse_pytest_terminal_output(stdout=truncated, stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert res["parse_success"] is False
    assert "MALFORMED OUTPUT" in res["status"]


def test_missing_duration_fails():
    """Summary line without valid duration 'in <X>s' must fail closed."""
    no_dur = "============================= 114 passed ============================="
    res = parse_pytest_terminal_output(stdout=no_dur, stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert res["parse_success"] is False
    assert "MALFORMED OUTPUT" in res["status"]


def test_duplicate_conflicting_summary_lines_fails():
    """Adversarial: conflicting summary lines in stdout must trigger duplicate conflicting rejection."""
    conflicting = """
    ============================= 10 passed in 2.50s =============================
    ============================= 20 passed in 5.00s =============================
    """
    res = parse_pytest_terminal_output(stdout=conflicting, stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert res["parse_success"] is False
    assert "DUPLICATE CONFLICTING SUMMARY LINES" in res["status"]


def test_nonzero_exit_code_with_passing_summary_fails():
    """A passing summary line accompanied by nonzero exit code must fail closed."""
    stdout = "============================= 114 passed in 45.41s ============================="
    res = parse_pytest_terminal_output(stdout=stdout, stderr="Process aborted by signal", exit_code=137)
    assert res["is_passed"] is False
    assert res["exit_code"] == 137
    assert "Non-zero exit code" in res["error"]


def test_valid_complete_pytest_summary_succeeds():
    """Realistic complete pytest output with test collection, progress dots, and summary line passes."""
    stdout = """
============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0
rootdir: C:\\Users\\rithv\\OneDrive\\Documents\\Desktop\\RR_ScoutIQ
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


def test_valid_complete_pytest_summary_with_skipped_tests():
    """Output with skipped tests is tracked accurately and allowed when policy permits."""
    stdout = """
============================= test session starts =============================
collected 102 items

tests/unit/test_a.py .................................................... [ 50%]
tests/unit/test_b.py ...................................s.s              [100%]
======================== 100 passed, 2 skipped in 14.20s =======================
"""
    # Allowed
    res_ok = parse_pytest_terminal_output(stdout=stdout, stderr="", exit_code=0, allow_skipped=True)
    assert res_ok["is_passed"] is True
    assert res_ok["tests_passed"] == 100
    assert res_ok["tests_skipped"] == 2
    assert res_ok["tests_collected"] == 102
    assert res_ok["duration_seconds"] == 14.20

    # Disallowed under strict policy
    res_strict = parse_pytest_terminal_output(stdout=stdout, stderr="", exit_code=0, allow_skipped=False)
    assert res_strict["is_passed"] is False
    assert "skipped tests not permitted" in res_strict["error"]


def test_inconsistent_totals_fails():
    """Mismatch between reported collected count and sum of outcomes must fail closed."""
    stdout = """
============================= test session starts =============================
collected 100 items

============================= 90 passed in 10.00s =============================
"""
    res = parse_pytest_terminal_output(stdout=stdout, stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert "INCONSISTENT REPORTED TOTALS" in res["status"]
    assert "Item count mismatch" in res["error"]
