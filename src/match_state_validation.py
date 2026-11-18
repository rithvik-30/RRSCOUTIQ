"""Read-only validation of innings structure and reconstructable match state."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "extracted"
OUTPUT_DIR = ROOT / "audit_reports" / "rules_validation" / "match_state"
BALL_PATH = DATA_DIR / "ball_by_ball.csv"
MATCH_PATH = DATA_DIR / "matches.csv"
COMPETITION_PATH = DATA_DIR / "competitions.csv"
BASELINE_HASH_PATH = (
    ROOT
    / "audit_reports"
    / "rules_validation"
    / "extras_legal_delivery"
    / "source_hash_verification.csv"
)
PROVIDER_SCORECARD_PATH = (
    ROOT
    / "audit_reports"
    / "rules_validation"
    / "provider_investigation"
    / "scorecard_reconciliation.csv"
)
MULTI_SCORECARD_PATH = (
    ROOT
    / "audit_reports"
    / "rules_validation"
    / "multi_match_reconciliation"
    / "scorecard_reconciliation.csv"
)
LEGAL_BALL_PATH = (
    ROOT
    / "audit_reports"
    / "rules_validation"
    / "extras_legal_delivery"
    / "legal_delivery_validation.csv"
)
WICKET_REPORT_PATH = (
    ROOT
    / "audit_reports"
    / "rules_validation"
    / "wicket_dismissal"
    / "wicket_dismissal_report.md"
)
SOURCE_CSVS = [
    BALL_PATH,
    MATCH_PATH,
    DATA_DIR / "playing_eleven.csv",
    DATA_DIR / "competition_team_player_mapping.csv",
    DATA_DIR / "teams.csv",
    COMPETITION_PATH,
]
SOURCE_ARCHIVE = ROOT / "data" / "data_pack.zip.zip"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_row(index: int) -> int:
    return index + 2


def parse_scorecard_total(value: str) -> int:
    match = re.search(r"(\d+)-\d+", value)
    if not match:
        raise ValueError(f"Could not parse scorecard innings total: {value!r}")
    return int(match.group(1))


def parse_scorecard_wickets(value: str) -> int:
    match = re.search(r"-(\d+)", value)
    if not match:
        raise ValueError(f"Could not parse scorecard wicket total: {value!r}")
    return int(match.group(1))


def parse_scorecard_balls(value: str) -> int:
    text = value.strip()
    if not re.fullmatch(r"\d+(?:\.\d+)?", text):
        raise ValueError(f"Could not parse scorecard over notation: {value!r}")
    whole, _, partial = text.partition(".")
    extra_balls = int(partial) if partial else 0
    if extra_balls > 5:
        raise ValueError(f"Invalid partial-over notation: {value!r}")
    return int(whole) * 6 + extra_balls


def load_scorecard_evidence() -> pd.DataFrame:
    provider = pd.read_csv(
        PROVIDER_SCORECARD_PATH, dtype=str, keep_default_na=False
    )
    multi = pd.read_csv(
        MULTI_SCORECARD_PATH, dtype=str, keep_default_na=False
    )
    rows: list[dict[str, str | int]] = []
    for row in provider.to_dict("records"):
        score = f"{row['scorecard_total_runs']}-{row['scorecard_wickets']}"
        rows.append(
            {
                "match_id": row["match_id"],
                "innings": row["innings"],
                "scorecard_source": "Cricbuzz",
                "scorecard_url": row["scorecard_source_url"],
                "scorecard_team": (
                    row["home_team"]
                    if row["innings"] == "1"
                    else row["away_team"]
                ),
                "scorecard_score": score,
                "scorecard_total_runs": int(row["scorecard_total_runs"]),
                "scorecard_wickets": int(row["scorecard_wickets"]),
                "scorecard_batter_runs": int(row["scorecard_batter_runs"]),
                "scorecard_extras": int(row["scorecard_extras"]),
                "scorecard_overs": row["scorecard_overs"],
                "scorecard_expected_balls": parse_scorecard_balls(
                    row["scorecard_overs"]
                ),
                "scorecard_source_rows": (
                    f"{row['source_first_csv_row']}-{row['source_last_csv_row']}"
                ),
            }
        )
    for row in multi.to_dict("records"):
        if row["innings"] not in {"1", "2"}:
            continue
        score_text = row["scorecard_total_wickets_overs"]
        rows.append(
            {
                "match_id": row["match_id"],
                "innings": row["innings"],
                "scorecard_source": row["scorecard_source"],
                "scorecard_url": row["scorecard_url"],
                "scorecard_team": row["scorecard_batting_team"],
                "scorecard_score": score_text,
                "scorecard_total_runs": parse_scorecard_total(score_text),
                "scorecard_wickets": parse_scorecard_wickets(score_text),
                "scorecard_batter_runs": int(
                    row["scorecard_batter_run_subtotal"]
                ),
                "scorecard_extras": parse_extras_total(
                    row["scorecard_extras"]
                ),
                "scorecard_overs": parse_over_notation(score_text),
                "scorecard_expected_balls": parse_scorecard_balls(
                    parse_over_notation(score_text)
                ),
                "scorecard_source_rows": row["source_excel_row_range"],
            }
        )
    scorecards = pd.DataFrame(rows)
    if scorecards.duplicated(["match_id", "innings"]).any():
        duplicates = scorecards.loc[
            scorecards.duplicated(["match_id", "innings"], keep=False),
            ["match_id", "innings"],
        ]
        raise ValueError(
            "Duplicate M2.2A/B scorecard evidence: "
            + duplicates.to_dict("records").__repr__()
        )
    if scorecards["scorecard_url"].eq("").any():
        raise ValueError("A scorecard evidence row has no source URL.")
    if not (
        scorecards["scorecard_total_runs"]
        == scorecards["scorecard_batter_runs"] + scorecards["scorecard_extras"]
    ).all():
        raise ValueError("Scorecard total does not equal batter subtotal plus extras.")
    return scorecards


def parse_over_notation(score: str) -> str:
    match = re.search(r"\((\d+(?:\.\d+)?)\s+overs?\)", score)
    if not match:
        raise ValueError(f"Could not parse scorecard overs from {score!r}")
    return match.group(1)


def parse_extras_total(value: str) -> int:
    match = re.match(r"\s*(\d+)", value)
    if not match:
        raise ValueError(f"Could not parse scorecard extras: {value!r}")
    return int(match.group(1))


def check_source_hashes() -> tuple[pd.DataFrame, dict[Path, str]]:
    protected = [*SOURCE_CSVS, SOURCE_ARCHIVE]
    missing = [str(path) for path in [*protected, BASELINE_HASH_PATH] if not path.is_file()]
    if missing:
        raise FileNotFoundError("Required sources are missing: " + ", ".join(missing))

    before = {path: sha256(path) for path in protected}
    baseline = pd.read_csv(
        BASELINE_HASH_PATH, dtype=str, keep_default_na=False
    )
    expected = dict(zip(baseline["source_file"], baseline["sha256"]))
    mismatches = []
    rows = []
    for path in protected:
        relative = path.relative_to(ROOT).as_posix()
        baseline_hash = expected.get(relative, "")
        status = "MATCH" if baseline_hash == before[path] else "MISMATCH"
        if status != "MATCH":
            mismatches.append(relative)
        rows.append(
            {
                "source_file": relative,
                "sha256": before[path],
                "baseline_sha256": baseline_hash,
                "baseline_result": status,
            }
        )
    if mismatches:
        raise RuntimeError(
            "Protected source hash mismatch against M2.2C baseline: "
            + ", ".join(mismatches)
        )
    return pd.DataFrame(rows), before


def metadata_frames(
    balls: pd.DataFrame,
    matches: pd.DataFrame,
    competitions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    matches = matches.copy()
    matches["matches_source_csv_row"] = matches.index + 2
    meta = matches.merge(
        competitions[["comp_id", "comp_name", "match_format", "season"]],
        on="comp_id",
        how="left",
        validate="many_to_one",
    )
    if meta["comp_name"].eq("").any() or meta["comp_name"].isna().any():
        raise ValueError("A match does not map to competition metadata.")
    ball_meta = balls[["match_id"]].merge(
        meta[
            [
                "match_id",
                "comp_id",
                "comp_name",
                "match_format",
                "season",
                "match_date",
                "home_team",
                "away_team",
                "home_team_id",
                "away_team_id",
                "result",
                "revised_target",
                "first_inn_revised_overs",
                "second_inn_revised_overs",
            ]
        ],
        on="match_id",
        how="left",
        validate="many_to_one",
    )
    if ball_meta["comp_id"].isna().any():
        raise ValueError("A delivery match does not map to match metadata.")
    return meta, ball_meta


def grouped_balls(balls: pd.DataFrame) -> list[tuple[tuple[str, str], pd.DataFrame]]:
    ordered = balls.copy()
    ordered["_source_index"] = ordered.index
    ordered["_sequence"] = pd.to_numeric(ordered["innings_ball_num"], errors="raise")
    return list(
        ordered.groupby(["match_id", "innings"], sort=False, dropna=False)
    )


def build_innings_structure(
    balls: pd.DataFrame,
    metadata: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    group_rows: list[dict[str, object]] = []
    anomaly_rows: list[dict[str, object]] = []
    innings_match_counts = balls.groupby("innings")["match_id"].nunique().to_dict()
    groups = grouped_balls(balls)
    group_presence: dict[str, set[str]] = {}
    for (match_id, innings), group in groups:
        group_presence.setdefault(match_id, set()).add(innings)
        meta = metadata.loc[metadata["match_id"].eq(match_id)].iloc[0]
        batting_teams = sorted(group["batting_team_id"].unique())
        bowling_teams = sorted(group["bowling_team_id"].unique())
        first_index = int(group["_source_index"].min())
        last_index = int(group["_source_index"].max())
        participant_ids = {
            meta["home_team_id"],
            meta["away_team_id"],
        }
        team_ids_valid = set(batting_teams + bowling_teams).issubset(
            participant_ids
        )
        teams_are_opponents = (
            len(batting_teams) == 1
            and len(bowling_teams) == 1
            and batting_teams[0] != bowling_teams[0]
        )
        seq = group["_sequence"]
        row = {
            "match_id": match_id,
            "match_date": meta["match_date"],
            "competition": meta["comp_name"],
            "format": meta["match_format"],
            "season": meta["season"],
            "result": meta["result"],
            "innings": innings,
            "source_csv": "ball_by_ball.csv",
            "source_excel_row_range": f"{source_row(first_index)}-{source_row(last_index)}",
            "delivery_rows": len(group),
            "distinct_batting_teams": len(batting_teams),
            "batting_team_ids": ";".join(batting_teams),
            "distinct_bowling_teams": len(bowling_teams),
            "bowling_team_ids": ";".join(bowling_teams),
            "teams_belong_to_match_participants": team_ids_valid,
            "batting_and_bowling_teams_differ": teams_are_opponents,
            "innings_ball_num_first": int(seq.min()),
            "innings_ball_num_last": int(seq.max()),
            "max_overid": int(pd.to_numeric(group["overid"]).max()),
            "max_over_ball_num": int(pd.to_numeric(group["over_ball_num"]).max()),
            "source_runs_sum_not_team_total": int(
                pd.to_numeric(group["runs"], errors="raise").sum()
            ),
            "is_wicket_true_count": int(group["is_wicket"].eq("true").sum()),
            "matches_with_this_innings_label": int(innings_match_counts[innings]),
            "interpretation_status": (
                "PROBABLE" if innings in {"1", "2"} else "UNRESOLVED"
            ),
            "interpretation_note": (
                "Source label 1/2; regulation role is supported in selected "
                "scorecards, not independently established for every match."
                if innings in {"1", "2"}
                else "Additional innings label; do not assume Super Over or "
                "other event type without match-specific evidence."
            ),
        }
        group_rows.append(row)
        if len(batting_teams) != 1 or len(bowling_teams) != 1:
            anomaly_rows.append(
                anomaly(
                    "MULTIPLE_TEAMS_WITHIN_INNINGS",
                    match_id,
                    innings,
                    f"{source_row(first_index)}-{source_row(last_index)}",
                    f"batting_team_ids={batting_teams}; bowling_team_ids={bowling_teams}",
                    "UNRESOLVED",
                )
            )
        if not team_ids_valid or not teams_are_opponents:
            anomaly_rows.append(
                anomaly(
                    "TEAM_IDS_CONFLICT_WITH_MATCH_OR_OPPOSITION",
                    match_id,
                    innings,
                    f"{source_row(first_index)}-{source_row(last_index)}",
                    f"batting={batting_teams}; bowling={bowling_teams}; "
                    f"match participants={sorted(participant_ids)}",
                    "UNRESOLVED",
                )
            )
        if innings in {"3", "4"}:
            anomaly_rows.append(
                anomaly(
                    "ADDITIONAL_INNINGS_LABEL",
                    match_id,
                    innings,
                    f"{source_row(first_index)}-{source_row(last_index)}",
                    f"{len(group)} rows; batting team {batting_teams}; result={meta['result']}",
                    "UNRESOLVED",
                )
            )

    for match in metadata.to_dict("records"):
        match_id = match["match_id"]
        present = group_presence.get(match_id, set())
        regulation = present.intersection({"1", "2"})
        if not present:
            anomaly_rows.append(
                anomaly(
                    "NO_BALL_BY_BALL_ROWS",
                    match_id,
                    "",
                    str(match["matches_source_csv_row"]),
                    f"match result={match['result']}",
                    "UNRESOLVED",
                    source_csv="matches.csv",
                )
            )
        elif regulation != {"1", "2"}:
            anomaly_rows.append(
                anomaly(
                    "FEWER_THAN_TWO_REGULATION_LABELS",
                    match_id,
                    "",
                    match_row_range(balls, match_id),
                    f"observed innings labels={sorted(present)}; result={match['result']}",
                    "UNRESOLVED",
                )
            )
        if {"1", "2"}.issubset(present):
            innings_groups = {
                innings: balls.loc[
                    balls["match_id"].eq(match_id)
                    & balls["innings"].eq(innings)
                ]
                for innings in ("1", "2")
            }
            teams = [
                group["batting_team_id"].iloc[0]
                for group in innings_groups.values()
            ]
            if teams[0] == teams[1]:
                rows = ";".join(
                    match_row_range(balls, match_id, innings)
                    for innings in ("1", "2")
                )
                anomaly_rows.append(
                    anomaly(
                        "SAME_BATTING_TEAM_IN_INNINGS_1_AND_2",
                        match_id,
                        "1;2",
                        rows,
                        f"batting team IDs={teams}",
                        "UNRESOLVED",
                    )
                )
    return pd.DataFrame(group_rows), pd.DataFrame(anomaly_rows)


def match_row_range(
    balls: pd.DataFrame,
    match_id: str,
    innings: str | None = None,
) -> str:
    mask = balls["match_id"].eq(match_id)
    if innings is not None:
        mask &= balls["innings"].eq(innings)
    indices = balls.index[mask]
    if len(indices) == 0:
        return ""
    return f"{source_row(int(indices.min()))}-{source_row(int(indices.max()))}"


def anomaly(
    category: str,
    match_id: str,
    innings: str,
    row_range: str,
    detail: str,
    status: str,
    source_csv: str = "ball_by_ball.csv",
) -> dict[str, str]:
    return {
        "issue_category": category,
        "match_id": match_id,
        "innings": innings,
        "source_csv": source_csv if row_range else "",
        "source_excel_row_range": row_range,
        "observed_detail": detail,
        "status": status,
    }


def build_delivery_order(
    balls: pd.DataFrame,
    metadata: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, object]] = []
    anomaly_rows: list[dict[str, object]] = []
    meta_by_match = metadata.set_index("match_id").to_dict("index")
    for (match_id, innings), original in grouped_balls(balls):
        group = original.sort_values("_source_index")
        n = len(group)
        sequence = group["_sequence"].astype(int).tolist()
        expected = list(range(1, n + 1))
        over = pd.to_numeric(group["overid"], errors="raise")
        ball_in_over = pd.to_numeric(group["over_ball_num"], errors="raise")
        over_pairs = list(zip(over.astype(int), ball_in_over.astype(int)))
        times = pd.to_datetime(
            group["delivery_ist_time"], utc=True, errors="coerce"
        )
        time_missing = int(times.isna().sum())
        time_ties = int((times.diff() == pd.Timedelta(0)).sum())
        time_decreases = int((times.diff() < pd.Timedelta(0)).sum())
        gt_six = ball_in_over.gt(6)
        first_index = int(group["_source_index"].iloc[0])
        last_index = int(group["_source_index"].iloc[-1])
        meta = meta_by_match[match_id]
        summary_rows.append(
            {
                "match_id": match_id,
                "match_date": meta["match_date"],
                "competition": meta["comp_name"],
                "format": meta["match_format"],
                "innings": innings,
                "source_excel_row_range": f"{source_row(first_index)}-{source_row(last_index)}",
                "delivery_rows": n,
                "innings_ball_num_first": sequence[0],
                "innings_ball_num_last": sequence[-1],
                "sequence_unique": len(set(sequence)) == n,
                "sequence_starts_at_1_and_contiguous": sequence == expected,
                "source_order_matches_sequence": sequence == expected,
                "overid_non_decreasing": bool(over.is_monotonic_increasing),
                "over_ball_tuple_non_decreasing": over_pairs == sorted(over_pairs),
                "delivery_timestamp_parse_failures": time_missing,
                "adjacent_timestamp_ties": time_ties,
                "timestamp_decreases_in_sequence_order": time_decreases,
                "over_ball_num_gt_6_rows": int(gt_six.sum()),
                "over_ball_num_gt_6_row_examples": ";".join(
                    str(source_row(int(index)))
                    for index in group.index[gt_six][:10]
                ),
                "recommended_order": "match_id, innings, innings_ball_num; preserve source row as tie-breaker",
                "status": (
                    "CONFIRMED STORED SEQUENCE"
                    if sequence == expected
                    and over.is_monotonic_increasing
                    and over_pairs == sorted(over_pairs)
                    else "UNRESOLVED CONFLICT"
                ),
            }
        )
        if sequence != expected:
            anomaly_rows.append(
                anomaly(
                    "INNINGS_SEQUENCE_GAP_DUPLICATE_OR_REORDER",
                    match_id,
                    innings,
                    f"{source_row(first_index)}-{source_row(last_index)}",
                    f"sequence values begin/end {sequence[0]}/{sequence[-1]} for {n} rows",
                    "UNRESOLVED",
                )
            )
        if not over.is_monotonic_increasing or over_pairs != sorted(over_pairs):
            anomaly_rows.append(
                anomaly(
                    "OVER_FIELDS_CONFLICT_WITH_STORED_ORDER",
                    match_id,
                    innings,
                    f"{source_row(first_index)}-{source_row(last_index)}",
                    "overid/over_ball_num ordering differs from innings_ball_num source order",
                    "UNRESOLVED",
                )
            )
        if time_missing:
            for index in group.index[times.isna()]:
                anomaly_rows.append(
                    anomaly(
                        "MALFORMED_OR_EMPTY_DELIVERY_TIMESTAMP",
                        match_id,
                        innings,
                        str(source_row(int(index))),
                        f"raw timestamp={group.loc[index, 'delivery_ist_time']!r}",
                        "UNRESOLVED",
                    )
                )
        previous_time = times.shift(1)
        for position, (index, current_time, prior_time) in enumerate(
            zip(group.index, times, previous_time)
        ):
            if pd.isna(prior_time) or pd.isna(current_time):
                continue
            if current_time == prior_time:
                anomaly_rows.append(
                    anomaly(
                        "ADJACENT_TIMESTAMP_TIE",
                        match_id,
                        innings,
                        f"{source_row(int(group.index[position - 1]))};{source_row(int(index))}",
                        f"both source rows have timestamp {group.loc[index, 'delivery_ist_time']}",
                        "UNRESOLVED TIMESTAMP SEMANTICS",
                    )
                )
            elif current_time < prior_time:
                anomaly_rows.append(
                    anomaly(
                        "TIMESTAMP_DECREASES_IN_STORED_SEQUENCE",
                        match_id,
                        innings,
                        f"{source_row(int(group.index[position - 1]))};{source_row(int(index))}",
                        f"{group.loc[index, 'delivery_ist_time']} follows {group.loc[group.index[position - 1], 'delivery_ist_time']}",
                        "UNRESOLVED; USE STORED SEQUENCE",
                    )
                )
        for index in group.index[gt_six]:
            anomaly_rows.append(
                anomaly(
                    "OVER_BALL_NUM_EXCEEDS_SIX",
                    match_id,
                    innings,
                    str(source_row(int(index))),
                    f"overid={group.loc[index, 'overid']}; over_ball_num={group.loc[index, 'over_ball_num']}; not interpreted as legal-ball count",
                    "CONFIRMED STORED VALUE; MEANING UNRESOLVED",
                )
            )
    return pd.DataFrame(summary_rows), pd.DataFrame(anomaly_rows)


def build_innings_validations(
    balls: pd.DataFrame,
    metadata: pd.DataFrame,
    scorecards: pd.DataFrame,
    legal_evidence: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    meta_by_match = metadata.set_index("match_id").to_dict("index")
    score_by_key = {
        (row["match_id"], row["innings"]): row
        for row in scorecards.to_dict("records")
    }
    legal = legal_evidence.loc[
        legal_evidence["candidate_rule"].eq("all recorded rows")
    ].set_index(["match_id", "innings"])
    legal_excluding_wide = legal_evidence.loc[
        legal_evidence["candidate_rule"].eq("exclude extras_type=wide")
    ].set_index(["match_id", "innings"])
    legal_excluding_wide_overstep = legal_evidence.loc[
        legal_evidence["candidate_rule"].eq("exclude wide and Overstep labels")
    ].set_index(["match_id", "innings"])
    legal_excluding_other = legal_evidence.loc[
        legal_evidence["candidate_rule"].eq(
            "exclude wide, Overstep, and other labels"
        )
    ].set_index(["match_id", "innings"])

    cumulative_rows: list[dict[str, object]] = []
    wicket_rows: list[dict[str, object]] = []
    overs_rows: list[dict[str, object]] = []
    first_innings_rows: list[dict[str, object]] = []
    for (match_id, innings), original in grouped_balls(balls):
        group = original.sort_values("_sequence")
        meta = meta_by_match[match_id]
        scorecard = score_by_key.get((match_id, innings))
        indexes = group["_source_index"].astype(int)
        excel_first, excel_last = source_row(indexes.min()), source_row(indexes.max())
        run_values = pd.to_numeric(group["runs"], errors="raise")
        wicket_flags = group["is_wicket"].eq("true").astype(int)
        source_runs_sum = int(run_values.sum())
        wicket_count = int(wicket_flags.sum())
        row_range = f"{excel_first}-{excel_last}"
        if scorecard:
            if row_range != scorecard["scorecard_source_rows"]:
                raise ValueError(
                    f"Scorecard source row range differs for {match_id} "
                    f"innings {innings}: {row_range} != "
                    f"{scorecard['scorecard_source_rows']}."
                )
            if scorecard["scorecard_team"] == meta["home_team"]:
                expected_batting_team_id = meta["home_team_id"]
            elif scorecard["scorecard_team"] == meta["away_team"]:
                expected_batting_team_id = meta["away_team_id"]
            else:
                raise ValueError(
                    f"Scorecard team {scorecard['scorecard_team']!r} is not "
                    f"a participant in match {match_id}."
                )
            if set(group["batting_team_id"]) != {expected_batting_team_id}:
                raise ValueError(
                    f"Local batting team for {match_id} innings {innings} "
                    "does not match the retained scorecard."
                )
            batter_match = source_runs_sum == scorecard["scorecard_batter_runs"]
            wicket_match = wicket_count == scorecard["scorecard_wickets"]
            batter_status = "MATCH" if batter_match else "MISMATCH"
            wicket_status = "MATCH" if wicket_match else "MISMATCH"
            team_total_status = "UNVERIFIABLE - NO LOCAL TEAM-TOTAL FIELD"
            score_status = (
                "PARTIAL MATCH"
                if batter_match and wicket_match
                else "MISMATCH"
            )
            scorecard_source = scorecard["scorecard_source"]
            scorecard_url = scorecard["scorecard_url"]
            score_total = scorecard["scorecard_total_runs"]
            score_batter = scorecard["scorecard_batter_runs"]
            score_extras = scorecard["scorecard_extras"]
            score_wickets = scorecard["scorecard_wickets"]
            score_overs = scorecard["scorecard_overs"]
            expected_balls = scorecard["scorecard_expected_balls"]
        else:
            batter_match = ""
            wicket_match = ""
            batter_status = "UNVERIFIABLE"
            wicket_status = "UNVERIFIABLE"
            team_total_status = "UNVERIFIABLE"
            score_status = "UNVERIFIABLE"
            scorecard_source = ""
            scorecard_url = ""
            score_total = ""
            score_batter = ""
            score_extras = ""
            score_wickets = ""
            score_overs = ""
            expected_balls = ""
        source_runs_before = run_values.cumsum().shift(1, fill_value=0)
        source_runs_after = run_values.cumsum()
        for position, index in enumerate(group.index):
            cumulative_rows.append(
                {
                    "match_id": match_id,
                    "match_date": meta["match_date"],
                    "competition": meta["comp_name"],
                    "format": meta["match_format"],
                    "result": meta["result"],
                    "innings": innings,
                    "source_csv": "ball_by_ball.csv",
                    "dataframe_index": int(index),
                    "source_excel_row": source_row(int(index)),
                    "source_excel_row_range_for_innings": row_range,
                    "innings_ball_num": int(group.loc[index, "_sequence"]),
                    "overid": group.loc[index, "overid"],
                    "over_ball_num": group.loc[index, "over_ball_num"],
                    "batting_team_id": group.loc[index, "batting_team_id"],
                    "runs_raw": group.loc[index, "runs"],
                    "extras_type_raw": group.loc[index, "extras_type"],
                    "extras1_runs_raw": group.loc[index, "extras1_runs"],
                    "extras_2_runs_raw": group.loc[index, "extras_2_runs"],
                    "cumulative_runs_field_before_delivery": int(
                        source_runs_before.iloc[position]
                    ),
                    "cumulative_runs_field_after_delivery": int(
                        source_runs_after.iloc[position]
                    ),
                    "source_runs_field_innings_sum": source_runs_sum,
                    "source_runs_sum_equals_scorecard_batter_runs": batter_match,
                    "scorecard_batter_runs": score_batter,
                    "scorecard_total_runs": score_total,
                    "scorecard_extras_total": score_extras,
                    "scorecard_final_wickets": score_wickets,
                    "scorecard_overs": score_overs,
                    "scorecard_source": scorecard_source,
                    "scorecard_url": scorecard_url,
                    "local_team_total_runs_field_present": False,
                    "cumulative_team_score_before_delivery": "",
                    "cumulative_team_score_after_delivery": "",
                    "team_score_status": "UNRESOLVED",
                    "batter_run_subtotal_comparison_status": batter_status,
                    "wicket_count_comparison_status": wicket_status,
                    "team_total_comparison_status": team_total_status,
                    "comparison_status": score_status,
                    "innings_aggregate_comparison_status": score_status,
                    "interpretation_limit": (
                        "Cumulative values are the raw `runs` field only, not "
                        "team score. Extras and per-delivery total-run semantics "
                        "are unresolved."
                    ),
                }
            )
        wickets_before = wicket_flags.cumsum().shift(1, fill_value=0)
        wickets_after = wicket_flags.cumsum()
        for position, index in enumerate(group.index):
            wicket_rows.append(
                {
                    "match_id": match_id,
                    "match_date": meta["match_date"],
                    "competition": meta["comp_name"],
                    "format": meta["match_format"],
                    "innings": innings,
                    "source_csv": "ball_by_ball.csv",
                    "dataframe_index": int(index),
                    "source_excel_row": source_row(int(index)),
                    "innings_ball_num": int(group.loc[index, "_sequence"]),
                    "overid": group.loc[index, "overid"],
                    "over_ball_num": group.loc[index, "over_ball_num"],
                    "is_wicket": group.loc[index, "is_wicket"],
                    "dismissal_type": group.loc[index, "dismissal_type"],
                    "dismissed_player_id": group.loc[index, "dismissed_player_id"],
                    "team_wickets_before_delivery_from_flag": int(
                        wickets_before.iloc[position]
                    ),
                    "team_wickets_after_delivery_from_flag": int(
                        wickets_after.iloc[position]
                    ),
                    "innings_final_wicket_count_from_flag": wicket_count,
                    "scorecard_final_wickets": score_wickets,
                    "final_wicket_count_matches_scorecard": wicket_match,
                    "wicket_state_status": (
                        "PROBABLE TEAM-WICKET PROGRESSION; SELECTED SCORECARD CHECK"
                        if scorecard
                        else "SOURCE-FLAG CUMSUM CONFIRMED; TEAM-WICKET SEMANTICS UNRESOLVED"
                    ),
                    "interpretation_limit": (
                        "Cumulative count is derived from the source flag in stored "
                        "sequence; dismissal/player anomalies remain uncorrected. "
                        "Bowler credit is not inferred."
                    ),
                }
            )

        def candidate_count(frame: pd.DataFrame) -> str:
            key = (match_id, innings)
            if key not in frame.index:
                return ""
            return str(frame.loc[key, "candidate_legal_delivery_count"])

        candidate_all = candidate_count(legal)
        candidate_wide = candidate_count(legal_excluding_wide)
        candidate_wide_overstep = candidate_count(legal_excluding_wide_overstep)
        candidate_wide_overstep_other = candidate_count(legal_excluding_other)
        overs_rows.append(
            {
                "match_id": match_id,
                "match_date": meta["match_date"],
                "competition": meta["comp_name"],
                "format": meta["match_format"],
                "result": meta["result"],
                "innings": innings,
                "source_csv": "ball_by_ball.csv",
                "source_excel_row_range": row_range,
                "delivery_row_count_not_legal_balls": len(group),
                "max_overid": int(pd.to_numeric(group["overid"]).max()),
                "max_over_ball_num": int(
                    pd.to_numeric(group["over_ball_num"]).max()
                ),
                "scorecard_overs": score_overs,
                "scorecard_expected_balls": expected_balls,
                "candidate_count_all_rows": candidate_all,
                "candidate_count_excluding_wide": candidate_wide,
                "candidate_count_excluding_wide_overstep": candidate_wide_overstep,
                "candidate_count_excluding_wide_overstep_other": candidate_wide_overstep_other,
                "scorecard_source": scorecard_source,
                "scorecard_url": scorecard_url,
                "legal_balls_status": "UNRESOLVED",
                "overs_completed_status": "UNRESOLVED",
                "balls_remaining_status": "UNRESOLVED",
                "interpretation_limit": (
                    "Candidate row exclusions are descriptive comparisons only; "
                    "they do not establish row-level legality. Do not treat "
                    "overid or over_ball_num as legal-ball counts."
                ),
            }
        )
        if innings == "1":
            first_innings_rows.append(
                {
                    "match_id": match_id,
                    "match_date": meta["match_date"],
                    "competition": meta["comp_name"],
                    "format": meta["match_format"],
                    "result": meta["result"],
                    "innings": innings,
                    "source_csv": "ball_by_ball.csv",
                    "source_excel_row_range": row_range,
                    "delivery_rows": len(group),
                    "innings_ball_num_first": int(group["_sequence"].min()),
                    "innings_ball_num_last": int(group["_sequence"].max()),
                    "source_runs_sum_field_only": source_runs_sum,
                    "scorecard_batter_runs": score_batter,
                    "scorecard_team_total": score_total,
                    "scorecard_wickets": score_wickets,
                    "scorecard_overs": score_overs,
                    "scorecard_url": scorecard_url,
                    "stored_delivery_order_status": "CONFIRMED STORED SEQUENCE",
                    "source_wicket_progression_status": (
                        "PROBABLE; FINAL COUNT SCORECARD-CHECKED"
                        if scorecard
                        else "SOURCE-FLAG CUMSUM CONFIRMED; TEAM-WICKET SEMANTICS UNRESOLVED"
                    ),
                    "team_score_progression_status": "UNRESOLVED",
                    "legal_ball_progress_status": "UNRESOLVED",
                    "par_or_scoring_trajectory_status": "NOT APPLICABLE IN M2.3",
                    "interpretation_limit": (
                        "No validated per-delivery team-run or legal-ball field; "
                        "do not call cumulative `runs` a team score or infer par."
                    ),
                }
            )
    return (
        pd.DataFrame(cumulative_rows),
        pd.DataFrame(wicket_rows),
        pd.DataFrame(overs_rows),
        pd.DataFrame(first_innings_rows),
    )


def build_target_validation(
    balls: pd.DataFrame,
    metadata: pd.DataFrame,
    scorecards: pd.DataFrame,
) -> pd.DataFrame:
    scorecard_first = scorecards.loc[scorecards["innings"].eq("1")].set_index(
        "match_id"
    )
    innings_by_match = {
        match_id: set(group["innings"].unique())
        for match_id, group in balls.groupby("match_id", sort=False)
    }
    row_ranges: dict[str, dict[str, str]] = {}
    for (match_id, innings), group in balls.groupby(
        ["match_id", "innings"], sort=False
    ):
        row_ranges.setdefault(match_id, {})[innings] = (
            f"{source_row(int(group.index.min()))}-"
            f"{source_row(int(group.index.max()))}"
        )
    innings_facts: dict[tuple[str, str], dict[str, object]] = {}
    for (match_id, innings), group in balls.groupby(
        ["match_id", "innings"], sort=False
    ):
        innings_facts[(match_id, innings)] = {
            "runs_sum": int(pd.to_numeric(group["runs"], errors="raise").sum()),
            "wickets": int(group["is_wicket"].eq("true").sum()),
            "batting_team_ids": set(group["batting_team_id"]),
        }
    rows = []
    for match in metadata.to_dict("records"):
        match_id = match["match_id"]
        innings = innings_by_match.get(match_id, set())
        ranges = row_ranges.get(match_id, {})
        first_range = ranges.get("1", "")
        second_range = ranges.get("2", "")
        has_scorecard = match_id in scorecard_first.index
        result_has_dls = bool(re.search(r"\bD/?L(?:S)?\b", match["result"], re.I))
        result_has_no_result_or_abandonment = bool(
            re.search(r"\bno\s+result\b|\babandon(?:ed|ment)?\b", match["result"], re.I)
        )
        revised_target_present = match["revised_target"].strip() != ""
        revised_overs_present = (
            match["first_inn_revised_overs"].strip() != ""
            or match["second_inn_revised_overs"].strip() != ""
        )
        interruption_reasons = []
        if result_has_dls:
            interruption_reasons.append("result mentions D/L or DLS")
        if result_has_no_result_or_abandonment:
            interruption_reasons.append("result is No Result or Abandoned")
        if revised_target_present:
            interruption_reasons.append("revised_target is populated")
        if revised_overs_present:
            interruption_reasons.append("revised-overs field is populated")
        interruption_or_revised_indicated = bool(interruption_reasons)
        if has_scorecard:
            first = scorecard_first.loc[match_id]
            scorecard_url = first["scorecard_url"]
            scorecard_total = int(first["scorecard_total_runs"])
            first_facts = innings_facts.get((match_id, "1"))
            if first_facts is None:
                first_innings_validation = "UNVERIFIABLE - LOCAL INNINGS 1 ABSENT"
            else:
                if first["scorecard_team"] == match["home_team"]:
                    expected_team_id = match["home_team_id"]
                elif first["scorecard_team"] == match["away_team"]:
                    expected_team_id = match["away_team_id"]
                else:
                    expected_team_id = ""
                first_checks_match = (
                    row_ranges.get(match_id, {}).get("1")
                    == first["scorecard_source_rows"]
                    and first_facts["runs_sum"] == first["scorecard_batter_runs"]
                    and first_facts["wickets"] == first["scorecard_wickets"]
                    and expected_team_id != ""
                    and first_facts["batting_team_ids"] == {expected_team_id}
                )
                first_innings_validation = (
                    "PARTIAL MATCH - ROW RANGE, BATTER-RUN SUBTOTAL, TEAM, AND WICKETS"
                    if first_checks_match
                    else "MISMATCH"
                )
            ordinary_scope = (
                "2" in innings
                and first_innings_validation.startswith("PARTIAL MATCH")
                and not interruption_or_revised_indicated
            )
            scorecard_target = (
                scorecard_total + 1 if ordinary_scope else ""
            )
            target_basis = (
                "Independent scorecard first-innings total + 1; sample only"
                if ordinary_scope
                else ""
            )
            target_status = (
                "PROBABLE INDEPENDENT SCORECARD REFERENCE; NOT LOCAL PRE-DELIVERY STATE"
                if ordinary_scope
                else "UNRESOLVED (REVISED/INTERRUPTED OR INSUFFICIENTLY VALIDATED)"
            )
        else:
            scorecard_target = ""
            scorecard_url = ""
            scorecard_total = ""
            target_basis = ""
            target_status = "UNRESOLVED"
            first_innings_validation = "UNVERIFIABLE - NO TRANSCRIBED SCORECARD"
        rows.append(
            {
                "match_id": match_id,
                "match_date": match["match_date"],
                "matches_source_csv_row": match["matches_source_csv_row"],
                "competition": match["comp_name"],
                "format": match["match_format"],
                "home_team": match["home_team"],
                "away_team": match["away_team"],
                "result": match["result"],
                "innings_labels_present": ";".join(sorted(innings)),
                "innings_1_source_excel_rows": first_range,
                "innings_2_source_excel_rows": second_range,
                "revised_target_raw": match["revised_target"],
                "revised_target_populated": revised_target_present,
                "revised_target_status": (
                    "PRESENT - RAW VALUE; SEMANTICS AND TIMING UNRESOLVED"
                    if revised_target_present
                    else "EMPTY - DOES NOT ESTABLISH ORDINARY TARGET"
                ),
                "first_inn_revised_overs_raw": match["first_inn_revised_overs"],
                "second_inn_revised_overs_raw": match["second_inn_revised_overs"],
                "revised_overs_populated": revised_overs_present,
                "revised_overs_status": (
                    "PRESENT - RAW VALUE; UNITS AND TIMING UNRESOLVED"
                    if revised_overs_present
                    else "EMPTY - DOES NOT ESTABLISH STANDARD OVERS"
                ),
                "result_text_mentions_dls_dl": result_has_dls,
                "result_text_mentions_no_result_or_abandonment": (
                    result_has_no_result_or_abandonment
                ),
                "interruption_or_revised_indicated": interruption_or_revised_indicated,
                "interruption_or_revised_indications": "; ".join(interruption_reasons),
                "first_innings_scorecard_validation_status": first_innings_validation,
                "scorecard_first_innings_total": scorecard_total,
                "sample_ordinary_target_from_scorecard": scorecard_target,
                "target_derivation_basis": target_basis,
                "scorecard_source_url": scorecard_url,
                "local_target_field_present": False,
                "target_status": target_status,
                "ordinary_target_local_field_status": (
                    "NOT PRESENT IN matches.csv" if scorecard_target != "" else "NOT ESTABLISHED"
                ),
                "runs_required_status": "UNRESOLVED",
                "balls_remaining_status": "UNRESOLVED",
                "required_run_rate_status": "UNRESOLVED",
                "current_run_rate_status": "UNRESOLVED",
                "chasing_or_defending_status": (
                    "PROBABLE FROM INNINGS LABELS IN THE SELECTED REGULATION SAMPLE"
                    if {"1", "2"}.issubset(innings)
                    else "UNRESOLVED"
                ),
                "interpretation_limit": (
                    "No ordinary target column exists. A scorecard-derived target "
                    "is included only where previous independent scorecard evidence "
                    "exists; no local target is derived from an unvalidated innings "
                    "total. Revised target/overs semantics and effective timing are "
                    "unresolved."
                ),
            }
        )
    return pd.DataFrame(rows)


def write_report(
    innings: pd.DataFrame,
    anomalies: pd.DataFrame,
    order: pd.DataFrame,
    order_anomalies: pd.DataFrame,
    scores: pd.DataFrame,
    wickets: pd.DataFrame,
    overs: pd.DataFrame,
    targets: pd.DataFrame,
    first_innings: pd.DataFrame,
    hashes: pd.DataFrame,
) -> None:
    scorecard_rows = scores.loc[
        scores["scorecard_url"].ne("")
    ].drop_duplicates(["match_id", "innings"])
    batter_match_count = int(
        scorecard_rows["source_runs_sum_equals_scorecard_batter_runs"]
        .astype(str)
        .eq("True")
        .sum()
    )
    wicket_groups = (
        wickets.loc[wickets["scorecard_final_wickets"].ne("")][
            [
                "match_id",
                "innings",
                "innings_final_wicket_count_from_flag",
                "scorecard_final_wickets",
            ]
        ]
        .drop_duplicates(["match_id", "innings"])
    )
    wicket_match_count = int(
        (
            pd.to_numeric(
                wicket_groups["innings_final_wicket_count_from_flag"],
                errors="coerce",
            )
            == pd.to_numeric(wicket_groups["scorecard_final_wickets"], errors="coerce")
        )
        .sum()
    )
    comparison_groups = scores.drop_duplicates(["match_id", "innings"])
    comparison_counts = comparison_groups["comparison_status"].value_counts().to_dict()
    groups = int(len(innings))
    timestamp_decreases = int(order["timestamp_decreases_in_sequence_order"].sum())
    timestamp_ties = int(order["adjacent_timestamp_ties"].sum())
    anomaly_categories = (
        anomalies["issue_category"].value_counts().to_dict()
        if not anomalies.empty
        else {}
    )
    one_innings = int(
        anomalies["issue_category"]
        .eq("FEWER_THAN_TWO_REGULATION_LABELS")
        .sum()
    )
    no_rows = int(anomalies["issue_category"].eq("NO_BALL_BY_BALL_ROWS").sum())
    missing_label_results = Counter(
        row.split("result=", 1)[-1]
        for row in anomalies.loc[
            anomalies["issue_category"].eq("FEWER_THAN_TWO_REGULATION_LABELS"),
            "observed_detail",
        ]
    )
    ordinary_target_count = int(
        targets["sample_ordinary_target_from_scorecard"].ne("").sum()
    )
    interrupted_or_revised_count = int(
        targets["interruption_or_revised_indicated"].astype(bool).sum()
    )
    innings_counts = (
        innings.groupby("innings")["match_id"].nunique().sort_index().to_dict()
    )
    output_descriptions = [
        ("innings_structure_summary.csv", "One row per match/innings with row range, team IDs, counts, and source-field totals."),
        ("innings_anomalies.csv", "Match-level coverage and unusual innings-label records; empty source ranges mean no ball rows exist."),
        ("delivery_order_validation.csv", "Per-innings ordering checks for sequence, over labels, timestamps, and source rows."),
        ("delivery_order_anomalies.csv", "Row-level timestamp ties/decreases, over-ball labels above six, and any ordering conflicts."),
        ("cumulative_score_validation.csv", "Per-innings source `runs` sum versus recorded scorecard subtotals; local team totals remain explicitly absent."),
        ("wicket_progression_validation.csv", "Per-delivery source wicket flag and cumulative team-wicket count before/after in stored sequence."),
        ("overs_and_balls_validation.csv", "Per-innings row counts, scorecard overs where available, and descriptive candidate counts; no legal balls are asserted."),
        ("target_and_chase_validation.csv", "Per-match target fields, source innings availability, and sample scorecard-derived ordinary targets."),
        ("first_innings_state_validation.csv", "Per-first-innings availability checks for score, wickets, ordering, balls, and par-trajectory inputs."),
        ("source_hash_verification.csv", "SHA-256 comparison of six original CSVs and archive against the M2.2C baseline."),
    ]
    lines = [
        "# M2.3 Innings and Match-State Reconstruction Validation",
        "",
        "## Scope and evidence boundaries",
        "",
        "This read-only investigation tests whether the supplied fields support "
        "a match state immediately before each delivery. It does not create "
        "pressure scores or player metrics. Source CSVs are read as strings "
        "with `keep_default_na=False`; original values are not normalized, "
        "imputed, removed, or written back.",
        "",
        "Prior evidence remains binding: `runs` is **PROBABLE** as batter runs "
        "at innings scope; extras and per-delivery team-run attribution are "
        "**UNRESOLVED**; `Overstep` is not established as a No ball; legal-ball "
        "identification is **UNRESOLVED**; and dismissal-player/bowler-credit "
        "semantics retain the M2.2D limitations. Those findings are not "
        "upgraded by this structural investigation.",
        "",
        "## Innings structure",
        "",
        f"The source contains {groups:,} match/innings groups. Match counts by "
        f"raw innings label are `{innings_counts}`. There are "
        f"{innings['match_id'].nunique():,} matches with delivery rows; "
        f"{no_rows} additional match records have no ball-by-ball rows. "
        f"{one_innings} matches with delivery rows have fewer than both "
        "innings labels 1 and 2 present. Those 22 records comprise "
        f"{missing_label_results.get('No Result', 0)} `No Result` and "
        f"{missing_label_results.get('Match Abandoned', 0)} `Match Abandoned` "
        "results; these are incomplete coverage scopes, not assumed complete "
        "one-innings matches.",
        "",
        "Every observed `(match_id, innings)` group has exactly one batting "
        "team ID and one bowling team ID. Labels 1 and 2 are the regulation "
        "innings labels in the selected scorecard sample and their roles are "
        "**PROBABLE** dataset-wide, not provider-confirmed for every record. "
        "Labels 3 and 4 occur in six matches (25 and 13 rows respectively); "
        "they appear in pairs in this file but are not automatically called "
        "Super Overs. Match-specific interpretation remains **UNRESOLVED** "
        "without scorecard evidence. See `innings_anomalies.csv` for each "
        "short/absent scope and source row locator.",
        "",
        "The 16 match records with no delivery rows are marked abandoned in "
        "`matches.csv`; this observed association does not establish a "
        "provider completeness rule. Source has 22 delivered matches lacking "
        "one of innings labels 1 or 2. Nineteen have `No Result` and three "
        "have `Match Abandoned`; their innings coverage is not treated as a "
        "complete match-state record.",
        "",
        "## Delivery ordering",
        "",
        f"All {groups:,} innings groups have `innings_ball_num` starting at 1 "
        "and contiguous in source row order, with no duplicate sequence values. "
        "In all groups, `overid` is non-decreasing and the pair "
        "`(overid, over_ball_num)` is non-decreasing in the same stored order. "
        f"All delivery timestamps parse as UTC strings; {timestamp_ties} "
        f"adjacent ties and {timestamp_decreases} within-innings decreases "
        "prevent timestamps from serving as a dependable event-order key. "
        "There are stored `over_ball_num` values greater than six; that field "
        "is not a legal-ball count.",
        "",
        "**Ordering recommendation:** order by `(match_id, innings, "
        "innings_ball_num)` and preserve the original source row as an "
        "audit/tie-break reference. This is **CONFIRMED** as reproduction of "
        "the stored sequence. It is not independent proof of event chronology, "
        "legal-ball numbering, or over completion. Timestamp semantics remain "
        "**UNRESOLVED**.",
        "",
        "## Cumulative score reconstruction",
        "",
        f"Previously transcribed independent scorecards cover "
        f"{len(scorecard_rows)} regulation innings. Local `runs` sums equal "
        f"the recorded batter-run subtotal in {batter_match_count}/"
        f"{len(scorecard_rows)}; final local wicket flags equal scorecard "
        f"wickets in {wicket_match_count}/{len(scorecard_rows)}. Row-range "
        "and batting-team IDs are also checked against the retained evidence. "
        "These are aggregate reconciliations, not per-delivery total-score "
        "validations.",
        "",
        "Scorecard comparison status is explicit: "
        f"{comparison_counts.get('EXACT MATCH', 0)} exact, "
        f"{comparison_counts.get('PARTIAL MATCH', 0)} partial, "
        f"{comparison_counts.get('MISMATCH', 0)} mismatch, and "
        f"{comparison_counts.get('UNVERIFIABLE', 0)} unverifiable innings. "
        "A partial match means the batter-run subtotal and wicket count match, "
        "but local team total runs are unavailable; an exact team-score match "
        "cannot be asserted from this source.",
        "",
        "There is no validated team-runs/total-runs field. The `runs` value is "
        "only **PROBABLE** as batter runs and the extras fields are "
        "**UNRESOLVED**. Therefore local cumulative team score before/after "
        "each delivery is **UNRESOLVED** and no team-score trajectory is "
        "constructed. Scorecard totals/extras are independent innings "
        "references, not a way to allocate per-delivery runs.",
        "",
        "## Wickets lost",
        "",
        "Cumulative `is_wicket` counts are emitted per delivery in stored "
        "sequence. Their interpretation as team-wicket progression is "
        "**PROBABLE**: the final local count matches the independent scorecard "
        f"count in {wicket_match_count}/{len(scorecard_rows)} sampled "
        "regulation innings, and the M2.2D investigation found one detailed "
        "innings whose dismissal rows matched. This is not dataset-wide "
        "validation of every wicket event or timing.",
        "",
        "The 12 rows with a dismissed-player ID but a false wicket flag and "
        "the one `Retire Out` with a missing dismissed-player ID remain "
        "unchanged. A missing dismissed-player ID does not prevent counting "
        "the source `is_wicket=true` flag, but may affect batter dismissal "
        "identity. Team wickets and bowler-creditable wickets remain distinct; "
        "the latter are **UNRESOLVED**.",
        "",
        "## Overs and balls remaining",
        "",
        "Delivery-row count and `overid`/`over_ball_num` are reported as stored "
        "observations only. Prior M2.2C comparisons of four candidate row "
        "exclusion rules against 18 scorecard over totals are descriptive; no "
        "candidate identifies row-level legality or generalizes. Legal balls, "
        "overs completed on a legal-ball basis, balls remaining, and "
        "over-based calculations are **UNRESOLVED**.",
        "",
        "## Targets and chase state",
        "",
        "`matches.csv` has no ordinary target field. `revised_target` is "
        "populated on 23 of 883 matches and revised-overs fields on 25 each; "
        "their scale, effective timing, and DLS relationship are unresolved. "
        f"Result text or revised fields indicate an interrupted/revised scope "
        f"for {interrupted_or_revised_count} matches. The output separates "
        "these from ordinary target references and preserves the raw revised "
        "values without interpreting units or timing. An ordinary "
        "scorecard-derived target (first-innings total + 1) is included for "
        f"{ordinary_target_count} sample matches only, after validating the "
        "first-innings row range, batting team, batter-run subtotal, and "
        "wickets against retained independent evidence. These are external "
        "references, not locally reconstructed pre-delivery targets.",
        "",
        "A general local target, runs required, balls remaining, required run "
        "rate, and current run rate cannot be reconstructed reliably. "
        "Chasing/defending may be described as **PROBABLE** from labels 1/2 "
        "in the selected regulation sample only; interrupted/revised-target "
        "cases and broader classification remain **UNRESOLVED**.",
        "",
        "## First-innings state",
        "",
        "Stored delivery order and source wicket-flag progression are available "
        "for inspection. Local current team score, scoring progression, balls "
        "remaining, and over progress are **UNRESOLVED** because total runs "
        "and delivery legality are not established. A par score or expected "
        "trajectory is **NOT APPLICABLE** to this validation milestone and "
        "must not be invented.",
        "",
        "## Status summary",
        "",
        "| State component | Status | Evidence / limit |",
        "|---|---|---|",
        "| Stored delivery row order using `innings_ball_num` | CONFIRMED | Contiguous, unique, begins at 1 in every observed match/innings group and agrees with source row order. |",
        "| `delivery_ist_time` as event chronology | UNRESOLVED | Four within-innings decreases and 39 adjacent ties; UTC suffix does not resolve event semantics. |",
        "| Innings labels 1/2 as regulation innings | PROBABLE | Agreement with selected scorecard evidence; not independently established for every match. |",
        "| Innings labels 3/4 as Super Overs | UNRESOLVED | Six matches have labels 3/4; only some prior scorecards mention tie-break context and the exact innings mapping is not universally validated. |",
        "| Source innings labels 1-4 as literal values | CONFIRMED | All four labels and their row/match distributions are recorded without renumbering. |",
        "| Local cumulative team score | UNRESOLVED | No validated per-delivery total-run field or extras aggregation. |",
        "| Wickets lost from `is_wicket` | PROBABLE | Sample final counts agree with scorecards; source anomalies and wider event validation remain. |",
        "| Bowler-creditable wickets | UNRESOLVED | M2.2D classification remains probable for common labels and unresolved for provider semantics. |",
        "| Legal balls, overs completed, balls remaining | UNRESOLVED | Candidate exclusions do not validate row-level legality. |",
        "| Ordinary target from local first-innings data | UNRESOLVED | No ordinary target field; local team total is not reconstructable reliably. |",
        "| Revised target / interrupted chase state | UNRESOLVED | Sparse fields and unknown units/timing; no matched DLS reconstruction is established. |",
        "| First-innings par/trajectory | NOT APPLICABLE | No approved expected-score model or par definition is part of M2.3 validation. |",
        "",
        "## Generated outputs and columns",
        "",
        "| File | Contents |",
        "|---|---|",
    ]
    for filename, description in output_descriptions:
        lines.append(f"| `{filename}` | {description} |")
    lines.extend(
        [
            "",
            "`source_excel_row` is the original CSV row number including the "
            "header; `dataframe_index` is zero-based. Blank scorecard fields "
            "mean that no previous independent scorecard transcription exists, "
            "not that the value is zero. Scorecard URLs are preserved wherever "
            "a prior reconciliation exists.",
            "",
            "## Source preservation and milestone status",
            "",
            "The script compares the six source CSV hashes and original ZIP "
            "hash to the M2.2C manifest before writing and rechecks them after "
            "analysis. No previous M1/M2.2 report is overwritten. M2.3 remains "
            "**IN PROGRESS**: stored ordering and selected aggregate wicket/"
            "batter-run comparisons are validated, but core team-score, "
            "legal-ball, target, and revised-chase state is not reliable enough "
            "for a pre-delivery match state or pressure calculation.",
            "",
            "| Protected source | SHA-256 | Baseline result |",
            "|---|---|---|",
        ]
    )
    for row in hashes.to_dict("records"):
        lines.append(
            f"| `{row['source_file']}` | `{row['sha256']}` | "
            f"{row['baseline_result']} |"
        )
    (OUTPUT_DIR / "match_state_validation_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    required = [
        *SOURCE_CSVS,
        SOURCE_ARCHIVE,
        BASELINE_HASH_PATH,
        PROVIDER_SCORECARD_PATH,
        MULTI_SCORECARD_PATH,
        LEGAL_BALL_PATH,
        WICKET_REPORT_PATH,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Required files are missing: " + ", ".join(missing))

    hash_frame, hashes_before = check_source_hashes()
    balls = pd.read_csv(BALL_PATH, dtype=str, keep_default_na=False)
    matches = pd.read_csv(MATCH_PATH, dtype=str, keep_default_na=False)
    competitions = pd.read_csv(
        COMPETITION_PATH, dtype=str, keep_default_na=False
    )
    required_ball_columns = {
        "match_id",
        "innings",
        "overid",
        "over_ball_num",
        "innings_ball_num",
        "batting_team_id",
        "bowling_team_id",
        "runs",
        "is_wicket",
        "delivery_ist_time",
        "extras_type",
        "extras1_runs",
        "extras_2_runs",
    }
    absent = required_ball_columns.difference(balls.columns)
    if absent:
        raise ValueError("ball_by_ball.csv lacks columns: " + ", ".join(sorted(absent)))
    if not balls["is_wicket"].isin({"true", "false"}).all():
        raise ValueError("Unexpected raw is_wicket value.")

    metadata, _ = metadata_frames(balls, matches, competitions)
    scorecards = load_scorecard_evidence()
    legal_evidence = pd.read_csv(LEGAL_BALL_PATH, dtype=str, keep_default_na=False)
    innings, innings_anomalies = build_innings_structure(balls, metadata)
    order, order_anomalies = build_delivery_order(balls, metadata)
    scores, wickets, overs, first_innings = build_innings_validations(
        balls, metadata, scorecards, legal_evidence
    )
    targets = build_target_validation(balls, metadata, scorecards)

    if len(innings) != 1724:
        raise AssertionError(f"Expected 1,724 innings groups, found {len(innings)}.")
    if (
        len(
            scores.loc[scores["scorecard_url"].ne("")].drop_duplicates(
                ["match_id", "innings"]
            )
        )
        != 18
    ):
        raise AssertionError("Expected 18 selected scorecard innings.")
    if len(wickets) != len(balls):
        raise AssertionError("Wicket progression does not cover every delivery.")
    if innings["delivery_rows"].sum() != len(balls):
        raise AssertionError("Innings groups do not account for every delivery.")
    if int(innings_anomalies["issue_category"].eq("NO_BALL_BY_BALL_ROWS").sum()) != 16:
        raise AssertionError("Expected 16 matches without delivery rows.")
    if int(
        innings_anomalies["issue_category"]
        .eq("FEWER_THAN_TWO_REGULATION_LABELS")
        .sum()
    ) != 22:
        raise AssertionError("Expected 22 matches missing one regulation innings label.")
    if not order["sequence_starts_at_1_and_contiguous"].all():
        raise AssertionError("At least one innings delivery sequence is not contiguous.")
    if not order["over_ball_tuple_non_decreasing"].all():
        raise AssertionError("Over labels conflict with stored order.")
    if (
        scores["innings_aggregate_comparison_status"] == "MISMATCH"
    ).any():
        raise AssertionError("A selected scorecard aggregate comparison mismatched.")
    if hashes_before != {path: sha256(path) for path in hashes_before}:
        raise RuntimeError("Protected source files changed during analysis.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    reports = {
        "innings_structure_summary.csv": innings,
        "innings_anomalies.csv": innings_anomalies,
        "delivery_order_validation.csv": order,
        "delivery_order_anomalies.csv": order_anomalies,
        "cumulative_score_validation.csv": scores,
        "wicket_progression_validation.csv": wickets,
        "overs_and_balls_validation.csv": overs,
        "target_and_chase_validation.csv": targets,
        "first_innings_state_validation.csv": first_innings,
        "source_hash_verification.csv": hash_frame,
    }
    for filename, frame in reports.items():
        frame.to_csv(OUTPUT_DIR / filename, index=False, encoding="utf-8-sig")
    write_report(
        innings,
        innings_anomalies,
        order,
        order_anomalies,
        scores,
        wickets,
        overs,
        targets,
        first_innings,
        hash_frame,
    )
    print(
        f"Innings groups: {len(innings)}; delivery rows: {len(balls)}; "
        f"scorecard innings: "
        f"{scores.loc[scores.scorecard_url.ne('')][['match_id', 'innings']].drop_duplicates().shape[0]}; "
        f"order groups with sequential stored indexes: "
        f"{int(order.sequence_starts_at_1_and_contiguous.sum())}/{len(order)}; "
        f"timestamp decreases: "
        f"{int(order.timestamp_decreases_in_sequence_order.sum())}; "
        f"source hashes: {len(hash_frame)} matched."
    )
    print(f"Reports: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
