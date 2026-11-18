"""Generate source-row-level investigation files for the M1 audit findings."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "extracted"
OUTPUT_DIR = ROOT / "audit_reports" / "anomaly_investigation"
CHUNK_SIZE = 100_000

BALL_FILE = "ball_by_ball.csv"
MATCH_FILE = "matches.csv"
PLAYING_FILE = "playing_eleven.csv"
MAPPING_FILE = "competition_team_player_mapping.csv"

BALL_CONTEXT = [
    "match_id",
    "innings",
    "overid",
    "over_ball_num",
    "innings_ball_num",
    "striker_id",
    "striker_name",
    "non_striker_id",
    "non_striker_name",
    "bowler_id",
    "bowler_name",
    "is_wicket",
    "dismissal_type_id",
    "dismissal_type",
    "dismissed_player_id",
    "bowl_speed",
    "extras_type",
    "extras1_runs",
    "extras_2_runs",
    "runs",
    "is_four",
    "is_six",
]

EXTRAS_FIELDS = [
    "match_id",
    "innings",
    "overid",
    "over_ball_num",
    "innings_ball_num",
    "striker_id",
    "striker_name",
    "bowler_id",
    "bowler_name",
    "extras_type",
    "extras1_runs",
    "extras_2_runs",
    "runs",
    "is_four",
    "is_six",
]


def _read_csv(filename: str) -> pd.DataFrame:
    path = SOURCE_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"Expected extracted CSV is missing: {path}")
    try:
        return pd.read_csv(
            path,
            encoding="utf-8-sig",
            low_memory=False,
            keep_default_na=False,
            na_values=[""],
        )
    except UnicodeDecodeError:
        return pd.read_csv(
            path,
            encoding="cp1252",
            low_memory=False,
            keep_default_na=False,
            na_values=[""],
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _locator(df: pd.DataFrame, filename: str) -> pd.DataFrame:
    result = pd.DataFrame(index=df.index)
    result["source_csv"] = filename
    result["source_csv_row"] = df.index.to_series(index=df.index) + 2
    result["dataframe_index"] = df.index
    return result


def _columns(df: pd.DataFrame, candidates: list[str]) -> list[str]:
    return [column for column in candidates if column in df.columns]


def _player_names(
    mapping: pd.DataFrame,
    matches: pd.DataFrame,
    playing: pd.DataFrame,
) -> pd.Series:
    """Resolve playing-eleven names through match competition/team mapping."""
    match_comp = matches[["match_id", "comp_id"]].drop_duplicates("match_id")
    merged = playing.merge(
        match_comp,
        on="match_id",
        how="left",
        validate="many_to_one",
    )
    map_keys = mapping[
        ["comp_id", "team_id", "player_id", "player_name"]
    ].drop_duplicates()
    merged = merged.merge(
        map_keys,
        on=["comp_id", "team_id", "player_id"],
        how="left",
        validate="many_to_one",
    )
    return merged.set_index(playing.index)["player_name"]


def _write_csv(df: pd.DataFrame, filename: str) -> Path:
    path = OUTPUT_DIR / filename
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _all_extras_records(ball: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Return all issue rows plus one traceable example of every field combination."""
    required = _columns(ball, EXTRAS_FIELDS)
    extras_type_text = ball["extras_type"].astype("string").str.strip().str.casefold()
    missing_or_none_type = (
        ball["extras_type"].isna()
        | extras_type_text.eq("")
        | extras_type_text.eq("none")
    )
    extras1 = pd.to_numeric(ball["extras1_runs"], errors="coerce")
    extras2 = pd.to_numeric(ball["extras_2_runs"], errors="coerce")

    extras1_without_type = missing_or_none_type & extras1.notna() & extras1.ne(0)
    extras2_nonzero = extras2.notna() & extras2.ne(0)
    review_mask = extras1_without_type | extras2_nonzero

    combination_fields = [
        "extras_type",
        "extras1_runs",
        "extras_2_runs",
        "runs",
        "is_four",
        "is_six",
    ]
    present_combination_fields = _columns(ball, combination_fields)
    if len(present_combination_fields) != len(combination_fields):
        raise ValueError("The audited ball-by-ball CSV is missing extras fields.")

    grouped = ball.groupby(present_combination_fields, dropna=False, sort=False)
    examples = grouped.head(1).copy()
    example_indexes = set(examples.index)
    issue_indexes = set(ball.index[review_mask])
    chosen_indexes = sorted(example_indexes | issue_indexes)
    result = ball.loc[chosen_indexes, required].copy()
    result = _locator(ball.loc[chosen_indexes], BALL_FILE).join(result)
    selected_type = ball.loc[chosen_indexes, "extras_type"]
    selected_type_text = selected_type.astype("string").str.strip().str.casefold()
    result["extras_type_missing_or_literal_none_with_nonzero_extras1"] = (
        (
            selected_type.isna()
            | selected_type_text.eq("")
            | selected_type_text.eq("none")
        )
        & pd.to_numeric(ball.loc[chosen_indexes, "extras1_runs"], errors="coerce").ne(0)
    ).to_numpy()
    result["extras_type_is_literal_none"] = selected_type_text.eq("none").to_numpy()
    group_ids = grouped.ngroup()
    group_sizes = group_ids.value_counts()
    result["extras_combination_row_count"] = (
        group_ids.loc[chosen_indexes].map(group_sizes).to_numpy()
    )
    result["extras_2_runs_nonzero"] = (
        pd.to_numeric(ball.loc[chosen_indexes, "extras_2_runs"], errors="coerce").ne(0)
    ).to_numpy()
    result["is_representative_of_distinct_extras_combination"] = [
        index in example_indexes for index in chosen_indexes
    ]
    result["anomaly_or_review_reason"] = [
        _extras_reason(
            result.iloc[position],
            bool(result.iloc[position]["is_representative_of_distinct_extras_combination"]),
        )
        for position in range(len(result))
    ]
    return result, len(examples)


def _extras_reason(row: pd.Series, is_representative: bool) -> str:
    reasons: list[str] = []
    if row["extras_type_missing_or_literal_none_with_nonzero_extras1"]:
        reasons.append(
            "extras_type is blank or the literal 'None' while extras1_runs is "
            "nonzero; field semantics are unverified"
        )
    if row["extras_2_runs_nonzero"]:
        reasons.append("extras_2_runs is nonzero; meaning is unverified")
    if is_representative:
        reasons.append(
            "representative of a distinct observed combination of "
            "extras_type/extras1_runs/extras_2_runs/runs/is_four/is_six"
        )
    return "; ".join(reasons)


def _source_excel_lines(path: Path) -> tuple[int, int]:
    """Return data-record count and physical-line count for a CSV with a header."""
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source)
        try:
            next(reader)
        except StopIteration as exc:
            raise ValueError(f"CSV has no header: {path}") from exc
        record_count = 0
        multiline_records = 0
        previous_line = reader.line_num
        while True:
            try:
                next(reader)
            except StopIteration:
                break
            record_count += 1
            if reader.line_num != previous_line + 1:
                multiline_records += 1
            previous_line = reader.line_num
        return record_count, multiline_records


def _verify_source_rows(outputs: list[Path]) -> None:
    """Re-read every cited source row and compare exported original values."""
    for output_path in outputs:
        source_states: dict[str, dict[str, Any]] = {}
        for chunk in pd.read_csv(
            output_path,
            encoding="utf-8-sig",
            low_memory=False,
            keep_default_na=False,
            na_values=[""],
            chunksize=5000,
        ):
            for filename, rows in chunk.groupby("source_csv", sort=False):
                filename = str(filename)
                ordered_rows = rows.sort_values("source_csv_row")
                if filename not in source_states:
                    source_path = SOURCE_DIR / filename
                    source_file = source_path.open(encoding="utf-8-sig", newline="")
                    reader = csv.reader(source_file)
                    header = next(reader)
                    header_positions = {
                        name: index for index, name in enumerate(header)
                    }
                    source_states[filename] = {
                        "file": source_file,
                        "reader": reader,
                        "header": header,
                        "header_positions": header_positions,
                        "current_excel_row": 1,
                        "current_record": None,
                    }
                state = source_states[filename]
                for _, record in ordered_rows.iterrows():
                    excel_row = int(record["source_csv_row"])
                    expected_index = excel_row - 2
                    if "dataframe_index" in record.index:
                        if int(record["dataframe_index"]) != expected_index:
                            raise AssertionError(
                                f"DataFrame index mismatch at {filename}:{excel_row}"
                            )
                    if excel_row < state["current_excel_row"]:
                        raise AssertionError(
                            f"Source locators are not in source-row order in "
                            f"{output_path.name}: {filename}:{excel_row}"
                        )
                    while state["current_excel_row"] < excel_row:
                        try:
                            state["current_record"] = next(state["reader"])
                        except StopIteration as exc:
                            raise AssertionError(
                                f"Source row {excel_row} does not exist in {filename}"
                            ) from exc
                        state["current_excel_row"] += 1
                    source_record = state["current_record"]
                    if source_record is None:
                        raise AssertionError(
                            f"Source row {excel_row} does not exist in {filename}"
                        )
                    if len(source_record) != len(state["header"]):
                        raise AssertionError(
                            f"Column count mismatch at {filename}:{excel_row}"
                        )
                    for column in state["header"]:
                        if column not in record.index:
                            continue
                        expected = source_record[state["header_positions"][column]]
                        actual = record[column]
                        if pd.isna(actual):
                            if expected.strip():
                                raise AssertionError(
                                    f"Value mismatch at {filename}:{excel_row}:{column}"
                                )
                        elif str(actual) != expected:
                            if str(actual).casefold() in {"true", "false"} and (
                                str(actual).casefold() == expected.strip().casefold()
                            ):
                                continue
                            try:
                                numeric_match = float(actual) == float(expected)
                            except (TypeError, ValueError):
                                numeric_match = False
                            if not numeric_match:
                                raise AssertionError(
                                    f"Value mismatch at {filename}:{excel_row}:{column}: "
                                    f"{actual!r} != {expected!r}"
                                )
        for state in source_states.values():
            state["file"].close()


    for filename in (
        BALL_FILE,
        MATCH_FILE,
        PLAYING_FILE,
        MAPPING_FILE,
    ):
        record_count, multiline_records = _source_excel_lines(SOURCE_DIR / filename)
        if multiline_records:
            raise AssertionError(
                f"{filename} contains multiline records; Excel row locators need "
                "physical-line handling."
            )
        if not record_count:
            raise AssertionError(f"No records found in {filename}")


def _markdown_table(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_No affected records._"
    selected_columns = _columns(df, columns)
    subset = df.loc[:, selected_columns].astype("string").fillna("")
    escape = lambda value: str(value).replace("|", r"\|").replace("\r", " ").replace("\n", " ")
    lines = [
        "| " + " | ".join(selected_columns) + " |",
        "| " + " | ".join("---" for _ in selected_columns) + " |",
    ]
    lines.extend(
        "| " + " | ".join(escape(value) for value in row) + " |"
        for row in subset.itertuples(index=False, name=None)
    )
    return "\n".join(lines)


def _build_summary(
    negative: pd.DataFrame,
    wicket: pd.DataFrame,
    repeated: pd.DataFrame,
    coverage: pd.DataFrame,
    extras: pd.DataFrame,
    extras_combinations: int,
    zero_mom: pd.DataFrame,
) -> pd.DataFrame:
    issue_rows = int(
        extras[
            "extras_type_missing_or_literal_none_with_nonzero_extras1"
        ].sum()
    )
    extras2_rows = int(extras["extras_2_runs_nonzero"].sum())
    groups = int(
        repeated[
            ["match_id", "team_id", "player_id"]
        ].drop_duplicates().shape[0]
    )

    summaries = [
        {
            "category": "Negative bowling speed",
            "source_csv": BALL_FILE,
            "affected_records": len(negative),
            "distinct_keys_or_values": len(negative),
            "classification": "Suspicious value; not confirmed error",
            "investigation_file": "negative_bowling_speed_records.csv",
            "review_note": "Verify source convention and delivery-level record before interpreting -1.",
        },
        {
            "category": "Wicket without dismissed-player ID",
            "source_csv": BALL_FILE,
            "affected_records": int(
                wicket["issue_category"].eq("wicket_without_dismissed_player_id").sum()
            ),
            "distinct_keys_or_values": "",
            "classification": "Record inconsistency; may be incomplete or a source convention",
            "investigation_file": "wicket_dismissal_inconsistencies.csv",
            "review_note": "Confirm dismissal type and whether an ID is expected for this event.",
        },
        {
            "category": "Dismissed-player ID without wicket flag",
            "source_csv": BALL_FILE,
            "affected_records": int(
                wicket["issue_category"].eq("dismissed_player_id_without_wicket_flag").sum()
            ),
            "distinct_keys_or_values": "",
            "classification": "Record inconsistency; source semantics need review",
            "investigation_file": "wicket_dismissal_inconsistencies.csv",
            "review_note": "Review is_wicket, dismissal type, and dismissed-player ID together.",
        },
        {
            "category": "Zero-coded player of the match",
            "source_csv": MATCH_FILE,
            "affected_records": len(zero_mom),
            "distinct_keys_or_values": 1,
            "classification": "Possible placeholder; not a mapped player ID",
            "investigation_file": "zero_player_of_match_records.csv",
            "review_note": "Confirm whether 0 encodes no award/unknown rather than a real player.",
        },
        {
            "category": "Repeated playing-eleven candidate keys",
            "source_csv": PLAYING_FILE,
            "affected_records": len(repeated),
            "distinct_keys_or_values": groups,
            "classification": "Suspicious repetition; rows differ in batting_order",
            "investigation_file": "repeated_playing_eleven_records.csv",
            "review_note": "All rows retained; inspect both batting-order values per player and match.",
        },
        {
            "category": "Matches without ball-by-ball records",
            "source_csv": MATCH_FILE,
            "affected_records": int(coverage["missing_dataset"].eq(BALL_FILE).sum()),
            "distinct_keys_or_values": int(
                coverage.loc[
                    coverage["missing_dataset"].eq(BALL_FILE), "match_id"
                ].nunique()
            ),
            "classification": "Expected-looking coverage gap; all observed results are Match Abandoned",
            "investigation_file": "missing_match_coverage.csv",
            "review_note": "Validate match outcome, archive scope, and whether abandoned games have delivery rows.",
        },
        {
            "category": "Matches without playing-eleven records",
            "source_csv": MATCH_FILE,
            "affected_records": int(coverage["missing_dataset"].eq(PLAYING_FILE).sum()),
            "distinct_keys_or_values": int(
                coverage.loc[
                    coverage["missing_dataset"].eq(PLAYING_FILE), "match_id"
                ].nunique()
            ),
            "classification": "Expected-looking coverage gap; all observed results are Match Abandoned",
            "investigation_file": "missing_match_coverage.csv",
            "review_note": "Validate match outcome and whether a lineup is expected for abandoned games.",
        },
        {
            "category": "Blank/None-coded extras_type with nonzero extras1_runs",
            "source_csv": BALL_FILE,
            "affected_records": issue_rows,
            "distinct_keys_or_values": extras_combinations,
            "classification": "Literal None/blank marker; field semantics unverified",
            "investigation_file": "extras_investigation.csv",
            "review_note": "All affected rows are included; literal 'None' is preserved exactly and is not assumed to be a null.",
        },
        {
            "category": "Nonzero extras_2_runs",
            "source_csv": BALL_FILE,
            "affected_records": extras2_rows,
            "distinct_keys_or_values": "",
            "classification": "Unusual value requiring source-definition review",
            "investigation_file": "extras_investigation.csv",
            "review_note": "All rows with nonzero extras_2_runs are included; do not infer meaning.",
        },
        {
            "category": "Distinct extras-field combinations",
            "source_csv": BALL_FILE,
            "affected_records": extras_combinations,
            "distinct_keys_or_values": extras_combinations,
            "classification": "Observed value combinations; examples only",
            "investigation_file": "extras_investigation.csv",
            "review_note": "At least one exact source record is included for every combination.",
        },
    ]
    return pd.DataFrame(summaries)


def _build_report(
    summary: pd.DataFrame,
    negative: pd.DataFrame,
    wicket: pd.DataFrame,
    repeated: pd.DataFrame,
    coverage: pd.DataFrame,
    extras: pd.DataFrame,
    zero_mom: pd.DataFrame,
    extras_combinations: int,
) -> str:
    lines = [
        "# RR ScoutIQ — M1 Anomaly Investigation",
        "",
        "This report locates audit findings in the extracted source CSVs. "
        "It does not change or clean source records.",
        "",
        "## Source and row-number convention",
        "",
        f"Source directory: `data/extracted/`.",
        "CSV files have one header row and no embedded-newline records. "
        "Accordingly, `source_csv_row` is the Excel row number including the header, "
        "and `dataframe_index = source_csv_row - 2` for the default pandas read.",
        "Every output record carries its source filename, row number, and DataFrame "
        "index where applicable. CSV fields in the locator files are copied from "
        "the source unless explicitly labeled as a lookup or investigation annotation.",
        "",
        "## Findings and classification",
        "",
        _markdown_table(
            summary,
            [
                "category",
                "source_csv",
                "affected_records",
                "distinct_keys_or_values",
                "classification",
                "investigation_file",
                "review_note",
            ],
        ),
        "",
        "Classification is evidence-based and does not assert that a suspicious "
        "record is a definite source error.",
        "",
        "## Negative bowling speed",
        "",
        f"Observed: {len(negative)} record with a negative `bowl_speed`. "
        "A negative value is suspicious, but the source convention is unknown; "
        "it is not classified as a definite error.",
        "",
        _markdown_table(
            negative,
            [
                "source_csv_row",
                "dataframe_index",
                "match_id",
                "innings",
                "overid",
                "over_ball_num",
                "innings_ball_num",
                "bowler_id",
                "bowler_name",
                "bowl_speed",
                "reason",
            ],
        ),
        "",
        "Investigate the provider's missing/invalid-speed convention and verify the "
        "delivery against an authoritative source before deciding how to handle it.",
        "",
        "## Wicket/dismissed-player inconsistencies",
        "",
        "The table lists every row in either direction of the audit check. "
        "These are internal field inconsistencies, not proof of an incorrect dismissal.",
        "",
        _markdown_table(
            wicket,
            [
                "issue_category",
                "source_csv_row",
                "dataframe_index",
                "match_id",
                "innings",
                "overid",
                "over_ball_num",
                "innings_ball_num",
                "striker_id",
                "striker_name",
                "non_striker_id",
                "non_striker_name",
                "bowler_id",
                "bowler_name",
                "is_wicket",
                "dismissal_type",
                "dismissed_player_id",
                "dismissed_player_name_lookup",
            ],
        ),
        "",
        "Review the original delivery event and the source definitions for `is_wicket`, "
        "`dismissal_type`, and `dismissed_player_id`. Do not infer the affected player "
        "from striker/batter fields.",
        "",
        "## Zero-coded player-of-the-match values",
        "",
        f"Observed: {len(zero_mom)} match rows have `man_of_the_match = 0`. "
        "Zero is not a player ID in the competition/team/player mapping, so it may "
        "be a placeholder. The match CSV has no player-name field for this value; "
        "the lookup column records whether the mapping contains a name.",
        "",
        _markdown_table(
            zero_mom,
            [
                "source_csv_row",
                "dataframe_index",
                "match_id",
                "match_date",
                "result",
                "man_of_the_match",
                "player_name_lookup",
                "reason",
            ],
        ),
        "",
        "Confirm the source's encoding for missing/unawarded player-of-the-match "
        "values before treating zero as missing.",
        "",
        "## Repeated playing-eleven candidate keys",
        "",
        f"Observed: {len(repeated)} rows in "
        f"{repeated[['match_id', 'team_id', 'player_id']].drop_duplicates().shape[0]} "
        "candidate-key groups. All candidate-key repetitions differ in `batting_order`; "
        "they are not exact duplicate records. The playing-eleven file does not itself "
        "contain player names; `player_name_lookup` is joined from the mapping by "
        "competition, team, and player where available.",
        "",
        _markdown_table(
            repeated,
            [
                "source_csv_row",
                "dataframe_index",
                "match_id",
                "team_id",
                "player_id",
                "player_name_lookup",
                "batting_order",
                "is_played",
                "is_captain",
                "is_wk",
                "is_impact",
                "is_impact_off",
            ],
        ),
        "",
        "Inspect each player's rows as a group. A changed batting order may be a "
        "source issue, a repeated lineup state, or an intended roster/impact-player "
        "representation; this audit alone does not determine which.",
        "",
        "## Missing match coverage",
        "",
        "All listed matches have no rows in the named related CSV. In the audited "
        "source, all these matches have result `Match Abandoned`, so the gap may be "
        "expected; verify dataset inclusion rules rather than classifying it as data loss.",
        "",
        _markdown_table(
            coverage,
            [
                "source_csv",
                "source_csv_row",
                "dataframe_index",
                "missing_dataset",
                "match_id",
                "match_date",
                "result",
            ],
        ),
        "",
        "## Extras semantics",
        "",
        f"The source contains {extras_combinations} distinct observed combinations "
        "of `extras_type`, `extras1_runs`, `extras_2_runs`, `runs`, `is_four`, and "
        "`is_six`. The investigation CSV contains all rows with blank/literal "
        "`None` `extras_type` and nonzero `extras1_runs` ("
        f"{int(extras['extras_type_missing_or_literal_none_with_nonzero_extras1'].sum()):,} rows), "
        "all rows with nonzero `extras_2_runs` ("
        f"{int(extras['extras_2_runs_nonzero'].sum()):,} rows), and at least one "
        "source-row example of every distinct six-field combination. No field "
        "meaning or bowling-runs formula is assumed.",
        "",
        "Exact representative rows and all relevant values:",
        "",
        _markdown_table(
            extras.loc[
                extras["is_representative_of_distinct_extras_combination"]
            ],
            [
                "source_csv_row",
                "dataframe_index",
                "match_id",
                "innings",
                "overid",
                "over_ball_num",
                "innings_ball_num",
                "bowler_id",
                "bowler_name",
                "extras_type",
                "extras1_runs",
                "extras_2_runs",
                "runs",
                "is_four",
                "is_six",
                "extras_combination_row_count",
                "anomaly_or_review_reason",
            ],
        ),
        "",
        "The original audit's default pandas parsing counted the literal CSV string "
        "`None` as missing. This investigation preserves that source string and "
        "distinguishes it from a blank cell. Review the data dictionary or provider "
        "documentation, especially why `extras1_runs` is 6 on those rows. Do not "
        "sum, reinterpret, or correct these fields until their schema is established.",
        "",
        "## Other audit flags and scope",
        "",
        "All issue categories from `audit_reports/data_quality_issues.csv` are "
        "represented above: negative speed, repeated candidate keys, zero-coded "
        "player-of-the-match, both wicket/dismissed-ID directions, and ambiguous "
        "extras. The original audit found zero exact duplicate rows. The 16 missing "
        "ball-by-ball match rows and three missing playing-eleven match rows are "
        "listed individually above; these groups are not disjoint if a match is "
        "missing from both datasets.",
        "",
        "## Generated investigation files",
        "",
        "- `anomaly_summary.csv`",
        "- `negative_bowling_speed_records.csv`",
        "- `wicket_dismissal_inconsistencies.csv`",
        "- `repeated_playing_eleven_records.csv`",
        "- `missing_match_coverage.csv`",
        "- `extras_investigation.csv`",
        "- `zero_player_of_match_records.csv`",
        "- `anomaly_investigation_report.md`",
        "",
        "No player rankings, pressure scores, dataset cleaning, or M2 work was performed.",
        "",
    ]
    return "\n".join(lines)


def _verify_extras_combinations(ball: pd.DataFrame, extras: pd.DataFrame) -> int:
    fields = [
        "extras_type",
        "extras1_runs",
        "extras_2_runs",
        "runs",
        "is_four",
        "is_six",
    ]

    def key_from_row(row: pd.Series) -> tuple[str | None, ...]:
        values: list[str | None] = []
        for field in fields:
            value = row[field]
            values.append(None if pd.isna(value) else str(value))
        return tuple(values)

    expected = {key_from_row(row) for _, row in ball[fields].iterrows()}
    examples = extras.loc[
        extras["is_representative_of_distinct_extras_combination"], fields
    ]
    actual = {key_from_row(row) for _, row in examples.iterrows()}
    if expected != actual:
        raise AssertionError(
            f"Extras representative coverage mismatch: "
            f"missing={expected - actual}; extra={actual - expected}"
        )
    return len(expected)


def run_investigation() -> None:
    files = (BALL_FILE, MATCH_FILE, PLAYING_FILE, MAPPING_FILE)
    source_hashes_before = {
        filename: _sha256(SOURCE_DIR / filename) for filename in files
    }

    ball = _read_csv(BALL_FILE)
    matches = _read_csv(MATCH_FILE)
    playing = _read_csv(PLAYING_FILE)
    mapping = _read_csv(MAPPING_FILE)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    negative_mask = pd.to_numeric(ball["bowl_speed"], errors="coerce").lt(0)
    negative = ball.loc[negative_mask].copy()
    negative_output = _locator(negative, BALL_FILE).join(
        negative[_columns(negative, BALL_CONTEXT)]
    )
    negative_output["reason"] = "bowl_speed is below zero; source convention unknown"
    negative_path = _write_csv(
        negative_output, "negative_bowling_speed_records.csv"
    )

    wicket_flag = ball["is_wicket"].fillna(False).astype(bool)
    has_dismissed_id = ball["dismissed_player_id"].notna()
    wicket_masks = {
        "wicket_without_dismissed_player_id": wicket_flag & ~has_dismissed_id,
        "dismissed_player_id_without_wicket_flag": ~wicket_flag & has_dismissed_id,
    }
    wicket_parts: list[pd.DataFrame] = []
    for category, mask in wicket_masks.items():
        part = ball.loc[mask].copy()
        part_output = _locator(part, BALL_FILE).join(
            part[_columns(part, BALL_CONTEXT)]
        )
        part_output.insert(3, "issue_category", category)
        wicket_parts.append(part_output)
    wicket = pd.concat(wicket_parts, ignore_index=True)

    mapping_names: dict[str, set[str]] = {}
    for player_id, player_name in zip(mapping["player_id"], mapping["player_name"]):
        if pd.notna(player_id) and pd.notna(player_name):
            mapping_names.setdefault(str(int(player_id)), set()).add(
                str(player_name).strip()
            )
    dismissed_names: list[str] = []
    for player_id in wicket["dismissed_player_id"]:
        if pd.isna(player_id):
            dismissed_names.append("")
        else:
            names = mapping_names.get(str(int(player_id)), set())
            dismissed_names.append(" | ".join(sorted(names)) if names else "NOT FOUND")
    wicket["dismissed_player_name_lookup"] = dismissed_names
    wicket["reason"] = wicket["issue_category"].map(
        {
            "wicket_without_dismissed_player_id": (
                "is_wicket is true while dismissed_player_id is missing"
            ),
            "dismissed_player_id_without_wicket_flag": (
                "dismissed_player_id is populated while is_wicket is false"
            ),
        }
    )
    wicket = wicket.sort_values("source_csv_row", kind="stable").reset_index(drop=True)
    wicket_path = _write_csv(
        wicket, "wicket_dismissal_inconsistencies.csv"
    )

    duplicate_mask = playing.duplicated(
        ["match_id", "team_id", "player_id"], keep=False
    )
    repeated = playing.loc[duplicate_mask].copy()
    repeated["player_name_lookup"] = _player_names(
        mapping, matches, playing
    ).loc[repeated.index]
    repeated_output = _locator(repeated, PLAYING_FILE).join(repeated)
    repeated_output["reason"] = (
        "candidate key (match_id, team_id, player_id) occurs multiple times; "
        "all group rows are included"
    )
    repeated_path = _write_csv(
        repeated_output, "repeated_playing_eleven_records.csv"
    )

    coverage_parts: list[pd.DataFrame] = []
    coverage_counts = {
        BALL_FILE: set(ball["match_id"].dropna()),
        PLAYING_FILE: set(playing["match_id"].dropna()),
    }
    for missing_dataset, present_ids in coverage_counts.items():
        missing_matches = matches.loc[~matches["match_id"].isin(present_ids)].copy()
        if missing_matches.empty:
            continue
        part = _locator(missing_matches, MATCH_FILE).join(missing_matches)
        part.insert(3, "missing_dataset", missing_dataset)
        part["reason"] = (
            f"match_id is present in matches.csv but absent from {missing_dataset}"
        )
        coverage_parts.append(part)
    coverage = pd.concat(coverage_parts, ignore_index=True)
    if not coverage.empty:
        coverage = coverage.sort_values(
            "source_csv_row", kind="stable"
        ).reset_index(drop=True)
    coverage_path = _write_csv(coverage, "missing_match_coverage.csv")

    zero_mask = pd.to_numeric(
        matches["man_of_the_match"], errors="coerce"
    ).eq(0)
    zero_mom = matches.loc[zero_mask].copy()
    map_player_ids = set(pd.to_numeric(mapping["player_id"], errors="coerce").dropna())
    zero_mom_output = _locator(zero_mom, MATCH_FILE).join(
        zero_mom[
            _columns(
                zero_mom,
                ["match_id", "match_date", "result", "man_of_the_match"],
            )
        ]
    )
    zero_mom_output["player_name_lookup"] = [
        "NOT FOUND" if 0 not in map_player_ids else "MAPPING CONTAINS ID 0"
        for _ in range(len(zero_mom_output))
    ]
    zero_mom_output["reason"] = (
        "man_of_the_match is 0; value 0 is absent from the player mapping"
    )
    zero_path = _write_csv(zero_mom_output, "zero_player_of_match_records.csv")

    extras, extras_combinations = _all_extras_records(ball)
    extras_path = _write_csv(extras, "extras_investigation.csv")
    if _verify_extras_combinations(ball, extras) != extras_combinations:
        raise AssertionError("Not every distinct extras-field combination is represented.")

    summary = _build_summary(
        negative,
        wicket,
        repeated,
        coverage,
        extras,
        extras_combinations,
        zero_mom_output,
    )
    summary_path = _write_csv(summary, "anomaly_summary.csv")

    record_outputs = [
        negative_path,
        wicket_path,
        repeated_path,
        coverage_path,
        zero_path,
        extras_path,
    ]
    _verify_source_rows(record_outputs)

    report = _build_report(
        summary,
        negative_output,
        wicket,
        repeated_output,
        coverage,
        extras,
        zero_mom_output,
        extras_combinations,
    )
    report_path = OUTPUT_DIR / "anomaly_investigation_report.md"
    report_path.write_text(report, encoding="utf-8")

    changed = [
        filename
        for filename in files
        if _sha256(SOURCE_DIR / filename) != source_hashes_before[filename]
    ]
    if changed:
        raise AssertionError(f"Source CSVs changed during investigation: {changed}")

    expected_outputs = (
        summary_path,
        negative_path,
        wicket_path,
        repeated_path,
        coverage_path,
        extras_path,
        zero_path,
        report_path,
    )
    for path in expected_outputs:
        if not path.is_file() or path.stat().st_size == 0:
            raise AssertionError(f"Investigation output missing or empty: {path}")

    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Negative bowling-speed rows: {len(negative_output)}")
    print(f"Wicket/dismissal inconsistency rows: {len(wicket)}")
    print(f"Repeated playing-eleven rows: {len(repeated_output)}")
    print(f"Repeated candidate-key groups: "
          f"{repeated[['match_id', 'team_id', 'player_id']].drop_duplicates().shape[0]}")
    print(f"Missing-match coverage rows: {len(coverage)}")
    print(f"Zero-coded player-of-the-match rows: {len(zero_mom_output)}")
    print(f"Distinct extras combinations represented: {extras_combinations}")
    print(f"Extras rows included: {len(extras)}")
    print("All cited source rows matched their original CSV values.")
    print("Source CSV hashes unchanged.")
    print("Generated files:")
    for path in expected_outputs:
        print(f"  {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    run_investigation()
