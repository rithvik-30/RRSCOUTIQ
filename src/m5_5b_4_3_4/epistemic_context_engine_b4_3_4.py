"""
RR ScoutIQ — Milestone M5.5-B.4.3.4: Coherent Epistemic & Posterior Uncertainty Engine
Module: src/m5_5b_4_3_4/epistemic_context_engine_b4_3_4.py

Implements:
1. Exact match-aware posterior likelihood variance for contextual aggregates:
   - For bowler economy (in RPO):
     V_{i, c} = (6.0 * sigma2_within / n_{i, c}) + H_{i, c} * sigma2_match
     where:
       n_{i, c}: Total legal balls bowled by player i in context c
       H_{i, c} = sum_{m in M_{i, c}} (n_{im} / n_{i, c})^2: Herfindahl-Hirschman match concentration index
       sigma2_within: Within-spell delivery noise variance per over
       sigma2_match: Match environmental shock variance
   - Accounts for multiple spells in the same match by summing balls per match before squaring,
     preventing multiple spells in the same match from being treated as independent match shocks.
   - Properly differentiates equal volume concentrated in 1 match vs distributed across M matches.
2. Exposure-dependent Bayesian shrinkage weight:
   lambda_{i, c} = tau2_player / (tau2_player + V_{i, c})
   shrunk_estimate = lambda_{i, c} * Y_obs + (1 - lambda_{i, c}) * mu_prior
3. Complete mathematical separation of:
   - Latent ability uncertainty: Var(theta | data) = (1 - lambda_{i, c}) * tau2_player
   - Posterior predictive uncertainty for a held-out test spell of n_eval balls:
     Var(Y_new | data) = Var(theta | data) + sigma2_match + (6.0 * sigma2_within / n_eval)
"""

import math
from enum import Enum
from typing import Dict, Any, Optional, Union, Tuple, List
import numpy as np


class EpistemicStateB434(Enum):
    ZERO_CAREER_EXPOSURE = "ZERO_CAREER_EXPOSURE"
    ZERO_CONTEXT_EXPOSURE = "ZERO_CONTEXT_EXPOSURE"
    MISSING_OUTCOME = "MISSING_OUTCOME"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    VALID_CONTEXT_OBSERVATION = "VALID_CONTEXT_OBSERVATION"
    INVALID_EXPOSURE = "INVALID_EXPOSURE"


class ContextualPlayerBaselineRecordB434:
    """
    Encapsulates a player's context-consistent posterior baseline and distinguishes
    latent ability uncertainty from posterior predictive uncertainty, incorporating
    both within-spell delivery noise and match-level environmental shocks.
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
        sigma2_match: float = 1.45,
        sigma2_within: float = 22.84,
        context_match_balls_list: Optional[List[int]] = None
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
        
        # Rigorous crossed-effects variance components
        self.sigma2_within = float(max(1.0, sigma2_within))
        self.sigma2_match = float(max(0.0, sigma2_match))
        self.context_match_balls_list = context_match_balls_list
        
        self._classify_and_shrink()

    def _calculate_match_herfindahl(self, n_ctx: int) -> float:
        """
        Calculates the Herfindahl-Hirschman match exposure concentration:
            H = sum_m (n_{im} / n_{i, c})^2
        """
        if self.context_match_balls_list is not None and len(self.context_match_balls_list) > 0:
            arr = np.array(self.context_match_balls_list, dtype=float)
            total = float(np.sum(arr))
            if total > 0:
                return float(np.sum((arr / total) ** 2))
                
        # If match-level breakdown is not provided, use uniform split across context_matches
        n_m = max(1, self.context_matches)
        return float(1.0 / float(n_m))

    def _classify_and_shrink(self):
        # 1. Invalid exposure
        if (
            self.context_exposure is None or
            (isinstance(self.context_exposure, float) and np.isnan(self.context_exposure)) or
            self.context_exposure < 0 or
            not np.isfinite(self.context_exposure)
        ):
            self.state = EpistemicStateB434.INVALID_EXPOSURE
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
            self.state = EpistemicStateB434.ZERO_CAREER_EXPOSURE
            self.observed_context_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = self.context_prior_mean
            self.latent_variance = self.tau2_player
            self.latent_se = math.sqrt(self.tau2_player)
            self.eligibility_status = "INELIGIBLE_ZERO_CAREER_EXPOSURE"
            return
            
        # 3. Zero context exposure (career > 0, but no deliveries in this specific context)
        if n_ctx == 0:
            self.state = EpistemicStateB434.ZERO_CONTEXT_EXPOSURE
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
            self.state = EpistemicStateB434.MISSING_OUTCOME
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
            
            # Match concentration index
            self.match_herfindahl = self._calculate_match_herfindahl(n_ctx)
            
            # Likelihood observation variance:
            # V_{i, c} = (6.0 * sigma2_within / n_ctx) + H_{i, c} * sigma2_match
            self.var_observation = (6.0 * self.sigma2_within / float(n_ctx)) + (self.match_herfindahl * self.sigma2_match)
            
            # Bayesian shrinkage weight
            self.shrinkage_weight = float(self.tau2_player / (self.tau2_player + self.var_observation))
            
            # Effective prior sample size M_{0, i} for this specific player exposure distribution
            self.effective_m0 = float((self.var_observation / self.tau2_player) * float(n_ctx))
        else:
            # Batter Boundary% proportion
            self.observed_context_rate = events_float / float(n_ctx)
            self.match_herfindahl = float(1.0 / max(1.0, float(self.context_matches)))
            
            p_obs = np.clip(self.observed_context_rate, 0.02, 0.98)
            self.var_observation = float((p_obs * (1.0 - p_obs)) / float(n_ctx))
            self.shrinkage_weight = float(n_ctx) / (float(n_ctx) + self.prior_m0)
            self.effective_m0 = self.prior_m0
            
        self.has_observed_rate = True
        
        # Shrunk baseline estimate
        self.shrunk_estimate = self.shrinkage_weight * self.observed_context_rate + (1.0 - self.shrinkage_weight) * self.context_prior_mean
        
        # Latent ability posterior variance: (1 - lambda) * tau2_player
        self.latent_variance = (1.0 - self.shrinkage_weight) * self.tau2_player
        self.latent_se = math.sqrt(max(1e-8, self.latent_variance))
        
        if n_ctx < self.min_context_exposure:
            self.state = EpistemicStateB434.INSUFFICIENT_EVIDENCE
            self.eligibility_status = "SCREENED_INSUFFICIENT_SAMPLE"
        else:
            self.state = EpistemicStateB434.VALID_CONTEXT_OBSERVATION
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
            "effective_m0": getattr(self, "effective_m0", self.prior_m0),
            "match_herfindahl": getattr(self, "match_herfindahl", 1.0),
            "var_observation": getattr(self, "var_observation", np.nan),
            "shrinkage_weight": getattr(self, "shrinkage_weight", 0.0),
            "shrunk_estimate": self.shrunk_estimate,
            "latent_variance": self.latent_variance,
            "latent_se": self.latent_se,
            "eligibility_status": self.eligibility_status
        }
