"""
Phase 5.14.5.2 — Terminal Summary Finality & Adversarial Pytest Output Tests
RR ScoutIQ | Rajasthan Royals IPL 2027 Auction Strategy Hackathon

Verifies Fix A:
1. Rejects bare passing-count text without a summary ("1 passed").
2. Rejects ordinary log messages containing passing-count phrases.
3. Rejects empty or whitespace-only stdout.
4. Rejects truncated summary lines.
5. Rejects summary lines missing duration or with invalid duration.
6. Rejects summary lines with zero seconds (e.g., in 0.00s or in 0s).
7. Rejects two identical pytest summary lines.
8. Rejects two conflicting pytest summary lines.
9. Rejects a valid-looking summary followed by an error message.
10. Rejects a valid-looking summary followed by unfinished test progress output.
11. Rejects nonzero exit codes even if summary text appears passing.
12. Accepts valid complete pytest output with strictly positive duration.
13. Accurately tracks skipped tests and enforces allow_skipped policy.
14. Rejects inconsistent outcome counts (collected count != outcome sum).
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath("."))

from research.phase5_14_5.authoritative_gate import parse_pytest_terminal_output


def test_bare_passed_count_fails():
    """Adversarial: '1 passed' without summary markers or duration must fail closed."""
    res = parse_pytest_terminal_output(stdout="1 passed", stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert res["parse_success"] is False
    assert "MALFORMED OUTPUT" in res["status"]


def test_log_messages_with_passed_phrase_fails():
    """Adversarial: log lines containing '1 passed' or '5 passed' must not pass as summary."""
    stdout = """
    2026-11-18 19:40:01 [INFO] Initializing test runner...
    2026-11-18 19:40:02 [INFO] Subprocess status: 1 passed filter check.
    2026-11-18 19:40:03 [INFO] Teardown complete.
    """
    res = parse_pytest_terminal_output(stdout=stdout, stderr="", exit_code=0)
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
    res = parse_pytest_terminal_output(stdout="   \n \t  \r\n  ", stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert res["parse_success"] is False
    assert res["status"] == "FAILED — EMPTY OUTPUT"


def test_truncated_summary_fails():
    """Truncated summary without completion markers or duration must fail closed."""
    res = parse_pytest_terminal_output(stdout="=== 45 passed", stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert res["parse_success"] is False
    assert "MALFORMED OUTPUT" in res["status"]


def test_summary_followed_by_error_message_fails():
    """Adversarial: valid summary followed by post-summary error must fail closed."""
    stdout = """
============================= test session starts =============================
collected 20 items

test_module.py ....................                                     [100%]
============================== 20 passed in 1.45s ==============================
ERROR: process terminated after summary
"""
    res = parse_pytest_terminal_output(stdout=stdout, stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert res["parse_success"] is False
    assert "NON-EMPTY OUTPUT DETECTED AFTER SUMMARY LINE" in res["status"]
    assert "trailing non-empty line" in res["error"].lower()


def test_summary_followed_by_unfinished_progress_fails():
    """Adversarial: valid summary followed by unfinished test progress must fail closed."""
    stdout = """
============================= test session starts =============================
collected 30 items

test_a.py ...........                                                   [ 33%]
============================== 10 passed in 0.85s ==============================
test_b.py ..........                                                    [ 66%]
"""
    res = parse_pytest_terminal_output(stdout=stdout, stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert res["parse_success"] is False
    assert "NON-EMPTY OUTPUT DETECTED AFTER SUMMARY LINE" in res["status"]


def test_two_identical_summaries_fails():
    """Adversarial: duplicate identical summary lines must fail closed."""
    stdout = """
============================= test session starts =============================
collected 15 items
============================== 15 passed in 2.10s ==============================
============================== 15 passed in 2.10s ==============================
"""
    res = parse_pytest_terminal_output(stdout=stdout, stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert res["parse_success"] is False
    assert "DUPLICATE SUMMARY LINES DETECTED" in res["status"]


def test_two_conflicting_summaries_fails():
    """Adversarial: duplicate conflicting summary lines must fail closed."""
    stdout = """
============================= test session starts =============================
============================== 15 passed in 2.10s ==============================
============================== 10 passed in 1.50s ==============================
"""
    res = parse_pytest_terminal_output(stdout=stdout, stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert res["parse_success"] is False
    assert "DUPLICATE CONFLICTING SUMMARY LINES DETECTED" in res["status"]


def test_zero_second_duration_fails():
    """Adversarial: summary reporting zero seconds (in 0.00s or in 0s) must fail closed."""
    stdout = "============================== 10 passed in 0.00s =============================="
    res = parse_pytest_terminal_output(stdout=stdout, stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert res["parse_success"] is False
    assert "ZERO OR INVALID DURATION REPORTED" in res["status"]
    assert res["duration_seconds"] == 0.0


def test_missing_or_invalid_duration_fails():
    """Adversarial: summary missing 'in <duration>s' format must fail closed."""
    stdout = "============================== 10 passed =============================="
    res = parse_pytest_terminal_output(stdout=stdout, stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert res["parse_success"] is False
    assert "MALFORMED OUTPUT" in res["status"]


def test_nonzero_exit_code_fails():
    """Summary line appears passing, but exit code is nonzero -> must fail closed."""
    stdout = "============================== 25 passed in 3.12s =============================="
    res = parse_pytest_terminal_output(stdout=stdout, stderr="SIGKILL", exit_code=137)
    assert res["is_passed"] is False
    assert res["exit_code"] == 137
    assert "Non-zero exit code" in res["error"]


def test_valid_complete_pytest_summary_passes():
    """Realistic complete pytest output with test collection, progress, and terminal summary passes."""
    stdout = """
============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0
rootdir: C:\\Users\\rithv\\OneDrive\\Documents\\Desktop\\RR_ScoutIQ
collected 47 items

tests/phase5_14_5_1/test_a.py ......................... [ 53%]
tests/phase5_14_5_1/test_b.py ......................    [100%]
============================= 47 passed in 1.37s ==============================
"""
    res = parse_pytest_terminal_output(stdout=stdout, stderr="", exit_code=0)
    assert res["is_passed"] is True
    assert res["status"] == "PASSED"
    assert res["tests_collected"] == 47
    assert res["tests_passed"] == 47
    assert res["tests_failed"] == 0
    assert res["tests_errors"] == 0
    assert res["tests_skipped"] == 0
    assert res["duration_seconds"] == 1.37


def test_skipped_tests_policy():
    """Summary with skipped tests is accepted when policy allows, and rejected when strict."""
    stdout = """
============================= test session starts =============================
collected 50 items

tests/test_x.py .................................................. [100%]
======================== 48 passed, 2 skipped in 3.45s =========================
"""
    # Allowed
    res_ok = parse_pytest_terminal_output(stdout=stdout, stderr="", exit_code=0, allow_skipped=True)
    assert res_ok["is_passed"] is True
    assert res_ok["tests_passed"] == 48
    assert res_ok["tests_skipped"] == 2
    assert res_ok["tests_collected"] == 50
    assert res_ok["duration_seconds"] == 3.45

    # Disallowed under strict policy
    res_strict = parse_pytest_terminal_output(stdout=stdout, stderr="", exit_code=0, allow_skipped=False)
    assert res_strict["is_passed"] is False
    assert "skipped tests not permitted" in res_strict["error"]


def test_inconsistent_item_count_fails():
    """Reported collected items mismatching sum of execution outcomes must fail closed."""
    stdout = """
============================= test session starts =============================
collected 50 items

============================= 40 passed in 2.10s ==============================
"""
    res = parse_pytest_terminal_output(stdout=stdout, stderr="", exit_code=0)
    assert res["is_passed"] is False
    assert "INCONSISTENT REPORTED TOTALS" in res["status"]
    assert "Item count mismatch" in res["error"]
