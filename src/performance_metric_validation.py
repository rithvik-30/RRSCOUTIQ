"""Generate the read-only M2.4 metric and enrichment feasibility audit."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "extracted"
OUTPUT_DIR = ROOT / "audit_reports" / "performance_metrics"
BASELINE_HASH_PATH = (
    ROOT
    / "audit_reports"
    / "rules_validation"
    / "provider_encoding_resolution"
    / "source_hash_verification.csv"
)
SCORECARD_PATH = (
    ROOT
    / "audit_reports"
    / "rules_validation"
    / "provider_encoding_resolution"
    / "scorecard_validation.csv"
)
RULES_EVIDENCE_DIR = ROOT / "audit_reports" / "rules_validation"
SOURCE_FILES = [
    ROOT / "data" / "data_pack.zip.zip",
    DATA_DIR / "ball_by_ball.csv",
    DATA_DIR / "matches.csv",
    DATA_DIR / "playing_eleven.csv",
    DATA_DIR / "competition_team_player_mapping.csv",
    DATA_DIR / "teams.csv",
    DATA_DIR / "competitions.csv",
]
REQUIRED_BALL_COLUMNS = {
    "match_id",
    "innings",
    "striker_id",
    "bowler_id",
    "runs",
    "is_four",
    "is_six",
    "is_wicket",
    "dismissal_type",
    "dismissed_player_id",
    "extras_type",
    "extras1_runs",
    "extras_2_runs",
    "innings_ball_num",
    "overid",
    "over_ball_num",
}
REQUIRED_OUTPUTS = [
    OUTPUT_DIR / "metric_feasibility_matrix.csv",
    OUTPUT_DIR / "metric_validation_report.md",
    OUTPUT_DIR / "external_source_investigation.md",
    OUTPUT_DIR / "join_feasibility_report.md",
    OUTPUT_DIR / "final_methodology_recommendation.md",
    OUTPUT_DIR / "join_sample.csv",
    OUTPUT_DIR / "source_hash_verification.csv",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_raw_csv(path: Path, **kwargs: object) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, **kwargs)


def verify_source_hashes() -> pd.DataFrame:
    if not BASELINE_HASH_PATH.is_file():
        raise FileNotFoundError(f"Source hash baseline not found: {BASELINE_HASH_PATH}")
    baseline = read_raw_csv(BASELINE_HASH_PATH)
    if not {"source_file", "sha256"}.issubset(baseline.columns):
        raise ValueError(f"Unexpected source-hash schema: {BASELINE_HASH_PATH}")
    baseline_by_name = {
        Path(row.source_file).name: row.sha256
        for row in baseline.itertuples(index=False)
    }

    results: list[dict[str, str]] = []
    for path in SOURCE_FILES:
        if not path.is_file():
            raise FileNotFoundError(f"Protected source file not found: {path}")
        expected = baseline_by_name.get(path.name, "")
        actual = sha256(path)
        status = "MATCH" if expected and actual == expected else "NO BASELINE OR MISMATCH"
        results.append(
            {
                "source_file": path.relative_to(ROOT).as_posix(),
                "sha256": actual,
                "baseline_source": BASELINE_HASH_PATH.relative_to(ROOT).as_posix(),
                "baseline_sha256": expected,
                "baseline_result": status,
            }
        )

    result = pd.DataFrame(results)
    if not result["baseline_result"].eq("MATCH").all():
        raise AssertionError(
            "Protected source hashes differ from the retained baseline: "
            f"{result.loc[result.baseline_result.ne('MATCH')].to_dict('records')}"
        )
    return result


def source_csv(path: Path, **kwargs: object) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Required audit input not found: {path}")
    return read_raw_csv(path, **kwargs)


def source_evidence() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    balls = source_csv(DATA_DIR / "ball_by_ball.csv")
    missing_columns = sorted(REQUIRED_BALL_COLUMNS - set(balls.columns))
    if missing_columns:
        raise ValueError(f"ball_by_ball.csv is missing required columns: {missing_columns}")

    scorecard = source_csv(SCORECARD_PATH)
    required_scorecard_columns = {
        "match_id",
        "match_date",
        "competition",
        "format",
        "innings",
        "scorecard_url",
        "validation_dimension",
        "comparison_status",
    }
    if not required_scorecard_columns.issubset(scorecard.columns):
        raise ValueError(f"Unexpected scorecard validation schema: {SCORECARD_PATH}")

    regulation = scorecard[scorecard["innings"].isin({"1", "2"})].copy()
    regulation["match_id"] = pd.to_numeric(regulation["match_id"], errors="raise").astype(int)
    regulation["innings_num"] = pd.to_numeric(regulation["innings"], errors="raise").astype(int)
    innings_sample = regulation[
        ["match_id", "match_date", "competition", "format", "innings_num", "scorecard_url"]
    ].drop_duplicates()
    match_sample = innings_sample[
        ["match_id", "match_date", "competition", "format", "scorecard_url"]
    ].drop_duplicates()

    matches = source_csv(DATA_DIR / "matches.csv")
    competitions = source_csv(DATA_DIR / "competitions.csv")
    teams = source_csv(DATA_DIR / "teams.csv")
    matches["match_id"] = pd.to_numeric(matches["match_id"], errors="raise").astype(int)
    matches["comp_id"] = pd.to_numeric(matches["comp_id"], errors="raise").astype(int)
    competitions["comp_id"] = pd.to_numeric(competitions["comp_id"], errors="raise").astype(int)
    teams["comp_id"] = pd.to_numeric(teams["comp_id"], errors="raise").astype(int)
    teams["team_id"] = pd.to_numeric(teams["team_id"], errors="raise").astype(int)
    balls["match_id"] = pd.to_numeric(balls["match_id"], errors="raise").astype(int)
    balls["innings"] = pd.to_numeric(balls["innings"], errors="raise").astype(int)
    balls["batting_team_id"] = pd.to_numeric(
        balls["batting_team_id"], errors="raise"
    ).astype(int)

    joined = match_sample.merge(
        matches[["match_id", "comp_id", "match_date"]],
        how="left",
        on="match_id",
        validate="one_to_one",
        suffixes=("_scorecard", "_local"),
        indicator=True,
    )
    joined = joined.merge(
        competitions[["comp_id", "comp_name", "match_format"]],
        how="left",
        on="comp_id",
        validate="many_to_one",
    )
    joined["local_date_matches_retained_date"] = (
        joined["match_date_scorecard"] == joined["match_date_local"]
    )
    joined["local_competition_name_matches"] = (
        joined["competition"] == joined["comp_name"]
    )
    joined["local_format_matches"] = joined["format"] == joined["match_format"]

    local_innings = (
        balls.groupby(["match_id", "innings"], as_index=False)
        .agg(
            delivery_rows=("innings_ball_num", "size"),
            batting_team_ids=("batting_team_id", lambda values: "|".join(
                str(value) for value in sorted(set(values))
            )),
        )
    )
    sample_innings = innings_sample.merge(
        local_innings,
        how="left",
        left_on=["match_id", "innings_num"],
        right_on=["match_id", "innings"],
        validate="one_to_one",
    )
    sample_innings["local_innings_exists"] = sample_innings["delivery_rows"].notna()
    sample_innings = sample_innings.merge(
        matches[["match_id", "comp_id"]], on="match_id", how="left", validate="many_to_one"
    )

    def team_context_is_mapped(row: pd.Series) -> bool:
        if not row["local_innings_exists"]:
            return False
        team_ids = [int(value) for value in row["batting_team_ids"].split("|") if value]
        return all(
            (
                (teams["comp_id"] == int(row["comp_id"]))
                & (teams["team_id"] == team_id)
            ).any()
            for team_id in team_ids
        )

    sample_innings["local_batting_team_context_maps"] = sample_innings.apply(
        team_context_is_mapped, axis=1
    )

    if len(innings_sample) != 18 or len(match_sample) != 9:
        raise AssertionError(
            "Expected the retained 18 regulation innings across nine scorecard "
            f"matches; found {len(innings_sample)} innings and {len(match_sample)} matches."
        )
    if not joined["_merge"].eq("both").all():
        raise AssertionError("A retained scorecard match ID no longer joins locally.")
    if not joined[
        [
            "local_date_matches_retained_date",
            "local_competition_name_matches",
            "local_format_matches",
        ]
    ].all().all():
        raise AssertionError("Retained scorecard match metadata does not match local metadata.")
    if not sample_innings[
        ["local_innings_exists", "local_batting_team_context_maps"]
    ].all().all():
        raise AssertionError("A retained regulation innings or batting-team context is unmapped.")

    return regulation, joined, sample_innings


def metric_matrix(scorecard: pd.DataFrame) -> pd.DataFrame:
    run_checks = scorecard[
        scorecard["validation_dimension"].eq("runs field sum vs scorecard batter-run subtotal")
    ]
    wicket_checks = scorecard[
        scorecard["validation_dimension"].eq("source is_wicket count vs scorecard wickets")
    ]
    balls_faced_checks = scorecard[
        scorecard["validation_dimension"].eq("batter balls faced")
    ]
    bowler_runs_checks = scorecard[
        scorecard["validation_dimension"].eq("bowler runs conceded")
    ]
    bowler_wicket_checks = scorecard[
        scorecard["validation_dimension"].eq("bowler-creditable wickets")
    ]
    candidate_ball_checks = scorecard[
        scorecard["validation_dimension"].eq("candidate ball count vs scorecard overs")
    ]
    evidence = {
        "runs_exact": int(run_checks["comparison_status"].eq("EXACT MATCH").sum()),
        "runs_rows": len(run_checks),
        "wickets_exact": int(wicket_checks["comparison_status"].eq("EXACT MATCH").sum()),
        "wickets_rows": len(wicket_checks),
        "balls_faced_unverifiable": int(
            balls_faced_checks["comparison_status"].eq("UNVERIFIABLE").sum()
        ),
        "bowler_runs_unverifiable": int(
            bowler_runs_checks["comparison_status"].eq("UNVERIFIABLE").sum()
        ),
        "bowler_wickets_unverifiable": int(
            bowler_wicket_checks["comparison_status"].eq("UNVERIFIABLE").sum()
        ),
        "candidate_balls_partial": int(
            candidate_ball_checks["comparison_status"].eq("PARTIAL MATCH").sum()
        ),
    }

    rows = [
        {
            "discipline": "Batting",
            "metric": "Batter runs",
            "exact_source_columns": "runs; striker_id; match_id; innings",
            "candidate_calculation_or_rule": (
                "Sum validated batter-run events by batter/innings; no player-level metric is calculated here."
            ),
            "evidence_status": "PROBABLE",
            "recommendation": "PROVISIONAL",
            "sample_size_and_validation_coverage": (
                f"{evidence['runs_exact']}/{evidence['runs_rows']} aggregate innings "
                "exactly match scorecard batter-run subtotals; zero player-level scorecard "
                "reconciliations are retained."
            ),
            "edge_cases_and_failure_conditions": (
                "Aggregate equality does not prove delivery or player attribution; extras, "
                "special innings, and provider scope remain open."
            ),
            "open_dependencies": (
                "Player-level scorecard comparisons; provider definition; special-innings and extras handling."
            ),
        },
        {
            "discipline": "Batting",
            "metric": "Balls faced",
            "exact_source_columns": (
                "striker_id; extras_type; extras1_runs; extras_2_runs; innings_ball_num"
            ),
            "candidate_calculation_or_rule": (
                "Count only deliveries proven to count as a ball faced under provider and applicable scoring rules."
            ),
            "evidence_status": "UNRESOLVED",
            "recommendation": "EXCLUDE",
            "sample_size_and_validation_coverage": (
                f"{evidence['balls_faced_unverifiable']}/18 regulation innings are "
                "UNVERIFIABLE; player-level external balls-faced values were not retained."
            ),
            "edge_cases_and_failure_conditions": (
                "Wides, No balls, and unusual events; innings_ball_num is a stored row sequence, not a legal-ball count."
            ),
            "open_dependencies": "Provider event mapping and player-level scorecard evidence.",
        },
        {
            "discipline": "Batting",
            "metric": "Strike rate",
            "exact_source_columns": "runs; striker_id; validated balls faced",
            "candidate_calculation_or_rule": "100 * validated batter runs / validated balls faced.",
            "evidence_status": "UNRESOLVED",
            "recommendation": "EXCLUDE",
            "sample_size_and_validation_coverage": (
                "No player-level numerator validation; balls-faced denominator has zero independently validated player values."
            ),
            "edge_cases_and_failure_conditions": "Zero balls faced; incomplete innings; unvalidated extras and dismissal events.",
            "open_dependencies": "Validated player runs, balls faced, and minimum-opportunity policy.",
        },
        {
            "discipline": "Batting",
            "metric": "Batting average",
            "exact_source_columns": "runs; dismissed_player_id; is_wicket; dismissal_type",
            "candidate_calculation_or_rule": (
                "Validated batter runs / dismissals charged to that batter; not calculated."
            ),
            "evidence_status": "UNRESOLVED",
            "recommendation": "EXCLUDE",
            "sample_size_and_validation_coverage": (
                "Dismissal categories were inspected; 13 source rows have wicket/player-ID inconsistencies; "
                "no complete player dismissal-scorecard reconciliation exists."
            ),
            "edge_cases_and_failure_conditions": (
                "Retire Out, missing dismissed-player ID, 12 IDs with false wicket flags, not-out innings, and provider semantics."
            ),
            "open_dependencies": "Player-level runs and dismissal denominators validated by category.",
        },
        {
            "discipline": "Batting",
            "metric": "Fours",
            "exact_source_columns": "is_four; runs; striker_id",
            "candidate_calculation_or_rule": "Count validated batter four outcomes; do not repair false flags.",
            "evidence_status": "PROBABLE",
            "recommendation": "PROVISIONAL",
            "sample_size_and_validation_coverage": (
                "All true flags agree with runs=4 in the prior audit; 20 runs=4 rows have false flags; "
                "no player-level scorecard boundary check is retained."
            ),
            "edge_cases_and_failure_conditions": "Incomplete flags and unclear boundary semantics on extras-related rows.",
            "open_dependencies": "Provider definition and player-level boundary scorecard comparison.",
        },
        {
            "discipline": "Batting",
            "metric": "Sixes",
            "exact_source_columns": "is_six; runs; striker_id",
            "candidate_calculation_or_rule": "Count validated batter six outcomes; do not repair false flags.",
            "evidence_status": "PROBABLE",
            "recommendation": "PROVISIONAL",
            "sample_size_and_validation_coverage": (
                "All true flags agree with runs=6 in the prior audit; 3 runs=6 rows have false flags; "
                "no player-level scorecard boundary check is retained."
            ),
            "edge_cases_and_failure_conditions": "Incomplete flags and unclear boundary semantics on extras-related rows.",
            "open_dependencies": "Provider definition and player-level boundary scorecard comparison.",
        },
        {
            "discipline": "Batting",
            "metric": "Dismissal information",
            "exact_source_columns": "is_wicket; dismissal_type; dismissed_player_id",
            "candidate_calculation_or_rule": (
                "Retain raw source categories and flags for audit only; do not infer missing IDs."
            ),
            "evidence_status": "CONDITIONAL",
            "recommendation": "PROVISIONAL",
            "sample_size_and_validation_coverage": (
                f"{evidence['wickets_exact']}/{evidence['wickets_rows']} selected regulation innings "
                "match aggregate team-wicket counts; one detailed innings was compared by dismissal."
            ),
            "edge_cases_and_failure_conditions": (
                "13 flag/ID inconsistencies; Retire Out; misspelled Obstructing label; blank and unfamiliar categories."
            ),
            "open_dependencies": "Provider meaning, category normalization, and player-level dismissal reconciliation.",
        },
        {
            "discipline": "Bowling",
            "metric": "Wickets credited to bowler",
            "exact_source_columns": "is_wicket; dismissal_type; dismissed_player_id; bowler_id",
            "candidate_calculation_or_rule": (
                "Apply category-level credit rules only after provider labels and dismissed events are validated."
            ),
            "evidence_status": "UNRESOLVED",
            "recommendation": "EXCLUDE",
            "sample_size_and_validation_coverage": (
                f"{evidence['bowler_wickets_unverifiable']}/18 retained metric comparisons are "
                "UNVERIFIABLE; a separate one-innings detailed dismissal/bowling-figures comparison "
                "is limited corroboration."
            ),
            "edge_cases_and_failure_conditions": (
                "RunOut, Retire Out, Obstructing the field, unknown provider spellings, and ID/flag disagreements."
            ),
            "open_dependencies": "Provider category mapping and bowler-figures reconciliation across more matches.",
        },
        {
            "discipline": "Bowling",
            "metric": "Runs conceded by bowler",
            "exact_source_columns": (
                "bowler_id; runs; extras_type; extras1_runs; extras_2_runs"
            ),
            "candidate_calculation_or_rule": (
                "Sum striker runs plus applicable bowler-charged extras only after each field/event is validated."
            ),
            "evidence_status": "UNRESOLVED",
            "recommendation": "EXCLUDE",
            "sample_size_and_validation_coverage": (
                f"{evidence['bowler_runs_unverifiable']}/18 regulation innings are UNVERIFIABLE; "
                "per-bowler scorecard figures are not retained."
            ),
            "edge_cases_and_failure_conditions": (
                "Wide/No-ball mapping, Byes/Leg-byes, penalty runs, multiple extras, and non-additive encoded fields."
            ),
            "open_dependencies": "Provider codebook and exact per-bowler scorecard reconciliation.",
        },
        {
            "discipline": "Bowling",
            "metric": "Balls bowled",
            "exact_source_columns": (
                "bowler_id; extras_type; innings_ball_num; overid; over_ball_num"
            ),
            "candidate_calculation_or_rule": "Count validated legal balls attributed to each bowler.",
            "evidence_status": "UNRESOLVED",
            "recommendation": "EXCLUDE",
            "sample_size_and_validation_coverage": (
                f"A noncanonical candidate count is PARTIAL MATCH in {evidence['candidate_balls_partial']}/18 "
                "innings; no event-level legal-ball mapping is validated."
            ),
            "edge_cases_and_failure_conditions": (
                "Every delivery row is not a legal ball; Overstep and other categories are unresolved."
            ),
            "open_dependencies": "Legal-delivery identification and scorecard balls/overs by bowler.",
        },
        {
            "discipline": "Bowling",
            "metric": "Overs bowled",
            "exact_source_columns": "bowler_id; validated legal balls",
            "candidate_calculation_or_rule": "Derive cricket overs from validated legal-ball counts, not display-row count.",
            "evidence_status": "UNRESOLVED",
            "recommendation": "EXCLUDE",
            "sample_size_and_validation_coverage": (
                "Legal balls are unresolved; overid and over_ball_num do not provide a validated bowler over total."
            ),
            "edge_cases_and_failure_conditions": "Partial overs, illegal deliveries, interrupted innings, and source-specific labels.",
            "open_dependencies": "Validated legal-ball counts and applicable match conditions.",
        },
        {
            "discipline": "Bowling",
            "metric": "Economy rate",
            "exact_source_columns": "validated bowler runs conceded; validated legal balls",
            "candidate_calculation_or_rule": "Runs conceded per six legal balls; not calculated.",
            "evidence_status": "UNRESOLVED",
            "recommendation": "EXCLUDE",
            "sample_size_and_validation_coverage": "Both the numerator and denominator are unresolved.",
            "edge_cases_and_failure_conditions": "Partial overs and bowler-charged extras.",
            "open_dependencies": "Validated conceded runs and legal balls.",
        },
        {
            "discipline": "Bowling",
            "metric": "Bowling average",
            "exact_source_columns": "validated bowler runs conceded; validated bowler-creditable wickets",
            "candidate_calculation_or_rule": "Bowler runs conceded / bowler-creditable wickets; not calculated.",
            "evidence_status": "UNRESOLVED",
            "recommendation": "EXCLUDE",
            "sample_size_and_validation_coverage": "Both components are unresolved.",
            "edge_cases_and_failure_conditions": "Zero wickets; dismissal credit and extras allocation.",
            "open_dependencies": "Validated conceded runs and bowler-creditable wickets.",
        },
        {
            "discipline": "Bowling",
            "metric": "Bowling strike rate",
            "exact_source_columns": "validated legal balls; validated bowler-creditable wickets",
            "candidate_calculation_or_rule": "Legal balls bowled / bowler-creditable wickets; not calculated.",
            "evidence_status": "UNRESOLVED",
            "recommendation": "EXCLUDE",
            "sample_size_and_validation_coverage": "Both components are unresolved.",
            "edge_cases_and_failure_conditions": "Zero wickets; illegal deliveries; provider dismissal semantics.",
            "open_dependencies": "Validated legal balls and bowler-creditable wickets.",
        },
    ]
    rules_and_encodings = {
        "Batter runs": (
            "MCC Law 18 distinguishes bat runs from extras; provider fields require separate validation.",
            "`runs` is probable only at aggregate innings scope; extras fields remain unresolved.",
            f"{evidence['runs_exact']}/{evidence['runs_rows']} aggregate innings exact; no player-level scorecard comparison.",
        ),
        "Balls faced": (
            "Scorecard convention; whether Wide/No ball counts depends on event classification and applicable playing conditions.",
            "Wide-like label is probable; Overstep and other-event mappings remain unresolved.",
            f"{evidence['balls_faced_unverifiable']}/18 innings unverifiable; no player balls-faced values retained.",
        ),
        "Strike rate": (
            "Statistical convention: batter runs per 100 balls faced.",
            "Both player-level numerator and balls-faced event mapping are unvalidated.",
            "No player-level strike-rate components can be compared.",
        ),
        "Batting average": (
            "Statistical convention: runs per dismissal charged to the batter; not-outs are excluded from dismissal count.",
            "Dismissed-player IDs and wicket flags disagree on 13 rows; Retire Out policy/provider mapping is unresolved.",
            "No complete player-level runs-and-dismissals comparison is retained.",
        ),
        "Fours": (
            "MCC Law 19 governs boundaries; scorecard boundary count is an outcome statistic.",
            "True `is_four` agrees with `runs=4`, but 20 run-4 rows have false flags.",
            "Source flag agreement only; no player-level boundary scorecard comparison.",
        ),
        "Sixes": (
            "MCC Law 19 governs boundaries; scorecard boundary count is an outcome statistic.",
            "True `is_six` agrees with `runs=6`, but 3 run-6 rows have false flags.",
            "Source flag agreement only; no player-level boundary scorecard comparison.",
        ),
        "Dismissal information": (
            "MCC Laws 25 and 32-40 distinguish batter retirement and dismissal modes; team wickets and player dismissals are distinct.",
            "13 source flag/ID inconsistencies and an unexplained misspelled dismissal label remain.",
            "Team-wicket totals exact in selected innings; one detailed innings compared by dismissal.",
        ),
        "Wickets credited to bowler": (
            "MCC dismissal laws identify modes; conventional scorecard attribution credits only selected dismissal types.",
            "Provider spellings, dismissed-player identity, and category-to-bowler-credit mapping are not fully validated.",
            f"{evidence['bowler_wickets_unverifiable']}/18 innings unverifiable for bowler-credit figures.",
        ),
        "Runs conceded by bowler": (
            "MCC Law 18.10.3 describes bowler debits for striker runs, No-ball extras, and Wide runs when identified.",
            "`extras1_runs`, `extras_2_runs`, Overstep, and multiple-extras allocation are unresolved.",
            f"{evidence['bowler_runs_unverifiable']}/18 innings unverifiable for per-bowler runs.",
        ),
        "Balls bowled": (
            "MCC Laws 17, 21, and 22 govern valid balls and Wide/No ball events.",
            "No-ball mapping, Overstep, and other event legality are unresolved; sequence fields are not legal-ball counts.",
            f"Candidate count is PARTIAL MATCH in {evidence['candidate_balls_partial']}/18; no delivery-level legal-ball validation.",
        ),
        "Overs bowled": (
            "MCC Law 17 defines an over by valid balls; display overs can include a partial over.",
            "The dataset's overid/over_ball_num definitions and illegal-delivery mapping are unresolved.",
            "No validated legal-ball count or bowler-over comparison is retained.",
        ),
        "Economy rate": (
            "Statistical convention: bowler runs conceded per six legal balls (per over).",
            "Both bowler-charged runs and legal-ball denominators are unresolved.",
            "Neither component has a validated per-bowler comparison.",
        ),
        "Bowling average": (
            "Statistical convention: bowler runs conceded per bowler-creditable wicket.",
            "Conceded runs and dismissal credit are unresolved.",
            "Neither component has a validated per-bowler comparison.",
        ),
        "Bowling strike rate": (
            "Statistical convention: legal balls bowled per bowler-creditable wicket.",
            "Legal-ball counts and wicket credit are unresolved.",
            "Neither component has a validated per-bowler comparison.",
        ),
    }
    matrix = pd.DataFrame(rows)
    matrix["cricket_rule_or_statistical_convention"] = matrix["metric"].map(
        lambda metric: rules_and_encodings[metric][0]
    )
    matrix["unresolved_provider_encodings"] = matrix["metric"].map(
        lambda metric: rules_and_encodings[metric][1]
    )
    matrix["validation_test_result"] = matrix["metric"].map(
        lambda metric: rules_and_encodings[metric][2]
    )
    return matrix


def markdown_table(frame: pd.DataFrame) -> str:
    lines = [
        "| " + " | ".join(str(column) for column in frame.columns) + " |",
        "| " + " | ".join("---" for _ in frame.columns) + " |",
    ]
    for row in frame.itertuples(index=False, name=None):
        values = [
            str(value).replace("|", r"\|").replace("\r", " ").replace("\n", " ")
            for value in row
        ]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def write_reports(
    matrix: pd.DataFrame,
    scorecard: pd.DataFrame,
    match_sample: pd.DataFrame,
    innings_sample: pd.DataFrame,
    hashes: pd.DataFrame,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    matrix.to_csv(OUTPUT_DIR / "metric_feasibility_matrix.csv", index=False)
    hashes.to_csv(OUTPUT_DIR / "source_hash_verification.csv", index=False)

    join_rows = match_sample.merge(
        innings_sample[["match_id", "innings_num", "delivery_rows", "batting_team_ids"]],
        on="match_id",
        how="left",
    )
    join_rows["external_team_metadata_retained"] = False
    join_rows["external_player_metadata_retained"] = False
    join_rows["external_link_retest_status"] = (
        "Retained prior cross-reference; not independently re-tested in M2.4"
    )
    join_rows.to_csv(OUTPUT_DIR / "join_sample.csv", index=False)

    exact_runs = scorecard[
        (scorecard["validation_dimension"] == "runs field sum vs scorecard batter-run subtotal")
        & (scorecard["comparison_status"] == "EXACT MATCH")
        & scorecard["innings"].isin({"1", "2"})
    ]
    exact_wickets = scorecard[
        (scorecard["validation_dimension"] == "source is_wicket count vs scorecard wickets")
        & (scorecard["comparison_status"] == "EXACT MATCH")
        & scorecard["innings"].isin({"1", "2"})
    ]
    unverifiable_balls = scorecard[
        (scorecard["validation_dimension"] == "batter balls faced")
        & (scorecard["comparison_status"] == "UNVERIFIABLE")
        & scorecard["innings"].isin({"1", "2"})
    ]
    unverifiable_bowler_runs = scorecard[
        (scorecard["validation_dimension"] == "bowler runs conceded")
        & (scorecard["comparison_status"] == "UNVERIFIABLE")
        & scorecard["innings"].isin({"1", "2"})
    ]
    unverifiable_bowler_wickets = scorecard[
        (scorecard["validation_dimension"] == "bowler-creditable wickets")
        & (scorecard["comparison_status"] == "UNVERIFIABLE")
        & scorecard["innings"].isin({"1", "2"})
    ]
    partial_candidate_balls = scorecard[
        (scorecard["validation_dimension"] == "candidate ball count vs scorecard overs")
        & (scorecard["comparison_status"] == "PARTIAL MATCH")
        & scorecard["innings"].isin({"1", "2"})
    ]
    format_counts = ", ".join(
        f"{format_name}: {count}"
        for format_name, count in match_sample["format"].value_counts().items()
    )
    summary = (
        f"- Retained regulation sample: **18 innings across 9 matches** "
        f"({format_counts}).\n"
        f"- Aggregate batter-run comparisons: **{len(exact_runs)}/18 EXACT MATCH**.\n"
        f"- Aggregate team-wicket comparisons: **{len(exact_wickets)}/18 EXACT MATCH**.\n"
        f"- Batter balls faced: **{len(unverifiable_balls)}/18 UNVERIFIABLE**.\n"
        f"- Bowler runs conceded: **{len(unverifiable_bowler_runs)}/18 UNVERIFIABLE**.\n"
        f"- Bowler-creditable wickets: **{len(unverifiable_bowler_wickets)}/18 UNVERIFIABLE**.\n"
        f"- A noncanonical candidate legal-ball count is only **PARTIAL MATCH** in "
        f"{len(partial_candidate_balls)}/18 innings; this does not validate the candidate rule.\n"
    )
    (OUTPUT_DIR / "metric_validation_report.md").write_text(
        "# M2.4 metric validation report\n\n"
        "## Scope and guardrails\n\n"
        "This is a feasibility investigation only. It does not calculate player performance "
        "values, rankings, pressure scores, models, or dashboards. Source records and prior "
        "milestone evidence are read-only. Aggregate scorecard comparisons are not treated as "
        "player-level validation.\n\n"
        "## Retained validation evidence\n\n"
        + summary
        + "\nThe prior M2.2E scorecard file contains 18 selected regulation innings across "
        "nine matches. Its broader table also includes special-innings scopes marked "
        "UNVERIFIABLE; these are not counted as regulation observations here. The exact "
        "provider/source row evidence remains in "
        "[the M2.2E scorecard validation](../rules_validation/provider_encoding_resolution/scorecard_validation.csv) "
        "and [the M2.2E report](../rules_validation/provider_encoding_resolution/provider_encoding_resolution_report.md).\n\n"
        "## Decision matrix\n\n"
        + markdown_table(
            matrix[
                [
                    "discipline",
                    "metric",
                    "exact_source_columns",
                    "cricket_rule_or_statistical_convention",
                    "unresolved_provider_encodings",
                    "validation_test_result",
                    "evidence_status",
                    "recommendation",
                    "sample_size_and_validation_coverage",
                    "edge_cases_and_failure_conditions",
                ]
            ]
        )
        + "\n\n"
        "## Metric-specific limits\n\n"
        "- `runs` is **PROBABLE** as an aggregate batter-run subtotal in the selected sample, "
        "not confirmed as a player-level or provider-wide contract.\n"
        "- `is_four`/`is_six` are **PROBABLE** event flags but incomplete: 20 rows with "
        "`runs=4` and 3 with `runs=6` have false flags. No player boundary reconciliation exists.\n"
        "- Team wickets are separate from bowler-creditable wickets. Prior team-wicket totals "
        "match the selected scorecards, but bowler-credit categories remain only probable and "
        "provider mapping is unresolved. Preserve the 12 false-flag dismissed IDs and the "
        "match 40709 `Retire Out` record at source CSV row 127901; see the retained "
        "[false-flag ID records](../rules_validation/wicket_dismissal/dismissed_player_without_wicket_flag.csv) "
        "and [missing dismissed-player record](../rules_validation/wicket_dismissal/missing_dismissed_player_records.csv).\n"
        "- MCC Laws are rule context, not proof of provider event encoding. See "
        "[the existing cricket rules validation](../../docs/CRICKET_RULES_VALIDATION.md). "
        "`Overstep` is not "
        "assumed to mean No ball; `extras1_runs` and `extras_2_runs` are not added as runs.\n"
        "- `playing_eleven.is_played` does not prove a player's actual participation.\n\n"
        "## Status\n\n"
        "**M2.4 remains IN PROGRESS.** Existing data supports descriptive source inspection "
        "and provisional aggregate batter-run interpretation only. No listed player performance "
        "metric is approved for selection or ranking calculations.\n",
        encoding="utf-8",
    )

    (OUTPUT_DIR / "external_source_investigation.md").write_text(
        "# External source investigation\n\n"
        "## Evidence boundary\n\n"
        "This M2.4 run could not use the requested BrowserOS neo website session: its "
        "session/tab research actions were not available in the active tool set. No source "
        "website, API, downloadable archive, terms page, or coverage endpoint was independently "
        "opened during this milestone. Accordingly, the table below records retained local "
        "evidence and research leads, not verified present-day source capability or legal access.\n\n"
        "## Candidate assessment\n\n"
        "| Candidate | Historical coverage evidence | Batter/bowler statistics | Ball-by-ball | IDs / matching | Access, reproducibility, and legal status |\n"
        "|---|---|---|---|---|---|\n"
        "| Cricbuzz scorecards | Prior retained M2.2 evidence references 9 matches and 18 regulation innings spanning IPL 2022-2025 and T20I 2022-2025. This is bounded prior evidence, not a current coverage audit. | Aggregate batter-run subtotals and team wickets were transcribed for the selected innings. Per-batter balls faced, per-bowler figures, and bowler-creditable wickets are not retained as verified comparisons. | Not tested or retained in this milestone. | Provider URL identifiers are retained; local match IDs were associated in prior investigations. No reusable provider-to-local ID API or player crosswalk is established. | Historical pages are linked in the retained CSV; current access, extraction reproducibility, API terms, and permitted reuse were not verified. |\n"
        "| Official IPL/BCCI scorecards | Not independently inspected for this milestone. | Unknown. | Unknown. | No crosswalk tested. | Availability, access method, terms, and 2022-2026 coverage are unverified. |\n"
        "| ICC / official tournament scorecards | Not independently inspected for this milestone. | Unknown. | Unknown. | No crosswalk tested. | Availability, access method, terms, and relevant competition coverage are unverified. |\n"
        "| ESPNcricinfo or other reputable scorecards | No evidence retained in this workspace for a tested sample. | Unknown. | Unknown. | No crosswalk tested. | Access, reproducibility, terms, and relevant historical coverage are unverified. |\n"
        "| Cricsheet or another public ball-by-ball archive | Candidate lead only; no dataset, schema, license, or match sample was inspected. | Unknown. | Unknown until a specific archive and coverage manifest are tested. | No local match/player crosswalk tested. | Dataset-specific license, conditions, and 2022-2026 coverage are unverified. |\n\n"
        "## Conclusion\n\n"
        "The original provider remains unidentified. The retained Cricbuzz scorecard sample "
        "demonstrates bounded historical comparison evidence, not a usable enrichment pipeline. "
        "No candidate source is confirmed as legally and reproducibly usable for the required "
        "2022-2026 match scope. External enrichment feasibility therefore remains **UNRESOLVED**; "
        "re-open this section only after website access and source terms/coverage can be verified.\n",
        encoding="utf-8",
    )

    match_join_summary = (
        f"- The 9 match IDs represented in the retained scorecard sample join to exactly one "
        f"`matches.csv` row each: **{len(match_sample)}/9**.\n"
        f"- Their retained dates, competition names, and formats agree with local "
        f"`matches.csv`/`competitions.csv`: **{len(match_sample)}/9** for each field.\n"
        f"- The 18 numeric regulation innings have local delivery rows and their batting-team "
        f"IDs map in competition context: **{len(innings_sample)}/18**.\n"
    )
    (OUTPUT_DIR / "join_feasibility_report.md").write_text(
        "# Join and reconciliation feasibility\n\n"
        "## Candidate strategy\n\n"
        "1. Match the external scorecard to a local fixture using competition/format, date, "
        "the two opposing teams, and (where available) stage/match number/venue. Treat local "
        "`match_id` and the external provider ID as distinct source keys; record the explicit "
        "crosswalk rather than replacing either ID.\n"
        "2. Match innings using batting team plus innings order, then reconcile totals and "
        "innings status. Keep Super Overs, abandoned/incomplete innings, and revised targets "
        "as separate cases rather than forcing a regulation-innings match.\n"
        "3. Match players within the fixture using team and stable source ID when shared; "
        "otherwise use reviewed name/alias plus team and role/innings evidence. Names alone "
        "are not unique. Require manual review for ambiguous aliases, transfers, or duplicate "
        "candidate matches.\n"
        "4. Preserve source values, URLs, retrieval date, license/access notes, raw scorecard "
        "records, and comparison outcomes in separate enrichment tables. Never overwrite the "
        "supplied CSVs or silently resolve a conflict.\n\n"
        "## Local join test\n\n"
        + match_join_summary
        + "\nThe generated [`join_sample.csv`](join_sample.csv) lists every retained match/innings "
        "reference. This is a replay of local key/metadata joins against prior manual scorecard "
        "references, not an independent scrape or verification of each external page's teams. "
        "External team and player rows were not preserved in the scorecard evidence, so it is "
        "not possible to claim an external player-level join test.\n\n"
        "## Reconciliation classifications\n\n"
        "| Case | Result from retained evidence |\n"
        "|---|---|\n"
        "| Exact local metadata joins | 9/9 retained match IDs, dates, competitions, and formats join to the local match/competition tables. This is an internal join check, not an exact external identity confirmation. |\n"
        "| External match identity | 9 prior URL-to-local-ID cross-references are retained; they were not independently re-tested in M2.4. No new exact external identity match is claimed. |\n"
        "| Ambiguous external match candidates | Not assessable; no candidate-result sets or external team/date metadata were archived for this test. |\n"
        "| Unmatched external/local matches | Not assessable beyond the nine retained links; no systematic source inventory was available. |\n"
        "| Duplicate match candidates | Not assessable; no provider-wide match list was downloaded. |\n"
        "| Player identity matches/mismatches | Not assessable; player-level external scorecard rows and an external player-ID map were not retained. |\n"
        "| Innings identity | 18 numeric regulation innings join to local delivery groups and competition-scoped batting-team IDs. Five additional special-innings scopes in the old evidence remain UNVERIFIABLE. |\n\n"
        "The current sample has no demonstrated unmatched or mismatched player records; that "
        "absence is not evidence that such cases do not exist. Cross-source matching requires "
        "a documented external identity sample before it can be called operationally feasible.\n",
        encoding="utf-8",
    )

    (OUTPUT_DIR / "final_methodology_recommendation.md").write_text(
        "# M2.4 final methodology recommendation\n\n"
        "## Decision matrix\n\n"
        "| Approach | Assessment |\n"
        "|---|---|\n"
        "| A. Existing dataset only | Not defensible for standard batting/bowling rates or pressure comparisons yet. It preserves useful event and identity context, but balls faced, legal balls, bowler runs conceded, bowler-credit wickets, and match state are unresolved. |\n"
        "| B. External enrichment only | Not defensible at present. No external provider has been shown to cover the required population with verified access, terms, stable IDs, and reproducible delivery-level data. It would also discard the original feed's contextual source records. |\n"
        "| C. Hybrid | **Recommended, conditional.** Preserve original records unchanged, then add separately versioned and licensed scorecard/ball-by-ball evidence with explicit match/player crosswalks, field-level provenance, reconciliation status, and human-reviewed conflicts. Do not compute metrics until required fields reconcile. |\n\n"
        "## Metric decisions\n\n"
        "- **Provisional evidence only:** aggregate `runs` as batter-run subtotal in the 18 selected regulation innings; raw boundary flags; raw team-wicket and dismissal fields for audit. These are not approved player metrics.\n"
        "- **Exclude pending evidence:** balls faced, strike rate, batting average, bowler-creditable wickets, bowler runs conceded, balls/overs bowled, economy, bowling average, and bowling strike rate.\n"
        "- **Not approved:** all pressure features, final player performance formulas, eligibility thresholds, rankings, machine learning, and dashboards.\n\n"
        "## Readiness and next steps\n\n"
        "M2.2 and M2.3 remain **IN PROGRESS**. M2.4 is **IN PROGRESS**, not complete: no external source is currently established as legally/reproducibly usable, and external match/player reconciliation could not be independently replayed. Before M2.4 closure, inspect candidate source terms and coverage; archive a diverse match/player scorecard sample; test exact/ambiguous/unmatched/duplicate identities; validate per-batter and per-bowler figures plus legal-ball rules; and obtain cricket-domain review. Then preserve the approved findings for M2.5 human review. Do not begin ranking or pressure implementation before those gates and separate methodology approval.\n",
        encoding="utf-8",
    )


def main() -> None:
    initial_rule_hashes = {
        path.relative_to(RULES_EVIDENCE_DIR).as_posix(): sha256(path)
        for path in RULES_EVIDENCE_DIR.rglob("*")
        if path.is_file()
    }
    hashes = verify_source_hashes()
    scorecard, match_sample, innings_sample = source_evidence()
    matrix = metric_matrix(scorecard)
    write_reports(matrix, scorecard, match_sample, innings_sample, hashes)

    final_rule_hashes = {
        path.relative_to(RULES_EVIDENCE_DIR).as_posix(): sha256(path)
        for path in RULES_EVIDENCE_DIR.rglob("*")
        if path.is_file()
    }
    if initial_rule_hashes != final_rule_hashes:
        raise AssertionError("A prior rules-validation artifact changed during M2.4 generation.")
    for path in REQUIRED_OUTPUTS:
        if not path.is_file() or path.stat().st_size == 0:
            raise AssertionError(f"Required M2.4 output is missing or empty: {path}")
    print(f"Generated {len(REQUIRED_OUTPUTS)} non-empty M2.4 evidence files in {OUTPUT_DIR}")
    print("Protected source hashes match the retained M2.2E baseline.")
    print("Prior audit_reports/rules_validation files are unchanged.")
    print(f"Metric matrix rows: {len(matrix)}; regulation innings: {len(innings_sample)}; matches: {len(match_sample)}")
    print("M2.4 remains IN PROGRESS; no player metrics or rankings were calculated.")


if __name__ == "__main__":
    main()
