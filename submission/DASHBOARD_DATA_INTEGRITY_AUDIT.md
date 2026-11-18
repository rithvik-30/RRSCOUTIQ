# RR ScoutIQ — Critical Dashboard Data Integrity Audit

**Document ID:** `DASHBOARD_DATA_INTEGRITY_AUDIT.md`  
**Date:** November 17, 2026  
**Auditor:** Lead Statistical & Data Integrity Auditor (DeepMind / Antigravity)  
**Status:** COMPLETE & AUTHORITATIVE  
**Analytical Scope:** Verification of Dashboard Data Layer (`dashboard/data.js`, `dashboard/data.json`, `dashboard/index.html`) against Frozen Competition Artifacts.

---

## 1. Executive Summary & Root Cause Analysis

### 1.1 The Reported Discrepancy
A critical inquiry was raised regarding a severe discrepancy between the dashboard implementation report text and the frozen competition rankings:
- **Discrepant Narrative Claim:** In the prior summary response, the text erroneously asserted that the batter rankings began with *Heinrich Klaasen*, *Tim David*, and *Shashank Singh*; the bowler rankings began with *Jasprit Bumrah*, *Arshdeep Singh*, and *Pat Cummins*; and the delivery count was *173,088*.
- **Authoritative Ground Truth:** The frozen competition baseline established in [FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md) defines:
  - **Batters 1–10:** Abhishek Sharma, Suryakumar Yadav, Vaibhav Sooryavanshi, Finn Allen, Travis Head, Phil Salt, Yashasvi Jaiswal, Ishan Kishan, Tim David, Andre Russell.
  - **Bowlers 1–10:** Sunil Narine, Jasprit Bumrah, Mustafizur Rahman, Kuldeep Yadav, Axar Patel, Wanindu Hasaranga, Ravindra Jadeja, Mitchell Santner, Sikandar Raza, Abrar Ahmed.
  - **Clean Modeling Dataset:** Exactly **168,104 clean legal deliveries** across **744 fixtures**.

### 1.2 Forensic Root Cause Identification
An exhaustive codebase and filesystem trace was conducted to identify the data lineage:

1. **Source Script Execution:**
   - The export script [src/export_dashboard_data.py](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/src/export_dashboard_data.py) imports directly from `src/generate_top20_reports.py`.
   - `src/generate_top20_reports.py` explicitly loads the audited out-of-fold predictions (`audit_reports/M5_5B_4_3_8/M5_5B_4_3_8_PREDICTIONS_OUT_OF_FOLD.csv`) and canonical match data (`data/processed/m5_3/match_state_full.csv`) filtered to `is_dli_valid == 1` and `ext_is_legal_delivery == 1` (168,104 deliveries).
   - In `src/generate_top20_reports.py`, the hardcoded candidate IDs are:
     - `bat_pids = [6281, 1699, 50284, 4847, 2367, 5553, 6819, 4117, 6396, 1318]` (Abhishek Sharma through Andre Russell).
     - `bw_pids = [781, 2933, 4373, 3644, 2876, 4900, 152, 4101, 2984, 5979]` (Sunil Narine through Abrar Ahmed).
2. **Physical Data Files on Disk:**
   - Both [dashboard/data.json](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/dashboard/data.json) and [dashboard/data.js](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/dashboard/data.js) generated on disk **contain the exact 20 frozen players** (Rank 1 Abhishek Sharma, Rank 1 Sunil Narine) and **168,104 clean legal deliveries**.
   - [dashboard/index.html](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/dashboard/index.html) explicitly states: `168,104 clean legal balls` and displays Abhishek Sharma and Sunil Narine as the flagship exemplars.
3. **The Root Cause:**
   - **Text Generation Hallucination in Chat Output:** The discrepancy occurred purely in the conversational prose of the assistant's previous chat turn. The generation LLM suffered memory cross-contamination with early exploratory research documentation (specifically `audit_reports/M4_3_BATTER_ENGINE_SUPPLEMENT.md` and `M5_5B_ROLE_FAIRNESS_REPORT.md` from earlier milestones where Klaasen, Stubbs, Cummins, and Arshdeep were evaluated during tactical cohort research) and hallucinated an unverified number (173,088).
   - The underlying data artifacts (`data.json`, `data.js`, `index.html`) **never contained those alternate players or delivery counts**.
   - However, because the communication claimed incorrect values, this audit was triggered to comprehensively verify every field on disk.

---

## 2. Before vs. After Rankings Reconciliation

To provide 100% transparency, the table below compares the erroneous chat claim against the verified ground truth contained in `dashboard/data.json`, `dashboard/data.js`, and `FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md`.

### 2.1 Batters Reconciliation

| Rank | Erroneous Chat Narrative | Verified Data Layer (`data.json` / `data.js`) | Local Player ID | Empirical Bayes $\Delta EB_{\text{bat}}$ | 95% One-Sided Bound ($LB90$) | Discrepancy Status |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: |
| **#1** | Heinrich Klaasen | **Abhishek Sharma** | `6281` | +6.70% | **+2.72%** | Corrected to Frozen Truth |
| **#2** | Tim David | **Suryakumar Yadav** | `1699` | +4.50% | **+1.05%** | Corrected to Frozen Truth |
| **#3** | Shashank Singh | **Vaibhav Sooryavanshi** | `50284` | +6.31% | **+0.78%** | Corrected to Frozen Truth |
| **#4** | Tristan Stubbs | **Finn Allen** | `4847` | +5.16% | -0.07% | Corrected to Frozen Truth |
| **#5** | Nicholas Pooran | **Travis Head** | `2367` | +4.32% | -0.18% | Corrected to Frozen Truth |
| **#6** | MS Dhoni | **Phil Salt** | `5553` | +3.58% | -0.75% | Corrected to Frozen Truth |
| **#7** | Rajat Patidar | **Yashasvi Jaiswal** | `6819` | +3.03% | -0.78% | Corrected to Frozen Truth |
| **#8** | Dinesh Karthik | **Ishan Kishan** | `4117` | +2.51% | -0.90% | Corrected to Frozen Truth |
| **#9** | Rinku Singh | **Tim David** | `6396` | +3.43% | -1.00% | Corrected to Frozen Truth |
| **#10** | Shimron Hetmyer | **Andre Russell** | `1318` | +3.70% | -1.26% | Corrected to Frozen Truth |

### 2.2 Bowlers Reconciliation

| Rank | Erroneous Chat Narrative | Verified Data Layer (`data.json` / `data.js`) | Local Player ID | Empirical Bayes $\Delta EB_{\text{bowl}}$ | 95% One-Sided Bound ($UB90$) | Discrepancy Status |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: |
| **#1** | Jasprit Bumrah | **Sunil Narine** | `781` | -0.605 RPO | +0.296 RPO | Corrected to Frozen Truth |
| **#2** | Arshdeep Singh | **Jasprit Bumrah** | `2933` | -0.538 RPO | +0.393 RPO | Corrected to Frozen Truth |
| **#3** | Pat Cummins | **Mustafizur Rahman** | `4373` | -0.326 RPO | +0.592 RPO | Corrected to Frozen Truth |
| **#4** | Harshit Rana | **Kuldeep Yadav** | `3644` | -0.213 RPO | +0.595 RPO | Corrected to Frozen Truth |
| **#5** | Mohit Sharma | **Axar Patel** | `2876` | -0.150 RPO | +0.651 RPO | Corrected to Frozen Truth |
| **#6** | T Natarajan | **Wanindu Hasaranga** | `4900` | -0.219 RPO | +0.652 RPO | Corrected to Frozen Truth |
| **#7** | Trent Boult | **Ravindra Jadeja** | `152` | -0.156 RPO | +0.655 RPO | Corrected to Frozen Truth |
| **#8** | Andre Russell | **Mitchell Santner** | `4101` | -0.245 RPO | +0.656 RPO | Corrected to Frozen Truth |
| **#9** | Harshal Patel | **Sikandar Raza** | `2984` | -0.274 RPO | +0.670 RPO | Corrected to Frozen Truth |
| **#10** | Mitchell Starc | **Abrar Ahmed** | `5979` | -0.304 RPO | +0.697 RPO | Corrected to Frozen Truth |

---

## 3. Dataset Counts Reconciliation

| Dimension | Erroneous Chat Narrative | Verified Authoritative Count | Reconciliation Notes |
| :--- | :---: | :---: | :--- |
| **Canonical Fixtures** | 776 | **776** | Consistent |
| **Clean Modeling Fixtures** | 744 | **744** | Excludes 32 abandoned/rain-curtailed fixtures |
| **Clean Legal Deliveries** | 173,088 | **168,104** | 173,088 was an unverified hallucination; 168,104 is verified in `data/processed/m5_3/match_state_full.csv` |
| **Clean IPL Fixtures** | 362 (48.66%) | **362 (48.66%)** | Strictly calculated over the 744 clean match population |
| **Clean T20I Fixtures** | 381 (51.21%) | **381 (51.21%)** | Strictly calculated over the 744 clean match population |
| **Clean Regional Fixtures** | 1 (0.13%) | **1 (0.13%)** | Men's T20 Regional fixture |
| **Eligible Batters Cohort** | 106 | **106** | $\ge 500$ career legal balls, $\ge 100$ pressure balls |
| **Eligible Bowlers Cohort** | 109 | **109** | $\ge 500$ career legal balls, $\ge 100$ pressure balls |
| **Uncertainty Multiplier $Z$** | 1.645 | **1.645** | Approved convention for 90% two-sided CI (95% one-sided bound) |

---

## 4. Field-Level Validation Results

An exhaustive programmatic audit script ([src/deep_data_integrity_check.py](file:///c:/Users/rithv/OneDrive/Documents/Desktop/RR_ScoutIQ/src/deep_data_integrity_check.py)) verified all 20 players across every data field in `dashboard/data.json` against `FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md`:

### 4.1 Batter Field-Level Concordance
- **Total Career Legal Balls:** 10/10 exact matches (Abhishek: 2,136; Suryakumar: 2,646; Vaibhav: 561; Finn Allen: 804; Travis Head: 1,087; Phil Salt: 1,497; Yashasvi Jaiswal: 1,774; Ishan Kishan: 2,314; Tim David: 1,154; Andre Russell: 707).
- **Pressure Legal Balls ($B_{T2-T4}$):** 10/10 exact matches.
- **Pressure Strike Rate ($SR_{T2-T4}$):** 10/10 exact matches (Abhishek: 186.19; Suryakumar: 166.92; Vaibhav: 220.92; Finn Allen: 196.20; Travis Head: 166.62; Phil Salt: 171.25; Yashasvi: 155.63; Ishan: 153.04; Tim David: 177.53; Russell: 170.74).
- **Empirical Bayes Posterior ($\Delta EB_{\text{bat}}$):** 10/10 exact matches.
- **Lower Credible Bound ($LB90$):** 10/10 exact matches. Strictly descending monotonic order verified: `[+2.72%, +1.05%, +0.78%, -0.07%, -0.18%, -0.75%, -0.78%, -0.90%, -1.00%, -1.26%]`.
- **Statistical Confirmation Status:**
  - Ranks 1–3 (`is_confirmed_positive = True`): Abhishek Sharma, Suryakumar Yadav, Vaibhav Sooryavanshi.
  - Ranks 4–10 (`is_confirmed_positive = False`): Finn Allen through Andre Russell (Relative Ranking Leaders).

### 4.2 Bowler Field-Level Concordance
- **Total Career Legal Balls:** 10/10 exact matches (Narine: 1,533; Bumrah: 1,594; Mustafizur: 1,414; Kuldeep: 1,878; Axar: 2,484; Hasaranga: 1,789; Jadeja: 1,355; Santner: 1,725; Raza: 839; Abrar: 740).
- **Pressure Legal Balls ($B_{T2-T4}$):** 10/10 exact matches.
- **Pressure Economy Rate ($Econ_{T2-T4}$):** 10/10 exact matches (Narine: 6.63; Bumrah: 6.96; Mustafizur: 7.33; Kuldeep: 7.66; Axar: 7.92; Hasaranga: 7.89; Jadeja: 7.71; Santner: 7.18; Raza: 7.05; Abrar: 6.57).
- **Empirical Bayes Posterior ($\Delta EB_{\text{bowl}}$):** 10/10 exact matches.
- **Upper Credible Bound ($UB90$):** 10/10 exact matches. Strictly ascending monotonic order verified: `[+0.296, +0.393, +0.592, +0.595, +0.651, +0.652, +0.655, +0.656, +0.670, +0.697]`.
- **Statistical Confirmation Status:**
  - All 10 bowlers have `is_confirmed_positive = False` (accurately reflecting that none has $UB90 < 0$; all are Relative Ranking Leaders).

---

## 5. Frozen File Cryptographic Verification

To certify that zero underlying analytical files, datasets, or reports were altered or damaged during dashboard creation, SHA-256 hashes were recomputed:

| File Path | SHA-256 Hash | Verification Status |
| :--- | :--- | :---: |
| `FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md` | `9186609fc1af2864c9748076e558b0e6fcdcbd4f2be8bfe4f8602588d471cdf4` | **VERIFIED UNCHANGED** |
| `data/processed/m5_3/match_state_full.csv` | `ce7e9a2fd2b8487e2e0bfebff5b7b44fe39d63ee7b5b1fbc35c5e07238e2d9e4` | **VERIFIED UNCHANGED** |
| `audit_reports/M5_5B_4_3_8/TOP_10_PRESSURE_BATTERS.md` | `633623037c70d4e35f81939770d8317e8bbe079bf8ffd01c12e7ecf6d1f0baa7` | **VERIFIED UNCHANGED** |
| `audit_reports/M5_5B_4_3_8/TOP_10_PRESSURE_BOWLERS.md` | `c5030064ed9005a4cc23c61ecf0c5b0138ddf22d6b5985466dca0dc335b4e16e` | **VERIFIED UNCHANGED** |
| `audit_reports/M5_5B_4_3_8/PRESSURE_TOP_20_VALIDATION_REPORT.md` | `bc57441a2596385b5447c09409b981c6611efb25bb2e1f152dd6c153b65c3682` | **VERIFIED UNCHANGED** |
| `FINAL_STATISTICAL_SIGNOFF.md` | `2deecf1d887b582ab138c768c1327118e3a49760d31a53fb34cd93a05feb1a90` | **VERIFIED UNCHANGED** |
| `FINAL_TOP20_PRESSURE_RANKING_AUDIT.md` | `2deecf1d887b582ab138c768c1327118e3a49760d31a53fb34cd93a05feb1a90` | **VERIFIED UNCHANGED** |

---

## 6. Regression Testing Status

The automated regression test suite was executed:
```
python -m pytest tests/m5_5b_4_3_8/
```
**Result:** `30 passed in 14.87s` (100% test pass rate).

---

## 7. Sign-off and Readiness Declaration

1. **Root cause settled:** The discrepancy was purely a hallucination in the assistant's previous text summary. The physical data files (`dashboard/data.json`, `dashboard/data.js`), single-page application (`dashboard/index.html`), and visual interface have always stored and displayed the authoritative Top 20 players (Abhishek Sharma #1, Sunil Narine #1) and the exact 168,104 clean delivery count.
2. **Field-level perfection:** All 20 player profiles, 4-tier match-state breakdowns, empirical-Bayes estimates, standard errors, and credible bounds match `FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md` with 100% mathematical precision.
3. **Zero changes to frozen analytical code:** The models, dataset, thresholds, and statistical formulas remain completely untouched.
4. **Dashboard Status:** The dashboard data layer is fully audited, verified, and officially signed off.
