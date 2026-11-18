"""
RR ScoutIQ - Milestone M2.5 Consolidated Data Reliability Matrix Generator (Refined)
Script: src/generate_m2_5_reliability_matrix.py

Generates the comprehensive 29-item Data Reliability Matrix:
- CONFIRMED: 14 items
- PROVISIONAL: 3 items
- EXTERNAL_ENRICHMENT_REQUIRED: 5 items
- UNRESOLVED: 3 items
- EXCLUDED: 4 items
Total: 29 items (100% unique, zero duplicates, exactly matching M2_5_DOMAIN_REVIEW.md)
"""

import os
import pandas as pd

BASE_DIR = os.path.abspath(".")
REPORTS_DIR = os.path.join(BASE_DIR, "audit_reports", "performance_metrics")
os.makedirs(REPORTS_DIR, exist_ok=True)

matrix_data = [
    # -------------------------------------------------------------
    # CONFIRMED (14 items)
    # -------------------------------------------------------------
    {
        "metric_or_field": "Batter Runs (Off Bat)",
        "classification": "CONFIRMED",
        "definition": "Runs scored directly off the bat by the striker on legal balls or no-balls.",
        "formula": "sum(runs)",
        "source_columns": "ball_by_ball.runs",
        "external_dependencies": "None (Verified against Cricsheet ground truth)",
        "validation_sample_size": "145 active striker innings across 8 pilot matches; 18 scorecard innings in M2.2B",
        "known_limitations": "Does not include extras awarded to the team (byes, leg-byes, wides, no-balls).",
        "pressure_analysis_suitability": "YES - Primary batting output measure."
    },
    {
        "metric_or_field": "Balls Faced",
        "classification": "CONFIRMED",
        "definition": "Deliveries faced by the striker that count towards batting strike rate.",
        "formula": "count(striker deliveries) - count(wides faced)",
        "source_columns": "ball_by_ball.striker_id, ball_by_ball.extras_type (or ext_batter_balls_faced)",
        "external_dependencies": "None (Formula mathematically proven 100% across 145 innings)",
        "validation_sample_size": "145 active striker innings (1,994 deliveries)",
        "known_limitations": "Non-strikers run out facing 0 balls (diamond ducks) have 0 balls faced and 0 delivery rows as striker.",
        "pressure_analysis_suitability": "YES - Essential denominator for batting strike rate and dot ball percentage."
    },
    {
        "metric_or_field": "Batting Strike Rate",
        "classification": "CONFIRMED",
        "definition": "Scoring velocity per 100 balls faced.",
        "formula": "(Batter Runs / Balls Faced) * 100",
        "source_columns": "Derived from Batter Runs and Balls Faced",
        "external_dependencies": "None",
        "validation_sample_size": "145 active striker innings",
        "known_limitations": "Undefined when Balls Faced == 0 (e.g. diamond ducks). Sensitive to extreme small-sample noise (< 10 balls).",
        "pressure_analysis_suitability": "YES - Core measure of scoring urgency in pressure phases."
    },
    {
        "metric_or_field": "Boundary Fours",
        "classification": "CONFIRMED",
        "definition": "Deliveries where the ball struck the boundary rope on 4 runs.",
        "formula": "count(is_four == True)",
        "source_columns": "ball_by_ball.is_four",
        "external_dependencies": "None",
        "validation_sample_size": "145 batter innings (100% agreement)",
        "known_limitations": "20 rows in dataset have runs==4 and is_four==False, which represent all-run non-boundary fours.",
        "pressure_analysis_suitability": "YES - Boundary-hitting efficiency metric."
    },
    {
        "metric_or_field": "Boundary Sixes",
        "classification": "CONFIRMED",
        "definition": "Deliveries where the ball cleared the boundary rope on the full for 6 runs.",
        "formula": "count(is_six == True)",
        "source_columns": "ball_by_ball.is_six",
        "external_dependencies": "None",
        "validation_sample_size": "145 batter innings (100% agreement)",
        "known_limitations": "3 rows in dataset have runs==6 and is_six==False.",
        "pressure_analysis_suitability": "YES - Maximum boundary power metric."
    },
    {
        "metric_or_field": "Batting Dismissals / Outs",
        "classification": "CONFIRMED",
        "definition": "Count of times a batter was dismissed (out).",
        "formula": "count(is_wicket == True and dismissed_player_id == striker_id and dismissal_type != 'retired hurt')",
        "source_columns": "ball_by_ball.is_wicket, dismissed_player_id, dismissal_type",
        "external_dependencies": "None (Retired hurt proven as non-out under MCC Law 25.4.2)",
        "validation_sample_size": "145 batter innings",
        "known_limitations": "Must explicitly exclude retired hurt (e.g. Sanju Samson in match 40725). Run outs at non-striker end require dismissed_player_id check.",
        "pressure_analysis_suitability": "YES - Required for batting average and dismissal rate."
    },
    {
        "metric_or_field": "Legal Balls Bowled",
        "classification": "CONFIRMED",
        "definition": "Number of fair, legal deliveries completed towards the 6-ball over.",
        "formula": "count(deliveries where extras_type not in ['wide', 'Overstep', 'other'])",
        "source_columns": "ball_by_ball.bowler_id, ball_by_ball.extras_type (or ext_is_legal_delivery)",
        "external_dependencies": "None (Formula mathematically proven 100% across 99 bowler innings)",
        "validation_sample_size": "99 bowler innings (20 match innings)",
        "known_limitations": "Requires excluding 'other' (uncredited no-balls with runs off bat) alongside 'wide' and 'Overstep'.",
        "pressure_analysis_suitability": "YES - Indispensable denominator for economy rate, strike rate, and overs bowled."
    },
    {
        "metric_or_field": "Bowler-Credited Wickets",
        "classification": "CONFIRMED",
        "definition": "Wickets credited to the bowler's individual record under MCC Laws.",
        "formula": "count(is_wicket == True and dismissal_type in ['Bowled', 'Caught', 'LBW', 'Stump', 'Hit Wicket'])",
        "source_columns": "ball_by_ball.is_wicket, ball_by_ball.dismissal_type (or ext_is_bowler_wicket)",
        "external_dependencies": "None",
        "validation_sample_size": "99 bowler innings (100% match across all direct modes)",
        "known_limitations": "Must exclude RunOut (fielding wicket) and Retire Out (tactical retirement).",
        "pressure_analysis_suitability": "YES - Core wicket-taking impact metric."
    },
    {
        "metric_or_field": "Bowling Strike Rate",
        "classification": "CONFIRMED",
        "definition": "Legal balls bowled per bowler-credited wicket.",
        "formula": "Legal Balls Bowled / Bowler Wickets",
        "source_columns": "Derived from Legal Balls and Bowler Wickets",
        "external_dependencies": "None",
        "validation_sample_size": "64 bowler innings with >= 1 wicket (100% match)",
        "known_limitations": "Undefined when Bowler Wickets == 0 (35 out of 99 bowler innings in pilot).",
        "pressure_analysis_suitability": "YES - Essential measure of wicket-taking frequency under pressure."
    },
    {
        "metric_or_field": "Innings Label",
        "classification": "CONFIRMED",
        "definition": "Identifies the match innings (1 = first innings, 2 = chase, 3/4 = Super Over).",
        "formula": "ball_by_ball.innings",
        "source_columns": "ball_by_ball.innings",
        "external_dependencies": "None",
        "validation_sample_size": "All 200,999 deliveries across 883 matches",
        "known_limitations": "Super Overs are represented by innings 3 and 4 across 6 matches.",
        "pressure_analysis_suitability": "YES - Establishes chasing vs target-setting context."
    },
    {
        "metric_or_field": "Wickets Lost Before Delivery",
        "classification": "CONFIRMED",
        "definition": "Team wickets fallen in the innings prior to the current delivery.",
        "formula": "cumsum(is_wicket == True and dismissal_type != 'retired hurt') - current delivery wicket",
        "source_columns": "ball_by_ball.is_wicket, dismissal_type, innings_ball_num",
        "external_dependencies": "None (Requires strictly excluding retired hurt)",
        "validation_sample_size": "All 1,994 pilot deliveries",
        "known_limitations": "Must account for retired hurt departures which do not reduce wickets in hand.",
        "pressure_analysis_suitability": "YES - Measures resource loss and batting collapse pressure."
    },
    {
        "metric_or_field": "Wickets in Hand",
        "classification": "CONFIRMED",
        "definition": "Remaining wickets available to the batting side (10 - wickets lost).",
        "formula": "10 - Wickets Lost Before Delivery",
        "source_columns": "Derived from Wickets Lost Before Delivery",
        "external_dependencies": "None",
        "validation_sample_size": "All 1,994 pilot deliveries",
        "known_limitations": "Assumes standard 11-player lineup (10 dismissable wickets).",
        "pressure_analysis_suitability": "YES - Major factor in resource pressure."
    },
    {
        "metric_or_field": "Match Phase (Standard 20-Over Matches)",
        "classification": "CONFIRMED",
        "definition": "Strategic game phase in full 20-over fixtures: Powerplay (balls 1-36), Middle (balls 37-90), Death (balls 91-120).",
        "formula": "Derived from cumsum(ext_is_legal_delivery)",
        "source_columns": "ext_is_legal_delivery",
        "external_dependencies": "None (Requires legal ball progression, not raw overid)",
        "validation_sample_size": "All standard 20-over innings in pilot",
        "known_limitations": "Applies strictly to standard 20-over matches; shortened matches require prorated playing conditions.",
        "pressure_analysis_suitability": "YES - Essential for phase-specific pressure evaluation (e.g. Death overs)."
    },
    {
        "metric_or_field": "Super Over Indicator",
        "classification": "CONFIRMED",
        "definition": "Indicates extreme tie-break pressure situation.",
        "formula": "innings in [3, 4]",
        "source_columns": "ball_by_ball.innings",
        "external_dependencies": "None",
        "validation_sample_size": "6 Super Over matches in dataset (4 innings in pilot)",
        "known_limitations": "Extremely small sample size (only 6 matches across 883). Cannot be used in isolation for player rankings.",
        "pressure_analysis_suitability": "YES - Maximum pressure flag (contextual multiplier or qualitative review)."
    },

    # -------------------------------------------------------------
    # PROVISIONAL (3 items)
    # -------------------------------------------------------------
    {
        "metric_or_field": "Batting Average",
        "classification": "PROVISIONAL",
        "definition": "Runs scored per dismissal.",
        "formula": "sum(Batter Runs) / count(Dismissals)",
        "source_columns": "Derived from Batter Runs and Dismissals",
        "external_dependencies": "None",
        "validation_sample_size": "Sample-validated; undefined when Dismissals == 0 (Not Out innings)",
        "known_limitations": "Undefined for not-out innings (division by zero); heavily distorted in short T20 sample sizes.",
        "pressure_analysis_suitability": "CONDITIONAL - Requires minimum innings threshold; strike rate and balls per dismissal are preferred in T20."
    },
    {
        "metric_or_field": "Legal Balls Remaining (Standard 20-Over Matches)",
        "classification": "PROVISIONAL",
        "definition": "Remaining legal deliveries available to complete a regulation 20-over innings.",
        "formula": "120 - cumsum(ext_is_legal_delivery prior)",
        "source_columns": "ext_is_legal_delivery",
        "external_dependencies": "Assumes standard 120-ball allocation",
        "validation_sample_size": "Standard 20-over pilot fixtures",
        "known_limitations": "Assumes full 20 overs (120 balls). Does not apply to curtailed or rain-interrupted matches.",
        "pressure_analysis_suitability": "YES for regulation 20-over matches; EXCLUDED for shortened matches."
    },
    {
        "metric_or_field": "Target Score (Standard 20-Over Chase)",
        "classification": "PROVISIONAL",
        "definition": "Target runs required to win in an uninterrupted regulation 20-over Innings 2.",
        "formula": "Innings 1 Total Runs + 1",
        "source_columns": "Innings 1 cumulative total runs",
        "external_dependencies": "Hybrid enrichment for exact Innings 1 total runs",
        "validation_sample_size": "Standard pilot chasing matches",
        "known_limitations": "Valid only when Innings 1 was completed without interruption. Missing from raw matches.csv.",
        "pressure_analysis_suitability": "YES for uninterrupted chases; DO NOT apply to mid-match rain curtailments."
    },

    # -------------------------------------------------------------
    # EXTERNAL_ENRICHMENT_REQUIRED (5 items)
    # -------------------------------------------------------------
    {
        "metric_or_field": "Bowler Runs Conceded",
        "classification": "EXTERNAL_ENRICHMENT_REQUIRED",
        "definition": "Total runs debited against the bowler (batter runs + wide runs + no-ball runs).",
        "formula": "sum(ext_bowler_debit_runs)",
        "source_columns": "ball_by_ball.runs, ext_bowler_debit_runs",
        "external_dependencies": "Cricsheet delivery extras breakdown (to separate bowler debits from team byes/leg-byes/penalties)",
        "validation_sample_size": "99 bowler innings across 8 pilot matches (100% match)",
        "known_limitations": "Raw CSV lacks explicit delivery-level bye/leg-bye/wide run amounts; naive local sum is unreliable without hybrid layer.",
        "pressure_analysis_suitability": "YES (with Hybrid Layer) - Core bowling containment metric."
    },
    {
        "metric_or_field": "Bowler Economy Rate",
        "classification": "EXTERNAL_ENRICHMENT_REQUIRED",
        "definition": "Average runs conceded per 6 legal balls bowled.",
        "formula": "Bowler Runs Conceded / (Legal Balls Bowled / 6.0)",
        "source_columns": "ext_bowler_debit_runs, ext_is_legal_delivery",
        "external_dependencies": "Cricsheet delivery extras breakdown",
        "validation_sample_size": "99 bowler innings",
        "known_limitations": "Requires Legal Balls >= 1. Distorted over very small samples (e.g. 1 over).",
        "pressure_analysis_suitability": "YES (with Hybrid Layer) - Primary pressure metric in death overs and powerplay."
    },
    {
        "metric_or_field": "Bowling Average",
        "classification": "EXTERNAL_ENRICHMENT_REQUIRED",
        "definition": "Runs conceded per bowler-credited wicket.",
        "formula": "Bowler Runs Conceded / Bowler Wickets",
        "source_columns": "ext_bowler_debit_runs, Bowler Wickets",
        "external_dependencies": "Cricsheet delivery extras breakdown",
        "validation_sample_size": "64 bowler innings with >= 1 wicket (100% match)",
        "known_limitations": "Undefined when Bowler Wickets == 0. Highly volatile in short T20 spells.",
        "pressure_analysis_suitability": "CONDITIONAL - Secondary to economy and strike rate in T20 pressure contexts."
    },
    {
        "metric_or_field": "Cumulative Score Before Delivery",
        "classification": "EXTERNAL_ENRICHMENT_REQUIRED",
        "definition": "Running innings total runs accumulated prior to the current delivery.",
        "formula": "cumsum(ext_delivery_total_runs) - current delivery total runs",
        "source_columns": "ext_delivery_total_runs, innings_ball_num",
        "external_dependencies": "Cricsheet delivery total runs (including all extras)",
        "validation_sample_size": "1,994 deliveries across 20 innings (100% exact match)",
        "known_limitations": "Cannot be computed from raw CSV alone because raw extras amounts (byes/leg-byes/wides) are not stored as delivery runs.",
        "pressure_analysis_suitability": "YES (with Hybrid Layer) - Critical input for required run rate and pressure state."
    },
    {
        "metric_or_field": "Required Run Rate (RRR in Standard Chases)",
        "classification": "EXTERNAL_ENRICHMENT_REQUIRED",
        "definition": "Runs required per 6 legal balls to achieve the target in uninterrupted Innings 2.",
        "formula": "(Runs Required / Legal Balls Remaining) * 6.0",
        "source_columns": "Derived from Target, Cumulative Score, and Legal Balls Remaining",
        "external_dependencies": "Hybrid layer for exact score and legal balls",
        "validation_sample_size": "Pilot standard chasing innings",
        "known_limitations": "Undefined when Legal Balls Remaining == 0. Volatile in final over (< 6 balls). Meaningless in Innings 1.",
        "pressure_analysis_suitability": "YES (Innings 2 only) - Gold standard measure of chase pressure."
    },

    # -------------------------------------------------------------
    # UNRESOLVED (3 items)
    # -------------------------------------------------------------
    {
        "metric_or_field": "Playing Eleven Participation (is_played)",
        "classification": "UNRESOLVED",
        "definition": "Participation flag in playing_eleven.csv.",
        "formula": "playing_eleven.is_played",
        "source_columns": "playing_eleven.is_played",
        "external_dependencies": "None",
        "validation_sample_size": "28,381 rows profiled in M1/M2.1",
        "known_limitations": "8,678 missing batting orders; 75 repeated player keys; does not prove actual participation (substitutes vs starters). Actual participation must be verified from ball_by_ball.csv.",
        "pressure_analysis_suitability": "NO - Use ball_by_ball appearance as proof of participation."
    },
    {
        "metric_or_field": "Revised DLS Target & Mid-Match Interruption Timing",
        "classification": "UNRESOLVED",
        "definition": "Target score and required run rate in rain-interrupted/curtailed fixtures.",
        "formula": "matches.revised_target",
        "source_columns": "matches.revised_target, first_inn_revised_overs, second_inn_revised_overs",
        "external_dependencies": "Delivery index of rain delay / interruption point",
        "validation_sample_size": "23 matches with revised_target; 34 matches with revised overs",
        "known_limitations": "Interruption delivery index is NOT recorded in raw CSVs. Applying revised target from ball 0.1 causes information leakage / historical backcasting.",
        "pressure_analysis_suitability": "UNRESOLVED - Cannot calculate pre-delivery RRR in rain-curtailed chases without delivery interruption timestamps."
    },
    {
        "metric_or_field": "Match Phase in Shortened Matches",
        "classification": "UNRESOLVED",
        "definition": "Prorated phase boundaries (Powerplay / Middle / Death) in curtailed matches.",
        "formula": "Prorated by scheduled overs",
        "source_columns": "matches.first_inn_revised_overs / second_inn_revised_overs",
        "external_dependencies": "Competition-specific playing conditions table (Appendix 1)",
        "validation_sample_size": "34 curtailed matches in dataset",
        "known_limitations": "Standard 6-over Powerplay does not apply to 5-15 over innings. Scale of revised overs fields is undocumented.",
        "pressure_analysis_suitability": "UNRESOLVED - Exclude curtailed matches from phase-specific death/powerplay comparisons."
    },

    # -------------------------------------------------------------
    # EXCLUDED (4 items)
    # -------------------------------------------------------------
    {
        "metric_or_field": "Bowling Delivery Speed (bowl_speed)",
        "classification": "EXCLUDED",
        "definition": "Telemetry speed recorded in raw dataset.",
        "formula": "ball_by_ball.bowl_speed",
        "source_columns": "ball_by_ball.bowl_speed",
        "external_dependencies": "None",
        "validation_sample_size": "200,999 deliveries profiled in M1",
        "known_limitations": "77,861 zeros, negative values (-1), values > 1400 km/h; undocumented units and calibration. Unusable.",
        "pressure_analysis_suitability": "NO - EXCLUDED from all performance analysis."
    },
    {
        "metric_or_field": "Player of the Match (man_of_the_match)",
        "classification": "EXCLUDED",
        "definition": "Award identifier in matches.csv.",
        "formula": "matches.man_of_the_match",
        "source_columns": "matches.man_of_the_match",
        "external_dependencies": "None",
        "validation_sample_size": "883 matches profiled in M1",
        "known_limitations": "119 matches have value 0 (unmapped/unawarded); highly subjective post-match editorial judgment.",
        "pressure_analysis_suitability": "NO - EXCLUDED from objective pressure rating."
    },
    {
        "metric_or_field": "Qualitative Shot Style (stroke)",
        "classification": "EXCLUDED",
        "definition": "Qualitative shot descriptor in ball_by_ball.csv.",
        "formula": "ball_by_ball.stroke",
        "source_columns": "ball_by_ball.stroke",
        "external_dependencies": "None",
        "validation_sample_size": "200,999 deliveries",
        "known_limitations": "Sparse (missing on 6,158 rows), unvalidated taxonomy, subjective observer coding.",
        "pressure_analysis_suitability": "NO - EXCLUDED from quantitative performance metrics."
    },
    {
        "metric_or_field": "Qualitative Delivery Style (delivery_style)",
        "classification": "EXCLUDED",
        "definition": "Qualitative ball movement/trajectory descriptor.",
        "formula": "ball_by_ball.delivery_style",
        "source_columns": "ball_by_ball.delivery_style",
        "external_dependencies": "None",
        "validation_sample_size": "200,999 deliveries",
        "known_limitations": "Sparse (missing on 391 rows), unvalidated taxonomy, subjective observer coding.",
        "pressure_analysis_suitability": "NO - EXCLUDED from quantitative performance metrics."
    }
]

df = pd.DataFrame(matrix_data)
csv_path = os.path.join(REPORTS_DIR, "consolidated_data_reliability_matrix.csv")
df.to_csv(csv_path, index=False)
print(f"Saved {csv_path} ({len(df)} unique metrics/fields cataloged)")
print("Breakdown by classification:")
print(df["classification"].value_counts())
