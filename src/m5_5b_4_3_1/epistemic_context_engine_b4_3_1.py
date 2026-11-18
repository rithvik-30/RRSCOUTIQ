"""
RR ScoutIQ — Milestone M5.5-B.4.3.1: Coherent Epistemic & Posterior Uncertainty Engine
Module: src/m5_5b_4_3_1/epistemic_context_engine_b4_3_1.py

Implements:
1. Complete mathematical separation of:
   - Latent ability uncertainty (Var(theta | data)): uncertainty about player's true underlying rate.
   - Posterior predictive uncertainty (Var(Y_new | data)): predictive dispersion for a held-out spell.
   - Population contextual prior uncertainty (tau^2_player): training-estimated between-player heterogeneity.
2. Coherent Empirical Bayes Shrinkage:
   - Uses training-fold estimated between-player variance tau^2_player from Henderson Method III.
   - lambda = n_ctx / (n_ctx + M0)
   - shrunk_estimate = lambda * Y_obs + (1 - lambda) * mu_prior
   - Var_latent = (1 - lambda) * tau^2_player
3. Predictive Variance calculation for any held-out evaluation exposure n_eval:
   - For bowler economy (in RPO): Var_predictive = Var_latent + sigma2_match + (sigma2_within / (n_eval / 6.0))
   - For batter boundary proportion: Var_latent represents parameter uncertainty on probability scale.
4. Context isolation:
   - Personal observation Y_{i, c} is computed strictly at context resolution.
   - Changing Powerplay outcomes has ZERO effect on Death context observations.
5. Epistemic states:
   - ZERO_CAREER_EXPOSURE
   - ZERO_CONTEXT_EXPOSURE
   - MISSING_OUTCOME
   - INSUFFICIENT_EVIDENCE (0 < n_ctx < 30)
   - VALID_CONTEXT_OBSERVATION (n_ctx >= 30)
   - INVALID_EXPOSURE
"""

import math
from enum import Enum
from typing import Dict, Any, Optional, Union, Tuple
import numpy as np


class EpistemicStateB431(Enum):
    ZERO_CAREER_EXPOSURE = "ZERO_CAREER_EXPOSURE"
    ZERO_CONTEXT_EXPOSURE = "ZERO_CONTEXT_EXPOSURE"
    MISSING_OUTCOME = "MISSING_OUTCOME"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    VALID_CONTEXT_OBSERVATION = "VALID_CONTEXT_OBSERVATION"
    INVALID_EXPOSURE = "INVALID_EXPOSURE"


class ContextualPlayerBaselineRecordB431:
    """
    Encapsulates a player's context-consistent posterior baseline and distinguishes
    latent ability uncertainty from posterior predictive uncertainty.
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
        player_heterogeneity_tau2: Optional[float] = None,
        prior_m0: float = 100.0,
        is_economy: bool = False,
        min_context_exposure: int = 30,
        tau2_player: Optional[float] = None,
        context_prior_mean_variance: float = 0.0001,
        sigma2_match: float = 1.32,
        sigma2_within: float = 23.06
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
        tau2_val = player_heterogeneity_tau2 if player_heterogeneity_tau2 is not None else (tau2_player if tau2_player is not None else 0.002)
        self.tau2_player = float(max(1e-6, tau2_val))
        self.prior_m0 = float(max(1.0, prior_m0))
        self.is_economy = bool(is_economy)
        self.min_context_exposure = int(min_context_exposure)
        self.context_prior_mean_variance = float(context_prior_mean_variance)
        self.population_mean_sampling_variance = self.context_prior_mean_variance
        
        # Rigorous crossed-effects variance architecture
        self.sigma2_within = float(max(1.0, sigma2_within))
        self.sigma2_match = float(max(0.0, sigma2_match))
        self.sigma2_over = self.sigma2_within + self.sigma2_match
        
        self._classify_and_shrink()

    def _classify_and_shrink(self):
        # 1. Invalid exposure
        if (
            self.context_exposure is None or
            (isinstance(self.context_exposure, float) and np.isnan(self.context_exposure)) or
            self.context_exposure < 0 or
            not np.isfinite(self.context_exposure)
        ):
            self.state = EpistemicStateB431.INVALID_EXPOSURE
            self.observed_context_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = np.nan
            self.latent_variance = np.nan
            self.latent_se = np.nan
            self.eligibility_status = "ERROR_INVALID_EXPOSURE"
            return
            
        n_ctx = int(self.context_exposure)
        
        # 2. Zero career exposure
        if self.career_exposure <= 0:
            self.state = EpistemicStateB431.ZERO_CAREER_EXPOSURE
            self.observed_context_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = self.context_prior_mean
            self.latent_variance = self.tau2_player
            self.latent_se = math.sqrt(self.tau2_player)
            self.eligibility_status = "INELIGIBLE_ZERO_CAREER_EXPOSURE"
            return
            
        # 3. Zero context exposure (career > 0, but no deliveries in this specific context)
        if n_ctx == 0:
            self.state = EpistemicStateB431.ZERO_CONTEXT_EXPOSURE
            self.observed_context_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = self.context_prior_mean
            self.latent_variance = self.tau2_player
            self.latent_se = math.sqrt(self.tau2_player)
            self.eligibility_status = "FALLBACK_ZERO_CONTEXT_EXPOSURE"
            return
            
        # 4. Missing outcome in context
        if (
            self.context_events is None or
            (isinstance(self.context_events, float) and np.isnan(self.context_events)) or
            not np.isfinite(self.context_events)
        ):
            self.state = EpistemicStateB431.MISSING_OUTCOME
            self.observed_context_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = np.nan
            self.latent_variance = self.tau2_player
            self.latent_se = math.sqrt(self.tau2_player)
            self.eligibility_status = "CORRUPTED_MISSING_OUTCOME"
            return
            
        # 5. Positive context exposure with valid observation
        events_float = float(self.context_events)
        if self.is_economy:
            # Bowler economy in RPO
            self.observed_context_rate = 6.0 * (events_float / float(n_ctx))
        else:
            # Proportion metric (Boundary%)
            self.observed_context_rate = events_float / float(n_ctx)
            
        self.has_observed_rate = True
        
        # Shrinkage weight lambda = n_ctx / (n_ctx + M0)
        shrinkage_weight = float(n_ctx) / (float(n_ctx) + self.prior_m0)
        self.shrinkage_weight = shrinkage_weight
        
        # Shrunk baseline estimate
        self.shrunk_estimate = shrinkage_weight * self.observed_context_rate + (1.0 - shrinkage_weight) * self.context_prior_mean
        
        # Latent ability posterior variance: (1 - lambda) * tau2_player
        self.latent_variance = (1.0 - shrinkage_weight) * self.tau2_player
        self.latent_se = math.sqrt(max(1e-8, self.latent_variance))
        
        if n_ctx < self.min_context_exposure:
            self.state = EpistemicStateB431.INSUFFICIENT_EVIDENCE
            self.eligibility_status = "SCREENED_INSUFFICIENT_SAMPLE"
        else:
            self.state = EpistemicStateB431.VALID_CONTEXT_OBSERVATION
            self.eligibility_status = "ELIGIBLE_ROBUST_OBSERVATION"

    @property
    def shrunk_baseline(self) -> float:
        return self.shrunk_estimate

    @property
    def posterior_variance(self) -> float:
        return self.latent_variance

    @property
    def posterior_variance_latent(self) -> float:
        return self.latent_variance

    @property
    def standard_error(self) -> float:
        return self.latent_se

    def get_predictive_variance(self, n_eval: Union[int, float] = 6) -> float:
        """
        Computes the posterior predictive variance for a held-out observation
        with evaluation exposure n_eval (e.g. legal balls in a spell).
        """
        n_e = max(1.0, float(n_eval))
        if self.is_economy:
            # Three-component variance decomposition:
            # Var_pred = Var_latent + Var_match + Var_within(n_eval)
            # where Var_within = (sigma2_within * 6.0) / n_e
            var_within = (self.sigma2_within * 6.0) / n_e
            return float(self.latent_variance + self.sigma2_match + var_within)
        else:
            p = float(np.clip(self.shrunk_estimate, 0.01, 0.99))
            var_sampling = (p * (1.0 - p)) / n_e
            return float(self.latent_variance + var_sampling)

    def get_predictive_se(self, n_eval: Union[int, float] = 6) -> float:
        return float(math.sqrt(max(1e-8, self.get_predictive_variance(n_eval))))

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
            "tau2_player": self.tau2_player,
            "prior_m0": self.prior_m0,
            "shrinkage_weight": getattr(self, "shrinkage_weight", 0.0),
            "shrunk_estimate": self.shrunk_estimate,
            "latent_variance": self.latent_variance,
            "latent_se": self.latent_se,
            "eligibility_status": self.eligibility_status
        }
