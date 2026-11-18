# RR ScoutIQ — Phase 4.6.4: Cross-Phase Effect Estimate Reconciliation

**Document Reference**: `research/CSPM_PHASE_4_6_4_EFFECT_ESTIMATE_RECONCILIATION.md`  
**Author**: RR ScoutIQ Statistical Governance & Audit Group  
**Scope**: Full mathematical, programmatic, and clerical reconciliation across Phases 4.6.1, 4.6.2, and 4.6.3  
**Status**: APPROVED & FINALIZED  
**Evaluation Cohort**: Chronological Split (Training: 2008–2020, $N = 431$ fixtures; Testing: 2021–2024, $N = 299$ fixtures, $66,457$ legal deliveries)  
**Resampling Specifications**: $B = 5,000$ Match-Clustered Bootstrap Iterations (Seed 42)  

---

## 1. Executive Summary & Root Cause Analysis

A rigorous numerical audit was conducted to reconcile apparent discrepancies in the effect estimates reported between Phase 4.6.1 and Phases 4.6.2/4.6.3:

| Comparison (Rate Estimand) | Phase 4.6.1 Report ($\text{CSPM} - \text{DLI}$) | Phase 4.6.3 Table ($\text{DLI} - \text{CSPM}$) | Converted to $\text{CSPM} - \text{DLI}$ | Discrepancy |
| :--- | :---: | :---: | :---: | :---: |
| **Top 5 Batters: Runs / 100 Balls** | **$-8.68$** | $+8.30$ | **$-8.30$** | $+0.38$ |
| **Top 10 Batters: Runs / 100 Balls** | **$-5.22$** | $+3.32$ | **$-3.32$** | $+1.90$ |
| **Top 5 Bowlers: Saved / 100 Balls** | **$-0.72$** | $-0.66$ | **$+0.66$** | $+1.38$ |
| **Top 10 Bowlers: Saved / 100 Balls** | **$-2.38$** | $+1.77$ | **$-1.77$** | $+0.61$ |

### Root Cause Diagnosis

Through line-by-line programmatic inspection of `scratch/phase4_6_1_statistical_audit.py`, `scratch/phase4_6_1_reconciled_bootstrap.csv`, `scratch/phase4_6_2_audit_verify.py`, and the underlying canonical data, the root causes have been definitively identified:

1. **Sign Convention Inversion**:
   - Phase 4.6.1 defined the difference as $\Delta = \text{Metric}_{\text{CSPM}} - \text{Metric}_{\text{DLI}}$ (negative values indicate DLI outperformance).
   - Phase 4.6.2 flipped the definition to $\Delta = \text{Metric}_{\text{DLI}} - \text{Metric}_{\text{CSPM}}$ (positive values indicate DLI outperformance).
2. **Clerical Transcription / Drafting Error in Phase 4.6.2 Table**:
   - The bootstrap resamples ($B = 5,000$, Seed 42), tail counts, and p-values ($0.0132, 0.0900, 0.0968, 0.7179$) across all phases are **100% identical and derived from the same underlying simulation run**.
   - Specifically, for Top 10 Batters, the tail count was $32$ draws $\ge 0$ out of $5,000$, giving $p = 2 \times (1 + 32) / 5001 = 0.0132$. That tail count belongs strictly to the bootstrap distribution with **mean $-5.22$ and 95% CI $[-9.38, -1.13]$** ($\text{CSPM} - \text{DLI}$).
   - However, when constructing the markdown text table in `CSPM_PHASE_4_6_2_FINAL_INFERENCE_AUDIT.md`, the author manually transcribed corrupt values into the point estimate and CI columns:
     - Top 10 Batters: typed `+3.32` and `[+0.58, +6.02]` instead of `+5.26` (descriptive pooled) / `+5.22` (bootstrap mean) and `[+1.13, +9.38]`.
     - Top 10 Bowlers: typed `+1.77` and `[-0.38, +3.75]` instead of `+2.36` (descriptive pooled) / `+2.38` (bootstrap mean) and `[-0.36, +5.28]`.
     - Top 5 Batters: typed `+8.30` and `[-1.87, +18.66]` instead of `+8.64` (descriptive pooled) / `+8.68` (bootstrap mean) and `[-1.78, +18.66]`.
     - Top 5 Bowlers: typed `-0.66` instead of `+0.68` (descriptive pooled) / `+0.72` (bootstrap mean) and `[-3.18, +4.62]` (DLI actually saved *more* runs than CSPM: $7.95$ vs $7.27$, so $\text{DLI} - \text{CSPM}$ is positive, not negative).
3. **Estimand Integrity**:
   - The estimand is strictly the **pooled rate difference** ($\frac{\sum \text{Numerator}}{\sum \text{Denominator}} \times 100$).
   - The descriptive pooled rates match the bootstrap sample means within $\le 0.04$ runs/100 balls (pure Monte Carlo resampling variation).

---

## 2. Independent Descriptive Reconstruction (Player-by-Player)

Using the frozen player rankings (`scratch/train_only_*`) and the held-out test dataset ($2021$–$2024$, $N = 299$ matches, $66,457$ legal deliveries), all four primary rate estimands are reconstructed below.

### Estimand 1: Top 5 Batters — Runs over Context / 100 Balls

#### DLI Cohort (Top 5 Batters)
| Player ID | Canonical Name | Legal Balls Faced | Numerator (Runs over Context) | Individual Rate (r/100b) |
| :---: | :--- | :---: | :---: | :---: |
| 1699 | Suryakumar Yadav | 858 | $+189.77$ | $+22.12$ |
| 2367 | Travis Head | 563 | $+166.53$ | $+29.58$ |
| 6819 | Yashasvi Jaiswal | 598 | $+117.39$ | $+19.63$ |
| 2258 | Sanju Samson | 871 | $+140.42$ | $+16.12$ |
| 6281 | Abhishek Sharma | 1,277 | $+863.02$ | $+67.58$ |
| **Total** | **DLI Top 5 Pooled** | **4,167** | **$+1,477.12$** | **$+35.4480$** |

#### CSPM Cohort (Top 5 Batters)
| Player ID | Canonical Name | Legal Balls Faced | Numerator (Runs over Context) | Individual Rate (r/100b) |
| :---: | :--- | :---: | :---: | :---: |
| 6819 | Yashasvi Jaiswal | 598 | $+117.39$ | $+19.63$ |
| 1699 | Suryakumar Yadav | 858 | $+189.77$ | $+22.12$ |
| 1318 | Andre Russell | 139 | $+21.86$ | $+15.73$ |
| 3125 | Nicholas Pooran | 425 | $+127.22$ | $+29.93$ |
| 6396 | Tim David | 459 | $+208.26$ | $+45.37$ |
| **Total** | **CSPM Top 5 Pooled** | **2,479** | **$+664.49$** | **$+26.8048$** |

- **Descriptive Pooled Difference ($\text{DLI} - \text{CSPM}$)**: $35.4480 - 26.8048 = \mathbf{+8.6432 \text{ runs / 100 balls}}$
- **Descriptive Pooled Difference ($\text{CSPM} - \text{DLI}$)**: $26.8048 - 35.4480 = \mathbf{-8.6432 \text{ runs / 100 balls}}$
- **Bootstrap Mean ($\text{CSPM} - \text{DLI}$)**: **$-8.6801$** | **Bootstrap Median**: **$-8.7092$** | **95% CI**: $[-18.66, +1.78]$

---

### Estimand 2: Top 10 Batters — Runs over Context / 100 Balls

#### DLI Cohort (Top 10 Batters)
| Player ID | Canonical Name | Legal Balls Faced | Numerator (Runs over Context) | Individual Rate (r/100b) |
| :---: | :--- | :---: | :---: | :---: |
| 1699 | Suryakumar Yadav | 858 | $+189.77$ | $+22.12$ |
| 2367 | Travis Head | 563 | $+166.53$ | $+29.58$ |
| 6819 | Yashasvi Jaiswal | 598 | $+117.39$ | $+19.63$ |
| 2258 | Sanju Samson | 871 | $+140.42$ | $+16.12$ |
| 6281 | Abhishek Sharma | 1,277 | $+863.02$ | $+67.58$ |
| 1318 | Andre Russell | 139 | $+21.86$ | $+15.73$ |
| 5553 | Phil Salt | 678 | $+259.62$ | $+38.29$ |
| 838 | Glenn Maxwell | 149 | $+12.31$ | $+8.26$ |
| 813 | Jos Buttler | 1,138 | $+314.25$ | $+27.61$ |
| 6396 | Tim David | 459 | $+208.26$ | $+45.37$ |
| **Total** | **DLI Top 10 Pooled** | **6,730** | **$+2,293.41$** | **$+34.0774$** |

#### CSPM Cohort (Top 10 Batters)
| Player ID | Canonical Name | Legal Balls Faced | Numerator (Runs over Context) | Individual Rate (r/100b) |
| :---: | :--- | :---: | :---: | :---: |
| 6819 | Yashasvi Jaiswal | 598 | $+117.39$ | $+19.63$ |
| 1699 | Suryakumar Yadav | 858 | $+189.77$ | $+22.12$ |
| 1318 | Andre Russell | 139 | $+21.86$ | $+15.73$ |
| 3125 | Nicholas Pooran | 425 | $+127.22$ | $+29.93$ |
| 6396 | Tim David | 459 | $+208.26$ | $+45.37$ |
| 2258 | Sanju Samson | 871 | $+140.42$ | $+16.12$ |
| 6281 | Abhishek Sharma | 1,277 | $+863.02$ | $+67.58$ |
| 5553 | Phil Salt | 678 | $+259.62$ | $+38.29$ |
| 768 | Reeza Hendricks | 103 | $-21.27$ | $-20.65$ |
| 7897 | Namboori Tilak Varma | 1,227 | $+5.65$ | $+0.46$ |
| **Total** | **CSPM Top 10 Pooled** | **6,635** | **$+1,911.92$** | **$+28.8157$** |

- **Descriptive Pooled Difference ($\text{DLI} - \text{CSPM}$)**: $34.0774 - 28.8157 = \mathbf{+5.2617 \text{ runs / 100 balls}}$
- **Descriptive Pooled Difference ($\text{CSPM} - \text{DLI}$)**: $28.8157 - 34.0774 = \mathbf{-5.2617 \text{ runs / 100 balls}}$
- **Bootstrap Mean ($\text{CSPM} - \text{DLI}$)**: **$-5.2161$** | **Bootstrap Median**: **$-5.2245$** | **95% CI**: $[-9.38, -1.13]$

---

### Estimand 3: Top 5 Bowlers — Runs Saved / 100 Balls

#### DLI Cohort (Top 5 Bowlers)
| Player ID | Canonical Name | Legal Balls Bowled | Numerator (Runs Saved) | Individual Rate (saved/100b) |
| :---: | :--- | :---: | :---: | :---: |
| 781 | Sunil Narine | 579 | $+102.47$ | $+17.70$ |
| 8661 | Matheesha Pathirana | 349 | $-17.42$ | $-4.99$ |
| 4101 | Mitchell Santner | 741 | $+8.52$ | $+1.15$ |
| 2933 | Jasprit Bumrah | 873 | $+180.41$ | $+20.67$ |
| 19316 | Maheesh Theekshana | 723 | $-14.51$ | $-2.01$ |
| **Total** | **DLI Top 5 Pooled** | **3,265** | **$+259.47$** | **$+7.9469$** |

#### CSPM Cohort (Top 5 Bowlers)
| Player ID | Canonical Name | Legal Balls Bowled | Numerator (Runs Saved) | Individual Rate (saved/100b) |
| :---: | :--- | :---: | :---: | :---: |
| 781 | Sunil Narine | 579 | $+102.47$ | $+17.70$ |
| 4101 | Mitchell Santner | 741 | $+8.52$ | $+1.15$ |
| 2933 | Jasprit Bumrah | 873 | $+180.41$ | $+20.67$ |
| 19316 | Maheesh Theekshana | 723 | $-14.51$ | $-2.01$ |
| 3644 | Kuldeep Yadav | 837 | $-4.02$ | $-0.48$ |
| **Total** | **CSPM Top 5 Pooled** | **3,753** | **$+272.87$** | **$+7.2706$** |

- **Descriptive Pooled Difference ($\text{DLI} - \text{CSPM}$)**: $7.9469 - 7.2706 = \mathbf{+0.6763 \text{ runs saved / 100 balls}}$
- **Descriptive Pooled Difference ($\text{CSPM} - \text{DLI}$)**: $7.2706 - 7.9469 = \mathbf{-0.6763 \text{ runs saved / 100 balls}}$
- **Bootstrap Mean ($\text{CSPM} - \text{DLI}$)**: **$-0.7161$** | **Bootstrap Median**: **$-0.6899$** | **95% CI**: $[-4.62, +3.18]$

---

### Estimand 4: Top 10 Bowlers — Runs Saved / 100 Balls

#### DLI Cohort (Top 10 Bowlers)
| Player ID | Canonical Name | Legal Balls Bowled | Numerator (Runs Saved) | Individual Rate (saved/100b) |
| :---: | :--- | :---: | :---: | :---: |
| 781 | Sunil Narine | 579 | $+102.47$ | $+17.70$ |
| 8661 | Matheesha Pathirana | 349 | $-17.42$ | $-4.99$ |
| 4101 | Mitchell Santner | 741 | $+8.52$ | $+1.15$ |
| 2933 | Jasprit Bumrah | 873 | $+180.41$ | $+20.67$ |
| 19316 | Maheesh Theekshana | 723 | $-14.51$ | $-2.01$ |
| 152 | Ravindra Jadeja | 425 | $-28.10$ | $-6.61$ |
| 2876 | Axar Patel | 1,111 | $-103.33$ | $-9.30$ |
| 3644 | Kuldeep Yadav | 837 | $-4.02$ | $-0.48$ |
| 2417 | Akeal Hosein | 690 | $-2.39$ | $-0.35$ |
| 305 | Ravichandran Ashwin | 186 | $-33.90$ | $-18.23$ |
| **Total** | **DLI Top 10 Pooled** | **6,514** | **$+87.72$** | **$+1.3467$** |

#### CSPM Cohort (Top 10 Bowlers)
| Player ID | Canonical Name | Legal Balls Bowled | Numerator (Runs Saved) | Individual Rate (saved/100b) |
| :---: | :--- | :---: | :---: | :---: |
| 781 | Sunil Narine | 579 | $+102.47$ | $+17.70$ |
| 4101 | Mitchell Santner | 741 | $+8.52$ | $+1.15$ |
| 2933 | Jasprit Bumrah | 873 | $+180.41$ | $+20.67$ |
| 19316 | Maheesh Theekshana | 723 | $-14.51$ | $-2.01$ |
| 3644 | Kuldeep Yadav | 837 | $-4.02$ | $-0.48$ |
| 2417 | Akeal Hosein | 690 | $-2.39$ | $-0.35$ |
| 2876 | Axar Patel | 1,111 | $-103.33$ | $-9.30$ |
| 4722 | Rashid Khan | 647 | $-105.04$ | $-16.23$ |
| 7503 | Ravi Bishnoi | 612 | $-99.42$ | $-16.25$ |
| 305 | Ravichandran Ashwin | 186 | $-33.90$ | $-18.23$ |
| **Total** | **CSPM Top 10 Pooled** | **6,999** | **$-71.22$** | **$-1.0176$** |

- **Descriptive Pooled Difference ($\text{DLI} - \text{CSPM}$)**: $1.3467 - (-1.0176) = \mathbf{+2.3643 \text{ runs saved / 100 balls}}$
- **Descriptive Pooled Difference ($\text{CSPM} - \text{DLI}$)**: $-1.0176 - 1.3467 = \mathbf{-2.3643 \text{ runs saved / 100 balls}}$
- **Bootstrap Mean ($\text{CSPM} - \text{DLI}$)**: **$-2.3755$** | **Bootstrap Median**: **$-2.3666$** | **95% CI**: $[-5.28, +0.36]$

---

## 3. Authoritative Reconciled Primary Inference Table

This table provides the definitive, mathematically reconciled figures that must be cited in all RR ScoutIQ documentation. Both sign conventions are displayed to avoid future ambiguity.

### Orientation A: Conventional Direction ($\Delta = \text{DLI} - \text{CSPM}$)
*Positive values indicate DLI superiority.*

| Rank ($k$) | Primary Rate Estimand | Descriptive Pooled Diff ($\hat{\Delta}$) | Bootstrap Mean Diff ($\bar{\Delta}^*$) | 95% Bootstrap CI | Unadjusted $p$-value (plus-one) | Step Multiplier | Holm-Adjusted $p$-value ($\tilde{p}_{(k)}$) | Significant at $\alpha = 0.05$? |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | **Top 10 Batters**: Runs / 100 Balls | **$+5.26$** | **$+5.22$** | $[+1.13, +9.38]$ | **$0.0132$** | $4$ | **$0.0528$** | **NO** ($p \ge 0.05$) |
| **2** | **Top 10 Bowlers**: Saved / 100 Balls | **$+2.36$** | **$+2.38$** | $[-0.36, +5.28]$ | **$0.0900$** | $3$ | **$0.2700$** | **NO** |
| **3** | **Top 5 Batters**: Runs / 100 Balls | **$+8.64$** | **$+8.68$** | $[-1.78, +18.66]$ | **$0.0968$** | $2$ | **$0.2700$** | **NO** |
| **4** | **Top 5 Bowlers**: Saved / 100 Balls | **$+0.68$** | **$+0.72$** | $[-3.18, +4.62]$ | **$0.7179$** | $1$ | **$0.7179$** | **NO** |

### Orientation B: Implementation Direction ($\Delta = \text{CSPM} - \text{DLI}$)
*Negative values indicate DLI superiority.*

| Rank ($k$) | Primary Rate Estimand | Descriptive Pooled Diff ($\hat{\Delta}$) | Bootstrap Mean Diff ($\bar{\Delta}^*$) | 95% Bootstrap CI | Unadjusted $p$-value (plus-one) | Step Multiplier | Holm-Adjusted $p$-value ($\tilde{p}_{(k)}$) | Significant at $\alpha = 0.05$? |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | **Top 10 Batters**: Runs / 100 Balls | **$-5.26$** | **$-5.22$** | $[-9.38, -1.13]$ | **$0.0132$** | $4$ | **$0.0528$** | **NO** ($p \ge 0.05$) |
| **2** | **Top 10 Bowlers**: Saved / 100 Balls | **$-2.36$** | **$-2.38$** | $[-5.28, +0.36]$ | **$0.0900$** | $3$ | **$0.2700$** | **NO** |
| **3** | **Top 5 Batters**: Runs / 100 Balls | **$-8.64$** | **$-8.68$** | $[-18.66, +1.78]$ | **$0.0968$** | $2$ | **$0.2700$** | **NO** |
| **4** | **Top 5 Bowlers**: Saved / 100 Balls | **$-0.68$** | **$-0.72$** | $[-4.62, +3.18]$ | **$0.7179$** | $1$ | **$0.7179$** | **NO** |

---

## 4. Preservation of Substantive Findings

The resolution of the clerical transcription errors does not alter the substantive conclusions:

1. **Non-Significance Under Multiplicity Control**:  
   Every Holm-adjusted p-value remains $\ge 0.05$ ($\tilde{p}_{(1)} = 0.0528, \tilde{p}_{(2)} = 0.2700, \tilde{p}_{(3)} = 0.2700, \tilde{p}_{(4)} = 0.7179$). None of the four primary rate estimands achieve formal statistical significance at $\alpha = 0.05$.
2. **Directional Support Without Confirmatory Proof for Batters**:  
   DLI demonstrates a consistent directional rate advantage over CSPM ($+5.26$ runs/100b for Top 10; $+8.64$ runs/100b for Top 5) alongside massive playing-time survivor volume ($+812.63$ cumulative runs over context for Top 5; $+381.49$ for Top 10). However, statistical superiority is not formally confirmed after Holm correction ($p_{\text{adj}} = 0.0528$).
3. **No Statistically Significant Difference for Bowlers**:  
   Observed bowler rate differences ($+0.68$ runs saved/100b for Top 5, $p = 0.7179$; $+2.36$ runs saved/100b for Top 10, $p = 0.0900$) show no statistically significant difference between DLI and CSPM.
4. **Bowling Equivalence Not Established**:  
   Because no equivalence margin $\pm \delta$ was pre-specified in the protocol and the 95% CI spans $[-3.18, +4.62]$ runs/100b, formal statistical equivalence has not been established.

---

## 5. Governance & Repository Verification

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

All 52 tests in `tests/cspm` and `tests/m5_5b_4_3_8` executed and passed in $14.57$s:

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

============================= 52 passed in 14.57s =============================
```

---

## 6. Final Statement of Reproducibility and Citation Guidance

### Reproducibility Statement
The four primary rate estimands are **100% reproducible and mathematically verified**.
- The descriptive pooled differences on the held-out test data are:
  - Top 5 Batters: $\mathbf{+8.64 \text{ runs / 100 balls}}$ in favor of DLI ($-8.64$ for CSPM - DLI).
  - Top 10 Batters: $\mathbf{+5.26 \text{ runs / 100 balls}}$ in favor of DLI ($-5.26$ for CSPM - DLI).
  - Top 5 Bowlers: $\mathbf{+0.68 \text{ runs saved / 100 balls}}$ in favor of DLI ($-0.68$ for CSPM - DLI).
  - Top 10 Bowlers: $\mathbf{+2.36 \text{ runs saved / 100 balls}}$ in favor of DLI ($-2.36$ for CSPM - DLI).
- The bootstrap sample means from $B = 5,000$ iterations are $+8.68, +5.22, +0.72, +2.38$ (DLI - CSPM), matching the descriptive estimates within sampling error.

### Citation Guidance
When citing these figures in final project documentation, teams must cite:
1. **The Descriptive Pooled Rate Differences** ($+8.64, +5.26, +0.68, +2.36$ for DLI - CSPM), or the corresponding bootstrap sample means ($+8.68, +5.22, +0.72, +2.38$).
2. **The Correct 95% Bootstrap Percentile Confidence Intervals** (Top 10 Batters: $[+1.13, +9.38]$; Top 10 Bowlers: $[-0.36, +5.28]$; Top 5 Batters: $[-1.78, +18.66]$; Top 5 Bowlers: $[-3.18, +4.62]$).
3. **The Holm-Bonferroni Adjusted P-Values** ($0.0528, 0.2700, 0.2700, 0.7179$), noting that all comparisons fail to reach formal statistical significance after multiplicity control.
4. **The Unchanged Strategic Recommendation**:
   > ### **`Retain DLI for selection and CSPM as a supplementary match-state diagnostic.`**
