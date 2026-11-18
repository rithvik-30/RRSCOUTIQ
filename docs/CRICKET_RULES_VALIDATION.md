# RR ScoutIQ - Cricket Rules and Dataset Convention Validation

## Purpose and status vocabulary

This is the M2 rules-and-data validation record for the six supplied CSVs. It
separates (1) what the source files literally contain, (2) what cricket rules
say, and (3) what the provider's fields mean. A cricket rule does not establish
how a particular event is encoded in `ball_by_ball.csv`.

Statuses apply to the stated proposition:

- **CONFIRMED** - the fact is directly supported by the source data and,
  where applicable, the cricket rule. For provider semantics, direct provider
  documentation or sufficiently strong independent validation is required for
  the scope of the stated conclusion.
- **PROBABLE** - the source pattern and any partial independent corroboration
  support the interpretation, but provider documentation or validation across
  the relevant dataset scope is absent.
- **UNRESOLVED** - available data and rule references do not establish the
  interpretation.
- **NOT APPLICABLE** - the event/field is not represented in this supplied
  dataset or is not relevant to the stated calculation.

No player-performance calculation, ranking, or pressure method is implemented
or approved here. In particular, do not treat an empty field as zero.

## Evidence generated from the source files

The read-only evidence generator is [`../src/rules_validation.py`](../src/rules_validation.py).
It reads raw CSV values with pandas `keep_default_na=False`; thus the literal
text `None` in `extras_type` is retained and is not conflated with an empty CSV
cell. Its outputs are:

- [`../audit_reports/rules_validation/field_distributions.csv`](../audit_reports/rules_validation/field_distributions.csv) -
  frequency distributions for the fields examined here. Timestamp values are
  represented by suffix and rows-per-distinct-timestamp distributions because
  almost every timestamp is unique.
- [`../audit_reports/rules_validation/representative_delivery_records.csv`](../audit_reports/rules_validation/representative_delivery_records.csv) -
  source-row examples, including all 31 distinct extras/runs/boundary
  combinations, all six `Retire Out` records, all 13 wicket/ID disagreements,
  boundary-flag disagreements, all negative and >200 speed values, and
  timestamp order examples.
- [`../audit_reports/rules_validation/representative_lineup_records.csv`](../audit_reports/rules_validation/representative_lineup_records.csv) -
  raw status values and all repeated `(match_id, team_id, player_id)` rows.
- [`../audit_reports/rules_validation/representative_match_records.csv`](../audit_reports/rules_validation/representative_match_records.csv) -
  all 119 zero-coded player-of-the-match rows and rows with revised target/overs.
- [`../audit_reports/rules_validation/interpretation_tests.csv`](../audit_reports/rules_validation/interpretation_tests.csv) -
  reproducible checks and their bounded interpretations.
- [`../audit_reports/rules_validation/source_sha256.csv`](../audit_reports/rules_validation/source_sha256.csv) -
  SHA-256 digests of the six source CSVs at report generation.
- [`../src/provider_investigation.py`](../src/provider_investigation.py) -
  read-only reproducible analysis for provider-specific run/extras patterns
  and one independent scorecard comparison.
- [`../audit_reports/rules_validation/provider_investigation/`](../audit_reports/rules_validation/provider_investigation/) -
  provider-search log, raw cross-tabulations, exact `wide`/`Overstep` source
  rows, scorecard reconciliation, and evidence summary.
- [`../src/extras_legal_delivery_validation.py`](../src/extras_legal_delivery_validation.py) -
  read-only M2.2C analysis of all extras combinations, scorecard comparisons,
  candidate legal-ball counts, and bowler-run data sufficiency.
- [`../audit_reports/rules_validation/extras_legal_delivery/`](../audit_reports/rules_validation/extras_legal_delivery/) -
  M2.2C combination frequencies, representative source records, scorecard
  evidence, candidate delivery counts, bowler-run investigation, and hashes.

`source_csv_row` is the CSV/Excel row number including the header;
`dataframe_index` is the zero-based pandas row index. Representative files
retain only fields present in their source CSV. Full frequency distributions
and exact locators are in the linked CSVs rather than being repeated in full
here.

## Authoritative rule references

MCC states it is the custodian and drafter of the Laws; it also cautions that
playing conditions can vary from the Laws. The dataset includes T20 and T20I
matches, and the historical competition-specific playing conditions have not
been collected for every match. Therefore, law summaries below are rule
references, not proof of provider encoding or of which historical competition
addendum applied.

1. [MCC - About the Laws of Cricket](https://www.lords.org/mcc/about-the-laws-of-cricket)
   identifies MCC as custodian and explains the distinction between Laws and
   playing regulations. The MCC edition index lists the **2017 Code, 3rd
   Edition (2022)**; use the edition and applicable playing conditions in force
   for each match before implementing a rule.
2. [MCC Law 17 - The Over](https://lawsofcricket.lords.org/laws-of-cricket/the-over)
   says only valid balls count towards the six-ball over; the corresponding
   provisions on valid balls exclude a No ball and a Wide.
3. [MCC Law 18 - Scoring Runs](https://lawsofcricket.lords.org/laws-of-cricket/the-over-scoring-runs-dead-ball-and-extras/scoring-runs)
   distinguishes runs scored from the bat from other scoring categories and
   governs scoring/attribution. Law 18 does not define the provider's columns
   or RR ScoutIQ's statistical metrics.
4. MCC Law 19 (Boundaries), Law 21 (No ball), Law 22 (Wide ball), Law 25
   (Batter's innings, including retirement), and Laws 32-39 (the named modes
   of dismissal below) are relevant to the candidate interpretations.
5. [ICC Playing Conditions index](https://www.icc-cricket.com/about/cricket/rules-and-regulations/playing-conditions)
   currently lists, among other documents, the ICC Men's T20I Playing
   Conditions - October 2026. That document is relevant only where its scope
   and effective date apply; it does not retroactively establish the conditions
   for every supplied T20 or T20I record.

The current MCC online-law routes are cited for navigation; the official Laws
edition and the historical ICC/competition conditions applicable to each match
must be checked before translating these rules into source-row flags.
During this review, the MCC law-reader page returned an access error and the
ICC PDF opened without readable page text in the browser. The MCC source
references below identify rule numbers and the official edition/index; no
historical ICC playing-condition clause has been independently applied to a
specific match. This access limitation is another reason to require a
domain-reviewed check before implementing calculations.

## Provider provenance and independent scorecard check

The archive, problem-statement PDF, local documentation, and web searches for
the raw field names did not identify the original data provider or a provider
data dictionary. The problem statement establishes the competition scope
(historical IPL/T20I data from 2022 onward), not the column definitions. The
exact searches and outcomes are recorded in
[`../audit_reports/rules_validation/provider_investigation/provider_search_results.md`](../audit_reports/rules_validation/provider_investigation/provider_search_results.md).
Search-result checks are not proof that no provider documentation exists.

An independent Cricbuzz scorecard was available for match 14113 (Rajasthan
Royals v Lucknow Super Giants, 2022-04-10). Its
[scorecard](https://www.cricbuzz.com/live-cricket-scorecard/45981/rr-vs-lsg-20th-match-indian-premier-league-2022)
reports 165/6 and 162/8 in 20 overs, with extras of 9 (3 leg-byes, 6 wides)
and 5 (1 leg-bye, 4 wides). In the source CSV, the `runs` sums are 156 and 157,
matching the scorecard batter-run totals, while not matching team totals. There
are 6 and 8 source wicket flags, matching the scorecard wickets. There are 126
and 124 stored deliveries; excluding the 6 and 4 `wide`-labeled rows leaves
120 candidate valid balls per innings, matching 20 six-ball overs. Neither
innings contains `Overstep`.

This is a real external reconciliation for both innings of one match, not
provider documentation or validation across the full dataset. It supports the
interpretations below without proving that all provider events are encoded the
same way. Full source row ranges, raw category frequencies, and comparison
fields are in `scorecard_reconciliation.csv`; the complete row-level `wide`
and `Overstep` records are in `wide_overstep_examples.csv`.

## A. Runs and extras

### `runs`

- **Observed values:** `0` 79,387; `1` 72,267; `2` 12,547; `3` 656; `4`
  23,303; `5` 25; `6` 12,814 (200,999 total). See the full distribution and
  representative rows in the evidence files above.
- **Observed examples:** run values 0-6 occur with literal `extras_type=None`;
  `wide` rows have `runs=0`; `Overstep` rows include several values from 0-6.
- **Rule reference:** MCC Law 18 distinguishes runs credited from the bat and
  other scoring categories. MCC Laws 19 and 21-22 govern boundary and illegal
  delivery situations.
- **Independent validation:** in match 14113, innings sums are 156 and 157;
  the independent scorecard's batter-run totals are 156 and 157, while team
  totals are 165 and 162. Scorecard extras account for the difference.
- **Status: PROBABLE** as batter runs dataset-wide. The match provides strong
  corroboration for two complete innings, but no provider definition or
  cross-competition validation is available. It is not a team-total field in
  this tested match. Do not treat this sample as confirmation of every
  exceptional extras encoding or use it alone to approve performance
  calculations.

### `extras1_runs`

- **Observed values:** 6: 189,167; 2: 7,714; 3: 2,748; 1: 576; 4: 529; 5:
  264; 7: 1.
- **Observed relationship:** each of the seven raw `extras_type` values maps
  to exactly one `extras1_runs` value in this file: literal `None` -> 6,
  `wide` -> 2, `legbyes` -> 3, `Overstep` -> 1, `byes` -> 4, `other` -> 5,
  `Penalty` -> 7. These values are category-correlated, not run totals that
  have been independently validated.
- **Scorecard check:** in match 14113 the scorecard records wides and
  leg-byes, while `extras1_runs` takes the constant category-associated values
  2 and 3 on those labels and 6 on ordinary `None` rows. It is not an
  interpreted scorecard extras amount.
- **Representative records:** all distinct combinations, including
  `Overstep` examples at source rows 497, 1,231, 1,487, 4,189, and 5,837, are
  in `representative_delivery_records.csv`.
- **Status: PROBABLE** that this behaves like a numeric category/code field
  rather than an amount of runs, because each value is fixed one-to-one with a
  label and includes `None -> 6`. The code meanings and whether it is an
  identifier or another category field remain unresolved. Never sum it as
  extras or runs.

### `extras_2_runs`

- **Observed values:** 0: 200,963; 1: 20; 4: 16. All 36 nonzero cases are
  represented in the distinct-combination source examples.
- **Observed examples:** nonzero values occur with `extras_type=None`,
  `Overstep`, and `other`; they do not define a consistent relationship to
  `runs` from the available columns.
- **Independent check:** `extras_2_runs` sums to zero in both innings of match
  14113 despite scorecard extras of 9 and 5. This disproves its use as the
  complete extras total in those innings; it does not identify its actual
  meaning.
- **Status: UNRESOLVED.** Its name is not sufficient proof that it is a
  numeric extras amount. Do not add it to or subtract it from any other field.

### `extras_type`

- **Raw observed values:** literal text `None`: 189,167; `wide`: 7,714;
  `legbyes`: 2,748; `Overstep`: 576; `byes`: 529; `other`: 264; `Penalty`: 1.
  There are no empty cells in this column in the source.
- **Status:** **CONFIRMED** as a distribution of literal source labels;
  **UNRESOLVED** as a provider-defined event taxonomy. In particular, `None`
  is literal text, not an actual missing value. Preserve it until the provider
  defines it.

### `wide`

- **Observed pattern:** all 7,714 rows labeled `wide` have
  `(extras1_runs, extras_2_runs, runs, is_four, is_six) = (2, 0, 0, False,
  False)`. Examples include source rows 41 and 45. Wide-labeled rows also
  include `Stump` and `RunOut` labels, e.g. source row 3,243 has `Stump`.
- **Rule reference:** MCC Law 22 defines a Wide and its treatment; under Law
  17 a Wide does not count as a valid ball.
- **Independent check:** in match 14113, the numbers of `wide` rows (6 and 4)
  match the scorecard wide totals, and excluding those rows yields 120
  candidate valid deliveries in each 20-over innings. This supports the
  `wide` mapping in this match only.
- **Status: PROBABLE** that provider label `wide` denotes an MCC-style Wide
  event; **CONFIRMED** that a Wide is not a valid ball under the cited Laws.
  Do not convert the label into a validated run amount: the observed
  `extras1_runs=2` does not match the ordinary one-run Wide penalty as a simple
  numeric amount, reinforcing that its field semantics are not clear.

### `Overstep`

- **Observed pattern:** 576 rows, all with `extras1_runs=1`. The eight distinct
  combinations of `extras_2_runs`, `runs`, and boundary flags, including
  runs 0-4 and 6, are enumerated in
  [`field_distributions.csv`](../audit_reports/rules_validation/field_distributions.csv)
  and represented by source rows 497, 1,231, 1,487, 4,189, 5,837, 12,979,
  24,455, and 44,695.
- The source calls this observed category `Overstep`; no provider reference
  was found establishing whether the term is provider-specific or what event
  it encodes.
- The source has no `no-ball` `extras_type` label and no explicit
  `is_no_ball`/legal-delivery flag.
- **Rule reference:** MCC Law 21 governs a No ball; MCC Law 17 determines
  valid-ball counting. The word “Overstep” alone is not the source's
  attestation that this is a No ball.
- **Status: UNRESOLVED.** Do not treat `Overstep` as a No ball or infer legal
  balls from it without provider confirmation.

## B. Legal deliveries

### Legal-ball identification

- **Rule:** under MCC Laws 17, 21, and 22, only valid deliveries count towards
  the six valid balls in an over; a No ball or Wide is not a valid ball.
- **Dataset evidence:** there is no explicit legal-ball flag. The only possible
  indicators are `extras_type` (with `wide` and `Overstep` labels) and the
  `overid`, `over_ball_num`, and `innings_ball_num` sequence fields.
- **Independent check:** excluding `wide` rows gives the scorecard's 120
  valid deliveries in both innings of match 14113, which had no `Overstep`
  rows. This validates only that match's candidate treatment.
- **Status:** **CONFIRMED** rule; **UNRESOLVED** dataset-wide legal-ball
  identification. The `wide` mapping is probable for the checked match, and
  `Overstep` mapping is unresolved. The source also has `other` and `Penalty`
  categories. Do not implement balls bowled, overs, or legal-delivery counts
  from the present fields.

### Over counting

- **Rule:** an over comprises six valid balls, not six attempted deliveries
  (MCC Law 17).
- **Observed fields:** `overid` ranges 1-20; `over_ball_num` ranges 1-13, with
  two records reaching 13. It is not a legal-ball count.
- **Status:** **CONFIRMED** rule; **UNRESOLVED** whether `overid` is a
  provider-normalized over label or how extras affect its increments. It must
  not be converted to legal balls without validation.

### Overstep and Wide handling

- **Rule:** a validly identified Wide or No ball does not count as one of the
  six valid balls (MCC Laws 17, 21, and 22).
- **Dataset evidence:** 7,714 `wide` rows share one stored pattern; 576
  `Overstep` rows span eight combinations, and there is no explicit no-ball
  label.
- **Status:** rule confirmed; `wide` encoding probable; `Overstep` and its
  legal-ball treatment unresolved.

### Innings ball numbering

- **Observed:** `innings_ball_num` increases from 1 without gaps or duplicates
  in source order within all 1,724 `(match_id, innings)` groups.
- **Status: PROBABLE** as the preferred stored-row sequence key. This confirms
  its internal continuity, not that it is a legally counted-ball number or
  independently verified event chronology.
- **Exception:** `delivery_ist_time` has 39 adjacent ties and four decreases
  within match/innings source order (source rows 5,630, 39,886, 68,477,
  199,829), so the timestamp cannot replace the sequence field as a reliable
  order without provider explanation.

## C. Bowling calculations

### Bowler-conceded runs

- MCC Law 18 governs scoring and attribution categories. The dataset's
  `runs`, `extras_type`, `extras1_runs`, and `extras_2_runs` do not yet identify
  a consistent total or bowler charge; for example, all Wide-labeled rows
  store `runs=0`, `extras1_runs=2`.
- **Status: UNRESOLVED.** No bowler-conceded-runs formula is approved. Required
  provider definitions include whether `runs` is batter/team/other runs, the
  meaning of `extras_2_runs`, and attribution for every extras category.
- **Implementation decision:** none. Do not sum, subtract, or impute any of
  these fields.

### Legal balls bowled

- MCC Laws 17, 21, and 22 provide the rule once No ball and Wide events are
  correctly identified.
- **Status: UNRESOLVED for this dataset** because `Overstep` has no verified
  mapping and no legal-delivery indicator exists.
- **Implementation decision:** none until provider event meanings and
  competition-specific conditions are confirmed. `over_ball_num` is not a
  substitute.

### Wickets credited to bowler

- MCC dismissal Laws identify modes of dismissal; a team-wicket or dismissal
  flag is not by itself a bowler-credit rule. Law 21 also limits which
  dismissals are possible from a No ball. The source does not identify legal
  delivery status reliably, and it has 13 disagreements between `is_wicket`
  and dismissed-player-ID presence.
- Observed non-bowler/exception candidates include `RunOut`, `Retire Out`, and
  `Obstructing the field`; do not count every `is_wicket=True` row as a
  bowler-credited wicket.
- **Status: UNRESOLVED** for the source metric. Exact bowler-credit policy
  requires the selected scorecard/statistical convention and validated
  provider dismissal/illegal-delivery encoding.
- **Implementation decision:** none. Keep team wickets, batter dismissals,
  and bowler-credited wickets as separate concepts.

### Economy rate

- Economy rate is a statistical measure, not a stand-alone MCC Law. Any
  calculation needs a validated bowler-conceded-runs numerator and a validated
  legal-balls denominator.
- **Status: UNRESOLVED.** No economy-rate formula is implemented or adopted.
  Do not treat missing, ambiguous, or sentinel values as zero.

## D. Batting calculations

### Batter runs

- MCC Law 18 provides conditional scoring attribution; the dataset's `runs`
  definition and its relationship to extras have not been established.
- **Status: UNRESOLVED.** No batter-run calculation is approved. The striker
  ID and `runs` column alone are not sufficient evidence.

### Balls faced and strike rate

- Balls faced and strike rate are statistical conventions, not defined by the
  MCC Laws as source-column formulas. Source rows do not contain a
  `balls_faced` or validated legal-delivery field.
- Whether a Wide or No ball counts as a ball faced must follow the chosen
  scorecard/statistical standard and verified provider signals.
- Strike rate therefore lacks both an approved batter-run numerator and
  balls-faced denominator.
- **Status: UNRESOLVED.** No balls-faced or strike-rate calculation is
  implemented.

### Batting average

- Batting average requires batter-run totals and a validated count of
  dismissals that count against the batter. `is_wicket`, `dismissal_type`, and
  `dismissed_player_id` are inconsistent on 13 rows; `Retire Out` and
  `Retired Hurt` require distinct treatment.
- **Status: UNRESOLVED.** No batting-average denominator or exceptional-case
  policy is approved. Missing dismissal IDs must not be changed to zero or
  inferred from striker/non-striker fields.

### Boundary calculations

- MCC Law 19 defines boundary scoring conditions. The source has `is_four`
  true on 23,283 rows and `is_six` true on 12,811 rows. Every true `is_four`
  row has `runs=4`, and every true `is_six` row has `runs=6`; conversely, 20
  rows with `runs=4` and 3 rows with `runs=6` have the corresponding flag
  false.
- **Status: PROBABLE** that the flags denote boundary-related events, but
  **UNRESOLVED** whether they are complete/canonical or how extras and boundary
  rules are reflected in `runs`.
- **Implementation decision:** none. Do not count boundaries from `runs=4/6`
  alone, and do not silently repair false flags.

## E. Dismissal rules

### All observed dismissal types

Nonempty `dismissal_type` frequencies in `ball_by_ball.csv`:

| Raw label | Rows | MCC rule family/reference | Dataset interpretation |
|---|---:|---|---|
| `Caught` | 7,557 | Law 33 | Label observed; event validity/credit not independently verified |
| `Bowled` | 1,775 | Law 32 | Label observed; event validity/credit not independently verified |
| `LBW` | 709 | Law 36 | Label observed; event validity/credit not independently verified |
| `RunOut` | 600 | Law 38 | Label observed; not to be conflated with bowler-credited wickets |
| `Stump` | 214 | Law 39 | Provider label is `Stump`; canonical mapping is probable, not specified |
| `Hit Wicket` | 17 | Law 35 | Label observed; event validity/credit not independently verified |
| `Retire Out` | 6 | Law 25.4 | MCC recognizes retirement as out under specified conditions; source event/identity still needs validation |
| `Obstructing the field` | 1 | Law 37 | Label observed; spelling differs from the other source spelling |
| `Obstracting the field` | 2 | Law 37, probable spelling variant | Likely misspelling/variant; not normalized |

The empty `dismissal_type` value occurs on 190,118 rows; it is not itself a
dismissal category. `dismissal_type_id` values are 1: 1,775; 2: 7,557; 3:
709; 4: 600; 5: 214; 6: 17; 9: 6; 10: 3; empty: 190,118. No supplied code
dictionary maps these IDs authoritatively to labels. In this extract the
observed ID/label pairs are 1/`Bowled`, 2/`Caught`, 3/`LBW`, 4/`RunOut`,
5/`Stump`, 6/`Hit Wicket`, 9/`Retire Out`, and 10/the two
`Obstracting` plus one `Obstructing` labels. Each observed ID has one label
pairing, but this remains an empirical mapping rather than an authoritative
code dictionary.

**Status:** raw labels and counts are **CONFIRMED**. Mapping to the laws is
**PROBABLE** from label names; exact provider coding, spelling normalization,
event validity, and bowler credit remain **UNRESOLVED**.

### `Retire Out`

- **Rule:** MCC Law 25.4 allows retirement and distinguishes a batter who
  retires for a reason other than injury/illness or another accepted cause;
  if the batter does not resume, the batter may be recorded as retired out
  under the Law's conditions. An actual source label does not prove those
  conditions were met.
- **Data:** six rows, all with `is_wicket=True`. Source row locators are
  7,905 (match 14113), 61,390 (20244), 66,623 (21585), 127,901 (40709),
  129,393 (40715), and 143,342 (41512). One, row 127,901, has no
  `dismissed_player_id`; in other records the player ID may differ from
  `striker_id`.
- **Status:** **CONFIRMED** that MCC Law 25.4 classifies a qualifying
  non-injury retirement that is not resumed as out; **UNRESOLVED** whether
  these provider records satisfy the Law's conditions and whether their player
  IDs are correctly assigned. Do not infer the retired batter from the
  striker, non-striker, or bowler.

### `RunOut`

- **Rule:** MCC Law 38 defines Run out. It is a distinct dismissal mode; a
  dismissal label alone does not establish who should receive a statistical
  bowling credit.
- **Data:** 600 rows labeled `RunOut`; some coincide with Wide/Overstep labels.
  Examples and exact source rows are in the representative-delivery report.
- **Status:** label/rule-family mapping **PROBABLE**; provider event and
  bowler-credit convention **UNRESOLVED**. Do not count every RunOut as a
  bowler wicket.

### `Retired Hurt`

- **Rule:** MCC Law 25.4 distinguishes an injured/ill batter's retirement and
  possible return from a retirement classified as out.
- **Data:** zero rows use case-insensitive `Retired Hurt` or
  `Retired_Hurt` in `dismissal_type`.
- **Status: NOT APPLICABLE** to observed dismissal rows. This does not rule
  out another provider encoding or prove no such event occurred outside the
  supplied fields.

### Other non-bowler dismissals

- **Observed candidate labels:** `Obstructing the field`/`Obstracting the
  field` (3 total) and `Retire Out` (6 total), plus `RunOut` (600). These are
  modes requiring separate statistical treatment; no universal bowler-credit
  formula is inferred here.
- **Other named categories:** Hit the ball twice, Timed out, and other Laws
  are not observed as `dismissal_type` labels. Do not treat absence of a label
  as proof that no equivalent event could be encoded differently.
- **Status:** legal modes can be referenced to MCC Laws 25, 34, 37, 38, and
  40; dataset mapping and metric treatment remain **UNRESOLVED**.

## F. Other dataset conventions

### `bowl_speed` units and sentinel values

- **Observed distribution:** 200,999 nonempty numeric values; 77,861 zeros;
  one negative (`-1`); 19 values above 200; minimum -1.0; median 91.7; 99th
  percentile 146.0; maximum 1456.1.
- **Exact known exception:** source row 6,758, match 14108, bowler Axar Patel
  (`bowler_id=2876`), value `-1`.
- **Examples:** zero and >200 values, including all 19 >200 records, are
  locatable in `representative_delivery_records.csv`.
- **Status: UNRESOLVED.** No unit, accepted range, missing-value code, or
  conversion is supported by the source or a cricket Law. Do not rescale,
  discard, or coerce zero/negative/outlier values.

### Innings and over fields

- `innings`: values 1: 105,727; 2: 95,234; 3: 25; 4: 13. Values 3 and 4
  appear in both T20 (15 and 11 rows) and T20I (10 and 2 rows). For example,
  match 34429 has innings 3 and 4 records; match 48029 has innings 3. This
  pattern may correspond to additional innings such as a tie-break, but the
  data alone does not establish that.
- `overid`: 1-20. `over_ball_num`: 1-13; two rows have value 13. It cannot
  stand alone for legal balls or over completion.
- `innings_ball_num`: no gaps/duplicates and starts at 1 in source order in
  all 1,724 match/innings groups. It is a consistent stored sequence, not a
  documented legal-ball count.
- **Status:** distributions **CONFIRMED**; format/event meanings and the
  over-numbering convention **UNRESOLVED**. Apply T20/T20I conditions for each
  match only after obtaining the applicable historical version.

### `playing_eleven` status fields

| Field | Observed values/frequencies |
|---|---|
| `is_played` | true 19,714; false 8,667 |
| `is_captain` | literal `true` 1,683; literal `false` 18,031; empty 8,667 |
| `is_wk` | literal `true` 1,675; literal `false` 18,039; empty 8,667 |
| `is_impact` | 1: 558; 0: 27,823 |
| `is_impact_off` | 1: 558; 0: 27,823 |
| `batting_order` | empty 8,678; observed values 1-13, with 7 rows at 13 |

The `is_impact` and `is_impact_off` values are equal on 27,265 of 28,381 rows
and differ on 1,116. The repeated candidate key `(match_id, team_id,
player_id)` also occurs in 75 rows across 35 groups with varying
`batting_order` (see the M1 investigation report and generated representative
lineup records).

**Status: UNRESOLVED.** Field names suggest roles/status but do not define
whether these fields mean selected, appeared, substituted, currently active,
or an impact-substitution state at a particular time. Do not use them to
determine an eligible XI or a batter's dismissal/participation without the
provider's schema.

### Zero-coded player-of-the-match

- **Observed:** `matches.man_of_the_match=0` on 119 of 883 match rows;
  nonzero values on 764. Zero does not map to a player in the supplied player
  mapping (M1 verified).
- **Status: UNRESOLVED.** It may be a placeholder, unknown, unawarded, or
  another feed code; do not convert it to missing or interpret it as a player.
- All 119 match rows and exact row locators are in
  `representative_match_records.csv`.

### `delivery_ist_time` timezone and ordering

- All 200,999 source strings end in literal `UTC`, despite the field name
  containing `ist`; all parse as timestamps when parsed explicitly as UTC.
- There are 200,826 distinct timestamps, 39 adjacent equal timestamp pairs,
  and four timestamp decreases within match/innings source order. The
  decreasing records are source rows 5,630, 39,886, 68,477, and 199,829.
- **Status:** suffix and parse result **CONFIRMED** as data observations;
  timezone intent, timestamp semantics, and chronological ordering
  **UNRESOLVED**. Do not use the timestamp to order deliveries or convert
  timezones based on the column name alone.

### Match targets and revised overs

- `matches.csv` has 23 populated `revised_target` values and 25 populated
  values in each of `first_inn_revised_overs` and
  `second_inn_revised_overs`; the three fields are empty on most match rows.
  There is no separate ordinary target column in the supplied match table.
- **Status: UNRESOLVED.** The scale/unit and effective point of revised values
  are undocumented. A populated target value alone does not reconstruct the
  target available before a delivery. Do not assume empty revised fields mean
  a standard full-length innings or a numeric zero.

## M2.2B multi-match scorecard evidence

The read-only reconciliation generator and complete source-row outputs are
listed in
[`../audit_reports/rules_validation/multi_match_reconciliation/reconciliation_report.md`](../audit_reports/rules_validation/multi_match_reconciliation/reconciliation_report.md).
Eight independent Cricbuzz scorecards were checked: four IPL matches from
2022-2025 and four T20Is from 2022, 2024, and 2025. The selected matches
include varied extras, `Overstep` rows, high scoring, ties, and Super Overs.
Every scorecard URL and exact local source row range appears in
`selected_matches.csv` and `scorecard_reconciliation.csv`.

In all 16 regulation innings:

- The local `runs` sum equals the scorecard team total minus the scorecard's
  published aggregate extras. This independently reproduces the scorecard
  batter-run subtotal, but does not define the provider field or any
  performance formula.
- The local `is_wicket=true` count equals the scorecard wicket count.
- The scorecard's overs are recorded for context. They are not used to infer
  legal deliveries or a row-exclusion rule.

Five matches are fully verified at match scope. Three matches are partially
verified only for their Super Over scope: match 40725 and match 34429 have
local innings 3-4 but the accessible scorecard pages expose only regulation
innings; match 28962's result reports two Super Overs but the local file has
no rows beyond innings 2. These limitations are detailed in
`unverified_matches.csv`.

Local `wide` and `Overstep` category-row counts are listed beside scorecard
aggregate wide and No-ball run values. These are not equivalent units. For
example, match 14094 innings 1 has one local `Overstep` row and two scorecard
No-ball runs; match 13513 innings 1 has the same difference. Matches where
counts align do not confirm a provider mapping. No `Overstep`-to-No-ball
mapping, extras-field formula, or legal-delivery convention is approved.
`extras1_runs` and `extras_2_runs` remain unresolved.

All six extracted CSV hashes match the existing M2 baseline manifest. The
original archive hash was captured and remained unchanged during the run. The
report's hash manifest is
`../audit_reports/rules_validation/multi_match_reconciliation/source_sha256.csv`.

## Validation status and implementation decisions

| Convention | Status | Implementation decision now |
|---|---|---|
| Preserve literal `None` separately from empty CSV values | CONFIRMED | Read with raw-value preservation (or equivalent explicit NA controls); retain both values unchanged. Required field: `extras_type`. Test: literal `None` count 189,167 and empty count 0. |
| MCC legal-ball rule | CONFIRMED as a rule only | A No ball/Wide is not one of the six valid balls (Laws 17, 21, 22). Do not compute a dataset `legal_ball` flag until each source event is mapped. |
| `wide` source mapping | PROBABLE (scorecard-aligned sample patterns; provider meaning not documented) | Keep raw label. Do not equate category-row counts with wide-run totals. No numeric extras formula. |
| `Overstep` source mapping | UNRESOLVED | Keep raw label; do not classify as No ball or infer legal status. |
| `innings_ball_num` stored sequence | PROBABLE | It may be used to reproduce the provided source order within match/innings after uniqueness/continuity assertions; it must not be called a legal-ball number or used alone to claim event chronology. |
| `runs` field meaning | PROBABLE as batter runs dataset-wide | In 16 regulation innings across eight IPL/T20I matches, the local sum equals scorecard team total minus scorecard extras. Preserve raw values; provider documentation and validation outside the sampled formats/seasons and exceptional innings are still absent. |
| `extras1_runs` field role | PROBABLE category/code field | Preserve the raw value; do not sum it as runs or extras. Code definitions remain unknown. |
| `extras_2_runs` field meaning | UNRESOLVED | Preserve the raw value; do not add/subtract it from other fields. |
| Runs/extras aggregation, bowler-conceded runs, legal balls, wicket credits, economy rate | UNRESOLVED | No formula or exceptional-case handling is approved. Required source definitions and validation examples are listed in sections A-C. |
| Batter runs, balls faced, strike rate, average, boundaries | UNRESOLVED (boundary flags PROBABLE) | No metric calculation. Confirm run attribution, facing/illegal-delivery convention, dismissal denominator, and flag completeness first. |
| `is_wicket` count vs team wickets | CONFIRMED in the 16 tested regulation innings | The local true-flag count equals the independent scorecard wicket count. This does not identify a dismissed player or establish bowler credit. Preserve raw labels and IDs; do not repair the 13 inconsistencies. |
| Speed, innings/over, lineup, award, timestamp conventions | UNRESOLVED | Preserve source values; no normalization, inference, or sentinel replacement. |

There are no confirmed RR ScoutIQ player-performance calculation conventions
yet. The M2.2B multi-match scorecard results strengthen evidence for `runs` and
the regulation-innings wicket counts, but do not establish provider-wide
definitions or approve calculations. The only immediate implementation rule
is raw-value preservation and reproducible source-row sequencing for
inspection. No batting, bowling, economy, or ranking calculation should be
implemented from this document.

## Human review and next investigation

1. Obtain the provider's data dictionary and a few source event/scorecard
   examples for `runs`, `extras1_runs`, `extras_2_runs`, `extras_type`,
   `Overstep`, and the `wide` records. Ask explicitly whether `extras1_runs`
   is an enum/code.
2. Obtain event-level legal-delivery and scoring semantics, especially how
   no-balls, wides, byes, leg-byes, penalty runs, and boundary runs are
   represented. The M2.2B scorecards provide multi-match corroboration, not
   event-level provider definitions; keep those evidence types separate.
3. Obtain the competition-specific T20/T20I playing conditions effective on
   each match date, including tie-break/additional-innings rules.
4. Request provider definitions for dismissal type IDs, player dismissed,
   bowler wicket credit, `Retire Out`, and the 12 rows with a dismissed ID but
   `is_wicket=False`.
5. Request the `bowl_speed` unit/range/sentinel convention, lineup-field
   state timing, player-of-the-match zero meaning, and timestamp timezone/event
   semantics.
6. After domain review, add approved definitions and hand-calculable test
   cases. M2.2 remains in progress. M2.3 has since performed a structural
   match-state validation, but unresolved M2.2 run/extras/legal-delivery
   semantics still block reliable match-state reconstruction and metrics.

## M2.2D: wicket and dismissal validation

The read-only validation script is
[`../src/wicket_dismissal_validation.py`](../src/wicket_dismissal_validation.py).
Its reproducible outputs are in
[`../audit_reports/rules_validation/wicket_dismissal/`](../audit_reports/rules_validation/wicket_dismissal/).
The script preserves raw source strings, verifies all 13 known anomaly
locators, reconciles the already recorded scorecard totals, and checks the six
extracted CSVs and original archive against the M2.2C hash baseline.

### Source observations

The nine nonblank exact `dismissal_type` values and counts are: `Caught`
(7,557), `Bowled` (1,775), `LBW` (709), `RunOut` (600), `Stump` (214),
`Hit Wicket` (17), `Retire Out` (6), `Obstracting the field` (2), and
`Obstructing the field` (1). The empty value occurs 190,118 times. The source
has no `dismissed_player_name` column; names in the evidence are explicit
contextual lookups using competition, batting team, and player ID.

Of the empty-label rows, 190,106 have an empty dismissed-player ID and 12 have
a populated ID while `is_wicket=false`. There is one `is_wicket=true` record
with a missing dismissed-player ID: Excel source row 127,901 / DataFrame index
127,899, match 40709, innings 2, `Retire Out`. No player is inferred for it.
No zero-coded or literal-`None` dismissed-player IDs were found. All 13
previously flagged row/match pairs match the original CSV; no record was
modified.

### Rules vs provider interpretation

MCC Laws 25 and 32-40 name retirement and dismissal modes. These laws do not
define the provider's raw labels, ID dictionary, player-ID quality, or a
statistical bowler-credit field. As conventional statistical practice,
Bowled, Caught, LBW, Stumped, and Hit Wicket are **PROBABLE** bowler-credit
categories; RunOut, Retire Out, and exact `Obstructing the field` are
**PROBABLE** non-credit categories. These are not provider-confirmed. The
source's `Stump` to Stumped mapping is **PROBABLE** only. The spelling
`Obstracting the field` remains **UNRESOLVED** and is not normalized, even
though it shares dismissal_type_id 10 with the exact spelling.

The source has six `Retire Out` rows, all with `is_wicket=true`; five have a
dismissed-player ID and one does not. This confirms observed encoding, not
that each event satisfies the relevant Law conditions. Exact categories
`Caught and Bowled`, `Retired Hurt`, `Handled the Ball`, and `Timed Out` were
not observed and are **NOT APPLICABLE** to this extract's observed category
list, not proof those events never occurred.

### Independent reconciliation and implementation decision

The selected M2.2A/B evidence has 18 regulation innings where local
`is_wicket=true` counts equal scorecard team-wicket totals. This is
**CONFIRMED** for those aggregate comparisons only. In match 14094, innings 1,
all five local dismissed-player lookups and dismissal labels match the
Cricbuzz scorecard; its five team wickets include four bowling wickets, with
the local RunOut corresponding to the non-bowler-credit event. The detailed
comparison is limited to this one innings. Sources and row-level values are
recorded in `match_wicket_reconciliation.csv`.

**Implementation decision:** no batter-dismissal denominator or
bowler-wicket calculation is approved. Keep team wickets, player-dismissal
identity, and bowler credit separate. `is_wicket` aggregate matching does not
resolve the 13 row-level inconsistencies or establish provider-wide
semantics. M2.2D and overall M2.2 remain **IN PROGRESS**; M2.3 match-state
reconstruction had **NOT STARTED at the time this M2.2D record was written**.

## M2.2C: extras and legal-delivery validation

The M2.2C analysis reads original CSVs as strings with
`keep_default_na=False`; it preserves literal `None` separately from empty
cells. It leaves all source records unchanged and verifies the six CSV hashes
against the existing M2 manifest and the archive hash against M2.2B. It
accounts for all 31 observed combinations across all 200,999 delivery rows.
Evidence CSVs include representative source row numbers, match IDs, innings,
delivery/player fields, and scorecard URLs.

### Extras fields and category labels

Observed `extras_type` row counts are:

| Raw value | Rows | Status of provider interpretation |
|---|---:|---|
| Literal `None` | 189,167 | UNRESOLVED |
| `wide` | 7,714 | PROBABLE as a wide-related event label; not a run amount |
| `legbyes` | 2,748 | UNRESOLVED |
| `Overstep` | 576 | UNRESOLVED; not identified as a No ball |
| `byes` | 529 | UNRESOLVED |
| `other` | 264 | UNRESOLVED |
| `Penalty` | 1 | UNRESOLVED |

`extras1_runs` is constant per category label (`None`=6, `wide`=2,
`legbyes`=3, `Overstep`=1, `byes`=4, `other`=5, `Penalty`=7). This is
**PROBABLE** evidence of a category/code field, but no provider documentation
defines the values. They are not approved as run amounts. `extras_2_runs` is
0 on 200,963 rows, 1 on 20, and 4 on 16. The 36 nonzero records occur with
literal `None` (1), `Overstep` (21), and `other` (14); each also has
`runs=0` and false boundary flags. This establishes only co-occurrence; its
meaning is **UNRESOLVED**.

There is no source `wide` boolean column. `wide` is one value in the
single-valued `extras_type` field. Thus `wide` and `Overstep` labels cannot
co-occur as two values in that same source field; separate nonzero
`extras_2_runs` values do not establish multiple awarded extras. M2.2B
scorecard checks still support `runs` as **PROBABLE** batter runs in
regulation-innings aggregate, not as a fully confirmed row-level field for
every extras situation.

### Wide and Overstep scorecard comparison

In 18 regulation innings from nine matches, wide-label row counts equalled
scorecard aggregate wide-run totals in 11 innings and differed in 7.
`Overstep` row counts equalled scorecard No-ball extras numerically in 14
innings and differed in 4. Those units are different (source event rows
versus scorecard runs); equality is not proof of mapping. Some scorecards
record No-ball extras where no `Overstep` row exists, and other source labels
also occur in innings with No-ball extras. Consequently, mapping `Overstep`
to No ball remains **UNRESOLVED**.

The comparison reports all selected match IDs, dates, competitions, innings,
scorecard sources/URLs, local source row ranges, raw category counts, and
source-row locators in `wide_overstep_analysis.csv`.

### Candidate legal-delivery counts

Scorecard over notation was converted to balls as completed overs × 6 plus
the partial-over ball count (not as a decimal number). Against the 18
aggregate scorecard totals:

| Candidate rule | Candidate counts matching scorecard |
|---|---:|
| Treat all recorded rows as balls | 1/18 |
| Exclude `extras_type=wide` rows | 9/18 |
| Exclude `wide` and `Overstep` rows | 14/18 |
| Exclude `wide`, `Overstep`, and `other` rows | 18/18 |

Excluding undocumented `other` happens to match the selected sample, but
does not validate that label as an illegal delivery. These are aggregate
comparisons, not delivery-level identification. The sample-fitted candidate
rules are not approved for calculations.

**Status: UNRESOLVED. Legal deliveries cannot be identified reliably from
the provided `extras_type` values or the absent `wide` boolean.** The data
has no explicit legal-ball or No-ball field; obtain provider definitions and
additional event-level validation before using legal-ball counts.

### Bowler-conceded runs

MCC [Law 18.10.3](https://lawsofcricket.lords.org/laws-of-cricket/the-over-scoring-runs-dead-ball-and-extras/scoring-runs)
states the bowler is debited with runs scored by the striker, No-ball extras,
and Wide runs. MCC [Law 17](https://lawsofcricket.lords.org/laws-of-cricket/the-over)
defines valid balls; the MCC Laws also address No balls (Law 21) and Wides
(Law 22). These are rule references only. The separate provider mappings
remain unverified. Under the cited bowler-debit rule, Byes, Leg byes, and
Penalty runs are not included among the listed debits, but the source labels
and amounts have not been independently defined.

`runs` is **PROBABLE** as batter runs at innings scope; `extras1_runs` is
**PROBABLE** as a code-like field; the `wide` category is **PROBABLE** as an
event label. `extras_2_runs`, `Overstep`, `other`, and delivery-level extra
amounts remain **UNRESOLVED**. Aggregate scorecard extras cannot be allocated
to a particular delivery or bowler. **No reliable bowler-conceded-runs
formula can be calculated from the current validated fields; no formula is
implemented.**

### M2.2C convention and implementation statuses

| Convention | Status | Implementation decision |
|---|---|---|
| All 31 observed six-field combinations account for the source rows | CONFIRMED | Keep complete raw combination table and exact representative locators; do not transform source rows. |
| Physical source `wide` column exists | NOT APPLICABLE | It is absent. Preserve `extras_type`; do not rename a derived label test as a source column. |
| `runs` as batter runs | PROBABLE | May be described as innings-level scorecard corroboration only; no new performance formula. |
| `extras1_runs` is code-like | PROBABLE | Preserve the raw integer; do not aggregate as runs. |
| `extras_2_runs` is an additional extras amount | UNRESOLVED | Preserve; do not add/subtract it. |
| `extras_type=wide` marks a wide-related event | PROBABLE | Retain raw label; do not use row count as wide runs or legal-ball rule. |
| `Overstep` means No ball | UNRESOLVED | Do not map or use as a legality filter. |
| `other` denotes an illegal delivery | UNRESOLVED | Do not exclude it from legal-ball calculations. |
| Delivery-level legal-ball identification | UNRESOLVED | No legal-ball formula or flag. |
| Bowler-conceded runs from supplied source fields | UNRESOLVED | Do not implement a formula; obtain provider definitions/event-level run attribution. |
| MCC bowler-debit categories when event types are known | CONFIRMED as a cricket rule only | Apply only after provider categories and amounts are validated. |

M2.2C is complete as an investigation of the requested evidence, but the
essential provider conventions remain unresolved. M2.2 remains **IN
PROGRESS**; this addendum does not approve any batting/bowling metric,
ranking, pressure score, or downstream implementation.

## M2.3: innings and match-state reconstruction validation

The read-only generator is
[`../src/match_state_validation.py`](../src/match_state_validation.py). The
audited output bundle is
[`../audit_reports/rules_validation/match_state/`](../audit_reports/rules_validation/match_state/),
with the main report at
[`../audit_reports/rules_validation/match_state/match_state_validation_report.md`](../audit_reports/rules_validation/match_state/match_state_validation_report.md).
The completion audit read every generated CSV, checked the implementation
against its output, independently recomputed source hashes, fixed an innings
final-wicket report aggregation defect, and regenerated the existing outputs.
It did not create an alternate report set or modify source data.

### Findings

- **CONFIRMED:** 200,999 delivery records form 1,724 match/innings groups;
  raw label counts across distinct matches are 1: 867, 2: 845, 3: 6, 4: 6.
  Each group has one batting and one bowling team, both distinct and among the
  match participants.
- **CONFIRMED:** all 1,724 `innings_ball_num` sequences are unique,
  contiguous from 1, and in source-row order. `overid` and
  `(overid, over_ball_num)` are non-decreasing in that order. This validates
  reproducing stored order, not actual chronology or legal-ball numbering.
- **CONFIRMED:** all timestamps parse; there are 39 adjacent timestamp ties
  and four within-innings decreases. `over_ball_num > 6` occurs on 8,429
  rows. Use `(match_id, innings, innings_ball_num)` to reproduce stored
  sequence, with source row retained for audit; timestamp and over-ball
  semantics remain unresolved.
- **CONFIRMED as arithmetic:** cumulative raw `runs` and `is_wicket` flag
  sums before/after each delivery are calculated in stored order. They do not
  constitute team score or validated dismissal identity.
- **PARTIAL MATCH:** the 18 innings with retained scorecard evidence match on
  local `runs` subtotal versus scorecard batter runs and final source wicket
  flags versus scorecard wickets, with retained row-range and batting-team
  checks. They are not exact team-score comparisons because no validated
  local team-total field exists. The other 1,706 innings are unverifiable
  against a retained scorecard; there are no mismatches in the 18 tested
  innings.
- **PROBABLE:** labels 1/2 represent the two regulation innings in the
  selected scorecard sample; `runs` is a batter-run subtotal at innings
  scope; source `is_wicket` progression represents team-wicket progression
  for the selected reconciled sample.
- **UNRESOLVED:** labels 3/4 as Super Overs generally; completeness of
  one-innings scopes; provider semantics of timestamp/over fields;
  per-delivery team score and extras allocation; legal balls, overs completed
  and balls remaining; ordinary local targets; runs/current/required run
  rates; revised/interrupted chase state; and team-wicket semantics outside
  the sampled scorecards.
- **NOT APPLICABLE:** first-innings par or expected-scoring trajectory is not
  defined or implemented in M2.3.

All 16 matches without delivery rows have `Match Abandoned`. Twenty-two
delivered matches lack one of innings labels 1/2: 19 have `No Result` and
three `Match Abandoned`. The anomaly file retains these coverage scopes
without treating them as complete innings. Additional labels 3/4 occur in
six matches each; they are recorded as additional raw labels, not
automatically called Super Overs.

`matches.csv` has 23 populated `revised_target` values and 25 populated
values in each revised-overs field. The script preserves these as raw values,
flags D/L or DLS, No Result/Abandoned, and populated revision fields, and
does not interpret units or effective timing. Nine ordinary target
references are shown from independently checked scorecards only; they are
not local pre-delivery target state. No unsupported runs-required, balls-
remaining, current-run-rate, or required-run-rate values are produced.

### Status table and calculation gate

| State component | Status | Implementation gate |
|---|---|---|
| Raw innings label values / row groups | **CONFIRMED** | Retain labels and match/row coverage. |
| 1/2 as regulation innings | **PROBABLE** | Do not universalize beyond the independent sample. |
| 3/4 as Super Over | **UNRESOLVED** | Require per-match scorecard/competition evidence. |
| Stored order by innings sequence | **CONFIRMED** | May reproduce source order only; preserve source row. |
| Event chronology from timestamp | **UNRESOLVED** | Do not use as primary order. |
| Runs cumsum arithmetic | **CONFIRMED** | Raw field cumsum only; no team-score naming. |
| Cumulative team score | **UNRESOLVED** | Do not add `extras1_runs` or `extras_2_runs`; no total-run formula. |
| Wicket-flag cumsum arithmetic | **CONFIRMED** | Source flag progression only; do not infer bowler credit. |
| Team-wicket progression semantics | **PROBABLE in scorecard sample; UNRESOLVED elsewhere** | Preserve the M2.2D 13 anomalies and validate broader semantics. |
| Legal balls / overs / balls remaining | **UNRESOLVED** | No candidate exclusion rule is adopted. |
| Target/chase state and run rates | **UNRESOLVED** | External ordinary target references are sample evidence only. |
| First-innings par/trajectory | **NOT APPLICABLE** | No model or expected trajectory is implemented. |

### Source integrity and milestone status

All six extracted CSV hashes match the M1, M2.2B, M2.2C, and M2.3
manifests. The original archive hash matches the retained M2.2B and M2.2C
manifests. The M1 manifest contains only the six extracted CSV hashes; no M1
archive baseline is claimed.

**M2.3 remains IN PROGRESS.** The stored order and selected partial
scorecard checks are validated, but the central state needed for pressure
analysis—team score, legal-ball progress, targets and revised chase state—is
not reliable. M2.2 also remains in progress. Do not compute pressure scores,
player metrics, rankings, or trajectories from this validation.

## M2.2E: provider and scoring-encoding resolution

The read-only investigation is
[`../src/provider_encoding_resolution.py`](../src/provider_encoding_resolution.py).
Its generated evidence is in
[`../audit_reports/rules_validation/provider_encoding_resolution/`](../audit_reports/rules_validation/provider_encoding_resolution/).
The investigation reuses the already transcribed M2.2A/M2.2B scorecards,
checks their source ranges against the original CSV, preserves all prior
evidence, and does not modify the source ZIP or CSVs.

### Provider identification

**UNRESOLVED:** the dataset provider remains unidentified. The original ZIP
has an empty comment and contains six CSVs plus the hackathon problem PDF.
The PDF title identifies the problem statement, and its Google Docs renderer
metadata does not identify a data vendor. The repository and prior exact
searches contain no verifiable provider URL, data schema, API documentation,
or codebook. The exact queries and outcomes remain in
[`../audit_reports/rules_validation/provider_investigation/provider_search_results.md`](../audit_reports/rules_validation/provider_investigation/provider_search_results.md)
and the new
[`../audit_reports/rules_validation/provider_encoding_resolution/provider_identification_report.md`](../audit_reports/rules_validation/provider_encoding_resolution/provider_identification_report.md).

### Provider-field evidence classifications

| Field/convention | Status | Evidence and limitation |
|---|---|---|
| `runs` as batter runs | **PROBABLE** | Sums match scorecard batter-run subtotals in 18 regulation innings across nine T20/T20I matches. No provider definition; not a universal delivery-level guarantee. |
| Literal `extras_type=None` | **CONFIRMED as raw text; meaning UNRESOLVED** | 189,167 rows; retain the literal string separately from empty cells. |
| `extras1_runs` | **PROBABLE** code/category role | Each observed extras label has one corresponding code value (None=6, Overstep=1, Penalty=7, byes=4, legbyes=3, other=5, wide=2). This correlation does not supply a code dictionary or make it additive. |
| `extras_2_runs` | **UNRESOLVED** | Nonzero on 36 rows: 20 values of 1 and 16 of 4. No field definition or additivity rule. |
| Additivity of the run-named fields | **UNRESOLVED** | All three naive sums (`runs+extras1_runs`, `runs+extras_2_runs`, and all three fields summed) mismatch independently recorded team totals in all 18 selected innings. This rejects those naive sums in the sample, not all undocumented transformations. |
| `extras_type=wide` | **PROBABLE** wide-like label | 7,714 rows; source run/code patterns are included in the CSV evidence, but event rows are not wide-run units and no dedicated wide flag exists. |
| `extras_type=Overstep` | **UNRESOLVED** | 576 rows; no explicit No-ball field; do not identify it as a No ball. |
| `byes` / `legbyes` provider mapping | **UNRESOLVED** | Raw labels occur, but scorecard aggregates and category names do not verify source event mappings or amounts. |
| Penalty, `other`, and multiple-extras encoding | **UNRESOLVED** | Sparse/residual labels and 36 nonzero second-field records lack provider definitions. |
| Legal-delivery identification | **UNRESOLVED** | No dedicated legal-ball field. All-row counts matched scorecard overs 1/18, excluding wide 9/18, excluding wide and Overstep 14/18, and excluding wide/Overstep/other 18/18. The last is sample-fitted, not a rule. |
| Batter balls faced | **UNRESOLVED** | Striker-linked delivery rows are available, but legal/faced-delivery rules and retained player scorecard ball counts are unavailable. |
| Bowler runs conceded | **UNRESOLVED** | No verified delivery-level mapping for batter runs and bowler-charged extras; previous evidence lacks per-bowler scorecard figures. |

`extras_encoding_analysis.csv` includes all 31 observed combinations, their
counts, raw numeric-field arithmetic (explicitly descriptive only), sample
match/innings values, and representative source-row locators. The
`batter_balls_faced_analysis.csv` and
`bowler_runs_conceded_analysis.csv` files contain raw/candidate counts, not
validated performance statistics. No strike rates or economy rates are
calculated.

### Independent comparisons and cricket rules

The 18 retained scorecard innings cover IPL T20 and T20I across 2022–2025.
Aggregate local `runs` equals scorecard batter runs in 18/18; source wicket
counts equal scorecard team wickets in 18/18. These are exact comparisons of
those two dimensions only; overall innings status is **PARTIAL MATCH** because
the local team total and extras allocation cannot be reconstructed. Candidate
legal-ball count matches are **PARTIAL MATCH** only; a matching count does not
establish which delivery rows are legal. Event-row counts compared with
scorecard extras-run amounts are **UNVERIFIABLE** because the units are not
validated. Batter balls faced, bowler runs conceded, and bowler-creditable
wickets are **UNVERIFIABLE** from retained scorecards. New browser access to
scorecard and MCC pages failed, so no additional scorecard values were
transcribed.

Official cricket law remains separate from the provider mapping:

- MCC [Law 17: The Over](https://lawsofcricket.lords.org/laws-of-cricket/the-over)
  governs valid balls in an over.
- MCC [Law 18: Scoring Runs](https://lawsofcricket.lords.org/laws-of-cricket/the-over-scoring-runs-dead-ball-and-extras/scoring-runs),
  including 18.10.3, describes bowler debits for striker runs, No-ball extras,
  and Wide runs; Byes and Leg byes are not among those listed debits when their
  event types are known. Penalty-run treatment depends on the relevant
  Law/event.
- ICC [Playing Conditions index](https://www.icc-cricket.com/about/cricket/rules-and-regulations/playing-conditions)
  is a starting point for competition-specific conditions; the applicable
  historical document was not verified for every selected match.

These laws do not establish that `Overstep`, `extras1_runs`, or
`extras_2_runs` represents any particular event. Do not add extras fields or
infer delivery legality from labels without provider/domain validation.

### Integrity and milestone status

All seven source hashes match the M2.3 baseline. The script verified the
18 scorecard row ranges, 134 representative extras rows, 647 batter-group
representative rows, and 535 bowler-group representative rows. It writes only
to the new M2.2E evidence directory; earlier M1/M2.2A–D/M2.3 reports remain
intact.

**M2.2E remains IN PROGRESS. Overall M2.2 remains IN PROGRESS.** Provider
identity, extras code meanings, `extras_2_runs`, No-ball mapping, legal balls,
batter balls faced, and bowler-conceded runs are essential unresolved
conventions. No downstream formula is approved.

## M3.1A: feature feasibility evidence

The separate read-only audit is
[`../src/feature_feasibility_audit.py`](../src/feature_feasibility_audit.py);
its reports and consolidated matrix are in
[`../audit_reports/feature_feasibility/`](../audit_reports/feature_feasibility/).
It does not upgrade the M2.2/M2.3 provider or match-state findings.

- **CONFIRMED:** `innings_ball_num` reproduces stored source order in all
  1,724 match/innings groups; contextual striker, non-striker, bowler, and
  populated dismissed-player IDs/names map to the supplied player map.
- **PROBABLE:** innings labels 1/2 are regulation innings in selected
  scorecard cases; `runs` represents batter-run subtotal at aggregate innings
  scope; `is_wicket` matches scorecard team-wicket totals in the selected
  18-innings sample. None of these observations confirms provider-wide
  semantics.
- **CONDITIONAL:** prior-row cumsum of raw `is_wicket` is arithmetically
  reproducible in stored order, but team-wicket interpretation remains
  limited by the 13 M2.2D anomalies and selected scorecards.
- **UNRESOLVED:** actual legal balls/overs, phase boundaries, labels 3/4
  event meanings, balls faced, player-level batting runs, bowler-credit
  wickets, and every derived pressure context. No calculated metric is
  authorized by the audit.
- **NOT APPLICABLE:** absent standard dismissal labels remain absent; no
  source events are synthesized for them.

MCC Laws 17, 21, and 22 remain rule references for valid-ball treatment after
the delivery event is known. They do not prove this provider's Wide/No-ball
encoding or balls-faced convention. The existing M2.2D category assessments
remain probable/unresolved by dismissal type; bowler-credit counts are not
calculated. Preserve raw rows, the 13 wicket/player-ID inconsistencies, and
the distinction between team wickets and bowler-creditable wickets.

M3.1A is complete as a feasibility investigation only. M2.2 and M2.3 remain
in progress, and no feature, pressure definition, performance formula, or
ranking methodology is approved.

`playing_eleven.is_played`, `batting_order`, and impact-field semantics/timing
remain **UNRESOLVED**. Five lineup IDs are unmapped (all with raw
`is_played=false`); 75 rows repeat the lineup candidate key in 35 groups. Do
not infer actual match participation or eligibility from these flags.
