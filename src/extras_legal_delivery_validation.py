"""Profile extras encoding and compare candidate deliveries to scorecards."""

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
M1_HASH_PATH = ROOT / "audit_reports" / "rules_validation" / "source_sha256.csv"
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
M2B_HASH_PATH = (
    ROOT / "audit_reports" / "rules_validation" / "multi_match_reconciliation" / "source_sha256.csv"
)
OUTPUT_DIR = (
    ROOT / "audit_reports" / "rules_validation" / "extras_legal_delivery"
)
SOURCE_CSVS = [
    BALL_PATH,
    MATCHES_PATH,
    ROOT / "data" / "extracted" / "playing_eleven.csv",
    ROOT / "data" / "extracted" / "competition_team_player_mapping.csv",
    ROOT / "data" / "extracted" / "teams.csv",
    COMPETITIONS_PATH,
]
SOURCE_ARCHIVE = ROOT / "data" / "data_pack.zip.zip"

COMBO_COLUMNS = [
    "extras_type",
    "extras1_runs",
    "extras_2_runs",
    "runs",
    "is_four",
    "is_six",
]
LAW_18_URL = (
    "https://lawsofcricket.lords.org/laws-of-cricket/"
    "the-over-scoring-runs-dead-ball-and-extras/scoring-runs"
)
LAW_17_URL = "https://lawsofcricket.lords.org/laws-of-cricket/the-over"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_counts(series: pd.Series) -> str:
    counts = series.value_counts(dropna=False).sort_index().to_dict()
    return json.dumps(counts, ensure_ascii=False, sort_keys=True)


def excel_row(index: int) -> int:
    return index + 2


def find_source_status(value: str) -> tuple[str, str]:
    if value == "wide":
        return (
            "PROBABLE",
            "The category label and repeated source pattern are consistent "
            "with a wide-event label; scorecard wide runs sometimes exceed "
            "the number of such rows.",
        )
    if value == "Overstep":
        return (
            "UNRESOLVED",
            "The local label count does not consistently equal scorecard "
            "No-ball runs and other local labels also occur in innings with "
            "No-ball extras.",
        )
    if value == "None":
        return (
            "UNRESOLVED",
            "This is the literal source string, not an empty cell. The "
            "provider's intended meaning is undocumented.",
        )
    return (
        "UNRESOLVED",
        "The raw category is observed, but its provider definition is "
        "unavailable; its label alone does not establish scoring or legality.",
    )


def possible_interpretation(value: str) -> str:
    if value == "None":
        return (
            "Literal source category `None`; it may be a no-extras marker, "
            "but that interpretation is not confirmed."
        )
    if value == "wide":
        return (
            "Candidate wide-event category based on its label and scorecard "
            "comparison; not a wide-run amount or explicit legal-ball flag."
        )
    if value == "Overstep":
        return (
            "Provider category named `Overstep`; no verified mapping to a "
            "No ball or another event."
        )
    if value == "other":
        return (
            "Provider category `other`; event type and legal-delivery effect "
            "are unknown."
        )
    if value == "Penalty":
        return (
            "Provider category named `Penalty`; the penalty type and amount "
            "are unknown."
        )
    return (
        f"Label suggests {value!r} as a cricket category, but the provider "
        "definition and delivery-level attribution are not documented."
    )


def parse_scorecard_overs(value: str) -> int:
    text = value.strip()
    match = re.fullmatch(r"(\d+)(?:\.(\d))?", text)
    if not match:
        raise ValueError(f"Unrecognized scorecard over notation: {value!r}")
    completed_overs = int(match.group(1))
    balls_in_partial_over = int(match.group(2) or 0)
    if balls_in_partial_over > 5:
        raise ValueError(f"Invalid balls component in scorecard overs: {value!r}")
    return completed_overs * 6 + balls_in_partial_over


def normalize_scorecards() -> pd.DataFrame:
    m2a = pd.read_csv(M2A_SCORECARD_PATH, dtype=str, keep_default_na=False)
    m2b = pd.read_csv(M2B_SCORECARD_PATH, dtype=str, keep_default_na=False)
    normalized: list[dict[str, str]] = []

    required_m2a = {
        "match_id",
        "match_date",
        "innings",
        "source_first_csv_row",
        "source_last_csv_row",
        "scorecard_source_url",
        "scorecard_wides",
        "scorecard_noballs",
        "scorecard_overs",
        "scorecard_extras",
        "scorecard_byes",
        "scorecard_legbyes",
    }
    if not required_m2a.issubset(m2a.columns):
        raise ValueError(
            "M2.2A scorecard report lacks required columns: "
            + ", ".join(sorted(required_m2a.difference(m2a.columns)))
        )
    for _, row in m2a.iterrows():
        normalized.append(
            {
                "match_id": row["match_id"],
                "match_date": row["match_date"],
                "competition": "IPL 2022",
                "format": "T20",
                "innings": row["innings"],
                "scorecard_team": (
                    row["home_team"] if row["innings"] == "1" else row["away_team"]
                ),
                "scorecard_overs": row["scorecard_overs"],
                "scorecard_wides": row["scorecard_wides"],
                "scorecard_noballs": row["scorecard_noballs"],
                "scorecard_byes": row["scorecard_byes"],
                "scorecard_legbyes": row["scorecard_legbyes"],
                "scorecard_extras": row["scorecard_extras"],
                "scorecard_source": "Cricbuzz",
                "scorecard_source_url": row["scorecard_source_url"],
                "source_first_csv_row": row["source_first_csv_row"],
                "source_last_csv_row": row["source_last_csv_row"],
            }
        )

    required_m2b = {
        "match_id",
        "match_date",
        "competition",
        "format",
        "team_1",
        "team_2",
        "innings",
        "source_excel_row_range",
        "scorecard_source",
        "scorecard_url",
        "scorecard_total_wickets_overs",
        "scorecard_extras",
        "scorecard_wide_runs",
        "scorecard_no_ball_runs",
    }
    if not required_m2b.issubset(m2b.columns):
        raise ValueError(
            "M2.2B scorecard report lacks required columns: "
            + ", ".join(sorted(required_m2b.difference(m2b.columns)))
        )
    for _, row in m2b.iterrows():
        if row["innings"] not in {"1", "2"}:
            continue
        overs_match = re.search(
            r"\(([^ ]+) overs\)", row["scorecard_total_wickets_overs"]
        )
        extras_match = re.search(
            r"\(b (\d+), lb (\d+), w (\d+), nb (\d+), p (\d+)\)",
            row["scorecard_extras"],
        )
        if not overs_match or not extras_match:
            raise ValueError(
                f"Could not parse M2.2B scorecard values for "
                f"match {row['match_id']} innings {row['innings']}."
            )
        first_row, last_row = row["source_excel_row_range"].split("-")
        normalized.append(
            {
                "match_id": row["match_id"],
                "match_date": row["match_date"],
                "competition": row["competition"],
                "format": row["format"],
                "innings": row["innings"],
                "scorecard_team": row["scorecard_batting_team"],
                "scorecard_overs": overs_match.group(1),
                "scorecard_wides": row["scorecard_wide_runs"],
                "scorecard_noballs": row["scorecard_no_ball_runs"],
                "scorecard_byes": extras_match.group(1),
                "scorecard_legbyes": extras_match.group(2),
                "scorecard_extras": row["scorecard_extras"],
                "scorecard_source": row["scorecard_source"],
                "scorecard_source_url": row["scorecard_url"],
                "source_first_csv_row": first_row,
                "source_last_csv_row": last_row,
            }
        )

    scorecards = pd.DataFrame(normalized)
    if scorecards.duplicated(["match_id", "innings"]).any():
        duplicates = scorecards.loc[
            scorecards.duplicated(["match_id", "innings"], keep=False),
            ["match_id", "innings"],
        ]
        raise ValueError(
            "Duplicate match/innings scorecard evidence: "
            + duplicates.to_dict("records").__repr__()
        )
    scorecards["scorecard_expected_balls"] = scorecards[
        "scorecard_overs"
    ].map(parse_scorecard_overs)
    if scorecards["scorecard_source_url"].str.strip().eq("").any():
        raise ValueError("A scorecard evidence row has no source URL.")
    return scorecards


def build_combinations(
    balls: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    group = balls.groupby(COMBO_COLUMNS, sort=True, dropna=False)
    combo_rows: list[dict[str, object]] = []
    representative_rows: list[dict[str, object]] = []
    representative_columns = [
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
        "runs",
        "is_four",
        "is_six",
        "extras_type",
        "extras1_runs",
        "extras_2_runs",
    ]

    for key, records in group:
        category, extras1, extras2, runs, is_four, is_six = key
        match_ids = sorted(records["match_id"].unique(), key=lambda item: int(item))
        innings = sorted(records["innings"].unique(), key=lambda item: int(item))
        status, evidence_note = find_source_status(category)
        combo_id = f"C{len(combo_rows) + 1:02d}"
        combo_rows.append(
            {
                "combination_id": combo_id,
                "extras_type_raw": category,
                "extras1_runs_raw": extras1,
                "extras_2_runs_raw": extras2,
                "runs_raw": runs,
                "is_four_raw": is_four,
                "is_six_raw": is_six,
                "source_wide_column_present": False,
                "wide_label_derived_from_extras_type": category == "wide",
                "occurrences": len(records),
                "match_count": len(match_ids),
                "match_ids": ";".join(match_ids),
                "innings_values": ";".join(innings),
                "representative_source_rows": ";".join(
                    str(excel_row(index)) for index in records.index[:3]
                ),
                "possible_interpretation": possible_interpretation(category),
                "evidence_supporting_interpretation": evidence_note
                + " `extras1_runs` is constant within each category label; "
                "this is a code-like pattern, not a confirmed meaning. "
                "`extras_2_runs` and delivery-level `runs` semantics are "
                "not established by the combination alone.",
                "confidence_status": status,
            }
        )
        representative = records.iloc[0]
        representative_rows.append(
            {
                "combination_id": combo_id,
                "source_csv_filename": "ball_by_ball.csv",
                "source_csv_row": excel_row(int(representative.name)),
                "dataframe_index": int(representative.name),
                "wide_field_value": "NOT PRESENT IN SOURCE",
                "wide_label_derived_from_extras_type": category == "wide",
                "combination_occurrences": len(records),
                "combination_match_ids": ";".join(match_ids),
                "possible_interpretation": possible_interpretation(category),
                "confidence_status": status,
                **{
                    column: representative[column]
                    for column in representative_columns
                },
            }
        )

    combinations = pd.DataFrame(combo_rows)
    representatives = pd.DataFrame(representative_rows)
    if combinations["occurrences"].sum() != len(balls):
        raise AssertionError(
            "Extras combinations do not account for every delivery row."
        )
    if len(combinations) != 31:
        raise AssertionError(
            f"Expected 31 previously observed combinations; "
            f"found {len(combinations)}."
        )
    return combinations, representatives


def build_scorecard_comparisons(
    balls: pd.DataFrame, scorecards: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    wide_rows: list[dict[str, object]] = []
    legal_rows: list[dict[str, object]] = []
    for scorecard in scorecards.to_dict("records"):
        match_id = scorecard["match_id"]
        innings = scorecard["innings"]
        group = balls[
            balls["match_id"].eq(match_id) & balls["innings"].eq(innings)
        ]
        if group.empty:
            raise ValueError(
                f"Scorecard match {match_id} innings {innings} has no local rows."
            )
        first_row = excel_row(int(group.index.min()))
        last_row = excel_row(int(group.index.max()))
        if (
            first_row != int(scorecard["source_first_csv_row"])
            or last_row != int(scorecard["source_last_csv_row"])
        ):
            raise AssertionError(
                f"Source row range does not match scorecard evidence for "
                f"{match_id} innings {innings}."
            )

        categories = group["extras_type"]
        wide_mask = categories.eq("wide")
        overstep_mask = categories.eq("Overstep")
        other_mask = categories.eq("other")
        wide_count = int(wide_mask.sum())
        overstep_count = int(overstep_mask.sum())
        other_count = int(other_mask.sum())
        extras2_nonzero = pd.to_numeric(
            group["extras_2_runs"], errors="raise"
        ).gt(0)
        scorecard_wide_runs = int(scorecard["scorecard_wides"])
        scorecard_no_ball_runs = int(scorecard["scorecard_noballs"])
        expected_balls = int(scorecard["scorecard_expected_balls"])
        row_count = len(group)

        wide_rows.append(
            {
                **scorecard,
                "source_csv_filename": "ball_by_ball.csv",
                "source_excel_row_range": f"{first_row}-{last_row}",
                "source_dataframe_index_range": (
                    f"{int(group.index.min())}-{int(group.index.max())}"
                ),
                "source_delivery_rows": row_count,
                "source_extras_type_counts": json_counts(categories),
                "source_wide_label_rows": wide_count,
                "source_overstep_label_rows": overstep_count,
                "source_other_label_rows": other_count,
                "source_extras_2_nonzero_rows": int(extras2_nonzero.sum()),
                "source_wide_label_excel_rows": ";".join(
                    str(excel_row(int(index)))
                    for index in group.index[wide_mask]
                ),
                "source_overstep_label_excel_rows": ";".join(
                    str(excel_row(int(index)))
                    for index in group.index[overstep_mask]
                ),
                "source_other_label_excel_rows": ";".join(
                    str(excel_row(int(index)))
                    for index in group.index[other_mask]
                ),
                "scorecard_wide_runs": scorecard_wide_runs,
                "scorecard_no_ball_runs": scorecard_no_ball_runs,
                "wide_row_count_vs_scorecard_wide_runs": (
                    "EQUAL NUMERICALLY"
                    if wide_count == scorecard_wide_runs
                    else "DIFFERENT UNITS/COUNTS"
                ),
                "overstep_row_count_vs_scorecard_no_ball_runs": (
                    "EQUAL NUMERICALLY"
                    if overstep_count == scorecard_no_ball_runs
                    else "DIFFERENT/NO DIRECT MAPPING"
                ),
                "interpretation_note": (
                    "Source label row counts are event-row counts; scorecard "
                    "wide/No-ball figures are runs. Numeric equality is not "
                    "proof of provider mapping. `wide` is not a source column."
                ),
                "status": "UNRESOLVED",
            }
        )

        candidates = [
            ("all recorded rows", row_count),
            ("exclude extras_type=wide", row_count - wide_count),
            (
                "exclude wide and Overstep labels",
                row_count - wide_count - overstep_count,
            ),
            (
                "exclude wide, Overstep, and other labels",
                row_count - wide_count - overstep_count - other_count,
            ),
        ]
        for rule_name, candidate_count in candidates:
            difference = candidate_count - expected_balls
            legal_rows.append(
                {
                    "match_id": match_id,
                    "match_date": scorecard["match_date"],
                    "competition": scorecard["competition"],
                    "format": scorecard["format"],
                    "innings": innings,
                    "scorecard_batting_team": scorecard["scorecard_team"],
                    "scorecard_source": scorecard["scorecard_source"],
                    "scorecard_source_url": scorecard["scorecard_source_url"],
                    "source_csv_filename": "ball_by_ball.csv",
                    "source_excel_row_range": f"{first_row}-{last_row}",
                    "source_delivery_rows": row_count,
                    "scorecard_overs": scorecard["scorecard_overs"],
                    "scorecard_expected_balls_from_overs": expected_balls,
                    "source_wide_label_rows": wide_count,
                    "source_overstep_label_rows": overstep_count,
                    "source_other_label_rows": other_count,
                    "candidate_rule": rule_name,
                    "candidate_legal_delivery_count": candidate_count,
                    "candidate_minus_scorecard_expected_balls": difference,
                    "candidate_matches_scorecard_total": difference == 0,
                    "status": "DESCRIPTIVE CANDIDATE ONLY",
                    "interpretation_limit": (
                        "A match to the aggregate scorecard over count does "
                        "not identify which source rows were legal. Category "
                        "semantics are not established; over totals do not "
                        "validate the candidate rule outside this selected "
                        "match/innings."
                    ),
                }
            )

    return pd.DataFrame(wide_rows), pd.DataFrame(legal_rows)


def build_bowler_runs_table(balls: pd.DataFrame) -> pd.DataFrame:
    category_specs = [
        ("runs", "Batter-run candidate", "MCC Law 18.10.3", "PROBABLE"),
        ("None", "Literal raw extras_type value", "MCC Law 18", "UNRESOLVED"),
        ("wide", "Wide label", "MCC Laws 17, 18.10.3, 22", "PROBABLE"),
        ("Overstep", "Provider extras_type label", "MCC Laws 17, 18.10.3, 21 if No ball", "UNRESOLVED"),
        ("byes", "Byes label", "MCC Law 18.10.3", "UNRESOLVED"),
        ("legbyes", "Leg-byes label", "MCC Law 18.10.3", "UNRESOLVED"),
        ("Penalty", "Penalty label", "MCC Law 18.10.3", "UNRESOLVED"),
        ("other", "Other label", "MCC Law 18.10.3", "UNRESOLVED"),
    ]
    rows: list[dict[str, object]] = []
    for category, candidate, law, provider_status in category_specs:
        if category == "runs":
            group = balls
            category_label = "FIELD: runs"
        else:
            group = balls[balls["extras_type"].eq(category)]
            category_label = f"extras_type={category!r}"
        row_ids = [str(excel_row(int(index))) for index in group.index[:5]]
        if category == "wide":
            law_rule = (
                "MCC states bowler is debited all runs scored as Wides."
            )
            blockers = (
                "Provider `wide` label is probable, not documented. No source "
                "wide-run amount field exists; extras1_runs is category-constant "
                "and extras_2_runs is unresolved. The source has no `wide` "
                "boolean column."
            )
        elif category == "Overstep":
            law_rule = (
                "If the source event is a No ball, MCC Law 18.10.3 debits "
                "No-ball extras; source mapping is unverified."
            )
            blockers = (
                "Overstep-to-No-ball mapping is unresolved; observed row "
                "counts do not consistently equal scorecard No-ball run totals."
            )
        elif category in {"byes", "legbyes"}:
            law_rule = (
                "MCC Law 18.10.3 does not list Byes or Leg byes among runs "
                "debited to the bowler."
            )
            blockers = (
                "Provider category meaning and run amounts are unverified; "
                "extras fields do not provide a confirmed amount."
            )
        elif category == "Penalty":
            law_rule = (
                "MCC Law 18.10.3's bowler debit list does not include Penalty "
                "runs."
            )
            blockers = (
                "One source row uses this label, but the provider event and "
                "amount are undocumented."
            )
        elif category == "other":
            law_rule = (
                "No category-specific bowler attribution can be assigned "
                "without knowing what the provider label contains."
            )
            blockers = (
                "Some `other` rows have nonzero extras_2_runs; neither field's "
                "meaning is known."
            )
        elif category == "None":
            law_rule = (
                "MCC Law 18.10.3 debits runs scored by the striker, but this "
                "raw label is not established as a no-extras marker."
            )
            blockers = (
                "Preserve the literal `None`; no source documentation "
                "establishes its semantics."
            )
        else:
            law_rule = (
                "MCC Law 18.10.3 debits striker runs, No-ball extras, and "
                "Wide runs."
            )
            blockers = (
                "The M2.2B scorecard reconciliation supports `runs` as batter "
                "runs at innings level, not definitive delivery-level "
                "attribution or every exception."
            )
        rows.append(
            {
                "source_category_or_field": category_label,
                "candidate_event_interpretation": candidate,
                "source_row_count": len(group),
                "source_extras1_runs_values": json_counts(group["extras1_runs"])
                if len(group)
                else "{}",
                "source_extras_2_runs_values": json_counts(
                    group["extras_2_runs"]
                )
                if len(group)
                else "{}",
                "source_runs_values": json_counts(group["runs"])
                if len(group)
                else "{}",
                "source_four_flag_values": json_counts(group["is_four"])
                if len(group)
                else "{}",
                "source_six_flag_values": json_counts(group["is_six"])
                if len(group)
                else "{}",
                "representative_source_excel_rows": ";".join(row_ids),
                "mcc_rule_reference": law,
                "mcc_rule_status": "CONFIRMED AS RULE, NOT PROVIDER MAPPING",
                "law_level_bowler_attribution": law_rule,
                "provider_encoding_status": provider_status,
                "dataset_evidence_and_blockers": blockers,
                "bowler_runs_implementation_decision": (
                    "DO NOT IMPLEMENT: a validated delivery-level amount for "
                    "striker runs, No-ball extras, and Wide runs is unavailable."
                ),
            }
        )
    rows.append(
        {
            "source_category_or_field": "OVERALL DATA SUFFICIENCY",
            "candidate_event_interpretation": (
                "Assess whether bowler-conceded runs can be calculated"
            ),
            "source_row_count": len(balls),
            "source_extras1_runs_values": "",
            "source_extras_2_runs_values": "",
            "source_runs_values": "",
            "source_four_flag_values": "",
            "source_six_flag_values": "",
            "representative_source_excel_rows": "",
            "mcc_rule_reference": LAW_18_URL,
            "mcc_rule_status": "CONFIRMED AS RULE, NOT PROVIDER MAPPING",
            "law_level_bowler_attribution": (
                "MCC Law 18.10.3: debit the bowler with runs scored by the "
                "striker, No-ball extras, and Wides."
            ),
            "provider_encoding_status": "UNRESOLVED",
            "dataset_evidence_and_blockers": (
                "`runs` is probable as batter runs at innings scope; the "
                "`wide` label is probable as an event label; Overstep, "
                "extras1_runs, extras_2_runs, and `other` are unresolved. "
                "Aggregate scorecard extras do not attribute extras to "
                "individual bowlers/deliveries. Penalty/Bye/Leg-bye amounts "
                "are not validated in the source."
            ),
            "bowler_runs_implementation_decision": (
                "UNRESOLVED; insufficient validated delivery-level fields. "
                "Do not compute a formula."
            ),
        }
    )
    return pd.DataFrame(rows)


def write_report(
    balls: pd.DataFrame,
    combinations: pd.DataFrame,
    scorecards: pd.DataFrame,
    wide_analysis: pd.DataFrame,
    legal_validation: pd.DataFrame,
    bowler_investigation: pd.DataFrame,
    hash_rows: pd.DataFrame,
) -> None:
    category_counts = balls["extras_type"].value_counts(dropna=False).sort_index()
    extras2_nonzero = pd.to_numeric(balls["extras_2_runs"], errors="raise").gt(0)
    wide_equal = int(
        wide_analysis["wide_row_count_vs_scorecard_wide_runs"]
        .eq("EQUAL NUMERICALLY")
        .sum()
    )
    overstep_equal = int(
        wide_analysis["overstep_row_count_vs_scorecard_no_ball_runs"]
        .eq("EQUAL NUMERICALLY")
        .sum()
    )
    rule_counts = legal_validation.groupby("candidate_rule")[
        "candidate_matches_scorecard_total"
    ].agg(["sum", "count"])

    lines = [
        "# M2.2C Extras and Legal-Delivery Investigation",
        "",
        "## Scope and source preservation",
        "",
        "This report profiles raw values from the original `ball_by_ball.csv` "
        "with `keep_default_na=False`. No source row was changed, removed, "
        "normalized, or imputed. The literal string `None` remains distinct "
        "from an empty cell. The provided file has no `wide` column; `wide` "
        "is an observed value in `extras_type`. Evidence therefore records "
        "both the absent-column fact and a clearly labeled flag derived only "
        "as `extras_type == 'wide'`.",
        "",
        f"- Delivery rows: **{len(balls):,}**.",
        f"- Observed distinct combinations of `extras_type`, `extras1_runs`, "
        "`extras_2_runs`, `runs`, `is_four`, and `is_six`: "
        f"**{len(combinations)}**, accounting for "
        f"**{int(combinations.occurrences.sum()):,}** rows.",
        f"- Nonzero `extras_2_runs`: **{int(extras2_nonzero.sum())}** rows. "
        "This co-occurrence does not prove that more than one extras category "
        "was awarded.",
        f"- Scorecard comparisons: **{len(scorecards)}** regulation innings "
        f"across **{scorecards.match_id.nunique()}** matches in T20 and T20I, "
        "using the previously recorded M2.2A/M2.2B scorecard URLs.",
        "",
        "## Observed extras categories",
        "",
        "| Raw `extras_type` value | Rows | Provider status |",
        "|---|---:|---|",
    ]
    for category, count in category_counts.items():
        status, _ = find_source_status(category)
        lines.append(f"| `{category}` | {int(count):,} | {status} |")

    lines.extend(
        [
            "",
            "The raw `extras1_runs` value is constant within each category in "
            "this extract (literal `None`→6, `wide`→2, `legbyes`→3, "
            "`Overstep`→1, `byes`→4, `other`→5, `Penalty`→7). This is a "
            "confirmed data pattern and a **PROBABLE** code-like role, not a "
            "definition of those numbers. `extras_2_runs` is 0 on 200,963 "
            "rows, 1 on 20, and 4 on 16. Its 36 nonzero rows occur with "
            "literal `None` (1), `Overstep` (21), and `other` (14); all have "
            "`runs=0` and false boundary flags. Meaning remains "
            "**UNRESOLVED**.",
            "",
            "The six-field grouping includes all observed run and boundary "
            "patterns. The 31 combinations, occurrence counts, complete "
            "match-ID lists, innings values, representative locators, and "
            "bounded interpretations are in `extras_combinations.csv`. One "
            "exact original delivery row per combination is in "
            "`extras_representative_records.csv`.",
            "",
            "The source has one single-valued `extras_type` per row, so `wide` "
            "and `Overstep` labels do not overlap as values in that column. "
            "The 36 nonzero `extras_2_runs` records coexist with those labels "
            "on the same row, but this only establishes field co-occurrence; "
            "it does not establish multiple awarded extras.",
            "",
            "M2.2B independently reconciled local `runs` sums to scorecard "
            "batter-run subtotals in 16 innings; that supports `runs` as "
            "**PROBABLE** batter runs at innings scope. It does not settle "
            "row-level allocation for every extras combination or make "
            "`extras_2_runs` a runs amount.",
            "",
            "## Wide and Overstep comparisons",
            "",
            f"Across {len(wide_analysis)} scorecard innings, source "
            "`extras_type=wide` row counts equalled the scorecard's aggregate "
            f"wide-run total in {wide_equal} innings. Equality in one innings "
            "is a numeric coincidence between event-row count and a run "
            "total; in other innings scorecard wide runs exceed source wide "
            "rows. The label is **PROBABLE** as identifying a wide-related "
            "event, but row count cannot be used as the runs amount.",
            "",
            f"Source `Overstep` row counts numerically equalled scorecard "
            f"No-ball extras in {overstep_equal} innings. The relationship "
            "was not consistent: scorecards show No-ball extras in some "
            "innings with no `Overstep` rows, and some innings have "
            "`other` rows alongside No-ball extras. Other numeric matches "
            "do not establish the provider mapping. **Overstep remains "
            "UNRESOLVED and is not classified as a No ball.**",
            "",
            "Exact match/innings values, source row ranges, individual "
            "wide/Overstep/other row locators, extras summaries, and all "
            "scorecard URLs are in `wide_overstep_analysis.csv`.",
            "",
            "## Candidate legal-delivery counts",
            "",
            "Scorecard overs are written in over notation (for example, "
            "`19.2` means 19 completed overs plus 2 balls) and are converted "
            "to an aggregate ball count for comparison only. Candidate rules "
            "do not establish row-level legality.",
            "",
            "| Candidate rule | Innings matching scorecard over total | Innings compared |",
            "|---|---:|---:|",
        ]
    )
    for candidate_rule, values in rule_counts.iterrows():
        lines.append(
            f"| {candidate_rule} | {int(values['sum'])} | "
            f"{int(values['count'])} |"
        )

    lines.extend(
        [
            "",
            "| Match | Innings | Source rows | Scorecard overs / expected balls | All rows | Exclude wide | Exclude wide + Overstep | Exclude wide + Overstep + other |",
            "|---:|---:|---|---|---:|---:|---:|---:|",
        ]
    )
    first_rule = legal_validation[
        legal_validation["candidate_rule"].eq("all recorded rows")
    ]
    for row in first_rule.itertuples():
        related = legal_validation[
            legal_validation["match_id"].eq(row.match_id)
            & legal_validation["innings"].eq(row.innings)
        ].set_index("candidate_rule")
        counts = {
            key: int(related.loc[key, "candidate_legal_delivery_count"])
            for key in related.index
        }
        lines.append(
            f"| {row.match_id} | {row.innings} | "
            f"{row.source_excel_row_range} | {row.scorecard_overs} / "
            f"{row.scorecard_expected_balls_from_overs} | "
            f"{counts['all recorded rows']} | "
            f"{counts['exclude extras_type=wide']} | "
            f"{counts['exclude wide and Overstep labels']} | "
            f"{counts['exclude wide, Overstep, and other labels']} |"
        )
    lines.extend(
        [
            "",
            "Excluding only `wide` does not match scorecard over counts in "
            "every innings. Excluding `wide` and `Overstep` still leaves "
            "exceptions. Excluding `other` as well happens to match the "
            "aggregate overs in this selected sample, but `other` semantics "
            "are unknown and this would be a sample-fitted rule, not a "
            "validated legal-delivery formula. Do not apply any of these "
            "candidate rules to player metrics.",
            "",
            "**Conclusion: legal deliveries cannot currently be identified "
            "reliably from `extras_type`/the absent `wide` field.** The 18 "
            "innings cover two formats, multiple seasons, and several "
            "scorecard extras patterns, but are still a selected sample. "
            "There is no explicit legal-ball/no-ball field; provider "
            "definitions and event-level validation remain necessary.",
            "",
            "## Bowler-conceded runs",
            "",
            f"[MCC Law 18 - Scoring Runs]({LAW_18_URL}) section 18.10.3 says "
            "the bowler is debited with all runs scored by the striker, all "
            "runs scored as No-ball extras, and all runs scored as Wides. "
            "This is a rule-level statement; it does not define the provider "
            "fields. MCC [Law 17]({LAW_17_URL}) governs valid balls; MCC "
            "Laws 21 and 22 address No balls and Wides respectively.",
            "",
            "Under that rule, Byes, Leg byes, and Penalty runs are not listed "
            "as bowler debits. Whether a source row labeled `byes`, "
            "`legbyes`, `Penalty`, or `Overstep` actually encodes that event "
            "is a separate provider question. `other` is wholly unknown.",
            "",
            "The source does not provide a validated per-delivery Wide "
            "amount, No-ball amount, or a confirmed `Overstep`/No-ball "
            "mapping. `extras1_runs` is category-constant and "
            "`extras_2_runs` is unresolved; neither is approved as a run "
            "amount. Scorecard extras are aggregate innings totals and do "
            "not assign runs to a bowler or delivery.",
            "",
            "**Conclusion: bowler-conceded runs cannot be calculated "
            "reliably from the present fields.** No formula is implemented "
            "or recommended. The category/field assessment and rule sources "
            "are in `bowler_runs_conceded_investigation.csv`.",
            "",
            "## Status summary",
            "",
            "- **CONFIRMED:** 31 observed combinations account for all "
            "200,999 records; the raw `wide` boolean column is absent; the "
            "single `extras_type` value is mutually exclusive across source "
            "rows; M2.2B scorecard totals support `runs` at innings scope; "
            "MCC Laws 17/18/21/22 say how valid balls and bowler debit rules "
            "work when event types are known.",
            "- **PROBABLE:** `runs` is batter runs at innings scope; "
            "`extras1_runs` is code-like; `extras_type=wide` identifies a "
            "wide-related event, but not the wide-run amount.",
            "- **UNRESOLVED:** meanings of `extras_2_runs`, `Overstep`, "
            "`other`, and the numeric extras fields; complete extras "
            "attribution; row-level legal delivery; and bowler-conceded "
            "runs.",
            "- **NOT APPLICABLE:** none of the requested event categories is "
            "declared irrelevant to the intended calculations. A physical "
            "`wide` column is not applicable because it is not present; use "
            "the raw `extras_type` label without renaming it to a source "
            "boolean.",
            "",
            "## Integrity verification",
            "",
            "The script checks every selected scorecard row range against the "
            "original CSV, compares all six source CSV SHA-256 values with "
            "the existing M2 baseline, and verifies the M2.2B archive hash. "
            "The generated `source_hash_verification.csv` records the "
            "baseline check. Original source hashes are unchanged.",
            "",
            "| Source | SHA-256 | Baseline result |",
            "|---|---|---|",
        ]
    )
    for row in hash_rows.itertuples():
        lines.append(
            f"| `{row.source_file}` | `{row.sha256}` | {row.baseline_result} |"
        )
    (OUTPUT_DIR / "extras_legal_delivery_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    required_files = [
        *SOURCE_CSVS,
        SOURCE_ARCHIVE,
        M1_HASH_PATH,
        M2A_SCORECARD_PATH,
        M2B_SCORECARD_PATH,
        M2B_HASH_PATH,
    ]
    missing = [str(path) for path in required_files if not path.is_file()]
    if missing:
        raise FileNotFoundError("Required evidence is missing: " + ", ".join(missing))

    hashes_before = {
        path: sha256(path) for path in [*SOURCE_CSVS, SOURCE_ARCHIVE]
    }
    baseline = pd.read_csv(M1_HASH_PATH, dtype=str, keep_default_na=False)
    m2b_hashes = pd.read_csv(M2B_HASH_PATH, dtype=str, keep_default_na=False)
    if not {"source_csv", "sha256"}.issubset(baseline.columns):
        raise ValueError("M2 baseline hash file is missing source_csv/sha256.")
    if not {"source_file", "sha256"}.issubset(m2b_hashes.columns):
        raise ValueError("M2.2B hash file is missing source_file/sha256.")

    baseline_hash_map = dict(zip(baseline["source_csv"], baseline["sha256"]))
    m2b_hash_map = dict(zip(m2b_hashes["source_file"], m2b_hashes["sha256"]))
    if len(SOURCE_CSVS) != 6:
        raise AssertionError(f"Expected six source CSVs, got {len(SOURCE_CSVS)}.")
    for path in SOURCE_CSVS:
        if baseline_hash_map.get(path.name) != hashes_before[path]:
            raise RuntimeError(
                f"{path.name} hash differs from the original M2 baseline."
            )
    archive_relative = SOURCE_ARCHIVE.relative_to(ROOT).as_posix()
    if m2b_hash_map.get(archive_relative) != hashes_before[SOURCE_ARCHIVE]:
        raise RuntimeError("Archive hash differs from the M2.2B source manifest.")

    balls = pd.read_csv(BALL_PATH, dtype=str, keep_default_na=False)
    required_columns = set(COMBO_COLUMNS).union(
        {
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
        }
    )
    absent_columns = required_columns.difference(balls.columns)
    if absent_columns:
        raise ValueError(
            "ball_by_ball.csv is missing required columns: "
            + ", ".join(sorted(absent_columns))
        )
    if "wide" in balls.columns:
        raise AssertionError(
            "The inspected schema changed: re-evaluate the source wide column."
        )

    matches = pd.read_csv(MATCHES_PATH, dtype=str, keep_default_na=False)
    competitions = pd.read_csv(
        COMPETITIONS_PATH, dtype=str, keep_default_na=False
    )
    scorecards = normalize_scorecards()
    match_metadata = matches[
        ["match_id", "comp_id", "home_team", "away_team", "match_date"]
    ].merge(
        competitions[["comp_id", "comp_name", "match_format"]],
        on="comp_id",
        how="left",
        validate="many_to_one",
    )
    scorecards = scorecards.drop(
        columns=["competition", "format"], errors="ignore"
    ).merge(
        match_metadata,
        on=["match_id", "match_date"],
        how="left",
        validate="many_to_one",
    )
    if scorecards["comp_name"].eq("").any() or scorecards["comp_name"].isna().any():
        raise AssertionError("A scorecard match did not map to competition metadata.")
    scorecards = scorecards.rename(
        columns={"comp_name": "competition", "match_format": "format"}
    )

    combinations, representatives = build_combinations(balls)
    wide_analysis, legal_validation = build_scorecard_comparisons(
        balls, scorecards
    )
    bowler_investigation = build_bowler_runs_table(balls)

    hashes_after = {
        path: sha256(path) for path in [*SOURCE_CSVS, SOURCE_ARCHIVE]
    }
    if hashes_before != hashes_after:
        raise RuntimeError("A protected source file changed during analysis.")
    hash_rows = []
    for path in SOURCE_CSVS:
        hash_rows.append(
            {
                "source_file": path.relative_to(ROOT).as_posix(),
                "sha256": hashes_before[path],
                "baseline_result": "MATCHES M2 SOURCE MANIFEST",
            }
        )
    hash_rows.append(
        {
            "source_file": archive_relative,
            "sha256": hashes_before[SOURCE_ARCHIVE],
            "baseline_result": "MATCHES M2.2B SOURCE MANIFEST",
        }
    )
    hash_frame = pd.DataFrame(hash_rows)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combinations.to_csv(
        OUTPUT_DIR / "extras_combinations.csv",
        index=False,
        encoding="utf-8-sig",
    )
    representatives.to_csv(
        OUTPUT_DIR / "extras_representative_records.csv",
        index=False,
        encoding="utf-8-sig",
    )
    saved_representatives = pd.read_csv(
        OUTPUT_DIR / "extras_representative_records.csv",
        dtype=str,
        keep_default_na=False,
    )
    for row in saved_representatives.to_dict("records"):
        source_index = int(row["dataframe_index"])
        if excel_row(source_index) != int(row["source_csv_row"]):
            raise AssertionError(
                f"Representative locator mismatch for index {source_index}."
            )
        source_record = balls.iloc[source_index]
        for column in COMBO_COLUMNS + [
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
        ]:
            if row[column] != source_record[column]:
                raise AssertionError(
                    f"Representative value mismatch at CSV row "
                    f"{row['source_csv_row']}, field {column}."
                )
    wide_analysis.to_csv(
        OUTPUT_DIR / "wide_overstep_analysis.csv",
        index=False,
        encoding="utf-8-sig",
    )
    legal_validation.to_csv(
        OUTPUT_DIR / "legal_delivery_validation.csv",
        index=False,
        encoding="utf-8-sig",
    )
    bowler_investigation.to_csv(
        OUTPUT_DIR / "bowler_runs_conceded_investigation.csv",
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
        combinations,
        scorecards,
        wide_analysis,
        legal_validation,
        bowler_investigation,
        hash_frame,
    )
    print(
        f"Generated {len(combinations)} combinations, "
        f"{len(representatives)} representative rows, "
        f"{len(wide_analysis)} scorecard innings, and "
        f"{len(legal_validation)} candidate-ball comparisons."
    )
    print(f"Reports: {OUTPUT_DIR}")
    print("All protected source hashes remained unchanged.")


if __name__ == "__main__":
    main()
