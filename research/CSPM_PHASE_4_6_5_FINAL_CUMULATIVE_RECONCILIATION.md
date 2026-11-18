# RR ScoutIQ — Phase 4.6.5: Final Cumulative Impact Figure Reconciliation

**Document Reference**: `research/CSPM_PHASE_4_6_5_FINAL_CUMULATIVE_RECONCILIATION.md`  
**Author**: RR ScoutIQ Statistical Governance & Audit Group  
**Scope**: Full investigation and resolution of the $+1,585$ cumulative impact figure discrepancy  
**Status**: APPROVED & FINALIZED  
**Evaluation Cohort**: Chronological Split (Training: 2008–2020, $N = 431$ fixtures; Testing: 2021–2024, $N = 299$ fixtures, $66,457$ legal deliveries)  
**Resampling Specifications**: $B = 5,000$ Match-Clustered Bootstrap Iterations (Seed 42)  

---

## 1. Executive Summary & Reconciliation Mandate

In Phase 4.6.4 (`research/CSPM_PHASE_4_6_4_EFFECT_ESTIMATE_RECONCILIATION.md`), the descriptive cumulative runs over context for the Top 5 Batters cohort were reconstructed player-by-player:
- **DLI Top 5 Batters**: $+1,477.12$ runs over context (across $4,167$ legal deliveries)
- **CSPM Top 5 Batters**: $+664.49$ runs over context (across $2,479$ legal deliveries)
- **Exact Arithmetic Difference ($\text{DLI} - \text{CSPM}$)**:
  $$\Delta_{\text{cumulative}} = 1,477.12 - 664.49 = \mathbf{+812.63 \text{ runs over context}}$$

However, in qualitative prose sections of Phase 4.6.2, 4.6.3, and 4.6.4, a figure of **"+1,585 cumulative runs"** (and $+1,760$ for Top 10) was cited.

This audit:
1. Traced the provenance and origin of the $+1,585$ figure.
2. Evaluated whether it corresponded to an alternative metric, pressure slice, or unadjusted run total.
3. Verified the exact cumulative comparison against the canonical held-out dataset.
4. Corrected all research documents and reconciled all inconsistent references across the repository.

---

## 2. Investigation into the Origin of the +1,585 Figure

### Provenance Audit
A chronological audit across all trajectory transcripts and intermediate research reports revealed:
- **Phase 4.6 (`CSPM_PHASE_4_6_PLAYER_SELECTION_VALIDATION.md`)**: Correctly reported DLI $+1,477.1$ runs vs CSPM $+664.5$ runs, with a difference of **$-812.6$ runs** ($\text{CSPM} - \text{DLI}$) and bootstrap median of **$-811.3$ runs** (Table 4, line 118).
- **Phase 4.6.1 (`CSPM_PHASE_4_6_1_STATISTICAL_CORRECTION.md`)**: Correctly reported DLI $+1,477.1$ runs vs CSPM $+664.5$ runs, with an advantage of **$+812.6$ net runs** ($\text{DLI} - \text{CSPM}$) and bootstrap mean of **$-811.71$ runs** (line 27, line 80).
- **Phase 4.6.2 (`CSPM_PHASE_4_6_2_FINAL_INFERENCE_AUDIT.md`)**: At step 14871/14874, the markdown text table and prose were manually authored. Concurrently with the clerical errors on rate differences ($+3.32$, $+1.77$, $+8.30$, $-0.66$), the author introduced the errant figures **$+1,585$** (Top 5) and **$+1,760$** (Top 10).

### Evaluation of Alternative Hypotheses
We tested whether $+1,585$ could have arisen from an alternative canonical metric or sub-cohort on the $66,457$ test deliveries:

| Hypothesis / Metric Candidate | DLI Cohort | CSPM Cohort | Observed Difference ($\text{DLI} - \text{CSPM}$) | Matches $+1,585$? |
| :--- | :---: | :---: | :---: | :---: |
| **1. Net Runs over Context (Canonical)** | **$+1,477.12$** | **$+664.49$** | **$+812.63$** | **NO** ($\mathbf{+812.63}$) |
| **2. Total Delivery Runs (Raw)** | $7,106$ | $4,116$ | $+2,990$ | **NO** |
| **3. Total Batter Runs (Raw)** | $7,031$ | $4,087$ | $+2,944$ | **NO** |
| **4. Runs under DLI Pressure ($\text{Tier} \ge \text{Med}$)** | $5,026$ | $3,510$ | $+1,516$ | **NO** (Close, but $\ne 1585$) |
| **5. Runs under CSPM Pressure ($\text{BPS} \ge 60$)** | $1,728$ | $1,165$ | $+563$ | **NO** |
| **6. Legal Delivery Exposure Volume** | $4,167$ | $2,479$ | $\mathbf{+1,688 \text{ balls}}$ | **NO** (Close: $1,688$) |

### Finding
The figure $+1,585$ **does not correspond to any reproducible metric or slice in the canonical data**. It was a clerical drafting artifact—likely a cognitive conflation between the delivery volume gap ($+1,688$ balls), the raw pressure run gap ($+1,516$ runs), and DLI's total context runs ($+1,477$ runs). Similarly, the $+1,760$ figure for Top 10 had no basis in data (the true Top 10 cumulative context difference is **$+381.49$ runs**).

---

## 3. Verified Canonical Cumulative Statistics

From the canonical match state records (`data/processed/m5_3/match_state_full.csv`), held-out test fixtures ($2021$–$2024$, $N = 299$), and frozen rankings (`scratch/train_only_*`):

### Top 5 Batters Cumulative Comparison
- **DLI Top 5 Batters**:
  - Deliveries Faced: **$4,167$ legal balls**
  - Context Value-Add Runs: **$+1,477.12$ runs**
  - Component Players: Suryakumar Yadav ($+189.77$), Travis Head ($+166.53$), Yashasvi Jaiswal ($+117.39$), Sanju Samson ($+140.42$), Abhishek Sharma ($+863.02$)
- **CSPM Top 5 Batters**:
  - Deliveries Faced: **$2,479$ legal balls**
  - Context Value-Add Runs: **$+664.49$ runs**
  - Component Players: Yashasvi Jaiswal ($+117.39$), Suryakumar Yadav ($+189.77$), Andre Russell ($+21.86$), Nicholas Pooran ($+127.22$), Tim David ($+208.26$)
- **Canonical Cumulative Difference**:
  $$\Delta_{\text{cumulative, Top 5}} = 1,477.12 - 664.49 = \mathbf{+812.63 \text{ runs over context in favor of DLI}}$$
- **Bootstrap Resampling ($B = 5,000$ Iterations, Seed 42)**:
  - Mean Paired Difference ($\text{DLI} - \text{CSPM}$): **$+811.71$ runs**
  - Median Paired Difference: **$+808.69$ runs**
  - 95% Percentile Confidence Interval: **$[+346.02, +1,298.00]$ runs**

### Top 10 Batters Cumulative Comparison
- **DLI Top 10 Batters**: $6,730$ legal balls, **$+2,293.41$ runs over context**
- **CSPM Top 10 Batters**: $6,635$ legal balls, **$+1,911.92$ runs over context**
- **Canonical Cumulative Difference**:
  $$\Delta_{\text{cumulative, Top 10}} = 2,293.41 - 1,911.92 = \mathbf{+381.49 \text{ runs over context in favor of DLI}}$$
- **Bootstrap Resampling ($B = 5,000$ Iterations, Seed 42)**:
  - Mean Paired Difference ($\text{DLI} - \text{CSPM}$): **$+378.96$ runs**
  - Median Paired Difference: **$+378.90$ runs**
  - 95% Percentile Confidence Interval: **$[+81.37, +672.33]$ runs**

---

## 4. Repository-Wide Correction and Reconciliation

All occurrences of the errant $+1,585$ and $+1,760$ figures were searched and purged across the research repository:

1. **`research/CSPM_PHASE_4_6_2_FINAL_INFERENCE_AUDIT.md`**:
   - Line 31: Replaced `cumulative net runs ($+1,585$ runs for Top 5; $+1,760$ runs for Top 10)` with `cumulative net runs ($+812.63$ runs for Top 5; $+381.49$ runs for Top 10)`.
   - Line 162: Replaced `\Delta_{\text{cumulative}} = +1,585` with `\Delta_{\text{cumulative}} = +812.63 \text{ net runs over context in favor of DLI}`.
2. **`research/CSPM_PHASE_4_6_3_FINAL_CORRECTION.md`**:
   - Line 81: Replaced `cumulative volume ($+1,585$ runs for Top 5)` with `cumulative volume ($+812.63$ runs over context for Top 5; $+381.49$ for Top 10)`.
3. **`research/CSPM_PHASE_4_6_4_EFFECT_ESTIMATE_RECONCILIATION.md`**:
   - Line 213: Replaced `cumulative runs for Top 5 ($+1,585$)` with `cumulative runs over context ($+812.63$ for Top 5; $+381.49$ for Top 10)`.
4. **Verification**: A repository-wide regex search confirmed **zero remaining occurrences** of $+1,585$ or $+1,760$.

---

## 5. Comprehensive Summary of Authoritative Out-of-Sample Results

Below is the definitive, cross-reconciled reference table for all Phase 4.6 evaluation metrics on the unseen test set ($2021$–$2024$):

### Primary Rate Estimands (Per 100 Legal Balls)
*Direction: $\Delta = \text{DLI} - \text{CSPM}$ (Positive = DLI Superior)*

| Estimand | DLI Rate | CSPM Rate | Observed Diff ($\hat{\Delta}$) | Bootstrap Mean ($\bar{\Delta}^*$) | 95% Bootstrap CI | Unadjusted $p$ (plus-one) | Holm-Adjusted $p$ ($\tilde{p}$) | Significant ($\alpha = 0.05$)? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Top 10 Batters (Runs/100b)** | $34.08$ | $28.82$ | **$+5.26$** | **$+5.22$** | $[+1.13, +9.38]$ | $0.0132$ | **$0.0528$** | **NO** |
| **Top 10 Bowlers (Saved/100b)** | $1.35$ | $-1.02$ | **$+2.36$** | **$+2.38$** | $[-0.36, +5.28]$ | $0.0900$ | **$0.2700$** | **NO** |
| **Top 5 Batters (Runs/100b)** | $35.45$ | $26.80$ | **$+8.64$** | **$+8.68$** | $[-1.78, +18.66]$ | $0.0968$ | **$0.2700$** | **NO** |
| **Top 5 Bowlers (Saved/100b)** | $7.95$ | $7.27$ | **$+0.68$** | **$+0.72$** | $[-3.18, +4.62]$ | $0.7179$ | **$0.7179$** | **NO** |

### Secondary Cumulative Impact Estimands (Total Runs over Context)
*Direction: $\Delta = \text{DLI} - \text{CSPM}$ (Positive = DLI Superior)*

| Estimand | DLI Total | CSPM Total | Observed Diff ($\Delta$) | Bootstrap Mean ($\bar{\Delta}^*$) | 95% Bootstrap CI | Statistical Finding |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Top 5 Batters (Cumulative Runs)** | $+1,477.12$ | $+664.49$ | **$+812.63$** | **$+811.71$** | $[+346.02, +1,298.00]$ | DLI Volume/Durability Superior |
| **Top 10 Batters (Cumulative Runs)** | $+2,293.41$ | $+1,911.92$ | **$+381.49$** | **$+378.96$** | $[+81.37, +672.33]$ | DLI Volume/Durability Superior |
| **Top 5 Bowlers (Cumulative Saved)** | $+259.47$ | $+272.87$ | **$-13.40$** | **$-12.53$** | $[-142.64, +119.75]$ | No Statistical Difference |
| **Top 10 Bowlers (Cumulative Saved)** | $+87.72$ | $-71.22$ | **$+158.94$** | **$+159.67$** | $[-25.45, +350.37]$ | No Statistical Difference |

---

## 6. Governance Verification

### Cryptographic Hashes (Byte-for-Byte Invariance)

```
================================================================================
CANONICAL REPOSITORY INTEGRITY VERIFICATION
================================================================================
Target File: data/processed/m5_3/match_state_full.csv
Expected SHA-256: CE7E9A2FD2B8487E2E0BFEBFF5B7B44FE39D63EE7B5B1FBC35C5E07238E2D9E4
Computed SHA-256: CE7E9A2FD2B8487E2E0BFEBFF5B7B44FE39D63EE7B5B1FBC35C5E07238E2D9E4
Status: EXACT MATCH (VERIFIED IMMUTABLE)

Target File: FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md
Expected SHA-256: 0E0A11F87622DBEED44C3D918F37C5C9DE2F2BE8B22AC180099B5ADD1B882A1D
Computed SHA-256: 0E0A11F87622DBEED44C3D918F37C5C9DE2F2BE8B22AC180099B5ADD1B882A1D
Status: EXACT MATCH (VERIFIED IMMUTABLE)
================================================================================
```

### Full Regression Suite Execution

All 52 unit and regression tests in `tests/cspm` and `tests/m5_5b_4_3_8` executed and passed cleanly:

```
============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0
rootdir: C:\Users\rithv\OneDrive\Documents\Desktop\RR_ScoutIQ
plugins: anyio-4.10.0, asyncio-1.4.0
asyncio: mode=Mode.STRICT, debug=False
collected 52 items

tests\cspm\test_chase_probability.py ...                                 [  5%]
tests\cspm\test_first_innings.py ....                                    [ 13%]
tests\cspm\test_leverage.py ...                                          [ 19%]
tests\cspm\test_outcome_model.py ...                                     [ 25%]
tests\cspm\test_pipeline.py ..                                           [ 28%]
tests\cspm\test_pressure_engine.py ..                                    [ 32%]
tests\cspm\test_venue_par.py .....                                       [ 42%]
tests\m5_5b_4_3_8\test_remediation_b4_3_8.py ........................... [ 94%]
...                                                                      [100%]

============================= 52 passed in 14.86s =============================
```

---

## 7. Final Strategic Recommendation

The single authorized recommendation across all governance phases remains unchanged:

> ### **`Retain DLI for selection and CSPM as a supplementary match-state diagnostic.`**
