# RR ScoutIQ — Milestone R1.1.1: Final Interaction Model Correction & Targeted Validation Report

**Milestone:** R1.1.1 — Final Interaction Model Correction & Targeted Statistical Verification  
**Project:** RR ScoutIQ — Pressure Performance Intelligence System (*SupeRR Selector Season 2*)  
**Status:** Verification Complete — **EMPIRICAL SUPPORT WITH DOCUMENTED LIMITATIONS**  
**Execution Environment:** `RRScoutIQenv` (Python 3.13.9, pytest 9.2.0, scikit-learn 1.9.1, scipy 1.18.1, pandas 2.2.3, numpy 2.2.3)  
**Sample Population:** Exact-Six Legal Delivery Runway ($N = 159,225$ deliveries across $G = 744$ match clusters)  
**Dependent Variable:** Forward Wicket Hazard Exposure ($y = \text{fwd\_wkts\_scaled} = \text{actual wickets in forward 6 legal deliveries}$)  

---

## Executive Summary

This targeted validation resolves the remaining econometric and interpretation questions regarding the innings-interaction specification in Milestone R1.1.1. Previously, an interaction model restricted the control variable coefficients (wickets in hand, balls remaining, match phase indicators, and run rates) to be identical across innings, allowing only the Dynamic Leverage Index ($\text{DLI}$) slope to differ. 

To determine whether this restriction distorted the test of equal DLI slopes, we estimated a **fully interacted regression model** interacting the innings indicator ($I(\text{Chase})$) with **ALL** explanatory variables (including the intercept and all five control covariates). We evaluated:
1. A direct linear contrast test of the DLI slope difference between Setting and Chasing:
   $$H_0: \beta_{\text{DLI, setting}} = \beta_{\text{DLI, chase}} \iff \beta_{\text{diff}} = 0$$
2. A formal **joint match-clustered Wald test** of all five control interactions simultaneously, verified under both raw and correlation-standardized covariance scalings:
   $$H_0: \beta_{W_{\text{hand}}\times\text{Chase}} = \beta_{B_{\text{rem}}\times\text{Chase}} = \beta_{\text{PP}\times\text{Chase}} = \beta_{\text{Death}\times\text{Chase}} = \beta_{\text{Rate}\times\text{Chase}} = 0$$
3. A rigorous econometric reassessment of the pooled model, characterizing $\hat{\beta}_{\text{DLI}} = +0.063820$ strictly as a **pooled conditional association under the original regression specification**, while avoiding causal terminology and rejecting claims of parameter equivalence or structural common effects.

### Key Empirical Findings

1. **Setting DLI Slope:** $\hat{\beta}_{\text{DLI, setting}} = \mathbf{+0.09502}$ (Match-Clustered $\text{SE} = 0.030980, t = 3.067, p = 0.00224$).
2. **Chasing DLI Slope:** $\hat{\beta}_{\text{DLI, chase}} = \mathbf{+0.06720}$ (Match-Clustered $\text{SE} = 0.016536, t = 4.064, p < 0.0001$).
3. **Linear Contrast Slope Difference ($\text{Chase} - \text{Setting}$):** $\Delta \hat{\beta} = \mathbf{-0.02781}$ ($\text{Setting} - \text{Chase} = \mathbf{+0.02781}$).
4. **Match-Clustered SE of Difference:** $\mathbf{0.035608}$ (Cluster inflation ratio $= 2.38\times$ over classical SE of $0.014970$).
5. **Clustered Contrast $t$-Statistic:** $t = \frac{-0.02781}{0.035608} = \mathbf{-0.781}$.
6. **Two-Sided Clustered $p$-Value:** $p = \mathbf{0.43498} \approx \mathbf{0.435}$.
7. **95% Clustered Confidence Interval of Difference:** $[-0.09772, +0.04209]$.
8. **Corrected Contrast Interpretation:** The nonsignificant contrast ($p = 0.435$) represents a **failure to reject equal slopes**; it does **not** establish slope equality or practical equivalence. The confidence interval $[-0.09772, +0.04209]$ is wide and permits potentially substantial cricket differences (from an essentially flat slope of $-0.0027$ in chase up to $+0.1371$, which would be $44\%$ steeper than setting). No retrospective equivalence margin is assumed.
9. **Joint Wald Test of Control Interactions:** $W = \mathbf{7.2020}$ ($\text{df} = 5, p = \mathbf{0.20604}$); equivalent $F(5, 743) = \mathbf{1.4404}$ ($p = \mathbf{0.20747}$). The joint null of zero control interactions is **not rejected** at $\alpha = 0.05$.
10. **Covariance Matrix Numerical Stability:** Correlation-standardized scaling ($D = \text{diag}(1/\text{SE})$) reduces the condition number from $8238.45$ (raw unit artifact) to $\mathbf{9.3663}$ ($< 10.0$), with eigenvalues in $[\mathbf{0.218439}, \mathbf{2.045959}]$, full numerical rank ($5/5$), and exact machine-epsilon invariance ($|W^* - W| = 8.88 \times 10^{-16}$).
11. **Pooled-Model Descriptive Status:** The original pooled coefficient ($\hat{\beta}_{\text{DLI}} = +0.063820, t = 6.198, p < 0.0001$) is characterized strictly as a **pooled conditional association under the original regression specification**. It is not claimed to be a minimum-variance estimator, a simple sample-weighted average, or a structural common-effect estimate.

---

## 1. Specification of the Fully Interacted Model

### 1.1 Mathematical Formulation

Let $i \in \{1, \dots, N\}$ index deliveries within match cluster $g \in \{1, \dots, G\}$ ($N = 159,225, G = 744$). Let $C_i = I(\text{Innings}_i = 2)$ be the indicator variable for chasing innings ($C_i = 1$ for Chase, $C_i = 0$ for Setting).

The fully interacted model includes the main effects of all covariates and their cross-products with $C_i$:

$$
\begin{aligned}
y_i = \beta_0 &+ \beta_1 W_i + \beta_2 B_i + \beta_3 \text{PP}_i + \beta_4 \text{Death}_i + \beta_5 R_i + \beta_6 \text{DLI}_i \\
&+ \gamma_0 C_i + \gamma_1 (W_i \times C_i) + \gamma_2 (B_i \times C_i) + \gamma_3 (\text{PP}_i \times C_i) + \gamma_4 (\text{Death}_i \times C_i) + \gamma_5 (R_i \times C_i) + \gamma_6 (\text{DLI}_i \times C_i) + \varepsilon_i
\end{aligned}
$$

Where:
- $y_i$: Forward wicket hazard exposure ($\text{fwd\_wkts\_scaled}$, count of wickets lost in the exact subsequent 6 legal deliveries).
- $W_i$: Wickets in hand ($W_{\text{hand}} \in [1, 10]$).
- $B_i$: Legal balls remaining in the innings ($B_{\text{rem}} \in [0, 119]$).
- $\text{PP}_i$: Powerplay indicator ($I(\text{Over} < 6)$).
- $\text{Death}_i$: Death overs indicator ($I(\text{Over} \ge 16)$).
- $R_i$: Canonical run rate ($R_i = \text{CRR}$ for Setting; $R_i = \text{RRR}$ for Chasing).
- $\text{DLI}_i$: Approved M3 Dynamic Leverage Index ($DLI \in [0.10, 5.00]$).
- $C_i$: Chasing innings indicator ($I(\text{Chase})$).

In this formulation:
- The base coefficients ($\beta_0, \dots, \beta_6$) represent the parameters for **Setting innings** ($C_i = 0$).
- The interaction coefficients ($\gamma_0, \dots, \gamma_6$) represent the **differential shifts** for **Chasing innings** ($C_i = 1$).
- The total parameters for Chasing innings are given by $\beta_k + \gamma_k$.
- The parameter $\gamma_6$ is precisely the **linear contrast** $\beta_{\text{DLI, chase}} - \beta_{\text{DLI, setting}}$.

### 1.2 Clustered Sandwich Covariance Implementation

All inference is conducted using the Liang-Zeger / Cameron-Gelbach-Miller match-clustered sandwich estimator with small-sample finite correction:

$$
V_{\text{cluster}} = (X^T X)^{-1} \left[ \left(\frac{G}{G - 1}\right) \left(\frac{N - 1}{N - K}\right) \sum_{g=1}^G X_g^T \hat{\varepsilon}_g \hat{\varepsilon}_g^T X_g \right] (X^T X)^{-1}
$$

Where $N = 159,225$, $K = 14$, $G = 744$, $X_g$ is the submatrix of regressors for match $g$, and $\hat{\varepsilon}_g$ is the vector of OLS residuals for match $g$.

---

## 2. Complete Fully Interacted Regression Results

Below are the complete estimation results for the fully interacted model ($N = 159,225$, $G = 744$ match clusters), persisted in `research/R1_1_1_TARGETED_VERIFICATION/fully_interacted_regression.csv`:

| Parameter / Variable | Coeff ($\hat{\beta}$) | Std Coeff | OLS SE | White HC1 SE | Clustered SE | Clustered $t$ | $p$-value | 95% Clustered Conf Int | Inflation Ratio |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Base Intercept (Setting)** | $+0.08349$ | $0.0000$ | $0.042914$ | $0.043145$ | $0.101225$ | $+0.825$ | $0.40972$ | $[-0.11523, +0.28222]$ | $2.36\times$ |
| **Base $W_{\text{hand}}$ (Setting)** | $+0.03003$ | $+0.1135$ | $0.002679$ | $0.002630$ | $0.006598$ | $+4.552$ | $< 0.0001$ | $[+0.01708, +0.04299]$ | $2.46\times$ |
| **Base $B_{\text{rem}}$ (Setting)** | $-0.00277$ | $-0.1628$ | $0.000175$ | $0.000172$ | $0.000364$ | $-7.600$ | $< 0.0001$ | $[-0.00348, -0.00205]$ | $2.08\times$ |
| **Base $I(\text{PP})$ (Setting)** | $+0.08661$ | $+0.0747$ | $0.007959$ | $0.007266$ | $0.015492$ | $+5.590$ | $< 0.0001$ | $[+0.05619, +0.11702]$ | $1.95\times$ |
| **Base $I(\text{Death})$ (Setting)** | $+0.08992$ | $+0.0633$ | $0.008038$ | $0.008207$ | $0.017291$ | $+5.201$ | $< 0.0001$ | $[+0.05598, +0.12387]$ | $2.15\times$ |
| **Base Rate (Setting CRR)** | $+0.00124$ | $+0.0088$ | $0.001026$ | $0.001003$ | $0.002193$ | $+0.564$ | $0.57272$ | $[-0.00307, +0.00554]$ | $2.14\times$ |
| **Setting DLI Slope ($\beta_{\text{DLI, setting}}$)** | $\mathbf{+0.09502}$ | $+0.1326$ | $0.013415$ | $0.013886$ | $\mathbf{0.030980}$ | $\mathbf{+3.067}$ | $\mathbf{0.00224}$ | $[+0.03420, +0.15584]$ | $2.31\times$ |
| **Diff Intercept (Chase - Setting)** | $+0.17058$ | $+0.1560$ | $0.046579$ | $0.047127$ | $0.113059$ | $+1.509$ | $0.13178$ | $[-0.05137, +0.39253]$ | $2.43\times$ |
| **Diff $W_{\text{hand}}$ (Chase - Setting)** | $-0.01517$ | $-0.1116$ | $0.003294$ | $0.003307$ | $0.008171$ | $-1.856$ | $0.06381$ | $[-0.03121, +0.00087]$ | $2.48\times$ |
| **Diff $B_{\text{rem}}$ (Chase - Setting)** | $+0.00039$ | $+0.0283$ | $0.000243$ | $0.000240$ | $0.000514$ | $+0.749$ | $0.45380$ | $[-0.00062, +0.00139]$ | $2.12\times$ |
| **Diff $I(\text{PP})$ (Chase - Setting)** | $-0.01148$ | $-0.0078$ | $0.011360$ | $0.010512$ | $0.022442$ | $-0.512$ | $0.60914$ | $[-0.05554, +0.03258]$ | $1.98\times$ |
| **Diff $I(\text{Death})$ (Chase - Setting)** | $-0.01479$ | $-0.0070$ | $0.011531$ | $0.012300$ | $0.026027$ | $-0.568$ | $0.56991$ | $[-0.06589, +0.03630]$ | $2.26\times$ |
| **Diff Rate (Chase RRR - Setting CRR)** | $-0.00365$ | $-0.0414$ | $0.001423$ | $0.001480$ | $0.003123$ | $-1.170$ | $0.24250$ | $[-0.00979, +0.00248]$ | $2.19\times$ |
| **Diff DLI Slope ($\beta_{\text{DLI, chase}} - \beta_{\text{DLI, setting}}$)** | $\mathbf{-0.02781}$ | $-0.0539$ | $0.014970$ | $0.015705$ | $\mathbf{0.035608}$ | $\mathbf{-0.781}$ | $\mathbf{0.43498}$ | $[-0.09772, +0.04209]$ | $2.38\times$ |
| **Chase Total DLI Slope ($\beta_{\text{DLI, chase}}$)** | $\mathbf{+0.06720}$ | $+0.1147$ | $0.006610$ | $0.007304$ | $\mathbf{0.016536}$ | $\mathbf{+4.064}$ | $< \mathbf{0.0001}$ | $[+0.03474, +0.09967]$ | $2.50\times$ |

---

## 3. Corrected Interpretation of the DLI Slope Contrast

### 3.1 Linear Contrast Summary

The direct linear contrast testing the difference between innings types:

$$H_0: \beta_{\text{DLI, setting}} = \beta_{\text{DLI, chase}} \iff \gamma_6 = 0$$

yields:
- **Point Estimate ($\text{Chase} - \text{Setting}$):** $\Delta \hat{\beta} = \mathbf{-0.02781}$ ($\text{Setting} - \text{Chase} = \mathbf{+0.02781}$)
- **Match-Clustered Standard Error:** $\mathbf{0.035608}$
- **Clustered $t$-Statistic:** $\mathbf{-0.781}$
- **Two-Sided $p$-Value:** $\mathbf{0.43498} \approx \mathbf{0.435}$
- **95% Clustered Confidence Interval:** $\mathbf{[-0.09772, +0.04209]}$

### 3.2 Methodological Correction: Non-Significance vs. Equivalence

> [!WARNING]
> **Econometric Interpretation Correction**  
> A non-significant hypothesis test ($p = 0.435$) indicates **failure to reject equal slopes**. It does **NOT** establish equality, homogeneity, or practical equivalence. In statistical inference, absence of evidence is not evidence of absence.

1. **Permissible Magnitude of Differences:**  
   The estimated Setting DLI slope is $\hat{\beta}_{\text{DLI, setting}} = +0.09502$. The 95% confidence interval for the difference $[-0.09772, +0.04209]$ is wide relative to the point estimate:
   - At the lower bound ($-0.09772$), the data cannot rule out a true Chase DLI slope as low as:
     $$\beta_{\text{DLI, chase}} \approx 0.09502 - 0.09772 = \mathbf{-0.00270}$$
     which would correspond to an essentially flat, non-existent conditional hazard association in chasing innings.
   - At the upper bound ($+0.04209$), the data cannot rule out a true Chase DLI slope as high as:
     $$\beta_{\text{DLI, chase}} \approx 0.09502 + 0.04209 = \mathbf{+0.13711}$$
     which would represent a $44\%$ steeper conditional association in chasing than in setting.
   - Because the data permit both a zero slope and a substantially steeper slope in chasing, asserting that the two slopes are "equal" or "identical" is an econometric error. The cluster-robust precision is simply insufficient to distinguish between these substantively different states of nature.

2. **Equivalence Margin Protocol:**  
   We strictly refrain from introducing an equivalence margin retrospectively. If a formal equivalence test (such as Two One-Sided Tests / TOST) were to be considered in future research, its equivalence margin $[-\Delta_0, +\Delta_0]$ must be:
   - Formulated and justified independently on substantive cricket-domain and operational grounds;
   - Specified strictly *a priori* (prior to viewing the estimation results);
   - Never chosen post-hoc to conveniently enclose the empirical confidence interval.

---

## 4. Joint Match-Clustered Wald Test of the Five Control Interactions & Numerical Stability Audit

Rather than relying on five individual $t$-tests to evaluate whether control relationships differ across innings, we performed a formal **joint Wald test** on all five control interaction terms simultaneously.

### 4.1 Joint Null Hypothesis and Restriction Matrix

Let $\gamma = (\gamma_1, \gamma_2, \gamma_3, \gamma_4, \gamma_5)^T$ denote the vector of interaction coefficients for the five controls:
$$H_0: \begin{pmatrix} \gamma_1 \\ \gamma_2 \\ \gamma_3 \\ \gamma_4 \\ \gamma_5 \end{pmatrix} = \begin{pmatrix} \beta_{W_{\text{hand}} \times \text{Chase}} \\ \beta_{B_{\text{rem}} \times \text{Chase}} \\ \beta_{\text{PP} \times \text{Chase}} \\ \beta_{\text{Death} \times \text{Chase}} \\ \beta_{\text{Rate} \times \text{Chase}} \end{pmatrix} = \begin{pmatrix} 0 \\ 0 \\ 0 \\ 0 \\ 0 \end{pmatrix} \quad \text{vs.} \quad H_1: \gamma \neq 0$$

Using the $5 \times 14$ selection matrix $R$, the restriction vector is $r = R \hat{\beta}$ and the restriction covariance is $V_R = R V_{\text{cluster}} R^T$. The joint Wald statistic is:
$$W = r^T V_R^{-1} r \sim \chi^2(q), \quad q = 5$$
And the small-sample $F$-equivalent is:
$$F = \frac{W}{q} \sim F(q, G - 1), \quad q = 5, \; G - 1 = 743$$

### 4.2 Standardized Scaling Transformation & Numerical Stability Verification

To address the elevated condition number of the unscaled restriction covariance submatrix ($\kappa(V_R) = 8238.45$), we evaluated the matrix under an explicit **correlation-standardized scaling transformation**:

$$D = \text{diag}\left(\frac{1}{\text{SE}(r_1)}, \dots, \frac{1}{\text{SE}(r_5)}\right) = \text{diag}\left(\frac{1}{\sqrt{[V_R]_{11}}}, \dots, \frac{1}{\sqrt{[V_R]_{55}}}\right)$$

Under this transformation:
- The scaled restrictions are $r^* = D r$ (standardized to unit estimated variance).
- The scaled covariance matrix is $V_R^* = D V_R D$, which corresponds exactly to the empirical correlation matrix of the restriction estimators.
- Analytically, the Wald statistic is scale-invariant: $W^* = (r^*)^T (V_R^*)^{-1} r^* = r^T D (D V_R D)^{-1} D r = r^T V_R^{-1} r = W$.

#### Numerical Comparison (Unscaled vs. Standardized Scaling)

| Diagnostic / Metric | Unscaled Raw Submatrix ($V_R$) | Standardized Correlation ($V_R^* = D V_R D$) | Invariance & Stability Assessment |
|:---|:---:|:---:|:---|
| **Condition Number ($\kappa$)** | $8238.45$ | $\mathbf{9.3663}$ | $\kappa < 10.0$ confirms excellent conditioning in scale-free space |
| **Minimum Eigenvalue ($\lambda_{\min}$)** | $9.8189 \times 10^{-8}$ | $\mathbf{0.218439}$ | Well separated from zero |
| **Maximum Eigenvalue ($\lambda_{\max}$)** | $8.0893 \times 10^{-4}$ | $\mathbf{2.045959}$ | Tightly bounded spectrum |
| **Numerical Rank** | $5$ (out of $5$) | $\mathbf{5}$ (out of $5$) | Full column rank; zero rank deficiency |
| **Joint Wald $\chi^2$ Statistic ($W$)** | $7.202027$ | $\mathbf{7.202027}$ | Absolute diff: $\mathbf{8.88 \times 10^{-16}}$ (exact machine epsilon) |
| **Finite-Sample $F$-Statistic ($F$)** | $1.440405$ | $\mathbf{1.440405}$ | Identical across scalings |
| **$p$-Value ($F(5, 743)$)** | $0.20747$ | $\mathbf{0.20747}$ | Identical across scalings |
| **Statistical Decision ($\alpha = 0.05$)** | Fail to Reject | **Fail to Reject** | Decision unchanged |

> [!NOTE]
> **Resolution of Numerical Conditioning**  
> We do not describe the matrix as numerically stable merely because it is full rank. The standardized scaling transformation demonstrates that the elevated condition number ($8238.45$) was entirely an artifact of disparate measurement units across variables (specifically, legal balls remaining $B_{\text{rem}} \in [0, 119]$ whose estimator variance is $\approx 2.6 \times 10^{-7}$ versus binary phase indicators whose estimator variances are $\approx 5.0 \times 10^{-4}$ to $6.8 \times 10^{-4}$). In correlation-standardized scale, the condition number is $\kappa = 9.37 < 10.0$, and the recomputed Wald statistic is invariant within $8.88 \times 10^{-16}$. There is no material numerical instability.

Persisted in [joint_control_wald_test.csv](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/research/R1_1_1_TARGETED_VERIFICATION/joint_control_wald_test.csv).

---

## 5. Reassessment of the Pooled-Model Interpretation

Based on the linear contrast test and the joint control interaction test, we rigorously delineate the statistical interpretation of the observational regression:

### 5.1 Four Critical Methodological Distinctions

1. **Does evidence support a difference in DLI slopes?**  
   **No.** The empirical contrast yields $t = -0.781$ with $p = 0.435$. The sample does not contain statistically detectable evidence of a difference in DLI slopes between chasing and setting. However, as established in Section 3, this failure to reject cannot rule out meaningful differences due to the wide confidence interval ($[-0.098, +0.042]$).

2. **Does evidence support common control relationships?**  
   **The sample does not reject common controls.** The joint Wald test yields $W = 7.2020$ with $p = 0.206$. There is no joint statistical evidence that the baseline control variables ($W_{\text{hand}}, B_{\text{rem}}, I(\text{PP}), I(\text{Death}), \text{Rate}$) exhibit different slopes across innings. Again, this is a failure to reject; it does not prove identical cricket dynamics.

3. **Can the original pooled coefficient be retained as a descriptive summary?**  
   **Yes, as a pooled conditional association under the original regression specification.**  
   Under the original pooled specification (which imposes common slopes on controls and DLI), the estimated coefficient:
   $$\hat{\beta}_{\text{DLI}} = +0.063820 \quad (\text{Clustered SE} = 0.010297, t = 6.198, p < 0.0001)$$
   represents the pooled conditional linear association between DLI and forward wicket hazard, holding constant the included covariates.  
   - We **qualify** that in multiple regression with covariates, the pooled coefficient is not necessarily a simple sample-weighted average of the separate subgroup slopes; rather, it reflects a conditional projection weighted by residual subpopulation regressor variances.
   - We **do not claim** that it is a minimum-variance estimator or an optimal estimator in the presence of potential parameter heterogeneity, as that requires strong homoskedasticity and parameter invariance assumptions that are not mathematically established here.
   - We strictly **avoid causal language**: $\hat{\beta}_{\text{DLI}}$ measures an observational conditional association, not a causal "effect" or "escalation rate."

4. **Is the evidence sufficient to call it a structural "common-effect estimate"?**  
   **No.**  
   Labeling $\hat{\beta}_{\text{DLI}}$ a "common-effect estimate" implies that there exists a single structural invariant parameter $\beta$ governing match leverage identically across both game contexts, and that pooling data introduces zero aggregation bias. Failure to reject an interaction ($p = 0.435$) does **not** prove the absence of aggregation bias. Because the setting and chasing DLI formulas are mathematically distinct by design (Setting relies on phase-based run accumulation and progress functions; Chasing relies on required run rates and terminal runway), the pooled model must be described strictly as a **pooled conditional association**, not a verified structural common effect.

---

## 6. Comprehensive Comparison Across Three Regression Specifications

| Metric / Parameter | Spec A: Original Pooled Model | Spec B: DLI-Only Interaction | Spec C: Fully Interacted Model |
|:---|:---:|:---:|:---:|
| **Control Covariates Slope Assumption** | Restricted (Equal across innings) | Restricted (Equal across innings) | **Unrestricted (Free by innings)** |
| **Setting DLI Slope ($\hat{\beta}_{\text{setting}}$)** | $+0.063820$ (pooled) | $+0.062024$ | $\mathbf{+0.09502}$ |
| Setting DLI Clustered SE | $0.010297$ | $0.012586$ | $0.030980$ |
| Setting DLI Clustered $t$-stat | $+6.198$ | $+4.928$ | $+3.067$ |
| Setting DLI $p$-value | $< 0.0001$ | $< 0.0001$ | $0.00224$ |
| **Chasing DLI Slope ($\hat{\beta}_{\text{chase}}$)** | $+0.063820$ (pooled) | $+0.065487$ | $\mathbf{+0.06720}$ |
| Chasing DLI Clustered SE | $0.010297$ | $0.014299$ | $0.016536$ |
| Chasing DLI Clustered $t$-stat | $+6.198$ | $+4.580$ | $+4.064$ |
| Chasing DLI $p$-value | $< 0.0001$ | $< 0.0001$ | $< 0.0001$ |
| **Slope Difference ($\hat{\beta}_{\text{chase}} - \hat{\beta}_{\text{setting}}$)** | $0$ (imposed by restriction) | $\mathbf{+0.003463}$ | $\mathbf{-0.02781}$ |
| Clustered SE of Difference | N/A | $0.014302$ | $0.035608$ |
| Clustered $t$-stat of Difference | N/A | $+0.242$ | $\mathbf{-0.781}$ |
| **Two-Sided $p$-value of Difference** | N/A | $\mathbf{0.80916}$ | $\mathbf{0.43498}$ |
| **95% Clustered CI of Difference** | N/A | $[-0.02462, +0.03154]$ | $\mathbf{[-0.09772, +0.04209]}$ |
| **Joint Control Interaction Test ($W, p$)** | N/A (imposed) | N/A (imposed) | $\mathbf{W = 7.202, p = 0.206}$ |
| Overall Model $R^2$ | $0.00767$ | $0.00767$ | $0.00778$ |
| Sample Size ($N$) | $159,225$ | $159,225$ | $159,225$ |
| Match Clusters ($G$) | $744$ | $744$ | $744$ |

---

## 7. Documentation Correction in Conditioning Diagnostics

In response to forensic review feedback, `regression_conditioning_diagnostics.csv` has been corrected to eliminate ambiguity between variable-level and matrix-level diagnostics:

### 7.1 Restructuring Details
- **Previous Ambiguity:** Singular values were previously displayed on the same row as individual covariate VIFs, which could inadvertently suggest that singular value $j$ corresponded to covariate $j$.
- **Corrected Architecture:** The diagnostic table now cleanly separates diagnostics into distinct sections:
  1. **Section A (Variable-Level):** Evaluates Variance Inflation Factors ($\text{VIF}$) for each specific covariate to detect multicollinearity. All singular value fields are left empty.
  2. **Section B (Matrix-Level Spectrum):** Reports the singular value components ($\sigma_1, \dots, \sigma_7$) of the full design matrix $X$. Covariate VIF fields are left empty.
  3. **Section C (Matrix-Level Conditioning):** Reports the matrix condition numbers ($\kappa$) under both raw and standardized column scalings.

### 7.2 Corrected Diagnostic Table

| Diagnostic Level | Diagnostic Type | Variable / Component Name | VIF Factor | Collinearity / Conditioning Status | Singular Value (Unscaled) | Singular Value (Scaled) | Interpretation Note |
|:---|:---|:---|:---:|:---|:---:|:---:|:---|
| **Variable-Level** | Variance Inflation Factor (VIF) | `Intercept` | $1.0000$ | Low Multicollinearity (VIF < 5) | — | — | Evaluates multicollinearity of specific covariate |
| **Variable-Level** | Variance Inflation Factor (VIF) | `W_hand` | $4.6824$ | Low Multicollinearity (VIF < 5) | — | — | Evaluates multicollinearity of specific covariate |
| **Variable-Level** | Variance Inflation Factor (VIF) | `B_rem` | $7.6213$ | Moderate Multicollinearity (5 $\le$ VIF < 10) | — | — | Evaluates multicollinearity of specific covariate |
| **Variable-Level** | Variance Inflation Factor (VIF) | `is_PP` | $3.8982$ | Low Multicollinearity (VIF < 5) | — | — | Evaluates multicollinearity of specific covariate |
| **Variable-Level** | Variance Inflation Factor (VIF) | `is_Death` | $2.5157$ | Low Multicollinearity (VIF < 5) | — | — | Evaluates multicollinearity of specific covariate |
| **Variable-Level** | Variance Inflation Factor (VIF) | `Rate` | $2.5133$ | Low Multicollinearity (VIF < 5) | — | — | Evaluates multicollinearity of specific covariate |
| **Variable-Level** | Variance Inflation Factor (VIF) | `DLI` | $\mathbf{5.7933}$ | Moderate Multicollinearity (5 $\le$ VIF < 10) | — | — | Evaluates multicollinearity of specific covariate |
| **Matrix-Level** | Singular Value Component | `Singular_Value_Component_1` | — | Matrix Conditioning Spectrum | $29,531.13$ | $754.98$ | Singular value component 1 of design matrix X |
| **Matrix-Level** | Singular Value Component | `Singular_Value_Component_2` | — | Matrix Conditioning Spectrum | $2,554.39$ | $426.22$ | Singular value component 2 of design matrix X |
| **Matrix-Level** | Singular Value Component | `Singular_Value_Component_3` | — | Matrix Conditioning Spectrum | $744.67$ | $399.03$ | Singular value component 3 of design matrix X |
| **Matrix-Level** | Singular Value Component | `Singular_Value_Component_4` | — | Matrix Conditioning Spectrum | $233.26$ | $323.73$ | Singular value component 4 of design matrix X |
| **Matrix-Level** | Singular Value Component | `Singular_Value_Component_5` | — | Matrix Conditioning Spectrum | $134.21$ | $264.26$ | Singular value component 5 of design matrix X |
| **Matrix-Level** | Singular Value Component | `Singular_Value_Component_6` | — | Matrix Conditioning Spectrum | $84.36$ | $125.38$ | Singular value component 6 of design matrix X |
| **Matrix-Level** | Singular Value Component | `Singular_Value_Component_7` | — | Matrix Conditioning Spectrum | $38.06$ | $115.48$ | Singular value component 7 of design matrix X |
| **Matrix-Level** | Matrix Condition Number | `Full_Design_Matrix_Unscaled_Kappa` | — | Matrix Conditioning (Unscaled) | $\mathbf{775.84}$ | — | Ratio $s_{\max} / s_{\min} = 775.84$ (dominated by natural unit scales) |
| **Matrix-Level** | Matrix Condition Number | `Full_Design_Matrix_Scaled_Kappa` | — | Well-Conditioned (Scaled) | — | $\mathbf{6.54}$ | Ratio $s_{\max} / s_{\min} = 6.54 < 10$ (well-conditioned) |

---

## 8. Canonical Integrity and Regression Test Suite

### 8.1 Canonical File Hash Verification (13/13 Bitwise Exact)

All 13 canonical datasets were verified pre- and post-execution using SHA-256 bitwise comparison. Zero modifications occurred to any canonical file:

| File Canonical Path | Status | Verification Check |
|:---|:---:|:---:|
| `data/data_pack.zip.zip` | **MATCH** | 100% Bitwise Exact |
| `data/extracted/ball_by_ball.csv` | **MATCH** | 100% Bitwise Exact |
| `data/extracted/matches.csv` | **MATCH** | 100% Bitwise Exact |
| `data/extracted/competitions.csv` | **MATCH** | 100% Bitwise Exact |
| `data/extracted/teams.csv` | **MATCH** | 100% Bitwise Exact |
| `data/extracted/playing_eleven.csv` | **MATCH** | 100% Bitwise Exact |
| `data/extracted/competition_team_player_mapping.csv` | **MATCH** | 100% Bitwise Exact |
| `data/enriched/pilot/enriched_ball_by_ball_pilot.csv` | **MATCH** | 100% Bitwise Exact |
| `data/enriched/full/enriched_ball_by_ball_full.csv` | **MATCH** | 100% Bitwise Exact |
| `data/processed/m5_3/match_state_full.csv` | **MATCH** | 100% Bitwise Exact |
| `data/processed/m5_3/match_state_validation_summary.csv` | **MATCH** | 100% Bitwise Exact |
| `data/processed/m5_3/match_state_exclusion_register.csv` | **MATCH** | 100% Bitwise Exact |
| `data/processed/m5_3/match_state_match_summary.csv` | **MATCH** | 100% Bitwise Exact |

### 8.2 Targeted Test Suite Status

The verification test suite was executed in `RRScoutIQenv`:
- `pytest tests/r1_1_1_targeted_verification/test_r1_1_1_verification.py -v`:
  - `test_clustered_se_inflation_ratio`: **PASSED**
  - `test_exact_6_ball_window_bounds`: **PASSED**
  - `test_forensic_csv_deliverables_exist`: **PASSED**
  - `test_sensitivity_interaction_and_conditioning`: **PASSED**
  - `test_fully_interacted_slope_contrast`: **PASSED**
  - `test_joint_control_wald_test`: **PASSED**
- **Result:** **6 passed in 5.63s** (Exit code 0).

---

## 9. Compliance and Governance Sign-Off

### 9.1 Strict Governance Checklist
- [x] **Corrected Pooled DLI Coefficient Interpretation:** Defined strictly as a pooled conditional association under the original regression specification; qualified that it is not necessarily a simple sample-weighted average; eliminated unproven minimum-variance claims; avoided causal language.
- [x] **Verified Joint Wald Covariance Stability:** Documented standardized diagonal scaling ($D = \text{diag}(1/\text{SE})$); proved condition number drops to $\kappa = 9.37 < 10.0$ in scale-free space; verified full rank ($5/5$) and machine-epsilon invariance ($|dW| = 8.88 \times 10^{-16}$).
- [x] **Interpretation of DLI Contrast Corrected:** Explicitly stated that non-significance ($p = 0.435$) is failure to reject, not proof of equality. Stated that the confidence interval $[-0.098, +0.042]$ permits both a flat slope and a $44\%$ steeper slope in chasing. Refrained from retrospective equivalence margin specification.
- [x] **Joint Match-Clustered Wald Test Executed:** Evaluated $H_0: \gamma = 0$ across all 5 control interactions ($W = 7.2020, p = 0.20604; F = 1.4404, p = 0.20747$).
- [x] **Zero Methodology Alterations:** No approved M3 mathematical formulas, parameters, or clamp limits modified.
- [x] **Zero Production Code / Data Changes:** Canonical datasets untouched (13/13 SHA-256 match).
- [x] **No Performance Ratings / Rankings / Draft Boards:** Strictly validation and econometric research.
- [x] **Milestone Status Maintained:** Marked as **EMPIRICAL SUPPORT WITH DOCUMENTED LIMITATIONS**; halted for human review without premature approval.
