"""Extract and audit the RR ScoutIQ dataset without changing source files."""

from __future__ import annotations

import hashlib
import re
import stat
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ARCHIVE_PATH = DATA_DIR / "data_pack.zip.zip"
EXTRACTED_DIR = DATA_DIR / "extracted"
REPORT_DIR = ROOT / "audit_reports"
VISUALIZATION_DIR = REPORT_DIR / "visualizations"
CHUNK_SIZE = 100_000

ISSUE_COLUMNS = [
    "severity",
    "file",
    "check",
    "column",
    "affected_rows",
    "details",
    "examples",
]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_member_path(root: Path, member_name: str) -> Path:
    normalized_name = member_name.replace("\\", "/")
    member = PurePosixPath(normalized_name)
    if member.is_absolute() or not member.parts or any(
        part in {"", ".", ".."} for part in member.parts
    ):
        raise ValueError(f"Unsafe archive member path: {member_name!r}")
    destination = root.joinpath(*member.parts)
    if not destination.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Archive member escapes extraction directory: {member_name!r}")
    return destination


def extract_archive(archive_path: Path, output_dir: Path) -> list[Path]:
    """Extract all regular archive files without overwriting different user files."""
    if not archive_path.is_file():
        raise FileNotFoundError(f"Dataset archive not found: {archive_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    extracted_paths: list[Path] = []
    seen_destinations: set[Path] = set()

    with zipfile.ZipFile(archive_path) as archive:
        corrupt_member = archive.testzip()
        if corrupt_member is not None:
            raise zipfile.BadZipFile(f"Corrupt archive member: {corrupt_member}")

        for info in archive.infolist():
            if info.is_dir():
                _safe_member_path(output_dir, info.filename).mkdir(
                    parents=True, exist_ok=True
                )
                continue

            destination = _safe_member_path(output_dir, info.filename)
            if destination in seen_destinations:
                raise ValueError(f"Duplicate destination in archive: {info.filename}")
            seen_destinations.add(destination)

            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError(f"Archive contains an unsupported symbolic link: {info.filename}")

            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                with archive.open(info) as source:
                    archived_hash = hashlib.sha256(source.read()).hexdigest()
                if _sha256_file(destination) != archived_hash:
                    raise FileExistsError(
                        f"Refusing to overwrite existing file with different contents: "
                        f"{destination}"
                    )
            else:
                try:
                    with archive.open(info) as source, destination.open("xb") as target:
                        while chunk := source.read(CHUNK_SIZE):
                            target.write(chunk)
                except Exception:
                    destination.unlink(missing_ok=True)
                    raise
            extracted_paths.append(destination)

    return extracted_paths


def _column(df: pd.DataFrame | None, candidates: tuple[str, ...]) -> str | None:
    if df is None:
        return None
    by_normalized_name = {
        re.sub(r"[^a-z0-9]", "", str(name).lower()): str(name)
        for name in df.columns
    }
    for candidate in candidates:
        found = by_normalized_name.get(
            re.sub(r"[^a-z0-9]", "", candidate.lower())
        )
        if found is not None:
            return found
    return None


def _id_keys(series: pd.Series) -> pd.Series:
    values = series.astype("string").str.strip()
    values = values.mask(values.str.fullmatch(r"\d+\.0", na=False), values.str[:-2])
    return values.mask(values.eq("") | values.str.lower().isin({"nan", "none", "<na>"}))


def _display_values(series: pd.Series, limit: int = 5) -> str:
    values = series.dropna().astype(str).drop_duplicates().head(limit).tolist()
    return "; ".join(values)


def _add_issue(
    issues: list[dict[str, Any]],
    severity: str,
    file_name: str,
    check: str,
    column: str,
    affected_rows: int,
    details: str,
    examples: str = "",
) -> None:
    issues.append(
        {
            "severity": severity,
            "file": file_name,
            "check": check,
            "column": column,
            "affected_rows": int(affected_rows),
            "details": details,
            "examples": examples,
        }
    )


def _load_csv(path: Path) -> tuple[pd.DataFrame, str]:
    try:
        return pd.read_csv(path, low_memory=False, encoding="utf-8-sig"), "utf-8-sig"
    except UnicodeDecodeError:
        return pd.read_csv(path, low_memory=False, encoding="cp1252"), "cp1252"


def load_datasets(csv_paths: list[Path]) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    frames: dict[str, pd.DataFrame] = {}
    encodings: dict[str, str] = {}
    for path in sorted(csv_paths, key=lambda item: item.name.lower()):
        frame, encoding = _load_csv(path)
        frames[path.name] = frame
        encodings[path.name] = encoding
    return frames, encodings


def _key_columns(file_name: str, df: pd.DataFrame) -> list[str]:
    candidates: dict[str, tuple[tuple[str, ...], ...]] = {
        "matches.csv": (("match_id",),),
        "competitions.csv": (("comp_id",),),
        "teams.csv": (("comp_id", "team_id"),),
        "competition_team_player_mapping.csv": (
            ("comp_id", "team_id", "player_id"),
        ),
        "playing_eleven.csv": (("match_id", "team_id", "player_id"),),
        "ball_by_ball.csv": (
            ("match_id", "innings", "overid", "over_ball_num"),
        ),
    }
    for candidate_group in candidates.get(file_name, ()):
        columns = [_column(df, (candidate,)) for candidate in candidate_group]
        if all(columns):
            return [str(column) for column in columns]
    return []


def build_basic_audit(
    frames: dict[str, pd.DataFrame],
    issues: list[dict[str, Any]],
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    missing_rows: list[dict[str, Any]] = []
    duplicate_rows: list[dict[str, Any]] = []
    overview: list[str] = []

    for file_name, df in frames.items():
        exact_duplicates = int(df.duplicated().sum())
        key_columns = _key_columns(file_name, df)
        key_duplicate_groups = 0
        key_duplicate_rows = 0
        key_examples = ""
        varying_columns: list[str] = []
        if key_columns:
            duplicate_mask = df.duplicated(subset=key_columns, keep=False)
            key_duplicate_rows = int(duplicate_mask.sum())
            duplicate_records = df.loc[duplicate_mask]
            key_duplicate_groups = int(
                duplicate_records[key_columns].drop_duplicates().shape[0]
            )
            if key_duplicate_rows:
                grouped = duplicate_records.groupby(key_columns, dropna=False)
                varying_columns = [
                    str(column)
                    for column in df.columns
                    if column not in key_columns
                    and grouped[column].nunique(dropna=False).gt(1).any()
                ]
                example_columns = key_columns + varying_columns
                key_examples = (
                    duplicate_records[example_columns]
                    .drop_duplicates()
                    .head(5)
                    .astype(str)
                    .to_dict("records")
                )
                key_examples = "; ".join(map(str, key_examples))
        duplicate_rows.append(
            {
                "file": file_name,
                "rows": len(df),
                "exact_duplicate_rows": exact_duplicates,
                "key_columns": ", ".join(key_columns),
                "duplicate_key_groups": key_duplicate_groups,
                "rows_in_duplicate_key_groups": key_duplicate_rows,
                "varying_non_key_columns": ", ".join(varying_columns),
                "examples": key_examples,
            }
        )
        if exact_duplicates:
            _add_issue(
                issues,
                "warning",
                file_name,
                "Exact duplicate records",
                "",
                exact_duplicates,
                "Rows exactly matching an earlier full record; retained in all analyses.",
            )
        if key_duplicate_rows:
            _add_issue(
                issues,
                "warning",
                file_name,
                "Duplicate candidate key",
                ", ".join(key_columns),
                key_duplicate_rows,
                "Rows share a candidate key but are not exact duplicates; "
                f"varying non-key columns: {', '.join(varying_columns) or 'none'}. "
                "Retained; validate whether repeated entries are expected.",
                key_examples,
            )

        overview.extend(
            [
                f"Dataset: {file_name}",
                f"Rows: {len(df):,}",
                f"Columns: {len(df.columns):,}",
                f"Exact duplicate rows: {exact_duplicates:,}",
                f"Candidate key: {', '.join(key_columns) if key_columns else 'not inferred'}",
                "Column names and inferred pandas data types:",
            ]
        )
        for column in df.columns:
            missing_count = int(df[column].isna().sum())
            missing_rows.append(
                {
                    "file": file_name,
                    "column": str(column),
                    "dtype": str(df[column].dtype),
                    "missing_count": missing_count,
                    "missing_percent": (
                        round(missing_count / len(df) * 100, 4) if len(df) else 0.0
                    ),
                    "unique_non_missing": int(df[column].nunique(dropna=True)),
                }
            )
            overview.append(
                f"  {column}: dtype={df[column].dtype}; "
                f"missing={missing_count:,}; "
                f"unique_non_missing={df[column].nunique(dropna=True):,}"
            )

            normalized = re.sub(r"[^a-z0-9]", "", str(column).lower())
            if normalized == "id" or normalized.endswith("id"):
                overview.append(
                    f"    distinct ID values: {df[column].nunique(dropna=True):,}"
                )

        numeric_columns = df.select_dtypes(include="number").columns
        for column in numeric_columns:
            normalized = re.sub(r"[^a-z0-9]", "", str(column).lower())
            if normalized.endswith("id"):
                continue
            negative_mask = df[column].lt(0) & df[column].notna()
            negative_count = int(negative_mask.sum())
            if negative_count:
                _add_issue(
                    issues,
                    "warning",
                    file_name,
                    "Negative numeric values",
                    str(column),
                    negative_count,
                    "Negative values found; review against this field's intended meaning.",
                    _display_values(df.loc[negative_mask, column]),
                )

        overview.append("")

    return (
        pd.DataFrame(missing_rows),
        pd.DataFrame(duplicate_rows),
        overview,
    )


def _check_foreign_key(
    source: pd.DataFrame,
    source_file: str,
    source_column: str,
    target_keys: set[str],
    relation_name: str,
    issues: list[dict[str, Any]],
    placeholder_keys: tuple[str, ...] = (),
) -> None:
    keys = _id_keys(source[source_column])
    unmatched_mask = (
        keys.notna()
        & ~keys.isin(target_keys)
        & ~keys.isin(placeholder_keys)
    )
    unmatched = keys.loc[unmatched_mask]
    if not unmatched.empty:
        _add_issue(
            issues,
            "warning",
            source_file,
            f"Unmatched relationship: {relation_name}",
            source_column,
            int(unmatched_mask.sum()),
            f"Non-empty source IDs are absent from the referenced dataset "
            f"({unmatched.nunique()} distinct IDs).",
            "; ".join(unmatched.drop_duplicates().head(8).astype(str)),
        )


def audit_relationships(
    frames: dict[str, pd.DataFrame], issues: list[dict[str, Any]]
) -> list[str]:
    report: list[str] = ["Cross-dataset relationships:"]

    matches = frames.get("matches.csv")
    competitions = frames.get("competitions.csv")
    teams = frames.get("teams.csv")
    mapping = frames.get("competition_team_player_mapping.csv")
    playing = frames.get("playing_eleven.csv")
    ball = frames.get("ball_by_ball.csv")

    if matches is not None and competitions is not None:
        source_col = _column(matches, ("comp_id",))
        target_col = _column(competitions, ("comp_id",))
        if source_col and target_col:
            target = set(_id_keys(competitions[target_col]).dropna())
            _check_foreign_key(
                matches,
                "matches.csv",
                source_col,
                target,
                "matches.comp_id -> competitions.comp_id",
                issues,
            )
            report.append(
                f"  matches -> competitions: {matches[source_col].nunique(dropna=True):,} "
                f"distinct competition IDs in matches; {len(target):,} in competitions."
            )

    if teams is not None and competitions is not None:
        source_col = _column(teams, ("comp_id",))
        target_col = _column(competitions, ("comp_id",))
        if source_col and target_col:
            target = set(_id_keys(competitions[target_col]).dropna())
            _check_foreign_key(
                teams,
                "teams.csv",
                source_col,
                target,
                "teams.comp_id -> competitions.comp_id",
                issues,
            )

    if mapping is not None and competitions is not None:
        source_col = _column(mapping, ("comp_id",))
        target_col = _column(competitions, ("comp_id",))
        if source_col and target_col:
            target = set(_id_keys(competitions[target_col]).dropna())
            _check_foreign_key(
                mapping,
                "competition_team_player_mapping.csv",
                source_col,
                target,
                "mapping.comp_id -> competitions.comp_id",
                issues,
            )

    if matches is not None:
        match_col = _column(matches, ("match_id",))
        match_keys = (
            set(_id_keys(matches[match_col]).dropna()) if match_col else set()
        )
        for source_df, source_name in ((playing, "playing_eleven.csv"), (ball, "ball_by_ball.csv")):
            source_col = _column(source_df, ("match_id",))
            if source_df is not None and source_col and match_col:
                _check_foreign_key(
                    source_df,
                    source_name,
                    source_col,
                    match_keys,
                    f"{source_name}.match_id -> matches.match_id",
                    issues,
                )
                report.append(
                    f"  {source_name} -> matches: "
                    f"{source_df[source_col].nunique(dropna=True):,} distinct source "
                    f"match IDs; {len(match_keys):,} in matches."
                )
                if match_col:
                    source_keys = set(_id_keys(source_df[source_col]).dropna())
                    without_rows = set(_id_keys(matches[match_col]).dropna()) - source_keys
                    if without_rows:
                        result_col = _column(matches, ("result", "status", "match_status"))
                        outcomes = (
                            matches.loc[
                                _id_keys(matches[match_col]).isin(without_rows),
                                result_col,
                            ]
                            .fillna("<missing>")
                            .astype(str)
                            .value_counts()
                            if result_col
                            else pd.Series(dtype="int64")
                        )
                        outcome_summary = "; ".join(
                            f"{value}={count:,}" for value, count in outcomes.items()
                        )
                        report.append(
                            f"  Matches without {source_name} rows: "
                            f"{len(without_rows):,}"
                            + (
                                f" (result values: {outcome_summary})"
                                if outcome_summary
                                else ""
                            )
                        )

        if teams is not None:
            team_col = _column(teams, ("team_id",))
            if team_col:
                team_keys = set(_id_keys(teams[team_col]).dropna())
                for names in (("home_team_id",), ("away_team_id",)):
                    source_col = _column(matches, names)
                    if source_col:
                        _check_foreign_key(
                            matches,
                            "matches.csv",
                            source_col,
                            team_keys,
                            f"matches.{source_col} -> teams.team_id",
                            issues,
                        )

    if teams is not None and mapping is not None:
        team_col = _column(teams, ("team_id",))
        map_team_col = _column(mapping, ("team_id",))
        if team_col and map_team_col:
            _check_foreign_key(
                mapping,
                "competition_team_player_mapping.csv",
                map_team_col,
                set(_id_keys(teams[team_col]).dropna()),
                "mapping.team_id -> teams.team_id",
                issues,
            )

    if teams is not None:
        team_col = _column(teams, ("team_id",))
        if team_col:
            known_team_keys = set(_id_keys(teams[team_col]).dropna())
            for source_df, source_file, id_candidate in (
                (playing, "playing_eleven.csv", "team_id"),
                (ball, "ball_by_ball.csv", "batting_team_id"),
                (ball, "ball_by_ball.csv", "bowling_team_id"),
            ):
                source_col = _column(source_df, (id_candidate,))
                if source_df is not None and source_col:
                    _check_foreign_key(
                        source_df,
                        source_file,
                        source_col,
                        known_team_keys,
                        f"{source_file}.{source_col} -> teams.team_id",
                        issues,
                    )

    if mapping is not None:
        map_player_col = _column(mapping, ("player_id",))
        map_name_col = _column(mapping, ("player_name",))
        known_player_keys = (
            set(_id_keys(mapping[map_player_col]).dropna())
            if map_player_col
            else set()
        )
        if map_player_col:
            for source_df, source_file, id_candidates in (
                (playing, "playing_eleven.csv", ("player_id",)),
                (ball, "ball_by_ball.csv", ("striker_id",)),
                (ball, "ball_by_ball.csv", ("non_striker_id",)),
                (ball, "ball_by_ball.csv", ("bowler_id",)),
                (ball, "ball_by_ball.csv", ("dismissed_player_id",)),
                (matches, "matches.csv", ("man_of_the_match",)),
                (matches, "matches.csv", ("home_team_captain_id",)),
                (matches, "matches.csv", ("away_team_captain_id",)),
            ):
                source_col = _column(source_df, id_candidates)
                if source_df is not None and source_col:
                    placeholders: tuple[str, ...] = ()
                    if source_file == "matches.csv" and source_col == "man_of_the_match":
                        placeholders = ("0",)
                        placeholder_mask = _id_keys(source_df[source_col]).eq("0")
                        if placeholder_mask.any():
                            _add_issue(
                                issues,
                                "warning",
                                source_file,
                                "Zero-coded player reference",
                                source_col,
                                int(placeholder_mask.sum()),
                                "Value 0 is not a player ID in the mapping file and appears "
                                "to be a missing/placeholder value; confirm the source convention.",
                                "0",
                            )
                    _check_foreign_key(
                        source_df,
                        source_file,
                        source_col,
                        known_player_keys,
                        f"{source_file}.{source_col} -> mapping.player_id",
                        issues,
                        placeholder_keys=placeholders,
                    )

    if matches is not None and teams is not None:
        team_col = _column(teams, ("team_id",))
        if team_col:
            known_team_keys = set(_id_keys(teams[team_col]).dropna())
            for candidate in ("toss_win_team_id", "win_team_id"):
                    source_col = _column(matches, (candidate,))
                    if source_col:
                        _check_foreign_key(
                            matches,
                            "matches.csv",
                            source_col,
                            known_team_keys,
                            f"matches.{source_col} -> teams.team_id",
                            issues,
                        )

        if ball is not None and map_player_col and map_name_col:
            names_by_player: dict[str, set[str]] = defaultdict(set)
            for player_id, player_name in zip(
                _id_keys(mapping[map_player_col]), mapping[map_name_col]
            ):
                if pd.notna(player_id) and pd.notna(player_name):
                    names_by_player[player_id].add(str(player_name).strip().casefold())
            for id_name, name_name in (
                ("striker_id", "striker_name"),
                ("non_striker_id", "non_striker_name"),
                ("bowler_id", "bowler_name"),
            ):
                id_col = _column(ball, (id_name,))
                name_col = _column(ball, (name_name,))
                if not id_col or not name_col:
                    continue
                mismatches: list[str] = []
                mismatch_rows = 0
                id_keys = _id_keys(ball[id_col])
                for index, (player_id, player_name) in enumerate(
                    zip(id_keys, ball[name_col])
                ):
                    if (
                        pd.notna(player_id)
                        and pd.notna(player_name)
                        and player_id in names_by_player
                        and str(player_name).strip().casefold()
                        not in names_by_player[player_id]
                    ):
                        mismatch_rows += 1
                        if len(mismatches) < 8:
                            mismatches.append(
                                f"{player_id}:{str(player_name).strip()}"
                            )
                if mismatch_rows:
                    _add_issue(
                        issues,
                        "warning",
                        "ball_by_ball.csv",
                        "Player ID/name mismatch against mapping",
                        f"{id_col}/{name_col}",
                        mismatch_rows,
                        f"{mismatch_rows:,} rows have a mapped ID but a name not "
                        "listed for that ID in the mapping file.",
                        "; ".join(mismatches),
                    )
    report.append("  Foreign-key and ID/name comparisons use non-empty IDs only.")
    return report


def build_player_coverage(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    players: dict[str, dict[str, Any]] = {}

    def get_player(player_id: Any) -> dict[str, Any] | None:
        if pd.isna(player_id):
            return None
        key = str(player_id)
        return players.setdefault(
            key,
            {
                "player_id": key,
                "names": set(),
                "mapping_competitions": set(),
                "playing_eleven_rows": 0,
                "striker_deliveries": 0,
                "non_striker_deliveries": 0,
                "bowler_deliveries": 0,
                "dismissed_records": 0,
            },
        )

    mapping = frames.get("competition_team_player_mapping.csv")
    if mapping is not None:
        id_col = _column(mapping, ("player_id",))
        name_col = _column(mapping, ("player_name",))
        comp_col = _column(mapping, ("comp_id",))
        if id_col:
            for _, row in mapping.iterrows():
                player = get_player(_id_keys(pd.Series([row[id_col]])).iloc[0])
                if player is None:
                    continue
                if name_col and pd.notna(row[name_col]):
                    player["names"].add(str(row[name_col]).strip())
                if comp_col and pd.notna(row[comp_col]):
                    player["mapping_competitions"].add(
                        str(_id_keys(pd.Series([row[comp_col]])).iloc[0])
                    )

    playing = frames.get("playing_eleven.csv")
    if playing is not None:
        id_col = _column(playing, ("player_id",))
        if id_col:
            for player_id in _id_keys(playing[id_col]):
                player = get_player(player_id)
                if player is not None:
                    player["playing_eleven_rows"] += 1

    ball = frames.get("ball_by_ball.csv")
    if ball is not None:
        for id_name, name_name, count_name in (
            ("striker_id", "striker_name", "striker_deliveries"),
            ("non_striker_id", "non_striker_name", "non_striker_deliveries"),
            ("bowler_id", "bowler_name", "bowler_deliveries"),
            ("dismissed_player_id", None, "dismissed_records"),
        ):
            id_col = _column(ball, (id_name,))
            name_col = _column(ball, (name_name,)) if name_name else None
            if not id_col:
                continue
            ids = _id_keys(ball[id_col])
            counts = ids.value_counts(dropna=True)
            names_by_id: dict[str, set[str]] = defaultdict(set)
            if name_col:
                for player_id, player_name in zip(ids, ball[name_col]):
                    if pd.notna(player_id) and pd.notna(player_name):
                        names_by_id[player_id].add(str(player_name).strip())
            for player_id, count in counts.items():
                player = get_player(player_id)
                if player is not None:
                    player[count_name] = int(count)
                    player["names"].update(names_by_id.get(player_id, set()))

    rows = []
    for player_id in sorted(players):
        player = players[player_id]
        rows.append(
            {
                "player_id": player_id,
                "player_names_observed": " | ".join(sorted(player["names"])),
                "mapping_competition_count": len(player["mapping_competitions"]),
                "playing_eleven_rows": player["playing_eleven_rows"],
                "striker_deliveries": player["striker_deliveries"],
                "non_striker_deliveries": player["non_striker_deliveries"],
                "bowler_deliveries": player["bowler_deliveries"],
                "dismissed_records": player["dismissed_records"],
            }
        )
    return pd.DataFrame(rows)


def build_competition_analysis(
    frames: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    competitions = frames.get("competitions.csv")
    if competitions is None:
        return pd.DataFrame()
    comp_col = _column(competitions, ("comp_id",))
    name_col = _column(competitions, ("comp_name", "competition_name", "name"))
    format_col = _column(competitions, ("match_format", "format"))
    season_col = _column(competitions, ("season", "year"))
    rows: list[dict[str, Any]] = []
    matches = frames.get("matches.csv")
    mapping = frames.get("competition_team_player_mapping.csv")
    teams = frames.get("teams.csv")
    playing = frames.get("playing_eleven.csv")
    ball = frames.get("ball_by_ball.csv")
    match_comp = _column(matches, ("comp_id",))
    match_id = _column(matches, ("match_id",))
    ball_match_id = _column(ball, ("match_id",))
    playing_match_id = _column(playing, ("match_id",))

    for _, competition in competitions.iterrows():
        raw_comp_id = competition[comp_col] if comp_col else pd.NA
        comp_key = (
            _id_keys(pd.Series([raw_comp_id])).iloc[0]
            if pd.notna(raw_comp_id)
            else pd.NA
        )
        selected_matches = (
            matches.loc[_id_keys(matches[match_comp]).eq(comp_key)]
            if matches is not None and match_comp and pd.notna(comp_key)
            else pd.DataFrame()
        )
        match_keys = (
            set(_id_keys(selected_matches[match_id]).dropna())
            if match_id
            else set()
        )

        def count_comp_rows(df: pd.DataFrame | None, id_col: str | None) -> int:
            if df is None or id_col is None or not match_keys:
                return 0
            return int(_id_keys(df[id_col]).isin(match_keys).sum())

        team_count = 0
        if teams is not None:
            team_comp = _column(teams, ("comp_id",))
            team_id = _column(teams, ("team_id",))
            if team_comp and team_id and pd.notna(comp_key):
                selected_teams = teams.loc[_id_keys(teams[team_comp]).eq(comp_key)]
                team_count = int(_id_keys(selected_teams[team_id]).nunique())

        mapped_players = 0
        if mapping is not None:
            mapping_comp = _column(mapping, ("comp_id",))
            mapping_player = _column(mapping, ("player_id",))
            if mapping_comp and mapping_player and pd.notna(comp_key):
                selected_mapping = mapping.loc[
                    _id_keys(mapping[mapping_comp]).eq(comp_key)
                ]
                mapped_players = int(_id_keys(selected_mapping[mapping_player]).nunique())

        rows.append(
            {
                "comp_id": raw_comp_id,
                "competition_name": competition[name_col] if name_col else "",
                "match_format": competition[format_col] if format_col else "",
                "season": competition[season_col] if season_col else "",
                "match_count": len(selected_matches),
                "team_count": team_count,
                "mapped_player_count": mapped_players,
                "playing_eleven_rows": count_comp_rows(playing, playing_match_id),
                "ball_delivery_rows": count_comp_rows(ball, ball_match_id),
            }
        )
    return pd.DataFrame(rows)


def _boolean_values(series: pd.Series) -> pd.Series:
    values = series.astype("string").str.strip().str.lower()
    return values.isin({"true", "1", "yes", "y"})


def audit_ball_by_ball(
    frames: dict[str, pd.DataFrame], issues: list[dict[str, Any]]
) -> list[str]:
    df = frames.get("ball_by_ball.csv")
    if df is None:
        return ["ball_by_ball.csv was not found; delivery-level audit unavailable."]
    lines = ["Ball-by-ball detail:"]

    for column in (
        "runs",
        "extras1_runs",
        "extras_2_runs",
        "is_four",
        "is_six",
        "is_wicket",
        "dismissal_type",
        "extras_type",
        "innings",
        "match_id",
        "striker_id",
        "bowler_id",
    ):
        actual = _column(df, (column,))
        if actual is not None:
            lines.append(
                f"  {actual}: distinct={df[actual].nunique(dropna=True):,}; "
                f"values/sample={_display_values(df[actual], 10)}"
            )

    innings_col = _column(df, ("innings",))
    match_col = _column(df, ("match_id",))
    if innings_col:
        distribution = df[innings_col].value_counts(dropna=False).sort_index()
        lines.append("  Innings delivery rows: " + "; ".join(
            f"{index}={value:,}" for index, value in distribution.items()
        ))
    if match_col and innings_col:
        deliveries = df.groupby([match_col, innings_col], dropna=False).size()
        if not deliveries.empty:
            lines.append(
                "  Deliveries per match/innings: "
                f"innings={len(deliveries):,}; min={int(deliveries.min()):,}; "
                f"median={deliveries.median():.1f}; max={int(deliveries.max()):,}"
            )

    over_ball_col = _column(df, ("over_ball_num",))
    if over_ball_col:
        ball_numbers = pd.to_numeric(df[over_ball_col], errors="coerce")
        counts = ball_numbers.value_counts().sort_index()
        lines.append(
            "  over_ball_num distribution: "
            + "; ".join(
                f"{int(value)}={int(count):,}" for value, count in counts.items()
            )
        )

    timestamp_col = _column(df, ("delivery_ist_time", "delivery_time", "timestamp"))
    if timestamp_col:
        timestamps = pd.to_datetime(df[timestamp_col], errors="coerce", utc=True)
        invalid_timestamps = df[timestamp_col].notna() & timestamps.isna()
        lines.append(
            f"  Delivery timestamps: parsed={int(timestamps.notna().sum()):,}; "
            f"unparseable={int(invalid_timestamps.sum()):,}; "
            f"range={timestamps.min() if timestamps.notna().any() else 'unavailable'} "
            f"to {timestamps.max() if timestamps.notna().any() else 'unavailable'}"
        )
        if invalid_timestamps.any():
            _add_issue(
                issues,
                "warning",
                "ball_by_ball.csv",
                "Unparseable delivery timestamps",
                timestamp_col,
                int(invalid_timestamps.sum()),
                "Non-empty delivery timestamp values could not be parsed.",
                _display_values(df.loc[invalid_timestamps, timestamp_col]),
            )

    for id_name in ("striker_id", "non_striker_id", "bowler_id"):
        column = _column(df, (id_name,))
        if column:
            lines.append(
                f"  Distinct {id_name.removesuffix('_id')} IDs: "
                f"{_id_keys(df[column]).nunique(dropna=True):,}"
            )

    runs_col = _column(df, ("runs",))
    if runs_col:
        runs = pd.to_numeric(df[runs_col], errors="coerce")
        if runs.notna().any():
            lines.append(
                f"  Parsed {runs_col} numeric summary: "
                f"min={runs.min():g}; median={runs.median():g}; max={runs.max():g}; "
                f"non_numeric_non_missing={int(runs.isna().sum() - df[runs_col].isna().sum()):,}"
            )
            for flag_name, expected in (("is_four", 4), ("is_six", 6)):
                flag_col = _column(df, (flag_name,))
                if flag_col:
                    flags = _boolean_values(df[flag_col])
                    mismatch = flags & runs.notna() & runs.ne(expected)
                    mismatch_count = int(mismatch.sum())
                    lines.append(
                        f"  {flag_name} rows where {runs_col} != {expected}: "
                        f"{mismatch_count:,} (field semantics should be validated)"
                    )
                    if mismatch_count:
                        _add_issue(
                            issues,
                            "warning",
                            "ball_by_ball.csv",
                            f"{flag_name} / runs consistency",
                            f"{flag_name}/{runs_col}",
                            mismatch_count,
                            "Flagged boundary records do not equal the expected batter-run "
                            "value; confirm source-field semantics before using the field.",
                            _display_values(df.loc[mismatch, runs_col]),
                        )

    wicket_col = _column(df, ("is_wicket",))
    dismissal_col = _column(df, ("dismissal_type",))
    if wicket_col:
        wickets = _boolean_values(df[wicket_col])
        lines.append(f"  Rows marked as wickets: {int(wickets.sum()):,}")
        if dismissal_col:
            wicket_types = df.loc[wickets, dismissal_col].fillna("<missing>").astype(str)
            lines.append(
                "  Dismissal types on wicket rows: "
                + "; ".join(
                    f"{name}={count:,}"
                    for name, count in wicket_types.value_counts().items()
                )
            )
            missing_type = wickets & df[dismissal_col].isna()
            if missing_type.any():
                _add_issue(
                    issues,
                    "warning",
                    "ball_by_ball.csv",
                    "Wicket without dismissal type",
                    dismissal_col,
                    int(missing_type.sum()),
                    "Rows marked as wickets have a missing dismissal type.",
                )
        dismissed_id_col = _column(df, ("dismissed_player_id",))
        if dismissed_id_col:
            missing_dismissed_player = wickets & df[dismissed_id_col].isna()
            if missing_dismissed_player.any():
                _add_issue(
                    issues,
                    "warning",
                    "ball_by_ball.csv",
                    "Wicket without dismissed-player ID",
                    dismissed_id_col,
                    int(missing_dismissed_player.sum()),
                    "Rows marked as wickets do not identify a dismissed player.",
                )
            extra_dismissed_ids = ~wickets & df[dismissed_id_col].notna()
            if extra_dismissed_ids.any():
                _add_issue(
                    issues,
                    "warning",
                    "ball_by_ball.csv",
                    "Dismissed-player ID without wicket flag",
                    f"{wicket_col}/{dismissed_id_col}",
                    int(extra_dismissed_ids.sum()),
                    "Rows contain a dismissed-player ID but are not marked as wickets.",
                )

    extras_col = _column(df, ("extras_type",))
    wide_count = no_ball_count = 0
    if extras_col:
        extras = df[extras_col].astype("string").str.strip().str.casefold()
        lines.append(
            "  Extras type values: "
            + "; ".join(
                f"{name}={count:,}"
                for name, count in extras.fillna("<missing>").value_counts().items()
            )
        )
        wide_mask = extras.str.contains(r"\bwide\b|\bwides\b", regex=True, na=False)
        no_ball_mask = extras.str.contains(
            r"no[\s_-]*balls?|\bnoballs?\b|overstep", regex=True, na=False
        )
        wide_count = int(wide_mask.sum())
        no_ball_count = int(no_ball_mask.sum())
        overlap_count = int((wide_mask & no_ball_mask).sum())
        if wide_count or no_ball_count:
            lines.append(
                f"  Extras labels support a provisional legal-delivery distinction: "
                f"wide={wide_count:,}; no-ball/Overstep={no_ball_count:,}; "
                f"overlap={overlap_count:,}; provisionally legal rows="
                f"{len(df) - int((wide_mask | no_ball_mask).sum()):,}. "
                "Treat Overstep as a no-ball only after confirming the source definition; "
                "rows are not removed."
            )
        else:
            lines.append(
                "  Extras labels did not identify wide/no-ball rows; legal-delivery "
                "counts cannot be inferred from these labels alone."
            )
        extras1_col = _column(df, ("extras1_runs",))
        extras2_col = _column(df, ("extras_2_runs", "extras2_runs"))
        if extras1_col:
            extras1 = pd.to_numeric(df[extras1_col], errors="coerce")
            no_extras_mask = df[extras_col].isna()
            nonzero_without_type = no_extras_mask & extras1.notna() & extras1.ne(0)
            lines.append(
                f"  {extras1_col} is nonzero while {extras_col} is missing on "
                f"{int(nonzero_without_type.sum()):,} rows; values="
                f"{_display_values(df.loc[nonzero_without_type, extras1_col], 8)}. "
                "Do not interpret this field as additional delivery runs without "
                "confirming its source semantics."
            )
            if nonzero_without_type.any():
                _add_issue(
                    issues,
                    "warning",
                    "ball_by_ball.csv",
                    "Extras amount present without extras type",
                    f"{extras_col}/{extras1_col}",
                    int(nonzero_without_type.sum()),
                    "The extras amount field is nonzero where the extras type is missing; "
                    "its semantics are ambiguous and it should not be summed as delivery "
                    "runs without source documentation.",
                    _display_values(
                        df.loc[nonzero_without_type, extras1_col], 8
                    ),
                )
        if extras2_col:
            extras2 = pd.to_numeric(df[extras2_col], errors="coerce")
            lines.append(
                f"  {extras2_col}: nonzero rows={int(extras2.gt(0).sum()):,}; "
                f"values={_display_values(df[extras2_col], 8)}."
            )

    match = frames.get("matches.csv")
    if match is not None and match_col:
        match_id_col = _column(match, ("match_id",))
        if match_id_col:
            ball_keys = set(_id_keys(df[match_col]).dropna())
            match_keys = set(_id_keys(match[match_id_col]).dropna())
            lines.append(
                f"  Match ID coverage: {len(ball_keys):,} distinct IDs in deliveries; "
                f"{len(ball_keys & match_keys):,} found in matches.csv; "
                f"{len(ball_keys - match_keys):,} unmatched."
            )

    return lines


def audit_matches(
    frames: dict[str, pd.DataFrame], issues: list[dict[str, Any]]
) -> list[str]:
    matches = frames.get("matches.csv")
    if matches is None:
        return ["matches.csv was not found; match-level audit unavailable."]
    lines = ["Match-level detail:"]

    date_col = _column(matches, ("match_date", "date"))
    if date_col:
        dates = pd.to_datetime(matches[date_col], errors="coerce", utc=True)
        invalid_mask = matches[date_col].notna() & dates.isna()
        lines.append(
            f"  Match dates: valid={int(dates.notna().sum()):,}; "
            f"invalid={int(invalid_mask.sum()):,}; "
            f"range={dates.min() if dates.notna().any() else 'unavailable'} to "
            f"{dates.max() if dates.notna().any() else 'unavailable'}"
        )
        if invalid_mask.any():
            _add_issue(
                issues,
                "warning",
                "matches.csv",
                "Unparseable match dates",
                date_col,
                int(invalid_mask.sum()),
                "Non-empty date values could not be parsed.",
                _display_values(matches.loc[invalid_mask, date_col]),
            )

    for candidates, label in (
        (("stage",), "Stages"),
        (("toss_opted", "toss_decision"), "Toss decisions"),
    ):
        column = _column(matches, candidates)
        if column:
            counts = matches[column].fillna("<missing>").astype(str).value_counts()
            lines.append(
                f"  {label}: "
                + "; ".join(f"{value}={count:,}" for value, count in counts.items())
            )

    result_col = _column(matches, ("result", "status", "match_status"))
    if result_col:
        result_values = matches[result_col].dropna().astype(str).str.strip()
        common_results = result_values.value_counts().head(8)
        lines.append(
            f"  Match results/status: {len(result_values):,} populated records; "
            f"{result_values.nunique():,} distinct raw strings; "
            + "; ".join(
                f"{value}={count:,}" for value, count in common_results.items()
            )
            + ("; additional distinct strings omitted" if result_values.nunique() > 8 else "")
        )

    competitions = frames.get("competitions.csv")
    if competitions is not None:
        match_comp = _column(matches, ("comp_id",))
        competition_comp = _column(competitions, ("comp_id",))
        format_col = _column(competitions, ("match_format", "format"))
        if match_comp and competition_comp and format_col:
            format_by_comp = dict(
                zip(
                    _id_keys(competitions[competition_comp]),
                    competitions[format_col].astype("string"),
                )
            )
            formats = _id_keys(matches[match_comp]).map(format_by_comp)
            counts = formats.fillna("<unmatched/missing>").value_counts()
            lines.append(
                "  Competition formats by match: "
                + "; ".join(f"{value}={count:,}" for value, count in counts.items())
            )

    for column_name in (
        "revised_target",
        "first_inn_revised_overs",
        "second_inn_revised_overs",
    ):
        column = _column(matches, (column_name,))
        if column:
            numeric = pd.to_numeric(matches[column], errors="coerce")
            lines.append(
                f"  {column}: populated={int(numeric.notna().sum()):,}; "
                f"non_numeric_non_missing="
                f"{int(numeric.isna().sum() - matches[column].isna().sum()):,}; "
                f"distinct={numeric.nunique(dropna=True):,}; "
                f"values/sample={_display_values(matches[column], 8)}"
            )
            invalid_numeric = matches[column].notna() & numeric.isna()
            if invalid_numeric.any():
                _add_issue(
                    issues,
                    "warning",
                    "matches.csv",
                    "Non-numeric target/overs value",
                    column,
                    int(invalid_numeric.sum()),
                    "Non-empty values could not be parsed as numeric.",
                    _display_values(matches.loc[invalid_numeric, column]),
                )

    explicit_target_col = _column(
        matches, ("target", "innings_target", "target_runs")
    )
    if explicit_target_col:
        lines.append(
            f"  Explicit target field: {explicit_target_col} "
            f"({int(matches[explicit_target_col].notna().sum()):,} populated rows)."
        )
    else:
        lines.append(
            "  No separate ordinary innings-target column was found; revised_target "
            "is the only target-like field identified."
        )

    return lines


def build_visualizations(
    frames: dict[str, pd.DataFrame], missing: pd.DataFrame
) -> list[str]:
    VISUALIZATION_DIR.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []

    if not missing.empty:
        totals = missing.groupby("file")["missing_count"].sum().sort_values()
        fig, ax = plt.subplots(figsize=(9, max(3.5, 0.5 * len(totals))))
        totals.plot.barh(ax=ax, color="#7b2c3b")
        ax.set_title("Missing values by dataset")
        ax.set_xlabel("Missing cells")
        ax.set_ylabel("")
        fig.tight_layout()
        path = VISUALIZATION_DIR / "missing_values_by_dataset.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        generated.append(path.name)

    competitions = frames.get("competitions.csv")
    if competitions is not None:
        format_col = _column(competitions, ("match_format", "format"))
        if format_col:
            counts = competitions[format_col].fillna("<missing>").astype(str).value_counts()
            fig, ax = plt.subplots(figsize=(8, 4.5))
            counts.plot.bar(ax=ax, color="#e09f3e")
            ax.set_title("Competitions by format")
            ax.set_xlabel("Format")
            ax.set_ylabel("Competition records")
            ax.tick_params(axis="x", labelrotation=35)
            fig.tight_layout()
            path = VISUALIZATION_DIR / "competitions_by_format.png"
            fig.savefig(path, dpi=150)
            plt.close(fig)
            generated.append(path.name)

    ball = frames.get("ball_by_ball.csv")
    if ball is not None:
        innings_col = _column(ball, ("innings",))
        match_col = _column(ball, ("match_id",))
        if innings_col and match_col:
            counts = (
                ball.groupby([match_col, innings_col], dropna=False)
                .size()
                .rename("delivery_rows")
                .reset_index()
            )
            fig, ax = plt.subplots(figsize=(8, 4.5))
            counts["delivery_rows"].plot.hist(
                bins=min(40, max(10, int(counts["delivery_rows"].nunique()))),
                ax=ax,
                color="#3a6b75",
            )
            ax.set_title("Delivery rows per match innings")
            ax.set_xlabel("Delivery rows")
            ax.set_ylabel("Innings")
            fig.tight_layout()
            path = VISUALIZATION_DIR / "deliveries_per_innings.png"
            fig.savefig(path, dpi=150)
            plt.close(fig)
            generated.append(path.name)

    matches = frames.get("matches.csv")
    if matches is not None:
        date_col = _column(matches, ("match_date", "date"))
        if date_col:
            dates = pd.to_datetime(matches[date_col], errors="coerce")
            dates = dates.dropna()
            if not dates.empty:
                counts = dates.dt.to_period("M").value_counts().sort_index()
                fig, ax = plt.subplots(figsize=(10, 4.5))
                counts.plot(ax=ax, color="#477998")
                ax.set_title("Matches by month")
                ax.set_xlabel("Month")
                ax.set_ylabel("Matches")
                fig.tight_layout()
                path = VISUALIZATION_DIR / "matches_by_month.png"
                fig.savefig(path, dpi=150)
                plt.close(fig)
                generated.append(path.name)

    return generated


def build_overview(
    archive_path: Path,
    extracted_paths: list[Path],
    frames: dict[str, pd.DataFrame],
    encodings: dict[str, str],
    basic_lines: list[str],
    relationship_lines: list[str],
    ball_lines: list[str],
    match_lines: list[str],
    quality_issues: list[dict[str, Any]],
    visualizations: list[str],
) -> str:
    lines = [
        "RR ScoutIQ – Dataset Audit (Milestone 1)",
        "=" * 48,
        f"Source archive: {archive_path}",
        f"Extracted directory: {EXTRACTED_DIR}",
        f"Extracted regular files: {len(extracted_paths)}",
        f"CSV datasets loaded: {len(frames)}",
        f"Identified PDF files: "
        f"{sum(path.suffix.lower() == '.pdf' for path in extracted_paths)}",
        "",
        "Archive files:",
    ]
    lines.extend(f"  {path.relative_to(EXTRACTED_DIR)}" for path in extracted_paths)
    lines.extend(["", "Dataset details:", ""])
    lines.extend(basic_lines)
    lines.extend(["", "CSV text encodings:"])
    lines.extend(f"  {name}: {encoding}" for name, encoding in encodings.items())
    lines.extend(["", *relationship_lines, "", *ball_lines, "", *match_lines])
    lines.extend(
        [
            "",
            "Overall audit counts:",
            f"  Data-quality issue records: {len(quality_issues)}",
            f"  Issue rows with affected records: "
            f"{sum(issue['affected_rows'] > 0 for issue in quality_issues)}",
            "  No source rows were intentionally removed or modified.",
            "",
            "Visualizations:",
        ]
    )
    lines.extend(f"  audit_reports/visualizations/{name}" for name in visualizations)
    return "\n".join(lines) + "\n"


def run_audit() -> None:
    extracted_paths = extract_archive(ARCHIVE_PATH, EXTRACTED_DIR)
    csv_paths = [
        path
        for path in EXTRACTED_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() == ".csv"
    ]
    pdf_paths = [
        path
        for path in EXTRACTED_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf"
    ]

    for pdf_path in pdf_paths:
        with pdf_path.open("rb") as pdf_file:
            if not pdf_file.read(5).startswith(b"%PDF-"):
                raise ValueError(f"PDF extension found but PDF signature is missing: {pdf_path}")

    frames, encodings = load_datasets(csv_paths)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    issues: list[dict[str, Any]] = []

    missing, duplicates, basic_lines = build_basic_audit(frames, issues)
    relationship_lines = audit_relationships(frames, issues)
    player_coverage = build_player_coverage(frames)
    competition_analysis = build_competition_analysis(frames)
    ball_lines = audit_ball_by_ball(frames, issues)
    match_lines = audit_matches(frames, issues)
    visualizations = build_visualizations(frames, missing)

    missing.to_csv(REPORT_DIR / "missing_values.csv", index=False)
    duplicates.to_csv(REPORT_DIR / "duplicate_analysis.csv", index=False)
    player_coverage.to_csv(REPORT_DIR / "player_coverage.csv", index=False)
    competition_analysis.to_csv(REPORT_DIR / "competition_analysis.csv", index=False)
    pd.DataFrame(issues, columns=ISSUE_COLUMNS).to_csv(
        REPORT_DIR / "data_quality_issues.csv", index=False
    )
    overview = build_overview(
        ARCHIVE_PATH,
        extracted_paths,
        frames,
        encodings,
        basic_lines,
        relationship_lines,
        ball_lines,
        match_lines,
        issues,
        visualizations,
    )
    (REPORT_DIR / "dataset_overview.txt").write_text(overview, encoding="utf-8")

    expected_reports = (
        "dataset_overview.txt",
        "missing_values.csv",
        "duplicate_analysis.csv",
        "player_coverage.csv",
        "competition_analysis.csv",
        "data_quality_issues.csv",
    )
    missing_reports = [
        name for name in expected_reports if not (REPORT_DIR / name).is_file()
    ]
    if missing_reports:
        raise RuntimeError(f"Report generation incomplete: {missing_reports}")

    print(f"Archive: {ARCHIVE_PATH}")
    print(f"Extracted files: {len(extracted_paths)}")
    print(f"CSV datasets audited: {len(frames)}")
    print(f"PDF files identified: {len(pdf_paths)}")
    print("Reports:")
    for report in expected_reports:
        path = REPORT_DIR / report
        print(f"  {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")
    print("Visualizations:")
    for name in visualizations:
        print(f"  {(VISUALIZATION_DIR / name).relative_to(ROOT)}")
    print("No player rankings, pressure scores, or ML models were produced.")


if __name__ == "__main__":
    run_audit()
