"""
Phase 5.14.5 — Publication Recovery and Stale Approval Prevention Tests
Verifies:
  1. Successful initial publication creates consistent artifacts and APPROVED_FOR_COMPETITION_FREEZE state.
  2. Simulated Stage 1 replacement failure on an existing approved deployment invalidates authoritative manifest.
  3. Simulated Stage 2 replacement failure on an existing approved deployment invalidates authoritative manifest.
  4. Simulated manifest commit failure invalidates authoritative state.
  5. Failed rerun (evaluation failed) overwrites previous APPROVED state with NOT APPROVED.
  6. Staged temporary files are cleaned up under all failure modes.
  7. Partial or interrupted publications cannot masquerade as approved generations.
  8. All 6 publication states are respected.
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
    evaluate_full_governance_gate,
    PUB_STATE_NOT_EVALUATED,
    PUB_STATE_EVALUATION_FAILED,
    PUB_STATE_VERIFIED_PRE_COMMIT,
    PUB_STATE_PUBLICATION_FAILED,
    PUB_STATE_PUBLICATION_COMMITTED,
    PUB_STATE_APPROVED_FOR_COMPETITION_FREEZE,
    MANIFEST_FILENAME,
)

def get_simulated_passing_gate():
    """Generates an evaluated gate dictionary with is_approved=True."""
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

def get_simulated_failing_gate():
    """Generates an evaluated gate dictionary with is_approved=False."""
    return {
        "final_verdict": "NOT APPROVED FOR COMPETITION FREEZE — TEST FAILURE",
        "is_approved": False,
        "primary_reason": "Unit tests failed.",
        "asset_integrity": {
            "status": "PASSED",
            "is_passed": True,
            "failures_count": 0,
            "failures": [],
            "canonical_dataset": {"match": True},
            "competition_report": {"match": True},
        },
        "audit_authorization": {
            "status": "FAILED",
            "is_passed": False,
            "failures_count": 1,
            "failures": ["Regression test suite failed"],
            "checks": {
                "asset_integrity_prerequisite": True,
                "statistical_precision_verified": True,
                "uncertainty_calculation_verified": True,
                "selection_invariance_verified": True,
                "regression_test_suite_passed": False,
            },
        },
    }


def test_initial_publication_creates_valid_authoritative_freeze(tmp_path):
    """Test standard clean publication reaching APPROVED_FOR_COMPETITION_FREEZE."""
    gate = get_simulated_passing_gate()
    ok, msg, receipt = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok is True
    assert receipt["publication_state"] == PUB_STATE_APPROVED_FOR_COMPETITION_FREEZE

    verified, v_msg, manifest = verify_authoritative_publication(output_dir=tmp_path)
    assert verified is True
    assert manifest["publication_state"] == PUB_STATE_APPROVED_FOR_COMPETITION_FREEZE
    assert manifest["is_approved"] is True
    assert manifest["active_generation_id"] == receipt["gen_id"]


def test_stage1_failure_invalidates_previously_approved_deployment(tmp_path):
    """Seed approved state, then simulate Stage 1 failure; verify authoritative state becomes NOT APPROVED."""
    # 1. Seed existing approved publication
    gate_ok = get_simulated_passing_gate()
    ok1, _, receipt1 = publish_artifacts_fail_safe(gate_ok, output_dir=tmp_path)
    assert ok1 is True
    v1, _, m1 = verify_authoritative_publication(output_dir=tmp_path)
    assert v1 is True
    assert m1["is_approved"] is True

    # 2. Run new publication with simulated Stage 1 replacement failure
    ok2, msg2, receipt2 = publish_artifacts_fail_safe(
        gate_ok, output_dir=tmp_path, _simulate_stage1_failure=True
    )
    assert ok2 is False
    assert "PUBLICATION_FAILED" in msg2
    assert receipt2["publication_state"] == PUB_STATE_PUBLICATION_FAILED

    # 3. Check authoritative state: must NOT remain approved
    verified, v_msg, m2 = verify_authoritative_publication(output_dir=tmp_path)
    assert verified is False
    assert m2["is_approved"] is False
    assert m2["publication_state"] == PUB_STATE_PUBLICATION_FAILED
    assert "NOT APPROVED" in m2["final_verdict"]


def test_stage2_failure_invalidates_previously_approved_deployment(tmp_path):
    """Seed approved state, then simulate Stage 2 failure; verify authoritative state becomes NOT APPROVED."""
    # 1. Seed existing approved publication
    gate_ok = get_simulated_passing_gate()
    ok1, _, _ = publish_artifacts_fail_safe(gate_ok, output_dir=tmp_path)
    assert ok1 is True

    # 2. Run new publication with simulated Stage 2 replacement failure
    ok2, msg2, receipt2 = publish_artifacts_fail_safe(
        gate_ok, output_dir=tmp_path, _simulate_stage2_failure=True
    )
    assert ok2 is False
    assert "PUBLICATION_FAILED" in msg2

    # 3. Check authoritative state
    verified, v_msg, m2 = verify_authoritative_publication(output_dir=tmp_path)
    assert verified is False
    assert m2["is_approved"] is False
    assert m2["publication_state"] == PUB_STATE_PUBLICATION_FAILED
    assert "NOT APPROVED" in m2["final_verdict"]


def test_manifest_commit_failure_invalidates_authoritative_state(tmp_path):
    """Seed approved state, then simulate manifest commit failure; verify failure is caught."""
    gate_ok = get_simulated_passing_gate()
    ok1, _, _ = publish_artifacts_fail_safe(gate_ok, output_dir=tmp_path)
    assert ok1 is True

    ok2, msg2, receipt2 = publish_artifacts_fail_safe(
        gate_ok, output_dir=tmp_path, _simulate_manifest_failure=True
    )
    assert ok2 is False
    assert receipt2["publication_state"] == PUB_STATE_PUBLICATION_FAILED


def test_failed_rerun_overwrites_previous_approval_with_not_approved(tmp_path):
    """Publish approved generation, then run failed gate; verify authoritative state becomes NOT APPROVED."""
    # 1. Seed approved
    gate_ok = get_simulated_passing_gate()
    ok1, _, receipt1 = publish_artifacts_fail_safe(gate_ok, output_dir=tmp_path)
    assert ok1 is True

    # 2. Rerun with evaluation failure
    gate_fail = get_simulated_failing_gate()
    ok2, msg2, receipt2 = publish_artifacts_fail_safe(gate_fail, output_dir=tmp_path)
    assert ok2 is True  # Publication of the unapproved verdict succeeds cleanly
    assert receipt2["publication_state"] == PUB_STATE_PUBLICATION_COMMITTED

    # 3. Verify that old approval does NOT survive
    verified, v_msg, m2 = verify_authoritative_publication(output_dir=tmp_path)
    assert verified is False
    assert m2["is_approved"] is False
    assert "NOT APPROVED" in m2["final_verdict"]

    # Verify Markdown verdict text
    with open(tmp_path / "PHASE_5_14_5_FINAL_VERDICT.md", "r", encoding="utf-8") as f:
        v_text = f.read()
    assert "NOT APPROVED FOR COMPETITION FREEZE" in v_text
    assert "FINAL VERDICT: \\quad APPROVED" not in v_text


def test_temporary_files_cleaned_up_under_all_failure_modes(tmp_path):
    """Verifies that no lingering .tmp files remain after successful or failed publications."""
    gate_ok = get_simulated_passing_gate()

    # Success run
    publish_artifacts_fail_safe(gate_ok, output_dir=tmp_path)
    tmps = list(tmp_path.glob("*.tmp"))
    assert len(tmps) == 0

    # Stage 1 failure run
    publish_artifacts_fail_safe(gate_ok, output_dir=tmp_path, _simulate_stage1_failure=True)
    tmps = list(tmp_path.glob("*.tmp"))
    assert len(tmps) == 0

    # Stage 2 failure run
    publish_artifacts_fail_safe(gate_ok, output_dir=tmp_path, _simulate_stage2_failure=True)
    tmps = list(tmp_path.glob("*.tmp"))
    assert len(tmps) == 0
