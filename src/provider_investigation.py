"""Generate read-only evidence for unresolved provider run and delivery fields."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "extracted"
OUTPUT_DIR = ROOT / "audit_reports" / "rules_validation" / "provider_investigation"

SCORECARD_SOURCE = (
    "https://www.cricbuzz.com/live-cricket-scorecard/45981/"
    "rr-vs-lsg-20th-match-indian-premier-league-2022"
)
# Scorecard values are transcribed from this independent source, not source CSVs.
SCORECARD_INNINGS = {
    1: {
        "scorecard_total_runs": 165,
        "scorecard_wickets": 6,
        "scorecard_batter_runs": 156,
        "scorecard_extras": 9,
        "scorecard_byes": 0,
        "scorecard_legbyes": 3,
        "scorecard_wides": 6,
        "scorecard_noballs": 0,
        "scorecard_penalty": 0,
        "scorecard_overs": 20,
    },
    2: {
        "scorecard_total_runs": 162,
        "scorecard_wickets": 8,
        "scorecard_batter_runs": 157,
        "scorecard_extras": 5,
        "scorecard_byes": 0,
        "scorecard_legbyes": 1,
        "scorecard_wides": 4,
        "scorecard_noballs": 0,
        "scorecard_penalty": 0,
        "scorecard_overs": 20,
    },
}

EXAMPLE_FIELDS = [
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
    "dismissal_type",
    "dismissed_player_id",
    "extras_type",
    "extras1_runs",
    "extras_2_runs",
    "delivery_ist_time",
]


def read_source(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, keep_default_na=False, low_memory=False)


def write_cross_tabulation(deliveries: pd.DataFrame) -> None:
    result = (
        deliveries.groupby(
            ["extras_type", "extras1_runs", "extras_2_runs"],
            dropna=False,
            sort=True,
        )
        .size()
        .reset_index(name="row_count")
    )
    result.to_csv(OUTPUT_DIR / "extras_cross_tabulation.csv", index=False)


def write_runs_analysis(deliveries: pd.DataFrame) -> None:
    data = deliveries.copy()
    data["is_four_true"] = data["is_four"].map(
        lambda value: value is True or str(value).strip().lower() == "true"
    )
    data["is_six_true"] = data["is_six"].map(
        lambda value: value is True or str(value).strip().lower() == "true"
    )
    result = (
        data.groupby(["extras_type", "runs"], dropna=False, sort=True)
        .agg(
            row_count=("match_id", "size"),
            is_four_true_rows=("is_four_true", "sum"),
            is_six_true_rows=("is_six_true", "sum"),
            extras_2_runs_values=(
                "extras_2_runs",
                lambda values: "|".join(sorted(set(map(str, values)))),
            ),
        )
        .reset_index()
    )
    result.to_csv(OUTPUT_DIR / "runs_extras_analysis.csv", index=False)


def write_examples(deliveries: pd.DataFrame) -> int:
    selected = deliveries[deliveries["extras_type"].isin(["wide", "Overstep"])].copy()
    selected.insert(0, "source_csv_filename", "ball_by_ball.csv")
    selected.insert(1, "dataframe_index", selected.index)
    selected.insert(2, "source_csv_row", selected.index + 2)
    fields = [
        "source_csv_filename",
        "source_csv_row",
        "dataframe_index",
        *[field for field in EXAMPLE_FIELDS if field in selected.columns],
    ]
    selected[fields].to_csv(
        OUTPUT_DIR / "wide_overstep_examples.csv",
        index=False,
    )
    return len(selected)


def write_scorecard_reconciliation(
    deliveries: pd.DataFrame,
    matches: pd.DataFrame,
) -> None:
    match_id = 14113
    match = matches[matches["match_id"] == match_id]
    if len(match) != 1:
        raise ValueError(f"Expected one matches.csv row for match_id={match_id}")

    records: list[dict[str, object]] = []
    for innings, scorecard in SCORECARD_INNINGS.items():
        rows = deliveries[
            (deliveries["match_id"] == match_id)
            & (deliveries["innings"] == innings)
        ]
        if rows.empty:
            raise ValueError(f"No source deliveries for match {match_id}, innings {innings}")
        wide_rows = int((rows["extras_type"] == "wide").sum())
        overstep_rows = int((rows["extras_type"] == "Overstep").sum())
        legal_candidate = len(rows) - wide_rows
        record: dict[str, object] = {
            "match_id": match_id,
            "match_date": match.iloc[0]["match_date"],
            "home_team": match.iloc[0]["home_team"],
            "away_team": match.iloc[0]["away_team"],
            "result": match.iloc[0]["result"],
            "innings": innings,
            "source_csv_filename": "ball_by_ball.csv",
            "source_first_csv_row": int(rows.index.min()) + 2,
            "source_last_csv_row": int(rows.index.max()) + 2,
            "source_delivery_rows": len(rows),
            "source_runs_sum": int(pd.to_numeric(rows["runs"]).sum()),
            "source_is_wicket_count": int(
                rows["is_wicket"].map(
                    lambda value: value is True
                    or str(value).strip().lower() == "true"
                ).sum()
            ),
            "source_extras_type_None_rows": int((rows["extras_type"] == "None").sum()),
            "source_wide_rows": wide_rows,
            "source_legbyes_rows": int((rows["extras_type"] == "legbyes").sum()),
            "source_Overstep_rows": overstep_rows,
            "source_other_extras_rows": int(
                (~rows["extras_type"].isin(["None", "wide", "legbyes", "Overstep"])).sum()
            ),
            "source_extras_2_runs_sum": int(pd.to_numeric(rows["extras_2_runs"]).sum()),
            "source_max_over_ball_num": int(pd.to_numeric(rows["over_ball_num"]).max()),
            "scorecard_source_url": SCORECARD_SOURCE,
            "scorecard_total_runs": scorecard["scorecard_total_runs"],
            "scorecard_wickets": scorecard["scorecard_wickets"],
            "scorecard_batter_runs": scorecard["scorecard_batter_runs"],
            "scorecard_extras": scorecard["scorecard_extras"],
            "scorecard_byes": scorecard["scorecard_byes"],
            "scorecard_legbyes": scorecard["scorecard_legbyes"],
            "scorecard_wides": scorecard["scorecard_wides"],
            "scorecard_noballs": scorecard["scorecard_noballs"],
            "scorecard_penalty": scorecard["scorecard_penalty"],
            "scorecard_overs": scorecard["scorecard_overs"],
            "source_runs_match_scorecard_batter_runs": (
                int(pd.to_numeric(rows["runs"]).sum())
                == scorecard["scorecard_batter_runs"]
            ),
            "source_runs_match_scorecard_team_total": (
                int(pd.to_numeric(rows["runs"]).sum())
                == scorecard["scorecard_total_runs"]
            ),
            "source_wickets_match_scorecard": (
                int(
                    rows["is_wicket"].map(
                        lambda value: value is True
                        or str(value).strip().lower() == "true"
                    ).sum()
                )
                == scorecard["scorecard_wickets"]
            ),
            "wide_exclusion_candidate_balls": legal_candidate,
            "candidate_balls_match_scorecard_overs": (
                legal_candidate == scorecard["scorecard_overs"] * 6
            ),
        }
        records.append(record)

    pd.DataFrame(records).to_csv(
        OUTPUT_DIR / "scorecard_reconciliation.csv",
        index=False,
    )


def write_summary(deliveries: pd.DataFrame, example_rows: int) -> None:
    category_counts = deliveries["extras_type"].value_counts(dropna=False).to_dict()
    extras1_map = (
        deliveries.groupby("extras_type", dropna=False)["extras1_runs"]
        .agg(lambda values: sorted(set(map(str, values))))
        .to_dict()
    )
    extras2_counts = (
        deliveries["extras_2_runs"].value_counts(dropna=False).sort_index().to_dict()
    )
    summary = f"""# Provider evidence summary

## Scope and reproducibility

Generated by [`../../../src/provider_investigation.py`](../../../src/provider_investigation.py)
from the original `data/extracted/ball_by_ball.csv` and `matches.csv`, read
with pandas `keep_default_na=False`. Source CSVs are read-only. CSV row
locators include the header row (`source_csv_row = dataframe_index + 2`).

## Source observations

- Delivery rows inspected: {len(deliveries)}.
- `extras_type` frequencies: `{category_counts}`.
- Distinct `extras1_runs` values by raw `extras_type`: `{extras1_map}`.
- `extras_2_runs` frequency: `{extras2_counts}`.
- A separate `wide` column: {"present" if "wide" in deliveries.columns else "not present"}.
- Explicit no-ball or legal-delivery flag: not present in the inspected
  `ball_by_ball.csv` columns.
- Exact source records for all `wide` and `Overstep` rows:
  `wide_overstep_examples.csv` ({example_rows} rows).

The stable one-to-one pairing of raw category labels and `extras1_runs` is
consistent with a category/code field, not proof of its provider definition.
The label `None` remains literal text; no empty value is coerced to zero.

## Independent scorecard comparison

`scorecard_reconciliation.csv` compares both innings of match 14113
(Rajasthan Royals v Lucknow Super Giants, 2022-04-10) with the Cricbuzz
scorecard linked in that file. Scorecard figures in this script are transcribed
from that page; the script does not download or alter source data. In both
innings, the source `runs` sum matches the scorecard batter-run total, not the
team total. Source delivery rows less
the count of `extras_type=wide` rows equal 120 in each innings, matching 20
six-ball overs in that scorecard. The innings have no `Overstep` rows.

This is independent corroboration for one match only. It supports, but does
not establish for every competition, extras category, or unusual event, that
`runs` records batter runs and the `wide` label identifies an invalid delivery.
The match does not test the meaning of `Overstep`; no `Overstep` row is
reclassified as a No ball.

## Conclusions and limits

- `runs`: **PROBABLE** as batter runs dataset-wide; the tested match's two
  innings are directly reconciled, but broader/provider validation is absent.
- `extras1_runs`: **PROBABLE** as a category/code field; the code meanings
  remain unknown.
- `extras_2_runs`: **UNRESOLVED**; its nonzero values do not define its role,
  and it is zero in the scorecard-tested match despite recorded extras.
- `extras_type=wide`: **PROBABLE** as a Wide event label; the sample
  reconciliation supports its treatment in that match.
- `extras_type=Overstep`: **UNRESOLVED**; neither its event meaning nor
  validity for legal-ball counting is established.
- Legal-delivery reconstruction across the dataset: **UNRESOLVED**. The
  candidate wide exclusion matched this one match, but the dataset has no
  explicit legal-ball flag and the `Overstep` and other categories are not
  resolved.

Do not implement runs, extras, bowler-conceded runs, balls faced, legal balls,
or economy calculations from these findings alone.
"""
    (OUTPUT_DIR / "provider_evidence_summary.md").write_text(
        summary,
        encoding="utf-8",
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    deliveries = read_source(DATA_DIR / "ball_by_ball.csv")
    matches = read_source(DATA_DIR / "matches.csv")

    required = {
        "match_id",
        "innings",
        "over_ball_num",
        "runs",
        "extras_type",
        "extras1_runs",
        "extras_2_runs",
        "is_four",
        "is_six",
    }
    missing = required.difference(deliveries.columns)
    if missing:
        raise ValueError(f"Required source columns are absent: {sorted(missing)}")

    write_cross_tabulation(deliveries)
    write_runs_analysis(deliveries)
    example_rows = write_examples(deliveries)
    write_scorecard_reconciliation(deliveries, matches)
    write_summary(deliveries, example_rows)
    print(f"Provider investigation evidence written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
