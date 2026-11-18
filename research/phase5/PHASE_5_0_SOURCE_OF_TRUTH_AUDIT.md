# RR ScoutIQ — Phase 5.0: Repository Discovery and Source-of-Truth Audit

**Document Reference**: `research/phase5/PHASE_5_0_SOURCE_OF_TRUTH_AUDIT.md`  
**Audit Team**: Senior Cricket Analytics Research Group (Cricket Analyst, Statistical Validator, ML Auditor, Data Quality Engineer, Methodology Reviewer)  
**Status**: APPROVED & FINALIZED  
**Evaluation Scope**: Full Repository Discovery, Artifact Provenance Mapping, and Authority Disambiguation  

---

## 1. Executive Summary & Audit Mandate

The primary mandate of Phase 5.0 is to establish an unassailable **Source of Truth** for the RR ScoutIQ competition submission. In multi-stage analytics pipelines developed under hackathon conditions, multiple intermediate, experimental, and exploratory ranking files frequently co-exist across different directories. 

This audit:
1. Conducts an exhaustive structural scan of the entire repository.
2. Formally distinguishes between **authoritative production deliverables**, **frozen historical benchmarks**, **experimental research artifacts**, and **transient diagnostic scratch files**.
3. Reconciles all apparent naming and ranking divergences.
4. Codifies the exact mathematical inputs, models, and outputs that govern the official Top 10 Batter and Top 10 Bowler selections.

---

## 2. Definitive Source-of-Truth Map

The table below catalogs every critical artifact in the repository, defining its path, technical purpose, governance status, authority level, and relationship to the official Top 10 selections.

| File Path | Functional Purpose | Governance Status | Authority Level | Relationship to Official Top 10 |
| :--- | :--- | :---: | :---: | :--- |
| `FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md` | Final competition submission report presenting executive summary, methodology, official rankings, and player dossiers. | **FROZEN** (SHA-256: `0E0A11...`) | **PRIMARY AUTHORITATIVE** | Definitive written presentation of the official Top 10 Batters and Top 10 Bowlers. |
| `data/processed/m5_3/match_state_full.csv` | Canonical delivery-level dataset ($168,104$ valid DLI legal deliveries) with enriched match-state, phase, and DLI metrics. | **FROZEN** (SHA-256: `CE7E9A...`) | **PRIMARY AUTHORITATIVE** | The single immutable data substrate for all feature generation, baselines, and model training. |
| `dashboard/data.json` & `dashboard/data.js` | Web-facing JSON/JS payload driving the interactive scouting intelligence dashboard. | **FROZEN PRODUCTION** | **AUTHORITATIVE PRODUCTION** | Programmatic reflection of the official Top 10; matches competition report to the exact decimal. |
| `audit_reports/M5_5B_4_3_8/M5_5B_4_3_8_PREDICTIONS_OUT_OF_FOLD.csv` | Out-of-fold cross-validated predictions ($M_4$ context prior vs $M_5$ Empirical Bayes posterior) across all players and spells. | **FROZEN AUDIT** | **AUTHORITATIVE MODEL OUTPUT** | The exact statistical output file from which player-level $\Delta_{\text{EB}}$, $se_{\text{latent}}$, and conservative bounds are derived. |
| `audit_reports/M5_5B_4_3_8/FINAL_TOP20_PRESSURE_RANKING_AUDIT.md` | Milestone sign-off report certifying statistical rigor, Henderson III variance decomposition, and ranking bounds. | **FROZEN AUDIT** | **AUTHORITATIVE SIGN-OFF** | Certifies the official ranking logic ($\text{LB}_{90\% \text{ CI}}$ for batters, $\text{UB}_{90\% \text{ CI}}$ for bowlers). |
| `audit_reports/M5_5B_4_3_8/TOP_10_PRESSURE_BATTERS.md` | Detailed breakdown of the official Top 10 batters with exposure breakdowns across DLI tiers. | **FROZEN AUDIT** | **AUTHORITATIVE REPORT** | Component report for Section C of the final competition submission. |
| `audit_reports/M5_5B_4_3_8/TOP_10_PRESSURE_BOWLERS.md` | Detailed breakdown of the official Top 10 bowlers with exposure breakdowns across DLI tiers. | **FROZEN AUDIT** | **AUTHORITATIVE REPORT** | Component report for Section D of the final competition submission. |
| `data/enriched/player_crosswalk_m5_5.csv` | Canonical player identity crosswalk mapping local player IDs, canonical names, career exposure, and observed discipline roles. | **FROZEN ENRICHMENT** | **AUTHORITATIVE METADATA** | Provides name resolution, career delivery counts, and discipline classification. |
| `src/extract_exact_rankings.py` | Official ranking extraction utility aggregating out-of-fold predictions and applying eligibility gates. | **PRODUCTION CODE** | **AUTHORITATIVE UTILITY** | The authoritative production script that reproduces the exact Top 10 lists from `M5_5B_4_3_8_PREDICTIONS_OUT_OF_FOLD.csv`. |
| `src/export_dashboard_data.py` | ETL pipeline extracting verified player stats and exporting them to the dashboard assets. | **PRODUCTION CODE** | **AUTHORITATIVE PIPELINE** | Generates `dashboard/data.json` and `dashboard/data.js` directly from canonical deliveries and model outputs. |
| `src/generate_top20_reports.py` | Core statistical aggregator computing tier-by-tier delivery metrics, strike rates, economy rates, and hazards. | **PRODUCTION CODE** | **AUTHORITATIVE PIPELINE** | Provides the exact delivery-level accounting for every selected player. |
| `src/m5_5b_4_3_8/run_validation_b4_3_8.py` | Complete dual-domain hierarchical Empirical Bayes validation pipeline (Milestone M5.5-B.4.3.8). | **PRODUCTION ENGINE** | **AUTHORITATIVE ENGINE** | Implements Henderson III, LPMO priors, cluster-linearization, and GroupKFold cross-validation. |
| `scratch/train_only_batters_dli.csv` & `scratch/train_only_bowlers_dli.csv` | Training-only ranking files constructed strictly from 2008–2020 matches. | **RESEARCH SCRATCH** | **NON-AUTHORITATIVE (WALK-FORWARD ONLY)** | Used exclusively in Phase 4.6 for temporal walk-forward evaluation on 2021–2024 test matches. **NOT official rankings.** |
| `data/experimental/cspm/*` | Experimental shadow-mode CSPM outputs (delivery-level BPS/BoPS and shadow rankings). | **EXPERIMENTAL** | **NON-AUTHORITATIVE (DIAGNOSTIC ONLY)** | Experimental pipeline retained strictly as a supplementary match-state diagnostic. |

---

## 3. Disambiguation: Official Rankings vs. Chronological Training Rankings

A crucial distinction established during repository discovery is the difference between the **Official Production Rankings** and the **Phase 4.6 Training-Only Rankings**:

### 1. Official Production Rankings (Authoritative)
- **Scope**: Evaluated across the entire canonical modeling corpus ($168,104$ clean legal deliveries, $730$ fixtures) using 5-fold match-grouped cross-validation ($M_{5.5\text{-B.4.3.8}}$).
- **Eligibility Gates**:
  - Batters: $\ge 500$ career balls, $\ge 100$ pressure balls (T2–4), $se_{\text{latent}} \le 0.035$. Ranked descending by $\text{LB}_{90\% \text{ CI}} = \Delta_{\text{EB}} - 1.645 \times se_{\text{latent}}$.
  - Bowlers: $\ge 500$ career balls, $\ge 20$ pressure spells (or $\ge 100$ pressure balls), $se_{\text{latent}} \le 0.65$ RPO. Ranked ascending by $\text{UB}_{90\% \text{ CI}} = \Delta_{\text{EB}} + 1.645 \times se_{\text{latent}}$.
- **Official Top 10 Batters**:
  1. Abhishek Sharma (`6281`)
  2. Suryakumar Yadav (`1699`)
  3. Vaibhav Sooryavanshi (`50284`)
  4. Finn Allen (`4847`)
  5. Travis Head (`2367`)
  6. Phil Salt (`5553`)
  7. Yashasvi Jaiswal (`6819`)
  8. Ishan Kishan (`4117`)
  9. Tim David (`6396`)
  10. Andre Russell (`1318`)
- **Official Top 10 Bowlers**:
  1. Sunil Narine (`781`)
  2. Jasprit Bumrah (`2933`)
  3. Mustafizur Rahman (`4373`)
  4. Kuldeep Yadav (`3644`)
  5. Axar Patel (`2876`)
  6. Wanindu Hasaranga (`4900`)
  7. Ravindra Jadeja (`152`)
  8. Mitchell Santner (`4101`)
  9. Sikandar Raza (`2984`)
  10. Abrar Ahmed (`5979`)

### 2. Phase 4.6 Chronological Training-Only Rankings (Research Split Only)
- **Scope**: Constructed strictly from matches played prior to January 1, 2021 ($N = 431$ fixtures, $101,647$ deliveries) to evaluate out-of-sample performance on unseen $2021$–$2024$ matches ($N = 299$ fixtures).
- **Files**: `scratch/train_only_batters_dli.csv`, `scratch/train_only_bowlers_dli.csv`.
- **Purpose**: Strictly designed to audit chronological predictive superiority against CSPM.
- **Why They Differ**: Players who made their competitive debuts after 2020 (such as Vaibhav Sooryavanshi, ID `50284`) or had fewer than 500 balls prior to 2021 naturally did not appear in the 2008–2020 training split.
- **Governance Mandate**: Under no circumstances should Phase 4.6 training-only ranking files be confused with or substituted for the official production Top 10.

---

## 4. Canonical Definitions and Evaluation Columns

All delivery-level attributes and statistical metrics used in RR ScoutIQ adhere to strict canonical column specifications within `data/processed/m5_3/match_state_full.csv`:

### 1. Delivery Filtering & Integrity
- `is_dli_valid == 1`: Delivery has complete, uncorrupted match-state parameters (valid target, valid wickets, valid innings).
- `ext_is_legal_delivery == 1`: Legal delivery (excludes wides and no-balls from ball counts; bowler debit runs and batter runs are correctly partitioned).

### 2. DLI Pressure Categorization
- `dli`: Continuous Dynamic Leverage Index value calculated under frozen production formulas ($M_{5.3}$).
  - Setting ($I = 1$): $\text{DLI} = w_{\text{phase}} \cdot \left[1 + 0.15 \cdot (W - 3 \cdot \frac{O}{20}) + 0.10 \cdot \left(\frac{R_{\text{curr}}}{\max(1, O)} - \text{Par}_{\text{phase}}\right)\right]$
  - Chasing ($I = 2$): $\text{DLI} = w_{\text{phase}} \cdot \left[0.4 \cdot \text{RRR} + 0.15 \cdot W + 0.05 \cdot \text{ReqRuns} - 0.2 \cdot \text{OversRem}\right]$
- `pre_pressure_tier`: Delivery pressure tier:
  - `Tier 1: Low`: $\text{DLI} < 1.0$ (Normal baseline)
  - `Tier 2: Medium`: $1.0 \le \text{DLI} < 1.75$ (Moderate pressure)
  - `Tier 3: High`: $1.75 \le \text{DLI} < 3.0$ (High leverage)
  - `Tier 4: Extreme`: $\text{DLI} \ge 3.0$ (Crunch-time leverage)
  - *Combined Pressure*: Tiers 2, 3, and 4 ($\text{DLI} \ge 1.0$).
  - *High Pressure*: Tiers 3 and 4 ($\text{DLI} \ge 1.75$).

### 3. Contextual Baseline & Hierarchical Model Outputs
- `pred_m4`: Expected outcome from Model $M_4$ (contextual prior without player identity, conditioned on match phase and pressure tier).
- `pred_m5`: Shrunk posterior estimate from Model $M_5$ (hierarchical Empirical Bayes with Henderson III crossed variance components).
- `val_add` (Batters): $\text{pred}_{M_5} - \text{pred}_{M_4}$ (net contextual scoring value-add).
- `delta` (Bowlers): $\text{pred}_{M_5} - \text{pred}_{M_4}$ (contextual economy suppression in RPO).
- `se_latent_m5`: Latent standard error derived from two-way cluster-robust linearization.

---

## 5. Audit Conclusion & Source-of-Truth Sign-Off

The repository structure has been fully audited. All primary deliverables, data files, models, and scripts have been traced to their exact sources. 

The authoritative benchmarks for all subsequent Phase 5 evaluations are:
1. **Official Competition Report**: `FINAL_RR_SCOUTIQ_COMPETITION_REPORT.md`
2. **Canonical Deliveries**: `data/processed/m5_3/match_state_full.csv`
3. **Out-of-Fold Model Predictions**: `audit_reports/M5_5B_4_3_8/M5_5B_4_3_8_PREDICTIONS_OUT_OF_FOLD.csv`
4. **Interactive Dashboard Source**: `dashboard/data.json`

Phase 5.0 is formally signed off. The research team proceeds immediately to Phase 5.1.
