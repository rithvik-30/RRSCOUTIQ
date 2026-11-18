"""
RR ScoutIQ — Milestone M5.5-B.4.2: Context-Consistent Epistemic Baseline Engine
Module: src/m5_5b_4_2/epistemic_context_engine_b4_2.py

Implements:
1. Context-consistent player posterior estimation:
   - Calculates player personal observations at the EXACT contextual resolution as their priors.
   - For context c = (phase, tier): personal observation Y_{i, c} is derived EXCLUSIVELY
     from deliveries in that exact context c.
   - Invariant: Changing a player's Powerplay outcomes has ZERO effect on their Death personal observation.
2. Complete Epistemic States:
   - ZERO_CAREER_EXPOSURE: N_career == 0
   - ZERO_CONTEXT_EXPOSURE: N_career > 0 and N_context == 0
   - MISSING_OUTCOME: N > 0, events is NaN
   - INSUFFICIENT_EVIDENCE: 0 < N_context < N_min (screened for reliability)
   - VALID_CONTEXT_OBSERVATION: N_context >= N_min
   - INVALID_EXPOSURE: N < 0 or non-finite
3. Explicit tracking of:
   - context_exposure (N_{i, c})
   - context_matches (M_{i, c})
   - career_exposure (N_{i, career})
   - career_matches (M_{i, career})
4. Training-fold-only hyperparameter estimation:
   - M_0 and prior variances estimated strictly from training fold.
"""

import math
from enum import Enum
from typing import Dict, Any, Optional, Union, Tuple
import numpy as np
import pandas as pd


class EpistemicStateB42(Enum):
    ZERO_CAREER_EXPOSURE = "ZERO_CAREER_EXPOSURE"
    ZERO_CONTEXT_EXPOSURE = "ZERO_CONTEXT_EXPOSURE"
    MISSING_OUTCOME = "MISSING_OUTCOME"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    VALID_CONTEXT_OBSERVATION = "VALID_CONTEXT_OBSERVATION"
    INVALID_EXPOSURE = "INVALID_EXPOSURE"


class ContextualPlayerBaselineRecordB42:
    """
    Encapsulates a player's context-consistent baseline in a specific (phase, tier) context.
    """
    def __init__(
        self,
        player_id: int,
        phase: str,
        tier: str,
        context_exposure: Union[int, float],
        context_events: Optional[Union[int, float]],
        context_matches: int,
        career_exposure: int,
        career_events: Optional[Union[int, float]],
        career_matches: int,
        context_prior_mean: float,
        context_prior_variance: float,
        prior_m0: float,
        is_economy: bool = False,
        min_context_exposure: int = 30
    ):
        self.player_id = int(player_id)
        self.phase = str(phase)
        self.tier = str(tier)
        self.context_exposure = context_exposure
        self.context_events = context_events
        self.context_matches = int(context_matches)
        self.career_exposure = int(career_exposure)
        self.career_events = career_events
        self.career_matches = int(career_matches)
        self.context_prior_mean = float(context_prior_mean)
        self.context_prior_variance = float(context_prior_variance)
        self.prior_m0 = float(prior_m0)
        self.is_economy = bool(is_economy)
        self.min_context_exposure = int(min_context_exposure)
        
        self._classify_and_shrink()

    def _classify_and_shrink(self):
        # 1. Invalid exposure
        if (
            self.context_exposure is None or
            (isinstance(self.context_exposure, float) and np.isnan(self.context_exposure)) or
            self.context_exposure < 0 or
            not np.isfinite(self.context_exposure)
        ):
            self.state = EpistemicStateB42.INVALID_EXPOSURE
            self.observed_context_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = np.nan
            self.posterior_variance = np.nan
            self.standard_error = np.nan
            self.eligibility_status = "ERROR_INVALID_EXPOSURE"
            return
            
        n_ctx = int(self.context_exposure)
        
        # 2. Zero career exposure
        if self.career_exposure <= 0:
            self.state = EpistemicStateB42.ZERO_CAREER_EXPOSURE
            self.observed_context_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = self.context_prior_mean
            self.posterior_variance = self.context_prior_variance
            self.standard_error = math.sqrt(self.posterior_variance) if self.posterior_variance > 0 else 0.0
            self.eligibility_status = "INELIGIBLE_ZERO_CAREER_EXPOSURE"
            return
            
        # 3. Zero context exposure (has career experience, but no deliveries in this phase/tier)
        if n_ctx == 0:
            self.state = EpistemicStateB42.ZERO_CONTEXT_EXPOSURE
            self.observed_context_rate = np.nan
            self.has_observed_rate = False
            # Baseline falls back to context prior mean
            self.shrunk_estimate = self.context_prior_mean
            self.posterior_variance = self.context_prior_variance
            self.standard_error = math.sqrt(self.posterior_variance) if self.posterior_variance > 0 else 0.0
            self.eligibility_status = "FALLBACK_ZERO_CONTEXT_EXPOSURE"
            return
            
        # 4. Missing outcome in context
        if (
            self.context_events is None or
            (isinstance(self.context_events, float) and np.isnan(self.context_events)) or
            not np.isfinite(self.context_events)
        ):
            self.state = EpistemicStateB42.MISSING_OUTCOME
            self.observed_context_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = np.nan
            self.posterior_variance = self.context_prior_variance
            self.standard_error = math.sqrt(self.posterior_variance) if self.posterior_variance > 0 else 0.0
            self.eligibility_status = "CORRUPTED_MISSING_OUTCOME"
            return
            
        # 5. Positive context exposure with valid observation
        events_float = float(self.context_events)
        if self.is_economy:
            # Bowler economy observed context rate in RPO
            self.observed_context_rate = 6.0 * (events_float / float(n_ctx))
            # Sampling variance of mean rate in RPO: s^2 / (n / 6)
            # Empirical over variance ~ 16.0 RPO^2
            sampling_variance = 16.0 / max(1.0, (float(n_ctx) / 6.0))
        else:
            # Proportion metric (Boundary%)
            p_obs = events_float / float(n_ctx)
            self.observed_context_rate = p_obs
            sampling_variance = (p_obs * (1.0 - p_obs)) / float(n_ctx) if n_ctx > 1 else 0.25
            
        self.has_observed_rate = True
        
        # Shrinkage weight lambda = n_ctx / (n_ctx + M0)
        shrinkage_weight = float(n_ctx) / (float(n_ctx) + self.prior_m0)
        self.shrinkage_weight = shrinkage_weight
        
        # Context-consistent shrunk baseline
        self.shrunk_estimate = shrinkage_weight * self.observed_context_rate + (1.0 - shrinkage_weight) * self.context_prior_mean
        
        # Posterior uncertainty: shrinkage uncertainty + sampling uncertainty
        prior_error_contrib = ((1.0 - shrinkage_weight) ** 2) * self.context_prior_variance
        sampling_error_contrib = (shrinkage_weight ** 2) * sampling_variance
        self.posterior_variance = prior_error_contrib + sampling_error_contrib
        self.standard_error = math.sqrt(self.posterior_variance) if self.posterior_variance > 0 else 0.0
        
        if n_ctx < self.min_context_exposure:
            self.state = EpistemicStateB42.INSUFFICIENT_EVIDENCE
            self.eligibility_status = "SCREENED_INSUFFICIENT_SAMPLE"
        else:
            self.state = EpistemicStateB42.VALID_CONTEXT_OBSERVATION
            self.eligibility_status = "ELIGIBLE_ROBUST_OBSERVATION"

    @property
    def shrunk_baseline(self) -> float:
        return self.shrunk_estimate

    def to_dict(self) -> Dict[str, Any]:
        return {
            "player_id": self.player_id,
            "phase": self.phase,
            "tier": self.tier,
            "context_exposure": self.context_exposure,
            "context_events": self.context_events,
            "context_matches": self.context_matches,
            "career_exposure": self.career_exposure,
            "career_matches": self.career_matches,
            "state": self.state.value,
            "has_observed_rate": self.has_observed_rate,
            "observed_context_rate": self.observed_context_rate,
            "context_prior_mean": self.context_prior_mean,
            "prior_m0": self.prior_m0,
            "shrinkage_weight": getattr(self, "shrinkage_weight", 0.0),
            "shrunk_estimate": self.shrunk_estimate,
            "posterior_variance": self.posterior_variance,
            "standard_error": self.standard_error,
            "eligibility_status": self.eligibility_status
        }
