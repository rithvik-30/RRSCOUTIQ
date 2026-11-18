# RR ScoutIQ — Milestone R1.1.1: Targeted Statistical Verification Report

**Classification:** **EMPIRICAL SUPPORT WITH LIMITATIONS**  
**Milestone:** R1.1.1 — Targeted Statistical Clarification & Verification  
**Status:** COMPLETE (Ready for Human Review)  
**Date:** November 2026  
**Execution Environment:** `RRScoutIQenv` (Python 3.13.9, pytest 9.2.0, pandas 2.2.3, numpy 2.2.3, scikit-learn 1.9.1, scipy 1.18.1)  
**Data Scope:** 776 approved matches, 179,837 deliveries, 175,676 valid DLI observations  
**Full Regression Test Suite:** **213 passed in ~118s** (100% pass rate, exit code 0)  

---

## Executive Summary

Milestone R1.1.1 resolves four targeted methodological questions identified during peer review of R1.1:
1. **Forward Window Exactness:** We decompose the forward runway distribution across all deliveries, isolate complete 6-legal-delivery windows ($N = 159,225$) from partial terminal windows ($N = 4,433$), and quantify the impact of partial-window exposure scaling.
2. **Setting DLI Independent Predictive Power:** We evaluate 5 nested models predicting subsequent 6-ball outcomes in setting innings using 5-fold match-grouped cross-validation, demonstrating that Setting DLI adds no incremental predictive power beyond its raw state variables.
3. **Regression Inference Audit:** We audit the econometric properties of forward outcome regressions, accounting for overlapping rolling window moving-average (MA(5)) autocorrelation and intra-match correlation via cluster-robust sandwich covariance estimation.
4. **Threshold Robustness Framing:** We re-evaluate all 6 threshold perturbation sets, formally distinguishing cohort size starvation from statistical inferiority, and framing the approved M3 baseline as an operationally balanced convention rather than an ungrounded claim of "mathematical optimality."

---

## 1. Investigation 1: Forward Window Exactness & Window Length Audit

### 1.1 Window Length Distribution
Across all 168,104 valid legal deliveries, the actual number of subsequent legal deliveries remaining in the same innings ($k$) is distributed as follows:

| Window Length $k$ | Valid Legal Deliveries ($N$) | % of Valid Legal | Treatment in R1 / R1.1 | Exposure Multiplier | Primary Cricket Context |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **$k = 6$ (Complete)** | **159,225** | **94.718%** | **Complete Full Window** | **$6 / 6 = 1.00$** | **Standard in-play overs (Overs 1.1 to 19.0)** |
| $k = 5$ (Partial) | 1,476 | 0.878% | Scaled Partial Window | $6 / 5 = 1.20$ | Over 19.1 in completed innings |
| $k = 4$ (Partial) | 1,478 | 0.879% | Scaled Partial Window | $6 / 4 = 1.50$ | Over 19.2 in completed innings |
| $k = 3$ (Partial) | 1,479 | 0.880% | Scaled Partial Window | $6 / 3 = 2.00$ | Over 19.3 in completed innings |
| $k = 2$ (Truncated) | 1,481 | 0.881% | Excluded ($k < 3$) | $6 / 2 = 3.00$ | Over 19.4 in completed innings |
| $k = 1$ (Truncated) | 1,481 | 0.881% | Excluded ($k < 3$) | $6 / 1 = 6.00$ | Over 19.5 in completed innings |
| $k = 0$ (Terminal) | 1,484 | 0.883% | Excluded ($k = 0$) | N/A | Ball 120 (Final delivery of innings) |
| **Total Valid Legal** | **168,104** | **100.000%** | — | — | — |

### 1.2 Impact of Exposure Scaling on Primary Outcome Results
In R1 and R1.1, the forward-eligible population ($N = 163,658$) combined 159,225 complete windows ($k = 6$) with 4,433 partial windows ($k \in \{3, 4, 5\}$) using the exposure multiplier $(6 / k)$. 

Recalculating the primary results on **strictly exact 6-legal-delivery windows** ($N = 159,225$) isolates the pure, unscaled cricket dynamics:

| Pressure Tier | Exact-6 $N$ | Partial $N$ | Exact-6 Runs | Combined Runs | Delta Runs | Exact-6 Wkts | Combined Wkts | Delta Wkts | Exact-6 Dot % | Exact-6 Bnd % |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Low** | 21,435 | 698 | **8.643** | 8.797 | -0.154 | **0.269** | 0.268 | +0.001 | 41.33% | 20.54% |
| **Tier 2: Medium** | 62,928 | 202 | **8.690** | 8.711 | -0.021 | **0.273** | 0.273 | 0.000 | 34.79% | 18.47% |
| **Tier 3: High** | 56,847 | 1,296 | **9.239** | 9.334 | -0.096 | **0.350** | 0.360 | -0.010 | 31.54% | 18.93% |
| **Tier 4: Extreme** | 18,015 | 2,237 | **9.317** | 9.344 | -0.027 | **0.483** | **0.564** | **-0.082** | 34.64% | 19.09% |

#### Key Methodological Takeaways:
1. **Strict Monotonicity Preserved:** On strictly exact 6-legal-ball windows, subsequent wicket hazard accelerates monotonically:
   $$\text{Wicket Hazard: } \text{Tier 1 (0.269)} \longrightarrow \text{Tier 2 (0.273)} \longrightarrow \text{Tier 3 (0.350)} \longrightarrow \text{Tier 4 (0.483)}$$
   The hazard ratio between Tier 4 and Tier 1 is **1.80x** ($0.483 / 0.269$).
2. **Partial Window Exposure Effect in Tier 4:** In Tier 4, 2,237 partial deliveries occurred in the desperate final 3–5 balls of innings where teams were slogging or getting bowled out. Because the partial window scaled wicket rate in these balls was **1.223 wickets / 6 balls**, scaling by $6/k$ inflated the combined Tier 4 hazard to 0.564. Excluding partial windows reveals the true unscaled 6-ball hazard of **0.483**.
3. **Innings Boundary Invariant:** In 100% of cases, forward windows terminate strictly at innings boundaries and never cross into subsequent innings.

---

## 2. Investigation 2: Setting DLI Independent Model Comparison

To evaluate whether Setting DLI provides incremental predictive power beyond its constituent state variables, we evaluated 5 nested specifications predicting subsequent 6-ball outcomes across all setting deliveries with exact 6-ball windows ($N = 80,000+$) using **5-fold match-grouped cross-validation** (`GroupKFold` on `match_id`):

| Model Specification | Input Features | Forward Runs Out-of-Sample $R^2$ | Forward Runs RMSE | Forward Wkts Out-of-Sample $R^2$ | Forward Wkts RMSE | Forward Dot % Out-of-Sample $R^2$ | Wicket Occurrence ROC-AUC | Wicket Occurrence Brier Score |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Spec A** | Phase & Progression ($t$, Phase) | 0.03167 | 4.8086 | 0.02802 | 0.5337 | 0.07849 | 0.5771 | 0.1989 |
| **Spec B** | Phase, Prog & Wickets ($W_{\text{hand}}$) | 0.07360 | 4.7034 | 0.02893 | 0.5334 | 0.11399 | 0.5802 | 0.1987 |
| **Spec C** | Full Raw State ($t$, Phase, $W$, $CRR$) | **0.08225** | **4.6814** | **0.02871** | **0.5335** | **0.11744** | **0.5797** | **0.1988** |
| **Spec D** | Approved Setting DLI Alone | -0.00030 | 4.8874 | 0.01458 | 0.5374 | 0.00712 | 0.5629 | 0.2009 |
| **Spec E** | Full Raw State + Setting DLI | **0.08235** | **4.6811** | **0.02915** | **0.5334** | **0.11821** | **0.5826** | **0.1986** |

### Key Methodological Findings:
1. **Incremental Predictive Value is Negligible:** Adding Setting DLI to the full raw state variables yields:
   - Forward Runs: $\Delta R^2 = +0.00010$, $\Delta \text{RMSE} = -0.0003$
   - Forward Wickets: $\Delta R^2 = +0.00044$, $\Delta \text{RMSE} = -0.0001$
   - Forward Dot %: $\Delta R^2 = +0.00077$, $\Delta \text{RMSE} = -0.0090$
   - Wicket Occurrence: $\Delta \text{AUC} = +0.0029$, $\Delta \text{Brier} = -0.0002$
2. **Interpretation:** Setting DLI does not provide independent predictive information beyond $(t, \text{Phase}, W_{\text{hand}}, CRR)$. It is a closed-form composite formula designed to scale player performance according to game stage and resource scarcity, not an autonomous forecasting engine.

---

## 3. Investigation 3: Regression Inference Audit (Econometric Disclosure)

### 3.1 Econometric Issues: Overlapping Windows & Intra-Match Clustering
When regressing forward 6-ball outcomes on delivery-level state variables:
1. **Moving-Average Autocorrelation:** Successive deliveries share 5 of the same 6 forward deliveries, inducing an **MA(5) error covariance structure**.
2. **Match-Level Random Effects:** Deliveries within the same match share unobserved pitch, venue, and weather conditions.
3. **Inference Consequence:** Classical OLS assumes i.i.d. observations. This severely underestimates standard errors and inflates $t$-statistics by a factor of 2x to 3x.

### 3.2 Regression Model Specification
- **Formula:**
  $$\text{Fwd 6 Wkts} = \beta_0 + \beta_1 W_{\text{hand}} + \beta_2 B_{\text{rem}} + \beta_3 \mathbb{I}(\text{PP}) + \beta_4 \mathbb{I}(\text{Death}) + \beta_5 \text{Rate} + \beta_6 \text{DLI} + \epsilon$$
- **Sample Size:** $N = 159,225$ exact 6-ball deliveries across $G = 744$ matches.
- **Estimation:** OLS with Liang-Zeger / Cameron-Gelbach-Miller cluster-robust sandwich covariance clustered at `match_id`.

### 3.3 Econometric Comparison Table

| Regressor Variable | Coefficient $\hat{\beta}$ | Standardized $\beta$ | Classical OLS SE | OLS $t$-stat | White Robust SE | Match-Clustered SE | Clustered $t$-stat | Clustered $p$-value | 95% Clustered CI | SE Inflation Ratio |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Intercept** | 0.21241 | 0.0000 | 0.01340 | 15.85 | 0.01381 | 0.03187 | 6.66 | < 0.0001 | [0.1498, 0.2750] | 2.38x |
| **Wickets in Hand ($W$)** | +0.02061 | +0.0779 | 0.00142 | 14.57 | 0.00145 | 0.00350 | 5.88 | < 0.0001 | [0.0137, 0.0275] | 2.48x |
| **Balls Remaining ($B_{\text{rem}}$)** | -0.00268 | -0.1575 | 0.00012 | -23.09 | 0.00011 | 0.00026 | -10.46 | < 0.0001 | [-0.0032, -0.0022] | 2.21x |
| **Powerplay ($\mathbb{I}(\text{PP})$)** | +0.08189 | +0.0707 | 0.00565 | 14.48 | 0.00523 | 0.01130 | 7.25 | < 0.0001 | [0.0597, 0.1041] | 2.00x |
| **Death ($\mathbb{I}(\text{Death})$)** | +0.08594 | +0.0605 | 0.00557 | 15.43 | 0.00589 | 0.01240 | 6.93 | < 0.0001 | [0.0616, 0.1103] | 2.23x |
| **Run Rate (CRR / RRR)** | -0.00072 | -0.0051 | 0.00055 | -1.31 | 0.00058 | 0.00127 | -0.57 | 0.5687 | [-0.0032, +0.0018] | 2.30x |
| **Approved DLI** | **+0.06382** | **+0.0891** | **0.00426** | **14.98** | **0.00453** | **0.01030** | **6.20** | **< 0.0001** | **[+0.0436, +0.0840]** | **2.42x** |

#### Inference Conclusions:
1. **SE Inflation:** Match clustering and rolling window overlap inflate standard errors by **2.42x** for DLI (SE rises from 0.00426 to 0.01030).
2. **Statistical Significance Preserved:** Even after accounting for clustering, DLI remains statistically significant ($t = 6.20, p < 0.0001$, 95% CI $[+0.0436, +0.0840]$).
3. **Practical Effect Size:** Standardized $\beta = +0.0891$. Each +1.0 DLI increases subsequent 6-ball wicket expectancy by $+0.064$ wickets.

---

## 4. Investigation 4: Threshold Robustness Interpretation & Governance Framing

### 4.1 Re-evaluation Across Candidate Cutoffs (Exact-6 Windows)

| Candidate Name | Cutoffs ($T_1 / T_2 / T_3$) | Tier 1 % | Tier 2 % | Tier 3 % | Tier 4 % | Tier 1 Hazard | Tier 2 Hazard | $\Delta (T_2 - T_1)$ | Clustered Boot SE | 95% Clustered CI | $p$-value | Operational Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Approved M3 Baseline** | **0.90 / 1.35 / 2.25** | **13.46%** | **39.52%** | **35.70%** | **11.31%** | **0.2690** | **0.2728** | **+0.0037** | 0.0091 | [-0.0145, +0.0203] | 0.6830 | **Operationally Optimal** |
| Candidate A (Narrow) | 0.85 / 1.30 / 2.15 | 10.07% | 38.93% | 37.91% | 13.09% | 0.2694 | 0.2694 | -0.0001 | 0.0102 | [-0.0204, +0.0191] | 0.9951 | Viable Perturbation |
| Candidate B (Wide) | 0.95 / 1.40 / 2.35 | 17.61% | 39.02% | 33.44% | 9.93% | 0.2675 | 0.2757 | +0.0082 | 0.0079 | [-0.0078, +0.0234] | 0.3013 | Viable Perturbation |
| Candidate C (Conservative) | 0.80 / 1.25 / 2.00 | 7.10% | 37.93% | 38.79% | 16.18% | 0.2622 | 0.2683 | +0.0060 | 0.0115 | [-0.0178, +0.0274] | 0.6001 | Viable Perturbation |
| Candidate D (Aggressive) | 1.00 / 1.50 / 2.50 | 22.08% | 41.52% | 28.21% | 8.19% | 0.2651 | 0.2810 | +0.0159 | 0.0077 | [+0.0006, +0.0301] | **0.0394** | Viable Perturbation |
| Candidate E (Draft 0.70) | 0.70 / 1.30 / 2.00 | **2.25%** | 46.74% | 34.82% | 16.18% | 0.2819 | 0.2688 | **-0.0131** | 0.0208 | [-0.0545, +0.0289] | 0.5310 | **Operationally Defective** |

### 4.2 Critical Methodological Clarification:
1. **Cohort Starvation vs Statistical Inferiority:** Candidate E's hazard difference ($\Delta = -0.0131$, $p = 0.5310$) is **not statistically significant**. Rejecting Candidate E on the basis of a "statistically demonstrated inferiority" was an overstatement. Rather, Candidate E is rejected for a clear operational defect: **Tier 1 cohort starvation (holding only 2.25% of balls)**, which leaves the low-pressure baseline with insufficient observations.
2. **Reframing "Mathematical Optimality":** The Approved M3 Baseline (0.90 / 1.35 / 2.25) is **not claimed to be globally mathematically optimal** (which cannot be proven without an arbitrary utility function). It is an **operationally balanced, robust calibration** that allocates sufficient sample volume across all four tiers (13.5% / 39.5% / 35.7% / 11.3%) while preserving monotonic hazards.
3. **Provisional Status:** The approved thresholds should remain provisional conventions for player performance weighting, subject to future recalibration if required by auction decision models.

---

## 5. Deliverables Register

All required targeted verification artifacts have been generated and persisted:

1. **Master Targeted Verification Report:** [R1_1_1_TARGETED_VERIFICATION_REPORT.md](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_1_TARGETED_VERIFICATION/R1_1_1_TARGETED_VERIFICATION_REPORT.md)
2. **Window Length Audit Table:** [R1_1_1_WINDOW_LENGTH_AUDIT.csv](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_1_TARGETED_VERIFICATION/R1_1_1_WINDOW_LENGTH_AUDIT.csv)
3. **Setting Model Comparison Table:** [R1_1_1_SETTING_MODEL_COMPARISON.csv](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_1_TARGETED_VERIFICATION/R1_1_1_SETTING_MODEL_COMPARISON.csv)
4. **Clustered Regression Audit Table:** [R1_1_1_CLUSTERED_REGRESSION_AUDIT.csv](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_1_TARGETED_VERIFICATION/R1_1_1_CLUSTERED_REGRESSION_AUDIT.csv)
5. **Threshold Robustness Table:** [R1_1_1_THRESHOLD_ROBUSTNESS.csv](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_1_TARGETED_VERIFICATION/R1_1_1_THRESHOLD_ROBUSTNESS.csv)
6. **Reproducible Python Modules:** [src/r1_1_1_targeted_verification/](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/src/r1_1_1_targeted_verification/)
7. **Verification Test Battery:** [tests/r1_1_1_targeted_verification/test_r1_1_1_verification.py](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/tests/r1_1_1_targeted_verification/test_r1_1_1_verification.py)

### Cryptographic Hash Ledger:
- `data/enriched/full/enriched_ball_by_ball_full.csv`: `d246bcfa5d7b223be1888e5cfb5b734047c6387539e05aaf7af5bd28edd2e8df` (Bitwise Identical)
- `data/processed/m5_3/match_state_full.csv`: `ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4` (Bitwise Identical)

---

## 6. Strict Scope Boundary Enforcement

- Milestone R1.1.1 is complete.
- **DO NOT BEGIN M5.5, R2, OR M6.**
- Zero player ratings (BPPI/PPBI), Empirical Bayes shrinkage calculations, rankings, or auction recommendations have been generated.
