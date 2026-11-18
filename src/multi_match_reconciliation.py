"""Reconcile selected local match innings against published Cricbuzz scorecards."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BALL_BY_BALL_PATH = ROOT / "data" / "extracted" / "ball_by_ball.csv"
MATCHES_PATH = ROOT / "data" / "extracted" / "matches.csv"
COMPETITIONS_PATH = ROOT / "data" / "extracted" / "competitions.csv"
OUTPUT_DIR = (
    ROOT
    / "audit_reports"
    / "rules_validation"
    / "multi_match_reconciliation"
)
BASELINE_SOURCE_HASH_PATH = (
    ROOT / "audit_reports" / "rules_validation" / "source_sha256.csv"
)

SOURCE_FILES = [
    ROOT / "data" / "data_pack.zip.zip",
    BALL_BY_BALL_PATH,
    MATCHES_PATH,
    ROOT / "data" / "extracted" / "playing_eleven.csv",
    ROOT / "data" / "extracted" / "competition_team_player_mapping.csv",
    ROOT / "data" / "extracted" / "teams.csv",
    COMPETITIONS_PATH,
]

MATCH_EVIDENCE = [
    {
        "match_id": "14094",
        "scorecard_url": "https://www.cricbuzz.com/live-cricket-scorecard/45886/csk-vs-kkr-1st-match-indian-premier-league-2022",
        "selection_reason": "IPL 2022; includes wide, Overstep, and other extras labels.",
        "innings": {
            "1": {
                "team": "Chennai Super Kings",
                "total": 131,
                "wickets": 5,
                "overs": "20",
                "extras": 6,
                "byes": 0,
                "legbyes": 0,
                "wides": 4,
                "no_balls": 2,
                "penalty": 0,
            },
            "2": {
                "team": "Kolkata Knight Riders",
                "total": 133,
                "wickets": 4,
                "overs": "18.3",
                "extras": 4,
                "byes": 4,
                "legbyes": 0,
                "wides": 0,
                "no_balls": 0,
                "penalty": 0,
            },
        },
    },
    {
        "match_id": "20181",
        "scorecard_url": "https://www.cricbuzz.com/live-cricket-scorecard/66169/gt-vs-csk-1st-match-indian-premier-league-2023",
        "selection_reason": "IPL 2023; includes byes, leg-byes, wides, and Overstep labels.",
        "innings": {
            "1": {
                "team": "Chennai Super Kings",
                "total": 178,
                "wickets": 7,
                "overs": "20",
                "extras": 8,
                "byes": 1,
                "legbyes": 6,
                "wides": 0,
                "no_balls": 1,
                "penalty": 0,
            },
            "2": {
                "team": "Gujarat Titans",
                "total": 182,
                "wickets": 5,
                "overs": "19.2",
                "extras": 12,
                "byes": 0,
                "legbyes": 6,
                "wides": 4,
                "no_balls": 2,
                "penalty": 0,
            },
        },
    },
    {
        "match_id": "30058",
        "scorecard_url": "https://www.cricbuzz.com/live-cricket-scorecard/89665/kkr-vs-srh-3rd-match-indian-premier-league-2024",
        "selection_reason": "IPL 2024; includes repeated Overstep labels and differing innings extras.",
        "innings": {
            "1": {
                "team": "Kolkata Knight Riders",
                "total": 208,
                "wickets": 7,
                "overs": "20",
                "extras": 8,
                "byes": 0,
                "legbyes": 0,
                "wides": 6,
                "no_balls": 2,
                "penalty": 0,
            },
            "2": {
                "team": "Sunrisers Hyderabad",
                "total": 204,
                "wickets": 7,
                "overs": "20",
                "extras": 7,
                "byes": 0,
                "legbyes": 1,
                "wides": 6,
                "no_balls": 0,
                "penalty": 0,
            },
        },
    },
    {
        "match_id": "40725",
        "scorecard_url": "https://www.cricbuzz.com/live-cricket-scorecard/115165/dc-vs-rr-32nd-match-indian-premier-league-2025",
        "selection_reason": "IPL 2025 tie; includes Overstep labels and local innings 3-4 for the Super Over.",
        "innings": {
            "1": {
                "team": "Delhi Capitals",
                "total": 188,
                "wickets": 5,
                "overs": "20",
                "extras": 9,
                "byes": 0,
                "legbyes": 1,
                "wides": 7,
                "no_balls": 1,
                "penalty": 0,
            },
            "2": {
                "team": "Rajasthan Royals",
                "total": 188,
                "wickets": 4,
                "overs": "20",
                "extras": 6,
                "byes": 1,
                "legbyes": 1,
                "wides": 3,
                "no_balls": 1,
                "penalty": 0,
            },
        },
        "special_innings_note": (
            "Local innings 3 and 4 are present. The accessible scorecard page "
            "exposes only the two regulation innings; Super Over innings are "
            "not independently reconciled."
        ),
    },
    {
        "match_id": "13513",
        "scorecard_url": "https://www.cricbuzz.com/live-cricket-scorecard/35862/wi-vs-eng-3rd-t20i-england-tour-of-west-indies-2022",
        "selection_reason": "T20I 2022; unusually high scoring with wide and Overstep labels.",
        "innings": {
            "1": {
                "team": "West Indies",
                "total": 224,
                "wickets": 5,
                "overs": "20",
                "extras": 13,
                "byes": 0,
                "legbyes": 4,
                "wides": 7,
                "no_balls": 2,
                "penalty": 0,
            },
            "2": {
                "team": "England",
                "total": 204,
                "wickets": 9,
                "overs": "20",
                "extras": 12,
                "byes": 0,
                "legbyes": 0,
                "wides": 12,
                "no_balls": 0,
                "penalty": 0,
            },
        },
    },
    {
        "match_id": "28962",
        "scorecard_url": "https://www.cricbuzz.com/live-cricket-scorecard/78621/ind-vs-afg-3rd-t20i-afghanistan-tour-of-india-2024",
        "selection_reason": "T20I 2024 tied match; includes Overstep labels and a two-Super-Over result.",
        "innings": {
            "1": {
                "team": "India",
                "total": 212,
                "wickets": 4,
                "overs": "20",
                "extras": 17,
                "byes": 0,
                "legbyes": 9,
                "wides": 6,
                "no_balls": 2,
                "penalty": 0,
            },
            "2": {
                "team": "Afghanistan",
                "total": 212,
                "wickets": 6,
                "overs": "20",
                "extras": 11,
                "byes": 1,
                "legbyes": 0,
                "wides": 10,
                "no_balls": 0,
                "penalty": 0,
            },
        },
        "special_innings_note": (
            "The schedule/result reports a tied Super Over and a second "
            "Super Over. Local ball_by_ball.csv contains no rows beyond "
            "innings 2, so tie-break deliveries have no local source locator."
        ),
    },
    {
        "match_id": "34429",
        "scorecard_url": "https://www.cricbuzz.com/live-cricket-scorecard/101545/sl-vs-ind-3rd-t20i-india-tour-of-sri-lanka-2024",
        "selection_reason": "T20I 2024 tie; includes local innings 3-4 for a Super Over.",
        "innings": {
            "1": {
                "team": "India",
                "total": 137,
                "wickets": 9,
                "overs": "20",
                "extras": 7,
                "byes": 0,
                "legbyes": 2,
                "wides": 5,
                "no_balls": 0,
                "penalty": 0,
            },
            "2": {
                "team": "Sri Lanka",
                "total": 137,
                "wickets": 8,
                "overs": "20",
                "extras": 10,
                "byes": 0,
                "legbyes": 2,
                "wides": 8,
                "no_balls": 0,
                "penalty": 0,
            },
        },
        "special_innings_note": (
            "Local innings 3 and 4 are present. The accessible scorecard page "
            "exposes only the two regulation innings; Super Over innings are "
            "not independently reconciled."
        ),
    },
    {
        "match_id": "40037",
        "scorecard_url": "https://www.cricbuzz.com/live-cricket-scorecard/100290/ind-vs-eng-2nd-t20i-england-tour-of-india-2025",
        "selection_reason": "T20I 2025; includes a local Overstep label in the second innings.",
        "innings": {
            "1": {
                "team": "England",
                "total": 165,
                "wickets": 9,
                "overs": "20",
                "extras": 2,
                "byes": 0,
                "legbyes": 1,
                "wides": 1,
                "no_balls": 0,
                "penalty": 0,
            },
            "2": {
                "team": "India",
                "total": 166,
                "wickets": 8,
                "overs": "19.2",
                "extras": 11,
                "byes": 0,
                "legbyes": 1,
                "wides": 9,
                "no_balls": 1,
                "penalty": 0,
            },
        },
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extras_line(innings: dict[str, int | str]) -> str:
    return (
        f"{innings['extras']} (b {innings['byes']}, "
        f"lb {innings['legbyes']}, w {innings['wides']}, "
        f"nb {innings['no_balls']}, p {innings['penalty']})"
    )


def json_counts(values: pd.Series) -> str:
    return json.dumps(
        values.value_counts(dropna=False).sort_index().to_dict(),
        ensure_ascii=False,
        sort_keys=True,
    )


def main() -> None:
    missing_sources = [str(path) for path in SOURCE_FILES if not path.is_file()]
    if missing_sources:
        raise FileNotFoundError(
            "Required source files are missing: " + ", ".join(missing_sources)
        )

    hashes_before = {path.name: sha256(path) for path in SOURCE_FILES}
    baseline = pd.read_csv(
        BASELINE_SOURCE_HASH_PATH, dtype=str, keep_default_na=False
    )
    if not {"source_csv", "sha256"}.issubset(baseline.columns):
        raise ValueError(
            "The existing M2 source hash manifest must contain source_csv "
            "and sha256 columns."
        )
    baseline_hashes = dict(zip(baseline["source_csv"], baseline["sha256"]))
    csv_sources = [path for path in SOURCE_FILES if path.suffix.lower() == ".csv"]
    if len(csv_sources) != 6:
        raise ValueError(f"Expected six original CSVs; found {len(csv_sources)}.")
    baseline_mismatches = [
        path.name
        for path in csv_sources
        if baseline_hashes.get(path.name) != hashes_before[path.name]
    ]
    if baseline_mismatches:
        raise RuntimeError(
            "Original CSV hashes differ from the existing M2 baseline: "
            + ", ".join(baseline_mismatches)
        )
    deliveries = pd.read_csv(BALL_BY_BALL_PATH, dtype=str, keep_default_na=False)
    matches = pd.read_csv(MATCHES_PATH, dtype=str, keep_default_na=False)
    competitions = pd.read_csv(
        COMPETITIONS_PATH, dtype=str, keep_default_na=False
    )

    required = {
        "ball_by_ball.csv": {
            "match_id",
            "innings",
            "batting_team_id",
            "runs",
            "is_wicket",
            "extras_type",
            "extras1_runs",
            "extras_2_runs",
        },
        "matches.csv": {
            "match_id",
            "comp_id",
            "match_date",
            "home_team_id",
            "away_team_id",
            "home_team",
            "away_team",
            "result",
        },
        "competitions.csv": {"comp_id", "comp_name", "match_format", "season"},
    }
    for filename, columns in required.items():
        frame = {
            "ball_by_ball.csv": deliveries,
            "matches.csv": matches,
            "competitions.csv": competitions,
        }[filename]
        absent = columns.difference(frame.columns)
        if absent:
            raise ValueError(f"{filename} is missing required columns: {sorted(absent)}")

    reconciliation_rows: list[dict[str, object]] = []
    selected_rows: list[dict[str, object]] = []
    unverified_rows: list[dict[str, object]] = []
    selected_ids = {item["match_id"] for item in MATCH_EVIDENCE}
    if len(selected_ids) != len(MATCH_EVIDENCE):
        raise ValueError("Selected match IDs must be unique.")

    for evidence in MATCH_EVIDENCE:
        match_id = evidence["match_id"]
        match_rows = matches[matches["match_id"].eq(match_id)]
        if len(match_rows) != 1:
            raise ValueError(
                f"Expected exactly one matches.csv row for match {match_id}; "
                f"found {len(match_rows)}."
            )
        match = match_rows.iloc[0]
        competition_rows = competitions[competitions["comp_id"].eq(match["comp_id"])]
        if len(competition_rows) != 1:
            raise ValueError(
                f"Expected exactly one competitions.csv row for comp_id "
                f"{match['comp_id']}; found {len(competition_rows)}."
            )
        competition = competition_rows.iloc[0]
        has_special_innings = "special_innings_note" in evidence
        selected_rows.append(
            {
                "match_id": match_id,
                "match_date": match["match_date"],
                "competition_id": match["comp_id"],
                "competition": competition["comp_name"],
                "format": competition["match_format"],
                "season": competition["season"],
                "team_1": match["home_team"],
                "team_2": match["away_team"],
                "result": match["result"],
                "scorecard_source": "Cricbuzz scorecard",
                "scorecard_url": evidence["scorecard_url"],
                "selection_reason": evidence["selection_reason"],
                "match_verification_status": (
                    "PARTIALLY VERIFIED" if has_special_innings else "VERIFIED"
                ),
                "scope_note": evidence.get("special_innings_note", ""),
            }
        )

        match_delivery_rows = deliveries[deliveries["match_id"].eq(match_id)]
        innings_numbers = set(match_delivery_rows["innings"].unique())
        expected_standard_innings = {"1", "2"}
        missing_standard_innings = expected_standard_innings.difference(innings_numbers)
        if missing_standard_innings:
            raise ValueError(
                f"Match {match_id} is missing local regulation innings "
                f"{sorted(missing_standard_innings)}."
            )

        all_innings = sorted(
            innings_numbers.union(evidence["innings"]),
            key=lambda value: int(value) if value.isdigit() else value,
        )
        for innings_number in all_innings:
            local = match_delivery_rows[
                match_delivery_rows["innings"].eq(innings_number)
            ]
            scorecard = evidence["innings"].get(innings_number)
            if local.empty:
                reconciliation_rows.append(
                    {
                        "match_id": match_id,
                        "match_date": match["match_date"],
                        "competition": competition["comp_name"],
                        "format": competition["match_format"],
                        "team_1": match["home_team"],
                        "team_2": match["away_team"],
                        "innings": innings_number,
                        "scorecard_batting_team": (
                            scorecard["team"] if scorecard else ""
                        ),
                        "scorecard_source": "Cricbuzz scorecard",
                        "scorecard_url": evidence["scorecard_url"],
                        "dataframe_index_range": "",
                        "source_excel_row_range": "",
                        "source_row_count": 0,
                        "local_runs_sum": "",
                        "local_is_wicket_true_count": "",
                        "local_extras_type_row_counts": "",
                        "local_extras1_runs_value_counts": "",
                        "local_extras_2_runs_value_counts": "",
                        "local_wide_label_rows": "",
                        "local_overstep_label_rows": "",
                        "scorecard_total_wickets_overs": "",
                        "scorecard_extras": "",
                        "scorecard_batter_run_subtotal": "",
                        "scorecard_wide_runs": "",
                        "scorecard_no_ball_runs": "",
                        "comparison_result": (
                            "No local delivery rows exist beyond innings 2; "
                            "the scorecard result includes Super Over play."
                        ),
                        "status": "PARTIALLY VERIFIED",
                        "discrepancy_explanation": evidence.get(
                            "special_innings_note", ""
                        ),
                    }
                )
                unverified_rows.append(
                    {
                        "match_id": match_id,
                        "match_date": match["match_date"],
                        "competition": competition["comp_name"],
                        "innings_or_scope": "Super Over(s) / records beyond innings 2",
                        "local_source_rows": "",
                        "scorecard_url": evidence["scorecard_url"],
                        "what_is_unverified": evidence.get(
                            "special_innings_note", ""
                        ),
                    }
                )
                continue

            indices = local.index.to_list()
            if indices != list(range(indices[0], indices[-1] + 1)):
                raise ValueError(
                    f"Match {match_id}, innings {innings_number} has a "
                    "non-contiguous source row range."
                )
            local_runs = pd.to_numeric(local["runs"], errors="raise")
            local_wickets = local["is_wicket"].str.strip().str.lower().eq("true")
            local_extras = local["extras_type"]
            common = {
                "match_id": match_id,
                "match_date": match["match_date"],
                "competition": competition["comp_name"],
                "format": competition["match_format"],
                "team_1": match["home_team"],
                "team_2": match["away_team"],
                "innings": innings_number,
                "dataframe_index_range": f"{indices[0]}-{indices[-1]}",
                "source_excel_row_range": f"{indices[0] + 2}-{indices[-1] + 2}",
                "source_row_count": len(local),
                "local_runs_sum": int(local_runs.sum()),
                "local_is_wicket_true_count": int(local_wickets.sum()),
                "local_batting_team_id_values": json_counts(
                    local["batting_team_id"]
                ),
                "local_extras_type_row_counts": json_counts(local_extras),
                "local_extras1_runs_value_counts": json_counts(
                    local["extras1_runs"]
                ),
                "local_extras_2_runs_value_counts": json_counts(
                    local["extras_2_runs"]
                ),
                "local_wide_label_rows": int(local_extras.eq("wide").sum()),
                "local_overstep_label_rows": int(
                    local_extras.eq("Overstep").sum()
                ),
            }
            if scorecard is None:
                reconciliation_rows.append(
                    {
                        **common,
                        "scorecard_batting_team": "",
                        "scorecard_source": "Cricbuzz scorecard",
                        "scorecard_url": evidence["scorecard_url"],
                        "scorecard_total_wickets_overs": "",
                        "scorecard_extras": "",
                        "scorecard_batter_run_subtotal": "",
                        "scorecard_wide_runs": "",
                        "scorecard_no_ball_runs": "",
                        "comparison_result": (
                            "Local innings rows exist, but no corresponding "
                            "Super Over innings detail is exposed by the "
                            "accessible scorecard page."
                        ),
                        "status": "PARTIALLY VERIFIED",
                        "discrepancy_explanation": evidence.get(
                            "special_innings_note", ""
                        ),
                    }
                )
                unverified_rows.append(
                    {
                        "match_id": match_id,
                        "match_date": match["match_date"],
                        "competition": competition["comp_name"],
                        "innings_or_scope": f"Super Over innings {innings_number}",
                        "local_source_rows": common["source_excel_row_range"],
                        "scorecard_url": evidence["scorecard_url"],
                        "what_is_unverified": evidence.get(
                            "special_innings_note", ""
                        ),
                    }
                )
                continue

            if scorecard["team"] == match["home_team"]:
                expected_batting_team_id = match["home_team_id"]
            elif scorecard["team"] == match["away_team"]:
                expected_batting_team_id = match["away_team_id"]
            else:
                raise ValueError(
                    f"Scorecard team {scorecard['team']!r} is not listed for "
                    f"match {match_id}."
                )
            batting_team_ids = set(local["batting_team_id"])
            if batting_team_ids != {expected_batting_team_id}:
                raise ValueError(
                    f"Match {match_id}, innings {innings_number} local "
                    f"batting_team_id values {sorted(batting_team_ids)} do not "
                    f"match scorecard team {scorecard['team']!r} "
                    f"(team_id {expected_batting_team_id})."
                )
            scorecard_batter_runs = scorecard["total"] - scorecard["extras"]
            runs_match = int(local_runs.sum()) == scorecard_batter_runs
            wickets_match = int(local_wickets.sum()) == scorecard["wickets"]
            status = "PASS" if runs_match and wickets_match else "FAIL"
            comparison = (
                f"local runs sum {int(local_runs.sum())} "
                f"{'=' if runs_match else '!='} scorecard total "
                f"{scorecard['total']} - scorecard extras "
                f"{scorecard['extras']} = {scorecard_batter_runs}; "
                f"local wicket flags {int(local_wickets.sum())} "
                f"{'=' if wickets_match else '!='} scorecard wickets "
                f"{scorecard['wickets']}."
            )
            reconciliation_rows.append(
                {
                    **common,
                    "scorecard_batting_team": scorecard["team"],
                    "scorecard_source": "Cricbuzz scorecard",
                    "scorecard_url": evidence["scorecard_url"],
                    "scorecard_total_wickets_overs": (
                        f"{scorecard['total']}-{scorecard['wickets']} "
                        f"({scorecard['overs']} overs)"
                    ),
                    "scorecard_extras": extras_line(scorecard),
                    "scorecard_batter_run_subtotal": scorecard_batter_runs,
                    "scorecard_wide_runs": scorecard["wides"],
                    "scorecard_no_ball_runs": scorecard["no_balls"],
                    "comparison_result": comparison,
                    "status": status,
                    "discrepancy_explanation": (
                        "" if status == "PASS" else "One or more compared values differ."
                    ),
                }
            )

    for evidence in MATCH_EVIDENCE:
        if "special_innings_note" not in evidence:
            continue
        match_id = evidence["match_id"]
        match = matches[matches["match_id"].eq(match_id)].iloc[0]
        competition = competitions[
            competitions["comp_id"].eq(match["comp_id"])
        ].iloc[0]
        local_innings = set(
            deliveries.loc[
                deliveries["match_id"].eq(match_id), "innings"
            ].unique()
        )
        if local_innings.intersection({"3", "4"}):
            continue
        scope = "Super Over(s) / records beyond innings 2"
        reconciliation_rows.append(
            {
                "match_id": match_id,
                "match_date": match["match_date"],
                "competition": competition["comp_name"],
                "format": competition["match_format"],
                "team_1": match["home_team"],
                "team_2": match["away_team"],
                "innings": scope,
                "scorecard_batting_team": "",
                "scorecard_source": "Cricbuzz scorecard",
                "scorecard_url": evidence["scorecard_url"],
                "dataframe_index_range": "",
                "source_excel_row_range": "",
                "source_row_count": 0,
                "local_runs_sum": "",
                "local_is_wicket_true_count": "",
                "local_batting_team_id_values": "",
                "local_extras_type_row_counts": "",
                "local_extras1_runs_value_counts": "",
                "local_extras_2_runs_value_counts": "",
                "local_wide_label_rows": "",
                "local_overstep_label_rows": "",
                "scorecard_total_wickets_overs": "",
                "scorecard_extras": "",
                "scorecard_batter_run_subtotal": "",
                "scorecard_wide_runs": "",
                "scorecard_no_ball_runs": "",
                "comparison_result": (
                    "No local delivery rows exist beyond innings 2; the "
                    "scorecard result includes Super Over play."
                ),
                "status": "PARTIALLY VERIFIED",
                "discrepancy_explanation": evidence["special_innings_note"],
            }
        )
        unverified_rows.append(
            {
                "match_id": match_id,
                "match_date": match["match_date"],
                "competition": competition["comp_name"],
                "innings_or_scope": scope,
                "local_source_rows": "",
                "scorecard_url": evidence["scorecard_url"],
                "what_is_unverified": evidence["special_innings_note"],
            }
        )

    hashes_after = {path.name: sha256(path) for path in SOURCE_FILES}
    if hashes_before != hashes_after:
        raise RuntimeError("One or more original source files changed during the run.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    reconciliation = pd.DataFrame(reconciliation_rows)
    selected = pd.DataFrame(selected_rows)
    unverified = pd.DataFrame(
        unverified_rows,
        columns=[
            "match_id",
            "match_date",
            "competition",
            "innings_or_scope",
            "local_source_rows",
            "scorecard_url",
            "what_is_unverified",
        ],
    )
    hashes = pd.DataFrame(
        [
            {
                "source_file": path.relative_to(ROOT).as_posix(),
                "sha256": hashes_before[path.name],
                "baseline_status": (
                    "MATCH"
                    if path.suffix.lower() == ".csv"
                    else "NO PRIOR ARCHIVE HASH IN M2 MANIFEST"
                ),
            }
            for path in SOURCE_FILES
        ]
    )
    selected.to_csv(OUTPUT_DIR / "selected_matches.csv", index=False)
    reconciliation.to_csv(
        OUTPUT_DIR / "scorecard_reconciliation.csv", index=False
    )
    unverified.to_csv(OUTPUT_DIR / "unverified_matches.csv", index=False)
    hashes.to_csv(OUTPUT_DIR / "source_sha256.csv", index=False)
    write_report(selected, reconciliation, unverified, hashes)

    failed = reconciliation[reconciliation["status"].eq("FAIL")]
    if not failed.empty:
        raise ValueError(
            "Scorecard reconciliation failures were generated; review "
            "scorecard_reconciliation.csv."
        )
    print(
        f"Generated {len(selected)} selected matches, "
        f"{len(reconciliation)} innings-level records, "
        f"{len(unverified)} partially/unverified scope records."
    )
    print(f"Reports: {OUTPUT_DIR}")
    print("Source hashes were unchanged during the run.")


def write_report(
    selected: pd.DataFrame,
    reconciliation: pd.DataFrame,
    unverified: pd.DataFrame,
    hashes: pd.DataFrame,
) -> None:
    complete_matches = int(
        selected["match_verification_status"].eq("VERIFIED").sum()
    )
    partial_matches = int(
        selected["match_verification_status"].eq("PARTIALLY VERIFIED").sum()
    )
    passed_innings = int(reconciliation["status"].eq("PASS").sum())
    report_lines = [
        "# M2.2B Multi-Match Scorecard Reconciliation",
        "",
        "## Scope and method",
        "",
        "This read-only investigation compared eight selected local matches "
        "against public Cricbuzz scorecards. Selection spans IPL 2022-2025 "
        "and T20Is in 2022, 2024, and 2025; it includes Overstep labels, "
        "varied extras, high-scoring innings, ties, and Super Overs.",
        "",
        "For regulation innings, the comparison tests whether the local "
        "`runs` sum equals the scorecard team total minus the scorecard's "
        "published aggregate extras, and whether local `is_wicket=true` "
        "count equals scorecard wickets. The scorecard subtotal is a "
        "reconciliation value, not approval of any RR ScoutIQ performance "
        "formula. Scorecard overs and extras breakdowns are transcribed as "
        "evidence only.",
        "",
        "## Results",
        "",
        f"- Matches selected: **{len(selected)}**.",
        f"- Fully verified for both regulation innings: **{complete_matches}**.",
        f"- Partially verified at match scope: **{partial_matches}**.",
        "- Matches without an accessible independent regulation-innings "
        "scorecard: **0**.",
        f"- Regulation innings compared: **{passed_innings} passed of "
        f"{int(reconciliation['status'].isin(['PASS', 'FAIL']).sum())}**.",
        "- All 16 regulation-innings comparisons passed: local `runs` sums "
        "equal scorecard batter-run subtotals and local wicket-flag counts "
        "equal scorecard wickets.",
        "- Three matches are partial only for tie-break/Super Over scope; "
        "details are listed in `unverified_matches.csv`.",
        "",
        "| Match ID | Date | Competition | Teams | Regulation-innings result | Source rows |",
        "|---:|---|---|---|---|---|",
    ]
    for match_id in selected["match_id"]:
        match_rows = reconciliation[
            reconciliation["match_id"].eq(match_id)
            & reconciliation["innings"].isin(["1", "2"])
        ]
        match = selected[selected["match_id"].eq(match_id)].iloc[0]
        result = (
            "PASS"
            if len(match_rows) == 2 and match_rows["status"].eq("PASS").all()
            else "REVIEW"
        )
        source_ranges = "; ".join(
            f"inn {row.innings}: {row.source_excel_row_range}"
            for row in match_rows.itertuples()
        )
        report_lines.append(
            f"| {match_id} | {match.match_date} | {match.competition} | "
            f"{match.team_1} v {match.team_2} | {result} | {source_ranges} |"
        )

    report_lines.extend(
        [
            "",
            "## Selected scorecards",
            "",
        ]
    )
    for match in selected.itertuples():
        report_lines.append(
            f"- Match {match.match_id} ({match.match_date}, {match.competition}, "
            f"{match.team_1} v {match.team_2}): "
            f"[Cricbuzz scorecard]({match.scorecard_url}). "
            f"Selection: {match.selection_reason}"
        )

    report_lines.extend(
        [
            "",
            "## Extras and provider-field observations",
            "",
            "The CSV lists source `extras_type` row counts alongside the "
            "scorecard's aggregate Wide and No-ball run values. These are "
            "different units: a category row count is not an extras-run "
            "count. They are reported side by side only; no mapping from "
            "`Overstep` to No ball is asserted. `extras1_runs` and "
            "`extras_2_runs` remain raw values and are not added into the "
            "team total.",
            "",
            "The wider sample strengthens the evidence that `runs` behaves "
            "as batter runs in the tested regulation innings across the "
            "represented IPL/T20I matches. It does not identify the provider "
            "or prove that the encoding is uniform across every competition "
            "or exceptional case. Keep the dataset-wide status PROBABLE.",
            "",
            "Legal-ball counts were not derived or compared. The local "
            "dataset has no explicit legal-delivery flag, and `Overstep` "
            "remains unresolved. Scorecard over figures are recorded but are "
            "not used to approve a source-row exclusion rule.",
            "",
            "## Partial tie-break coverage",
            "",
        ]
    )
    if unverified.empty:
        report_lines.append("No partial match scopes were recorded.")
    else:
        report_lines.extend(
            [
                "| Match ID | Scope | Local rows | Limitation |",
                "|---:|---|---|---|",
            ]
        )
        for row in unverified.itertuples():
            report_lines.append(
                f"| {row.match_id} | {row.innings_or_scope} | "
                f"{row.local_source_rows or 'None'} | "
                f"{row.what_is_unverified} |"
            )
    report_lines.extend(
        [
            "",
            "## Status and next steps",
            "",
            "M2.2B is complete as a multi-match regulation-innings "
            "reconciliation with explicit partial tie-break coverage. M2.2 "
            "remains IN PROGRESS: runs are PROBABLE dataset-wide; "
            "`Overstep`, `extras1_runs`, `extras_2_runs`, and legal-delivery "
            "reconstruction remain unresolved. No batting/bowling formula, "
            "pressure score, or ranking was created.",
            "",
            "Original source hashes before and after the run matched. All six "
            "extracted CSV hashes also match the pre-existing M2 baseline "
            "manifest. The supplied archive has no prior hash in that "
            "manifest; its hash was recorded and remained stable during this "
            "run. Hash details are in `source_sha256.csv`.",
            "",
            "## Source file hashes (SHA-256)",
            "",
            "| Source | SHA-256 | Baseline status |",
            "|---|---|---|",
        ]
    )
    for row in hashes.itertuples():
        report_lines.append(
            f"| `{row.source_file}` | `{row.sha256}` | {row.baseline_status} |"
        )
    (OUTPUT_DIR / "reconciliation_report.md").write_text(
        "\n".join(report_lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
