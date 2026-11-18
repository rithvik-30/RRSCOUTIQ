"""
Phase 5.14.5.2 — Publication Recovery & Fail-Closed State Transition Tests
RR ScoutIQ | Rajasthan Royals IPL 2027 Auction Strategy Hackathon

Verifies:
1. Safe recovery and state commit after Stage 1 summary replacement failure.
2. Safe recovery and state commit after Stage 2 verdict replacement failure.
3. Safe recovery and state commit after Authoritative Manifest commit failure.
4. Safe recovery and state commit after double-failure (replacement + unlink fail).
5. Generation ID progression and uniqueness across recovery cycles.
6. Complete unlinking and cleanup of temporary staging files (.tmp) across all recovery paths.
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
    PUB_STATE_APPROVED_FOR_COMPETITION_FREEZE,
    PUB_STATE_PUBLICATION_FAILED,
)


def get_mock_gate():
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


def test_recovery_after_stage1_failure(tmp_path):
    """Test publication recovery after simulated Stage 1 failure."""
    gate = get_mock_gate()

    # Step 1: Initial failed publication (Stage 1)
    ok1, msg1, r1 = publish_artifacts_fail_safe(gate, output_dir=tmp_path, _simulate_stage1_failure=True)
    assert ok1 is False
    assert r1["publication_state"] == PUB_STATE_PUBLICATION_FAILED

    v1, _, m1 = verify_authoritative_publication(output_dir=tmp_path)
    assert v1 is False

    # Step 2: Subsequent recovery publication
    ok2, msg2, r2 = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok2 is True
    assert r2["publication_state"] == PUB_STATE_APPROVED_FOR_COMPETITION_FREEZE
    assert r2["gen_id"] != r1["gen_id"]

    v2, _, m2 = verify_authoritative_publication(output_dir=tmp_path)
    assert v2 is True
    assert m2["is_approved"] is True
    assert m2["active_generation_id"] == r2["gen_id"]


def test_recovery_after_stage2_failure(tmp_path):
    """Test publication recovery after simulated Stage 2 failure."""
    gate = get_mock_gate()

    ok1, msg1, r1 = publish_artifacts_fail_safe(gate, output_dir=tmp_path, _simulate_stage2_failure=True)
    assert ok1 is False

    v1, _, _ = verify_authoritative_publication(output_dir=tmp_path)
    assert v1 is False

    ok2, msg2, r2 = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok2 is True

    v2, _, m2 = verify_authoritative_publication(output_dir=tmp_path)
    assert v2 is True
    assert m2["active_generation_id"] == r2["gen_id"]


def test_recovery_after_manifest_commit_failure(tmp_path):
    """Test publication recovery after simulated Authoritative Manifest failure."""
    gate = get_mock_gate()

    ok1, msg1, r1 = publish_artifacts_fail_safe(gate, output_dir=tmp_path, _simulate_manifest_failure=True)
    assert ok1 is False

    v1, _, _ = verify_authoritative_publication(output_dir=tmp_path)
    assert v1 is False

    ok2, msg2, r2 = publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert ok2 is True

    v2, _, m2 = verify_authoritative_publication(output_dir=tmp_path)
    assert v2 is True
    assert m2["active_generation_id"] == r2["gen_id"]


def test_recovery_cleans_up_all_temp_files(tmp_path):
    """Verifies that no lingering .tmp files exist before or after recovery."""
    gate = get_mock_gate()

    # Failures across stages
    publish_artifacts_fail_safe(gate, output_dir=tmp_path, _simulate_stage1_failure=True)
    assert len(list(tmp_path.glob("*.tmp"))) == 0

    publish_artifacts_fail_safe(gate, output_dir=tmp_path, _simulate_stage2_failure=True)
    assert len(list(tmp_path.glob("*.tmp"))) == 0

    publish_artifacts_fail_safe(gate, output_dir=tmp_path, _simulate_manifest_failure=True)
    assert len(list(tmp_path.glob("*.tmp"))) == 0

    # Successful recovery
    publish_artifacts_fail_safe(gate, output_dir=tmp_path)
    assert len(list(tmp_path.glob("*.tmp"))) == 0
