# RR ScoutIQ - Cricket Data Schema and Observed Semantics

## Purpose and evidence levels

This document records the structure and relationships observed in the six
supplied CSVs for M2.1. It is not a cricket-law reference or a provider data
dictionary. Field meanings inferred from names are described as candidate
interpretations only. Unresolved items must not be encoded as assumptions.

Detailed column-level information is in
[`DATA_DICTIONARY.md`](DATA_DICTIONARY.md). M1 anomaly decisions and source
record locators are in
[`TECHNICAL_DECISIONS.md`](TECHNICAL_DECISIONS.md) and
[`../audit_reports/anomaly_investigation/anomaly_investigation_report.md`](../audit_reports/anomaly_investigation/anomaly_investigation_report.md).

## Supplied files and observed grain

| Dataset | Rows | Candidate grain / observed key |
|---|---:|---|
| `ball_by_ball.csv` | 200,999 | One recorded delivery/event row; `(match_id, innings, overid, over_ball_num)` is unique in this file. |
| `matches.csv` | 883 | One row per `match_id`; all 883 IDs are unique. |
| `playing_eleven.csv` | 28,381 | Match/team/player lineup-like rows; `(match_id, team_id, player_id)` repeats for 75 rows across 35 groups. |
| `competition_team_player_mapping.csv` | 6,413 | Competition/team/player/name relation; `(comp_id, team_id, player_id)` is unique. |
| `teams.csv` | 353 | Competition/team/name relation; `(comp_id, team_id)` is unique. |
| `competitions.csv` | 141 | One row per `comp_id`; ID is unique. |

These are observed candidate grains, not guarantees from a provider contract.

## Relationship diagram

```text
competitions.comp_id
    |-- matches.comp_id
    |       |-- matches.match_id -- ball_by_ball.match_id
    |       `-- matches.match_id -- playing_eleven.match_id
    |
    |-- teams.(comp_id, team_id)
    |       |-- matches.(comp_id, home_team_id / away_team_id)
    |       |-- ball_by_ball.(comp_id via match, batting_team_id /
    |       |                                    bowling_team_id)
    |       `-- playing_eleven.(comp_id via match, team_id)
    |
    `-- competition_team_player_mapping.(comp_id, team_id, player_id)
            |-- ball_by_ball player IDs and name labels, in match/team context
            `-- playing_eleven.(comp_id via match, team_id, player_id)
```

`comp_id` is obtained for delivery and playing-eleven rows by joining their
`match_id` to `matches.csv`. Team and player IDs must be scoped to that
competition/team context; name text alone is not a safe key.

## Observed relationship validation

- Every `matches.comp_id` maps to a `competitions.comp_id`.
- Three competitions in `competitions.csv` have no match rows in the supplied
  `matches.csv`: IDs **2940**, **3405**, and **3473**. Their presence does not
  establish whether the match file is incomplete or these are future/metadata-only
  competitions.
- Every match home/away `(comp_id, team_id)` pair maps to `teams.csv`.
- Every distinct delivery batting/bowling team-context pair checked maps to
  `teams.csv`.
- `teams.csv` has 353 unique `(comp_id, team_id)` keys. Every
  `(comp_id, team_id)` in the player mapping has a team row.
- `matches.match_id` is unique. All delivery match IDs present in
  `ball_by_ball.csv` are present in `matches.csv`; 16 match records have no
  delivery rows, all with `result = Match Abandoned`.
- Three match records have no `playing_eleven.csv` rows; all are marked
  `Match Abandoned`. These three overlap the 16 delivery gaps.
- `competition_team_player_mapping.csv` has 1,217 player IDs and 1,210 distinct
  name strings. An ID maps to one name in the mapping file, but seven names are
  associated with multiple player IDs. Names alone are therefore not unique.
- All 888 distinct `striker_id`, 867 `non_striker_id`, 647 `bowler_id`, and 814
  non-null `dismissed_player_id` values appearing in ball-by-ball data occur
  in the player-ID mapping.
- In match/competition/team context, all 13,729 distinct observed
  striker/name tuples, 12,596 non-striker/name tuples, and 10,094 bowler/name
  tuples matched the corresponding mapping player and exact name label in the
  inspected source.
- Five `playing_eleven.csv` rows did not map to the player mapping by
  `(comp_id, team_id, player_id)`. All five have match IDs
  37086, 37090, 37093, 37098, and 37099 and share the key
  `(comp_id=2670, team_id=4444, player_id=29833)`. Their `is_played` is false
  and `batting_order` is missing. This may indicate a placeholder or an
  incomplete mapping, but its meaning is not documented. Exact rows are in the
  M1 player-coverage/anomaly files.
- The ball-by-ball schema contains `striker_name`, `non_striker_name`, and
  `bowler_name`, but no `dismissed_player_name`; dismissed names require a
  contextual lookup if needed.

## Delivery ordering observations

- `innings_ball_num` values are contiguous within each of the 1,724 observed
  `(match_id, innings)` groups: source order increases by exactly one, with no
  duplicate sequence values or gaps.
- In source order, `overid` is nondecreasing within each group. Its values are
  1 through 20 in the full dataset.
- `over_ball_num` resets as the over changes and reaches 13 in some rows.
  Consequently, it is not sufficient by itself to count legal balls; extra
  deliveries/over-numbering semantics need validation.
- `innings` has values 1, 2, 3, and 4 (200,999 rows total: 105,727; 95,234;
  25; and 13, respectively). Validate which formats/competitions permit those
  innings before constructing match states.
- `delivery_ist_time` is a string. Observed examples end in `UTC` despite
  `IST` in the field name. All 200,999 values parsed as timestamps during M1,
  but timezone and event-time meaning are unverified.

The sequence evidence supports ordering deliveries as stored for inspection;
it does not define the scoring state, legal-ball rules, or pressure state.

## Extras, runs, boundary, and wicket observations

Pandas' default CSV NA handling recognizes the raw text `None` as missing.
The source contains the literal text `None` in `extras_type` on **189,167**
rows; that text is distinct from an empty field. The `extras_investigation.csv`
preserves the source value.

### Observed marginal values

| Field | Observed value | Rows |
|---|---|---:|
| `extras_type` (raw literal) | `None` | 189,167 |
|  | `wide` | 7,714 |
|  | `legbyes` | 2,748 |
|  | `Overstep` | 576 |
|  | `byes` | 529 |
|  | `other` | 264 |
|  | `Penalty` | 1 |
| `extras1_runs` | `6` | 189,167 |
|  | `2` | 7,714 |
|  | `3` | 2,748 |
|  | `1` | 576 |
|  | `4` | 529 |
|  | `5` | 264 |
|  | `7` | 1 |
| `extras_2_runs` | `0` | 200,963 |
|  | `1` | 20 |
|  | `4` | 16 |
| `runs` | `0` | 79,387 |
|  | `1` | 72,267 |
|  | `2` | 12,547 |
|  | `3` | 656 |
|  | `4` | 23,303 |
|  | `5` | 25 |
|  | `6` | 12,814 |
| `is_wicket` | `False` | 190,118 |
|  | `True` | 10,881 |

These are stored-value frequencies, not a definition of whether a value is
batter runs, team runs, penalty runs, or another provider-specific field.

### Observed combinations

There are 31 distinct combinations of
`(extras_type, extras1_runs, extras_2_runs, runs, is_four, is_six)`.
Counts below treat raw `None` as a displayed missing-like category for
readability; the source itself contains the literal `None`.

| `extras_type` raw value | `extras1_runs` | `extras_2_runs` | `runs` | `is_four` | `is_six` | Rows |
|---|---:|---:|---:|---|---|---:|
| `None` | 6 | 0 | 0 | False | False | 68,028 |
| `None` | 6 | 0 | 1 | False | False | 72,043 |
| `None` | 6 | 0 | 2 | False | False | 12,496 |
| `None` | 6 | 0 | 3 | False | False | 653 |
| `None` | 6 | 0 | 4 | False | False | 20 |
| `None` | 6 | 0 | 4 | True | False | 23,160 |
| `None` | 6 | 0 | 5 | False | False | 25 |
| `None` | 6 | 0 | 6 | False | False | 3 |
| `None` | 6 | 0 | 6 | False | True | 12,738 |
| `None` | 6 | 1 | 0 | False | False | 1 |
| `wide` | 2 | 0 | 0 | False | False | 7,714 |
| `legbyes` | 3 | 0 | 0 | False | False | 2,747 |
| `legbyes` | 3 | 0 | 1 | False | False | 1 |
| `byes` | 4 | 0 | 0 | False | False | 529 |
| `Overstep` | 1 | 0 | 0 | False | False | 218 |
| `Overstep` | 1 | 0 | 1 | False | False | 174 |
| `Overstep` | 1 | 0 | 2 | False | False | 33 |
| `Overstep` | 1 | 0 | 3 | False | False | 2 |
| `Overstep` | 1 | 0 | 4 | True | False | 81 |
| `Overstep` | 1 | 0 | 6 | False | True | 47 |
| `Overstep` | 1 | 1 | 0 | False | False | 12 |
| `Overstep` | 1 | 4 | 0 | False | False | 9 |
| `other` | 5 | 0 | 0 | False | False | 114 |
| `other` | 5 | 0 | 1 | False | False | 49 |
| `other` | 5 | 0 | 2 | False | False | 18 |
| `other` | 5 | 0 | 3 | False | False | 1 |
| `other` | 5 | 0 | 4 | True | False | 42 |
| `other` | 5 | 0 | 6 | False | True | 26 |
| `other` | 5 | 1 | 0 | False | False | 7 |
| `other` | 5 | 4 | 0 | False | False | 7 |
| `Penalty` | 7 | 0 | 0 | False | False | 1 |

### Boundary and dismissal relationships

- Every `is_four=True` row has `runs=4`; however, **20** rows have
  `runs=4` while `is_four=False`.
- Every `is_six=True` row has `runs=6`; however, **3** rows have
  `runs=6` while `is_six=False`.
- The false-flagged run-4/run-6 examples are in rows where raw
  `extras_type=None`; this correlation does not establish whether `runs`
  represents batter runs or whether the flag is incomplete.
- Dismissal labels/frequencies on rows where pandas parses the type as
  non-missing: Caught 7,557; Bowled 1,775; LBW 709; RunOut 600; Stump 214;
  Hit Wicket 17; Retire Out 6; Obstracting the field 2; Obstructing the field 1.
- There are 12 records with a dismissed-player ID and `is_wicket=False`, and
  one with `is_wicket=True` and no dismissed-player ID. Match 40709's row
  (Excel row 127901) has `Retire Out`.

### `wide` and `Overstep`

- Every observed `wide` row has the combination
  `(extras1_runs=2, extras_2_runs=0, runs=0, is_four=False, is_six=False)`
  (7,714 rows).
- `Overstep` occurs in six combinations: with `extras1_runs=1`,
  `extras_2_runs=0`, runs 0/1/2/3/4/6 (boundary flags true only for the
  observed run-4/run-6 groups), and with `extras_2_runs=1` or `4` when runs
  are zero. See the exact 31-combination table and source-row exemplars in
  `audit_reports/anomaly_investigation/extras_investigation.csv`.
- The labels may suggest cricket concepts, but whether `Overstep` means a
  no-ball, and how either label affects legal-delivery counts, is **not
  established by the data alone**.
- Do not infer a final extras aggregation, batter-run formula, legal-ball
  rule, or bowling-runs formula from these observed combinations.

## `bowl_speed` observations

- 200,999 values are non-null according to pandas.
- Minimum `-1.0`; maximum `1456.1`; median `91.7`; 99th percentile `146.0`.
- **77,861** values are exactly zero; **1** value is negative; **19** are
  greater than 200.
- Several maximum values exceed 1,000 (for example 1456.1, 1410.0, 1351.0).
  One negative record is match 14108, Axar Patel, `-1`.
- Units, valid range, zero/missing-value convention, and whether outliers are
  corrupt or differently scaled are all unresolved. Do not filter or rescale.

## Candidate column groups by RR ScoutIQ use

These are candidate inputs only. They are not approved formulas.

| Use area | Candidate columns |
|---|---|
| Batter identity | `striker_id`, `striker_name`, `non_striker_id`, `non_striker_name`, `batting_team_id`; contextual mapping through `matches.comp_id` and `competition_team_player_mapping.csv` |
| Batting performance | `striker_id`, `runs`, `is_four`, `is_six`, `is_wicket`, `dismissal_type`, `dismissed_player_id`, `innings`, `batting_order`, `match_id`; validate run and dismissal semantics first |
| Bowler identity/performance | `bowler_id`, `bowler_name`, `bowling_team_id`, `runs`, `extras_type`, `extras1_runs`, `extras_2_runs`, `is_wicket`, `dismissal_type`, `bowl_speed`; conceded-runs and legal-ball metrics are blocked on field validation |
| Match-state reconstruction | `match_id`, `innings`, `innings_ball_num`, `overid`, `over_ball_num`, `runs`, `is_wicket`, dismissal fields, extras fields; contextual match result/targets from `matches.csv` |
| Innings/delivery ordering | `match_id`, `innings`, `innings_ball_num`; `overid` and `over_ball_num` are useful cross-checks but not legal-ball measures |
| Match context | `matches.match_id`, `comp_id`, `match_date`, `stage`, `match_format`, home/away team IDs, toss/result and revised-target fields |
| Player/team/competition identity | `matches.match_id` -> `comp_id`; `teams.(comp_id, team_id)`; mapping `(comp_id, team_id, player_id)`; lineup `match_id`, `team_id`, `player_id` |

## Undocumented conventions and human-review questions

1. What do `runs`, `extras1_runs`, and `extras_2_runs` measure and how should
   they relate? Why is the raw literal `None` paired with `extras1_runs=6`?
2. Does `Overstep` have a specific provider meaning? How should wides and
   Overstep/no-balls affect legal-ball reconstruction?
3. What units/range does `bowl_speed` use? What do zero, negative, and
   >200/1,000 values encode?
4. What do `is_four`/`is_six` mean when `runs` is 4/6 but the flags are false?
5. How should each dismissal type, especially `Retire Out`, affect wicket and
   player-dismissal counts?
6. What do `overid`, `over_ball_num`, and innings values 3/4 mean in all
   supported formats? Is `innings_ball_num` provider-defined as the reliable
   sequence field?
7. Why is a field named `delivery_ist_time` populated with strings ending in
   `UTC`? Is it match event time, scheduled time, or another timestamp?
8. What are the semantics and update timing of `playing_eleven.is_played`,
   `batting_order`, `is_impact`, and `is_impact_off`?
9. Why is `(comp_id=2670, team_id=4444, player_id=29833)` missing from the
   player map while appearing on five not-played lineup rows?
10. Is `man_of_the_match=0` a missing/unknown/unawarded sentinel?
11. Are three competitions without match rows intentional? Are missing
    abandoned-match deliveries/lineups expected by design?
12. What timezone/date and match-target conventions apply to `matches.csv`?

## M2.1 scope boundary

M2.1 documents all CSV columns, observed pandas types/examples, candidate
relationships, and known ambiguities. It does **not** resolve the provider
questions, validate metric definitions, decide pressure situations, calculate
player rankings, or approve a ranking formula. Those are subsequent M2 work
items and remain not started unless explicitly tracked otherwise.

---

## M2.4 Conditional Hybrid Layer Schema & Crosswalk Architecture

Following the verification and approval of the Cricsheet open-data integration in Milestone M2.4, an immutable hybrid enrichment layer is established:

```text
Local matches.csv (883)
    `-- data/enriched/match_crosswalk.csv (883)
            |-- ext_cricsheet_match_id (e.g., 1304047)
            |-- ext_cricsheet_archive (ipl_json.zip / t20s_male_json.zip)
            `-- enrichment_status:
                    |-- COVERED (784 matches, 88.8%)
                    |-- CRICSHEET_POLICY_WITHHELD (61 Afghanistan fixtures, 6.9%)
                    |-- DEVELOPMENTAL_NOT_IN_CRICSHEET (25 Emerging matches, 2.8%)
                    `-- ABANDONED_UNPLAYED (13 unplayed matches, 1.5%)

Local ball_by_ball.csv (200,999) + match_crosswalk
    `-- data/enriched/pilot/enriched_ball_by_ball_pilot.csv (1,994 deliveries)
            |-- [Original 33 columns preserved intact]
            |-- ext_is_legal_delivery (Boolean)
            |-- ext_is_wide / ext_is_noball (Boolean)
            |-- ext_wide_runs / ext_noball_runs / ext_bye_runs / ext_legbye_runs / ext_penalty_runs
            |-- ext_delivery_total_runs (batter runs + all extras)
            |-- ext_bowler_debit_runs (batter runs + wides + noballs)
            |-- ext_batter_balls_faced (1 for legal and no-ball, 0 for wide)
            |-- ext_is_bowler_wicket (direct dismissal credit)
            |-- ext_is_retired_hurt (non-out departure flag)
            |-- ext_is_retired_out (non-bowler departure flag)
            `-- ext_provenance (Source archive & file)

Local players / playing_eleven + Cricsheet registry
    `-- data/enriched/player_crosswalk.csv
            |-- local_match_id + local_player_id
            |-- ext_cricsheet_player_id (e.g., ed23bb89)
            |-- ext_cricsheet_player_name (e.g., CV Varun)
            |-- match_method (EXACT_NAME, UNIQUE_SURNAME, INITIAL_DISAMBIGUATION, KNOWN_ALIAS_REGISTRY)
            `-- confidence (0.95 to 1.0)
```

---

## M3 Delivery Leverage & Performance Feature Schema

Documented in [`../audit_reports/M3_PRESSURE_METHODOLOGY.md`](../audit_reports/M3_PRESSURE_METHODOLOGY.md):

```text
Pre-Delivery Match State (Innings 2 Chase)
    |-- score_before: Cumulative innings runs before delivery
    |-- wickets_lost_before: Cumulative dismissals in innings before delivery
    |-- wickets_in_hand: 10 - wickets_lost_before
    |-- balls_remaining: 120 - legal_balls_bowled_before
    |-- runs_needed: max(0, target - score_before)
    |-- rrr: runs_needed / (balls_remaining / 6.0)
    `-- dli_chase: Clamp[(RRR / CRR_baseline) * (10 / (W_hand + 1))^0.5 * (1 + 24 / (B_rem + 12))^0.5, 0.1, 5.0]

Pre-Delivery Match State (Innings 1 Setting)
    |-- score_before: Cumulative innings runs before delivery
    |-- wickets_lost_before: Cumulative dismissals in innings before delivery
    |-- crr: score_before / (legal_balls_bowled_before / 6.0)
    `-- dli_setting: Clamp[Phase_Factor * (10 / (W_hand + 1))^0.6 * (1 + max(0, CRR_baseline - CRR)/6)^0.5, 0.2, 3.5]

Leverage Tiers (Reporting & Audit Grain)
    |-- Low Leverage: DLI < 0.75
    |-- Medium Leverage: 0.75 <= DLI < 1.35
    |-- High Leverage: 1.35 <= DLI < 2.25
    `-- Extreme Leverage: DLI >= 2.25 (Includes all Super Over deliveries: DLI = 3.50)

Batter Pressure Performance Features (BPPI)
    |-- xRA: runs_off_bat - E[runs | phase, role, tier]
    |-- delta_sr: SR_pressure - SR_normal_baseline
    |-- delta_bnd_pct: Boundary%_pressure - E[Boundary% | role]
    |-- delta_dot_pct: E[Dot% | role] - Dot%_pressure
    `-- delta_survival: E[Dismissal% | phase, W_hand] - Dismissal%_pressure

Bowler Pressure Performance Features (PPBI)
    |-- xRS: E[runs_conceded | overid, phase, tier] - bowler_debit_runs
    |-- delta_econ: Econ_normal_baseline - Econ_pressure
    |-- delta_wkt_pct: Wicket%_pressure - E[Wicket% | phase]
    |-- delta_dot_pct: Dot%_pressure - E[Dot% | phase]
    `-- delta_bnd_con_pct: E[BndCon% | phase] - BndCon%_pressure
```



