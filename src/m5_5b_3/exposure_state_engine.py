"""
RR ScoutIQ — Milestone M5.5-B.3: Exposure State Machine
Module: src/m5_5b_3/exposure_state_engine.py

Implements explicit separation of 5 epistemic states:
1. ZERO_EXPOSURE: exposure == 0
2. POSITIVE_EXPOSURE_MISSING_OUTCOME: exposure > 0, events is None/NaN
3. POSITIVE_EXPOSURE_VALID_OBSERVATION: exposure > 0, events is valid number
4. INVALID_EXPOSURE: exposure < 0 or invalid type
5. INSUFFICIENT_EVIDENCE: 0 < exposure < min_exposure
"""

import math
from enum import Enum
from typing import Dict, Any, Optional, Tuple, Union
import numpy as np


class ExposureState(Enum):
    ZERO_EXPOSURE = "ZERO_EXPOSURE"
    POSITIVE_EXPOSURE_MISSING_OUTCOME = "POSITIVE_EXPOSURE_MISSING_OUTCOME"
    POSITIVE_EXPOSURE_VALID_OBSERVATION = "POSITIVE_EXPOSURE_VALID_OBSERVATION"
    INVALID_EXPOSURE = "INVALID_EXPOSURE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class EpistemicBaselineRecord:
    """
    Explicitly tracks personal baseline, population prior, posterior estimate,
    uncertainty representation, and eligibility classification across all 5 exposure states.
    """
    def __init__(
        self,
        exposure: Union[int, float],
        observed_events: Optional[Union[int, float]],
        prior_mean: float,
        prior_m0: float,
        prior_variance: float,
        min_exposure: int = 30
    ):
        self.raw_exposure = exposure
        self.raw_events = observed_events
        self.prior_mean = float(prior_mean)
        self.prior_m0 = float(prior_m0)
        self.prior_variance = float(prior_variance)
        self.min_exposure = int(min_exposure)
        
        # State classification & parameter derivation
        self._classify_and_compute()

    def _classify_and_compute(self):
        # Check invalid exposure first
        if (
            self.raw_exposure is None or
            (isinstance(self.raw_exposure, float) and np.isnan(self.raw_exposure)) or
            self.raw_exposure < 0 or
            not np.isfinite(self.raw_exposure)
        ):
            self.state = ExposureState.INVALID_EXPOSURE
            self.observed_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = np.nan
            self.posterior_variance = np.nan
            self.standard_error = np.nan
            self.can_return_prior = True
            self.can_calculate_posterior = False
            self.eligibility_status = "ERROR_INVALID_EXPOSURE"
            return
            
        exposure_int = int(self.raw_exposure)
        
        # Check zero exposure
        if exposure_int == 0:
            self.state = ExposureState.ZERO_EXPOSURE
            self.observed_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = self.prior_mean  # Defaults to prior mean
            self.posterior_variance = self.prior_variance  # Unreduced variance
            self.standard_error = math.sqrt(self.prior_variance)
            self.can_return_prior = True
            self.can_calculate_posterior = False
            self.eligibility_status = "INELIGIBLE_ZERO_EXPOSURE"
            return
            
        # Positive exposure: check outcome missingness
        if (
            self.raw_events is None or
            (isinstance(self.raw_events, float) and np.isnan(self.raw_events)) or
            not np.isfinite(self.raw_events)
        ):
            self.state = ExposureState.POSITIVE_EXPOSURE_MISSING_OUTCOME
            self.observed_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = np.nan
            self.posterior_variance = self.prior_variance
            self.standard_error = math.sqrt(self.prior_variance)
            self.can_return_prior = True
            self.can_calculate_posterior = False
            self.eligibility_status = "CORRUPTED_MISSING_OUTCOME"
            return
            
        # Positive exposure with valid observation
        events_float = float(self.raw_events)
        self.observed_rate = events_float / float(exposure_int)
        self.has_observed_rate = True
        
        # Empirical Bayes shrinkage weight w = n / (n + M0)
        shrinkage_weight = float(exposure_int) / (float(exposure_int) + self.prior_m0)
        self.shrunk_estimate = (
            shrinkage_weight * self.observed_rate +
            (1.0 - shrinkage_weight) * self.prior_mean
        )
        
        # Posterior variance: tau_post^2 = tau_prior^2 * (M0 / (n + M0))
        self.posterior_variance = self.prior_variance * (self.prior_m0 / (float(exposure_int) + self.prior_m0))
        self.standard_error = math.sqrt(self.posterior_variance)
        self.can_return_prior = True
        self.can_calculate_posterior = True
        
        if exposure_int < self.min_exposure:
            self.state = ExposureState.INSUFFICIENT_EVIDENCE
            self.eligibility_status = "SCREENED_INSUFFICIENT_SAMPLE"
        else:
            self.state = ExposureState.POSITIVE_EXPOSURE_VALID_OBSERVATION
            self.eligibility_status = "ELIGIBLE_ROBUST_OBSERVATION"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exposure": self.raw_exposure,
            "events": self.raw_events,
            "state": self.state.value,
            "has_observed_rate": self.has_observed_rate,
            "observed_rate": self.observed_rate,
            "prior_mean": self.prior_mean,
            "prior_m0": self.prior_m0,
            "can_return_prior": self.can_return_prior,
            "can_calculate_posterior": self.can_calculate_posterior,
            "shrunk_estimate": self.shrunk_estimate,
            "posterior_variance": self.posterior_variance,
            "standard_error": self.standard_error,
            "eligibility_status": self.eligibility_status
        }
