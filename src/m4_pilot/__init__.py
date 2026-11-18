"""
RR ScoutIQ - Milestone M4 Controlled Pilot Package
===================================================

This package implements the modular analysis pipeline for the M4 Controlled Implementation Pilot,
operating strictly on the verified eight-match hybrid enriched pilot dataset.

Modules:
- input_validation: M4.1 input validation, crosswalk integrity, provenance, and data reconciliation.
- match_state_engine: M4.2 pre-delivery causal state reconstruction and DLI calculation (PLANNED).
- batter_engine: M4.3 batter tactical roles and BPPI components (PLANNED).
- bowler_engine: M4.4 bowler tactical roles and PPBI components (PLANNED).
- reliability_engine: M4.5 Bayesian shrinkage and Scheme B bootstrap (PLANNED).
- pilot_pipeline: Orchestration harness (PLANNED).
"""

__version__ = "0.4.1"
__all__ = ["input_validation"]

