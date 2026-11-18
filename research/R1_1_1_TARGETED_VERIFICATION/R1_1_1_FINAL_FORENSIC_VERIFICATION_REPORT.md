# RR ScoutIQ — Milestone R1.1.1: Final Forensic Verification Report

**Milestone:** R1.1.1 — Targeted Statistical Verification (Final Forensic Audit)  
**Project:** RR ScoutIQ — Pressure Performance Intelligence System (*SupeRR Selector Season 2*)  
**Evaluation Target:** Dynamic Leverage Index (DLI) Empirical Foundation & Statistical Validation  
**Execution Environment:** `RRScoutIQenv` (Python 3.13.9, pytest 9.2.0, scikit-learn 1.9.1, scipy 1.18.1, pandas 2.2.3, numpy 2.2.3)  
**Governance Disposition:** **VALIDATION PASS — EMPIRICAL SUPPORT WITH DOCUMENTED LIMITATIONS**  
**Authoritative Scope Boundaries:** VALIDATION-ONLY. Zero changes to approved M3 formulas or thresholds. Zero modifications to canonical production datasets. Zero BPPI, PPBI, Empirical Bayes shrinkage, player ratings, player rankings, or auction draft boards. Strictly prohibited from commencing M5.5, R2, or M6.

---

## Executive Summary

Before formal closure of Milestone R1.1.1, a final independent forensic verification was conducted across all four core methodological domains:
1. **Exact-Six Window Independent Reproduction:** Reconstructed all forward legal delivery windows from raw event sequences in `data/processed/m5_3/match_state_full.csv`. Verified the exact window-length distribution across all $168,104$ valid legal deliveries ($94.72\%$ complete 6-ball windows). Proved mathematically and empirically why the previously reported combined Tier 4 hazard ($0.564$) was elevated by $(6/k)$ exposure scaling over terminal partial deliveries ($k \in [3, 5]$), whereas the unscaled exact-6 hazard is $0.483$ ($0.4825$).
2. **Complete Setting DLI Model Comparison:** Recovered and compared all five nested specifications across identical match-grouped folds (`GroupKFold` on `match_id`, 5 folds, $N = 80,681$ 1st-innings deliveries). Documented that adding wickets in hand to progression increases Runs $R^2$ from $0.0183$ to $0.0576$, while Setting DLI alone explains nearly zero variation ($R^2 = 0.00019$). Adding Setting DLI to the full raw match state yields negligible incremental predictive gain ($\Delta R^2 \le +0.00077$, $\Delta \text{AUC} = +0.0028$), confirming Setting DLI functions as an operational importance weighting index rather than an autonomous predictive forecasting engine.
3. **Clustered Regression Independent Audit:** Reproduced the exact approved DLI coefficient ($\hat{\beta} = +0.063820$, standardized $\beta^* = 0.0891$). Demonstrated econometrically that the Liang-Zeger / Cameron-Gelbach-Miller cluster-robust sandwich covariance estimator ($V_{\text{cluster}} = c \cdot (X^TX)^{-1} [ \sum_g X_g^T e_g e_g^T X_g ] (X^TX)^{-1}$) directly subsumes moving-average MA(5) rolling-window correlation within its cluster score outer product, explaining the $2.42\times$ standard error inflation ($0.010297$ vs $0.004262$) without requiring a separate MA kernel. Audited the custom matrix implementation necessitated by Statsmodels absence in the environment.
4. **Threshold Adjacent-Tier Uncertainty:** Evaluated all adjacent-tier hazard differences ($\Delta H_{2-1}, \Delta H_{3-2}, \Delta H_{4-3}$) for both the Approved Baseline ($0.90 / 1.35 / 2.25$) and Candidate E ($0.70 / 1.30 / 2.00$) via a 1,000-replication match-clustered block bootstrap. Proved that Candidate E's negative point estimate ($\Delta H_{2-1} = -0.0131, p = 0.5479$) is pure statistical noise, and that Candidate E is rejected primarily due to **Tier 1 cohort starvation ($2.25\%$, $3,587$ balls)**. The Approved M3 Baseline is confirmed as an **operationally balanced convention** ($13.5\% / 39.5\% / 35.7\% / 11.3\%$), retained as provisional.

All 13 canonical production datasets and baseline files match bitwise pre- and post-pipeline. Complete regression suite passes: **213/213 passed in 112.53s**.

---

## Investigation A — Exact-Six Window Independent Reproduction

### 1. Window Construction Protocol & Integrity Invariants
Forward outcome windows were reconstructed by sorting deliveries chronologically within each match and innings (`match_id, innings, overid, over_ball_num`). For each reference delivery $i$:
- The window identifies strictly subsequent legal deliveries ($j > i$ where `ext_is_legal_delivery == True`).
- Deliveries are bounded strictly within the same innings (windows **never** cross innings boundaries).
- Deliveries with fewer than 6 future legal deliveries within that innings are identified as partial terminal windows ($k \in [1, 5]$) or terminal boundary deliveries ($k = 0$).
- Wides and no-balls inside the forward window contribute their debit runs and wicket events to the window outcomes without consuming legal ball slots.

### 2. Complete Window-Length Distribution ($N = 168,104$ Valid Legal Deliveries)

| Window Length ($k$) | Valid Legal Deliveries ($N$) | Proportion (%) | Mean Runs (Scaled) | Mean Wickets (Scaled) | Dot Ball % | Boundary % | Analysis Category |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$k = 0$** | 1,484 | 0.8828% | N/A | N/A | N/A | N/A | Terminal Delivery (0 Legal Balls Available) |
| **$k = 1$** | 1,481 | 0.8810% | 13.6367 | 1.5436 | 29.30% | 34.10% | Partial Window (1 Legal Ball Available) |
| **$k = 2$** | 1,481 | 0.8810% | 12.1884 | 1.1060 | 31.16% | 28.63% | Partial Window (2 Legal Balls Available) |
| **$k = 3$** | 1,479 | 0.8798% | 11.8066 | 0.9750 | 31.94% | 27.32% | Partial Window (3 Legal Balls Available) |
| **$k = 4$** | 1,478 | 0.8792% | 11.6245 | 0.9073 | 32.32% | 26.69% | Partial Window (4 Legal Balls Available) |
| **$k = 5$** | 1,476 | 0.8780% | 11.3821 | 0.8366 | 32.51% | 25.92% | Partial Window (5 Legal Balls Available) |
| **$k = 6$** | **159,225** | **94.7182%** | **8.9505** | **0.3236** | **34.49%** | **18.98%** | **Exact Complete Window (Primary Analysis)** |
| **Total** | **168,104** | **100.0000%** | — | — | — | — | Full Valid Legal Delivery Population |

### 3. Primary Out-of-Sample Outcomes on Exact Six-Legal-Ball Windows ($N = 159,225$)

| Pressure Tier | DLI Threshold Range | Sample Size ($N$) | Population Share (%) | Fwd 6-Ball Runs (Mean) | Fwd 6-Ball Wickets (Mean) | Fwd Dot Ball % | Fwd Boundary % |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Tier 1: Low** | $\text{DLI} < 0.90$ | 21,435 | 13.46% | 8.6432 | **0.2690** | 41.33% | 20.54% |
| **Tier 2: Medium** | $0.90 \le \text{DLI} < 1.35$ | 62,928 | 39.52% | 8.6900 | **0.2728** | 34.79% | 18.47% |
| **Tier 3: High** | $1.35 \le \text{DLI} < 2.25$ | 56,847 | 35.70% | 9.2386 | **0.3500** | 31.54% | 18.93% |
| **Tier 4: Extreme** | $\text{DLI} \ge 2.25$ | 18,015 | 11.31% | 9.3171 | **0.4825** | 34.64% | 19.09% |
| **Total Exact-6** | — | **159,225** | **100.00%** | **8.9505** | **0.3236** | **34.49%** | **18.98%** |

**Verification Confirmation:**
- Every exact-six window contains precisely 6 subsequent legal deliveries, begins strictly after the reference delivery, and never crosses an innings boundary.
- Strict hazard monotonicity is preserved: $0.2690 \to 0.2728 \to 0.3500 \to 0.4825$.
- Hazard ratio Tier 4 / Tier 1 is **$1.80\times$** ($0.4825 / 0.2690$).

### 4. Mathematical Reconciliation of Exposure Scaling $(6/k)$ in Terminal Overs
In the earlier R1/R1.1 reports, windows with runway $k \ge 3$ were included, and partial windows ($k \in [3, 5]$, $N = 4,433$) were scaled to a 6-ball rate via the multiplier $(6/k)$.
- In Tier 1: Only 698 partial deliveries occurred (Scaled Wkts = 0.230 vs Exact = 0.269).
- In Tier 2: Only 202 partial deliveries occurred (Scaled Wkts = 0.323 vs Exact = 0.273).
- In Tier 3: 1,296 partial deliveries occurred (Scaled Wkts = 0.816 vs Exact = 0.350).
- In Tier 4: **2,237 partial deliveries** occurred ($50.46\%$ of all partial deliveries in the dataset!).
  - In these terminal overs, the raw unscaled wicket loss across an average runway of ~4 balls was **$0.796$ wickets per partial window**.
  - Multiplying by $(6/k)$ produced an exposure-scaled wicket rate of **$1.2228$ wickets per 6 balls**.
  - Pooling the 18,015 exact-6 deliveries (mean $0.4825$) with the 2,237 scaled partial deliveries (mean $1.2228$) yields:
    $$\text{Combined Mean} = \frac{18,015 \times 0.4825 + 2,237 \times 1.2228}{18,015 + 2,237} = \frac{8,692.2 + 2,735.4}{20,252} = \mathbf{0.5642}$$
- **Why $(6/k)$ is an Invalid Estimator in Terminal Overs:**
  - Multiplying by $(6/k)$ assumes a **stationary, time-homogeneous Poisson process** where the instantaneous hazard rate $\lambda(t)$ is constant over the remaining balls.
  - In cricket, terminal overs under high/extreme pressure (overs 19–20 in chases, or final overs in 1st innings) represent **extreme non-stationary survival risk** (all-out slogs, run-outs, and tailender dismissals).
  - Extrapolating a 3-ball terminal burst to 6 balls assumes the team had 3 more wickets and 3 more balls to lose at that elevated burst rate, which severely distorts the true 6-ball hazard.
  - **Authoritative Resolution:** Exact-six complete windows ($N = 159,225$) must remain the primary benchmark for all future baseline comparisons. The true unscaled Tier 4 wicket hazard is **$0.483$** ($0.4825$).

All row-level and sectional results are preserved in [exact_six_independent_reproduction.csv](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_1_TARGETED_VERIFICATION/exact_six_independent_reproduction.csv).

---

## Investigation B — Complete Setting DLI Model Comparison

### 1. Model Specifications & Feature Spaces
Evaluated on the exact-six 1st-innings (Setting) population ($N = 80,681$ deliveries across $G = 744$ matches) using 5-fold match-grouped cross-validation (`GroupKFold` on `match_id`):
- **Spec 1 (Progression Only):** `[pre_legal_balls_bowled]` ($t \in [0, 120]$).
- **Spec 2 (Progression + Wickets in Hand):** `[pre_legal_balls_bowled, pre_wickets_in_hand]`.
- **Spec 3 (Full Raw Match State):** `[pre_legal_balls_bowled, pre_wickets_in_hand, is_pp, is_death, crr]`.
- **Spec 4 (Setting DLI Alone):** `[pre_dli]`.
- **Spec 5 (Full Raw Match State + Setting DLI):** `[pre_legal_balls_bowled, pre_wickets_in_hand, is_pp, is_death, crr, pre_dli]`.

### 2. Preprocessing & Out-of-Sample Protocol
- **Strict Anti-Leakage:** `StandardScaler` was fit exclusively on the training folds and applied to test folds.
- **Match-Grouped Folds:** Deliveries from the same match were strictly assigned to the same fold.
- **Continuous Targets:** Ordinary Least Squares Linear Regression. Evaluated via Out-of-Sample $R^2$, RMSE, MAE.
- **Binary Target:** Logistic Regression (`max_iter=500, random_state=42`) predicting $\Pr(\text{Wickets Lost} \ge 1)$. Evaluated via ROC-AUC, Brier score, and Log-loss.

### 3. Aggregate Out-of-Sample Model Comparison Table

| Target Outcome | Model Specification | OOF Primary Metric ($R^2$ or AUC) | OOF Secondary Metric (RMSE or Brier) | OOF Tertiary Metric (MAE or Log-loss) | Incremental Gain vs Raw State ($\Delta$) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Fwd 6-Ball Runs** | Spec 1: Progression Only | $R^2 = 0.01829$ | 4.8418 | 3.8564 | Baseline |
| | Spec 2: Progression + Wickets in Hand | $R^2 = 0.05757$ | 4.7439 | 3.7738 | $+0.03928$ |
| | Spec 3: Full Raw State (Prog, Wkt, Phase, CRR) | $R^2 = 0.08184$ | 4.6824 | 3.7215 | $+0.06355$ |
| | Spec 4: Setting DLI Alone | $R^2 = 0.00019$ | 4.8862 | 3.8804 | $-0.08165$ |
| | Spec 5: Full Raw State + Setting DLI | $R^2 = \mathbf{0.08181}$ | 4.6825 | 3.7217 | **$\Delta R^2 = -0.00003$** |
| **Fwd 6-Ball Wickets** | Spec 1: Progression Only | $R^2 = 0.02016$ | 0.5358 | 0.4478 | Baseline |
| | Spec 2: Progression + Wickets in Hand | $R^2 = 0.02081$ | 0.5357 | 0.4474 | $+0.00065$ |
| | Spec 3: Full Raw State (Prog, Wkt, Phase, CRR) | $R^2 = 0.02898$ | 0.5334 | 0.4442 | $+0.00882$ |
| | Spec 4: Setting DLI Alone | $R^2 = 0.01455$ | 0.5374 | 0.4502 | $-0.01443$ |
| | Spec 5: Full Raw State + Setting DLI | $R^2 = \mathbf{0.02916}$ | 0.5334 | 0.4439 | **$\Delta R^2 = +0.00018$** |
| **Fwd 6-Ball Dot %** | Spec 1: Progression Only | $R^2 = 0.06817$ | 21.1341 | 17.2137 | Baseline |
| | Spec 2: Progression + Wickets in Hand | $R^2 = 0.10567$ | 20.7046 | 16.8556 | $+0.03750$ |
| | Spec 3: Full Raw State (Prog, Wkt, Phase, CRR) | $R^2 = 0.11764$ | 20.5655 | 16.7492 | $+0.04947$ |
| | Spec 4: Setting DLI Alone | $R^2 = 0.00743$ | 21.8121 | 17.3511 | $-0.11021$ |
| | Spec 5: Full Raw State + Setting DLI | $R^2 = \mathbf{0.11831}$ | 20.5576 | 16.7556 | **$\Delta R^2 = +0.00067$** |
| **Fwd 6-Ball Bnd %** | Spec 1: Progression Only | $R^2 = -0.00020$ | 17.4743 | 13.7637 | Baseline |
| | Spec 2: Progression + Wickets in Hand | $R^2 = 0.02373$ | 17.2640 | 13.6571 | $+0.02393$ |
| | Spec 3: Full Raw State (Prog, Wkt, Phase, CRR) | $R^2 = 0.06310$ | 16.9123 | 13.5063 | $+0.06330$ |
| | Spec 4: Setting DLI Alone | $R^2 = 0.00233$ | 17.4522 | 13.7429 | $-0.06077$ |
| | Spec 5: Full Raw State + Setting DLI | $R^2 = \mathbf{0.06372}$ | 16.9067 | 13.5145 | **$\Delta R^2 = +0.00062$** |
| **Wicket Occurrence** | Spec 1: Progression Only | $\text{AUC} = 0.5769$ | 0.1997 | 0.5884 | Baseline |
| | Spec 2: Progression + Wickets in Hand | $\text{AUC} = 0.5784$ | 0.1996 | 0.5881 | $+0.0015$ |
| | Spec 3: Full Raw State (Prog, Wkt, Phase, CRR) | $\text{AUC} = 0.5797$ | 0.1987 | 0.5859 | $+0.0028$ |
| | Spec 4: Setting DLI Alone | $\text{AUC} = 0.5626$ | 0.2009 | 0.5909 | $-0.0171$ |
| | Spec 5: Full Raw State + Setting DLI | $\text{AUC} = \mathbf{0.5825}$ | 0.1986 | 0.5857 | **$\Delta \text{AUC} = +0.0028$** |

### 4. Predictive Association vs Causal Interpretation
- **Predictive Association:** Adding wickets in hand to match progression (Spec 2 vs Spec 1) provides substantial predictive lift for scoring velocity and dot ball frequency. However, Setting DLI alone (Spec 4) performs very poorly as an autonomous predictor ($R^2 = 0.00019$ for runs, $R^2 = 0.00743$ for dot balls), and adding it to the full raw state yields $\Delta R^2 \le +0.00067$.
- **Causal Interpretation:** Setting DLI does not "cause" runs or wickets. It is a deterministic, heuristic weight:
  $$\text{DLI}_{\text{setting}} = \text{Clamp}\left[ \Phi(t) \times \left(\frac{10}{W_{\text{hand}} + 1}\right)^{0.50}, 0.10, 5.00 \right]$$
  Its purpose in RR ScoutIQ is not to forecast subsequent over outcomes, but to provide an **objective situational difficulty weight** so that a dot ball or wicket in over 19 with 2 wickets in hand is appropriately weighted higher than in over 2 with 10 wickets in hand.

All fold-level and aggregate CV results are preserved in [setting_model_complete_comparison.csv](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_1_TARGETED_VERIFICATION/setting_model_complete_comparison.csv).

---

## Investigation C — Clustered Regression Independent Audit

### 1. Regression Specification & Sample Filters
- **Sample:** All valid DLI, legal deliveries with exact complete 6-legal-ball forward windows across both innings ($N = 159,225$ observations, $G = 744$ matches).
- **Dependent Variable ($y$):** Forward 6-ball wickets lost (`fwd_wkts_scaled` $\in [0, 6]$). Mean = $0.3236$, $\text{SD} = 0.6019$.
- **Independent Variables ($X$):**
  - Intercept ($1.0$)
  - Wickets in Hand ($W_{\text{hand}} \in [1, 10]$)
  - Legal Balls Remaining ($B_{\text{rem}} \in [0, 119]$)
  - Powerplay Indicator ($I(\text{Phase} == \text{Powerplay})$)
  - Death Phase Indicator ($I(\text{Phase} == \text{Death})$)
  - Run Rate ($RRR$ in chase, $CRR$ in setting)
  - Approved DLI ($\text{DLI} \in [0.10, 5.00]$, Mean = $1.472$, $\text{SD} = 0.8402$)

### 2. Independent Reproduction of Regression Results

| Variable | Raw Coeff ($\hat{\beta}$) | Standardized $\beta^*$ | Classical OLS SE | White HC1 SE | Match-Clustered SE | $t$-statistic (Clustered) | $p$-value (Clustered) | 95% Clustered CI | SE Inflation Ratio |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Intercept** | $+0.212407$ | $0.0000$ | $0.013397$ | $0.013810$ | **$0.031873$** | $6.664$ | $< 0.0001$ | $[+0.14983, +0.27498]$ | $2.38\times$ |
| **Wickets in Hand** | $+0.020609$ | $+0.0779$ | $0.001415$ | $0.001447$ | **$0.003502$** | $5.885$ | $< 0.0001$ | $[+0.01373, +0.02748]$ | $2.48\times$ |
| **Balls Remaining** | $-0.002677$ | $-0.1575$ | $0.000116$ | $0.000113$ | **$0.000256$** | $-10.460$ | $< 0.0001$ | $[-0.00318, -0.00217]$ | $2.21\times$ |
| **Powerplay** | $+0.081885$ | $+0.0707$ | $0.005654$ | $0.005231$ | **$0.011297$** | $7.248$ | $< 0.0001$ | $[+0.05971, +0.10406]$ | $2.00\times$ |
| **Death Phase** | $+0.085938$ | $+0.0605$ | $0.005570$ | $0.005893$ | **$0.012397$** | $6.932$ | $< 0.0001$ | $[+0.06160, +0.11028]$ | $2.23\times$ |
| **Run Rate** | $-0.000724$ | $-0.0051$ | $0.000552$ | $0.000582$ | **$0.001270$** | $-0.570$ | $0.56865$ | $[-0.00322, +0.00177]$ | $2.30\times$ |
| **Approved DLI** | **$+0.063820$** | **$+0.0891$** | **$0.004262$** | **$0.004530$** | **$0.010297$** | **$6.198$** | **$< 0.0001$** | **$[+0.04360, +0.08404]$** | **$2.42\times$** |

### 3. Covariance Estimator & Overlapping Window MA(5) Subsumption
- **Estimator Identified:** The implemented covariance matrix is the Liang-Zeger (1986) / Cameron, Gelbach & Miller (2011) cluster-robust sandwich covariance estimator:
  $$V_{\text{CR}}(\hat{\beta}) = c \cdot (X^T X)^{-1} \left( \sum_{g=1}^G X_g^T e_g e_g^T X_g \right) (X^T X)^{-1}, \quad c = \frac{G}{G-1} \cdot \frac{N-1}{N-K}$$
  where $G = 744, N = 159,225, K = 7$, yielding degrees of freedom $\text{df} = G - 1 = 743$.
- **Why Match Clustering Subsumes Rolling Window MA(5) Autocorrelation:**
  - In a rolling forward window of 6 legal deliveries, delivery $t$ and delivery $t+1$ share 5 legal balls in common. Under OLS, their error terms $e_t$ and $e_{t+1}$ exhibit moving-average correlation $\text{Cov}(e_t, e_{t+s}) > 0$ for $s \le 5$.
  - However, all rolling windows from match $g$ belong to the same match cluster $g$.
  - In the cluster-robust sandwich estimator, the score vector for cluster $g$ is $S_g = X_g^T e_g = \sum_{i \in g} x_i e_i$.
  - The cluster "meat" matrix is the outer product of this total score:
    $$S_g S_g^T = \left(\sum_{i \in g} x_i e_i\right) \left(\sum_{j \in g} x_j e_j\right)^T = \sum_{i \in g} \sum_{j \in g} e_i e_j x_i x_j^T$$
  - Notice that this sum includes the cross-products $e_i e_j x_i x_j^T$ for **every pair of deliveries $(i, j)$ in the match**, with no restriction on the lag $|i - j|$.
  - Consequently, the intra-match serial correlation induced by rolling 6-ball window overlap (lags $1 \le |i - j| \le 5$), as well as pitch/weather match-level common shocks, are **fully and non-parametrically captured** in the cluster meat matrix.
  - **Clarification:** No separate Newey-West or MA(5) HAC kernel was implemented, nor was one needed; the match-clustering block naturally subsumes the overlapping window dependency.

### 4. Coefficient Standardization & Statsmodels Availability Investigation
- **Standardization Method:** Standardized coefficients are defined by the standard econometric formulation:
  $$\beta^*_j = \hat{\beta}_j \times \frac{\text{SD}(X_j)}{\text{SD}(Y)} = 0.063820 \times \frac{0.8402}{0.6019} = \mathbf{0.0891}$$
  This indicates that a $1.0$ standard deviation increase in DLI is associated with a $+0.0891$ standard deviation increase in forward 6-ball wicket loss (+0.0536 wickets per SD of DLI).
- **Statsmodels Investigation:**
  - An attempt to import `statsmodels.api` in `RRScoutIQenv` raised `ModuleNotFoundError`.
  - The analysis used a custom closed-form matrix implementation in `numpy` and `scipy.stats`.
  - Forensic audit confirms that the custom matrix implementation strictly follows the textbook Liang-Zeger / Cameron-Gelbach-Miller sandwich covariance formulation, with finite-sample degrees-of-freedom correction $c = \frac{G}{G-1} \frac{N-1}{N-K}$ and Student's $t$-distribution critical values at $\text{df} = 743$.

All regression diagnostics and covariance matrices are preserved in [clustered_covariance_reproduction.csv](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_1_TARGETED_VERIFICATION/clustered_covariance_reproduction.csv).

---

## Investigation D — Threshold Adjacent-Tier Uncertainty

### 1. Match-Clustered Bootstrap Protocol
To assess the uncertainty of adjacent-tier hazard contrasts ($\Delta H_{2-1}, \Delta H_{3-2}, \Delta H_{4-3}$) without making parametric error assumptions:
- **Resampling Unit:** Entire matches (`match_id` cluster blocks, $G = 744$), preserving all intra-match serial correlation, team tactics, and rolling-window structures.
- **Replications:** $B = 1,000$ bootstrap iterations.
- **Random Seed:** Fixed seed `42` for strict reproducibility.
- **Sample:** Exact-six complete windows ($N = 159,225$).

### 2. Adjacent-Tier Contrast Results

| Partition Scheme | Cutoffs ($T_1 / T_2 / T_3$) | Adjacent Tier Contrast | Point Estimate ($\Delta H$) | Clustered Boot SE | 95% Percentile CI | $z$-statistic | $p$-value | Lower Tier $N$ | Upper Tier $N$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Approved M3 Baseline** | $[0.90 / 1.35 / 2.25]$ | $\Delta H_{2-1}$ ($T_2 - T_1$) | $+0.00373$ | $0.00916$ | $[-0.01470, +0.02089]$ | $0.407$ | $0.6842$ | 21,435 | 62,928 |
| | | $\Delta H_{3-2}$ ($T_3 - T_2$) | $+0.07724$ | $0.00678$ | $[+0.06460, +0.09070]$ | $11.393$ | $< 0.0001$ | 62,928 | 56,847 |
| | | $\Delta H_{4-3}$ ($T_4 - T_3$) | $+0.13253$ | $0.01099$ | $[+0.11187, +0.15486]$ | $12.059$ | $< 0.0001$ | 56,847 | 18,015 |
| **Candidate E (Draft)** | $[0.70 / 1.30 / 2.00]$ | $\Delta H_{2-1}$ ($T_2 - T_1$) | $-0.01306$ | $0.02173$ | $[-0.05739, +0.02789]$ | $-0.601$ | $0.5479$ | **3,587** | 74,425 |
| | | $\Delta H_{3-2}$ ($T_3 - T_2$) | $+0.06564$ | $0.00681$ | $[+0.05218, +0.07847]$ | $9.639$ | $< 0.0001$ | 74,425 | 55,443 |
| | | $\Delta H_{4-3}$ ($T_4 - T_3$) | $+0.12983$ | $0.00979$ | $[+0.11098, +0.14994]$ | $13.261$ | $< 0.0001$ | 55,443 | 25,770 |

### 3. Key Methodological & Governance Insights
1. **Candidate E Disqualification Reason:**
   - Under Candidate E ($T_1 = 0.70$), Tier 1 contracts to **$3,587$ legal balls ($2.25\%$ of the dataset)** across 744 matches (averaging fewer than 5 balls per match).
   - This creates severe **cohort sample starvation**, making baseline low-pressure normalization highly unstable across individual players.
   - The observed negative hazard difference ($\Delta H_{2-1} = -0.0131$) has a clustered bootstrap standard error of $0.0217$ and a 95% CI of $[-0.0574, +0.0279]$ ($p = 0.5479$). It is **statistically indistinguishable from zero**.
   - Candidate E is rejected due to **cohort size collapse**, not because $-0.0131$ represents a statistically significant inversion.
2. **Approved M3 Baseline Framing:**
   - The Approved M3 Baseline thresholds ($0.90 / 1.35 / 2.25$) produce balanced cohort distributions: Tier 1 ($13.46\%$), Tier 2 ($39.52\%$), Tier 3 ($35.70\%$), Tier 4 ($11.31\%$).
   - $\Delta H_{2-1} = +0.0037$ ($p = 0.6842$) reflects an empirically flat baseline between Low and Moderate pressure, while $\Delta H_{3-2} = +0.0772$ ($p < 0.0001$) and $\Delta H_{4-3} = +0.1325$ ($p < 0.0001$) exhibit massive, statistically undeniable risk step-ups.
   - The Approved Baseline is confirmed as an **operationally defensible and stable convention**, rather than a "globally mathematically optimal" partition. It is retained strictly as provisional.

All threshold bootstrap distributions and confidence intervals are preserved in [threshold_adjacent_tier_uncertainty.csv](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_1_TARGETED_VERIFICATION/threshold_adjacent_tier_uncertainty.csv).

---

## Canonical Cryptographic Verification (All 13 Files)

All 13 authoritative production datasets and historical baselines were verified bit-for-bit using SHA-256 both immediately prior to and immediately following verification execution:

| File Artifact | Canonical Path | Authoritative SHA-256 Digest | Pre-Check | Post-Check |
| :--- | :--- | :--- | :---: | :---: |
| **Protected Data Pack** | `data/data_pack.zip.zip` | `788f681b538ba95fb61bcaba7b7280e59a7789d043e7964ac3472c3d08291853` | MATCH | MATCH |
| **Protected Ball by Ball** | `data/extracted/ball_by_ball.csv` | `a3926f49d2c684dca2a5d2de535a02c5ee46ea654ca1e79dd31c69e7544e9889` | MATCH | MATCH |
| **Protected Matches** | `data/extracted/matches.csv` | `bb100ab84b8b9a15160c1f2315cf675210131a30e779ec5079fd5403dcf56eef` | MATCH | MATCH |
| **Protected Competitions** | `data/extracted/competitions.csv` | `507ceb7189f972d4e4f299ddcfc97f3c3247af1913f6291106f161fa8353fd9b` | MATCH | MATCH |
| **Protected Teams** | `data/extracted/teams.csv` | `a65e5922a9b3bf49247b24fc9471782e700efb31f8dcc5042923238b87c50a5d` | MATCH | MATCH |
| **Protected Playing Eleven** | `data/extracted/playing_eleven.csv` | `7517c73722a28d5d61c808ccf0cbed315a8780586d02e946eb9a7f5daf011c27` | MATCH | MATCH |
| **Protected Player Mapping** | `data/extracted/competition_team_player_mapping.csv` | `1ded4e42a933618572d6e2c3a521c3257eb1844fab4456d567d77cbb2d3bbb12` | MATCH | MATCH |
| **Protected Enriched Pilot** | `data/enriched/pilot/enriched_ball_by_ball_pilot.csv` | `a71f3ca75d3ba7aab60b797f78726f7d19551bde1221a3c97ed342c7fb0f9878` | MATCH | MATCH |
| **M5.2 Enriched Full** | `data/enriched/full/enriched_ball_by_ball_full.csv` | `d246bcfa5d7b223be1888e5cfb5b734047c6387539e05aaf7af5bd28edd2e8df` | MATCH | MATCH |
| **M5.3 Match State Full** | `data/processed/m5_3/match_state_full.csv` | `ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4` | MATCH | MATCH |
| **M5.3 Validation Summary** | `data/processed/m5_3/match_state_validation_summary.csv` | `e7998fd4f81a292585e6c23d85136a83996d9c51e5333865a6aa57a71cb6df71` | MATCH | MATCH |
| **M5.3 Exclusion Register** | `data/processed/m5_3/match_state_exclusion_register.csv` | `a193bfec188f5d2e59133dd69c60cefde9144f3a7e3a67fdfdfee6a3d6c47cf0` | MATCH | MATCH |
| **M5.3 Match Summary** | `data/processed/m5_3/match_state_match_summary.csv` | `9b9249dbbde001689b74eb3d49d041d58ee5ffa94d8f77a132d03c022c4e39f6` | MATCH | MATCH |

**Result:** 100% Bitwise Cryptographic Immutability Confirmed. Zero files modified.

---

## Regression Test Suite Execution

The complete project regression suite was executed in `RRScoutIQenv`:
- **Command:** `python -m pytest -v`
- **Total Tests Collected:** 213
- **Passed:** 213
- **Failed:** 0
- **Skipped:** 0
- **Exit Code:** 0
- **Duration:** 112.53s

---

## Artifact Register

The following authoritative deliverables have been generated and persisted:

| Artifact Name | Canonical Path | Description |
| :--- | :--- | :--- |
| **Master Forensic Report** | [R1_1_1_FINAL_FORENSIC_VERIFICATION_REPORT.md](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_1_TARGETED_VERIFICATION/R1_1_1_FINAL_FORENSIC_VERIFICATION_REPORT.md) | Authoritative forensic report across Investigations A through D. |
| **Exact-Six Reconstruction CSV** | [exact_six_independent_reproduction.csv](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_1_TARGETED_VERIFICATION/exact_six_independent_reproduction.csv) | Full window distribution (0..6), exact-6 tier outcomes, partial window exposure audit. |
| **Setting Model Comparison CSV** | [setting_model_complete_comparison.csv](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_1_TARGETED_VERIFICATION/setting_model_complete_comparison.csv) | Fold-level and aggregate CV metrics across all 5 model specifications. |
| **Clustered Covariance Reproduction CSV** | [clustered_covariance_reproduction.csv](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_1_TARGETED_VERIFICATION/clustered_covariance_reproduction.csv) | OLS vs White HC1 vs Match-Clustered covariance, SE inflation ratios, standardized betas. |
| **Threshold Adjacent Uncertainty CSV** | [threshold_adjacent_tier_uncertainty.csv](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_1_TARGETED_VERIFICATION/threshold_adjacent_tier_uncertainty.csv) | Match-clustered block bootstrap adjacent-tier hazard differences ($B=1,000$). |

---

## Final Governance Recommendation & Disposition

### Recommended Status: EMPIRICAL SUPPORT WITH DOCUMENTED LIMITATIONS
1. **Core Findings Validated:** The approved DLI captures meaningful situational difficulty and preserves monotonic wicket hazard ordering ($0.269 \to 0.273 \to 0.350 \to 0.483$) across exact complete 6-ball windows.
2. **Documented Limitations Preserved:**
   - DLI is an operational situational weighting index, not an autonomous forecasting engine.
   - Exposure scaling $(6/k)$ on partial windows is invalid in terminal overs; exact-six complete windows ($N = 159,225$) must remain the primary benchmark.
   - Approved thresholds ($0.90 / 1.35 / 2.25$) are operationally defensible conventions, not mathematically unique optima, and remain provisional.
3. **Execution Stop Enforced:** No BPPI, PPBI, player ratings, shrinkage, or draft boards have been produced. All work ceases immediately to allow independent human audit.
