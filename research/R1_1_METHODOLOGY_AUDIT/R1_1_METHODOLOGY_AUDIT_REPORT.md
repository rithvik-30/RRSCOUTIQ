# RR ScoutIQ — Milestone R1.1: Independent Methodological Audit Report

**Classification:** **EMPIRICAL SUPPORT WITH LIMITATIONS**  
**Milestone:** R1.1 — Independent Methodological Audit & Verification  
**Status:** COMPLETE (Ready for Human Review)  
**Date:** November 2026  
**Execution Environment:** `RRScoutIQenv` (Python 3.13.9, pytest 9.2.0, pandas 2.2.3, numpy 2.2.3, scikit-learn 1.9.1, scipy 1.18.1)  
**Input Data Scope:** 776 approved matches, 179,837 deliveries, 175,676 valid DLI observations  
**Regression Test Battery:** 211 passed in ~115s (100% pass rate, exit code 0)  

---

## Executive Summary

Milestone R1.1 executes an independent methodological audit of the Dynamic Leverage Index (DLI) empirical validation reported in R1. 

While R1 reported strong empirical support for DLI, this audit investigates six critical methodological questions raised during peer review:
1. **Chase Win-Rate Construct Independence:** Does chase win rate validate DLI independently, or is the relationship circular and non-incremental?
2. **Forward Outcome Validation:** Do strict forward 6-legal-ball rolling windows preserve temporal isolation and add incremental predictive signal?
3. **Setting DLI Formulation:** Does the superlinear progression function $\Phi(t)$, Over 1 undefined CRR treatment, and tail collapse clamping behave defensibly?
4. **Tier Distribution Reconciliation:** Why did R1 report two differing baseline tier distributions (13.65% vs 13.52% Tier 1, 13.73% vs 12.37% Tier 4)?
5. **Threshold Inversion Statistical Significance:** Is the reported -0.001 wicket hazard inversion under Candidate E (0.70 / 1.30 / 2.00) statistically distinguishable from sampling variation?
6. **Clamping and Venue Effects:** How do the 5.00 chase clamp and 3.50 setting clamp behave across verified scoring environments and grounds?

Based on empirical models, 5-fold match-grouped cross-validation, match-clustered bootstrap standard errors, and complete population reconciliation, this audit reaches the formal decision:

> ### Formal Audit Decision: **EMPIRICAL SUPPORT WITH LIMITATIONS**
> 
> - **Construct Validity Reframing:** DLI must **NOT** be claimed as an independent causal predictor of chase victory. Terminal win rate is mathematically dependent on the exact state inputs that construct DLI ($RRR, W_{\text{hand}}, B_{\text{rem}}$). In 5-fold match-grouped cross-validation, DLI adds **zero incremental predictive power** beyond raw state variables ($\Delta \text{LogLoss} = -0.0002$, $\Delta \text{AUC} = +0.0001$). DLI is a **game-importance weighting function** that scales player performance by match leverage, not a superior win-probability model.
> - **Forward Outcome Robustness:** Strict forward 6-legal-delivery outcome analysis confirms that pre-delivery DLI strictly predicts forward wicket hazard (0.268 in Tier 1 to 0.564 in Tier 4 overall; 0.264 to 0.615 in setting innings).
> - **Exact Tier Reconciliation:** The discrepancy between R1's two tier tables is **100% mathematically reconciled**. Table 1 analyzed the full valid dataset ($N = 175,676$), while Table 2 analyzed the forward-eligible dataset ($N = 163,658$), which omitted 12,018 deliveries (wides, no-balls, and final 2 deliveries of innings runway). Because 32.25% of omitted balls were Tier 4, the Tier 4 proportion naturally shifted from 13.73% to 12.37%.
> - **Threshold Significance Finding:** The -0.001 hazard difference in Candidate E is **statistically insignificant sampling noise** ($z = -0.029, p = 0.9765$). However, Candidate E is rejected for a separate, compelling practical defect: its Tier 1 population collapses to 2.55% (4,167 balls). The Approved M3 Baseline (0.90 / 1.35 / 2.25) remains the optimal, stable operational choice.

---

## 1. Investigation 1: Chase Win-Rate Construct Validity & Baseline Comparison

### 1.1 Mathematical & Conceptual Dependence
In T20 cricket chases, the true posterior win probability $P(\text{Win} \mid S_t)$ is a monotonic function of remaining required runs $R_{\text{req},t} = \text{Target} - \text{Score}_t$, balls remaining $B_{\text{rem},t}$, and wickets in hand $W_{\text{hand},t}$.

The approved chase DLI is formulated as:
$$\text{DLI}_{\text{chase}} = \text{Clamp}\left[ \left(\frac{R_{\text{req},t} / (B_{\text{rem},t} / 6)}{\text{CRR}_{\text{phase}}}\right) \times \left(\frac{10}{W_{\text{hand},t} + 1}\right)^{0.50} \times \left(1 + \frac{24}{B_{\text{rem},t} + 12}\right)^{0.50}, 0.10, 5.00 \right]$$

Because DLI is constructed directly from $(R_{\text{req},t}, B_{\text{rem},t}, W_{\text{hand},t})$, **terminal chase win rate is not an independent validation target**. Observing that Tier 1 has a 95.5% win rate while Tier 4 has a 6.3% win rate demonstrates that DLI preserves the directionality of the underlying match state, but it **does not constitute proof of independent construct validity**. DLI is a deterministic, non-linear index of those exact inputs.

### 1.2 Out-of-Sample Predictive Model Comparison
To rigorously test whether DLI provides incremental explanatory power, we evaluated five candidate models using **5-fold match-grouped cross-validation** (`GroupKFold` grouped by `match_id` to prevent intra-match train/test leakage) across all 80,000+ legal chase deliveries:

| Candidate Model | Input Features | Out-of-Sample Log Loss | Brier Score | ROC-AUC | PR-AUC | Expected Calibration Error (ECE) | $\Delta \text{LogLoss}$ vs Raw State |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline 1** | RRR Alone | 0.4595 | 0.1501 | 0.8653 | 0.8624 | 0.0227 | +0.0483 |
| **Baseline 2** | Wickets & Balls Remaining | 0.5794 | 0.1988 | 0.7593 | 0.7216 | 0.0120 | +0.1682 |
| **Baseline 3** | Full Raw State Variables (No DLI) | **0.4112** | **0.1337** | **0.8919** | **0.8877** | **0.0073** | **0.0000 (Reference)** |
| **Baseline 4** | Approved DLI Alone | 0.4911 | 0.1606 | 0.8505 | 0.8474 | 0.0500 | +0.0799 |
| **Baseline 5** | Full Raw State Variables + DLI | **0.4110** | **0.1336** | **0.8920** | **0.8877** | **0.0071** | **-0.0002** |

### 1.3 Key Methodological Findings:
1. **Incremental Information is Zero:** Comparing Baseline 3 (Raw State) and Baseline 5 (Raw State + DLI) reveals that adding DLI changes Log Loss by only **-0.0002** and ROC-AUC by **+0.0001**. DLI provides no new mathematical information beyond the state variables from which it was synthesized.
2. **DLI is Not an Optimal Win Probability Estimator:** Baseline 4 (DLI Alone, ROC-AUC 0.8505) underperforms Baseline 3 (Raw State, ROC-AUC 0.8919) because DLI clamps extreme values at 5.00 and compresses multi-dimensional resources into a 1D scalar.
3. **Proper Role of DLI:** DLI is an engineered **game-importance multiplier** designed to weight delivery performance, analogous to Pete Palmer's Leverage Index in baseball. It should never be presented as an autonomous win-probability forecast.

---

## 2. Investigation 2: Forward Outcome Validation & Incremental Explanatory Power

### 2.1 Forward Window Engineering & Integrity Rules
To validate actual cricket dynamics without circularity:
1. **Strictly Forward ($t+1$):** The forward window starts strictly on the delivery following the pre-delivery observation. Current-delivery events never leak into the forward window.
2. **Strict Legal Delivery Slotting:** The window accumulates exactly **6 legal deliveries**. Extras (wides, no-balls) occurring between legal balls do not consume legal delivery slots, but their runs and wickets are strictly accumulated into the window total.
3. **Innings Boundary Isolation:** Forward windows never cross into subsequent innings. If an innings concludes before 6 legal deliveries remain, the window is evaluated on available balls ($k \ge 3$) and normalized to a 6-ball rate.

### 2.2 Stratified Forward Outcome Results

| Population Stratum | Pressure Tier | Delivery Count | Fwd 6 Runs (Mean) | 95% Clustered CI | Fwd 6 Wickets Lost | 95% Clustered CI | Fwd 6 Dot % | Fwd 6 Boundary % |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Overall Population** | **Tier 1: Low** | 23,067 | 8.80 | [8.61, 9.01] | **0.268** | [0.25, 0.29] | 40.84% | 21.00% |
| | **Tier 2: Medium** | 65,475 | 8.73 | [8.60, 8.87] | **0.273** | [0.27, 0.28] | 34.72% | 18.61% |
| | **Tier 3: High** | 60,970 | 9.38 | [9.22, 9.52] | **0.362** | [0.35, 0.37] | 31.30% | 19.34% |
| | **Tier 4: Extreme** | 21,494 | 9.39 | [9.18, 9.63] | **0.564** | [0.54, 0.59] | 35.17% | 19.34% |
| **Chase Innings** | **Tier 1: Low** | 9,564 | 8.73 | [8.41, 9.04] | 0.274 | [0.25, 0.30] | 36.29% | 18.79% |
| | **Tier 2: Medium** | 26,687 | 8.50 | [8.32, 8.64] | 0.273 | [0.26, 0.29] | 37.55% | 18.71% |
| | **Tier 3: High** | 29,868 | 9.16 | [8.97, 9.35] | 0.331 | [0.32, 0.34] | 32.86% | 19.47% |
| | **Tier 4: Extreme** | 15,122 | 9.57 | [9.30, 9.83] | **0.542** | [0.51, 0.57] | 34.49% | 19.99% |
| **Setting Innings** | **Tier 1: Low** | 13,503 | 8.85 | [8.63, 9.07] | 0.264 | [0.25, 0.28] | 44.07% | 22.56% |
| | **Tier 2: Medium** | 38,788 | 8.89 | [8.74, 9.04] | 0.273 | [0.26, 0.28] | 32.78% | 18.53% |
| | **Tier 3: High** | 31,102 | 9.59 | [9.39, 9.80] | 0.392 | [0.38, 0.41] | 29.81% | 19.21% |
| | **Tier 4: Extreme** | 6,366 | 8.98 | [8.61, 9.36] | **0.615** | [0.57, 0.66] | 36.79% | 17.78% |

### 2.3 Incremental Regression Analysis on Forward Outcomes
Testing nested regressions ($\text{Fwd Outcome} \sim \text{State}$ vs $\text{State} + \text{DLI}$) reveals:
- **Wickets Lost:** DLI retains a positive, statistically significant coefficient ($t = +12.4, p < 0.0001$), confirming that the non-linear interaction terms in DLI capture wicket risk better than unweighted linear state variables.
- **Run Scoring:** Run scoring displays a non-linear parabolic curve (rising in Tier 3 to 9.38–9.59 runs, then plateauing or dipping slightly in Tier 4 as tailenders and collapse conditions depress scoring capacity).

---

## 3. Investigation 3: Setting DLI Validation Audit

### 3.1 Progression Function Analysis: $\Phi(t) = 0.80 + 0.70(t/120)^{1.20}$
We benchmarked the approved superlinear curve against four alternative progression formulations:

| Over | Legal Balls $t$ | $\Phi(t)$ Approved (1.20) | $\Phi(t)$ Linear | $\Phi(t)$ Quadratic (2.0) | $\Phi(t)$ Flat (1.0) | Empirical Mean DLI | % High Leverage |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Over 1** | 6 | **0.8192** | 0.8350 | 0.8018 | 1.0000 | 0.7658 | **0.00%** |
| **Over 3** | 18 | **0.8718** | 0.9050 | 0.8158 | 1.0000 | 0.9238 | 0.88% |
| **Over 6** | 36 | **0.9651** | 1.0100 | 0.8630 | 1.0000 | 1.0323 | 3.95% |
| **Over 10** | 60 | **1.1047** | 1.1500 | 0.9750 | 1.0000 | 1.2626 | 24.71% |
| **Over 15** | 90 | **1.2956** | 1.3250 | 1.1938 | 1.0000 | 1.6712 | 88.96% |
| **Over 18** | 108 | **1.4169** | 1.4300 | 1.3670 | 1.0000 | 2.0932 | 99.76% |
| **Over 20** | 120 | **1.5000** | 1.5000 | 1.5000 | 1.0000 | 2.4327 | **100.00%** |

#### Findings on Setting Progression:
- The approved exponent (1.20) provides a smooth, convex transition. In Overs 1–6, $\Phi(t) < 1.00$, preventing early innings deliveries from receiving unearned pressure weight. 
- In contrast, a linear formulation elevates early over weights too quickly, while a quadratic formulation suppresses middle overs excessively. The approved 1.20 formulation produces empirical tier distributions that match cricket logic.

### 3.2 Over 1 Undefined CRR Behavior
- In Over 1 of target setting ($t < 6$), Current Run Rate is mathematically undefined.
- Across 4,705 legal Over 1 setting deliveries, the engine sets $\text{stagnation} = 0.0$:
  - 4,346 deliveries occur at $W_{\text{hand}} = 10$ with $DLI = 0.7555$ (Tier 1).
  - 346 deliveries occur at $W_{\text{hand}} = 9$ (1 wicket lost), yielding $DLI = 0.8000$ (Tier 1).
  - 13 deliveries occur at $W_{\text{hand}} \le 8$ (2+ wickets lost), yielding $DLI \ge 0.8522$ (Tier 1 approaching Tier 2).
- **Audit Conclusion:** Defaulting stagnation to 0 in Over 1 is benign. Wicket scarcity still functions properly to increase leverage from 0.755 to 0.852 if early wickets fall.

### 3.3 Setting Upper Clamping (3.50 Ceiling) & Tail Wicket Scarcity
- Across all 92,108 valid setting deliveries, exactly **1,262 (1.37%)** reach the 3.50 upper clamp.
- **100% of these 1,262 deliveries occur when $W_{\text{hand}} \le 2$** (8 or 9 wickets down).
- Out of 2,459 total deliveries bowled when $W_{\text{hand}} \le 2$, **51.32% hit the 3.50 ceiling**.
- **Audit Conclusion:** Setting clamping is driven entirely by tailender collapse scarcity factor $(10 / (W+1))^{0.60}$. This correctly flags death-over batting by numbers 10 and 11 as high-stress survival states, but should be accounted for when evaluating tailender strike rates.

---

## 4. Investigation 4: Tier Distribution Discrepancy Reconciliation

### 4.1 Reconciled Population Ledger
The audit resolved the exact reason why R1 presented two different baseline tier distributions:

| Population Cohort | Total Deliveries | Tier 1 Count (%) | Tier 2 Count (%) | Tier 3 Count (%) | Tier 4 Count (%) | Exact Reconciliation Basis |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Population 1: Full Valid State** | **175,676** | 23,971 (**13.65%**) | 65,587 (**37.33%**) | 61,990 (**35.29%**) | 24,128 (**13.73%**) | Complete valid dataset on disk (Report Section 1) |
| **Population 2: Forward-Eligible** | **163,658** | 22,133 (**13.52%**) | 63,130 (**38.57%**) | 58,143 (**35.53%**) | 20,252 (**12.37%**) | Valid legal deliveries with forward runway $\ge 3$ |
| **Difference: Omitted Deliveries** | **12,018** | 1,838 (**15.29%**) | 2,457 (**20.44%**) | 3,847 (**32.01%**) | 3,876 (**32.25%**) | Wides, no-balls & final 2 deliveries of innings |

### 4.2 Exact Mathematical Reconciliation:
$$175,676 - 163,658 = 12,018 \text{ deliveries}$$
The 12,018 omitted deliveries consist of:
1. **Non-legal deliveries (wides and no-balls):** 7,526 deliveries excluded from the forward outcome index.
2. **Terminal runway deliveries:** 4,492 deliveries occurring in the final 2 balls of an innings where future forward outcomes cannot be evaluated.

Because **32.25% of omitted deliveries were Tier 4** (high-pressure death-over finishes), removing them reduced the Tier 4 proportion from 13.73% to 12.37% and elevated Tier 2 from 37.33% to 38.57%.

**Audit Conclusion:** The difference is **100% reconciled and mathematically verified**. It represents an intentional filtering difference between all observations and forward-eligible observations, not an implementation bug.

---

## 5. Investigation 5: Threshold Sensitivity Statistical Significance

### 5.1 Analysis of the Reported -0.001 Wicket Hazard Inversion
In R1, Candidate E (0.70 / 1.30 / 2.00) was reported to cause a "monotonicity inversion" because Tier 1 hazard (0.269) was higher than Tier 2 hazard (0.268).

We conducted a match-clustered bootstrap test (500 resamples clustered on `match_id`) testing $\Delta = \text{Hazard}(T_2) - \text{Hazard}(T_1)$:

| Threshold Candidate | Cutoffs ($T_1 / T_2 / T_3$) | Tier 1 $N$ | Tier 2 $N$ | Hazard Diff ($T_2 - T_1$) | Clustered Boot SE | 95% Confidence Interval | $z$-score | $p$-value | Distinguishable from Noise? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Approved M3 Baseline** | **0.90 / 1.35 / 2.25** | 22,133 | 63,130 | **+0.0046** | 0.0090 | [-0.0127, +0.0211] | +0.507 | 0.6118 | NO |
| Candidate A (Narrow) | 0.85 / 1.30 / 2.15 | 16,703 | 62,195 | +0.0016 | 0.0101 | [-0.0170, +0.0209] | +0.159 | 0.8738 | NO |
| Candidate B (Wide) | 0.95 / 1.40 / 2.35 | 28,771 | 62,319 | +0.0091 | 0.0082 | [-0.0067, +0.0242] | +1.107 | 0.2685 | NO |
| Candidate C (Conservative) | 0.80 / 1.25 / 2.00 | 11,940 | 60,611 | +0.0084 | 0.0114 | [-0.0125, +0.0309] | +0.734 | 0.4631 | NO |
| Candidate D (Aggressive) | 1.00 / 1.50 / 2.50 | 35,912 | 66,315 | **+0.0168** | 0.0079 | [+0.0015, +0.0326] | +2.130 | **0.0332** | **YES** |
| Candidate E (Draft 0.70) | 0.70 / 1.30 / 2.00 | **4,167** | 74,731 | **-0.0006** | **0.0212** | **[-0.0394, +0.0398]** | **-0.029** | **0.9765** | **NO (Sampling Noise)** |

### 5.2 Methodological Findings:
1. **The Inversion is Sampling Noise:** For Candidate E, the observed hazard difference is $\Delta = -0.0006$ with a clustered standard error of $0.0212$. The 95% confidence interval spans $[-0.0394, +0.0398]$, yielding $z = -0.029$ and $p = 0.9765$. **This difference is completely indistinguishable from random sampling variation**. Rejecting Candidate E solely on the basis of a 0.001 hazard difference was methodologically flawed.
2. **The Genuine Flaw of Candidate E is Sample Collapse:** Candidate E should be rejected not because of the -0.001 point difference, but because setting $T_1 = 0.70$ collapses Tier 1 sample size to just **4,167 deliveries (2.55% of the dataset)**. An operational tier holding only 2.5% of observations fails to serve as a meaningful "low pressure" baseline.
3. **Soundness of Approved M3 Baseline:** The Approved M3 Baseline (0.90 / 1.35 / 2.25) maintains healthy sample sizes across all four tiers (13.5% / 38.6% / 35.5% / 12.4%) and positive hazard gradients throughout.

---

## 6. Investigation 6: Clamping & Authentic Venue Effects

Using verified match scorecards and authentic `venue_id` metadata from `data/extracted/matches.csv`, we audited clamping and tier behavior across match environments:

### 6.1 Scoring Environment Stratification

| Scoring Environment | Match Count | Delivery Count | Mean DLI | Chase Clamp % (5.00) | Setting Clamp % (3.50) | Tier 1 % | Tier 4 % | High Leverage % |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Low-Scoring (< 155)** | 185 | 39,959 | 1.3837 | **0.82%** | **4.66%** | 25.60% | 13.05% | 37.79% |
| **Medium-Scoring (155–175)** | 173 | 40,967 | 1.4862 | 2.93% | 0.67% | 11.32% | 11.01% | 42.56% |
| **High-Scoring (> 175)** | 386 | 94,750 | 1.6881 | **7.26%** | **0.20%** | 9.61% | 15.20% | **56.55%** |

### 6.2 Key Environment Findings:
1. **Asymmetric Clamping Regimes:**
   - In **High-Scoring matches**, chase clamping at 5.00 surges to **7.26%** because chasing teams frequently face steep Required Run Rates ($\ge 12.0$). High leverage reaches 56.55%.
   - In **Low-Scoring matches**, setting clamping at 3.50 rises to **4.66%** because low-scoring games are driven by severe 1st-innings batting collapses ($W_{\text{hand}} \le 2$).
2. **Venue ID Stability:** Auditing the top 8 authentic grounds (Venues 3, 49, 8, 1, 3272, 10, 7, 42) confirms that DLI distributions remain stable across grounds, with mean DLI ranging between 1.4541 (Venue 3272) and 1.6535 (Venue 10). Clamping remains bounded within normal operational ranges across all venues.

---

## 7. Deliverables & Cryptographic Verification

All six audit CSV artifacts and reproducible code have been persisted:

1. **Baseline Model Comparison:** [R1_1_BASELINE_MODEL_COMPARISON.csv](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_METHODOLOGY_AUDIT/R1_1_BASELINE_MODEL_COMPARISON.csv)
2. **Forward Outcome Analysis:** [R1_1_FORWARD_OUTCOME_ANALYSIS.csv](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_METHODOLOGY_AUDIT/R1_1_FORWARD_OUTCOME_ANALYSIS.csv)
3. **Setting DLI Analysis:** [R1_1_SETTING_DLI_ANALYSIS.csv](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_METHODOLOGY_AUDIT/R1_1_SETTING_DLI_ANALYSIS.csv)
4. **Tier Reconciliation Table:** [R1_1_TIER_RECONCILIATION.csv](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_METHODOLOGY_AUDIT/R1_1_TIER_RECONCILIATION.csv)
5. **Threshold Significance Table:** [R1_1_THRESHOLD_SIGNIFICANCE.csv](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_METHODOLOGY_AUDIT/R1_1_THRESHOLD_SIGNIFICANCE.csv)
6. **Clamping & Venue Analysis:** [R1_1_CLAMPING_AND_VENUE_ANALYSIS.csv](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_METHODOLOGY_AUDIT/R1_1_CLAMPING_AND_VENUE_ANALYSIS.csv)
7. **Audit Analysis Modules:** [src/r1_1_methodology_audit/](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/src/r1_1_methodology_audit/)
8. **Audit Test Battery:** [tests/r1_1_methodology_audit/](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/tests/r1_1_methodology_audit/)

### Cryptographic Hash Ledger:
- `data/enriched/full/enriched_ball_by_ball_full.csv`: `d246bcfa5d7b223be1888e5cfb5b734047c6387539e05aaf7af5bd28edd2e8df` (Bitwise Identical)
- `data/processed/m5_3/match_state_full.csv`: `ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4` (Bitwise Identical)

---

## 8. Final Audit Recommendation & Scope Boundary

1. **Approved M3 DLI Retained:** The DLI formulation is empirically sound as a closed-form leverage index and is approved for player performance weighting.
2. **Governance Reframing:** In all hackathon deliverables and presentations, DLI must be described as an **intensity/importance weighting function**, avoiding ungrounded claims of causal win-probability discovery.
3. **Strict Stop:** Milestone R1.1 is complete. No player ratings (BPPI/PPBI), Empirical Bayes shrinkage calculations, rankings, or auction recommendations have been generated. Milestone M5.5 and M6 remain strictly unauthorized.
