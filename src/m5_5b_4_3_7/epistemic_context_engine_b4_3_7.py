"""
RR ScoutIQ — Milestone M5.5-B.4.3.7: Coherent Bayesian Epistemic & Posterior Uncertainty Engine
Module: src/m5_5b_4_3_7/epistemic_context_engine_b4_3_7.py

Remediates M5.5-B.4.3.7 Priority 1, 2, 3, and 4:
1. Full Joint Conjugate Gaussian Bayesian Model with Leave-Player-and-Matches-Out (LPMO) priors:
   Prior on theta_i before observing Y_{i, c}:
     theta_i ~ N(mu_LPMO, tau2_total) where tau2_total = tau2_player + sigma2_mu_LPMO
   Likelihood:
     Y_{i, c} | theta_i ~ N(theta_i, V_{i, c})
   Bayesian Posterior Distribution:
     lambda_bayes = tau2_total / (tau2_total + V_{i, c})
     posterior_mean = lambda_bayes * Y_{i, c} + (1 - lambda_bayes) * mu_LPMO
     posterior_variance = (tau2_total * V_{i, c}) / (tau2_total + V_{i, c}) = (1 - lambda_bayes) * tau2_total
2. Strict separation of Bayesian posterior variance from frequentist estimator MSE:
   - posterior_variance: True conditional variance Var(theta_i | Y_{i, c}, mu_LPMO)
   - frequentist_estimator_mse: E[(hat_theta - theta)^2] of two-stage plug-in estimator
3. Correct Asymptotics:
   - Fixed matches M with n -> infinity: V_{i, c} -> sigma2_match / M > 0.
     Match shock prevents posterior variance from collapsing to zero.
   - Increasing matches M -> infinity with n -> infinity: V_{i, c} -> 0, posterior variance -> 0.
4. Coherent Posterior Predictive Variance:
   Var(Y_new | data) = posterior_variance + sigma2_match + (6.0 * sigma2_within / n_eval)
   Without double counting: prior uncertainty enters strictly through posterior_variance.
5. LPMO Provenance & Match Audit:
   Stores excluded_match_count, remaining_match_count, effective_match_count, and match_concentration_hhi.
"""

import math
from enum import Enum
from typing import Dict, Any, Optional, Union, Tuple, List
import numpy as np


class EpistemicStateB437(Enum):
    ZERO_CAREER_EXPOSURE = "ZERO_CAREER_EXPOSURE"
    ZERO_CONTEXT_EXPOSURE = "ZERO_CONTEXT_EXPOSURE"
    MISSING_OUTCOME = "MISSING_OUTCOME"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    VALID_CONTEXT_OBSERVATION = "VALID_CONTEXT_OBSERVATION"
    INVALID_EXPOSURE = "INVALID_EXPOSURE"

# Alias for backward compatibility
EpistemicStateB436 = EpistemicStateB437


class ContextualPlayerBaselineRecordB437:
    """
    Encapsulates a player's context-consistent Bayesian posterior baseline under the
    Joint Conjugate Gaussian model using Leave-Player-and-Matches-Out (LPMO) contextual priors.
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
        context_match_balls_list: Optional[List[int]] = None,
        prior_provenance: str = "CELL_LPMO_ROBUST",
        prior_population_balls: int = 0,
        excluded_match_count: int = 0,
        remaining_match_count: int = 0,
        effective_match_count: float = 0.0,
        match_concentration_hhi: float = 0.0
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
        self.context_prior_mean_variance = float(max(0.0, context_prior_mean_variance))
        self.population_mean_sampling_variance = self.context_prior_mean_variance
        
        # Total marginal prior variance for player i: tau2_total = tau2_player + sigma2_mu_LPMO
        self.tau2_total = float(self.tau2_player + self.context_prior_mean_variance)
        
        # Rigorous crossed-effects variance components
        self.sigma2_within = float(max(1.0, sigma2_within))
        self.sigma2_match = float(max(0.0, sigma2_match))
        self.context_match_balls_list = context_match_balls_list
        self.prior_provenance = str(prior_provenance)
        self.prior_population_balls = int(prior_population_balls)
        
        # LPMO Match-Exclusion Audit Metadata
        self.excluded_match_count = int(excluded_match_count)
        self.remaining_match_count = int(remaining_match_count)
        self.effective_match_count = float(effective_match_count)
        self.match_concentration_hhi = float(match_concentration_hhi)
        
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
            self.state = EpistemicStateB437.INVALID_EXPOSURE
            self.observed_context_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = np.nan
            self.shrinkage_weight = 0.0
            self.var_observation = np.nan
            self.latent_posterior_variance = np.nan
            self.frequentist_mse = np.nan
            self.latent_se = np.nan
            self.eligibility_status = "ERROR_INVALID_EXPOSURE"
            return
            
        n_ctx = int(self.context_exposure)
        
        # 2. Zero career exposure
        if self.career_exposure <= 0:
            self.state = EpistemicStateB437.ZERO_CAREER_EXPOSURE
            self.observed_context_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = self.context_prior_mean
            self.shrinkage_weight = 0.0
            self.var_observation = np.nan
            self.latent_posterior_variance = self.tau2_total
            self.frequentist_mse = self.tau2_total
            self.latent_se = math.sqrt(max(1e-8, self.latent_posterior_variance))
            self.eligibility_status = "INELIGIBLE_ZERO_CAREER_EXPOSURE"
            return
            
        # 3. Zero context exposure (career > 0, but no deliveries in this specific context)
        if n_ctx == 0:
            self.state = EpistemicStateB437.ZERO_CONTEXT_EXPOSURE
            self.observed_context_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = self.context_prior_mean
            self.shrinkage_weight = 0.0
            self.var_observation = np.nan
            self.latent_posterior_variance = self.tau2_total
            self.frequentist_mse = self.tau2_total
            self.latent_se = math.sqrt(max(1e-8, self.latent_posterior_variance))
            self.eligibility_status = "FALLBACK_ZERO_CONTEXT_EXPOSURE"
            return
            
        # 4. Missing outcome in context
        if (
            self.context_events is None or
            (isinstance(self.context_events, float) and np.isnan(self.context_events)) or
            not np.isfinite(self.context_events)
        ):
            self.state = EpistemicStateB437.MISSING_OUTCOME
            self.observed_context_rate = np.nan
            self.has_observed_rate = False
            self.shrunk_estimate = np.nan
            self.shrinkage_weight = 0.0
            self.var_observation = np.nan
            self.latent_posterior_variance = self.tau2_total
            self.frequentist_mse = self.tau2_total
            self.latent_se = math.sqrt(max(1e-8, self.latent_posterior_variance))
            self.eligibility_status = "CORRUPTED_MISSING_OUTCOME"
            return
            
        # 5. Positive context exposure with valid observation
        events_float = float(self.context_events)
        if self.is_economy:
            # Bowler economy in RPO
            self.observed_context_rate = 6.0 * (events_float / float(n_ctx))
            self.match_herfindahl = self._calculate_match_herfindahl(n_ctx)
            
            # Exact Likelihood observation variance:
            # V_{i, c} = (6.0 * sigma2_within / n_ctx) + H_{i, c} * sigma2_match
            self.var_observation = (6.0 * self.sigma2_within / float(n_ctx)) + (self.match_herfindahl * self.sigma2_match)
            
            # Full Joint Conjugate Bayesian Shrinkage Weight:
            # lambda_bayes = tau2_total / (tau2_total + V_{i, c})
            self.shrinkage_weight = float(self.tau2_total / (self.tau2_total + self.var_observation))
            
            # Plug-in shrinkage weight for frequentist MSE comparison:
            self.lambda_plugin = float(self.tau2_player / (self.tau2_player + self.var_observation))
            self.effective_m0 = float((self.var_observation / self.tau2_player) * float(n_ctx))
        else:
            # Batter Boundary% proportion
            self.observed_context_rate = events_float / float(n_ctx)
            self.match_herfindahl = float(1.0 / max(1.0, float(self.context_matches)))
            
            p_obs = np.clip(self.observed_context_rate, 0.02, 0.98)
            self.var_observation = float((p_obs * (1.0 - p_obs)) / float(n_ctx))
            self.shrinkage_weight = float(self.tau2_total / (self.tau2_total + self.var_observation))
            self.lambda_plugin = float(n_ctx) / (float(n_ctx) + self.prior_m0)
            self.effective_m0 = self.prior_m0
            
        self.has_observed_rate = True
        
        # Bayesian Posterior Mean:
        # hat_theta = lambda_bayes * Y_obs + (1 - lambda_bayes) * mu_LPMO
        self.shrunk_estimate = (
            self.shrinkage_weight * self.observed_context_rate +
            (1.0 - self.shrinkage_weight) * self.context_prior_mean
        )
        
        # 1. Full Joint Conjugate Bayesian Posterior Variance:
        # Var(theta_i | Y_{i, c}, mu_LPMO) = (tau2_total * V_{i, c}) / (tau2_total + V_{i, c}) = (1 - lambda_bayes) * tau2_total
        self.latent_posterior_variance = float(
            (1.0 - self.shrinkage_weight) * self.tau2_total
        )
        self.latent_se = math.sqrt(max(1e-8, self.latent_posterior_variance))
        
        # 2. Frequentist Estimator MSE of two-stage plug-in estimator for explicit comparison:
        # MSE = (1 - lambda_plugin) * tau2_player + (1 - lambda_plugin)^2 * sigma2_mu_LPMO
        w_plugin = 1.0 - self.lambda_plugin
        self.frequentist_mse = float(
            w_plugin * self.tau2_player + (w_plugin ** 2) * self.context_prior_mean_variance
        )
        
        if n_ctx < self.min_context_exposure:
            self.state = EpistemicStateB437.INSUFFICIENT_EVIDENCE
            self.eligibility_status = "SCREENED_INSUFFICIENT_SAMPLE"
        else:
            self.state = EpistemicStateB437.VALID_CONTEXT_OBSERVATION
            self.eligibility_status = "ELIGIBLE_ROBUST_OBSERVATION"

    @property
    def shrunk_baseline(self) -> float:
        return self.shrunk_estimate

    @property
    def posterior_mean(self) -> float:
        return self.shrunk_estimate

    @property
    def posterior_variance(self) -> float:
        return self.latent_posterior_variance

    @property
    def posterior_variance_latent(self) -> float:
        return self.latent_posterior_variance

    @property
    def latent_variance(self) -> float:
        """Alias for backward compatibility."""
        return self.latent_posterior_variance

    @property
    def standard_error(self) -> float:
        return self.latent_se

    def get_predictive_variance(self, n_eval: Union[int, float] = 6) -> float:
        """
        Computes the posterior predictive variance for a held-out observation
        with evaluation exposure n_eval (e.g. legal balls in a spell).
        
        Incorporates:
        1. Bayesian Posterior Variance: (tau2_total * V) / (tau2_total + V)
        2. Match-level environmental shock variance: sigma2_match
        3. Within-spell delivery noise variance: (sigma2_within * 6.0) / n_eval
        """
        n_e = max(1.0, float(n_eval))
        if self.is_economy:
            var_within = (self.sigma2_within * 6.0) / n_e
            return float(self.latent_posterior_variance + self.sigma2_match + var_within)
        else:
            p = float(np.clip(self.shrunk_estimate, 0.01, 0.99))
            var_sampling = (p * (1.0 - p)) / n_e
            return float(self.latent_posterior_variance + var_sampling)

    def get_predictive_se(self, n_eval: Union[int, float] = 6) -> float:
        return float(math.sqrt(max(1e-8, self.get_predictive_variance(n_eval))))

    def get_predictive_variance_breakdown(self, n_eval: Union[int, float] = 6) -> Dict[str, float]:
        """
        Returns an exhaustive breakdown of the distinct variance components.
        """
        n_e = max(1.0, float(n_eval))
        if self.is_economy:
            v_match = float(self.sigma2_match)
            v_within = float((self.sigma2_within * 6.0) / n_e)
        else:
            p = float(np.clip(self.shrunk_estimate, 0.01, 0.99))
            v_match = 0.0
            v_within = float((p * (1.0 - p)) / n_e)
            
        v_latent_post = float(self.latent_posterior_variance)
        v_total_pred = float(v_latent_post + v_match + v_within)
        
        # Breakdown of marginal prior components:
        w_bayes = 1.0 - self.shrinkage_weight
        v_prior_player = float(w_bayes * self.tau2_player)
        v_prior_context = float(w_bayes * self.context_prior_mean_variance)
        
        return {
            "prior_player_component": v_prior_player,
            "prior_context_component": v_prior_context,
            "latent_posterior_variance": v_latent_post,
            "frequentist_estimator_mse": float(self.frequentist_mse),
            "match_environmental_variance": v_match,
            "within_sampling_variance": v_within,
            "total_predictive_variance": v_total_pred,
            "predictive_se": math.sqrt(max(1e-8, v_total_pred))
        }

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
            "context_prior_mean_variance": self.context_prior_mean_variance,
            "tau2_player": self.tau2_player,
            "tau2_total": self.tau2_total,
            "prior_provenance": self.prior_provenance,
            "prior_population_balls": self.prior_population_balls,
            "excluded_match_count": self.excluded_match_count,
            "remaining_match_count": self.remaining_match_count,
            "effective_match_count": self.effective_match_count,
            "match_concentration_hhi": self.match_concentration_hhi,
            "match_herfindahl": getattr(self, "match_herfindahl", 1.0),
            "var_observation": getattr(self, "var_observation", np.nan),
            "shrinkage_weight": getattr(self, "shrinkage_weight", 0.0),
            "shrunk_estimate": self.shrunk_estimate,
            "posterior_mean": self.shrunk_estimate,
            "posterior_variance": self.latent_posterior_variance,
            "frequentist_mse": self.frequentist_mse,
            "latent_se": self.latent_se,
            "eligibility_status": self.eligibility_status
        }


# Backward compatibility alias
ContextualPlayerBaselineRecordB436 = ContextualPlayerBaselineRecordB437
