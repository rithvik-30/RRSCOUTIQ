"""
RR ScoutIQ — Milestone M5.5-B.4.1: Unified Epistemic Baseline Engine
Module: src/m5_5b_4_1/epistemic_engine_b4_1.py

Fixes:
1. Complete unit harmonization for bowler economy:
   - When metric is Bowler Economy, observed personal rate is strictly RPO (6.0 * debit_runs / legal_balls).
   - Invariant: If observed RPO == prior RPO, shrunk estimate == prior RPO exactly across all exposure levels.
2. Distinct Epistemic States:
   - ZERO_EXPOSURE: N == 0 -> observed_rate is NaN, shrunk estimate is prior mean, variance is full prior variance.
   - POSITIVE_EXPOSURE_MISSING_OUTCOME: N > 0, events is NaN -> observed_rate is NaN, shrunk estimate is NaN.
   - POSITIVE_EXPOSURE_VALID_OBSERVATION: N >= N_min, valid events -> shrunk estimate combines observed and prior.
   - INSUFFICIENT_EVIDENCE: 0 < N < N_min -> screened for low reliability.
   - INVALID_EXPOSURE: N < 0 or non-finite -> error state.
3. Player-specific sampling variance inclusion in posterior uncertainty.
"""

import math
from enum import Enum
from typing import Dict, Any, Optional, Union
import numpy as np


class EpistemicState(Enum):
    ZERO_EXPOSURE = "ZERO_EXPOSURE"
    POSITIVE_EXPOSURE_MISSING_OUTCOME = "POSITIVE_EXPOSURE_MISSING_OUTCOME"
    POSITIVE_EXPOSURE_VALID_OBSERVATION = "POSITIVE_EXPOSURE_VALID_OBSERVATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    INVALID_EXPOSURE = "INVALID_EXPOSURE"


class EpistemicBaselineRecordB41:
    """
    Encapsulates an individual's personal baseline with strict unit consistency:
    - For proportion metrics (e.g. Boundary%): rate in [0, 1].
    - For bowler economy: rate strictly in RPO (runs per 6 legal balls).
    """
    def __init__(
        self,
        exposure: Union[int, float],
        observed_events: Optional[Union[int, float]],
        prior_mean: float,
        prior_m0: float,
        prior_variance: float,
        is_economy: bool = False,
        min_exposure: int = 30,
        player_sample_variance: Optional[float] = None
    ):
        self.raw_exposure = exposure
        self.raw_events = observed_events
        self.prior_mean = float(prior_mean)
        self.prior_m0 = float(prior_m0)
        self.prior_variance = float(prior_variance)
        self.is_economy = bool(is_economy)
        self.min_exposure = int(min_exposure)
        self.player_sample_variance = player_sample_variance
        
        self._classify_and_compute()

    def _classify_and_compute(self):
        # 1. Invalid exposure check
        if (
            self.raw_exposure is None or
            (isinstance(self.raw_exposure, float) and np.isnan(self.raw_exposure)) or
            self.raw_exposure < 0 or
            not np.isfinite(self.raw_exposure)
        ):
            self.state = EpistemicState.INVALID_EXPOSURE
            self.observed_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = np.nan
            self.posterior_variance = np.nan
            self.standard_error = np.nan
            self.eligibility_status = "ERROR_INVALID_EXPOSURE"
            return
            
        exposure_int = int(self.raw_exposure)
        
        # 2. Zero exposure check
        if exposure_int == 0:
            self.state = EpistemicState.ZERO_EXPOSURE
            self.observed_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = self.prior_mean
            self.posterior_variance = self.prior_variance
            self.standard_error = math.sqrt(self.prior_variance) if self.prior_variance > 0 else 0.0
            self.eligibility_status = "INELIGIBLE_ZERO_EXPOSURE"
            return
            
        # 3. Missing outcome check
        if (
            self.raw_events is None or
            (isinstance(self.raw_events, float) and np.isnan(self.raw_events)) or
            not np.isfinite(self.raw_events)
        ):
            self.state = EpistemicState.POSITIVE_EXPOSURE_MISSING_OUTCOME
            self.observed_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = np.nan
            self.posterior_variance = self.prior_variance
            self.standard_error = math.sqrt(self.prior_variance) if self.prior_variance > 0 else 0.0
            self.eligibility_status = "CORRUPTED_MISSING_OUTCOME"
            return
            
        # 4. Positive exposure with valid observation
        events_float = float(self.raw_events)
        if self.is_economy:
            # Bowler economy observed rate in RPO
            self.observed_rate = 6.0 * (events_float / float(exposure_int))
        else:
            # Proportion metric (Boundary%, Dot%, etc.)
            self.observed_rate = events_float / float(exposure_int)
            
        self.has_observed_rate = True
        
        # Shrinkage weight lambda = n / (n + M0)
        shrinkage_weight = float(exposure_int) / (float(exposure_int) + self.prior_m0)
        self.shrinkage_weight = shrinkage_weight
        
        # Shrunk estimate
        self.shrunk_estimate = (
            shrinkage_weight * self.observed_rate +
            (1.0 - shrinkage_weight) * self.prior_mean
        )
        
        # Player sampling variance:
        # If not provided, derive from observed rate
        if self.player_sample_variance is not None and np.isfinite(self.player_sample_variance):
            s2_player = float(self.player_sample_variance)
        else:
            if self.is_economy:
                # Bowler economy spell variance estimate ~ 16.0 (RPO^2)
                s2_player = 16.0
            else:
                s2_player = self.observed_rate * (1.0 - self.observed_rate)
                
        # Posterior variance combines prior uncertainty and player sampling variance
        n_eff = float(exposure_int) / (6.0 if self.is_economy else 1.0)
        sampling_error_contrib = (shrinkage_weight ** 2) * (s2_player / max(1.0, n_eff))
        prior_error_contrib = ((1.0 - shrinkage_weight) ** 2) * self.prior_variance
        self.posterior_variance = prior_error_contrib + sampling_error_contrib
        self.standard_error = math.sqrt(self.posterior_variance) if self.posterior_variance > 0 else 0.0
        
        if exposure_int < self.min_exposure:
            self.state = EpistemicState.INSUFFICIENT_EVIDENCE
            self.eligibility_status = "SCREENED_INSUFFICIENT_SAMPLE"
        else:
            self.state = EpistemicState.POSITIVE_EXPOSURE_VALID_OBSERVATION
            self.eligibility_status = "ELIGIBLE_ROBUST_OBSERVATION"

    @property
    def shrunk_baseline(self) -> float:
        return self.shrunk_estimate

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exposure": self.raw_exposure,
            "events": self.raw_events,
            "state": self.state.value,
            "has_observed_rate": self.has_observed_rate,
            "observed_rate": self.observed_rate,
            "prior_mean": self.prior_mean,
            "prior_m0": self.prior_m0,
            "shrinkage_weight": getattr(self, "shrinkage_weight", 0.0),
            "shrunk_estimate": self.shrunk_estimate,
            "posterior_variance": self.posterior_variance,
            "standard_error": self.standard_error,
            "eligibility_status": self.eligibility_status
        }
