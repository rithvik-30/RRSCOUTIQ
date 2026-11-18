"""Reassess provider encoding and scoring conventions without changing source data."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "extracted"
BALL_PATH = DATA_DIR / "ball_by_ball.csv"
MATCHES_PATH = DATA_DIR / "matches.csv"
TEAMS_PATH = DATA_DIR / "teams.csv"
COMPETITIONS_PATH = DATA_DIR / "competitions.csv"
ARCHIVE_PATH = ROOT / "data" / "data_pack.zip.zip"
BASELINE_HASH_PATH = (
    ROOT
    / "audit_reports"
    / "rules_validation"
    / "match_state"
    / "source_hash_verification.csv"
)
M2A_SCORECARD_PATH = (
    ROOT
    / "audit_reports"
    / "rules_validation"
    / "provider_investigation"
    / "scorecard_reconciliation.csv"
)
M2B_SCORECARD_PATH = (
    ROOT
    / "audit_reports"
    / "rules_validation"
    / "multi_match_reconciliation"
    / "scorecard_reconciliation.csv"
)
OUTPUT_DIR = (
    ROOT
    / "audit_reports"
    / "rules_validation"
    / "provider_encoding_resolution"
)

SOURCE_FILES = [
    ARCHIVE_PATH,
    BALL_PATH,
    MATCHES_PATH,
    ROOT / "data" / "extracted" / "playing_eleven.csv",
    ROOT / "data" / "extracted" / "competition_team_player_mapping.csv",
    TEAMS_PATH,
    COMPETITIONS_PATH,
]

EXTRA_FIELDS = [
    "extras_type",
    "extras1_runs",
    "extras_2_runs",
    "runs",
    "is_four",
    "is_six",
]

SEARCH_RESULTS = ROOT / "audit_reports" / "rules_validation" / "provider_investigation" / "provider_search_results.md"
LAW_17_URL = "https://lawsofcricket.lords.org/laws-of-cricket/the-over"
LAW_18_URL = (
    "https://lawsofcricket.lords.org/laws-of-cricket/"
    "the-over-scoring-runs-dead-ball-and-extras/scoring-runs"
)
MCC_ABOUT_URL = "https://www.lords.org/mcc/about-the-laws-of-cricket"
ICC_PLAYING_CONDITIONS_URL = (
    "https://www.icc-cricket.com/about/cricket/rules-and-regulations/"
    "playing-conditions"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def json_counts(values: pd.Series) -> str:
    counts = values.value_counts(dropna=False).sort_index().to_dict()
    return json.dumps(counts, ensure_ascii=False, sort_keys=True)


def source_excel_row(index: int) -> int:
    return index + 2


def _as_int(value: Any) -> int | None:
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _as_bool(value: Any) -> bool:
    return str(value).strip().casefold() in {"true", "1", "yes", "y"}


def overs_to_balls(value: Any) -> int | None:
    text = str(value).strip()
    match = re.fullmatch(r"(\d+)(?:\.(\d+))?", text)
    if not match:
        return None
    completed_overs = int(match.group(1))
    partial = int(match.group(2) or "0")
    if partial > 5:
        return None
    return completed_overs * 6 + partial


def parse_m2b_innings_total(value: str) -> tuple[str, str, str]:
    match = re.fullmatch(
        r"\s*(\d+)\s*-\s*(\d+)\s*\(([\d.]+)\s+overs?\)\s*",
        value,
        flags=re.IGNORECASE,
    )
    if not match:
        return "", "", ""
    return match.group(1), match.group(2), match.group(3)


def parse_m2b_extras(value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for label, amount in re.findall(r"\b(b|lb|w|nb|p)\s+(\d+)\b", value):
        result[label] = amount
    return result


def normalize_scorecard_evidence() -> pd.DataFrame:
    m2a = read_csv(M2A_SCORECARD_PATH)
    m2b = read_csv(M2B_SCORECARD_PATH)
    rows: list[dict[str, str]] = []

    for row in m2a.to_dict("records"):
        rows.append(
            {
                "match_id": row["match_id"],
                "match_date": row["match_date"],
                "innings": row["innings"],
                "scorecard_batting_team": "",
                "scorecard_source": "Cricbuzz",
                "scorecard_url": row["scorecard_source_url"],
                "source_first_row": row["source_first_csv_row"],
                "source_last_row": row["source_last_csv_row"],
                "source_row_count": row["source_delivery_rows"],
                "scorecard_total_runs": row["scorecard_total_runs"],
                "scorecard_wickets": row["scorecard_wickets"],
                "scorecard_overs": row["scorecard_overs"],
                "scorecard_batter_runs": row["scorecard_batter_runs"],
                "scorecard_extras": row["scorecard_extras"],
                "scorecard_byes": row["scorecard_byes"],
                "scorecard_legbyes": row["scorecard_legbyes"],
                "scorecard_wides": row["scorecard_wides"],
                "scorecard_noballs": row["scorecard_noballs"],
                "scorecard_penalty": row["scorecard_penalty"],
            }
        )

    for row in m2b.to_dict("records"):
        if row["innings"] not in {"1", "2"}:
            continue
        total, wickets, overs = parse_m2b_innings_total(
            row["scorecard_total_wickets_overs"]
        )
        extras = parse_m2b_extras(row["scorecard_extras"])
        rows.append(
            {
                "match_id": row["match_id"],
                "match_date": row["match_date"],
                "innings": row["innings"],
                "scorecard_batting_team": row["scorecard_batting_team"],
                "scorecard_source": row["scorecard_source"],
                "scorecard_url": row["scorecard_url"],
                "source_first_row": row["source_excel_row_range"].split("-")[0],
                "source_last_row": row["source_excel_row_range"].split("-")[-1],
                "source_row_count": row["source_row_count"],
                "scorecard_total_runs": total,
                "scorecard_wickets": wickets,
                "scorecard_overs": overs,
                "scorecard_batter_runs": row["scorecard_batter_run_subtotal"],
                "scorecard_extras": re.match(
                    r"\s*(\d+)", row["scorecard_extras"]
                ).group(1)
                if re.match(r"\s*(\d+)", row["scorecard_extras"])
                else "",
                "scorecard_byes": extras.get("b", ""),
                "scorecard_legbyes": extras.get("lb", ""),
                "scorecard_wides": row["scorecard_wide_runs"],
                "scorecard_noballs": row["scorecard_no_ball_runs"],
                "scorecard_penalty": extras.get("p", ""),
            }
        )

    result = pd.DataFrame(rows)
    if result.duplicated(["match_id", "innings"]).any():
        raise ValueError("Duplicate prior scorecard evidence for a match/innings")
    return result


def validate_prior_locators(
    balls: pd.DataFrame, evidence: pd.DataFrame
) -> pd.DataFrame:
    checks: list[dict[str, Any]] = []
    for row in evidence.to_dict("records"):
        subset = balls.loc[
            (balls["match_id"] == row["match_id"])
            & (balls["innings"] == row["innings"])
        ]
        if subset.empty:
            raise ValueError(
                f"No source rows for retained scorecard {row['match_id']}/{row['innings']}"
            )
        actual_first = source_excel_row(int(subset.index.min()))
        actual_last = source_excel_row(int(subset.index.max()))
        actual_count = len(subset)
        expected_first = int(row["source_first_row"])
        expected_last = int(row["source_last_row"])
        expected_count = int(row["source_row_count"])
        matches = (
            actual_first == expected_first
            and actual_last == expected_last
            and actual_count == expected_count
        )
        if not matches:
            raise ValueError(
                "Prior scorecard source locator mismatch for "
                f"{row['match_id']}/{row['innings']}: "
                f"expected {expected_first}-{expected_last}/{expected_count}; "
                f"actual {actual_first}-{actual_last}/{actual_count}"
            )
        checks.append(
            {
                "match_id": row["match_id"],
                "innings": row["innings"],
                "recorded_source_first_row": expected_first,
                "actual_source_first_row": actual_first,
                "recorded_source_last_row": expected_last,
                "actual_source_last_row": actual_last,
                "recorded_source_row_count": expected_count,
                "actual_source_row_count": actual_count,
                "source_locator_status": "MATCH",
                "scorecard_url": row["scorecard_url"],
            }
        )
    return pd.DataFrame(checks)


def _local_group(balls: pd.DataFrame, match_id: str, innings: str) -> pd.DataFrame:
    return balls.loc[
        (balls["match_id"] == match_id) & (balls["innings"] == innings)
    ].copy()


def create_extras_analysis(balls: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped = balls.groupby(EXTRA_FIELDS, dropna=False, sort=True)
    for values, group in grouped:
        if not isinstance(values, tuple):
            values = (values,)
        category, extras1, extras2, runs, is_four, is_six = values
        label = category
        if label == "wide":
            interpretation = "Wide-like provider label; event mapping not provider-confirmed."
            status = "PROBABLE"
        elif label in {"byes", "legbyes"}:
            interpretation = "Raw label resembles a cricket extras category; provider-specific event mapping/run amount unresolved."
            status = "UNRESOLVED"
        elif label == "Overstep":
            interpretation = "Provider-specific label; do not map to No ball without documentation."
            status = "UNRESOLVED"
        elif label == "Penalty":
            interpretation = "Single source label; event type and amount encoding unresolved."
            status = "UNRESOLVED"
        elif label == "other":
            interpretation = "Undocumented residual category; event type and amount encoding unresolved."
            status = "UNRESOLVED"
        else:
            interpretation = "Literal source value; no provider definition identified."
            status = "UNRESOLVED"
        rows.append(
            {
                "extras_type_raw": label,
                "extras1_runs_raw": extras1,
                "extras_2_runs_raw": extras2,
                "runs_raw": runs,
                "is_four_raw": is_four,
                "is_six_raw": is_six,
                "occurrence_count": len(group),
                "distinct_match_count": group["match_id"].nunique(),
                "match_ids_sample": ";".join(
                    group["match_id"].drop_duplicates().head(10).tolist()
                ),
                "innings_sample": ";".join(
                    group["innings"].drop_duplicates().tolist()
                ),
                "representative_source_excel_rows": ";".join(
                    str(source_excel_row(int(index)))
                    for index in group.index[:5]
                ),
                "representative_record_locators": json.dumps(
                    [
                        {
                            "source_excel_row": source_excel_row(int(index)),
                            "dataframe_index": int(index),
                            "match_id": group.at[index, "match_id"],
                            "innings": group.at[index, "innings"],
                            "innings_ball_num": group.at[index, "innings_ball_num"],
                        }
                        for index in group.index[:5]
                    ],
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "sum_runs_raw_descriptive_only": pd.to_numeric(
                    group["runs"], errors="raise"
                ).sum(),
                "sum_extras1_raw_descriptive_only": pd.to_numeric(
                    group["extras1_runs"], errors="raise"
                ).sum(),
                "sum_extras_2_raw_descriptive_only": pd.to_numeric(
                    group["extras_2_runs"], errors="raise"
                ).sum(),
                "sum_all_three_raw_fields_not_a_team_total": (
                    pd.to_numeric(group["runs"], errors="raise")
                    + pd.to_numeric(group["extras1_runs"], errors="raise")
                    + pd.to_numeric(group["extras_2_runs"], errors="raise")
                ).sum(),
                "possible_interpretation": interpretation,
                "status": status,
                "limitation": (
                    "Combination frequencies and arithmetic do not prove provider field definitions "
                    "or additivity. Preserve literal raw values."
                ),
            }
        )
    result = pd.DataFrame(rows)
    if len(result) != balls[EXTRA_FIELDS].drop_duplicates().shape[0]:
        raise ValueError("Not every observed extras combination was emitted")
    return result


def verify_representative_locators(
    balls: pd.DataFrame, extras: pd.DataFrame
) -> int:
    verified = 0
    for row in extras.to_dict("records"):
        expected = {
            "extras_type": row["extras_type_raw"],
            "extras1_runs": row["extras1_runs_raw"],
            "extras_2_runs": row["extras_2_runs_raw"],
            "runs": row["runs_raw"],
            "is_four": row["is_four_raw"],
            "is_six": row["is_six_raw"],
        }
        for locator in json.loads(row["representative_record_locators"]):
            index = int(locator["dataframe_index"])
            if source_excel_row(index) != int(locator["source_excel_row"]):
                raise ValueError(f"Bad source row arithmetic at dataframe index {index}")
            source = balls.loc[index]
            for field, value in expected.items():
                if source[field] != value:
                    raise ValueError(
                        f"Representative locator {index}/{field} does not match combination"
                    )
            for field in ("match_id", "innings", "innings_ball_num"):
                if source[field] != str(locator[field]):
                    raise ValueError(
                        f"Representative locator {index}/{field} does not match source"
                    )
            verified += 1
    return verified


def verify_player_row_locators(
    balls: pd.DataFrame,
    frame: pd.DataFrame,
    player_id_column: str,
    player_name_column: str,
    source_id_column: str,
    source_name_column: str,
) -> int:
    verified = 0
    for row in frame.to_dict("records"):
        expected_rows = [
            int(value)
            for value in row["representative_source_excel_rows"].split(";")
            if value
        ]
        for excel_row in expected_rows:
            index = excel_row - 2
            if index not in balls.index:
                raise ValueError(f"Player locator outside source file: row {excel_row}")
            source = balls.loc[index]
            if (
                source["match_id"] != row["match_id"]
                or source["innings"] != row["innings"]
                or source[source_id_column] != str(row[player_id_column])
                or source[source_name_column] != str(row[player_name_column])
            ):
                raise ValueError(
                    f"Player source locator {excel_row} does not match grouped record"
                )
            verified += 1
    return verified


def verify_legality_row_ranges(
    balls: pd.DataFrame, legality: pd.DataFrame
) -> None:
    for row in legality.to_dict("records"):
        group = _local_group(balls, row["match_id"], row["innings"])
        expected_range = (
            f"{source_excel_row(int(group.index.min()))}-"
            f"{source_excel_row(int(group.index.max()))}"
        )
        if (
            expected_range != row["source_excel_row_range"]
            or len(group) != int(row["source_delivery_row_count_not_legal_balls"])
        ):
            raise ValueError(
                f"Legal-delivery local row range mismatch for "
                f"{row['match_id']}/{row['innings']}"
            )


def create_delivery_legality_analysis(
    balls: pd.DataFrame, evidence: pd.DataFrame
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for e in evidence.to_dict("records"):
        group = _local_group(balls, e["match_id"], e["innings"])
        labels = group["extras_type"]
        wide = labels.eq("wide")
        overstep = labels.eq("Overstep")
        other = labels.eq("other")
        scorecard_balls = overs_to_balls(e["scorecard_overs"])
        if scorecard_balls is None:
            raise ValueError(
                f"Could not parse scorecard overs {e['scorecard_overs']!r} for {e['match_id']}"
            )
        candidates = [
            ("All delivery rows", len(group)),
            ("Exclude extras_type=wide", int((~wide).sum())),
            ("Exclude wide and Overstep (candidate only)", int((~(wide | overstep)).sum())),
            (
                "Exclude wide, Overstep, and other (candidate only)",
                int((~(wide | overstep | other)).sum()),
            ),
        ]
        row_range = (
            f"{source_excel_row(int(group.index.min()))}-"
            f"{source_excel_row(int(group.index.max()))}"
        )
        sequence = pd.to_numeric(group["innings_ball_num"], errors="raise")
        for rule, candidate in candidates:
            equal = candidate == scorecard_balls
            if rule == "All delivery rows":
                status = "EXACT MATCH" if equal else "MISMATCH"
            elif equal:
                status = "PARTIAL MATCH"
            else:
                status = "MISMATCH"
            records.append(
                {
                    "match_id": e["match_id"],
                    "match_date": e["match_date"],
                    "innings": e["innings"],
                    "scorecard_batting_team": e["scorecard_batting_team"],
                    "source_excel_row_range": row_range,
                    "source_delivery_row_count_not_legal_balls": len(group),
                    "wide_label_rows": int(wide.sum()),
                    "overstep_label_rows": int(overstep.sum()),
                    "other_label_rows": int(other.sum()),
                    "overid_max": max(
                        (_as_int(value) or 0 for value in group["overid"]),
                        default=0,
                    ),
                    "over_ball_num_max": max(
                        (_as_int(value) or 0 for value in group["over_ball_num"]),
                        default=0,
                    ),
                    "innings_ball_num_first": int(sequence.iloc[0]),
                    "innings_ball_num_last": int(sequence.iloc[-1]),
                    "innings_ball_num_unique_count": int(sequence.nunique()),
                    "innings_ball_num_contiguous_from_one": sequence.tolist()
                    == list(range(1, len(sequence) + 1)),
                    "scorecard_overs": e["scorecard_overs"],
                    "scorecard_expected_balls_from_overs": scorecard_balls,
                    "candidate_rule": rule,
                    "candidate_ball_count": candidate,
                    "candidate_minus_scorecard_expected_balls": candidate - scorecard_balls,
                    "numeric_count_equal": equal,
                    "comparison_status": status,
                    "scorecard_source": e["scorecard_source"],
                    "scorecard_url": e["scorecard_url"],
                    "interpretation_limit": (
                        "A numeric match is not validation of the candidate delivery rule. "
                        "The scorecard reports innings overs; no source row is independently "
                        "identified as a legal/illegal delivery."
                    ),
                }
            )
    return pd.DataFrame(records)


def create_batter_balls_analysis(
    balls: pd.DataFrame, evidence: pd.DataFrame
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for e in evidence.to_dict("records"):
        group = _local_group(balls, e["match_id"], e["innings"])
        for batter_id, batter_rows in group.groupby(
            ["striker_id", "striker_name"], sort=True, dropna=False
        ):
            player_id, player_name = batter_id
            type_counts = batter_rows["extras_type"].value_counts().to_dict()
            candidate_excluding_wide = int(
                batter_rows["extras_type"].ne("wide").sum()
            )
            candidate_excluding_known_labels = int(
                (~batter_rows["extras_type"].isin(["wide", "Overstep", "other"])).sum()
            )
            rows.append(
                {
                    "match_id": e["match_id"],
                    "match_date": e["match_date"],
                    "innings": e["innings"],
                    "player_id": player_id,
                    "player_name_source": player_name,
                    "striker_delivery_row_count_not_balls_faced": len(batter_rows),
                    "wide_label_rows": int(type_counts.get("wide", 0)),
                    "overstep_label_rows": int(type_counts.get("Overstep", 0)),
                    "other_label_rows": int(type_counts.get("other", 0)),
                    "literal_None_label_rows": int(type_counts.get("None", 0)),
                    "candidate_rows_excluding_wide_not_validated": candidate_excluding_wide,
                    "candidate_rows_excluding_wide_overstep_other_not_validated": candidate_excluding_known_labels,
                    "innings_ball_num_values": ";".join(
                        batter_rows["innings_ball_num"].head(8).tolist()
                    ),
                    "representative_source_excel_rows": ";".join(
                        str(source_excel_row(int(index)))
                        for index in batter_rows.index[:5]
                    ),
                    "external_batter_scorecard_balls_faced": "",
                    "scorecard_source_url": e["scorecard_url"],
                    "comparison_status": "UNVERIFIABLE",
                    "status": "UNRESOLVED",
                    "interpretation_limit": (
                        "Prior scorecard transcriptions are innings aggregates and do not retain "
                        "batter balls faced. Fresh browser access to scorecard pages failed. "
                        "Candidate row counts are not balls faced; legal delivery semantics and "
                        "batter-facing rules are not validated."
                    ),
                }
            )
    return pd.DataFrame(rows)


def create_bowler_runs_analysis(
    balls: pd.DataFrame, evidence: pd.DataFrame
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for e in evidence.to_dict("records"):
        group = _local_group(balls, e["match_id"], e["innings"])
        for (bowler_id, bowler_name), bowler_rows in group.groupby(
            ["bowler_id", "bowler_name"], sort=True, dropna=False
        ):
            category_rows = {
                label: int((bowler_rows["extras_type"] == label).sum())
                for label in sorted(bowler_rows["extras_type"].unique())
            }
            rows.append(
                {
                    "match_id": e["match_id"],
                    "match_date": e["match_date"],
                    "innings": e["innings"],
                    "bowler_id": bowler_id,
                    "bowler_name_source": bowler_name,
                    "delivery_row_count": len(bowler_rows),
                    "sum_runs_raw_field_not_bowler_conceded": pd.to_numeric(
                        bowler_rows["runs"], errors="raise"
                    ).sum(),
                    "extras_type_row_counts_raw": json.dumps(
                        category_rows, ensure_ascii=False, sort_keys=True
                    ),
                    "extras1_runs_raw_value_counts": json_counts(
                        bowler_rows["extras1_runs"]
                    ),
                    "extras_2_runs_raw_sum_uninterpreted": pd.to_numeric(
                        bowler_rows["extras_2_runs"], errors="raise"
                    ).sum(),
                    "representative_source_excel_rows": ";".join(
                        str(source_excel_row(int(index)))
                        for index in bowler_rows.index[:5]
                    ),
                    "external_scorecard_bowler_runs_conceded": "",
                    "scorecard_source_url": e["scorecard_url"],
                    "comparison_status": "UNVERIFIABLE",
                    "status": "UNRESOLVED",
                    "interpretation_limit": (
                        "Prior scorecard evidence stores innings aggregates, not bowler figures. "
                        "Raw `runs` sums and extras codes are not bowler-conceded runs. "
                        "No validated delivery-level allocation for batter runs, wides, no-balls, "
                        "byes, leg-byes, or penalties is available."
                    ),
                }
            )
    return pd.DataFrame(rows)


def create_scorecard_validation(
    balls: pd.DataFrame,
    evidence: pd.DataFrame,
    legality: pd.DataFrame,
    special_scopes: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for e in evidence.to_dict("records"):
        group = _local_group(balls, e["match_id"], e["innings"])
        if e["scorecard_batting_team"]:
            teams = group["batting_team_id"].drop_duplicates().tolist()
            if len(teams) != 1:
                raise ValueError(
                    f"Expected one batting team for {e['match_id']}/{e['innings']}"
                )
        local_runs = int(pd.to_numeric(group["runs"], errors="raise").sum())
        local_extras1_sum = int(
            pd.to_numeric(group["extras1_runs"], errors="raise").sum()
        )
        local_extras2_sum = int(
            pd.to_numeric(group["extras_2_runs"], errors="raise").sum()
        )
        local_wickets = int(group["is_wicket"].map(_as_bool).sum())
        local_team = ""
        fields = [
            (
                "runs field sum vs scorecard batter-run subtotal",
                str(local_runs),
                e["scorecard_batter_runs"],
                "EXACT MATCH"
                if str(local_runs) == e["scorecard_batter_runs"]
                else "MISMATCH",
                "Aggregate equality corroborates batter-run interpretation for this innings; it does not define every delivery.",
            ),
            (
                "local team total vs scorecard total",
                local_team,
                e["scorecard_total_runs"],
                "UNVERIFIABLE",
                "No validated local team-total field or extras aggregation is available.",
            ),
            (
                "raw runs + extras1_runs arithmetic vs scorecard team total (diagnostic only)",
                str(local_runs + local_extras1_sum),
                e["scorecard_total_runs"],
                "EXACT MATCH"
                if str(local_runs + local_extras1_sum) == e["scorecard_total_runs"]
                else "MISMATCH",
                "Arithmetic candidate only; a numeric result cannot establish that extras1_runs is additive or a run amount.",
            ),
            (
                "raw runs + extras_2_runs arithmetic vs scorecard team total (diagnostic only)",
                str(local_runs + local_extras2_sum),
                e["scorecard_total_runs"],
                "EXACT MATCH"
                if str(local_runs + local_extras2_sum) == e["scorecard_total_runs"]
                else "MISMATCH",
                "Arithmetic candidate only; extras_2_runs semantics remain unresolved.",
            ),
            (
                "raw runs + extras1_runs + extras_2_runs arithmetic vs scorecard team total (diagnostic only)",
                str(local_runs + local_extras1_sum + local_extras2_sum),
                e["scorecard_total_runs"],
                "EXACT MATCH"
                if str(local_runs + local_extras1_sum + local_extras2_sum)
                == e["scorecard_total_runs"]
                else "MISMATCH",
                "Arithmetic candidate only; neither extras field is validated as an additive run amount.",
            ),
            (
                "source is_wicket count vs scorecard wickets",
                str(local_wickets),
                e["scorecard_wickets"],
                "EXACT MATCH"
                if str(local_wickets) == e["scorecard_wickets"]
                else "MISMATCH",
                "Aggregate equality only; provider wicket/dismissal semantics and anomalies remain under review.",
            ),
            (
                "local extras allocation vs scorecard extras breakdown",
                json_counts(group["extras_type"]),
                json.dumps(
                    {
                        "extras": e["scorecard_extras"],
                        "byes": e["scorecard_byes"],
                        "legbyes": e["scorecard_legbyes"],
                        "wides": e["scorecard_wides"],
                        "no_balls": e["scorecard_noballs"],
                        "penalty": e["scorecard_penalty"],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "UNVERIFIABLE",
                "Local labels/codes and event-row counts are not validated run amounts and cannot be equated to scorecard runs.",
            ),
            (
                "wide-label event rows vs scorecard wide-run amount (units differ)",
                str(int(group["extras_type"].eq("wide").sum())),
                e["scorecard_wides"],
                "UNVERIFIABLE",
                "Provider event-row count is not a validated wide-run amount; comparisons are descriptive only.",
            ),
            (
                "Overstep-label event rows vs scorecard no-ball-run amount (units differ)",
                str(int(group["extras_type"].eq("Overstep").sum())),
                e["scorecard_noballs"],
                "UNVERIFIABLE",
                "Overstep is not confirmed as No ball, and event-row count is not a run amount.",
            ),
            (
                "byes-label event rows vs scorecard byes-run amount (units differ)",
                str(int(group["extras_type"].eq("byes").sum())),
                e["scorecard_byes"],
                "UNVERIFIABLE",
                "Provider mapping is not confirmed; event-row count is not a run amount.",
            ),
            (
                "legbyes-label event rows vs scorecard leg-byes-run amount (units differ)",
                str(int(group["extras_type"].eq("legbyes").sum())),
                e["scorecard_legbyes"],
                "UNVERIFIABLE",
                "Provider mapping is not confirmed; event-row count is not a run amount.",
            ),
            (
                "batter balls faced",
                "",
                "",
                "UNVERIFIABLE",
                "Prior retained scorecards do not contain per-batter balls-faced transcription; browser access failed.",
            ),
            (
                "bowler runs conceded",
                "",
                "",
                "UNVERIFIABLE",
                "Prior retained scorecards do not contain per-bowler figures; delivery-level runs/extras allocation is unresolved.",
            ),
            (
                "bowler-creditable wickets",
                "",
                "",
                "UNVERIFIABLE",
                "Prior aggregate wicket comparison is for team wickets; bowler-credit attribution is not locally validated.",
            ),
        ]
        candidate_rows = legality.loc[
            (legality["match_id"] == e["match_id"])
            & (legality["innings"] == e["innings"])
            & legality["candidate_rule"].eq(
                "Exclude wide, Overstep, and other (candidate only)"
            )
        ]
        candidate = candidate_rows.iloc[0] if not candidate_rows.empty else None
        if candidate is not None:
            candidate_equal = _as_bool(candidate["numeric_count_equal"])
            fields.append(
                (
                    "candidate ball count vs scorecard overs",
                    str(candidate["candidate_ball_count"]),
                    str(candidate["scorecard_expected_balls_from_overs"]),
                    "PARTIAL MATCH" if candidate_equal else "MISMATCH",
                    "Sample candidate excludes `wide`, `Overstep`, and `other`; numeric equality is not a confirmed legality rule.",
                )
            )
        else:
            fields.append(
                (
                    "candidate ball count vs scorecard overs",
                    "",
                    e["scorecard_overs"],
                    "UNVERIFIABLE",
                    "No parsed scorecard overs value was available.",
                )
            )
        source_first = source_excel_row(int(group.index.min()))
        source_last = source_excel_row(int(group.index.max()))
        overall_status = (
            "PARTIAL MATCH"
            if str(local_runs) == e["scorecard_batter_runs"]
            and str(local_wickets) == e["scorecard_wickets"]
            else "MISMATCH"
        )
        for dimension, local_value, external_value, status, explanation in fields:
            rows.append(
                {
                    "match_id": e["match_id"],
                    "match_date": e["match_date"],
                    "competition": e.get("competition", ""),
                    "format": e.get("format", ""),
                    "innings": e["innings"],
                    "local_batting_team_id_values": ";".join(
                        group["batting_team_id"].drop_duplicates().tolist()
                    ),
                    "scorecard_batting_team": e["scorecard_batting_team"],
                    "source_excel_row_range": f"{source_first}-{source_last}",
                    "local_value": local_value,
                    "external_scorecard_value": external_value,
                    "validation_dimension": dimension,
                    "comparison_status": status,
                    "overall_innings_status": overall_status,
                    "scorecard_source": e["scorecard_source"],
                    "scorecard_url": e["scorecard_url"],
                    "explanation_and_limit": explanation,
                }
            )
    for scope in special_scopes.to_dict("records"):
        local_scope = _local_group(balls, scope["match_id"], scope["innings"])
        local_scope_value = (
            "Local innings rows exist; independent scorecard figures not retained"
            if not local_scope.empty
            else "No local delivery rows beyond innings 2"
        )
        rows.append(
            {
                "match_id": scope["match_id"],
                "match_date": scope["match_date"],
                "competition": scope["competition"],
                "format": scope["format"],
                "innings": scope["innings"],
                "local_batting_team_id_values": "",
                "scorecard_batting_team": "",
                "source_excel_row_range": "",
                "local_value": local_scope_value,
                "external_scorecard_value": scope["scope_note"],
                "validation_dimension": "tie-break / special-innings delivery coverage",
                "comparison_status": "UNVERIFIABLE",
                "overall_innings_status": "UNVERIFIABLE",
                "scorecard_source": scope["scorecard_source"],
                "scorecard_url": scope["scorecard_url"],
                "explanation_and_limit": (
                    "Retained M2.2B evidence records tie-break play on the scorecard "
                    "but no local delivery rows beyond innings 2; no innings values "
                    "or player statistics are inferred."
                ),
            }
        )
    return pd.DataFrame(rows)


def read_special_scorecard_scopes() -> pd.DataFrame:
    m2b = read_csv(M2B_SCORECARD_PATH)
    special = m2b.loc[~m2b["innings"].isin(["1", "2"])].copy()
    if special.empty:
        return pd.DataFrame(
            columns=[
                "match_id",
                "match_date",
                "competition",
                "format",
                "innings",
                "scope_note",
                "scorecard_source",
                "scorecard_url",
            ]
        )
    return special.rename(
        columns={
            "scorecard_source": "scorecard_source",
            "scorecard_url": "scorecard_url",
            "discrepancy_explanation": "scope_note",
        }
    )[
        [
            "match_id",
            "match_date",
            "competition",
            "format",
            "innings",
            "scope_note",
            "scorecard_source",
            "scorecard_url",
        ]
    ]


def create_unresolved_fields() -> pd.DataFrame:
    unresolved = [
        ("Original dataset provider", "UNRESOLVED", "Archive contains data files and problem PDF only; prior local/web searches found no verifiable provider or schema.", "Obtain vendor/source contract, original download URL, or signed metadata."),
        ("runs", "PROBABLE", "Sum matches scorecard batter-run subtotal in 18 regulation innings across IPL/T20I; no provider documentation.", "Provider field definition and delivery-level exceptions across competitions."),
        ("extras_type literal None", "UNRESOLVED", "189,167 rows; paired with extras1_runs=6. Literal text is preserved, not treated as blank.", "Provider null/category convention."),
        ("extras1_runs", "PROBABLE", "A single constant value maps to each observed extras_type label, including literal None; pattern suggests a category/code field.", "Provider codebook; do not treat as additive amount."),
        ("extras_2_runs", "UNRESOLVED", "36 nonzero rows: 20 values of 1 and 16 of 4; appears on Overstep/other and one literal-None row.", "Provider definition and rule for relationship/additivity."),
        ("Additivity of runs/extras1_runs/extras_2_runs", "UNRESOLVED", "18 scorecard sums corroborate `runs` against batter runs; no local total/extras formula is validated.", "Provider scoring schema and delivery-level reconciliation."),
        ("extras_type=wide", "PROBABLE", "7,714 rows have this label; all have runs=0, extras1_runs=2, extras_2_runs=0; selected scorecards provide aggregate corroboration only.", "Provider mapping and explicit wide-run/legality indicator."),
        ("extras_type=Overstep", "UNRESOLVED", "576 rows; label counts do not consistently equal scorecard No-ball extras, and no explicit no-ball flag exists.", "Provider definition; do not infer No ball from label."),
        ("byes / legbyes provider event mapping", "UNRESOLVED", "Raw labels occur 529 and 2,748 times respectively; scorecard aggregates do not independently validate per-delivery event mapping or amount.", "Provider-specific code mapping and amount fields."),
        ("Penalty and other labels", "UNRESOLVED", "One Penalty row and 264 `other` rows; category/amount interpretation is not documented.", "Provider category definitions and source event evidence."),
        ("Multiple extras on one delivery", "UNRESOLVED", "Nonzero extras_2_runs and mixed source combinations exist, but no validated independent extras-per-delivery representation.", "Provider schema and row-level scorecard/event evidence."),
        ("Legal deliveries / overid / over_ball_num", "UNRESOLVED", "Candidate exclusions match scorecard ball totals inconsistently; excluding wide+Overstep+other matched 18/18 but is sample-fitted and uses undocumented labels.", "Provider legal-ball flag/rule plus delivery-level independent validation."),
        ("Batter balls faced", "UNRESOLVED", "Striker rows are available but the legal/faced-delivery rule and per-batter scorecard evidence are absent.", "Per-batter scorecard transcription and validated delivery classification."),
        ("Bowler runs conceded", "UNRESOLVED", "MCC rules identify categories when event types and amounts are known; source delivery-level amounts/allocation are not validated.", "Provider extra/run allocation plus independent per-bowler scorecards."),
        ("Cricket-law bowler debit categories", "CONFIRMED", "MCC Law 18.10.3 states bowler debit for runs scored by striker, No-ball extras and Wide runs; this is law, not provider mapping.", "Preserve rule/provider distinction; verify applicable competition conditions."),
        ("T20/T20I competition-specific scoring conditions", "UNRESOLVED", "The ICC playing-conditions index was identified, but historical conditions applying to each selected match were not individually validated.", "Match-date and competition-specific playing-condition documents."),
    ]
    return pd.DataFrame(
        unresolved,
        columns=[
            "field_or_rule",
            "status",
            "evidence",
            "evidence_needed_to_resolve",
        ],
    )


def create_source_hash_report() -> pd.DataFrame:
    baseline = read_csv(BASELINE_HASH_PATH)
    baseline_by_path = {
        row["source_file"].replace("\\", "/"): row
        for row in baseline.to_dict("records")
    }
    rows: list[dict[str, Any]] = []
    for path in SOURCE_FILES:
        relative = path.relative_to(ROOT).as_posix()
        if not path.is_file():
            raise FileNotFoundError(f"Protected source file missing: {relative}")
        digest = sha256(path)
        prior = baseline_by_path.get(relative)
        prior_hash = prior["sha256"] if prior else ""
        result = "MATCH" if prior_hash and digest == prior_hash else (
            "NO BASELINE" if not prior_hash else "MISMATCH"
        )
        rows.append(
            {
                "source_file": relative,
                "sha256": digest,
                "baseline_source": "M2.3 source_hash_verification.csv",
                "baseline_sha256": prior_hash,
                "baseline_result": result,
            }
        )
    return pd.DataFrame(rows)


def provider_identification_report() -> str:
    with zipfile.ZipFile(ARCHIVE_PATH) as archive:
        zip_comment = archive.comment.decode("utf-8", errors="replace")
        entries = archive.namelist()
        member_comments = {
            info.filename: info.comment.decode("utf-8", errors="replace")
            for info in archive.infolist()
            if info.comment
        }
        pdf_name = next(
            (name for name in entries if name.lower().endswith(".pdf")), ""
        )
        pdf_bytes = archive.read(pdf_name) if pdf_name else b""
        pdf_metadata_tokens = {}
        for key in (b"/Title", b"/Author", b"/Creator", b"/Producer", b"/Subject"):
            match = re.search(re.escape(key) + rb"\s*\(([^)]{0,500})\)", pdf_bytes)
            if match:
                pdf_metadata_tokens[key.decode("ascii")] = match.group(1).decode(
                    "latin-1", errors="replace"
                )
        archive_entries = "\n".join(f"- `{name}`" for name in entries)
    csv_headers = {
        path.name: pd.read_csv(path, dtype=str, keep_default_na=False, nrows=0).columns.tolist()
        for path in sorted(DATA_DIR.glob("*.csv"))
    }
    provenance_tokens = ("provider", "vendor", "source", "schema", "version", "url")
    provenance_columns = {
        filename: [
            column
            for column in columns
            if any(token in column.casefold() for token in provenance_tokens)
        ]
        for filename, columns in csv_headers.items()
    }
    header_summary = "\n".join(
        f"- `{filename}`: {len(columns)} columns; provenance-like headers: "
        f"`{provenance_columns[filename] or 'none'}`"
        for filename, columns in csv_headers.items()
    )
    member_comment_summary = (
        "\n".join(f"- `{name}`: `{comment}`" for name, comment in member_comments.items())
        if member_comments
        else "- No per-file ZIP comments."
    )
    search_log = (
        SEARCH_RESULTS.read_text(encoding="utf-8")
        if SEARCH_RESULTS.exists()
        else "Prior provider search log was unavailable."
    )
    search_log = search_log.strip()
    if len(search_log) > 4000:
        search_log = search_log[:4000] + "\n\n(Excerpt truncated; see prior report.)"
    metadata_summary = (
        "\n".join(f"- `{key}`: `{value}`" for key, value in pdf_metadata_tokens.items())
        if pdf_metadata_tokens
        else "- No uncompressed standard Info dictionary strings were extracted by the local metadata scan; this does not prove that the PDF has no metadata."
    )
    return f"""# Original dataset provider identification

## Result

**UNRESOLVED — the original dataset provider was not identified.** The evidence in the workspace does not justify attributing the feed to a vendor. Similar column names or familiar cricket labels are not provider proof.

## Local provenance inspection

- Original archive: `data/data_pack.zip.zip`
- ZIP comment: `{zip_comment or "(empty)"}`
- Per-file ZIP comments:
{member_comment_summary}
- Archive entries:
{archive_entries}
- The archive contains six CSV files and the hackathon problem-statement PDF; it has no separate README, provider manifest, schema, API documentation, or data dictionary.
- The previous local inspection of the PDF found no data-vendor attribution. The archive PDF metadata scan returned:
{metadata_summary}
- CSV header scan:
{header_summary}
- No provider/vendor/source/schema/version/URL-like column appears in the six CSV headers. `extras1_runs`, `extras_2_runs`, `delivery_ist_time`, and `Overstep` are not sufficient to identify a provider.
- No source/download URL or provider identity was found in the repository README or project documentation.

## Prior external search evidence

The earlier exact-field searches and outcomes are preserved in
[`../provider_investigation/provider_search_results.md`](../provider_investigation/provider_search_results.md).
They found no verifiable provider documentation for `extras1_runs`,
`extras_2_runs`, or `Overstep`. Searches:

- <https://www.bing.com/search?q=%22extras1_runs%22+cricket>
- <https://www.bing.com/search?q=%22extras_2_runs%22+cricket>
- <https://www.bing.com/search?q=%22Overstep%22+%22bowl_speed%22+cricket>
- <https://www.bing.com/search?q=%22extras1_runs%22+%22Overstep%22+cricket>

These are search-result checks, not proof documentation does not exist.

## Independent scorecards versus provider evidence

The retained scorecards are independent secondary scorecards, not the source
provider or provider documentation. Their URLs and transcribed innings
aggregates are carried into `scorecard_validation.csv`. During this
investigation, fresh browser navigation to the saved Cricbuzz and MCC pages
failed (`ERR_FAILED` / HTTP 401 on the MCC page); no new figures were
transcribed. No match or player value was fabricated.

## Cricket-law sources, not provider definitions

- MCC, *The Over*, Law 17: <{LAW_17_URL}>
- MCC, *Scoring Runs*, Law 18 (including 18.10.3): <{LAW_18_URL}>
- MCC Laws overview: <{MCC_ABOUT_URL}>
- ICC playing-conditions index: <{ICC_PLAYING_CONDITIONS_URL}>

These sources establish cricket rules only. They do not prove that this
dataset's `Overstep`, `extras1_runs`, `extras_2_runs`, or other values map to
any particular event.

## Evidence classification

| Question | Status | Basis |
|---|---|---|
| Original provider identity | **UNRESOLVED** | No source URL, vendor metadata, schema, or provider-specific documentation found. |
| `runs` as batter runs | **PROBABLE** | Eighteen independent scorecard innings match the local `runs` sum to batter-run subtotal; no vendor definition. |
| Provider-specific extras encoding | **UNRESOLVED** | Stable codes/patterns exist but no codebook or vendor evidence. |
| Identifying the vendor from cricket labels | **NOT APPLICABLE** | Similarity of generic labels is not provider-identification evidence. |
"""


def create_resolution_report(
    balls: pd.DataFrame,
    evidence: pd.DataFrame,
    extras: pd.DataFrame,
    legality: pd.DataFrame,
    batter: pd.DataFrame,
    bowler: pd.DataFrame,
    validation: pd.DataFrame,
    hashes: pd.DataFrame,
) -> str:
    label_counts = balls["extras_type"].value_counts(dropna=False).to_dict()
    extras1_by_label = {
        label: series.value_counts(dropna=False).sort_index().to_dict()
        for label, series in balls.groupby(
            "extras_type", dropna=False
        )["extras1_runs"]
    }
    extras1_distinct_count_by_label = (
        balls.groupby("extras_type", dropna=False)["extras1_runs"]
        .nunique(dropna=False)
        .to_dict()
    )
    extras2_nonzero = balls.loc[
        pd.to_numeric(balls["extras_2_runs"], errors="raise").ne(0)
    ]
    wide = balls.loc[balls["extras_type"].eq("wide")]
    overstep = balls.loc[balls["extras_type"].eq("Overstep")]
    wide_profile = {
        "runs": json_counts(wide["runs"]),
        "extras1_runs": json_counts(wide["extras1_runs"]),
        "extras_2_runs": json_counts(wide["extras_2_runs"]),
    }
    dedicated_event_flags = [
        column
        for column in ("wide", "is_no_ball", "no_ball", "is_legal_delivery")
        if column in balls.columns
    ]
    candidates = legality.loc[
        legality["candidate_rule"].isin(
            [
                "All delivery rows",
                "Exclude extras_type=wide",
                "Exclude wide and Overstep (candidate only)",
                "Exclude wide, Overstep, and other (candidate only)",
            ]
        )
    ]
    candidate_matches = (
        candidates.groupby("candidate_rule")["numeric_count_equal"].apply(
            lambda series: sum(_as_bool(value) for value in series)
        )
    )
    statuses = validation.groupby(
        ["validation_dimension", "comparison_status"], dropna=False
    ).size()
    additive_diagnostic_counts = {
        dimension: validation.loc[
            validation["validation_dimension"].eq(dimension),
            "comparison_status",
        ].value_counts().to_dict()
        for dimension in (
            "raw runs + extras1_runs arithmetic vs scorecard team total (diagnostic only)",
            "raw runs + extras_2_runs arithmetic vs scorecard team total (diagnostic only)",
            "raw runs + extras1_runs + extras_2_runs arithmetic vs scorecard team total (diagnostic only)",
        )
    }
    status_text = "\n".join(
        f"- `{dimension}` / `{status}`: {count} comparison rows"
        for (dimension, status), count in statuses.items()
    )
    hash_rows = "\n".join(
        f"| `{row.source_file}` | `{row.baseline_result}` | `{row.sha256}` |"
        for row in hashes.itertuples(index=False)
    )
    return f"""# M2.2E provider encoding and scoring-convention resolution

## Executive result

M2.2E is **IN PROGRESS**. The original provider was not identified, and its
field codebook remains unavailable. Prior independent scorecards strengthen
some interpretations, but they do not supply delivery-level extras, batter
balls-faced, or bowler-conceded-run values. No metric, strike rate, economy
rate, ranking, or pressure score is calculated.

## Dataset evidence

- {len(balls):,} source delivery rows were read with literal `None` retained as a string.
- Raw `extras_type` counts: `{json.dumps(label_counts, ensure_ascii=False, sort_keys=True)}`.
- `extras1_runs` values by raw label: `{json.dumps(extras1_by_label, ensure_ascii=False, sort_keys=True)}`. Each observed label has one corresponding code value; this supports a **PROBABLE** code-like interpretation, not a definition.
- Distinct `extras1_runs` values per label: `{json.dumps(extras1_distinct_count_by_label, ensure_ascii=False, sort_keys=True)}`.
- `extras_2_runs` is nonzero on {len(extras2_nonzero)} rows: `{json.dumps(Counter(extras2_nonzero["extras_2_runs"]), sort_keys=True)}`. These records are preserved in the full combination table; their meaning and additivity are **UNRESOLVED**.
- Dedicated wide/no-ball/legal-delivery columns found in this CSV: `{dedicated_event_flags or "none"}`. The `wide` and `Overstep` values are category labels.
- Raw `runs` value counts on Wide labels: `{json_counts(wide["runs"])}`; on Overstep labels: `{json_counts(overstep["runs"])}`. These are stored values, not extra-run totals.
- All {len(extras)} observed combinations of `extras_type`, `extras1_runs`, `extras_2_runs`, `runs`, `is_four`, and `is_six` are included in `extras_encoding_analysis.csv`.

## Field conclusions

| Field/convention | Status | Evidence and limit |
|---|---|---|
| Original provider | **UNRESOLVED** | ZIP comment is empty; archive lists only the six CSVs and problem PDF; previous exact-field searches yielded no verifiable vendor/schema. |
| `runs` | **PROBABLE** as batter runs at innings scope | In {len(evidence)} prior scorecard innings, the local sum agrees with scorecard batter-run subtotals. This is aggregate corroboration, not vendor documentation or a universal delivery-level guarantee. |
| `extras_type` literal `None` | **UNRESOLVED** | It is literal source text on {label_counts.get("None", 0):,} rows, paired with `extras1_runs=6`; do not convert it to empty or ordinary zero. |
| `extras1_runs` | **PROBABLE** code/category field | It has a stable one-to-one mapping to observed `extras_type` labels, including `None`; its codes are not validated run amounts and are not added. |
| `extras_2_runs` | **UNRESOLVED** | {len(extras2_nonzero)} nonzero rows include values 1 and 4; no provider meaning or additive rule is established. |
| Additivity of the three run-named fields | **UNRESOLVED** | Do not assume `runs + extras1_runs + extras_2_runs` is a team total. No validated local team-total field exists. |
| `extras_type=wide` | **PROBABLE** as a wide-like label | {len(wide):,} rows; raw distributions are `runs={wide_profile["runs"]}`, `extras1_runs={wide_profile["extras1_runs"]}`, `extras_2_runs={wide_profile["extras_2_runs"]}`. Prior scorecards show only aggregate wides, not row-level allocation. |
| `extras_type=Overstep` | **UNRESOLVED** | {len(overstep):,} rows; no mapping to No ball is proven. Its row counts do not consistently equal scorecard No-ball run totals. |
| Raw `extras_type` category strings | **CONFIRMED** as stored values | Exact literal labels and counts are preserved; the strings alone do not prove provider event mapping. |
| `byes` / `legbyes` provider mapping | **UNRESOLVED** | Raw labels occur in source; field code values 4 and 3 are not validated as run amounts or event codes. |
| `Penalty` / `other` | **UNRESOLVED** | Rare or residual labels lack provider definitions; no formula is applied. |
| Multiple extras on a delivery | **UNRESOLVED** | `extras_2_runs` nonzero rows and mixed combinations are observable, but the field semantics and event allocation are unknown. |

`extras_encoding_analysis.csv` includes raw combination counts, match/innings
examples, source-row locators, and descriptive sums of each raw numeric field.
Those sums are explicitly not interpreted as score.

The three arithmetic candidates (`runs + extras1_runs`, `runs +
extras_2_runs`, and all three fields summed) were compared with the
independently transcribed team totals in the 18 innings. Their status counts
are `{json.dumps(additive_diagnostic_counts, ensure_ascii=False, sort_keys=True)}`.
All three candidates mismatch the team total in this selected sample. This
rejects those naive sums for these cases; it does not define the provider
fields or exclude a separately documented transformation.

## Delivery legality

Candidate match counts against expected balls parsed from the retained
scorecard overs:

{chr(10).join(f"- `{rule}`: {int(count)}/{len(evidence)} innings are numerically equal" for rule, count in candidate_matches.items())}

These outcomes reproduce earlier M2.2C tests. Excluding `wide`, `Overstep`,
and `other` happens to match the aggregate scorecard ball counts in all
selected innings, but `other` is undocumented and this sample-fitted rule is
not validated at delivery level. Status: **UNRESOLVED**. Neither
`over_ball_num` nor `innings_ball_num` means legal balls; the latter supports
stored row ordering only.

`wide` rows are **PROBABLE** wide-like events, but a dependable legality filter
is not established. `Overstep` remains **UNRESOLVED** and is not classified as
a No ball. Byes, leg-byes, penalty, and other rows cannot be assigned a
legal/illegal state from the available provider evidence.

## Batter balls faced

`batter_balls_faced_analysis.csv` gives player-level source row counts and
descriptive candidate counts only for batters in the previously
scorecard-reconciled innings. These are explicitly not balls faced. The
retained scorecard transcriptions lack batter-level balls faced, and fresh
browser access failed during this task. Wides, No balls, and other events
cannot be reliably counted under provider rules. Conclusion:
**UNRESOLVED; do not calculate balls faced or strike rates.**

## Bowler runs conceded

`bowler_runs_conceded_analysis.csv` lists per-bowler delivery row counts, raw
`runs` sums, and raw extras-label/code distributions without calling them
conceded runs. MCC Law 18.10.3 describes the bowler debit as runs scored by
the striker, No-ball extras, and Wide runs. Byes and leg-byes are not among
those listed bowler debits when their event types are known; penalty-run
treatment depends on the relevant Law/event. The separate law-rule conclusion
is **CONFIRMED**; dataset mapping is not. Byes, leg-byes, and penalty labels
cannot be reliably allocated from these columns. Retained scorecards do not
include per-bowler figures, and fresh page access failed. Conclusion:
**UNRESOLVED; do not calculate conceded runs or economy rates.**

## Independent scorecard validation

`scorecard_validation.csv` contains the 18 previously retained regulation
innings across IPL T20 and T20I competitions and 9 matches, with source URLs,
local row ranges, raw local values, external scorecard values, and
per-dimension status. Aggregate `runs`-to-batter subtotal and wicket-count
checks are exact in the selected sample; the overall innings comparisons are
partial because local team totals/extras allocation are not validated.
Batter balls faced, bowler conceded runs, and bowler-creditable wickets are
unverifiable from the evidence retained. No additional scorecard was
transcribed because fresh browser navigation failed; the prior cross-format
sample was reused rather than fabricated or silently expanded.

Comparison status counts by dimension:

{status_text}

Comparison statuses describe the stated numeric pair only. A matching
candidate legal-ball count does not validate the candidate's event rule.

## Cricket law versus provider encoding

- MCC Law 17 (valid balls within an over): <{LAW_17_URL}>
- MCC Law 18, including 18.10.3 (scoring and bowler-debited runs): <{LAW_18_URL}>
- MCC Laws overview: <{MCC_ABOUT_URL}>
- ICC playing-conditions index: <{ICC_PLAYING_CONDITIONS_URL}>

These are law/playing-condition references, not source-provider definitions.
Historical conditions were not individually matched to every competition
season in this task.

## Hash verification

All seven protected source files are checked against the prior M2.3 baseline:

| File | Baseline result | Current SHA-256 |
|---|---|---|
{hash_rows}

No original CSV or ZIP content is written by this script.

## Final status

M2.2E remains **IN PROGRESS** because the provider, extras codes,
`extras_2_runs`, No-ball mapping, legal-delivery rule, batter balls-faced
semantics, and bowler-conceded-run reconstruction are not adequately
validated. Overall M2.2 remains **IN PROGRESS**. Do not mark the field
conventions complete based on these limited scorecard aggregates.
"""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    original_hashes_before = {path: sha256(path) for path in SOURCE_FILES}

    baseline = read_csv(BASELINE_HASH_PATH)
    expected_hashes = {
        row["source_file"].replace("\\", "/"): row["sha256"]
        for row in baseline.to_dict("records")
    }
    for source_path in SOURCE_FILES:
        relative = source_path.relative_to(ROOT).as_posix()
        if expected_hashes.get(relative) != original_hashes_before[source_path]:
            raise ValueError(f"Protected source hash mismatch before run: {relative}")

    balls = read_csv(BALL_PATH)
    required = {
        "match_id",
        "innings",
        "innings_ball_num",
        "overid",
        "over_ball_num",
        "striker_id",
        "striker_name",
        "bowler_id",
        "bowler_name",
        "batting_team_id",
        "bowling_team_id",
        *EXTRA_FIELDS,
        "is_wicket",
    }
    missing = required.difference(balls.columns)
    if missing:
        raise ValueError(f"Required source columns missing: {sorted(missing)}")

    evidence = normalize_scorecard_evidence()
    locator_checks = validate_prior_locators(balls, evidence)
    special_scopes = read_special_scorecard_scopes()
    match_table = read_csv(MATCHES_PATH)
    competitions = read_csv(COMPETITIONS_PATH)
    evidence = evidence.merge(
        match_table[["match_id", "comp_id", "match_date"]],
        on="match_id",
        how="left",
        suffixes=("", "_match"),
        validate="many_to_one",
    )
    comp_lookup = competitions[["comp_id", "comp_name", "match_format"]].rename(
        columns={"comp_name": "competition", "match_format": "format"}
    )
    evidence = evidence.merge(comp_lookup, on="comp_id", how="left", validate="many_to_one")
    evidence["match_date"] = evidence["match_date"].where(
        evidence["match_date"].ne(""), evidence["match_date_match"]
    )
    evidence = evidence.drop(columns=["match_date_match"])
    if evidence["scorecard_url"].eq("").any():
        raise ValueError("A prior scorecard comparison has no source URL")

    extras = create_extras_analysis(balls)
    representative_locators_verified = verify_representative_locators(
        balls, extras
    )
    legality = create_delivery_legality_analysis(balls, evidence)
    batter = create_batter_balls_analysis(balls, evidence)
    bowler = create_bowler_runs_analysis(balls, evidence)
    batter_locators_verified = verify_player_row_locators(
        balls,
        batter,
        "player_id",
        "player_name_source",
        "striker_id",
        "striker_name",
    )
    bowler_locators_verified = verify_player_row_locators(
        balls,
        bowler,
        "bowler_id",
        "bowler_name_source",
        "bowler_id",
        "bowler_name",
    )
    verify_legality_row_ranges(balls, legality)
    validation = create_scorecard_validation(
        balls, evidence, legality, special_scopes
    )
    unresolved = create_unresolved_fields()
    hashes = create_source_hash_report()

    outputs = {
        "extras_encoding_analysis.csv": extras,
        "delivery_legality_analysis.csv": legality,
        "batter_balls_faced_analysis.csv": batter,
        "bowler_runs_conceded_analysis.csv": bowler,
        "scorecard_validation.csv": validation,
        "unresolved_provider_fields.csv": unresolved,
        "source_hash_verification.csv": hashes,
    }
    for filename, frame in outputs.items():
        frame.to_csv(OUTPUT_DIR / filename, index=False, encoding="utf-8-sig")

    identification = provider_identification_report()
    (OUTPUT_DIR / "provider_identification_report.md").write_text(
        identification, encoding="utf-8"
    )
    report = create_resolution_report(
        balls, evidence, extras, legality, batter, bowler, validation, hashes
    )
    (OUTPUT_DIR / "provider_encoding_resolution_report.md").write_text(
        report, encoding="utf-8"
    )

    for path, digest in original_hashes_before.items():
        if sha256(path) != digest:
            raise RuntimeError(
                f"Protected source changed during investigation: {path.relative_to(ROOT)}"
            )
    if len(locator_checks) != len(evidence):
        raise RuntimeError("Not all retained scorecard source ranges were checked")
    if representative_locators_verified < len(extras):
        raise RuntimeError("Representative source-row locators were not verified")
    locator_checks.to_csv(
        OUTPUT_DIR / "scorecard_source_locator_checks.csv",
        index=False,
        encoding="utf-8-sig",
    )
    print(
        f"Rows: {len(balls):,}; extras combinations: {len(extras)}; "
        f"scorecard innings: {len(evidence)}; source locators checked: "
        f"{len(locator_checks)} scorecard groups/{representative_locators_verified} "
        f"extras representative rows/{batter_locators_verified} batter rows/"
        f"{bowler_locators_verified} bowler rows; protected hashes matched: "
        f"{len(hashes)}."
    )
    print(f"Outputs: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
