# RR ScoutIQ - Data Dictionary

## Scope and interpretation

This dictionary describes the six extracted CSVs as observed in the M1/M2.1
workspace. The data types below are pandas-inferred types from a default
`read_csv(..., low_memory=False)` load; they are not a provider schema or a
claim about canonical types. Examples are observed values, not definitions.

“Appears to represent” and “potential use” are hypotheses from field names,
values, and observed joins. An unresolved convention is explicitly marked
**Unknown**. Do not use a suggested purpose as proof of cricket semantics.
Source files under `data/extracted/` remain unchanged.

Rows / columns: `ball_by_ball.csv` 200,999 / 33;
`matches.csv` 883 / 22; `playing_eleven.csv` 28,381 / 9;
`competition_team_player_mapping.csv` 6,413 / 6; `teams.csv` 353 / 3;
`competitions.csv` 141 / 4.

## `ball_by_ball.csv`

| Column | pandas dtype | Missing (default pandas) | Example observed value(s) | Appears to represent / potential use | Uncertainty / caution |
|---|---|---:|---|---|---|
| `match_id` | `int64` | 0 | `13511`, `14108` | Match identifier; join to `matches.match_id`. | Observed 867 distinct IDs; 16 matches in `matches.csv` have no delivery rows. |
| `innings` | `int64` | 0 | `1`, `2`, `3`, `4` | Innings label; partition deliveries and score state. | Only four labels observed; match-format-specific innings rules require validation. |
| `overid` | `int64` | 0 | `1`, `9`, `20` | Over identifier/sequence within innings; group deliveries into over-like units. | Values 1–20; source-order values are nondecreasing by innings. Whether zero-based/one-based or special-innings semantics are universal is unconfirmed. |
| `over_ball_num` | `int64` | 0 | `1`, `6`, `7`, `13` | Within-over delivery position/sequence label. | Values 1–13 and reset as `overid` changes; not a legal-ball count by itself. |
| `innings_ball_num` | `int64` | 0 | `1`, `55`, `136` | Delivery sequence number within an innings; useful for ordering/state reconstruction. | In this file, it increases by one in source order within each match/innings, with no gaps or duplicate values. Provider definition still undocumented. |
| `batting_team_id` | `int64` | 0 | `22`, `28` | Batting-side team ID; join to `teams.team_id` in match competition context. | Team IDs must be scoped by competition; not proof of home/away status. |
| `bowling_team_id` | `int64` | 0 | `28`, `22` | Bowling-side team ID; join to `teams.team_id` in match competition context. | Same team-context caveat. |
| `striker_id` | `int64` | 0 | `1187`, `6273` | ID of the listed striker; candidate batter identity. | Contextual mapping to competition/team/player mapping verified for observed delivery tuples. |
| `striker_name` | `str` | 0 | `Jason Roy`, `Tom Banton` | Name label accompanying `striker_id`. | Names are not unique globally; use ID plus competition/team context. |
| `non_striker_id` | `int64` | 0 | `6273`, `1210` | ID of listed non-striker; candidate batter identity. | Name/identity role is inferred from field name; contextual mapping was consistent in observed tuples. |
| `non_striker_name` | `str` | 0 | `Tom Banton`, `James Vince` | Name label accompanying `non_striker_id`. | Not a globally unique key. |
| `bowler_id` | `int64` | 0 | `1772`, `2633` | ID of listed bowler; candidate bowling-performance identity. | Contextual mapping to mapping file was consistent in observed tuples. |
| `bowler_name` | `str` | 0 | `Sheldon Cottrell`, `Jason Holder` | Name label accompanying `bowler_id`. | Not a globally unique key. |
| `batting_type` | `str` | 0 | `RHB`, `LHB` | Batting-style/handedness label. | Likely handedness, but provider codes and effective date are undocumented. |
| `bowling_type` | `str` | 0 | `Left-arm fast-medium`, `Right-arm medium-fast`, `Slow left-arm orthodox` | Textual bowling-style label. | Taxonomy and consistency rules are undocumented; observed 12 distinct labels. |
| `batting_order` | `int64` | 0 | `1`, `2`, `4` | Batter order/position field on delivery rows; may support role/context grouping. | Meaning may differ from the repeated `playing_eleven.batting_order`; its interpretation and update timing are unverified. |
| `runs` | `int64` | 0 | `0`, `1`, `4`, `6` | Run-related delivery value; candidate batting/scoring input. | Field semantics (batter runs vs delivery/team runs, treatment of extras) are not documented. Do not combine with extras fields without validation. |
| `is_four` | `bool` | 0 | `True`, `False` | Four-related Boolean flag; potential boundary descriptor. | Every `True` row has `runs=4`; 20 rows with `runs=4` have `False`. Flag semantics and source omissions need review. |
| `is_six` | `bool` | 0 | `True`, `False` | Six-related Boolean flag; potential boundary descriptor. | Every `True` row has `runs=6`; 3 rows with `runs=6` have `False`. Do not assume equivalence to `runs`. |
| `is_wicket` | `bool` | 0 | `False`, `True` | Wicket-related event flag; potential wicket-state input. | 10,881 rows are true. Relationship to dismissal type/ID is inconsistent in 13 rows; cricket meaning of each dismissal needs validation. |
| `dismissal_type_id` | `float64` | 190,118 | `1.0`, `2.0`, `5.0` | Numeric code associated with dismissal type. | Sparse; code-to-label mapping is not supplied. Float dtype results from missing values, not necessarily fractional IDs. |
| `dismissal_type` | `str` | 190,118 | `Caught`, `Bowled`, `LBW`, `RunOut`, `Retire Out` | Text label for a dismissal-related event. | Includes both `Obstracting the field` and `Obstructing the field`; definitions and wicket-credit rules are unresolved. |
| `dismissed_player_id` | `float64` | 190,107 | `1187.0`, `6273.0` | ID of player named as dismissed. | Sparse and inconsistent with `is_wicket` on 13 rows. No dismissed-player name column exists in this file. |
| `extras_type` | `str` | 189,167 | `None` (literal in raw CSV), `wide`, `legbyes`, `byes`, `Overstep`, `other`, `Penalty` | Provider-supplied extras/event category; potential input to delivery classification after validation. | Raw `None` is text, not an empty field; pandas default NA parsing treats it as missing. Labels and `Overstep` meaning are undocumented. |
| `extras1_runs` | `int64` | 0 | `6`, `2`, `3`, `1`, `4`, `5`, `7` | Numeric field associated with extras in name only. | Value is `6` on all 189,167 rows whose raw `extras_type` is literal `None`; other values align with labels in the data but meaning is unverified. Do not sum it as extras/runs. |
| `extras_2_runs` | `int64` | 0 | `0`, `1`, `4` | Second numeric field associated with extras in name only. | Nonzero on 36 rows (20 values of 1, 16 values of 4); meaning and relationship to `runs`/`extras1_runs` unknown. |
| `pace_or_spin` | `str` | 0 | `Pace`, `Spin` | Broad bowling-style category. | Taxonomy and assignment rules are undocumented; possible descriptive grouping, not a validated performance metric. |
| `bowl_speed` | `float64` | 0 | `0.0`, `91.7`, `130.4`, `1456.1`, `-1.0` | Numeric bowling-speed-like field; possible descriptive analysis. | Units are unknown. 77,861 zeros, one negative (`-1`), and 19 values above 200 occur; max is 1456.1. Zero/sentinel/scale meanings are unresolved. |
| `stroke` | `str` | 6,158 | `Cover Drive`, `Flick`, `Square Cut` | Textual stroke/shot descriptor. | Provider taxonomy and whether it describes batter intent or coded outcome are unknown. |
| `delivery_style` | `str` | 391 | `Inswing`, `Seamed In`, `Full Toss`, `Out Swing` | Textual delivery/ball-style descriptor. | Provider taxonomy and consistency are unknown. |
| `over_or_around` | `str` | 407 | `Over`, `Around` | Descriptive delivery line/angle label suggested by its name. | Exact cricket definition and reference frame are not documented. |
| `on_or_off` | `str` | 0 | `Off-side`, `On-side` | Descriptive side/location label suggested by its name. | Exact perspective (batter, bowler, or field) is not documented. |
| `delivery_ist_time` | `str` | 0 | `2022-01-23 00:00:00 UTC` | Delivery-associated timestamp string. | Despite `IST` in the column name, observed strings end in `UTC`; timezone, event meaning, and repeated timestamps require provider clarification. |

## `matches.csv`

| Column | pandas dtype | Missing | Example observed value(s) | Appears to represent / potential use | Uncertainty / caution |
|---|---|---:|---|---|---|
| `match_id` | `int64` | 0 | `13511`, `13512` | Match primary identifier; joins to delivery and lineup rows. | Unique across 883 rows in this file. |
| `comp_id` | `int64` | 0 | `1331`, `1358` | Competition identifier; joins to `competitions.comp_id`. | All match IDs map to a competition; three competition metadata rows have no match rows. |
| `match_number` | `int64` | 0 | `1`, `2`, `75` | Competition/match sequence label. | Not unique globally; numbering scope/rules are not documented. |
| `match_date` | `str` | 0 | `2022-01-22`, `2026-11-01` | Match date; useful for time-based grouping. | All values parsed in M1, but local time/timezone and date-source conventions are unspecified. |
| `stage` | `str` | 0 | `League`, `Qualifier`, `Eliminator`, `Final` | Competition stage label. | `Others`, `Super 4`, and other labels occur; taxonomy/normalization not defined. |
| `venue_id` | `int64` | 0 | `54`, `8`, `44` | Venue identifier. | No venue dimension/name file was supplied; ID meaning cannot be enriched from these six CSVs. |
| `venue_country` | `str` | 0 | `West Indies`, `India`, `Australia` | Venue-country/host-location label. | Whether this is country, territory, or competition-specific label is not defined. |
| `home_team_id` | `int64` | 0 | `28`, `18`, `20` | Team ID labelled as home team; candidate match-team relation. | Label does not prove a formal home advantage; joins validated using competition context. |
| `home_team` | `str` | 0 | `West Indies`, `India`, `Chennai Super Kings` | Name corresponding to `home_team_id`. | Use ID for joins; home designation semantics need validation. |
| `away_team_id` | `int64` | 0 | `22`, `28`, `27` | Team ID labelled as away team. | Same home/away caveat. |
| `away_team` | `str` | 0 | `England`, `West Indies`, `Sri Lanka` | Name corresponding to `away_team_id`. | Use ID for joins; label can be checked against team metadata. |
| `home_team_captain_id` | `float64` | 44 | `494.0`, `126.0`, `250.0` | Candidate player ID for home-team captain. | Sparse; float caused by missingness; ID/name and match-time roster semantics should be validated. |
| `away_team_captain_id` | `float64` | 45 | `478.0`, `1596.0`, `494.0` | Candidate player ID for away-team captain. | Same captain-field caveat. |
| `toss_win_team_id` | `float64` | 15 | `28.0`, `22.0`, `18.0` | Team ID labelled toss winner. | Sparse; expected to relate to one match team but not independently verified as a rule. |
| `toss_opted` | `str` | 15 | `Fielding`, `Batting` | Toss decision label. | Decision taxonomy/provider spelling not documented. |
| `man_of_the_match` | `int64` | 0 | `0`, `4986`, `1699` | Candidate player ID for player of the match. | 119 zero values do not map to a player ID; zero is a possible placeholder, not a confirmed meaning. |
| `first_inn_revised_overs` | `float64` | 858 | `114.0`, `84.0`, `66.0` | Revised first-innings overs-related value. | Units/scale are undocumented (values look like integer multiples in many cases); missing on most rows. |
| `second_inn_revised_overs` | `float64` | 858 | `114.0`, `42.0`, `48.0` | Revised second-innings overs-related value. | Same scale and rules unknown. |
| `revised_target` | `float64` | 860 | `143.0`, `56.0`, `91.0` | Revised target-like match value. | Only 23 populated; no separate ordinary target column; target timing and adjustment rules unknown. |
| `knock_out` | `int64` | 0 | `0`, `1` | Binary-looking knockout indicator. | Encoding semantics and relation to `stage` are not documented. |
| `win_team_id` | `float64` | 41 | `28.0`, `22.0`, `18.0` | Candidate match-winning team ID. | Missing for some outcomes; result text is not normalized and may include no-result/abandoned cases. |
| `result` | `str` | 0 | `West Indies Won by 9 Wickets`, `No Result`, `Match Abandoned` | Match result/status text. | 670 distinct raw strings; case, spelling, and result formats vary. Do not parse without rules. |

## `playing_eleven.csv`

| Column | pandas dtype | Missing | Example observed value(s) | Appears to represent / potential use | Uncertainty / caution |
|---|---|---:|---|---|---|
| `match_id` | `int64` | 0 | `13511`, `13512` | Match reference; joins to `matches.match_id`. | 880 distinct matches; three matches have no lineup rows. |
| `team_id` | `int64` | 0 | `22`, `28`, `20` | Team associated with lineup record. | Scope by match competition; team membership joins are contextual. |
| `player_id` | `int64` | 0 | `1187`, `6273`, `1210` | Player reference; joins through match competition/team to player mapping. | Five rows for one `(comp_id=2670, team_id=4444, player_id=29833)` key did not map; all have `is_played=False` and missing batting order. |
| `batting_order` | `float64` | 8,678 | `1.0`, `2.0`, `3.0` | Candidate batting-order/position field. | 35 candidate-key groups repeat with different values; source meaning (planned/actual/state) is unknown. |
| `is_played` | `bool` | 0 | `True`, `False` | Participation-related Boolean flag by name. | Exact definition and timing (selected, appeared, substituted) are undocumented. |
| `is_captain` | `object` | 8,667 | `False`, `True` | Captain-related flag. | Null-heavy object dtype; no timing/convention documented. |
| `is_wk` | `object` | 8,667 | `False`, `True` | Wicketkeeper-related flag suggested by name. | Expansion of `wk` and null/role semantics require confirmation. |
| `is_impact` | `int64` | 0 | `0`, `1` | Impact-player-related indicator by name. | Integer 0/1 observed; competition-specific rules/timing not documented. |
| `is_impact_off` | `int64` | 0 | `0`, `1` | Impact/off-player-related indicator by name. | Meaning and relationship to `is_impact` are undocumented. |

## `competition_team_player_mapping.csv`

| Column | pandas dtype | Missing | Example observed value(s) | Appears to represent / potential use | Uncertainty / caution |
|---|---|---:|---|---|---|
| `comp_id` | `int64` | 0 | `1331`, `1358` | Competition identifier; joins to competitions and match context. | 140 distinct competition IDs represented. |
| `comp_name` | `str` | 0 | `England in West Indies T20I Series 2022`, `IPL 2022` | Competition name label. | Text label; `comp_id` is the join key. |
| `team_id` | `int64` | 0 | `22`, `28`, `242` | Team identifier in competition context. | `team_id` alone is not the documented composite key. |
| `team_name` | `str` | 0 | `England`, `West Indies`, `Sunrisers Hyderabad` | Team name label. | Repeated across competitions; join using IDs. |
| `player_id` | `int64` | 0 | `478`, `479`, `722` | Player identifier in competition/team context. | `(comp_id, team_id, player_id)` has no duplicate rows; five lineup rows for one key were unmatched. |
| `player_name` | `str` | 0 | `Eoin Morgan`, `Adil Rashid`, `Liam Dawson` | Player name label for the contextual player ID. | There are 1,217 distinct IDs and 1,210 distinct names; seven names occur with multiple IDs. Names are not unique identifiers. |

## `teams.csv`

| Column | pandas dtype | Missing | Example observed value(s) | Appears to represent / potential use | Uncertainty / caution |
|---|---|---:|---|---|---|
| `comp_id` | `int64` | 0 | `1331`, `1358` | Competition reference. | 141 distinct competition IDs; joins to competition metadata. |
| `team_id` | `int64` | 0 | `22`, `28`, `242` | Team identifier in a competition. | `(comp_id, team_id)` is unique; `team_id` recurs across competitions. |
| `team_name` | `str` | 0 | `England`, `West Indies`, `Sunrisers Hyderabad` | Team name label. | Not a key; source spelling/aliases are not normalized. |

## `competitions.csv`

| Column | pandas dtype | Missing | Example observed value(s) | Appears to represent / potential use | Uncertainty / caution |
|---|---|---:|---|---|---|
| `comp_id` | `int64` | 0 | `3395`, `3405`, `3465` | Competition identifier; joins to match/team/player mapping data. | Unique in this file; three competition IDs have no corresponding matches in the supplied match table. |
| `comp_name` | `str` | 0 | `South Africa in New Zealand T20I Series 2026`, `IPL 2026` | Competition label. | Name text is not a normalized key. |
| `match_format` | `str` | 0 | `T20I`, `T20` | Competition-format label; candidate grouping dimension. | Only these two values observed; rules/format metadata are not supplied. |
| `season` | `str` | 0 | `2026`, `2022`, `2023` | Competition season/year-like label. | Stored as text; season boundary convention is unspecified. |

## Relationships and identity notes

The composite keys, observed join coverage, and caveats are documented in
[`CRICKET_DATA_SCHEMA.md`](CRICKET_DATA_SCHEMA.md). For exact row-level M1
anomalies, see
[`../audit_reports/anomaly_investigation/anomaly_investigation_report.md`](../audit_reports/anomaly_investigation/anomaly_investigation_report.md).

---

## Enriched Hybrid Layer (`data/enriched/`)

The enriched files do NOT overwrite original raw datasets. They reside in `data/enriched/` and provide reconciled external features with explicit `ext_` prefixes and complete source provenance.

### `data/enriched/match_crosswalk.csv` (883 rows)
Maps each local `match_id` to its Cricsheet match file and explains coverage/exception categories.
- `local_match_id` (`int64`): Primary key joining to local `matches.csv`.
- `match_date` (`str`): Date in local match record.
- `competition_name` (`str`): Local competition name.
- `format` (`str`): Local match format (`T20`, `T20I`).
- `home_team`, `away_team` (`str`): Local team names.
- `local_result` (`str`): Raw outcome string.
- `enrichment_status` (`str`): `COVERED` (784), `CRICSHEET_POLICY_WITHHELD` (61), `DEVELOPMENTAL_NOT_IN_CRICSHEET` (25), or `ABANDONED_UNPLAYED` (13).
- `ext_cricsheet_archive` (`str`): Source ZIP archive (`ipl_json.zip`, `t20s_male_json.zip`, or empty).
- `ext_cricsheet_file` (`str`): Cricsheet JSON filename (e.g., `1304047.json`).
- `ext_cricsheet_match_id` (`str`): Cricsheet numeric match ID.
- `provenance_notes` (`str`): Exact match matching method and date alignment.

### `data/enriched/player_crosswalk.csv`
Scoped mapping between local player IDs and Cricsheet player identifiers.
- `local_match_id` (`int64`): Match context ID.
- `local_player_id` (`int64`): Player ID in local dataset.
- `local_player_name` (`str`): Player name in local dataset.
- `ext_cricsheet_player_id` (`str`): Cricsheet unique person ID (e.g., `ed23bb89`, `a97c8ec2`).
- `ext_cricsheet_player_name` (`str`): Cricsheet official scorecard name (e.g., `CV Varun`, `PWH de Silva`).
- `match_method` (`str`): Matching rule (`EXACT_NAME`, `UNIQUE_SURNAME`, `INITIAL_DISAMBIGUATION`, `KNOWN_ALIAS_REGISTRY`).
- `confidence` (`float64`): Match confidence score (0.95 to 1.0).
- `status` (`str`): `RESOLVED` or `UNRESOLVED`.

### `data/enriched/pilot/enriched_ball_by_ball_pilot.csv` (1,994 deliveries)
Preserves all 33 original columns from `ball_by_ball.csv` and appends external verified fields:
- `ext_cricsheet_match_id` (`int64`): Cricsheet numeric match identifier.
- `ext_striker_cricsheet_id` (`str`): Cricsheet identifier for striker.
- `ext_bowler_cricsheet_id` (`str`): Cricsheet identifier for bowler.
- `ext_is_legal_delivery` (`bool`): `True` for legal deliveries; `False` for wides, oversteps, and uncredited no-balls.
- `ext_is_wide` (`bool`): `True` if delivery was a wide.
- `ext_is_noball` (`bool`): `True` if delivery was a no-ball (front-foot overstep or above waist height).
- `ext_wide_runs` (`int64`): Runs debited as wide extras.
- `ext_noball_runs` (`int64`): Runs debited as no-ball extras.
- `ext_bye_runs` (`int64`): Bye runs scored on delivery.
- `ext_legbye_runs` (`int64`): Leg-bye runs scored on delivery.
- `ext_penalty_runs` (`int64`): Penalty runs awarded on delivery.
- `ext_delivery_total_runs` (`int64`): Total runs scored on the delivery off bat plus all extras.
- `ext_bowler_debit_runs` (`int64`): Runs charged to the bowler (`batter_runs + wide_runs + noball_runs`).
- `ext_batter_balls_faced` (`int64`): 1 if ball counts towards batter balls faced (legal ball or no-ball); 0 if wide.
- `ext_is_bowler_wicket` (`bool`): `True` only for dismissals credited to bowler (bowled, caught, lbw, stumped, hit wicket).
- `ext_is_retired_hurt` (`bool`): `True` if departure was a retired hurt (non-out under Law 25.4.2).
- `ext_is_retired_out` (`bool`): `True` if departure was retired out (batter dismissed, but not credited to bowler).
- `ext_provenance` (`str`): Full attribution string (e.g., `Cricsheet ipl_json.zip 1304047.json`).

### `data/enriched/full/enriched_ball_by_ball_full.csv` (179,837 deliveries, 776 matches)
The full-dataset hybrid enriched delivery repository. Preserves all 33 original columns from `ball_by_ball.csv` intact and appends comprehensive external verified fields with `ext_` prefixes:
- `ext_cricsheet_match_id` (`str` / `float64`): Cricsheet match identifier.
- `ext_cricsheet_archive` (`str`): Source archive (`ipl_json.zip` or `t20s_male_json.zip`).
- `ext_cricsheet_file` (`str`): Cricsheet JSON filename.
- `ext_cricsheet_competition_name` (`str`): Event name from Cricsheet metadata.
- `ext_match_format` (`str`): Match format (`T20`, `IT20`).
- `ext_innings` (`int64`): Inning number (1 or 2).
- `ext_is_super_over` (`bool`): False across all enriched deliveries (Super Overs excluded in regulation-only matches).
- `ext_cricsheet_delivery_index` (`int64`): 1-based sequential delivery index within the Cricsheet match feed.
- `ext_striker_name` (`str`): Resolved official Cricsheet name for striker.
- `ext_striker_cricsheet_id` (`str`): Cricsheet person identifier for striker (100.0% resolved).
- `ext_non_striker_name` (`str`): Resolved official Cricsheet name for non-striker.
- `ext_non_striker_cricsheet_id` (`str`): Cricsheet person identifier for non-striker (100.0% resolved).
- `ext_bowler_name` (`str`): Resolved official Cricsheet name for bowler.
- `ext_bowler_cricsheet_id` (`str`): Cricsheet person identifier for bowler (100.0% resolved).
- `ext_dismissed_player_name` (`str`): Official Cricsheet name of dismissed player if wicket occurred.
- `ext_dismissed_player_cricsheet_id` (`str`): Cricsheet identifier for dismissed player.
- `ext_dismissed_player_local_id` (`float64`): Local player ID for dismissed player.
- `ext_batter_runs` (`int64`): Runs scored off bat (0 to 6).
- `ext_extra_runs` (`int64`): Total extras awarded on the delivery.
- `ext_extras_type` (`str`): Comma-separated list of active extra types (`wides`, `noballs`, `byes`, `legbyes`, `penalty`).
- `ext_delivery_total_runs` (`int64`): Total runs scored on the delivery (`ext_batter_runs + ext_extra_runs`).
- `ext_is_wide` (`bool`): True if wide extras occurred.
- `ext_wide_runs` (`int64`): Wide extras runs.
- `ext_is_noball` (`bool`): True if no-ball extras occurred.
- `ext_noball_runs` (`int64`): No-ball extras runs.
- `ext_is_bye` (`bool`): True if bye extras occurred.
- `ext_bye_runs` (`int64`): Bye extras runs.
- `ext_is_legbye` (`bool`): True if leg-bye extras occurred.
- `ext_legbye_runs` (`int64`): Leg-bye extras runs.
- `ext_is_penalty` (`bool`): True if penalty runs occurred.
- `ext_penalty_runs` (`int64`): Penalty runs.
- `ext_is_legal_delivery` (`bool`): True for legal deliveries (`not ext_is_wide and not ext_is_noball`).
- `ext_batter_balls_faced` (`int64`): 1 if ball counts towards batter balls faced (legal ball or no-ball); 0 if wide.
- `ext_bowler_debit_runs` (`int64`): Runs debited to bowler under MCC Law 18.10.3 (`ext_batter_runs + ext_wide_runs + ext_noball_runs`).
- `ext_is_four` (`bool`): True if 4 runs scored off bat.
- `ext_is_six` (`bool`): True if 6 runs scored off bat.
- `ext_is_wicket` (`bool`): True if a wicket occurred (excludes retired hurt).
- `ext_dismissal_kind` (`str`): Exact dismissal kind (`bowled`, `caught`, `lbw`, `run out`, `stumped`, `hit wicket`, `retired out`, `retired hurt`).
- `ext_is_bowler_wicket` (`bool`): True only for dismissals credited to bowler under MCC rules (bowled, caught, caught and bowled, lbw, stumped, hit wicket).
- `ext_is_retired_hurt` (`bool`): True if departure was retired hurt (non-out under MCC Law 25.4.2).
- `ext_is_retired_out` (`bool`): True if departure was retired out (team wicket, not credited to bowler).
- `ext_alignment_strategy` (`str`): Alignment strategy used (`CLEAN_VALIDATED`, `SAFE_REGULATION_ONLY`, `SAFE_MINOR_OMISSION`).
- `ext_provenance` (`str`): Full provenance string.

### `data/enriched/full/match_enrichment_manifest.csv` (883 rows)
Comprehensive match processing manifest providing complete tracking across all 883 inventory matches:
- `local_match_id` (`int64`): Local match identifier.
- `cricsheet_match_id` (`float64` / `str`): Corresponding Cricsheet match identifier.
- `processing_status` (`str`): `ENRICHED_AND_VALIDATED` (776), `EXCLUDED_POLICY_WITHHELD` (61), `UNRESOLVED_MATCH_MAPPING` (25), `EXCLUDED_UNPLAYED` (16), `MATCHED_WITH_WARNINGS` (5 quarantined).
- `original_delivery_count` (`int64`): Local delivery count.
- `enriched_delivery_count` (`int64`): Enriched delivery count (179,837 across enriched matches; 0 for excluded matches).
- `unmatched_delivery_count` (`int64`): Unmatched deliveries count (0 across enriched matches).
- `validation_status` (`str`): `PASSED` (776) or `EXCLUDED` (107).
- `exclusion_or_warning_reason` (`str`): Detailed reason for warning disposition or exclusion.
- `analytical_scope` (`str`): `FULL_MATCH` (772), `REGULATION_ONLY` (2), `SAFE_FULL_ALIGNMENT` (2), `EXCLUDED_QUARANTINE` (5), `EXCLUDED_POLICY` (61), `EXCLUDED_UNPLAYED` (16), `EXCLUDED_UNRESOLVED` (25).

### `data/enriched/full/enrichment_validation_summary.csv` (23 rows)
Field-level and event-level cricket validation results covering 100% of the 179,837 deliveries across Scope, Special Matches, Player Resolution, Scoring & Extras, and Dismissals & Wickets. All 23 checks PASSED.

---

## M5.3 Full-Scale Pre-Delivery Match-State Schema

### `data/processed/m5_3/match_state_full.csv` (179,837 rows, 776 matches)
Full enriched dataset augmented with causal pre-delivery match state, DLI, and leverage tiers:
- `pre_score` (`int64`): Cumulative runs scored by the batting team strictly before this delivery.
- `pre_wickets_lost` (`int64`): Cumulative wickets lost by the batting team strictly before this delivery (excluding retired hurt).
- `pre_wickets_in_hand` (`int64`): Wickets in hand ($10 - \text{pre\_wickets\_lost}$).
- `pre_legal_balls_bowled` (`int64`): Cumulative legal balls bowled before this delivery.
- `pre_legal_balls_rem` (`int64`): Legal balls remaining in the innings ($120 - \text{pre\_legal\_balls\_bowled}$ for regulation T20; $6 - \text{pre\_legal\_balls\_bowled}$ for Super Overs).
- `pre_crr` (`float64`): Current run rate before this delivery ($\text{pre\_score} / (\text{pre\_legal\_balls\_bowled} / 6)$ for $\ge 6$ legal balls; `NaN` otherwise).
- `pre_target` (`float64`): Target runs required to win in Innings 2 (Innings 1 score $+ 1$ for regulation; revised target for DLS; `NaN` for Innings 1).
- `pre_runs_required` (`float64`): Runs required to win ($\max(0, \text{pre\_target} - \text{pre\_score})$; `NaN` for Innings 1).
- `pre_rrr` (`float64`): Required run rate before this delivery ($\text{pre\_runs\_required} / (\text{pre\_legal\_balls\_rem} / 6)$; `NaN` for Innings 1, DLS, and shortened matches).
- `pre_innings_type` (`str`): Innings classification (`Setting`, `Chase`, `Super Over`).
- `pre_match_phase` (`str`): Phase category (`Powerplay` overs 1–6, `Middle` overs 7–15, `Death` overs 16–20, `Super Over`, `Shortened Match`).
- `pre_dli` (`float64`): Delivery Leverage Index (clamped to $[0.20, 3.50]$ for Setting, $[0.10, 5.00]$ for Chase, fixed $3.50$ for Super Over).
- `pre_pressure_tier` (`str`): Discrete leverage tier (`Tier 1: Low` $<0.90$, `Tier 2: Medium` $0.90 \le \text{DLI} < 1.35$, `Tier 3: High` $1.35 \le \text{DLI} < 2.25$, `Tier 4: Extreme` $\ge 2.25$).
- `is_dli_valid` (`bool`): True if DLI is analytically valid for standard benchmark comparisons (False for shortened matches and DLS chases).
- `dli_exclusion_reason` (`str`): Specific reason if DLI is invalid (`VALID_REGULATION`, `SHORTENED_MATCH_NON_STANDARD_PHASE`, `DLS_REVISED_TARGET_UNAVAILABLE_TIMING`, `SUPER_OVER_FIXED`).
- `is_super_over` (`bool`): True for Super Over deliveries (Innings 3 and 4).
- `is_shortened_match` (`bool`): True if match had revised overs recorded.
- `is_dls_match` (`bool`): True if match had a DLS revised target recorded.

### `data/processed/m5_3/match_state_validation_summary.csv` (12 rows)
Verification summary of the 12 mandatory cricket-domain invariant checks (all 12 PASSED).

### `data/processed/m5_3/match_state_exclusion_register.csv` (4,187 rows)
Register of all deliveries receiving special handling or DLI exclusion (2,560 shortened, 1,601 DLS, 26 Super Over).

### `data/processed/m5_3/match_state_match_summary.csv` (776 rows)
Match-level aggregate summary capturing delivery counts, innings totals, DLI validity rates, and match dispositions.


---

## M2.5 Consolidated Data Reliability Matrix

For detailed audit classification of all 26 raw and derived metrics across `CONFIRMED`, `PROVISIONAL`, `EXTERNAL_ENRICHMENT_REQUIRED`, `UNRESOLVED`, and `EXCLUDED` tiers, see:
[`../audit_reports/performance_metrics/consolidated_data_reliability_matrix.csv`](../audit_reports/performance_metrics/consolidated_data_reliability_matrix.csv) and [`../audit_reports/M2_5_DOMAIN_REVIEW.md`](../audit_reports/M2_5_DOMAIN_REVIEW.md).


