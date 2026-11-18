# RR ScoutIQ - Project Context

## Project identity and objective

**Project name:** RR ScoutIQ - Pressure Performance Intelligence System

**Hackathon context:** Rajasthan Royals SupeRR Selector Season 2.

**Problem statement:** Use historical cricket data to identify the top 10 batters
and top 10 bowlers who perform most reliably under pressure. The intended system
will compare ordinary performance with performance in pressure situations and
consider consistency, resilience, and statistical reliability.

The top-10 objective is the product goal, not a result already produced. M1
audited and documented the supplied data; it did not calculate player rankings,
pressure scores, or an agreed ranking formula.

## Repository layout

```text
RR_ScoutIQ/
|-- RRScoutIQenv/                  Existing Python virtual environment
|-- data/
|   |-- data_pack.zip.zip          Original supplied archive (preserve unchanged)
|   `-- extracted/
|       |-- ball_by_ball.csv
|       |-- competitions.csv
|       |-- competition_team_player_mapping.csv
|       |-- matches.csv
|       |-- playing_eleven.csv
|       |-- teams.csv
|       `-- Round 1 Problem Statement _ SupeRR Selector Season 2.docx.pdf
|-- audit_reports/
|   |-- anomaly_investigation/     Row-level investigation outputs
|   |-- rules_validation/          M2.2 distributions and row-level examples
|   |   |-- provider_investigation/ Provider searches and scorecard evidence
|   |   |-- multi_match_reconciliation/ M2.2B scorecard comparisons
|   |   |-- extras_legal_delivery/ M2.2C extras and candidate-ball comparisons
|   |   |-- match_state/           M2.3 innings/match-state validation
|   |   `-- provider_encoding_resolution/ M2.2E provider/encoding evidence
|   |-- feature_feasibility/       M3.1A feature feasibility evidence
|   |-- performance_metrics/       M2.4 metric/source/join feasibility
|   `-- visualizations/            M1 audit plots
|-- docs/
|   |-- AGENT_HANDOFF.md
|   |-- CRICKET_RULES_VALIDATION.md
|   |-- CRICKET_DATA_SCHEMA.md
|   |-- DATA_DICTIONARY.md
|   |-- MILESTONE_TRACKER.md
|   `-- TECHNICAL_DECISIONS.md
|-- notebooks/                     Present; no M1 notebook is required
|-- src/
|   |-- anomaly_investigation.py
|   |-- dataset_audit.py
|   |-- provider_investigation.py
|   |-- multi_match_reconciliation.py
|   |-- extras_legal_delivery_validation.py
|   |-- match_state_validation.py
|   |-- provider_encoding_resolution.py
|   |-- feature_feasibility_audit.py
|   |-- performance_metric_validation.py
|   `-- rules_validation.py
|-- .gitignore
|-- M1_COMPLETION_REPORT.md
|-- PROJECT_CONTEXT.md
`-- README.md
```

The requested archive name during setup was `data/data_pack.zip`, but the file
present in the workspace is `data/data_pack.zip.zip`. It is a valid archive,
passed its ZIP integrity check, and was used for M1 without renaming or modifying
it. Do not silently substitute another dataset or rename the original archive.

## Dataset inventory (verified in M1)

The archive contains six CSV files and one problem-statement PDF:

| File | Rows | Columns | Role |
|---|---:|---:|---|
| `ball_by_ball.csv` | 200,999 | 33 | Delivery-level batting, bowling, runs, wicket, extras, and descriptive fields |
| `matches.csv` | 883 | 22 | Match IDs, competition, date, teams, toss, revised-target fields, winner, result |
| `playing_eleven.csv` | 28,381 | 9 | Match/team/player lineup records and lineup flags |
| `competition_team_player_mapping.csv` | 6,413 | 6 | Competition/team/player IDs and names |
| `teams.csv` | 353 | 3 | Competition/team IDs and team names |
| `competitions.csv` | 141 | 4 | Competition IDs, names, format, season |
| `Round 1 Problem Statement _ SupeRR Selector Season 2.docx.pdf` | - | - | Hackathon problem statement |

Observed match formats are T20 (401 matches) and T20I (482 matches). Match dates
parse from 2022-01-22 through 2026-11-01. The delivery data contains innings
values 1 through 4. Full inferred column types and missing-value counts are in
[`audit_reports/dataset_overview.txt`](audit_reports/dataset_overview.txt) and
[`audit_reports/missing_values.csv`](audit_reports/missing_values.csv).

M1 verified that the seven extracted files match the archive contents. The
original archive and extracted CSVs are source data, not working files.

## Technology stack and environment

- Python 3.13.9 in the existing `RRScoutIQenv` virtual environment.
- pandas for CSV loading, tabular audit, joins, and report tables.
- matplotlib for M1 visualizations.
- Python standard library for paths, ZIP inspection/extraction, CSV checks,
  hashing, and validation.
- VS Code workspace on Windows.
- No dependency manifest or dashboard framework was found during M1. Do not
  assume or introduce a dashboard framework without a later approved decision.

Use the already-created environment:

```powershell
.\RRScoutIQenv\Scripts\python.exe --version
.\RRScoutIQenv\Scripts\python.exe src\dataset_audit.py
.\RRScoutIQenv\Scripts\python.exe src\anomaly_investigation.py
```

The two scripts use existing packages; do not reinstall packages just to repeat
M1. If a required package is unexpectedly unavailable, report the environment
issue before changing dependencies.

## Roles and responsibilities

No named team members or assigned owners are documented in the repository.
The following are proposed responsibilities, not confirmed assignments:

| Role | Responsibility |
|---|---|
| Cricket/domain reviewer | Define cricket rules, pressure context, innings and dismissal interpretation; resolve provider conventions |
| Data engineer | Preserve source data, create reproducible transformations, validate joins and maintain provenance |
| Metrics/statistics owner | Propose and validate batting/bowling measures, baseline comparisons, sample-size treatment, and uncertainty |
| Product/UX owner | Translate the approved results into hackathon user needs and dashboard requirements |
| QA/documentation owner | Maintain reproducible checks, milestone records, limitations, and handoff documentation |

One person may perform multiple roles. Do not imply that a role has approved a
metric or decision unless approval is recorded.

## Current progress and verified findings

- **M1 (dataset audit and anomaly investigation): completed.**
- **M2 (cricket data understanding and metric validation): in progress.**
- **M2.1 (complete schema understanding): completed.**
- **M2.2 (cricket/provider convention validation): in progress; not ready to close.**
- **M2.2D (wicket and dismissal validation): in progress with limited evidence.**
- **M2.2E (provider and encoding resolution): in progress; provider and core field conventions remain unresolved.**
- **M2.3 (innings and match-state reconstruction validation): in progress.**
- **M2.4 (performance metric validation & staged hybrid enrichment): completed (hybrid enrichment architecture implemented and pilot-validated).**
- **M2.5 (consolidated findings & human/domain review): completed (data reliability matrix, population profiling, and pressure feasibility documented in audit_reports/M2_5_DOMAIN_REVIEW.md).**
- **M2.6 (domain sign-off & methodology approval): ready for review before M3.**
- Six CSVs and one PDF were extracted and audited; all requested M1 reports and
  visualizations were generated.
- No exact duplicate full rows were found in the six CSVs.
- The candidate delivery key `(match_id, innings, overid, over_ball_num)` is
  unique in `ball_by_ball.csv`.
- Candidate key `(match_id, team_id, player_id)` repeats for 75
  `playing_eleven.csv` rows across 35 groups; those records have different
  `batting_order` values. They have not been deduplicated.
- There are 16 matches without ball-by-ball rows and 3 without playing-eleven
  rows. Every such match is marked `Match Abandoned`; this looks potentially
  expected but still requires confirmation against source coverage conventions.
- `matches.csv` has 119 `man_of_the_match = 0` values. Zero is not present as a
  player ID in the player mapping; its meaning is not documented.
- The delivery audit found 12 rows with a `dismissed_player_id` but
  `is_wicket=False`, and one row with `is_wicket=True` but no
  `dismissed_player_id`.
- The row at `ball_by_ball.csv` Excel row 127901 / DataFrame index 127899 /
  match_id 40709 has dismissal type `Retire Out`, `is_wicket=True`, and no
  dismissed-player ID. This is a flagged record, not a confirmed error.
- One negative `bowl_speed` is recorded at match 14108 for bowler Axar Patel
  (bowler_id 2876), value `-1`.
- The raw CSV stores the text `None` in `extras_type` on 189,167 rows; this is
  not the same as an empty CSV field. On those rows `extras1_runs` is 6. The
  field meanings are undocumented, so neither value should be reinterpreted
  without source documentation.
- There are 36 rows with nonzero `extras_2_runs`, and 31 distinct combinations
  of the requested extras/runs/flag fields. Exact records and representative
  combinations are in the investigation report.
- The original provider has not been identified and no provider data
  dictionary was found in the archive, local documentation, or searches for
  the unusual field names.
- The M2.2A Cricbuzz check for match 14113 remains a one-match precedent.
  M2.2B added eight independent Cricbuzz scorecards across IPL 2022-2025 and
  T20Is in 2022, 2024, and 2025. In all 16 regulation innings, the local
  `runs` sum equals scorecard team total minus scorecard aggregate extras, and
  local `is_wicket=true` counts equal scorecard wickets. Five matches were
  fully verified at match scope; three were partially verified because
  Super Over records were unavailable or not separately exposed. This
  strengthens `runs` as **PROBABLE** batter runs dataset-wide, not a
  provider-wide guarantee.
- `extras1_runs` remains probably a category/code field; `extras_2_runs`
  remains unresolved. `Overstep` is not confirmed as a No ball. Local counts
  of `wide` and `Overstep` labels are not interchangeable with scorecard runs
  in those categories. The source has no separate `wide`, `is_no_ball`, or
  legal-delivery column, so legal-ball reconstruction remains unresolved.
- M2.2C examined all 31 observed combinations of `extras_type`,
  `extras1_runs`, `extras_2_runs`, `runs`, `is_four`, and `is_six` across
  200,999 deliveries. `extras1_runs` is constant within each category label,
  which supports a **PROBABLE** code-like role but does not define the values.
  `extras_2_runs` is nonzero on 36 rows (20 values of 1 and 16 of 4), with
  meaning still **UNRESOLVED**. The source has no `wide` column; `wide` is only
  an `extras_type` label.
- In the 18 independently scorecard-reconciled regulation innings, excluding
  only `wide` labels matched the scorecard over total in 9; excluding both
  `wide` and `Overstep` matched 14; excluding `wide`, `Overstep`, and `other`
  matched all 18. The last is a sample-only candidate using an undocumented
  label, not a validated legal-delivery rule. Wide label counts equalled
  scorecard wide-run totals in 11/18 innings; `Overstep` row counts equalled
  scorecard No-ball extras in 14/18, but row counts and run totals are not
  interchangeable. Legal deliveries remain **UNRESOLVED**.
- MCC Law 18.10.3 defines bowler debits at rule level as striker runs,
  No-ball extras, and Wide runs. Source-level delivery amounts and category
  mappings are not established; bowler-conceded runs cannot yet be calculated
  reliably and no formula is approved.
- M2.2D found nine nonblank `dismissal_type` values plus blank, including
  `Obstracting the field` (2) and `Obstructing the field` (1); preserve both
  labels. All 13 previously identified wicket/player-ID inconsistencies were
  checked against source rows. There are 12 populated dismissed-player IDs
  with `is_wicket=false` and one `is_wicket=true` row (match 40709, source row
  127901) with `Retire Out` and no dismissed-player ID. No zero-coded IDs were
  observed. The source does not contain a dismissed-player name column.
- Local team-wicket flags match independent scorecard totals in 18 selected
  regulation innings. One detailed innings (match 14094, innings 1) matches
  all five scorecard dismissal names/types; the scorecard shows four bowling
  wickets for five team wickets, consistent with the local RunOut as
  non-bowler-credit. This detailed sample does not establish provider-wide
  meaning.
- Conventional bowler-credit interpretation for standard dismissal modes is
  **PROBABLE**, not provider-confirmed. `Stump` as Stumped is **PROBABLE**;
  `Obstracting the field` and provider dismissal/ID semantics remain
  **UNRESOLVED**. No batting-dismissal or bowler-wicket calculation is
  approved. M2.2D is not complete.
- M2.2D validation script and evidence:
  [`src/wicket_dismissal_validation.py`](src/wicket_dismissal_validation.py)
  and
  [`audit_reports/rules_validation/wicket_dismissal/wicket_dismissal_report.md`](audit_reports/rules_validation/wicket_dismissal/wicket_dismissal_report.md).
- M2.2C code and reproducible evidence:
  [`src/extras_legal_delivery_validation.py`](src/extras_legal_delivery_validation.py)
  and
  [`audit_reports/rules_validation/extras_legal_delivery/extras_legal_delivery_report.md`](audit_reports/rules_validation/extras_legal_delivery/extras_legal_delivery_report.md).
- `revised_target` is populated on 23 match rows; revised-over fields on 25.
  There is no separate ordinary innings-target field in `matches.csv`.
- M2.3 audited all 200,999 deliveries across 1,724 match/innings groups.
  `innings_ball_num` is unique, contiguous from 1, and follows source row
  order in every group; `overid` and `(overid, over_ball_num)` are monotone in
  that order. This confirms reproducible stored order, not event chronology or
  legal-ball numbering. There are 39 adjacent timestamp ties, four timestamp
  decreases, and 8,429 rows with `over_ball_num > 6`.
- Innings labels 1 and 2 are **PROBABLE** regulation-innings labels based on
  selected scorecards; labels 3 and 4 occur in six matches each but their
  meaning is **UNRESOLVED** unless independently verified. Sixteen matches
  with no delivery rows are marked `Match Abandoned`; 22 delivered matches
  lack one of labels 1/2 (19 `No Result`, three `Match Abandoned`). These are
  coverage observations, not proof of completeness.
- The M2.3 audit confirms the 18 selected local `runs` sums match scorecard
  batter-run subtotals and final wicket flags match scorecard wickets, after
  validating source row ranges and batting-team IDs. Scorecard comparisons
  are **PARTIAL MATCH**, not exact team-score matches: the source has no
  validated per-delivery team-total field. `runs` remains **PROBABLE** as
  batter runs; extras fields remain **UNRESOLVED** and are not added.
- Cumulative source `runs` and source wicket-flag progressions are retained
  for inspection. Team-score progression is **UNRESOLVED**; wicket cumsums
  are arithmetically **CONFIRMED**, while team-wicket semantics are
  **PROBABLE** only in the independently compared sample and otherwise
  **UNRESOLVED**. The M2.2D wicket/player-ID anomalies remain unchanged.
- Legal balls, completed overs, balls remaining, targets from local totals,
  runs required, current/required run rates, and revised-chase state are
  **UNRESOLVED**. Nine independent ordinary scorecard target references are
  available only for sample matches after first-innings source checks; they
  are not local pre-delivery targets. No par/scoring trajectory is approved.
  M2.3 therefore remains **IN PROGRESS**.
- M2.3 generator and audit outputs:
  [`src/match_state_validation.py`](src/match_state_validation.py) and
  [`audit_reports/rules_validation/match_state/match_state_validation_report.md`](audit_reports/rules_validation/match_state/match_state_validation_report.md).
- M2.3 completion audit confirmed the ten CSV outputs and the report are
  non-empty, the script compiles and regenerated the existing reports
  successfully, and all seven source hashes match retained baselines. All six
  extracted CSVs match M1/M2.2B/M2.2C/M2.3 manifests; the archive matches
  M2.2B/M2.2C/M2.3. M1 did not retain an archive hash.
- M2.2E generator and evidence:
  [`src/provider_encoding_resolution.py`](src/provider_encoding_resolution.py)
  and
  [`audit_reports/rules_validation/provider_encoding_resolution/`](audit_reports/rules_validation/provider_encoding_resolution/).
- M2.2E reused the 18 existing regulation-innings scorecard comparisons
  across nine IPL/T20/T20I matches. Local `runs` sums match scorecard
  batter-run subtotals and local wicket counts match team wickets in all 18;
  these are aggregate comparisons and overall innings comparisons remain
  partial. Three naive additive sums of the run-named fields mismatched
  scorecard team totals in all 18 selected innings.
- The original provider remains **UNRESOLVED**: the archive has no provider
  comment/schema, the PDF is the hackathon problem statement, and prior exact
  field searches found no verifiable provider documentation. `extras1_runs`
  is **PROBABLE** as a code-like field from its stable pairing with raw
  `extras_type` labels; `extras_2_runs`, `Overstep`, byes/leg-byes provider
  mapping, multiple extras, legal deliveries, batter balls faced, and bowler
  runs conceded remain **UNRESOLVED**. `wide` is **PROBABLE** as a wide-like
  label, not a fully validated legality flag.
- New M2.2E evidence covers all 31 extras combinations, candidate legal-ball
  comparisons, batter/bowler raw row counts (not metrics), per-dimension
  scorecard comparisons, source-row checks, and seven matching source hashes.
  New browser access to saved scorecards failed; no player-level balls-faced
  or bowler-conceded values were fabricated. M2.2E and overall M2.2 remain
  **IN PROGRESS**.
- M2.2 validation findings, rule references, row-level examples, multi-match
  scorecard comparisons, and open calculation gates are documented in
  [`docs/CRICKET_RULES_VALIDATION.md`](docs/CRICKET_RULES_VALIDATION.md).
  Generated evidence is in `audit_reports/rules_validation/`; source
  conventions for extras, legal deliveries, and performance formulas remain
  unresolved. See
  [`audit_reports/rules_validation/multi_match_reconciliation/reconciliation_report.md`](audit_reports/rules_validation/multi_match_reconciliation/reconciliation_report.md).
- Ball-by-ball match IDs match `matches.csv`; absent delivery/lineup coverage is
  on abandoned matches in the observed archive.
- No player rankings, pressure scores, ML models, or dashboard have been
  produced.

For exact source row numbers and anomaly classification, consult
[`docs/TECHNICAL_DECISIONS.md`](docs/TECHNICAL_DECISIONS.md) and
[`audit_reports/anomaly_investigation/anomaly_investigation_report.md`](audit_reports/anomaly_investigation/anomaly_investigation_report.md).

## Proposed performance-analysis methodology (unfinalized)

This section is a set of candidate questions and design directions for M2, not
an approved methodology. Thresholds, formulas, eligibility rules, weights, and
ranking rules remain undecided.

1. **Define the unit of analysis.** Candidate units include player-match,
   player-innings, and player-delivery. Keep competition, format, season, team,
   and player identifiers attached for traceability.
2. **Reconstruct pre-delivery state.** Order deliveries within match and innings;
   derive cumulative score and wickets *before* each delivery only after
   validating delivery ordering, total-run fields, wicket semantics, innings
   boundaries, and illegal-delivery rules.
3. **Define pressure situations with domain approval.** Candidate context
   variables include innings/phase, score or runs required, resources/wickets
   remaining, target difficulty, and match importance. The data has no explicit
   pressure label. Cutoffs and inclusion rules require a cricket-domain decision
   and validation; do not treat any candidate threshold as final.
4. **Compare like with like.** A proposed baseline compares pressure and
   non-pressure performance in relevant competition formats and roles. Decide
   whether comparisons are within-player, cohort-based, or both, and guard
   against small samples.
5. **Validate candidate batting measures.** Runs, balls faced, strike rate,
   boundaries, dismissals, and survival/contribution are candidates only. Their
   relationship to `runs`, `extras_type`, and extras amounts must be established.
6. **Validate candidate bowling measures.** Legal balls, wickets by dismissal
   type, and runs conceded are candidates only. Extras semantics and legality
   must be resolved before computing economy or conceded runs.
7. **Operationalize reliability.** Consistency, resilience, and statistical
   reliability need approved definitions, sample-size handling, and uncertainty
   treatment. No measure or weighting has been selected.
8. **Approve eligibility and ranking.** Establish minimum opportunities,
   treatment of incomplete/abandoned matches, player roles, ties, and how
   multiple metrics lead to a top 10 before publishing rankings.

No source convention, formula, or threshold should be invented to fill a gap.
Read [`docs/TECHNICAL_DECISIONS.md`](docs/TECHNICAL_DECISIONS.md) and obtain
approval before changing the pressure methodology or ranking formula.

## M3.1A feature feasibility audit

M3.1A is **COMPLETE** as a bounded investigation of innings-stage
reconstruction, batter participation/balls faced, bowler wicket attribution,
and the proposed feature set. The reproducible generator is
[`src/feature_feasibility_audit.py`](src/feature_feasibility_audit.py); its
reports and matrix are in
[`audit_reports/feature_feasibility/`](audit_reports/feature_feasibility/).

The audit confirms `innings_ball_num` reproduces stored row order in all 1,724
match/innings groups. It does not represent legal balls or prove chronology.
`overid` and `over_ball_num` remain raw over-like labels; legal deliveries,
actual overs, innings phase, and innings 3/4 meanings remain unresolved.
Striker, non-striker, and bowler IDs map to the supplied player mapping in
match competition/team context. That supports descriptive row attribution,
not balls faced or match participation. `runs` remains probable as a
batter-run subtotal only at aggregate innings scope. No balls-faced or strike
rate calculation is approved.

Bowler IDs also map contextually. `is_wicket` matches scorecard team-wicket
totals in 18 selected innings, but is not a bowler-credit field. Common
dismissal credit interpretations remain probable under the prior M2.2D
assessment; `RunOut` and `Retire Out` are not automatically credited, while
`Obstracting the field` remains unresolved. Preserve the 13 source
wicket/player-ID inconsistencies.

The matrix assesses 28 proposed batting, bowling, and pressure-context
features. No derived performance feature is approved for selection-quality
calculations; provisional fields are limited to descriptive use with their
evidence boundaries. M2.2 and M2.3 remain **IN PROGRESS**. M3 methodology is
still unapproved; this audit does not start pressure scoring, ranking, model,
or dashboard work.

The separate `playing_eleven.csv` contains 28,381 raw lineup-like records;
`is_played` values and timing are not defined. Five player keys do not map to
the supplied player map and all five are raw `is_played=false`; 75 rows repeat
the `(match_id, team_id, player_id)` candidate key in 35 groups. Preserve
these rows and do not infer actual appearance or eligibility from the lineup
flags.

## M2.4 performance metric validation & staged hybrid enrichment

The reproducible pipeline and audit generators are:
- Baseline analysis: [`src/performance_metric_validation.py`](src/performance_metric_validation.py)
- External source verification: [`src/external_source_verification.py`](src/external_source_verification.py)
- Independent metric audit: [`src/independent_metric_audit.py`](src/independent_metric_audit.py)
- Staged hybrid enrichment: [`src/staged_hybrid_enrichment.py`](src/staged_hybrid_enrichment.py)

Key verified outcomes and artifacts:
- **Cricsheet Open Data Archives:** Downloaded to `data/external/cricsheet/downloads/` with SHA-256 manifests verified under ODC-By v1.0.
- **Match Crosswalk (`data/enriched/match_crosswalk.csv`):** All 883 match records audited (784 covered, 61 policy-withheld, 25 developmental, 13 abandoned).
- **Player Crosswalk (`data/enriched/player_crosswalk.csv`):** 182 player appearances resolved across 8 representative fixtures (100.0%). Historical bowling anomalies in match 34429 (`AM Fernando`, `PWH de Silva`, `PHKD Mendis`, `BKG Mendis`, `RK Singh`) and domestic aliases (`CV Varun`, `MM Sharma`, `J Fraser-McGurk`) fully disambiguated.
- **Pilot Delivery Enrichment (`data/enriched/pilot/enriched_ball_by_ball_pilot.csv`):** 1,994 deliveries across 20 innings (including 4 Super Over innings) enriched with explicit `ext_` fields. Original 33 columns remain strictly untouched.
- **Comprehensive QA Scorecard Verification (`audit_reports/performance_metrics/pilot_enrichment_qa_report.csv`):** 100.0% exact match across all tested metrics (145/145 batter runs, 145/145 balls faced, 99/99 legal balls bowled, 99/99 bowler runs conceded, 99/99 bowler wickets, 99/99 economy rate, 64/64 bowling average, 64/64 bowling strike rate, 20/20 innings totals).
- **Final Verification Deliverables:** [`audit_reports/performance_metrics/final_m2_4_verification.md`](audit_reports/performance_metrics/final_m2_4_verification.md), alongside 5 audit CSVs (`sample_size_reconciliation.csv`, `player_identity_verification.csv`, `bowling_metric_reconciliation.csv`, `unresolved_mappings.csv`, `enrichment_integrity_checks.csv`).

**M2.4 is COMPLETE: Hybrid enrichment architecture implemented and pilot-validated.** Full-dataset enrichment across the 784 covered matches remains a separate future milestone. Rankings and pressure scoring remain strictly out of scope.

## M2.5 Consolidated Findings & Human/Domain Review

The consolidated findings and domain review were finalized in:
- Master Report: [`audit_reports/M2_5_DOMAIN_REVIEW.md`](audit_reports/M2_5_DOMAIN_REVIEW.md)
- Data Reliability Matrix (29 unique items): [`audit_reports/performance_metrics/consolidated_data_reliability_matrix.csv`](audit_reports/performance_metrics/consolidated_data_reliability_matrix.csv)
- Matrix Generator: [`src/generate_m2_5_reliability_matrix.py`](src/generate_m2_5_reliability_matrix.py)
- M3 Methodology Requirements & Specification: [`docs/M3_METHODOLOGY_REQUIREMENTS.md`](docs/M3_METHODOLOGY_REQUIREMENTS.md)

Key consolidated outcomes:
- **Data Reliability Matrix:** 29 metrics and fields classified into 5 tiers (14 Confirmed, 3 Provisional, 5 External Enrichment Required, 3 Unresolved, 4 Excluded).
- **Available Analysis Population:** Exactly 883 matches profiled (784 covered, 61 policy-withheld, 25 developmental, 13 abandoned). 958 active players identified.
- **Sample Skewness Quantified:** 41.9% of batters and 42.0% of bowlers have fewer than 5 innings. Strict qualification thresholds and empirical Bayesian shrinkage mandated for M3.
- **Pressure Context Feasibility:** Pre-delivery score, wickets in hand, match phase (in 20-over matches), and RRR (in standard Innings 2 chases) confirmed feasible via hybrid enrichment. Rain-curtailed chase RRR and shortened match phases explicitly classified as UNRESOLVED to prevent information leakage. Ball speed (`bowl_speed`), `man_of_the_match`, and qualitative observer styles strictly excluded.

**M2.5 is COMPLETE.** M2.6 domain review is completed.

## M3 Pressure Performance Methodology & Metric Approval

The formal pressure methodology is established and submitted for review:
- Master Specification: [`audit_reports/M3_PRESSURE_METHODOLOGY.md`](audit_reports/M3_PRESSURE_METHODOLOGY.md)
- Distribution & Empirical Baseline Script: [`src/research_m3_distributions.py`](src/research_m3_distributions.py)

Key methodological pillars:
1. **Zero Information Leakage:** Every pressure index is computed strictly from pre-delivery scorecard states ($RRR$, $B_{\text{rem}}$, $W_{\text{hand}}$, phase). Post-delivery outcomes and match results are strictly excluded.
2. **Dual-Regime Delivery Leverage Index (DLI):**
   - Innings 2 Chase: Multiplicative model combining RRR deficit, square-root wicket scarcity ($[10/(W_{\text{hand}}+1)]^{0.5}$), and hyperbolic temporal runway ($1 + 24/[B_{\text{rem}}+12]$), clamped to $[0.10, 5.00]$.
   - Innings 1 Setting: Resource collapse model combining phase weights (0.90, 1.00, 1.50) with wicket depletion ($[10/(W_{\text{hand}}+1)]^{0.6}$) and scoring stagnation.
   - Super Overs: Deterministic maximum leverage ($DLI = 3.50$).
   - DLS Exclusions: 23 rain-curtailed matches with revised targets excluded from continuous chase RRR modeling.
3. **Batter Pressure Performance Index (BPPI):** Integrates Expected Runs Added ($x\text{RA}$ per ball), situational strike rate delta ($\Delta \text{SR}$), boundary power, dot-ball suppression, and dismissal preservation. Rate-based metrics prevent volume bias.
4. **Bowler Pressure Performance Index (PPBI):** Integrates Expected Runs Saved ($x\text{RS}$ per ball), economy containment ($\Delta \text{Econ}$), wicket breakthrough rate, dot-ball creation, and boundary restriction. Decouples bowling opportunity difficulty (overs 19–20) from bowling quality.
5. **Statistical Reliability & Shrinkage:** Empirical Bayesian shrinkage ($\lambda = N / [N + K]$) with $K_{\text{bat}} = 40$ and $K_{\text{bowl}} = 48$ legal balls, pulling small samples toward tactical cohort priors. Mandated 1,000-draw bootstrap resampling for $90\%$ credible intervals and rank stability filtering (Rank IQR $\le 3.0$).
6. **Role Standardization & Unified Top 10:** Standardizes performance within tactical cohorts (Top Order, Middle, Finishers; Powerplay, Middle, Death) using cohort z-scores ($Z_{\text{role}}$) and franchise utility weights to derive single unified, defensible Top 10 lists for batters and bowlers.
7. **Dual-Tier Eligibility Gates:** Mandates $\ge 12$ career innings AND $\ge 120$ balls faced / 144 legal balls bowled, WITH $\ge 36$ pressure balls faced / 42 pressure legal balls bowled ($DLI \ge 1.35$).
8. **Validation Battery:** Formulates 8 empirical validation tests including anti-leakage audits, historical replays, shrinkage sensitivity, and bootstrap rank stability.

**Milestone M3: APPROVED AND CLOSED, with five explicitly provisional methodological components.**

The final refined methodology, dimensional corrections, population-wide validations, and definitive pre-implementation closure audits are documented in:
- Methodology Closure Audit: [`audit_reports/M3_METHODOLOGY_CLOSURE_AUDIT.md`](audit_reports/M3_METHODOLOGY_CLOSURE_AUDIT.md)
- Final Sign-off Validation Report: [`audit_reports/M3_FINAL_SIGNOFF_VALIDATION.md`](audit_reports/M3_FINAL_SIGNOFF_VALIDATION.md)
- Statistical Consistency Audit: [`audit_reports/M3_STATISTICAL_CONSISTENCY_AUDIT.md`](audit_reports/M3_STATISTICAL_CONSISTENCY_AUDIT.md)
- Final Evidence Audit: [`audit_reports/M3_FINAL_EVIDENCE_AUDIT.md`](audit_reports/M3_FINAL_EVIDENCE_AUDIT.md)
- Methodology Closure Script: [`src/methodology_closure_audit.py`](src/methodology_closure_audit.py)
- Vectorized Sign-Off Simulation Script: [`src/final_signoff_audit.py`](src/final_signoff_audit.py)

Key Verified Pre-Implementation Findings:
1. **Normal-Normal Statistical Appropriateness & Count Model Equivalence (Task 1):** Verified delivery-level outcome distributions ($37.1\%$ dots, $37.4\%$ singles, mean $1.395$, var $3.038$, skew $+1.44$). Unbalanced ANOVA derives $\tau_b = 15.96$ career SR points ($K_{\text{career}} = 121.5$ balls) and $\tau_b \approx 24.50$ high-pressure SR points ($K_{\text{press}} = 50.62$ balls). Explained that identical posterior means with Poisson-Gamma are an algebraic consequence of matching conjugate prior hyperparameters ($\mu_0, K$), not independent empirical validation. Clarified that $N_{\text{eff}} \approx 36 / (1 + 2 \times 0.06) \approx 32.1$ is strictly a lag-1-only illustrative baseline, not an empirically established effective sample size. Normal-Normal is retained as **PROVISIONAL**, requiring residual diagnostics and comparison against overdispersed alternatives during the controlled M4 pilot.
2. **Wicket Prior Cap Sensitivity ($M \in \{60, 90, 120, 180\}$) (Task 2):** Documented absolute differences $|\hat{p}_M - \hat{p}_{90}|$. Overall mean absolute change is only $0.0926\%$ ($M=60$) and $0.0758\%$ ($M=120$), dropping to $0.029\%$ for high-volume batters. Top-10 batter survival overlap is $10/10$ identical between $M=90, 120, 180$. $M = 90.0$ balls is formally labeled as a **pragmatic selected engineering setting** (not an empirical optimum), providing stable regularized shrinkage while uncapped REML ($M=1,613$) over-shrinks and collapses variance.
3. **Bootstrap Clustering & Multi-Innings Structure (Task 3):** Discovered that multi-innings match participation occurs in only $0.18\%$ of batter matches ($25/13,729$) and $0.12\%$ of bowler matches ($12/10,094$), exclusively in Super Over matches. Proved that Scheme B (Match-Innings) expands median SE by $1.13\times$ (batters) and $1.19\times$ (bowlers) over naive delivery bootstrap (Scheme A). Scheme C (Whole Match) is empirically identical to Scheme B (median ratio $1.00\times$, rank correlation $0.996$), with Scheme B confirmed as the standard. Monte Carlo stability shows $B=1,000$ draws achieves CV $\approx 0.55\%$.
4. **Role Standardization Safeguards & Engineering Labels (Task 4):** Evaluated alternative cohort cutoffs. Powerplay $\ge 40\%$ and Death $\ge 30\%$ preserves healthy cohorts (Middle $= 105$, PP $= 85$, Death $= 37$). Variance regularization ($\alpha = 0.10$) and partial pooling ($K_{\text{pool}} = 10$) have negligible rank impact ($\text{Corr} = 0.999998$, max $|\Delta Z| = 0.018$) while preventing variance collapse; formally designated as **defensible engineering safeguards**.
5. **Monotonicity & Interval Terminology (Task 5):** Clamped DLI is formally defined as **weakly monotonic** (non-decreasing). Uncertainty intervals are strictly audited and distinguished: Frequentist Confidence Intervals (bootstrap match sampling), Bayesian Credible Intervals (posterior distributions), and Descriptive Cross-Player Distributions (league quantiles).
6. **Master Decision Table & Three-Tier Evaluation (Task 6):** 14/14 Mathematically Verified; 9 Approved, 5 Provisional, 0 Unresolved, 0 Rejected; Ready for Controlled M4 Execution.

**Milestone M3: APPROVED AND CLOSED, with five explicitly provisional methodological components.**
**Milestone M4: APPROVED — IMPLEMENTATION IN PROGRESS (M4.1 & M4.2 COMPLETED).** Human authorization was granted to execute Milestone M4 in a staged, modular sequence. Modules M4.1 (18/18 tests pass) and M4.2 (22/22 tests pass, combined 40/40 tests pass) are COMPLETED AND FULLY AUDITED. Modules M4.3 through M4.6 remain subject to sequential authorization. Zero player rankings, zero pressure scores, and zero full-dataset enrichments have been generated. Raw datasets remain 100% untouched.


## M4 Controlled Implementation Pilot (Phases M4.1, M4.2 & M4.3 Executed & Audited)

The authoritative architecture and execution plan is documented in:
- Master Pilot Plan: [udit_reports/M4_CONTROLLED_PILOT_PLAN.md](audit_reports/M4_CONTROLLED_PILOT_PLAN.md)
- M4.1 Input Validation Engine: [src/m4_pilot/input_validation.py](src/m4_pilot/input_validation.py)
- M4.1 Independent Test Suite: [	ests/m4_pilot/test_input_validation.py](tests/m4_pilot/test_input_validation.py) (18/18 tests PASS).
- M4.2 Pre-Delivery Match-State Engine: [src/m4_pilot/match_state_engine.py](src/m4_pilot/match_state_engine.py)
- M4.2 Independent Test Suite: [	ests/m4_pilot/test_match_state_engine.py](tests/m4_pilot/test_match_state_engine.py) (22/22 tests PASS).
- M4.2 Conformance Audit Report: [udit_reports/M4_2_MATCH_STATE_AUDIT.md](audit_reports/M4_2_MATCH_STATE_AUDIT.md)
- M4.2 Supplementary Early DLI Audit: [udit_reports/M4_2_EARLY_INNINGS_DLI_SUPPLEMENT.md](audit_reports/M4_2_EARLY_INNINGS_DLI_SUPPLEMENT.md)
- M4.3 Batter Performance Engine: [src/m4_pilot/batter_engine.py](src/m4_pilot/batter_engine.py)
- M4.3 Independent Test Suite: [	ests/m4_pilot/test_batter_engine.py](tests/m4_pilot/test_batter_engine.py) (22/22 tests PASS).
- M4.3 Master Audit Report: [udit_reports/M4_3_BATTER_ENGINE_AUDIT.md](audit_reports/M4_3_BATTER_ENGINE_AUDIT.md)
- M4.3 Supplementary Audit Report: [udit_reports/M4_3_BATTER_ENGINE_SUPPLEMENT.md](audit_reports/M4_3_BATTER_ENGINE_SUPPLEMENT.md)

Key Verified Implementation Pillars (M4.1, M4.2 & M4.3):
1. **Pilot Scope Restriction:** Strictly bounded to the existing 8-match hybrid enriched pilot dataset (data/enriched/pilot/enriched_ball_by_ball_pilot.csv, 1,994 deliveries). Full 784-match enrichment remains strictly out of scope.
2. **Schema & Integrity Verification:** Confirmed all 51 expected columns exist with zero duplicate primary keys (match_id, innings, overid, over_ball_num) and zero unexpected nulls across all mandatory fields.
3. **Causal Isolation Anti-Leakage Architecture:** Pre-delivery states (pre_*) use strictly shifted cumulative histories to prevent current-ball contamination. Validated via causal isolation perturbation tests.
4. **Legality & Run Accounting Reconciliation:** Delivery legality rule verified as ext_is_legal_delivery == ~(ext_is_wide | ext_is_noball). Batter runs off the bat computed canonically as ext_delivery_total_runs - (all extras), totaling 2,671 runs across 1,929 balls faced. Disposes Match 20181 Over 9 using canonical Cricsheet delivery runs (2 on ball 4, 1 on ball 5).
5. **Innings-Level Tactical Role Assignment (Issue 1 - CORRECTED):** Tactical roles assigned per player-innings via actual entry over ($\\le 6.0$ Top Order, .1\\text{--}13.0$ Middle Order, $> 13.0$ Finisher) using ssign_innings_roles(). Resolves ecological fallacy of mean_entry_over where 16/33 multi-innings batters varied roles across matches (e.g. Hetmyer entered in over 10 Middle, over 18 Finisher, and over 1 in Super Over). Multi-role floaters are compared against weighted situational priors, while preserving player-level modal primary roles for cohort Z-score standardization.
6. **Bootstrap Estimator Consistency & Percentile Interval Reconciliation (Issue 2 - CORRECTED):** Replaced uncentered pseudo Z-scores in ootstrap_batter_uncertainty() with exact canonical cohort standardization parameters ({\\text{mean}}, \\sigma_{\\text{reg}}$) matching compute_bppi_scores(). Recalculated 90% Percentile Bootstrap CI for Shimron Hetmyer (=1,000$, seed 42) is $[+0.3364, +1.2477]$, centrally containing the point estimate ($+0.9102$) and aligning with bootstrap median ($+0.9102$). Full reproducible diagnostic and 10-bin histogram documented in supplement; verified by 	est_22_bootstrap_estimator_consistency_and_percentile_coverage.
7. **Decoupled Uncertainty Intervals:** Formally distinguished Normal-approximation CIs, percentile bootstrap CIs, and Bayesian credible intervals.
8. **BPPI Formulations & Multicollinearity Diagnostics:** Calculated all 5 approved components (\\text{RA}/\\text{ball}: 0.35, \\Delta\\text{SR}: 0.25, \\Delta\\text{Bnd\\%}: 0.15, \\Delta\\text{Dot\\%}: 0.15, \\Delta\\text{Survival}: 0.10$). Multicollinearity diagnostics confirm healthy VIFs ($< 5.0$ across all 5 dimensions; \\text{RA}: 4.14, \\Delta\\text{SR}: 3.22, \\Delta\\text{Bnd\\%}: 4.07, \\Delta\\text{Dot\\%}: 1.51, \\Delta\\text{Survival}: 1.26$).
9. **Empirical Bayes Shrinkage Framework:** Beta-Binomial shrinkage applied to proportions ({\\text{dot}} = 135.8, M_{\\text{bnd}} = 114.7, M_{\\text{wkt}} = 90.0$); Normal-Normal rate shrinkage applied to continuous rates ({\\text{xRA}} = 38.2, K_{\\text{SR}} = 50.62$). Normal-Normal maintained strictly as **PROVISIONAL**.
10. **Eligibility Gate Preservation:** 0/102 batters qualified under approved thresholds ($\\ge 12$ innings, $\\ge 120$ balls, $\\ge 36$ pressure balls). Every player has explicit exclusion reasons recorded.
11. **Raw Dataset Immutability Confirmed:** SHA-256 hashes for all 8 raw source CSVs, original archive, and pilot dataset re-verified bitwise identical.
12. **Zero Rankings / Zero Final Scores:** Hardcoded pipeline safeguards prevent ranking generation or pressure score publication.

**M4.1, M4.2 & M4.3 STATUS: COMPLETED, FULLY AUDITED & FORMALLY CLOSED — 62/62 UNIT TESTS PASS (M4.1: 18/18, M4.2: 22/22, M4.3: 22/22).** Module M4.4 strictly BLOCKED awaiting human review and explicit authorization.
