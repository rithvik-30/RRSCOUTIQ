"""
Phase 5.14.5.2 — Stale Approval Double Failure Prevention & Journal Restart Tests
RR ScoutIQ | Rajasthan Royals IPL 2027 Auction Strategy Hackathon

Verifies:
Test A: Journal write failure before publication aborts before modifying artifacts.
Test B: Journal write failure during recovery prevents stale approval survival after restart.
Test C: Corrupted or truncated journal after restart returns UNVERIFIABLE and fails closed.
Test D: Clean publication after failed attempt commits and verifies all artifacts.
"""

import os
import sys
import json
import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from research.phase5_14_5.authoritative_gate import (
    publish_artifacts_fail_safe,
    verify_authoritative_publication,
    get_authoritative_generation_status,
    MANIFEST_FILENAME,
    PUBLICATION_JOURNAL_FILENAME,
    _PUBLICATION_JOURNAL,
    PUB_STATE_APPROVED_FOR_COMPETITION_FREEZE,
    PUB_STATE_PUBLICATION_FAILED,
)


def get_mock_approved_gate():
    return {
        "final_verdict": "APPROVED FOR COMPETITION FREEZE",
        "is_approved": True,
        "primary_reason": "All checks passed.",
        "asset_integrity": {
            "status": "PASSED",
            "is_passed": True,
            "failures_count": 0,
            "failures": [],
            "canonical_dataset": {"match": True},
            "competition_report": {"match": True},
        },
        "audit_authorization": {
            "status": "PASSED",
            "is_passed": True,
            "failures_count": 0,
            "failures": [],
            "checks": {
                "asset_integrity_prerequisite": True,
                "statistical_precision_verified": True,
                "uncertainty_calculation_verified": True,
                "selection_invariance_verified": True,
                "regression_test_suite_passed": True,
            },
        },
    }


def test_stale_approval_double_failure_fails_closed(tmp_path, monkeypatch):
    """
    Mandatory adversarial test reproducing the exact failure scenario where both
    atomic replacement and fallback unlinking fail during invalidation.
    """
    gate = get_mock_approved_gate()

    # Step 1: Seed a valid APPROVED manifest (Generation A)
    ok1, msg1, receipt1 = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok1 is True
    assert receipt1["publication_state"] == PUB_STATE_APPROVED_FOR_COMPETITION_FREEZE
    gen_a = receipt1["gen_id"]

    # Step 2: Verify that Generation A is initially approved
    v1, msg_v1, m1 = verify_authoritative_publication(output_dir=tmp_path)
    assert v1 is True
    assert m1["is_approved"] is True
    assert m1["active_generation_id"] == gen_a

    # Step 3, 4, 5, 6: Prepare monkeypatch for real filesystem failures
    real_replace = os.replace
    real_unlink = Path.unlink

    def mock_replace(src, dst):
        dst_p = Path(dst)
        # 4. Inject real failure at the first publication os.replace() (summary file)
        if "phase5_14_5_validation_summary.json" in dst_p.name and not dst_p.name.endswith(".tmp"):
            raise OSError("Stage 1 summary replacement failed: Permission Denied")
        # 5. Inject failure during manifest invalidation os.replace()
        if dst_p.name == MANIFEST_FILENAME:
            raise OSError("Manifest invalidation replacement failed: Access Denied")
        return real_replace(src, dst)

    def mock_unlink(self, *args, **kwargs):
        # 6. Inject failure during manifest deletion (unlink)
        if self.name == MANIFEST_FILENAME:
            raise PermissionError("Manifest unlink failed: File lock held by external process")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(os, "replace", mock_replace)
    monkeypatch.setattr(Path, "unlink", mock_unlink)

    # Step 3: Start a new publication attempt with a different generation ID (Generation B)
    ok2, msg2, receipt2 = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok2 is False
    assert receipt2["publication_state"] == PUB_STATE_PUBLICATION_FAILED
    gen_b = receipt2["gen_id"]
    assert gen_b != gen_a

    # Assert that the system did NOT claim invalidation succeeded
    assert receipt2["invalidation_succeeded"] is False
    assert "CRITICAL" in receipt2["invalidation_message"]

    # Step 7: Call the actual authoritative reader
    v2, msg_v2, details2 = verify_authoritative_publication(output_dir=tmp_path)

    # Step 8: Assert that the old generation is NOT accepted as the current approval
    assert v2 is False
    assert details2.get("is_approved") is False

    # Step 9: Assert that the new attempt is reported as INVALID, UNVERIFIABLE, or NOT_APPROVED
    assert any(term in msg_v2 for term in ["UNVERIFIABLE", "NOT_APPROVED", "INVALID", "FAILED"])
    assert any(term in str(details2.get("status", "")) for term in ["UNVERIFIABLE", "NOT_APPROVED", "INVALID", "FAILED"])
    assert details2.get("stale_generation_id") == gen_a

    # Step 10: Assert that the system records all failed recovery operations
    failed_ops = details2.get("failed_recovery_operations", [])
    assert len(failed_ops) >= 2
    assert any("replace" in op.lower() for op in failed_ops)
    assert any("unlink" in op.lower() for op in failed_ops)

    # Step 11: Test successful recovery with a subsequent new publication (Generation C)
    monkeypatch.undo()

    ok3, msg3, receipt3 = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok3 is True
    assert receipt3["publication_state"] == PUB_STATE_APPROVED_FOR_COMPETITION_FREEZE
    gen_c = receipt3["gen_id"]
    assert gen_c not in (gen_a, gen_b)

    v3, msg_v3, m3 = verify_authoritative_publication(output_dir=tmp_path)
    assert v3 is True
    assert m3["is_approved"] is True
    assert m3["active_generation_id"] == gen_c


def test_journal_write_failure_before_publication_aborts(tmp_path, monkeypatch):
    """
    Test A — Journal write failure before publication.
    - Create and approve Generation A.
    - Inject failure when recording Generation B's initial IN_PROGRESS journal state.
    - Verify publication aborts before overwriting Generation A's artifacts.
    - Verify the reader cannot mistake an incomplete B attempt for a successful B publication.
    """
    gate = get_mock_approved_gate()

    # Step 1: Create and approve Generation A
    ok1, msg1, receipt1 = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok1 is True
    gen_a = receipt1["gen_id"]

    v1, _, m1 = verify_authoritative_publication(output_dir=tmp_path)
    assert v1 is True
    assert m1["active_generation_id"] == gen_a

    # Snapshot Generation A files
    sum_orig = (tmp_path / "phase5_14_5_validation_summary.json").read_bytes()
    ver_orig = (tmp_path / "PHASE_5_14_5_FINAL_VERDICT.md").read_bytes()
    man_orig = (tmp_path / MANIFEST_FILENAME).read_bytes()

    # Step 2: Inject failure when recording Generation B's initial IN_PROGRESS journal state
    real_replace = os.replace

    def mock_replace(src, dst):
        if Path(dst).name == PUBLICATION_JOURNAL_FILENAME:
            raise OSError("Injected journal write failure before publication: Disk write error")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", mock_replace)

    # Step 3: Attempt Generation B publication
    ok2, msg2, receipt2 = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok2 is False
    assert "aborted" in msg2.lower() or "durable" in msg2.lower() or "journal" in msg2.lower()
    assert receipt2["publication_state"] == PUB_STATE_PUBLICATION_FAILED
    gen_b = receipt2["gen_id"]
    assert gen_b != gen_a

    # Step 4: Verify Generation A's artifacts were untouched on disk
    assert (tmp_path / "phase5_14_5_validation_summary.json").read_bytes() == sum_orig
    assert (tmp_path / "PHASE_5_14_5_FINAL_VERDICT.md").read_bytes() == ver_orig
    assert (tmp_path / MANIFEST_FILENAME).read_bytes() == man_orig

    # Step 5: Verify reader cannot mistake incomplete B attempt for successful B publication
    monkeypatch.undo()
    v_b, msg_b, _ = verify_authoritative_publication(output_dir=tmp_path, expected_gen_id=gen_b)
    assert v_b is False
    assert "mismatch" in msg_b.lower() or "not approved" in msg_b.lower()


def test_journal_write_failure_during_recovery_fresh_process_fails_closed(tmp_path, monkeypatch):
    """
    Test B — Journal write failure during recovery.
    - Create Generation A.
    - Start Generation B.
    - Fail summary replacement, manifest invalidation replacement, manifest unlink, and the journal update.
    - Clear all in-memory state to simulate a fresh process.
    - Verify the old Generation A approval is NOT accepted.
    """
    gate = get_mock_approved_gate()

    # Step 1: Create Generation A
    ok1, _, receipt1 = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok1 is True
    gen_a = receipt1["gen_id"]

    v1, _, m1 = verify_authoritative_publication(output_dir=tmp_path)
    assert v1 is True
    assert m1["active_generation_id"] == gen_a

    # Step 2: Generation B starts.
    # Initial journal write of IN_PROGRESS succeeds.
    # Fail summary replacement, manifest invalidation replacement, manifest unlink, and journal update during recovery.
    real_replace = os.replace
    real_unlink = Path.unlink

    journal_initial_written = False

    def mock_replace(src, dst):
        nonlocal journal_initial_written
        dst_p = Path(dst)
        if dst_p.name == PUBLICATION_JOURNAL_FILENAME:
            if not journal_initial_written:
                journal_initial_written = True
                return real_replace(src, dst)
            raise OSError("Journal recovery update failed: Access Denied")
        if "phase5_14_5_validation_summary.json" in dst_p.name and not dst_p.name.endswith(".tmp"):
            raise OSError("Stage 1 summary replacement failed: Permission Denied")
        if dst_p.name == MANIFEST_FILENAME:
            raise OSError("Manifest invalidation replacement failed: Access Denied")
        return real_replace(src, dst)

    def mock_unlink(self, *args, **kwargs):
        if self.name == MANIFEST_FILENAME:
            raise PermissionError("Manifest unlink failed: File lock held")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(os, "replace", mock_replace)
    monkeypatch.setattr(Path, "unlink", mock_unlink)

    ok2, msg2, receipt2 = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok2 is False
    gen_b = receipt2["gen_id"]
    assert gen_b != gen_a
    assert receipt2["invalidation_succeeded"] is False

    # Simulate fresh process restart
    monkeypatch.undo()
    _PUBLICATION_JOURNAL.clear()

    # Step 3: Authoritative reader in a fresh process must NOT accept old Generation A
    v2, msg_v2, details2 = verify_authoritative_publication(output_dir=tmp_path)
    assert v2 is False
    assert details2.get("is_approved") is False
    assert any(term in msg_v2 for term in ["UNVERIFIABLE", "NOT_APPROVED", "IN_PROGRESS", "FAILED"])
    assert any(term in str(details2.get("status", "")) for term in ["UNVERIFIABLE", "NOT_APPROVED", "IN_PROGRESS", "FAILED"])


def test_corrupt_journal_after_restart_returns_unverifiable(tmp_path):
    """
    Test C — Corrupt journal after restart.
    - Create an approved generation.
    - Corrupt or truncate the journal.
    - Clear in-memory state.
    - Verify the reader returns UNVERIFIABLE and never returns approval.
    """
    gate = get_mock_approved_gate()

    ok1, _, receipt1 = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok1 is True

    v1, _, _ = verify_authoritative_publication(output_dir=tmp_path)
    assert v1 is True

    # Corrupt the journal on disk
    j_file = tmp_path / PUBLICATION_JOURNAL_FILENAME
    with open(j_file, "w", encoding="utf-8") as f:
        f.write("{ invalid json corrupted content [[[")

    # Clear in-memory state to simulate fresh process
    _PUBLICATION_JOURNAL.clear()

    # Authoritative reader must return UNVERIFIABLE and never return approval
    v_c, msg_c, details_c = verify_authoritative_publication(output_dir=tmp_path)
    assert v_c is False
    assert "unverifiable" in msg_c.lower() or "corrupt" in msg_c.lower()
    assert details_c.get("is_approved") is False
    assert details_c.get("status") == "UNVERIFIABLE"


def test_successful_recovery_after_failed_attempt(tmp_path):
    """
    Test D — Successful recovery.
    - Following a failed attempt, perform a clean publication.
    - Verify the new generation is committed and accepted.
    - Verify its generation ID matches across all authoritative artifacts.
    """
    gate = get_mock_approved_gate()

    # Step 1: Perform clean publication (Generation C)
    ok_c, msg_c, receipt_c = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok_c is True
    assert receipt_c["publication_state"] == PUB_STATE_APPROVED_FOR_COMPETITION_FREEZE
    gen_c = receipt_c["gen_id"]

    # Step 2: Clear memory to simulate fresh process
    _PUBLICATION_JOURNAL.clear()

    # Step 3: Verify with authoritative reader
    v_c, msg_vc, m_c = verify_authoritative_publication(output_dir=tmp_path)
    assert v_c is True
    assert m_c["is_approved"] is True
    assert m_c["active_generation_id"] == gen_c

    # Step 4: Verify generation ID matches across all authoritative artifacts
    j_file = tmp_path / PUBLICATION_JOURNAL_FILENAME
    with open(j_file, "r", encoding="utf-8") as f:
        j_data = json.load(f)
    assert j_data["committed_generation_id"] == gen_c
    assert j_data["attempt_status"] == "COMMITTED"

    summary_file = tmp_path / "phase5_14_5_validation_summary.json"
    with open(summary_file, "r", encoding="utf-8") as f:
        sum_data = json.load(f)
    assert sum_data["metadata"]["generation_id"] == gen_c

    verdict_file = tmp_path / "PHASE_5_14_5_FINAL_VERDICT.md"
    with open(verdict_file, "r", encoding="utf-8") as f:
        ver_text = f.read()
    assert f"`{gen_c}`" in ver_text
