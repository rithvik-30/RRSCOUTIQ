"""Read-only validation of wicket flags and dismissal labels."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BALL_PATH = ROOT / "data" / "extracted" / "ball_by_ball.csv"
MATCHES_PATH = ROOT / "data" / "extracted" / "matches.csv"
COMPETITIONS_PATH = ROOT / "data" / "extracted" / "competitions.csv"
PLAYER_MAP_PATH = (
    ROOT / "data" / "extracted" / "competition_team_player_mapping.csv"
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
BASELINE_HASH_PATH = (
    ROOT
    / "audit_reports"
    / "rules_validation"
    / "extras_legal_delivery"
    / "source_hash_verification.csv"
)
OUTPUT_DIR = ROOT / "audit_reports" / "rules_validation" / "wicket_dismissal"
SOURCE_CSVS = [
    BALL_PATH,
    MATCHES_PATH,
    ROOT / "data" / "extracted" / "playing_eleven.csv",
    PLAYER_MAP_PATH,
    ROOT / "data" / "extracted" / "teams.csv",
    COMPETITIONS_PATH,
]
SOURCE_ARCHIVE = ROOT / "data" / "data_pack.zip.zip"

MCC_LAWS_INDEX = "https://lawsofcricket.lords.org/home"
MCC_ABOUT_LAWS = "https://www.lords.org/mcc/about-the-laws-of-cricket"
MCC_LAW_18 = (
    "https://lawsofcricket.lords.org/laws-of-cricket/"
    "the-over-scoring-runs-dead-ball-and-extras/scoring-runs"
)
ICC_PLAYING_CONDITIONS_INDEX = (
    "https://www.icc-cricket.com/about/cricket/rules-and-regulations/"
    "playing-conditions"
)
DETAILED_SCORECARD_URL = (
    "https://www.cricbuzz.com/live-cricket-scorecard/45886/"
    "csk-vs-kkr-1st-match-indian-premier-league-2022"
)

KNOWN_ANOMALY_ROWS = {
    8247: "14114",
    23633: "15610",
    25857: "16064",
    47752: "20188",
    61018: "20243",
    63578: "20880",
    77114: "28964",
    79420: "29926",
    98954: "31709",
    112684: "37094",
    127901: "40709",
    131671: "40725",
    140263: "40763",
}

SCORECARD_DISMISSALS = [
    {
        "dismissed_player_name": "Ruturaj Gaikwad",
        "scorecard_dismissal": "Caught",
        "expected_local_label": "Caught",
    },
    {
        "dismissed_player_name": "Devon Conway",
        "scorecard_dismissal": "Caught",
        "expected_local_label": "Caught",
    },
    {
        "dismissed_player_name": "Robin Uthappa",
        "scorecard_dismissal": "Stumped",
        "expected_local_label": "Stump",
    },
    {
        "dismissed_player_name": "Ambati Rayudu",
        "scorecard_dismissal": "Run out",
        "expected_local_label": "RunOut",
    },
    {
        "dismissed_player_name": "Shivam Dube",
        "scorecard_dismissal": "Caught",
        "expected_local_label": "Caught",
    },
]

SCORECARD_BOWLER_WICKETS = {
    "Umesh Yadav": 2,
    "Varun Chakravarthy": 1,
    "Sunil Narine": 0,
    "Andre Russell": 1,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_row(index: int) -> int:
    return index + 2


def display_category(value: str) -> str:
    return value if value else "(blank)"


def id_state(value: str) -> str:
    if value == "":
        return "EMPTY"
    if value == "0":
        return "ZERO_CODED"
    if value == "None":
        return "LITERAL_NONE"
    return "POPULATED"


def parse_scorecard_wickets(value: str) -> int:
    match = re.search(r"-(\d+)\s*\(", value)
    if not match:
        raise ValueError(f"Could not parse scorecard wicket total: {value!r}")
    return int(match.group(1))


def lookup_dismissed_name(
    row: pd.Series,
    player_names: dict[tuple[str, str, str], set[str]],
) -> str:
    dismissed_id = row["dismissed_player_id"]
    if id_state(dismissed_id) != "POPULATED":
        return ""
    names = player_names.get(
        (row["comp_id"], row["batting_team_id"], dismissed_id), set()
    )
    if len(names) == 1:
        return next(iter(names))
    if not names:
        return "NOT FOUND IN CONTEXTUAL PLAYER MAP"
    return "AMBIGUOUS: " + ";".join(sorted(names))


def representative_records(
    group: pd.DataFrame,
    player_names: dict[tuple[str, str, str], set[str]],
    limit: int = 3,
) -> str:
    anomalies = group.loc[
        (group["is_wicket"].eq("true") & group["dismissed_player_id"].eq(""))
        | (group["is_wicket"].eq("false") & group["dismissed_player_id"].ne(""))
    ]
    selected = anomalies if not anomalies.empty else group
    items = []
    for index, row in selected.head(limit).iterrows():
        items.append(
            {
                "source_csv_row": csv_row(int(index)),
                "dataframe_index": int(index),
                "match_id": row["match_id"],
                "innings": row["innings"],
                "overid": row["overid"],
                "over_ball_num": row["over_ball_num"],
                "innings_ball_num": row["innings_ball_num"],
                "is_wicket": row["is_wicket"],
                "dismissal_type_id": row["dismissal_type_id"],
                "dismissal_type": row["dismissal_type"],
                "striker_id": row["striker_id"],
                "striker_name": row["striker_name"],
                "non_striker_id": row["non_striker_id"],
                "non_striker_name": row["non_striker_name"],
                "bowler_id": row["bowler_id"],
                "bowler_name": row["bowler_name"],
                "dismissed_player_id": row["dismissed_player_id"],
                "dismissed_player_name_lookup": lookup_dismissed_name(
                    row, player_names
                ),
            }
        )
    return json.dumps(items, ensure_ascii=False)


def build_player_name_lookup(
    balls: pd.DataFrame,
    matches: pd.DataFrame,
    player_map: pd.DataFrame,
) -> dict[tuple[str, str, str], set[str]]:
    match_comp = matches[["match_id", "comp_id"]]
    with_comp = balls[["match_id", "batting_team_id"]].merge(
        match_comp, on="match_id", how="left", validate="many_to_one"
    )
    if with_comp["comp_id"].isna().any():
        raise AssertionError("A delivery match did not map to comp_id.")
    names: dict[tuple[str, str, str], set[str]] = {}
    for row in player_map.itertuples(index=False):
        key = (row.comp_id, row.team_id, row.player_id)
        names.setdefault(key, set()).add(row.player_name)
    balls["comp_id"] = with_comp["comp_id"].to_numpy()
    return names


def build_category_and_cross_tab(
    balls: pd.DataFrame,
    matches: pd.DataFrame,
    player_names: dict[tuple[str, str, str], set[str]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    match_dates = dict(zip(matches["match_id"], matches["match_date"]))
    categories = []
    for category, group in balls.groupby("dismissal_type", sort=True, dropna=False):
        populated_ids = group.loc[
            group["dismissed_player_id"].map(id_state).eq("POPULATED"),
            "dismissed_player_id",
        ]
        examples = representative_records(group, player_names)
        categories.append(
            {
                "dismissal_type_raw": category,
                "category_display": display_category(category),
                "occurrences": len(group),
                "distinct_matches": group["match_id"].nunique(),
                "distinct_dismissed_player_ids": populated_ids.nunique(),
                "is_wicket_true_occurrences": int(
                    group["is_wicket"].eq("true").sum()
                ),
                "is_wicket_false_occurrences": int(
                    group["is_wicket"].eq("false").sum()
                ),
                "dismissed_player_id_populated_occurrences": int(
                    group["dismissed_player_id"].map(id_state).eq("POPULATED").sum()
                ),
                "dismissed_player_id_empty_occurrences": int(
                    group["dismissed_player_id"].map(id_state).eq("EMPTY").sum()
                ),
                "dismissed_player_id_zero_coded_occurrences": int(
                    group["dismissed_player_id"].map(id_state).eq("ZERO_CODED").sum()
                ),
                "dismissal_type_id_values": ";".join(
                    sorted(set(group["dismissal_type_id"]), key=lambda item: (item != "", item))
                ),
                "match_ids": ";".join(
                    sorted(group["match_id"].unique(), key=lambda item: int(item))
                ),
                "match_dates": ";".join(
                    f"{match_id}:{match_dates.get(match_id, '')}"
                    for match_id in sorted(
                        group["match_id"].unique(), key=lambda item: int(item)
                    )
                ),
                "representative_source_records_json": examples,
            }
        )
    category_frame = pd.DataFrame(categories)
    if int(category_frame["occurrences"].sum()) != len(balls):
        raise AssertionError(
            "Dismissal categories do not account for every source record."
        )

    cross = (
        balls.assign(
            dismissed_player_id_state=balls["dismissed_player_id"].map(id_state),
            dismissal_type_display=balls["dismissal_type"].map(display_category),
        )
        .groupby(
            [
                "is_wicket",
                "dismissal_type",
                "dismissal_type_id",
                "dismissed_player_id_state",
            ],
            dropna=False,
            sort=True,
        )
        .agg(
            occurrences=("match_id", "size"),
            distinct_matches=("match_id", "nunique"),
            distinct_dismissed_player_ids=(
                "dismissed_player_id",
                lambda values: values[
                    values.map(id_state).eq("POPULATED")
                ].nunique(),
            ),
            first_source_csv_row=("match_id", lambda values: csv_row(int(values.index[0]))),
        )
        .reset_index()
    )
    cross["category_display"] = cross["dismissal_type"].map(display_category)
    return category_frame, cross


def build_anomaly_tables(
    balls: pd.DataFrame,
    matches: pd.DataFrame,
    player_names: dict[tuple[str, str, str], set[str]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    match_metadata = matches[
        ["match_id", "comp_id", "match_date", "home_team", "away_team", "result"]
    ]
    issue_rows = balls.loc[
        (balls["is_wicket"].eq("true") & balls["dismissed_player_id"].ne("0"))
        | (balls["dismissed_player_id"].eq("0"))
    ].copy()
    missing = issue_rows.loc[
        issue_rows["is_wicket"].eq("true")
        & issue_rows["dismissed_player_id"].map(id_state).ne("POPULATED")
    ].copy()
    false_flag = balls.loc[
        balls["is_wicket"].eq("false")
        & balls["dismissed_player_id"].map(id_state).eq("POPULATED")
    ].copy()

    columns = [
        "source_csv_filename",
        "source_csv_row",
        "dataframe_index",
        "match_id",
        "match_date",
        "comp_id",
        "home_team",
        "away_team",
        "result",
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
        "dismissed_player_id_state",
        "dismissed_player_name_lookup",
        "extras_type",
        "runs",
    ]

    def format_anomalies(data: pd.DataFrame) -> pd.DataFrame:
        data = data.copy()
        data["dataframe_index"] = data.index
        data = data.merge(
            match_metadata,
            on=["match_id", "comp_id"],
            how="left",
            validate="many_to_one",
        )
        data["source_csv_filename"] = "ball_by_ball.csv"
        data["source_csv_row"] = data["dataframe_index"].map(
            lambda index: csv_row(int(index))
        )
        data["dismissed_player_id_state"] = data[
            "dismissed_player_id"
        ].map(id_state)
        data["dismissed_player_name_lookup"] = data.apply(
            lambda row: lookup_dismissed_name(row, player_names), axis=1
        )
        return data.reindex(columns=columns).sort_values("source_csv_row")

    return format_anomalies(missing), format_anomalies(false_flag)


def bowler_credit_rules() -> dict[str, dict[str, str]]:
    return {
        "Bowled": {
            "mcc_reference": "MCC Law 32 (Bowled)",
            "team_wicket_interpretation": "A dismissal category under the named MCC Law.",
            "credit": "Normally bowler-creditable under conventional scorecard attribution.",
            "status": "PROBABLE",
            "evidence": "The MCC law identifies the mode of dismissal; no provider codebook or direct scorecard bowled example was located for this validation set. Bowler-credit status remains a statistical convention rather than an established provider field.",
        },
        "Caught": {
            "mcc_reference": "MCC Law 33 (Caught)",
            "team_wicket_interpretation": "A dismissal category under the named MCC Law.",
            "credit": "Normally bowler-creditable under conventional scorecard attribution.",
            "status": "PROBABLE",
            "evidence": "In match 14094 innings 1, all three local Caught labels match scorecard caught dismissals; bowling figures include four wickets from three catches plus one stumping. This is one-match corroboration, not provider-wide confirmation.",
        },
        "Caught and Bowled": {
            "mcc_reference": "MCC Law 33 (Caught)",
            "team_wicket_interpretation": "Caught dismissal by the bowler.",
            "credit": "Normally bowler-creditable as a caught dismissal.",
            "status": "NOT APPLICABLE",
            "evidence": "No exact `Caught and Bowled` source category was observed. Do not infer this label from a Caught row or from dismissed-player/bowler ID comparisons.",
        },
        "LBW": {
            "mcc_reference": "MCC Law 36 (Leg before wicket)",
            "team_wicket_interpretation": "A dismissal category under the named MCC Law.",
            "credit": "Normally bowler-creditable under conventional scorecard attribution.",
            "status": "PROBABLE",
            "evidence": "The MCC law identifies the mode of dismissal; no provider codebook or direct scorecard LBW example was located for this validation set. Bowler-credit status remains a statistical convention rather than an established provider field.",
        },
        "Stump": {
            "mcc_reference": "MCC Law 39 (Stumped); source label is `Stump`",
            "team_wicket_interpretation": "Likely shorthand for the Stumped dismissal, but provider meaning is not documented.",
            "credit": "Normally bowler-creditable if the label means Stumped.",
            "status": "PROBABLE",
            "evidence": "In match 14094 innings 1, one local `Stump` record matches the scorecard's stumped dismissal and bowler figures. The source label is preserved; do not rename it in source data.",
        },
        "Hit Wicket": {
            "mcc_reference": "MCC Law 35 (Hit wicket)",
            "team_wicket_interpretation": "A dismissal category under the named MCC Law.",
            "credit": "Normally bowler-creditable under conventional scorecard attribution.",
            "status": "PROBABLE",
            "evidence": "The MCC law identifies the mode of dismissal; no direct scorecard hit-wicket example or provider credit field was located for this validation set.",
        },
        "RunOut": {
            "mcc_reference": "MCC Law 38 (Run out)",
            "team_wicket_interpretation": "A dismissal category under the named MCC Law.",
            "credit": "Not normally credited to the bowler.",
            "status": "PROBABLE",
            "evidence": "In match 14094 innings 1, the local RunOut matches the scorecard run out; five team wickets but only four bowling wickets are shown, and the bowling W figures align with the three Caught and one Stumped dismissals. This is one-match corroboration, not provider-wide confirmation.",
        },
        "Retire Out": {
            "mcc_reference": "MCC Law 25.4 (Retirement of a batter)",
            "team_wicket_interpretation": "Retired Out is distinct from Retired Hurt and can count as a dismissal under the Law.",
            "credit": "Not normally credited to the bowler.",
            "status": "PROBABLE",
            "evidence": "Six source rows have this label and all have `is_wicket=true`; one lacks dismissed_player_id. The law distinguishes retirement types. No independent scorecard detail for these six records or provider definition was found; do not infer missing player IDs.",
        },
        "Obstructing the field": {
            "mcc_reference": "MCC Law 37 (Obstructing the field)",
            "team_wicket_interpretation": "A dismissal category under the named MCC Law.",
            "credit": "Not normally credited to the bowler.",
            "status": "PROBABLE",
            "evidence": "The exact label aligns with the MCC dismissal name and the law identifies the mode. No provider credit field or independent scorecard example was located.",
        },
        "Obstracting the field": {
            "mcc_reference": "Potential MCC Law 37 spelling variant; not mapped",
            "team_wicket_interpretation": "Unresolved provider label; do not normalize based on spelling.",
            "credit": "Unresolved.",
            "status": "UNRESOLVED",
            "evidence": "Two rows contain the misspelled label; both have dismissal_type_id=10, as does the exact spelling. A shared code and similar text are not a provider definition.",
        },
        "Retired Hurt": {
            "mcc_reference": "MCC Law 25.4 (Retirement of a batter)",
            "team_wicket_interpretation": "A batter retiring hurt is not the same event as Retired Out; the Law provides for return/retired-not-out treatment.",
            "credit": "Not a bowler-creditable dismissal when recorded as retired not out.",
            "status": "NOT APPLICABLE",
            "evidence": "No exact `Retired Hurt` label was observed in dismissal_type. Do not treat it as equivalent to `Retire Out`.",
        },
        "Handled the Ball": {
            "mcc_reference": "Current MCC Code treats relevant conduct under Law 37 (Obstructing the field)",
            "team_wicket_interpretation": "Not observed as a separate source category.",
            "credit": "Not separately classifiable from this dataset.",
            "status": "NOT APPLICABLE",
            "evidence": "No exact `Handled the Ball` label was observed; do not create or infer a separate source category.",
        },
        "Timed Out": {
            "mcc_reference": "MCC Law 40 (Timed out)",
            "team_wicket_interpretation": "A named mode of dismissal under the MCC Laws.",
            "credit": "Not normally credited to the bowler under conventional scorecard attribution.",
            "status": "NOT APPLICABLE",
            "evidence": "No exact `Timed Out` category was observed. No provider/event evidence exists in this dataset to classify it.",
        },
    }


def build_bowler_credit_analysis(
    category_summary: pd.DataFrame,
) -> pd.DataFrame:
    rules = bowler_credit_rules()
    observed_map = {
        row["dismissal_type_raw"]: row
        for row in category_summary.to_dict("records")
    }
    categories = list(observed_map)
    categories.extend(
        label for label in rules if label not in observed_map
    )
    output = []
    for label in categories:
        observed = observed_map.get(label)
        rule = rules.get(
            label,
            {
                "mcc_reference": "No standard category mapping established",
                "team_wicket_interpretation": "Provider category remains unexplained.",
                "credit": "Unresolved.",
                "status": "UNRESOLVED",
                "evidence": "No authoritative rule mapping was established for this raw category.",
            },
        )
        output.append(
            {
                "dismissal_type_raw": label,
                "category_display": display_category(label),
                "observed_in_source": observed is not None,
                "source_occurrences": (
                    int(observed["occurrences"]) if observed is not None else 0
                ),
                "source_distinct_matches": (
                    int(observed["distinct_matches"]) if observed is not None else 0
                ),
                "source_is_wicket_true": (
                    int(observed["is_wicket_true_occurrences"])
                    if observed is not None
                    else 0
                ),
                "source_dismissed_id_populated": (
                    int(observed["dismissed_player_id_populated_occurrences"])
                    if observed is not None
                    else 0
                ),
                "mcc_rule_reference": rule["mcc_reference"],
                "team_wicket_interpretation": rule["team_wicket_interpretation"],
                "bowler_credit_interpretation": rule["credit"],
                "status": rule["status"],
                "supporting_evidence_and_limits": rule["evidence"],
                "implementation_decision": (
                    "Do not calculate bowler wickets; keep source labels/flags "
                    "unchanged pending provider and domain validation."
                ),
            }
        )
    return pd.DataFrame(output)


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def build_match_reconciliation(
    balls: pd.DataFrame,
    scorecards: pd.DataFrame,
    player_names: dict[tuple[str, str, str], set[str]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    detailed_rows = []
    for scorecard in scorecards.to_dict("records"):
        group = balls.loc[
            balls["match_id"].eq(scorecard["match_id"])
            & balls["innings"].eq(scorecard["innings"])
        ]
        if group.empty:
            raise AssertionError(
                f"No source rows for match {scorecard['match_id']} "
                f"innings {scorecard['innings']}."
            )
        first_row = csv_row(int(group.index.min()))
        last_row = csv_row(int(group.index.max()))
        if (
            first_row != int(scorecard["source_first_csv_row"])
            or last_row != int(scorecard["source_last_csv_row"])
        ):
            raise AssertionError(
                f"Source row range mismatch for match {scorecard['match_id']} "
                f"innings {scorecard['innings']}."
            )
        local_wickets = int(group["is_wicket"].eq("true").sum())
        scorecard_wickets = int(scorecard["scorecard_wickets"])
        details_available = (
            scorecard["match_id"] == "14094"
            and scorecard["innings"] == "1"
        )
        result = "PASS" if local_wickets == scorecard_wickets else "FAIL"
        detail_status = "AGGREGATE WICKETS ONLY"
        detail_url = scorecard["scorecard_source_url"]
        if details_available:
            events = group.loc[group["is_wicket"].eq("true")].copy()
            events["source_csv_row"] = [csv_row(int(index)) for index in events.index]
            events["dismissed_player_name_lookup"] = events.apply(
                lambda row: lookup_dismissed_name(row, player_names), axis=1
            )
            comparisons = []
            used_indices: set[int] = set()
            for expected in SCORECARD_DISMISSALS:
                match_index = None
                for index, event in events.iterrows():
                    if index in used_indices:
                        continue
                    name_match = (
                        normalize_name(event["dismissed_player_name_lookup"])
                        == normalize_name(expected["dismissed_player_name"])
                    )
                    label_match = event["dismissal_type"] == expected[
                        "expected_local_label"
                    ]
                    if name_match and label_match:
                        match_index = index
                        break
                if match_index is None:
                    comparisons.append(False)
                    detailed_rows.append(
                        {
                            "match_id": scorecard["match_id"],
                            "innings": scorecard["innings"],
                            "scorecard_source": scorecard["scorecard_source"],
                            "scorecard_source_url": detail_url,
                            "scorecard_dismissed_player": expected[
                                "dismissed_player_name"
                            ],
                            "scorecard_dismissal_text": expected[
                                "scorecard_dismissal"
                            ],
                            "local_source_csv_row": "",
                            "local_dismissed_player_id": "",
                            "local_dismissed_player_name_lookup": "",
                            "local_dismissal_type": "",
                            "local_striker_name": "",
                            "local_bowler_name": "",
                            "local_is_wicket": "",
                            "comparison_result": "NOT MATCHED",
                        }
                    )
                    continue
                used_indices.add(match_index)
                event = events.loc[match_index]
                comparisons.append(True)
                detailed_rows.append(
                    {
                        "match_id": scorecard["match_id"],
                        "innings": scorecard["innings"],
                        "scorecard_source": scorecard["scorecard_source"],
                        "scorecard_source_url": detail_url,
                        "scorecard_dismissed_player": expected[
                            "dismissed_player_name"
                        ],
                        "scorecard_dismissal_text": expected[
                            "scorecard_dismissal"
                        ],
                        "local_source_csv_row": int(event["source_csv_row"]),
                        "local_dismissed_player_id": event["dismissed_player_id"],
                        "local_dismissed_player_name_lookup": event[
                            "dismissed_player_name_lookup"
                        ],
                        "local_dismissal_type": event["dismissal_type"],
                        "local_striker_name": event["striker_name"],
                        "local_bowler_name": event["bowler_name"],
                        "local_is_wicket": event["is_wicket"],
                        "comparison_result": "MATCH",
                    }
                )
            details_match = (
                all(comparisons)
                and len(used_indices) == 5
                and len(events) == 5
            )
            if details_match:
                detail_status = "PASS - 5 DISMISSED PLAYERS AND LABELS MATCH"
            else:
                detail_status = "PARTIAL/FAIL - REVIEW DETAILED ROWS"

            creditable_labels = {
                "Caught",
                "Bowled",
                "LBW",
                "Hit Wicket",
                "Stump",
            }
            local_bowler_wickets = {
                bowler: int(
                    (
                        events.loc[events["bowler_name"].eq(bowler), "dismissal_type"]
                        .isin(creditable_labels)
                    ).sum()
                )
                for bowler in events["bowler_name"].unique()
            }
            scorecard_bowlers_match = all(
                SCORECARD_BOWLER_WICKETS.get(bowler) == wickets
                for bowler, wickets in local_bowler_wickets.items()
            )
            detail_status += (
                "; BOWLER FIGURES MATCH"
                if scorecard_bowlers_match
                else "; BOWLER FIGURES DIFFER"
            )
        rows.append(
            {
                "match_id": scorecard["match_id"],
                "match_date": scorecard["match_date"],
                "competition": scorecard["competition"],
                "format": scorecard["format"],
                "innings": scorecard["innings"],
                "scorecard_batting_team": scorecard["scorecard_team"],
                "source_csv_filename": "ball_by_ball.csv",
                "source_excel_row_range": f"{first_row}-{last_row}",
                "source_dataframe_index_range": (
                    f"{int(group.index.min())}-{int(group.index.max())}"
                ),
                "source_delivery_rows": len(group),
                "local_is_wicket_true_count": local_wickets,
                "local_is_wicket_false_count": int(
                    group["is_wicket"].eq("false").sum()
                ),
                "local_dismissal_type_true_row_counts": group.loc[
                    group["is_wicket"].eq("true"), "dismissal_type"
                ].value_counts(dropna=False).to_json(force_ascii=False),
                "scorecard_total_wickets": scorecard_wickets,
                "wicket_count_comparison": (
                    "MATCH" if local_wickets == scorecard_wickets else "DIFFER"
                ),
                "aggregate_comparison_status": result,
                "detailed_dismissal_comparison": detail_status,
                "detailed_comparison_scope": (
                    "Five batter dismissal lines and bowling W figures "
                    "independently read for this innings."
                    if details_available
                    else "Only aggregate wickets are present in preserved M2.2A/B evidence."
                ),
                "detailed_dismissal_records_json": json.dumps(
                    [
                        record
                        for record in detailed_rows
                        if record["match_id"] == scorecard["match_id"]
                        and record["innings"] == scorecard["innings"]
                    ],
                    ensure_ascii=False,
                ),
                "scorecard_source": scorecard["scorecard_source"],
                "scorecard_source_url": scorecard["scorecard_source_url"],
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(detailed_rows)


def load_scorecard_evidence() -> pd.DataFrame:
    m2a = pd.read_csv(M2A_SCORECARD_PATH, dtype=str, keep_default_na=False)
    m2b = pd.read_csv(M2B_SCORECARD_PATH, dtype=str, keep_default_na=False)
    rows = []
    for record in m2a.to_dict("records"):
        rows.append(
            {
                "match_id": record["match_id"],
                "match_date": record["match_date"],
                "competition": "IPL 2022",
                "format": "T20",
                "innings": record["innings"],
                "scorecard_team": (
                    record["home_team"]
                    if record["innings"] == "1"
                    else record["away_team"]
                ),
                "source_first_csv_row": record["source_first_csv_row"],
                "source_last_csv_row": record["source_last_csv_row"],
                "scorecard_wickets": record["scorecard_wickets"],
                "scorecard_source": "Cricbuzz scorecard",
                "scorecard_source_url": record["scorecard_source_url"],
            }
        )
    for record in m2b.to_dict("records"):
        if record["innings"] not in {"1", "2"}:
            continue
        rows.append(
            {
                "match_id": record["match_id"],
                "match_date": record["match_date"],
                "competition": record["competition"],
                "format": record["format"],
                "innings": record["innings"],
                "scorecard_team": record["scorecard_batting_team"],
                "source_first_csv_row": record[
                    "source_excel_row_range"
                ].split("-")[0],
                "source_last_csv_row": record[
                    "source_excel_row_range"
                ].split("-")[1],
                "scorecard_wickets": parse_scorecard_wickets(
                    record["scorecard_total_wickets_overs"]
                ),
                "scorecard_source": record["scorecard_source"],
                "scorecard_source_url": record["scorecard_url"],
            }
        )
    scorecards = pd.DataFrame(rows)
    if scorecards.duplicated(["match_id", "innings"]).any():
        raise AssertionError("Duplicate scorecard evidence for a match/innings.")
    if scorecards["scorecard_source_url"].str.strip().eq("").any():
        raise AssertionError("Scorecard evidence has a blank URL.")
    return scorecards.sort_values(
        ["match_date", "match_id", "innings"]
    ).reset_index(drop=True)


def write_report(
    balls: pd.DataFrame,
    categories: pd.DataFrame,
    cross_tab: pd.DataFrame,
    missing: pd.DataFrame,
    false_flag: pd.DataFrame,
    credit: pd.DataFrame,
    reconciliation: pd.DataFrame,
    detail_rows: pd.DataFrame,
    hashes: pd.DataFrame,
) -> None:
    status_counts = credit.groupby("status").size().to_dict()
    pass_count = int(
        reconciliation["aggregate_comparison_status"].eq("PASS").sum()
    )
    detail_pass = reconciliation[
        reconciliation["detailed_dismissal_comparison"].str.startswith(
            "PASS", na=False
        )
    ]
    categories_display = categories[
        ["category_display", "occurrences", "distinct_matches"]
    ]
    lines = [
        "# Wicket and Dismissal Validation (M2.2D)",
        "",
        "## Scope and evidence boundaries",
        "",
        "This read-only investigation profiles the source dismissal fields, "
        "verifies the previously reported anomaly rows against the original "
        "CSV, and compares local team-wicket flags with the independently "
        "recorded scorecard totals. It does not repair source rows or define "
        "a final batting/bowling metric.",
        "",
        "The existing milestone tracker reserves M2.3 for innings/match-state "
        "reconstruction. To avoid silently re-numbering that work, this "
        "wicket/dismissal investigation is tracked as M2.2D. M2.2 remains in "
        "progress and this investigation does not complete it.",
        "",
        "Source `dismissal_type` contains **nine nonblank exact strings** plus "
        "the empty value, for ten raw categories. Preserve original spelling "
        "and case. The source has no `dismissed_player_name` column; the "
        "lookup values below use `(competition, batting team, player ID)` "
        "against the supplied mapping file and are labeled as lookups, not "
        "source fields.",
        "",
        "## Observed dismissal categories",
        "",
        "| Raw category | Occurrences | Distinct matches | Distinct dismissed IDs | `is_wicket=true` | `is_wicket=false` | IDs populated | IDs empty |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in categories.to_dict("records"):
        lines.append(
            f"| `{row['category_display']}` | {row['occurrences']} | "
            f"{row['distinct_matches']} | "
            f"{row['distinct_dismissed_player_ids']} | "
            f"{row['is_wicket_true_occurrences']} | "
            f"{row['is_wicket_false_occurrences']} | "
            f"{row['dismissed_player_id_populated_occurrences']} | "
            f"{row['dismissed_player_id_empty_occurrences']} |"
        )
    lines.extend(
        [
            "",
            "Raw category frequencies account for all "
            f"{len(balls):,} delivery rows. Empty `dismissal_type` occurs on "
            "190,118 rows and is not converted into a dismissal category or "
            "assumed to mean the same thing as an empty player ID.",
            "",
            "All exact `is_wicket` × `dismissal_type` × "
            "`dismissal_type_id` × player-ID-state counts are in "
            "`wicket_flag_cross_tabulation.csv`. Up to three representative "
            "source records per category, including source row locator, "
            "match/innings/delivery, raw IDs and contextual dismissed-player "
            "name lookup, are embedded in `dismissal_category_summary.csv`.",
            "",
            "## Team wickets vs bowler-creditable wickets",
            "",
            "[MCC's Laws of Cricket portal]("
            f"{MCC_LAWS_INDEX}) identifies the official Laws; its [Law 18 "
            "scoring page]("
            f"{MCC_LAW_18}) section 18.10.3 specifies bowler-debited run "
            "categories, but does not itself define this dataset's dismissal "
            "codes or a bowler-wicket metric. MCC Laws 25 and 32-40 define "
            "retirement and dismissal modes (Bowled, Caught, Hit wicket, LBW, "
            "Obstructing the field, Run out, Stumped, and Timed out). The "
            "MCC [about the Laws]("
            f"{MCC_ABOUT_LAWS}) distinguishes Laws from playing conditions. "
            "The [ICC playing-conditions index]("
            f"{ICC_PLAYING_CONDITIONS_INDEX}) lists regulations, but the "
            "historical competition-specific conditions for all source "
            "matches were not identified here.",
            "",
            "Attempts to load individual MCC mode-of-dismissal pages in this "
            "browser session failed. Therefore the rule numbers are recorded "
            "as source references, not quoted as a verified statement that "
            "MCC itself sets every statistical bowler-credit convention. "
            "Bowler-credit interpretations are explicitly **PROBABLE** where "
            "they reflect normal scorecard attribution; they are not "
            "provider-confirmed.",
            "",
            "| Category | Conventional bowler credit | Status | Evidence limit |",
            "|---|---|---|---|",
        ]
    )
    for row in credit.to_dict("records"):
        if not row["observed_in_source"]:
            continue
        lines.append(
            f"| `{row['category_display']}` | "
            f"{row['bowler_credit_interpretation']} | {row['status']} | "
            f"{row['supporting_evidence_and_limits']} |"
        )
    lines.extend(
        [
            "",
            "For conventional scorecard attribution, **Bowled, Caught, "
            "LBW, Stumped, and Hit Wicket** are normally credited to the "
            "bowler; `Caught and Bowled` is a caught dismissal but is not a "
            "separate source category here. **Run out, Retired Out, and "
            "Obstructing the field** are normally not credited to the "
            "bowler. These are probable classifications for this project, "
            "not a validated formula or provider-specific guarantee. The "
            "raw `Stump` label is only probably equivalent to Stumped. "
            "`Obstracting the field` remains unresolved; do not normalize it "
            "to `Obstructing the field` merely because of similar spelling "
            "or a shared numeric ID.",
            "",
            "`Retired Hurt` is not equivalent to `Retire Out`; no "
            "`Retired Hurt`, `Timed Out`, `Handled the Ball`, or "
            "`Caught and Bowled` exact label is present in the source. These "
            "are marked **NOT APPLICABLE** as observed source categories, "
            "not imputed as absent events from every match.",
            "",
            "## Independent match-level reconciliation",
            "",
            f"The preserved M2.2A/B scorecard evidence covers "
            f"{len(reconciliation)} regulation innings. Local `is_wicket=true` "
            f"counts match aggregate scorecard wickets in {pass_count}/"
            f"{len(reconciliation)} innings. This confirms the team-wicket "
            "flag count only for those selected innings; it does not identify "
            "dismissed players or bowler credit.",
            "",
            "The Cricbuzz scorecard for match 14094, innings 1, was also read "
            "at [the recorded scorecard URL]("
            f"{DETAILED_SCORECARD_URL}). It lists five dismissed batters: "
            "three caught, one stumped, and one run out. Local labels and "
            "contextual player-ID lookups match all five details. Scorecard "
            "bowling figures show Umesh Yadav 2, Varun Chakravarthy 1, and "
            "Andre Russell 1 wickets (four total); the local three Caught and "
            "one `Stump` rows have the corresponding bowler names, while the "
            "RunOut is the fifth team wicket. This is one independent "
            "innings-level example, not global validation of every "
            "dismissal category.",
            "",
            "The detailed comparison with each exact source row is in "
            "`match_wicket_reconciliation.csv` (see its detailed-match "
            "columns) and `dismissal_category_summary.csv`. All other "
            "preserved scorecards provide aggregate wicket totals only in the "
            "M2.2A/B transcription; their per-batter dismissal details were "
            "not recorded here. Super Over scopes remain outside this "
            "regulation-innings reconciliation.",
            "",
            "## Anomaly findings",
            "",
            f"- Wicket flag true with an empty/zero-coded dismissed-player ID: "
            f"**{len(missing)}** record(s).",
            f"- Dismissed-player ID populated while `is_wicket=false`: "
            f"**{len(false_flag)}** record(s).",
            f"- Zero-coded (`0`) dismissed-player IDs anywhere in the source: "
            f"{int(balls['dismissed_player_id'].eq('0').sum())}.",
            f"- Literal string `None` dismissed-player IDs: "
            f"{int(balls['dismissed_player_id'].eq('None').sum())}.",
            f"- Empty dismissed-player IDs overall: "
            f"{int(balls['dismissed_player_id'].eq('').sum())}.",
            "",
            "All 13 previously identified Excel row numbers and match IDs "
            "were asserted against the source. The 12 populated-ID/false-flag "
            "rows have empty dismissal labels; they remain unadjudicated. "
            "The single wicket/ID gap is source row 127901 (DataFrame index "
            "127899), match 40709, innings 2, over 19, ball 5, with "
            "`dismissal_type=Retire Out`, `is_wicket=true`, and an empty "
            "`dismissed_player_id`. Do not infer the missing player from "
            "striker/non-striker fields.",
            "",
            "The source has six `Retire Out` rows across six matches; all six "
            "have `is_wicket=true`, five have populated player IDs and one "
            "has an empty ID. Their six exact records are included in the "
            "missing-ID report when applicable, the category examples, and "
            "the cross-tabulation. No record was removed or altered.",
            "",
            "## Status and calculation gate",
            "",
            "- **CONFIRMED:** exact source distributions and combinations; "
            "13 source-row anomalies and their fields; zero-coded ID count; "
            "local true-flag counts equal scorecard team wickets in the "
            "18 selected regulation innings; detailed dismissal names/types "
            "and bowling W figures match for match 14094 innings 1.",
            "- **PROBABLE:** conventional bowler credit for standard Law "
            "categories; `Stump` as Stumped; the single-match distinction "
            "between team wickets and bowler wickets.",
            "- **UNRESOLVED:** provider definitions for `is_wicket`, "
            "`dismissal_type_id`, `dismissal_type`, and "
            "`dismissed_player_id`; `Obstracting the field`; general "
            "dismissed-player ID quality; whether the M1 12 false-flag IDs "
            "are stale, unrelated, or provider-specific; bowler credit across "
            "all competitions and conditions.",
            "- **NOT APPLICABLE:** separate source labels for "
            "`Caught and Bowled`, `Retired Hurt`, `Handled the Ball`, and "
            "`Timed Out` were not observed; this does not assert those events "
            "never occurred outside represented rows or were not folded "
            "into another provider category.",
            "",
            "No bowler-wicket or batter-dismissal calculation is approved. "
            "Keep team-wicket state, player dismissal identity, and "
            "bowler-credit attribution separate until provider/domain review.",
            "",
            "## Source integrity",
            "",
            f"The script checked SHA-256 for all six extracted CSVs and the "
            f"original archive against the M2.2C baseline: "
            f"{len(hashes)} protected files. See "
            "`source_hash_verification.csv`.",
        ]
    )
    (OUTPUT_DIR / "wicket_dismissal_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    required = [
        *SOURCE_CSVS,
        SOURCE_ARCHIVE,
        M2A_SCORECARD_PATH,
        M2B_SCORECARD_PATH,
        BASELINE_HASH_PATH,
    ]
    missing_files = [str(path) for path in required if not path.is_file()]
    if missing_files:
        raise FileNotFoundError(
            "Required source/evidence files are missing: "
            + ", ".join(missing_files)
        )

    protected_paths = [*SOURCE_CSVS, SOURCE_ARCHIVE]
    before_hashes = {path: sha256(path) for path in protected_paths}
    baseline = pd.read_csv(
        BASELINE_HASH_PATH, dtype=str, keep_default_na=False
    )
    expected_hashes = dict(zip(baseline["source_file"], baseline["sha256"]))
    for path in SOURCE_CSVS:
        relative = path.relative_to(ROOT).as_posix()
        if expected_hashes.get(relative) != before_hashes[path]:
            raise RuntimeError(
                f"Source hash differs from M2.2C baseline: {relative}"
            )
    archive_relative = SOURCE_ARCHIVE.relative_to(ROOT).as_posix()
    if expected_hashes.get(archive_relative) != before_hashes[SOURCE_ARCHIVE]:
        raise RuntimeError("Archive hash differs from M2.2C baseline.")

    balls = pd.read_csv(BALL_PATH, dtype=str, keep_default_na=False)
    matches = pd.read_csv(MATCHES_PATH, dtype=str, keep_default_na=False)
    competitions = pd.read_csv(
        COMPETITIONS_PATH, dtype=str, keep_default_na=False
    )
    player_map = pd.read_csv(
        PLAYER_MAP_PATH, dtype=str, keep_default_na=False
    )
    required_columns = {
        "match_id",
        "innings",
        "overid",
        "over_ball_num",
        "innings_ball_num",
        "batting_team_id",
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
    }
    absent = required_columns.difference(balls.columns)
    if absent:
        raise ValueError(
            "ball_by_ball.csv lacks required fields: "
            + ", ".join(sorted(absent))
        )
    if not {"match_id", "comp_id", "match_date", "home_team", "away_team", "result"}.issubset(matches.columns):
        raise ValueError("matches.csv lacks required match metadata fields.")
    if not {"comp_id", "comp_name", "match_format"}.issubset(
        competitions.columns
    ):
        raise ValueError("competitions.csv lacks required competition fields.")
    if not {"comp_id", "team_id", "player_id", "player_name"}.issubset(
        player_map.columns
    ):
        raise ValueError("Player mapping lacks required contextual fields.")

    if not balls["is_wicket"].isin({"true", "false"}).all():
        raise AssertionError("Unexpected raw is_wicket value.")
    if set(balls["dismissal_type"].unique()) != {
        "",
        "Bowled",
        "Caught",
        "Hit Wicket",
        "LBW",
        "Obstracting the field",
        "Obstructing the field",
        "Retire Out",
        "RunOut",
        "Stump",
    }:
        raise AssertionError(
            "Observed dismissal_type categories changed; review before classifying."
        )

    match_data = matches.merge(
        competitions[["comp_id", "comp_name", "match_format"]],
        on="comp_id",
        how="left",
        validate="many_to_one",
    )
    if match_data["comp_name"].isna().any():
        raise AssertionError("A match did not map to competition metadata.")
    player_names = build_player_name_lookup(balls, matches, player_map)

    anomalies = balls.loc[
        (
            balls["dismissed_player_id"].ne("")
            & balls["is_wicket"].eq("false")
        )
        | (
            balls["is_wicket"].eq("true")
            & balls["dismissed_player_id"].eq("")
        )
    ]
    observed_anomaly_rows = {
        csv_row(int(index)): row["match_id"]
        for index, row in anomalies.iterrows()
    }
    if observed_anomaly_rows != KNOWN_ANOMALY_ROWS:
        raise AssertionError(
            "Wicket/ID anomaly rows differ from the previously audited 13 records."
        )
    retire_out = balls.loc[127901 - 2]
    if not (
        retire_out["match_id"] == "40709"
        and retire_out["innings"] == "2"
        and retire_out["overid"] == "19"
        and retire_out["over_ball_num"] == "5"
        and retire_out["innings_ball_num"] == "117"
        and retire_out["is_wicket"] == "true"
        and retire_out["dismissal_type"] == "Retire Out"
        and retire_out["dismissed_player_id"] == ""
    ):
        raise AssertionError("Match 40709 Retire Out source row changed.")
    if balls["dismissed_player_id"].eq("0").any():
        zero_coded_ids = balls.loc[
            balls["dismissed_player_id"].eq("0"), "dismissed_player_id"
        ].count()
    else:
        zero_coded_ids = 0

    category_summary, cross_tab = build_category_and_cross_tab(
        balls, matches, player_names
    )
    missing_ids, false_flag_ids = build_anomaly_tables(
        balls, match_data, player_names
    )
    if len(missing_ids) != 1 or len(false_flag_ids) != 12:
        raise AssertionError("Expected one missing dismissed ID and 12 false-flag IDs.")
    credit = build_bowler_credit_analysis(category_summary)
    scorecards = load_scorecard_evidence()
    reconciliation, detailed_comparisons = build_match_reconciliation(
        balls, scorecards, player_names
    )
    if len(reconciliation) != 18:
        raise AssertionError(
            f"Expected 18 regulation innings in M2.2A/B, found "
            f"{len(reconciliation)}."
        )
    if not reconciliation["aggregate_comparison_status"].eq("PASS").all():
        raise AssertionError("A local wicket count differs from scorecard total.")
    detailed = reconciliation.loc[
        reconciliation["match_id"].eq("14094")
        & reconciliation["innings"].eq("1")
    ].iloc[0]
    if (
        not detailed["detailed_dismissal_comparison"].startswith("PASS")
        or "BOWLER FIGURES MATCH" not in detailed["detailed_dismissal_comparison"]
        or len(detailed_comparisons) != 5
        or not detailed_comparisons["comparison_result"].eq("MATCH").all()
    ):
        raise AssertionError(
            "Detailed match 14094 innings 1 dismissal check failed."
        )

    for file_path in protected_paths:
        if sha256(file_path) != before_hashes[file_path]:
            raise RuntimeError(
                f"Protected source file changed during analysis: {file_path}"
            )
    hash_rows = [
        {
            "source_file": path.relative_to(ROOT).as_posix(),
            "sha256": before_hashes[path],
            "baseline_result": "MATCHES M2.2C SOURCE MANIFEST",
        }
        for path in SOURCE_CSVS
    ]
    hash_rows.append(
        {
            "source_file": archive_relative,
            "sha256": before_hashes[SOURCE_ARCHIVE],
            "baseline_result": "MATCHES M2.2C SOURCE MANIFEST",
        }
    )
    hash_frame = pd.DataFrame(hash_rows)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    category_summary.to_csv(
        OUTPUT_DIR / "dismissal_category_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    cross_tab.to_csv(
        OUTPUT_DIR / "wicket_flag_cross_tabulation.csv",
        index=False,
        encoding="utf-8-sig",
    )
    missing_ids.to_csv(
        OUTPUT_DIR / "missing_dismissed_player_records.csv",
        index=False,
        encoding="utf-8-sig",
    )
    false_flag_ids.to_csv(
        OUTPUT_DIR / "dismissed_player_without_wicket_flag.csv",
        index=False,
        encoding="utf-8-sig",
    )
    credit.to_csv(
        OUTPUT_DIR / "bowler_credit_analysis.csv",
        index=False,
        encoding="utf-8-sig",
    )
    reconciliation.to_csv(
        OUTPUT_DIR / "match_wicket_reconciliation.csv",
        index=False,
        encoding="utf-8-sig",
    )
    hash_frame.to_csv(
        OUTPUT_DIR / "source_hash_verification.csv",
        index=False,
        encoding="utf-8-sig",
    )
    write_report(
        balls,
        category_summary,
        cross_tab,
        missing_ids,
        false_flag_ids,
        credit,
        reconciliation,
        detailed_comparisons,
        hash_frame,
    )
    print(
        f"Categories: {len(category_summary)}; source rows accounted: "
        f"{int(category_summary.occurrences.sum())}; "
        f"anomalies: {len(missing_ids)} missing IDs, "
        f"{len(false_flag_ids)} IDs with false wicket flag; "
        f"scorecards: {len(reconciliation)} innings, "
        f"{int(reconciliation.aggregate_comparison_status.eq('PASS').sum())} pass; "
        f"detailed dismissal lines: {len(detailed_comparisons)} pass."
    )
    print(f"Dismissed-player zero codes: {zero_coded_ids}.")
    print(f"Reports: {OUTPUT_DIR}")
    print("All protected source hashes remained unchanged.")


if __name__ == "__main__":
    main()
