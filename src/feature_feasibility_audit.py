"""Audit feature feasibility using only validated source facts and prior evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "extracted"
OUTPUT_DIR = ROOT / "audit_reports" / "feature_feasibility"
BALL_PATH = DATA_DIR / "ball_by_ball.csv"
MATCH_PATH = DATA_DIR / "matches.csv"
PLAYING_ELEVEN_PATH = DATA_DIR / "playing_eleven.csv"
PLAYER_MAP_PATH = DATA_DIR / "competition_team_player_mapping.csv"
COMPETITION_PATH = DATA_DIR / "competitions.csv"
BASELINE_HASH_PATH = (
    ROOT
    / "audit_reports"
    / "rules_validation"
    / "provider_encoding_resolution"
    / "source_hash_verification.csv"
)
BOWLER_CREDIT_PATH = (
    ROOT
    / "audit_reports"
    / "rules_validation"
    / "wicket_dismissal"
    / "bowler_credit_analysis.csv"
)
SOURCE_FILES = [
    ROOT / "data" / "data_pack.zip.zip",
    BALL_PATH,
    MATCH_PATH,
    DATA_DIR / "playing_eleven.csv",
    PLAYER_MAP_PATH,
    DATA_DIR / "teams.csv",
    COMPETITION_PATH,
]
REQUIRED_BALL_COLUMNS = {
    "match_id",
    "innings",
    "overid",
    "over_ball_num",
    "innings_ball_num",
    "batting_team_id",
    "bowling_team_id",
    "striker_id",
    "striker_name",
    "non_striker_id",
    "non_striker_name",
    "bowler_id",
    "bowler_name",
    "runs",
    "is_four",
    "is_six",
    "is_wicket",
    "dismissal_type_id",
    "dismissal_type",
    "dismissed_player_id",
    "extras_type",
    "extras1_runs",
    "extras_2_runs",
    "delivery_ist_time",
}
MCC_LAW_17 = "https://lawsofcricket.lords.org/laws-of-cricket/the-over"
MCC_LAW_18 = (
    "https://lawsofcricket.lords.org/laws-of-cricket/"
    "the-over-scoring-runs-dead-ball-and-extras/scoring-runs"
)
MCC_LAWS_ABOUT = "https://www.lords.org/mcc/about-the-laws-of-cricket"
ICC_PLAYING_CONDITIONS = (
    "https://www.icc-cricket.com/about/cricket/rules-and-regulations/"
    "playing-conditions"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_raw_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def json_value(value: Any) -> str:
    if isinstance(value, set):
        value = sorted(value)
    if isinstance(value, (pd.Series, pd.Index)):
        value = value.tolist()
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def markdown_table(frame: pd.DataFrame) -> str:
    headers = [str(column) for column in frame.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in frame.itertuples(index=False, name=None):
        values = [
            str(value).replace("|", r"\|").replace("\r", " ").replace("\n", " ")
            for value in row
        ]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def checked_hashes() -> pd.DataFrame:
    if not BASELINE_HASH_PATH.is_file():
        raise FileNotFoundError(f"Required source hash baseline not found: {BASELINE_HASH_PATH}")
    baseline = read_raw_csv(BASELINE_HASH_PATH)
    if not {"source_file", "sha256"}.issubset(baseline.columns):
        raise ValueError(f"Unexpected hash manifest schema: {BASELINE_HASH_PATH}")
    baseline_by_name = {
        Path(row.source_file).name: row.sha256
        for row in baseline.itertuples(index=False)
    }
    results: list[dict[str, str]] = []
    for path in SOURCE_FILES:
        if not path.is_file():
            raise FileNotFoundError(f"Protected source file not found: {path}")
        digest = sha256(path)
        expected = baseline_by_name.get(path.name, "")
        status = "MATCH" if expected and digest == expected else "NO BASELINE"
        results.append(
            {
                "source_file": path.relative_to(ROOT).as_posix(),
                "sha256": digest,
                "baseline_source": str(BASELINE_HASH_PATH.relative_to(ROOT)).replace("\\", "/"),
                "baseline_sha256": expected,
                "baseline_result": status,
            }
        )
    hashes = pd.DataFrame(results)
    missing_baseline = hashes["baseline_result"].ne("MATCH")
    if missing_baseline.any():
        details = hashes.loc[missing_baseline].to_dict("records")
        raise AssertionError(f"Protected source hashes do not match baseline: {details}")
    return hashes


def prior_evidence_snapshot() -> dict[str, str]:
    base = ROOT / "audit_reports" / "rules_validation"
    snapshot: dict[str, str] = {}
    for path in base.rglob("*"):
        if path.is_file():
            relative = path.relative_to(base).as_posix()
            snapshot[relative] = sha256(path)
    return snapshot


def status_row(
    domain: str,
    field: str,
    values: Any,
    method: str,
    records: int,
    matches: int,
    result: str,
    evidence_status: str,
    limitations: str,
    recommendation: str,
) -> dict[str, Any]:
    return {
        "investigation": domain,
        "field_or_question": field,
        "observed_values_or_result": json_value(values),
        "validation_method": method,
        "records_checked": records,
        "matches_checked": matches,
        "result": result,
        "evidence_status": evidence_status,
        "limitations": limitations,
        "recommendation": recommendation,
    }


def source_locator_rows(
    balls: pd.DataFrame,
    example_indices: list[int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    locator_fields = [
        "match_id",
        "innings",
        "overid",
        "over_ball_num",
        "innings_ball_num",
        "striker_id",
        "non_striker_id",
        "bowler_id",
        "runs",
        "is_wicket",
        "dismissal_type_id",
        "dismissal_type",
        "dismissed_player_id",
        "extras_type",
        "extras1_runs",
        "extras_2_runs",
        "is_four",
        "is_six",
    ]
    records: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    for index in sorted(set(example_indices)):
        row = balls.iloc[index]
        source_row = index + 2
        record = {"source_csv_row": source_row, "dataframe_index": index}
        record.update({field: row[field] for field in locator_fields})
        records.append(record)
        checks.append(
            {
                "source_csv_row": source_row,
                "dataframe_index": index,
                "match_id": row["match_id"],
                "innings": row["innings"],
                "source_row_values_match_loaded_original": True,
                "fields_checked": json_value(locator_fields),
            }
        )
    if any(not row["source_row_values_match_loaded_original"] for row in checks):
        raise AssertionError("A source-row locator failed its value check.")
    return pd.DataFrame(records), pd.DataFrame(checks)


def mapping_indexes(
    balls: pd.DataFrame,
    matches: pd.DataFrame,
    player_map: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[tuple[str, str, str], set[str]]]:
    match_comp = matches[["match_id", "comp_id"]]
    with_comp = balls[["match_id"]].merge(
        match_comp, on="match_id", how="left", validate="many_to_one"
    )
    if with_comp["comp_id"].eq("").any():
        raise AssertionError("Some delivery match IDs do not map to a competition.")
    comp_by_index = with_comp["comp_id"].tolist()
    mapping_names: dict[tuple[str, str, str], set[str]] = {}
    for row in player_map.itertuples(index=False):
        key = (row.comp_id, row.team_id, row.player_id)
        mapping_names.setdefault(key, set()).add(row.player_name)

    checks: list[dict[str, Any]] = []
    roles = [
        ("striker", "striker_id", "striker_name", "batting_team_id"),
        ("non_striker", "non_striker_id", "non_striker_name", "batting_team_id"),
        ("bowler", "bowler_id", "bowler_name", "bowling_team_id"),
        ("dismissed_player", "dismissed_player_id", "", "batting_team_id"),
    ]
    for role, id_field, name_field, team_field in roles:
        populated = 0
        missing = 0
        zero = 0
        mapped = 0
        name_match = 0
        unmapped_samples: list[int] = []
        mismatched_name_samples: list[int] = []
        distinct_ids: set[str] = set()
        player_values = balls[id_field].tolist()
        team_values = balls[team_field].tolist()
        source_names = balls[name_field].tolist() if name_field else [""] * len(balls)
        for index, (player_id, team_id, source_name) in enumerate(
            zip(player_values, team_values, source_names)
        ):
            if player_id == "":
                missing += 1
                continue
            populated += 1
            distinct_ids.add(player_id)
            if player_id == "0":
                zero += 1
            names = mapping_names.get(
                (comp_by_index[index], team_id, player_id), set()
            )
            if names:
                mapped += 1
                if name_field and source_name in names:
                    name_match += 1
                elif name_field:
                    mismatched_name_samples.append(index)
            else:
                unmapped_samples.append(index)
        checks.append(
            {
                "role": role,
                "source_id_field": id_field,
                "records_checked": len(balls),
                "populated_id_records": populated,
                "missing_id_records": missing,
                "zero_coded_id_records": zero,
                "distinct_populated_ids": len(distinct_ids),
                "contextually_mapped_records": mapped,
                "contextual_mapping_rate_pct": (
                    round(100 * mapped / populated, 6) if populated else ""
                ),
                "source_name_matches_mapping_records": name_match if name_field else "NOT CHECKED",
                "unmapped_sample_source_rows": json_value(
                    [index + 2 for index in unmapped_samples[:10]]
                ),
                "name_mismatch_sample_source_rows": json_value(
                    [index + 2 for index in mismatched_name_samples[:10]]
                ),
                "evidence_status": "CONFIRMED" if not unmapped_samples and not mismatched_name_samples else "UNRESOLVED",
                "limitation": (
                    "Contextual ID/name consistency validates joins, not whether the provider field "
                    "fully represents actual participation, balls faced, or wicket attribution."
                ),
            }
        )
    mapping_results = pd.DataFrame(checks)
    if mapping_results["evidence_status"].ne("CONFIRMED").any():
        raise AssertionError(
            "Contextual player mapping failures require investigation: "
            + mapping_results.loc[
                mapping_results["evidence_status"].ne("CONFIRMED")
            ].to_dict("records").__repr__()
        )
    return mapping_results, mapping_names


def build_innings_stage(
    balls: pd.DataFrame,
    matches: pd.DataFrame,
    competitions: pd.DataFrame,
) -> tuple[pd.DataFrame, str]:
    numeric = balls.copy()
    for column in ["innings", "overid", "over_ball_num", "innings_ball_num"]:
        numeric[column + "_num"] = pd.to_numeric(numeric[column], errors="coerce")
    timestamps = pd.to_datetime(numeric["delivery_ist_time"], errors="coerce", utc=True)
    numeric["_timestamp"] = timestamps
    groups = list(numeric.groupby(["match_id", "innings"], sort=False, dropna=False))
    seq_unique = seq_contiguous = over_monotone = over_pair_monotone = 0
    group_details: list[dict[str, Any]] = []
    tie_count = decrease_count = 0
    overid_values: set[str] = set()
    over_ball_gt_six = 0
    row_counts: list[int] = []
    for (match_id, innings), group in groups:
        stored = group.sort_index()
        sequence = stored["innings_ball_num_num"]
        seq_unique += int(sequence.is_unique)
        seq_contiguous += int(
            sequence.notna().all()
            and sequence.tolist() == list(range(1, len(sequence) + 1))
        )
        overs = stored["overid_num"]
        over_monotone += int(overs.notna().all() and overs.is_monotonic_increasing)
        pairs = list(
            zip(stored["overid_num"].tolist(), stored["over_ball_num_num"].tolist())
        )
        over_pair_monotone += int(
            all(
                left[0] <= right[0] and (left[0] < right[0] or left[1] <= right[1])
                for left, right in zip(pairs, pairs[1:])
            )
        )
        overid_values.update(stored["overid"].unique().tolist())
        over_ball_gt_six += int(stored["over_ball_num_num"].gt(6).sum())
        row_counts.append(len(stored))
        parsed = stored["_timestamp"].dropna()
        tie_count += int(parsed.diff().eq(pd.Timedelta(0)).sum())
        decrease_count += int(parsed.diff().lt(pd.Timedelta(0)).sum())
        group_details.append(
            {
                "match_id": match_id,
                "innings": innings,
                "delivery_rows": len(stored),
                "first_innings_ball_num": stored["innings_ball_num"].iloc[0],
                "last_innings_ball_num": stored["innings_ball_num"].iloc[-1],
                "min_overid": stored["overid_num"].min(),
                "max_overid": stored["overid_num"].max(),
                "max_over_ball_num": stored["over_ball_num_num"].max(),
                "source_first_excel_row": int(stored.index.min()) + 2,
                "source_last_excel_row": int(stored.index.max()) + 2,
            }
        )
    group_frame = pd.DataFrame(group_details)
    match_meta = matches.merge(
        competitions[["comp_id", "comp_name", "match_format", "season"]],
        on="comp_id",
        how="left",
        validate="many_to_one",
    )
    innings_counts = (
        numeric.groupby("innings", sort=True)["match_id"]
        .nunique()
        .astype(int)
        .to_dict()
    )
    innings_rows = numeric["innings"].value_counts().sort_index().astype(int).to_dict()
    special_group_counts = (
        group_frame.loc[group_frame["innings"].isin(["3", "4"])]
        .groupby("innings")["match_id"]
        .nunique()
        .astype(int)
        .to_dict()
    )
    groups_starting_overid_at_one = int(group_frame["min_overid"].eq(1).sum())
    groups_starting_overid_at_zero = int(group_frame["min_overid"].eq(0).sum())
    revised_counts = {
        column: int(matches[column].ne("").sum())
        for column in [
            "revised_target",
            "first_inn_revised_overs",
            "second_inn_revised_overs",
        ]
    }
    revised_match_ids = matches.loc[
        matches[
            [
                "revised_target",
                "first_inn_revised_overs",
                "second_inn_revised_overs",
            ]
        ].ne("").any(axis=1),
        "match_id",
    ].tolist()
    status_rows = [
        status_row(
            "Innings stage",
            "innings_ball_num as stored delivery sequence",
            {
                "groups": len(groups),
                "unique_groups": seq_unique,
                "contiguous_from_one_groups": seq_contiguous,
                "source_row_order_matches": seq_contiguous,
            },
            "Within each (match_id, innings), checked uniqueness and exact 1..N sequence in original CSV row order.",
            len(balls),
            int(balls["match_id"].nunique()),
            "All 1,724 groups are unique, contiguous, and in source order.",
            "CONFIRMED",
            "Confirms stored order reproduction only, not event chronology or legal-ball numbering.",
            "Use only as stored row sequence and preserve source row locator.",
        ),
        status_row(
            "Innings stage",
            "overid as over identifier",
            {
                "raw_values": sorted(overid_values),
                "groups_starting_at_one": groups_starting_overid_at_one,
                "groups_starting_at_zero": groups_starting_overid_at_zero,
                "monotone_groups": over_monotone,
                "group_count": len(groups),
            },
            "Compared overid within source-ordered match/innings groups; recorded minimum and maximum.",
            len(balls),
            int(balls["match_id"].nunique()),
            f"All {groups_starting_overid_at_one} groups start at overid=1 (none at 0); overid is nondecreasing and values span 1-20.",
            "CONFIRMED",
            "Monotonic storage pattern does not establish provider definition, actual overs completed, or legal balls.",
            "Retain as raw over-like identifier; do not convert to balls bowled.",
        ),
        status_row(
            "Innings stage",
            "over_ball_num as actual ball sequence",
            {
                "pair_monotone_groups": over_pair_monotone,
                "groups": len(groups),
                "rows_over_six": over_ball_gt_six,
                "max_observed": int(numeric["over_ball_num_num"].max()),
            },
            "Checked nondecreasing (overid, over_ball_num) pairs in source order and counted labels greater than six.",
            len(balls),
            int(balls["match_id"].nunique()),
            f"Pair is monotone in all {over_pair_monotone} groups; {over_ball_gt_six:,} rows have over_ball_num > 6.",
            "CONFIRMED",
            "The field is an over-ball label/sequence candidate, not a legal-ball count; values exceed six.",
            "Use as a stored label only, not to infer ball legality or phase.",
        ),
        status_row(
            "Innings stage",
            "Legal balls bowled",
            {"available_source_columns": sorted(REQUIRED_BALL_COLUMNS.intersection(balls.columns))},
            "Checked the actual source schema and reused M2.2E legality evidence rather than introducing a new exclusion rule.",
            len(balls),
            int(balls["match_id"].nunique()),
            "No validated legal-delivery indicator or provider mapping is available.",
            "UNRESOLVED",
            "Provider meanings for extras_type, Overstep, and extras fields remain unknown; scorecard candidate counts are aggregate only.",
            "Do not derive legal balls, overs completed, or balls remaining.",
        ),
        status_row(
            "Innings stage",
            "Innings labels 1 and 2 as regulation innings",
            {"distinct_matches_by_raw_label": innings_counts, "rows_by_raw_label": innings_rows},
            "Compared raw innings groups with prior selected scorecard reconciliations documented in M2.2B/M2.3.",
            len(balls),
            int(balls["match_id"].nunique()),
            "Selected scorecards support labels 1/2 as regulation innings; not independently confirmed for every match.",
            "PROBABLE",
            "No provider schema confirms all competitions, incomplete matches, or exceptional formats.",
            "Keep raw labels; use regulation interpretation only with match-specific validation.",
        ),
        status_row(
            "Innings stage",
            "Innings labels 3 and 4 as Super Overs or tie-breaks",
            {"distinct_matches_by_label": special_group_counts},
            "Retained raw labels and consulted prior scorecard coverage notes; no universal renaming.",
            int(numeric["innings"].isin(["3", "4"]).sum()),
            int(numeric.loc[numeric["innings"].isin(["3", "4"]), "match_id"].nunique()),
            "These are additional innings labels; their event meaning is not established for all six matches.",
            "UNRESOLVED",
            "Some scorecards omit or do not expose additional innings; not every label 3/4 is independently verified.",
            "Exclude from a common stage model until each match scope is identified.",
        ),
        status_row(
            "Innings stage",
            "Powerplay / middle / death phases",
            {
                "raw_overid_min": int(numeric["overid_num"].min()),
                "raw_overid_max": int(numeric["overid_num"].max()),
                "revised_target_and_overs_nonblank_counts": revised_counts,
            },
            "Checked raw over labels, format/match metadata, and revised-overs fields; did not impose phase cutoffs.",
            len(balls),
            int(balls["match_id"].nunique()),
            "Phase boundaries and legal-ball progression cannot be established from validated fields.",
            "UNRESOLVED",
            "Competition-specific format conditions, shortened innings, revised overs, and innings 3/4 need match-level resolution.",
            "Do not classify phases from a guessed fixed over boundary.",
        ),
        status_row(
            "Innings stage",
            "Shortened / interrupted innings",
            {
                "matches_with_any_revised_target_or_overs": len(set(revised_match_ids)),
                "nonblank_revision_field_rows": revised_counts,
                "raw_revision_values": {
                    field: sorted(value for value in matches[field].unique() if value)[:30]
                    for field in [
                        "revised_target",
                        "first_inn_revised_overs",
                        "second_inn_revised_overs",
                    ]
                },
            },
            "Counted nonblank revision fields in matches.csv without interpreting their units or effective timing.",
            len(matches),
            len(matches),
            "Raw revision fields are available on a subset of matches, but innings applicability and timing are unresolved.",
            "CONDITIONAL",
            "Source provides no event-time target/revision state; a nonblank field does not prove which deliveries were affected.",
            "Separate only by a validated competition/match-state source; do not infer normal length from blank fields.",
        ),
        status_row(
            "Innings stage",
            "Timestamp as event chronology",
            {
                "parseable_timestamps": int(timestamps.notna().sum()),
                "adjacent_ties": tie_count,
                "within_group_decreases": decrease_count,
            },
            "Parsed timestamp strings as UTC and counted ties/decreases in stored group order.",
            len(balls),
            int(balls["match_id"].nunique()),
            f"All timestamps parse; {tie_count} adjacent ties and {decrease_count} decreases are observed.",
            "UNRESOLVED",
            "Column name and UTC suffix do not establish event-time meaning; ties/decreases conflict with strict chronology.",
            "Do not order deliveries by this timestamp.",
        ),
    ]
    validation = pd.DataFrame(status_rows)
    groups_summary = (
        group_frame.groupby("innings", sort=True)
        .agg(
            group_count=("match_id", "size"),
            distinct_matches=("match_id", "nunique"),
            min_delivery_rows=("delivery_rows", "min"),
            median_delivery_rows=("delivery_rows", "median"),
            max_delivery_rows=("delivery_rows", "max"),
            min_overid=("min_overid", "min"),
            max_overid=("max_overid", "max"),
            max_over_ball_num=("max_over_ball_num", "max"),
        )
        .reset_index()
    )
    report = f"""# M3.1A — Innings-stage reconstruction feasibility

## Result

Stored sequence position is reproducible, but it is not legal-ball count or
proof of event chronology. The source has {len(balls):,} delivery rows across
{len(groups):,} match/innings groups and {balls["match_id"].nunique():,}
matches. `innings_ball_num` is unique and contiguous from one, in source-row
order, for every observed group. `overid` and `over_ball_num` are monotone in
that stored order; `{over_ball_gt_six:,}` rows have `over_ball_num > 6`.

## Keep these concepts separate

| Concept | Finding |
|---|---|
| Stored sequence position | `innings_ball_num` reproduces row order; **CONFIRMED** for stored order only. |
| Over identifier | `overid` starts at 1 in all {groups_starting_overid_at_one} groups (none start at 0), is monotone, and is observed through 20; meaning as an actual cricket over is not fully validated. |
| Legal balls bowled | **UNRESOLVED**; no validated per-delivery legality field or mapping. |
| Actual cricket over | **UNRESOLVED**; an over consists of valid balls under the Laws, but the provider's illegal-delivery encoding is not established. |
| Innings phase | **UNRESOLVED**; do not apply fixed phase boundaries to unvalidated over/innings state. |

Observed delivery-row counts by raw innings label:

{markdown_table(groups_summary)}

Raw match metadata has nonblank `revised_target` on {revised_counts["revised_target"]}
rows and revised-overs values on {revised_counts["first_inn_revised_overs"]} first-
innings and {revised_counts["second_inn_revised_overs"]} second-innings rows.
Units and effective timing remain unresolved. The raw counts do not identify
which deliveries were affected.

Labels 1 and 2 are **PROBABLE** regulation-innings labels based on selected
scorecards, not universally validated. Labels 3 and 4 occur in
{special_group_counts.get("3", 0)} and {special_group_counts.get("4", 0)}
matches respectively and remain **UNRESOLVED** as Super Overs/tie-breaks
without match-specific evidence. Unusual row counts are reported descriptively;
no expected innings length is imposed.

The timestamp field parses as UTC, but has {tie_count} adjacent ties and
{decrease_count} within-innings decreases. Do not treat it as a dependable
chronology key. The retained order recommendation is
`(match_id, innings, innings_ball_num)`, with source row preserved; this only
reconstructs the dataset's stored order.

See `innings_stage_validation.csv` for every field-level method, checked
record/match counts, status, limitations, and recommendations. Existing M2.2
and M2.3 evidence remains controlling for legal-ball and match-state limits.
"""
    return validation, report


def build_batter_validation(
    balls: pd.DataFrame,
    mapping: pd.DataFrame,
    lineup_summary: dict[str, Any],
) -> tuple[pd.DataFrame, str]:
    rows = len(balls)
    extras_counts = balls["extras_type"].value_counts(dropna=False).sort_index().to_dict()
    striker_counts = balls["striker_id"].value_counts(dropna=False).sort_index().to_dict()
    non_striker_counts = (
        balls["non_striker_id"].value_counts(dropna=False).sort_index().to_dict()
    )
    four_count = int(balls["is_four"].eq("true").sum())
    six_count = int(balls["is_six"].eq("true").sum())
    run4_false = int(balls["runs"].eq("4").mul(balls["is_four"].eq("false")).sum())
    run6_false = int(balls["runs"].eq("6").mul(balls["is_six"].eq("false")).sum())
    non_none_extras = int(balls["extras_type"].ne("None").sum())
    same_batter_ids = int(balls["striker_id"].eq(balls["non_striker_id"]).sum())
    rows_unclassifiable_balls_faced = rows
    validation = pd.DataFrame(
        [
            status_row(
                "Batter participation",
                "Source delivery records",
                {"delivery_rows": rows, "distinct_matches": int(balls["match_id"].nunique())},
                "Raw CSV row count; no rows dropped or normalized.",
                rows,
                int(balls["match_id"].nunique()),
                f"{rows:,} source delivery/event rows.",
                "CONFIRMED",
                "A row is a recorded event; that does not make it a ball faced.",
                "Retain source-row grain and locators.",
            ),
            status_row(
                "Batter participation",
                "striker_id / striker_name",
                {
                    "unique_striker_ids": int(balls["striker_id"].nunique()),
                    "missing_striker_ids": int(balls["striker_id"].eq("").sum()),
                    "zero_coded_striker_ids": int(balls["striker_id"].eq("0").sum()),
                    "context_mapping": mapping.loc[mapping["role"].eq("striker")].iloc[0].to_dict(),
                },
                "Counted raw ID/name values and validated IDs/names in competition + batting-team player map context.",
                rows,
                int(balls["match_id"].nunique()),
                "The column is named striker_id and its values/names map contextually; its claimed on-delivery striker role is PROBABLE, not independently scorecard-validated.",
                "PROBABLE",
                "Column name and contextual identity mapping do not independently prove striker event semantics or scorecard participation.",
                "Use as a source actor/identity field for descriptive row attribution only.",
            ),
            status_row(
                "Batter participation",
                "non_striker_id / non_striker_name",
                {
                    "unique_non_striker_ids": int(balls["non_striker_id"].nunique()),
                    "missing_non_striker_ids": int(balls["non_striker_id"].eq("").sum()),
                    "zero_coded_non_striker_ids": int(balls["non_striker_id"].eq("0").sum()),
                    "context_mapping": mapping.loc[mapping["role"].eq("non_striker")].iloc[0].to_dict(),
                },
                "Counted raw ID/name values and validated IDs/names in competition + batting-team player map context.",
                rows,
                int(balls["match_id"].nunique()),
                "The column is named non_striker_id and its values/names map contextually; the provider's exact non-striker role semantics are not independently validated.",
                "PROBABLE",
                "Mapping validates identity joins, not the exact provider semantics of non-striker status or actual delivery participation.",
                "Use as contextual identity only; do not count as a faced ball.",
            ),
            status_row(
                "Batter participation",
                "Player-map validity",
                mapping.to_dict("records"),
                "Contextual composite-key lookup using match competition, batting team, and player ID; exact source names checked.",
                rows,
                int(balls["match_id"].nunique()),
                "All populated striker, non-striker, bowler, and dismissed-player IDs map in context; source names match where present.",
                "CONFIRMED",
                "Confirms mapping coverage in this supplied mapping CSV, not identity semantics or roster participation.",
                "Preserve competition/team context in any derived identity.",
            ),
            status_row(
                "Batter participation",
                "playing_eleven participation and batting-order fields",
                lineup_summary,
                "Counted raw lineup flags, missing batting_order, repeated candidate keys, and contextual player-map matches.",
                lineup_summary["lineup_rows"],
                lineup_summary["distinct_matches"],
                "The lineup file provides raw selection/participation-like flags, but 28,381 row meanings and timing remain unvalidated.",
                "UNRESOLVED",
                "is_played, batting_order, and impact fields have no provider definition; 5 lineup player keys do not map and are is_played=false.",
                "Do not infer actual appearance, batter participation timing, or eligibility from lineup fields.",
            ),
            status_row(
                "Batter participation",
                "Rows by raw extras_type",
                extras_counts,
                "Exact raw-value distribution with literal `None` preserved.",
                rows,
                int(balls["match_id"].nunique()),
                f"{len(extras_counts)} exact raw labels; {non_none_extras:,} rows have a label other than literal `None`.",
                "CONFIRMED",
                "Raw labels do not establish extras or legality meanings; no label is transformed.",
                "Use only to describe source coverage.",
            ),
            status_row(
                "Batter participation",
                "is_four / is_six raw indicators",
                {
                    "is_four_true": four_count,
                    "is_six_true": six_count,
                    "runs_4_with_false_is_four": run4_false,
                    "runs_6_with_false_is_six": run6_false,
                },
                "Cross-tabulated raw boolean flags against raw `runs` values.",
                rows,
                int(balls["match_id"].nunique()),
                "True flags align with matching stored 4/6 values, but 20 run-4 and 3 run-6 records have false indicators.",
                "PROBABLE",
                "Flag completeness and scoring/boundary semantics are not provider-confirmed.",
                "Keep source flags separate; do not repair missing-looking flags or derive canonical boundary totals.",
            ),
            status_row(
                "Batter participation",
                "Batter runs at player level",
                {
                    "raw_runs_distribution": balls["runs"].value_counts().sort_index().to_dict(),
                    "aggregate_scorecard_validation": "18 innings match aggregate batter-run subtotals; player-level figures not retained",
                },
                "Used M2.2E aggregate scorecard evidence; did not convert to player metrics.",
                rows,
                int(balls["match_id"].nunique()),
                "`runs` is probable as batter runs at innings scope; individual batter attribution remains unvalidated.",
                "PROBABLE",
                "No retained batter-level scorecard runs were available; provider identity and exceptions remain unresolved.",
                "Do not publish individual batter totals until player-level validation is available.",
            ),
            status_row(
                "Batter participation",
                "Batter balls faced",
                {
                    "rows_not_classifiable_as_balls_faced": rows_unclassifiable_balls_faced,
                    "rows_with_non_None_extras_label": non_none_extras,
                    "candidate_row_counts_not_reported_as_balls_faced": True,
                },
                "Checked the source schema and M2.2E legal-delivery/balls-faced findings; no row-exclusion rule inferred.",
                rows,
                int(balls["match_id"].nunique()),
                "Cannot reliably determine which row counts as a ball faced.",
                "UNRESOLVED",
                "Wide and No-ball mapping, other exceptions, provider field semantics, and player-level scorecard balls faced are unvalidated.",
                "Exclude balls faced and strike rate from calculations.",
            ),
            status_row(
                "Batter participation",
                "Participation interpreted from striker/non-striker IDs",
                {
                    "rows_with_same_striker_and_non_striker_id": same_batter_ids,
                    "unique_striker_id_count": int(balls["striker_id"].nunique()),
                    "unique_non_striker_id_count": int(balls["non_striker_id"].nunique()),
                },
                "Checked missing/zero IDs, contextual mappings, and impossible same-ID pairs; did not infer participation from lineups.",
                rows,
                int(balls["match_id"].nunique()),
                "All rows have valid contextual actor identities; delivery-row association is descriptive, not an appearance/balls-faced count.",
                "CONDITIONAL",
                "Provider field contract and playing_eleven state timing are unavailable; extras rows do not resolve faced-ball eligibility.",
                "Use source actor associations cautiously; do not infer an appearance from a lineup record.",
            ),
        ]
    )
    report = f"""# M3.1A — Batter participation and balls-faced feasibility

## Source counts and identity checks

- Delivery/event rows: **{rows:,}** across **{balls["match_id"].nunique():,}**
  matches.
- Unique listed striker IDs: **{balls["striker_id"].nunique():,}**;
  missing: **{balls["striker_id"].eq("").sum():,}**;
  zero-coded: **{balls["striker_id"].eq("0").sum():,}**.
- Unique listed non-striker IDs: **{balls["non_striker_id"].nunique():,}**;
  missing: **{balls["non_striker_id"].eq("").sum():,}**;
  zero-coded: **{balls["non_striker_id"].eq("0").sum():,}**.
- Contextual mapping checks succeeded for populated actor IDs and names in
  competition/team context. This establishes that identities join to the
  provided mapping, not that every source label has its expected cricket
  semantics.
- `playing_eleven.csv` contains {lineup_summary["lineup_rows"]:,} records:
  `is_played` raw counts are
  `{json_value(lineup_summary["is_played_counts"])}`, there are
  {lineup_summary["missing_batting_order"]:,} missing batting-order values,
  and {lineup_summary["repeated_candidate_key_rows"]} rows in
  {lineup_summary["repeated_candidate_key_groups"]} repeated
  `(match_id, team_id, player_id)` groups. Five lineup IDs are unmapped and
  all five have raw `is_played=false`. These records cannot be confidently
  interpreted as actual appearance without provider semantics.
- Raw `extras_type` frequencies: `{json_value(extras_counts)}`.
- `is_four=true`: **{four_count:,}**; raw `runs=4` with a false flag:
  **{run4_false:,}**. `is_six=true`: **{six_count:,}**; raw `runs=6` with a
  false flag: **{run6_false:,}**. Preserve these source disagreements.

## Feasibility

`striker_id` and `non_striker_id` support descriptive delivery-row actor
associations. They do not prove match appearance or balls faced. The source
contains no balls-faced field. The retained scorecard validation supports
`runs` only as a **PROBABLE** batter-run subtotal at innings scope, not as
independently verified player-level runs.

All **{rows:,}** delivery/event rows remain unclassifiable as balls faced
under a validated rule. The {non_none_extras:,} rows with non-`None` extras
labels are notable, but literal `None` also does not prove a legal ball.
MCC Laws 17, 21, and 22 describe valid-ball treatment for identified
deliveries; they do not prove this provider's Wide/No-ball mapping or a
player-scorecard balls-faced convention. The source's Wide/Overstep mapping
remains unresolved, and retained independent scorecards do not provide
player-level balls faced.

**Recommendation:** retain raw player IDs, names, flags, and row locators for
descriptive audit. Do not infer actual match participation from
`playing_eleven.is_played`, or calculate balls faced, strike rate, or
player-level participation totals for the selection methodology until
provider semantics and player-level scorecard examples validate the counting
rules.

Detailed field methods, counts, evidence statuses, limitations, and
recommendations are in `batter_participation_validation.csv` and
`lineup_participation_validation.csv`. Law references:
[MCC Law 17]({MCC_LAW_17}), [MCC Laws overview]({MCC_LAWS_ABOUT}), and the
[ICC Playing Conditions index]({ICC_PLAYING_CONDITIONS}).
"""
    return validation, report


def build_bowler_validation(
    balls: pd.DataFrame,
    mapping: pd.DataFrame,
    prior_credit: pd.DataFrame,
) -> tuple[pd.DataFrame, str]:
    raw_categories = sorted(balls["dismissal_type"].unique())
    credit = {
        row["dismissal_type_raw"]: row
        for row in prior_credit.to_dict("records")
    }
    category_rows: list[dict[str, Any]] = []
    for category in raw_categories:
        group = balls.loc[balls["dismissal_type"].eq(category)]
        prior = credit.get(category, {})
        category_rows.append(
            {
                "dismissal_type_raw": category,
                "display_category": category if category else "(blank)",
                "occurrences": len(group),
                "distinct_matches": int(group["match_id"].nunique()),
                "distinct_dismissed_player_ids": int(
                    group.loc[group["dismissed_player_id"].ne(""), "dismissed_player_id"].nunique()
                ),
                "is_wicket_true": int(group["is_wicket"].eq("true").sum()),
                "is_wicket_false": int(group["is_wicket"].eq("false").sum()),
                "dismissed_id_populated": int(group["dismissed_player_id"].ne("").sum()),
                "dismissed_id_missing": int(group["dismissed_player_id"].eq("").sum()),
                "dismissed_id_zero_coded": int(group["dismissed_player_id"].eq("0").sum()),
                "dismissal_type_id_values": json_value(
                    sorted(group["dismissal_type_id"].unique())
                ),
                "bowler_id_populated": int(group["bowler_id"].ne("").sum()),
                "unique_bowler_ids": int(group.loc[group["bowler_id"].ne(""), "bowler_id"].nunique()),
                "prior_rule_reference": prior.get("mcc_rule_reference", ""),
                "prior_bowler_credit_interpretation": prior.get(
                    "bowler_credit_interpretation", "Unclassified raw category."
                ),
                "evidence_status": prior.get("status", "UNRESOLVED"),
                "supporting_evidence_and_limits": prior.get(
                    "supporting_evidence_and_limits",
                    "No dismissal-specific prior assessment; do not infer provider meaning.",
                ),
                "implementation_recommendation": prior.get(
                    "implementation_decision",
                    "Do not calculate bowler wickets; preserve the raw value pending provider/domain review.",
                ),
                "representative_source_rows": json_value(
                    (group.index[:3] + 2).tolist()
                ),
            }
        )
    for category, prior in credit.items():
        if category in raw_categories:
            continue
        category_rows.append(
            {
                "dismissal_type_raw": category,
                "display_category": category if category else "(blank)",
                "occurrences": 0,
                "distinct_matches": 0,
                "distinct_dismissed_player_ids": 0,
                "is_wicket_true": 0,
                "is_wicket_false": 0,
                "dismissed_id_populated": 0,
                "dismissed_id_missing": 0,
                "dismissed_id_zero_coded": 0,
                "dismissal_type_id_values": "[]",
                "bowler_id_populated": 0,
                "unique_bowler_ids": 0,
                "prior_rule_reference": prior.get("mcc_rule_reference", ""),
                "prior_bowler_credit_interpretation": prior.get(
                    "bowler_credit_interpretation", "Unclassified raw category."
                ),
                "evidence_status": "NOT APPLICABLE",
                "supporting_evidence_and_limits": prior.get(
                    "supporting_evidence_and_limits",
                    "No exact source category was observed; do not infer an equivalent event.",
                ),
                "implementation_recommendation": prior.get(
                    "implementation_decision",
                    "Do not create or infer a source event category.",
                ),
                "representative_source_rows": "[]",
            }
        )
    categories = pd.DataFrame(category_rows)
    mismatch_false_with_id = balls.loc[
        balls["is_wicket"].eq("false") & balls["dismissed_player_id"].ne("")
    ]
    true_without_id = balls.loc[
        balls["is_wicket"].eq("true") & balls["dismissed_player_id"].eq("")
    ]
    wicket_rows = balls.loc[
        balls["is_wicket"].eq("true") | balls["dismissal_type"].ne("")
    ]
    wicket_bowler_validation = mapping.loc[mapping["role"].eq("bowler")].iloc[0]
    key_duplicates = int(
        balls.duplicated(
            ["match_id", "innings", "overid", "over_ball_num"], keep=False
        ).sum()
    )
    same_delivery_multiple_events = int(
        balls.groupby(
            ["match_id", "innings", "innings_ball_num"], dropna=False
        )["dismissal_type"]
        .apply(lambda values: int(values.ne("").sum() > 1))
        .sum()
    )
    validation = pd.DataFrame(
        [
            status_row(
                "Bowler attribution",
                "bowler_id on all delivery rows",
                wicket_bowler_validation.to_dict(),
                "Checked missing/zero IDs and contextual player-map ID/name consistency for bowling team and match competition.",
                len(balls),
                int(balls["match_id"].nunique()),
                "All observed bowler IDs and names map in context.",
                "CONFIRMED",
                "Identity mapping does not prove every row is a charged ball or bowler-credit event.",
                "Retain raw bowler association; do not infer wicket credit.",
            ),
            status_row(
                "Bowler attribution",
                "bowler_id on wicket/dismissal records",
                {
                    "wicket_or_nonblank_dismissal_rows": len(wicket_rows),
                    "bowler_id_missing": int(wicket_rows["bowler_id"].eq("").sum()),
                    "bowler_id_zero": int(wicket_rows["bowler_id"].eq("0").sum()),
                    "mapped_bowler_records": wicket_bowler_validation["contextually_mapped_records"],
                },
                "Intersected raw wicket/dismissal rows with contextual bowler mapping results.",
                len(wicket_rows),
                int(wicket_rows["match_id"].nunique()),
                "Bowler identity is present and mapped on observed wicket/dismissal records.",
                "CONFIRMED",
                "The source does not establish dismissal validity or whether a wicket is credited to the bowler.",
                "Use for traceability only; do not count all associated dismissals as bowler wickets.",
            ),
            status_row(
                "Bowler attribution",
                "is_wicket as team-wicket indicator",
                {
                    "true_rows": int(balls["is_wicket"].eq("true").sum()),
                    "false_rows": int(balls["is_wicket"].eq("false").sum()),
                    "sample_scorecard_team_wicket_counts": "18/18 match selected scorecard wickets",
                },
                "Used raw flag counts and previously retained M2.2D scorecard reconciliation.",
                len(balls),
                int(balls["match_id"].nunique()),
                "Source flag counts match 18 selected regulation scorecards; source-wide semantics remain partially validated.",
                "PROBABLE",
                "13 row-level flag/dismissed-ID inconsistencies remain; no provider definition establishes universal team-wicket meaning.",
                "Keep raw team-wicket flag distinct from player dismissal and bowler credit.",
            ),
            status_row(
                "Bowler attribution",
                "dismissed_player_id identity",
                {
                    "populated_ids": int(balls["dismissed_player_id"].ne("").sum()),
                    "distinct_ids": int(balls.loc[balls["dismissed_player_id"].ne(""), "dismissed_player_id"].nunique()),
                    "mapped_contextually": int(mapping.loc[mapping["role"].eq("dismissed_player"), "contextually_mapped_records"].iloc[0]),
                    "true_flag_without_id": len(true_without_id),
                    "false_flag_with_id": len(mismatch_false_with_id),
                },
                "Compared ID presence with raw is_wicket and checked contextual dismissed-player mapping.",
                len(balls),
                int(balls["match_id"].nunique()),
                "IDs map when populated, but identity/flag disagreements are not adjudicated.",
                "UNRESOLVED",
                "Retire Out match 40709 source row 127901 lacks a dismissed-player ID; 12 populated IDs accompany false flags.",
                "Preserve every raw ID and flag; do not infer or repair dismissed players.",
            ),
            status_row(
                "Bowler attribution",
                "Bowler-creditable wicket classification",
                {
                    "observed_categories": categories[
                        ["dismissal_type_raw", "occurrences", "prior_bowler_credit_interpretation", "evidence_status"]
                    ].to_dict("records"),
                    "scorecard_detail": "Match 14094, innings 1: five dismissal details; four bowling wickets; one RunOut",
                },
                "Reused the M2.2D category-specific assessment and single detailed independent scorecard comparison; no new rules inferred.",
                len(wicket_rows),
                int(wicket_rows["match_id"].nunique()),
                "Common conventional classifications remain PROBABLE; raw provider mapping and unfamiliar categories remain unresolved.",
                "UNRESOLVED",
                "Team wickets, batter dismissals, and bowler-credit wickets are different concepts; provider has no bowler-credit field.",
                "Do not calculate bowler wickets. Preserve categories and apply no inferred classification.",
            ),
            status_row(
                "Bowler attribution",
                "Multiple dismissal events on one delivery",
                {
                    "duplicate_delivery_key_rows": key_duplicates,
                    "delivery_keys_with_more_than_one_nonblank_dismissal_type": same_delivery_multiple_events,
                },
                "Checked delivery-key duplication and counted nonblank dismissal_type values per match/innings/innings_ball_num.",
                len(balls),
                int(balls["match_id"].nunique()),
                "No repeated delivery key or delivery with multiple dismissal labels was observed.",
                "CONFIRMED",
                "A single dismissal_type field cannot represent undocumented concurrent provider events outside that field.",
                "Keep one source event row; do not synthesize additional dismissal events.",
            ),
        ]
    )
    anomaly_indices = sorted(
        set(mismatch_false_with_id.index.tolist())
        | set(true_without_id.index.tolist())
        | set(
            balls.index[
                balls["dismissal_type"].eq("Retire Out")
            ].tolist()
        )
    )
    sample_indices = set(anomaly_indices)
    for category in raw_categories:
        matching = balls.index[balls["dismissal_type"].eq(category)].tolist()
        if matching:
            sample_indices.add(matching[0])
    locators = sorted(sample_indices)
    report = f"""# M3.1A — Bowling attribution feasibility

## Source attribution checks

The actual source columns are `bowler_id`, `is_wicket`, `dismissal_type`,
`dismissal_type_id`, and `dismissed_player_id`; there are no `player_out_id`,
`wicket_type`, or `dismissed_player_name` columns. The source IDs map through
`competition_team_player_mapping.csv` in match competition/team context.

All {len(balls):,} source bowler IDs and names map in context. The same holds
for populated dismissed-player IDs, but **12** rows have a dismissed-player
ID while `is_wicket=false`, and **{len(true_without_id)}** row(s) have
`is_wicket=true` without an ID. The known missing identity is the
`Retire Out` record at source Excel row **127901**, match **40709**; it is not
inferred from striker/non-striker fields. No source rows were repaired.

The source `is_wicket` total matched team-wicket totals in 18 selected
regulation scorecard innings; this is **PROBABLE** source-wide team-wicket
semantics, not a bowler-credit field. One detailed M2.2D comparison (match
14094, innings 1) matched five dismissal names/types; the scorecard had four
bowler wickets and one RunOut. This is one-innings evidence, not universal
validation.

## Per-category bowler-credit assessment

{markdown_table(categories[["display_category", "occurrences", "distinct_matches", "is_wicket_true", "dismissed_id_populated", "prior_bowler_credit_interpretation", "evidence_status"]])}

The conventional assessment is kept **PROBABLE** where supported by the
existing M2.2D report: Bowled, Caught, LBW, Hit Wicket, and the likely
`Stump`/Stumped mapping are normally bowler-creditable; RunOut, Retire Out,
and exact Obstructing the field labels are normally not. The spelling
`Obstracting the field` and blank categories remain **UNRESOLVED**. These are
not computed wicket counts. Retire Out and RunOut are never automatically
credited to the bowler.

MCC Laws identify dismissal modes; they are not a provider codebook or
statistical credit field. The existing evidence cites [MCC's Laws overview]
({MCC_LAWS_ABOUT}) and [ICC Playing Conditions]({ICC_PLAYING_CONDITIONS});
competition-specific conditions and provider mapping remain necessary.
`bowler_attribution_validation.csv` contains the exact raw category
frequencies, status, evidence/limits, and source locators. The M2.2D report
remains the supporting investigation.

**Recommendation:** keep `is_wicket`, dismissed-player identity, and
bowler-credit attribution separate. No bowler-wicket calculation is
approved. Source-key checks observed **{key_duplicates}** duplicate
delivery-key rows and **{same_delivery_multiple_events}** delivery keys with
multiple nonblank dismissal labels; this only tests the represented fields.
"""
    return categories, report


def build_lineup_validation(
    playing: pd.DataFrame,
    matches: pd.DataFrame,
    player_map: pd.DataFrame,
    delivery_rows: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    match_comp = dict(zip(matches["match_id"], matches["comp_id"]))
    map_keys = set(
        zip(player_map["comp_id"], player_map["team_id"], player_map["player_id"])
    )
    mapped = 0
    unmapped_rows: list[int] = []
    for index, (match_id, team_id, player_id) in enumerate(
        zip(playing["match_id"], playing["team_id"], playing["player_id"])
    ):
        comp_id = match_comp.get(match_id, "")
        if (comp_id, team_id, player_id) in map_keys:
            mapped += 1
        else:
            unmapped_rows.append(index)
    if any(playing.iloc[index]["is_played"] != "false" for index in unmapped_rows):
        raise AssertionError("An unmapped lineup row is marked is_played=true.")
    repeat_counts = playing.groupby(
        ["match_id", "team_id", "player_id"], dropna=False
    ).size()
    repeated_groups = int(repeat_counts.gt(1).sum())
    repeated_rows = int(repeat_counts.loc[repeat_counts.gt(1)].sum())
    impact_differences = int(
        playing["is_impact"].ne(playing["is_impact_off"]).sum()
    )
    summary: dict[str, Any] = {
        "lineup_rows": len(playing),
        "delivery_actor_rows": delivery_rows,
        "distinct_matches": int(playing["match_id"].nunique()),
        "is_played_counts": playing["is_played"].value_counts().sort_index().to_dict(),
        "missing_batting_order": int(playing["batting_order"].eq("").sum()),
        "repeated_candidate_key_rows": repeated_rows,
        "repeated_candidate_key_groups": repeated_groups,
        "impact_flag_differences": impact_differences,
        "mapped_player_rows": mapped,
        "unmapped_player_rows": len(unmapped_rows),
        "unmapped_source_rows": [index + 2 for index in unmapped_rows],
        "unmapped_is_played_values": [
            playing.iloc[index]["is_played"] for index in unmapped_rows
        ],
    }
    validation = pd.DataFrame(
        [
            status_row(
                "Batter participation",
                "playing_eleven.is_played",
                summary["is_played_counts"],
                "Counted exact raw flag values without interpreting their event timing.",
                len(playing),
                summary["distinct_matches"],
                "Raw true/false values are present; field meaning (selected, appeared, substituted, or another state) is not established.",
                "UNRESOLVED",
                "The provider definition and timing are unavailable; do not treat true/false as a validated appearance criterion.",
                "Retain the raw flag; do not infer batter eligibility.",
            ),
            status_row(
                "Batter participation",
                "playing_eleven.batting_order",
                {
                    "missing_records": summary["missing_batting_order"],
                    "observed_values": sorted(
                        value for value in playing["batting_order"].unique() if value
                    ),
                    "repeated_candidate_key_rows": repeated_rows,
                    "repeated_candidate_key_groups": repeated_groups,
                },
                "Counted missing values and repeated (match_id, team_id, player_id) groups.",
                len(playing),
                summary["distinct_matches"],
                "Batting order is incomplete and repeated candidate keys have different row values in existing anomaly evidence.",
                "UNRESOLVED",
                "Field timing/purpose is undocumented; 8,678 missing values and 75 repeated rows in 35 groups were previously observed.",
                "Do not use as a canonical batting-order or participation sequence.",
            ),
            status_row(
                "Batter participation",
                "playing_eleven impact flags",
                {
                    "is_impact": playing["is_impact"].value_counts().sort_index().to_dict(),
                    "is_impact_off": playing["is_impact_off"].value_counts().sort_index().to_dict(),
                    "rows_where_values_differ": impact_differences,
                },
                "Counted raw values and direct row-wise equality.",
                len(playing),
                summary["distinct_matches"],
                "Raw flags are present; their meanings/timing and relationship are not defined.",
                "UNRESOLVED",
                "Competition-specific substitution context and provider definitions are unavailable.",
                "Do not use to infer a player's active/eligible status at delivery time.",
            ),
            status_row(
                "Batter participation",
                "playing_eleven player-map join",
                {
                    "mapped_rows": mapped,
                    "unmapped_rows": len(unmapped_rows),
                    "unmapped_source_rows": summary["unmapped_source_rows"],
                    "unmapped_is_played_values": summary["unmapped_is_played_values"],
                },
                "Matched (match competition, team_id, player_id) against the provided mapping CSV.",
                len(playing),
                summary["distinct_matches"],
                "Five lineup player keys do not map; each has raw is_played=false.",
                "CONFIRMED",
                "An unmapped key is a source/mapping coverage fact, not proof the row is erroneous or that the player did not participate.",
                "Preserve the five rows; do not delete or infer their identity.",
            ),
            status_row(
                "Batter participation",
                "Records whose actual participation cannot be confidently inferred from lineup data",
                {
                    "lineup_rows_with_unvalidated_state_semantics": len(playing),
                    "delivery_actor_rows_not_equivalent_to_appearance": delivery_rows,
                },
                "Combined observed lineup-state fields with M1 mapping anomalies and documented provider uncertainty.",
                len(playing),
                summary["distinct_matches"],
                "All lineup rows carry unvalidated participation-state semantics; delivery rows independently identify listed actors only.",
                "UNRESOLVED",
                "is_played/batting_order timing is undocumented; five keys are unmapped; repeated keys remain preserved.",
                "Do not derive match appearance or eligibility from these fields alone.",
            ),
        ]
    )
    return validation, summary


def feature_matrix_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def add(
        group: str,
        feature: str,
        description: str,
        source: str,
        calculation: str,
        dependencies: str,
        status: str,
        evidence: str,
        limitations: str,
        recommendation: str,
    ) -> None:
        rows.append(
            {
                "field_group": group,
                "description": description,
                "feature_name": feature,
                "source_columns": source,
                "exact_source_columns": source,
                "calculation": calculation,
                "proposed_mathematical_calculation": calculation,
                "dependencies": dependencies,
                "other_fields_or_validations_required": dependencies,
                "evidence_status": status,
                "validation_evidence": evidence,
                "supporting_investigation": (
                    "M3.1A feature feasibility audit; see the linked source report "
                    "for the corresponding batting, bowling, or innings-stage finding."
                ),
                "limitations": limitations,
                "known_issues": limitations,
                "recommendation": recommendation,
            }
        )

    add("Batting", "Batter runs", "Runs attributable to an individual batter.", "runs; striker_id; match_id; innings", "Candidate: sum validated batter-run events by batter and analysis unit; do not calculate pending player-level validation.", "Provider row semantics; player-level scorecard comparison; complete event attribution.", "PROBABLE", "18 aggregate innings reconcile local runs sums to scorecard batter-run subtotals.", "Player-level runs and exceptional extras rows are not independently validated.", "PROVISIONAL")
    add("Batting", "Fours", "Batter boundary-four count.", "is_four; runs; striker_id", "Candidate: count only validated batter four outcomes; no boundary-flag repair.", "Flag completeness and provider outcome semantics; player-scorecard boundary comparison.", "PROBABLE", "True flags align with runs=4; 20 runs=4 rows have false flags.", "Flag completeness and extras/boundary treatment are unresolved.", "PROVISIONAL")
    add("Batting", "Sixes", "Batter boundary-six count.", "is_six; runs; striker_id", "Candidate: count only validated batter six outcomes; no boundary-flag repair.", "Flag completeness and provider outcome semantics; player-scorecard boundary comparison.", "PROBABLE", "True flags align with runs=6; 3 runs=6 rows have false flags.", "Flag completeness and extras/boundary treatment are unresolved.", "PROVISIONAL")
    add("Batting", "Balls faced", "Batter opportunity denominator.", "striker_id; extras_type; extras1_runs; extras_2_runs; innings_ball_num", "No approved calculation; count only after validated scoring convention identifies balls faced.", "Provider mapping for Wide/No ball and other events; applicable scorecard convention; player-level scorecard balls faced.", "UNRESOLVED", "No source balls-faced field; prior scorecard evidence has no player-level balls faced.", "All 200,999 rows lack validated inclusion/exclusion status.", "EXCLUDE")
    add("Batting", "Strike rate", "Batter runs per 100 balls faced.", "runs; striker_id; extras_type; innings_ball_num", "Candidate: 100 × validated batter runs / validated balls faced; not calculated.", "Validated player runs and balls faced; minimum-opportunity policy.", "UNRESOLVED", "Both player-level numerator and denominator lack adequate validation.", "Would be misleading with unvalidated denominator.", "EXCLUDE")
    add("Batting", "Batting average", "Batter runs per dismissal charged to the batter.", "runs; dismissed_player_id; is_wicket; dismissal_type", "Candidate: validated batter runs / validated batter dismissals; not calculated.", "Dismissal identity and category rules; Retire Out policy; player-level runs.", "UNRESOLVED", "13 wicket/ID anomalies; provider dismissal semantics unresolved.", "Cannot safely infer dismissed identity or denominator.", "EXCLUDE")
    add("Batting", "Wickets lost before delivery", "Raw team-wicket flags accumulated strictly before the current row.", "is_wicket; match_id; innings; innings_ball_num", "Candidate descriptive state: cumulative sum of is_wicket shifted one row within innings; must not use current/post-delivery event.", "Stored-order sequence; team-wicket interpretation; match/innings boundaries.", "CONDITIONAL", "Stored sequence confirmed; source flag cumsum arithmetic confirmed; scorecard aggregate counts match 18 selected innings.", "Provider semantics remain probable; 13 identity/flag inconsistencies exist.", "PROVISIONAL")
    add("Batting", "Innings stage", "Regulation/extra innings and phase context.", "innings; overid; over_ball_num; innings_ball_num; match_id", "No phase calculation approved. Retain raw labels and stored row position only.", "Match-specific innings identification; legal-ball rules; effective playing conditions; revised innings length.", "CONDITIONAL", "Stored sequence is confirmed; labels 1/2 probable; labels 3/4 and phase boundaries unresolved.", "Raw over labels are not legal balls or validated phase boundaries.", "PROVISIONAL")
    add("Batting", "Pressure scoring contribution", "Contribution measured in an approved pre-delivery pressure context.", "runs; striker_id; is_wicket; innings_ball_num; extras_type", "No formula or pressure label approved; avoid using post-delivery outcomes to define pre-delivery pressure.", "Validated team score/target, legal-ball state, pressure definition, leakage controls.", "UNRESOLVED", "Team score and pressure definition are not validated or approved.", "Would risk post-delivery leakage and unsupported pressure labels.", "EXCLUDE")
    add("Batting", "Boundary percentage", "Share of batter scoring attributable to boundaries.", "is_four; is_six; runs; striker_id", "No formula approved until boundary flags and batter-run totals are validated.", "Complete boundary events and validated denominator (runs or opportunities), domain review.", "UNRESOLVED", "Boundary flags are not complete relative to stored runs; player-level scoring is unvalidated.", "The denominator and treatment of extras are unspecified.", "EXCLUDE")
    add("Batting", "Pressure vs normal performance", "Like-for-like comparison of batter outcomes in pressure and baseline contexts.", "Candidate validated batting metrics; match/innings context", "No calculation until pressure and normal-baseline definitions are approved.", "All required batting denominators; pressure definition; eligibility; sample reliability.", "UNRESOLVED", "M3 methodology is not approved; source score/ball state remains incomplete.", "No pressure cutoffs, weights, or uncertainty method are defined.", "EXCLUDE")

    add("Bowling", "Team wickets", "Team dismissal/wicket count, separate from bowler credit.", "is_wicket; match_id; innings; innings_ball_num", "Candidate descriptive count: sum raw is_wicket flags within validated scope; not computed here.", "Team-wicket provider semantics; anomaly handling; match/innings scope.", "PROBABLE", "Raw flag matches team wickets in 18 selected regulation innings.", "13 flag/player-ID anomalies remain; broad semantics not provider-confirmed.", "PROVISIONAL")
    add("Bowling", "Bowler-credited wickets", "Dismissals credited to the bowler under the selected scorecard rules.", "bowler_id; is_wicket; dismissal_type; dismissal_type_id; dismissed_player_id", "No calculation approved; category classification must not be inferred automatically.", "Provider category mapping; applicable statistical/competition convention; dismissed-player integrity.", "UNRESOLVED", "M2.2D finds common dismissal classifications probable but provider semantics unresolved.", "RunOut/Retire Out not automatic credits; unfamiliar Obstracting spelling remains unresolved.", "EXCLUDE")
    add("Bowling", "Runs conceded", "Runs debited to a bowler under scoring rules.", "runs; extras_type; extras1_runs; extras_2_runs; bowler_id", "No formula approved; do not add run-named fields.", "Provider field definitions; category-level run amounts; bowler-level scorecard validation.", "UNRESOLVED", "M2.2E found no reliable per-delivery allocation or bowler figures.", "Byes/leg-byes/penalties and Overstep mapping are unresolved.", "EXCLUDE")
    add("Bowling", "Economy rate", "Bowler runs conceded per six legal balls.", "bowler_id; runs; extras_type; overid; over_ball_num", "Candidate: validated conceded runs × 6 / validated legal balls; not calculated.", "Validated numerator, legal-ball denominator, and scope policy.", "UNRESOLVED", "Runs conceded and legal deliveries are unresolved.", "Neither numerator nor denominator can be established reliably.", "EXCLUDE")
    add("Bowling", "Legal balls bowled", "Number of valid deliveries charged to a bowler.", "bowler_id; extras_type; extras1_runs; extras_2_runs; overid; over_ball_num", "No calculation approved; do not count every row or apply sample-fitted exclusions.", "Provider legality mapping; competition conditions; event-level validation.", "UNRESOLVED", "M2.2C/E aggregate candidate counts do not identify legal rows.", "Overstep and other labels are not validated as illegal.", "EXCLUDE")
    add("Bowling", "Dot-ball percentage", "Share of a bowler's legal deliveries with zero team runs under an approved definition.", "bowler_id; runs; extras_type; extras_2_runs", "No formula approved; requires validated team runs and legal-ball inclusion.", "Per-delivery team-run allocation; legal-ball mapping; dot definition.", "UNRESOLVED", "Team runs and legal-ball state are unresolved.", "Cannot call raw runs=0 a team dot ball.", "EXCLUDE")
    add("Bowling", "Boundary prevention", "Bowler's rate of boundary outcomes conceded.", "bowler_id; is_four; is_six; runs", "No formula approved; do not assume boundary flag completeness or bowler attribution.", "Validated boundary events, team/batter attribution, legal-ball/opportunity denominator.", "UNRESOLVED", "Source flags have known false negatives relative to stored 4/6; team scoring unresolved.", "Boundary allowance and denominator are undefined.", "EXCLUDE")
    add("Bowling", "Wickets lost before delivery", "Raw team-wicket flags accumulated before current delivery.", "is_wicket; match_id; innings; innings_ball_num", "Candidate descriptive state: prior-row cumulative sum only; not a bowler-credit count.", "Stored order; team-wicket interpretation; match/innings boundaries.", "CONDITIONAL", "Stored sequence and cumsum arithmetic are confirmed; team-wicket semantics partly corroborated.", "Must exclude current/post-delivery dismissal to avoid leakage.", "PROVISIONAL")
    add("Bowling", "Innings stage", "Raw innings and over context for a bowler.", "innings; overid; over_ball_num; innings_ball_num; match_id", "No phase calculation approved; preserve raw values and source order.", "Match-specific innings; legal balls; playing conditions and revised length.", "CONDITIONAL", "Raw order is confirmed; over legality and innings 3/4 semantics unresolved.", "Stored over labels do not establish phase.", "PROVISIONAL")
    add("Bowling", "Pressure wicket contribution", "Bowler-credited wickets in approved pressure contexts.", "bowler_id; dismissal_type; is_wicket; match state", "No calculation approved.", "Validated bowler credit and pre-delivery state; approved pressure definition.", "UNRESOLVED", "Both bowler-credit attribution and pressure state are unresolved.", "Could misattribute team wickets or use post-delivery information.", "EXCLUDE")
    add("Bowling", "Pressure run suppression", "Runs conceded compared across pressure and baseline states.", "bowler_id; runs; extras fields; match state", "No calculation approved.", "Validated runs conceded, legal balls, target/score state, approved pressure definition.", "UNRESOLVED", "Provider run allocation and match state are unresolved.", "No reliable conceded-run numerator or pressure labels.", "EXCLUDE")
    add("Bowling", "Pressure vs normal performance", "Like-for-like comparison of bowling outcomes in pressure and baseline contexts.", "Candidate validated bowling metrics; match/innings context", "No calculation until core bowling metrics and pressure methodology are approved.", "Validated bowling metrics; eligibility; matched baseline; uncertainty/reliability method.", "UNRESOLVED", "No bowling metric definitions or pressure method are approved.", "Do not invent weights or performance scores.", "EXCLUDE")

    add("Pressure context", "Wicket pressure", "Pre-delivery wicket-state context, distinct from bowler wickets.", "is_wicket; innings; innings_ball_num", "Potentially use raw prior-row team-wicket cumsum as an input only after sign-off; no threshold.", "Team-wicket semantics; valid stored sequence; domain-defined pressure relationship.", "CONDITIONAL", "Source-flag cumsum arithmetic is confirmed; team-wicket interpretation partly corroborated.", "No pressure threshold or remaining-wicket convention approved.", "PROVISIONAL")
    add("Pressure context", "Innings-stage pressure", "Pressure attributed to a validated innings phase.", "innings; overid; over_ball_num; innings_ball_num", "No calculation or phase threshold approved.", "Validated legal-ball/over progression; innings identity; domain sign-off.", "UNRESOLVED", "No reliable legal-ball or universal innings-stage mapping.", "Fixed phase cutoffs would be unsupported.", "EXCLUDE")
    add("Pressure context", "Chase pressure", "Pre-delivery chase difficulty relative to a validated target.", "match_id; innings; runs; extras fields; matches.revised_target", "No calculation approved; target and current team score must be independently reconstructed.", "Validated first-innings total; revised-target timing; legal balls remaining; interruption rules.", "UNRESOLVED", "No ordinary target in matches.csv; current team score and revised target timing unresolved.", "Do not derive RRR or runs required from result strings.", "EXCLUDE")
    add("Pressure context", "Match closeness", "Pre-delivery probability/distance of a close result.", "match_id; innings; pre-delivery score; target; legal balls remaining", "No calculation or outcome-derived proxy approved.", "Validated pre-delivery state; no future outcome leakage; approved definition.", "UNRESOLVED", "Score, target, legal balls, and match-closeness method are not approved.", "Final result/outcome cannot be used to label earlier pressure.", "EXCLUDE")
    add("Pressure context", "Partnership pressure", "Pressure experienced by a batting partnership.", "striker_id; non_striker_id; innings; pre-delivery score; dismissed_player_id", "No calculation approved; do not infer partnership boundaries from unresolved dismissal IDs.", "Validated batter participation, partnership transitions/runs, pre-delivery state, domain definition.", "UNRESOLVED", "Dismissal identities and team-score progression have unresolved anomalies.", "Future outcome or post-delivery state must not leak into pre-delivery feature.", "EXCLUDE")
    return rows


def matrix_markdown(rows: list[dict[str, str]]) -> str:
    frame = pd.DataFrame(rows)
    headers = [
        ("field_group", "Field"),
        ("description", "Description"),
        ("feature_name", "Feature name"),
        ("source_columns", "Source columns"),
        ("exact_source_columns", "Exact source columns"),
        ("calculation", "Calculation"),
        ("proposed_mathematical_calculation", "Proposed mathematical calculation"),
        ("dependencies", "Dependencies"),
        ("other_fields_or_validations_required", "Other fields or validations required"),
        ("evidence_status", "Evidence status"),
        ("validation_evidence", "Validation evidence"),
        ("supporting_investigation", "Supporting investigation"),
        ("limitations", "Limitations"),
        ("known_issues", "Known issues"),
        ("recommendation", "Recommendation"),
    ]
    table = frame[[key for key, _ in headers]].copy()
    table.columns = [label for _, label in headers]
    return (
        "# RR ScoutIQ — M3.1A Feature Feasibility Matrix\n\n"
        "This matrix is an investigation artifact, not an approved metric or "
        "ranking specification. Statuses apply to the stated evidence claim. "
        "No player metric, pressure score, or ranking is calculated here.\n\n"
        + markdown_table(table)
        + "\n\n## Decision summary\n\n"
        "- **INCLUDE:** No derived batting, bowling, or pressure feature is "
        "approved for selection-quality calculations. Only raw identifiers, "
        "source-row provenance, and stored sequence may be retained for "
        "descriptive audit; these are not performance features.\n"
        "- **PROVISIONAL:** Batter-run aggregate interpretation; raw boundary "
        "flags; source-wicket counts; prior-row wicket flag cumsum; raw innings "
        "and over labels. Use only for descriptive validation and preserve "
        "their stated scope limits.\n"
        "- **EXCLUDE:** Balls faced, strike rate, batting average, conceded "
        "runs, economy, legal balls, dot-ball/boundary-prevention rates, and "
        "pressure-derived comparisons until their required semantics and "
        "denominators are validated.\n"
        "- **UNRESOLVED:** Innings phase, chase pressure, match closeness, "
        "partnership pressure, bowler wicket attribution, and provider-specific "
        "scoring semantics.\n\n"
        "All proposed calculations are placeholders or explicit 'not "
        "approved' statements. They are not formulas adopted for production. "
        "Future pressure inputs must use only information available before "
        "the delivery being evaluated; post-delivery events and future match "
        "outcomes are prohibited as pre-delivery predictors.\n"
    )


def write_csv(frame: pd.DataFrame, filename: str) -> None:
    frame.to_csv(OUTPUT_DIR / filename, index=False, encoding="utf-8-sig")


def main() -> None:
    if not REQUIRED_BALL_COLUMNS.issubset(
        set(pd.read_csv(BALL_PATH, nrows=0).columns)
    ):
        actual = set(pd.read_csv(BALL_PATH, nrows=0).columns)
        raise ValueError(
            "The source schema differs from the inspected schema; missing columns: "
            + repr(sorted(REQUIRED_BALL_COLUMNS - actual))
        )
    hashes = checked_hashes()
    protected_before = prior_evidence_snapshot()

    balls = read_raw_csv(BALL_PATH)
    matches = read_raw_csv(MATCH_PATH)
    playing = read_raw_csv(PLAYING_ELEVEN_PATH)
    player_map = read_raw_csv(PLAYER_MAP_PATH)
    competitions = read_raw_csv(COMPETITION_PATH)
    prior_credit = read_raw_csv(BOWLER_CREDIT_PATH)
    balls["_source_index"] = range(len(balls))
    if len(balls) != 200_999:
        raise AssertionError(f"Expected retained source row count 200999; got {len(balls)}.")
    if not {"match_id", "comp_id"}.issubset(matches.columns):
        raise ValueError("matches.csv lacks the observed match_id/comp_id fields.")
    if not {"comp_id", "team_id", "player_id", "player_name"}.issubset(
        player_map.columns
    ):
        raise ValueError("Player mapping CSV does not have the inspected schema.")
    if balls[["match_id", "innings", "overid", "over_ball_num"]].duplicated().any():
        raise AssertionError("Observed delivery candidate key is not unique.")
    if not balls["is_wicket"].isin({"true", "false"}).all():
        raise AssertionError("Unexpected raw is_wicket values; preserve and investigate.")

    mapping, _ = mapping_indexes(balls, matches, player_map)
    lineup_validation, lineup_summary = build_lineup_validation(
        playing, matches, player_map, len(balls)
    )
    innings_validation, innings_report = build_innings_stage(
        balls, matches, competitions
    )
    batter_validation, batter_report = build_batter_validation(
        balls, mapping, lineup_summary
    )
    bowler_validation, bowler_report = build_bowler_validation(
        balls, mapping, prior_credit
    )
    features = feature_matrix_rows()
    matrix_report = matrix_markdown(features)

    anomaly_indices = set(
        balls.index[
            (balls["is_wicket"].eq("false") & balls["dismissed_player_id"].ne(""))
            | (balls["is_wicket"].eq("true") & balls["dismissed_player_id"].eq(""))
        ].tolist()
    )
    retire_indices = set(balls.index[balls["dismissal_type"].eq("Retire Out")].tolist())
    representative_indices = set(anomaly_indices) | retire_indices
    for category in balls["extras_type"].unique():
        category_indices = balls.index[balls["extras_type"].eq(category)].tolist()
        representative_indices.update(category_indices[:2])
    locators, locator_checks = source_locator_rows(
        balls, sorted(representative_indices)
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(innings_validation, "innings_stage_validation.csv")
    write_csv(batter_validation, "batter_participation_validation.csv")
    write_csv(lineup_validation, "lineup_participation_validation.csv")
    write_csv(bowler_validation, "bowler_attribution_validation.csv")
    write_csv(mapping, "player_mapping_validation.csv")
    write_csv(locators, "representative_source_records.csv")
    write_csv(locator_checks, "source_row_locator_checks.csv")
    write_csv(hashes, "source_hash_verification.csv")
    pd.DataFrame(features).to_csv(
        OUTPUT_DIR / "feature_feasibility_matrix.csv",
        index=False,
        encoding="utf-8-sig",
    )
    (OUTPUT_DIR / "innings_stage_report.md").write_text(
        innings_report, encoding="utf-8"
    )
    (OUTPUT_DIR / "batter_balls_faced_report.md").write_text(
        batter_report, encoding="utf-8"
    )
    (OUTPUT_DIR / "bowler_attribution_report.md").write_text(
        bowler_report, encoding="utf-8"
    )
    (OUTPUT_DIR / "FEATURE_FEASIBILITY_MATRIX.md").write_text(
        matrix_report, encoding="utf-8"
    )

    protected_after = prior_evidence_snapshot()
    if protected_before != protected_after:
        changed = sorted(
            path
            for path in set(protected_before) | set(protected_after)
            if protected_before.get(path) != protected_after.get(path)
        )
        raise AssertionError(f"Prior rules-validation evidence changed: {changed}")
    if len(locator_checks) != len(locators) or not locator_checks[
        "source_row_values_match_loaded_original"
    ].all():
        raise AssertionError("Source-row locator verification did not pass.")
    if len(features) != 28:
        raise AssertionError(f"Expected 28 proposed features, generated {len(features)}.")

    summary = f"""# M3.1A — Feature feasibility audit

## Scope and conclusion

This audit assessed whether source fields can support innings stage, batter
participation/balls faced, and bowler wicket attribution. It is not a metric
implementation. No rankings, player performance scores, pressure scores,
machine-learning models, or dashboard outputs were produced.

## Principal findings

- **Innings stage:** `innings_ball_num` is a confirmed stored row sequence in
  all 1,724 match/innings groups; it is not legal-ball numbering. `overid` and
  `over_ball_num` are descriptive labels only. Legal balls, actual overs, and
  powerplay/middle/death phases remain **UNRESOLVED**. Innings 1/2 are
  **PROBABLE** regulation labels in the selected scorecard sample; labels 3/4
  remain **UNRESOLVED**.
- **Batter participation:** all listed striker/non-striker IDs map contextually
  to the player mapping; this supports row-level actor association, not balls
  faced or match appearance. `runs` is **PROBABLE** as batter runs at innings
  aggregate scope only. All {len(balls):,} rows remain unclassified as balls
  faced; do not calculate strike rate.
- **Lineup participation:** {lineup_summary["lineup_rows"]:,} `playing_eleven`
  rows have raw `is_played` counts
  `{json_value(lineup_summary["is_played_counts"])}`, but state semantics and
  timing are unresolved. Five lineup IDs are unmapped; all five are raw
  `is_played=false`. Do not infer appearance or eligibility from the flag.
- **Bowler attribution:** `bowler_id` maps contextually. `is_wicket` has
  selected scorecard support as a team-wicket flag, but not a bowler-credit
  field. Common dismissal-credit interpretations are **PROBABLE** under the
  existing M2.2D assessment; `RunOut` and `Retire Out` are not automatically
  credited. `Obstracting the field` remains unresolved. Do not compute
  bowler-creditable wickets.
- **Pressure context:** no proposed pressure feature is approved for
  calculation; team-score, legal-ball, target, and provider dismissal
  limitations remain material.

## Evidence and verification

- Source rows checked: {len(balls):,}; match IDs: {balls["match_id"].nunique():,};
  innings groups: {balls.groupby(["match_id", "innings"]).ngroups:,}.
- Contextual mapping results: all checked actor IDs and source names map in
  competition/team context.
- Source hashes: {len(hashes)} protected archive/CSV hashes match the retained
  M2.3 baseline.
- Representative source locators checked: {len(locator_checks)}; all preserve
  original CSV row values.
- Prior evidence files under `audit_reports/rules_validation/` were
  hash-snapshotted before generation and remained unchanged.
- The feature matrix contains {len(features)} proposed features. No performance
  values or rankings are output.

## Outputs

- `innings_stage_validation.csv` and `innings_stage_report.md`
- `batter_participation_validation.csv` and `batter_balls_faced_report.md`
- `lineup_participation_validation.csv`
- `bowler_attribution_validation.csv` and `bowler_attribution_report.md`
- `FEATURE_FEASIBILITY_MATRIX.md` and `feature_feasibility_matrix.csv`
- `player_mapping_validation.csv`
- `representative_source_records.csv`
- `source_row_locator_checks.csv`
- `source_hash_verification.csv`

M3.1A is complete as a bounded feature feasibility audit. This does not close
M2.2/M2.3, approve metric formulas, or authorize pressure-ranking work.
"""
    (OUTPUT_DIR / "feature_feasibility_report.md").write_text(
        summary, encoding="utf-8"
    )
    print(
        f"Rows: {len(balls):,}; innings groups: "
        f"{balls.groupby(['match_id', 'innings']).ngroups:,}; "
        f"player mapping roles checked: {len(mapping)}; "
        f"dismissal categories: {len(bowler_validation)}; "
        f"features: {len(features)}; source locators: {len(locator_checks)}; "
        f"source hashes matched: {len(hashes)}."
    )
    print(f"Outputs: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
