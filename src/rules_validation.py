"""Profile cricket-rule-related fields without changing the source CSVs."""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path

import pandas as pd


DELIVERY_FIELDS = [
    "runs",
    "extras1_runs",
    "extras_2_runs",
    "extras_type",
    "is_four",
    "is_six",
    "is_wicket",
    "dismissal_type_id",
    "dismissal_type",
    "dismissed_player_id",
    "innings",
    "overid",
    "over_ball_num",
    "innings_ball_num",
    "bowl_speed",
    "delivery_ist_time",
]
LINEUP_FIELDS = [
    "batting_order",
    "is_played",
    "is_captain",
    "is_wk",
    "is_impact",
    "is_impact_off",
]
MATCH_FIELDS = [
    "man_of_the_match",
    "revised_target",
    "first_inn_revised_overs",
    "second_inn_revised_overs",
    "match_date",
    "result",
]


def read_source(data_dir: Path, filename: str) -> pd.DataFrame:
    return pd.read_csv(
        data_dir / filename,
        keep_default_na=False,
        low_memory=False,
    )


def source_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def value_text(value: object) -> str:
    return "<EMPTY>" if value == "" else str(value)


def field_distributions(
    frames: dict[str, pd.DataFrame],
    output_path: Path,
) -> None:
    records: list[dict[str, object]] = []
    field_sets = {
        "ball_by_ball.csv": DELIVERY_FIELDS,
        "playing_eleven.csv": LINEUP_FIELDS,
        "matches.csv": MATCH_FIELDS,
    }
    for filename, fields in field_sets.items():
        frame = frames[filename]
        for field in fields:
            if field not in frame.columns:
                continue
            if filename == "ball_by_ball.csv" and field == "delivery_ist_time":
                suffix_counts = Counter(
                    "UTC" if str(value).endswith("UTC") else "non-UTC suffix"
                    for value in frame[field]
                )
                records.extend(
                    {
                        "source_csv": filename,
                        "field": "delivery_ist_time_suffix",
                        "observed_value": value,
                        "frequency": frequency,
                    }
                    for value, frequency in sorted(suffix_counts.items())
                )
                per_timestamp = frame[field].value_counts().value_counts()
                records.extend(
                    {
                        "source_csv": filename,
                        "field": "delivery_ist_time_rows_per_distinct_value",
                        "observed_value": f"{int(rows_per_value)} row(s) per timestamp",
                        "frequency": int(distinct_timestamps),
                    }
                    for rows_per_value, distinct_timestamps in per_timestamp.items()
                )
                continue
            counts = Counter(value_text(value) for value in frame[field])
            records.extend(
                {
                    "source_csv": filename,
                    "field": field,
                    "observed_value": value,
                    "frequency": frequency,
                }
                for value, frequency in sorted(counts.items())
            )
    pd.DataFrame(records).to_csv(output_path, index=False, encoding="utf-8-sig")


def add_representative(
    selected: dict[int, list[str]],
    index: int,
    reason: str,
) -> None:
    selected.setdefault(index, [])
    if reason not in selected[index]:
        selected[index].append(reason)


def representative_records(
    frame: pd.DataFrame,
    filename: str,
    selected: dict[int, list[str]],
    output_path: Path,
) -> None:
    rows = []
    for index, reasons in sorted(selected.items()):
        record = frame.iloc[index].to_dict()
        record = {
            "source_csv": filename,
            "source_csv_row": index + 2,
            "dataframe_index": index,
            "selection_reason": "; ".join(reasons),
            **record,
        }
        rows.append(record)
    pd.DataFrame(rows).to_csv(output_path, index=False, encoding="utf-8-sig")


def build_delivery_examples(frame: pd.DataFrame, output_path: Path) -> None:
    selected: dict[int, list[str]] = {}

    extras_keys = [
        "extras_type",
        "extras1_runs",
        "extras_2_runs",
        "runs",
        "is_four",
        "is_six",
    ]
    for _, group in frame.groupby(extras_keys, dropna=False, sort=False):
        add_representative(
            selected,
            int(group.index[0]),
            "first source row for distinct extras/runs/boundary combination",
        )

    for field in [
        "extras_type",
        "runs",
        "extras1_runs",
        "extras_2_runs",
        "is_four",
        "is_six",
        "is_wicket",
        "dismissal_type_id",
        "dismissal_type",
        "dismissed_player_id",
        "innings",
        "overid",
        "over_ball_num",
    ]:
        for value, group in frame.groupby(field, dropna=False, sort=False):
            add_representative(
                selected,
                int(group.index[0]),
                f"first source row for {field}={value_text(value)}",
            )

    for index in frame.index[frame["dismissal_type"].eq("Retire Out")]:
        add_representative(
            selected,
            int(index),
            "Retire Out record",
        )

    dismissal_id_present = frame["dismissed_player_id"].ne("")
    wicket_flag = frame["is_wicket"].astype(str).str.lower().eq("true")
    for index in frame.index[dismissal_id_present.ne(wicket_flag)]:
        add_representative(
            selected,
            int(index),
            "is_wicket and dismissed_player_id presence disagree",
        )

    runs = pd.to_numeric(frame["runs"], errors="coerce")
    is_four = frame["is_four"].astype(str).str.lower().eq("true")
    is_six = frame["is_six"].astype(str).str.lower().eq("true")
    for index in frame.index[((runs.eq(4) & ~is_four) | (runs.eq(6) & ~is_six))]:
        add_representative(
            selected,
            int(index),
            "runs equals 4 or 6 while the corresponding boundary flag is false",
        )

    speed = pd.to_numeric(frame["bowl_speed"], errors="coerce")
    speed_examples = {
        int(frame.index[speed.idxmin()]): "minimum bowl_speed",
        int(frame.index[speed.idxmax()]): "maximum bowl_speed",
    }
    for index, reason in speed_examples.items():
        add_representative(selected, index, reason)
    for index in frame.index[speed.eq(0)]:
        add_representative(selected, int(index), "zero bowl_speed example")
        break
    for index in frame.index[speed.lt(0) | speed.gt(200)]:
        add_representative(
            selected,
            int(index),
            "negative or greater-than-200 bowl_speed",
        )

    over_ball = pd.to_numeric(frame["over_ball_num"], errors="coerce")
    for index in frame.index[over_ball.eq(13)]:
        add_representative(
            selected,
            int(index),
            "over_ball_num=13 example",
        )

    timestamps = pd.to_datetime(frame["delivery_ist_time"], utc=True, errors="coerce")
    for _, group in frame.groupby(["match_id", "innings"], sort=False):
        differences = timestamps.loc[group.index].diff()
        for index in differences.index[differences.lt(pd.Timedelta(0))]:
            add_representative(
                selected,
                int(index),
                "delivery_ist_time decreases within match/innings source order",
            )
        tied = differences.index[differences.eq(pd.Timedelta(0))]
        if len(tied):
            add_representative(
                selected,
                int(tied[0]),
                "delivery_ist_time ties the preceding source row",
            )

    representative_records(
        frame,
        "ball_by_ball.csv",
        selected,
        output_path,
    )


def build_lineup_examples(frame: pd.DataFrame, output_path: Path) -> None:
    selected: dict[int, list[str]] = {}
    for field in LINEUP_FIELDS:
        for value, group in frame.groupby(field, dropna=False, sort=False):
            add_representative(
                selected,
                int(group.index[0]),
                f"first source row for {field}={value_text(value)}",
            )

    key = ["match_id", "team_id", "player_id"]
    repeated = frame.duplicated(key, keep=False)
    for index in frame.index[repeated]:
        add_representative(
            selected,
            int(index),
            "row belongs to a repeated (match_id, team_id, player_id) group",
        )

    representative_records(
        frame,
        "playing_eleven.csv",
        selected,
        output_path,
    )


def build_match_examples(frame: pd.DataFrame, output_path: Path) -> None:
    selected: dict[int, list[str]] = {}
    zero_awards = frame["man_of_the_match"].astype(str).eq("0")
    for index in frame.index[zero_awards]:
        add_representative(
            selected,
            int(index),
            "zero-coded man_of_the_match",
        )
    for field in [
        "revised_target",
        "first_inn_revised_overs",
        "second_inn_revised_overs",
    ]:
        populated = frame[field].astype(str).ne("")
        for index in frame.index[populated]:
            add_representative(
                selected,
                int(index),
                f"populated {field}",
            )

    representative_records(
        frame,
        "matches.csv",
        selected,
        output_path,
    )


def append_test(
    tests: list[dict[str, object]],
    test: str,
    status: str,
    observed_result: str,
    interpretation: str,
    source_rows: str = "",
) -> None:
    tests.append(
        {
            "test": test,
            "status": status,
            "observed_result": observed_result,
            "interpretation": interpretation,
            "representative_source_rows": source_rows,
        }
    )


def build_tests(
    deliveries: pd.DataFrame,
    matches: pd.DataFrame,
    lineups: pd.DataFrame,
    competitions: pd.DataFrame,
    output_path: Path,
) -> None:
    tests: list[dict[str, object]] = []
    rows = deliveries.index + 2
    extras_fields = [
        "extras_type",
        "extras1_runs",
        "extras_2_runs",
        "runs",
        "is_four",
        "is_six",
    ]
    combo_counts = deliveries.groupby(extras_fields, dropna=False).size()
    append_test(
        tests,
        "Distinct extras/runs/boundary combinations",
        "CONFIRMED",
        f"{len(combo_counts)} combinations cover {int(combo_counts.sum())} delivery rows.",
        "Describes stored values only; does not establish a runs or extras formula.",
    )

    extras_dist = deliveries["extras_type"].value_counts(dropna=False).to_dict()
    append_test(
        tests,
        "extras_type categories",
        "CONFIRMED",
        "; ".join(f"{value_text(k)}={v}" for k, v in extras_dist.items()),
        "The raw text None is preserved distinctly from an empty CSV cell. The category labels' provider meanings remain unresolved.",
    )

    extras_code = deliveries.groupby("extras_type", dropna=False)["extras1_runs"].nunique()
    append_test(
        tests,
        "extras1_runs consistency by extras_type",
        "PROBABLE",
        f"Distinct extras1_runs values per type: {extras_code.to_dict()}",
        "One fixed numeric value per category is evidence of a possible category/code field, not proof it is not a run amount.",
    )
    extra2_counts = deliveries["extras_2_runs"].value_counts().to_dict()
    append_test(
        tests,
        "extras_2_runs values",
        "UNRESOLVED",
        f"Frequency by value: {extra2_counts}",
        "Only nonzero values are 1 and 4; role and arithmetic relationship to other fields are unknown.",
    )

    wide = deliveries["extras_type"].eq("wide")
    wide_combos = deliveries.loc[wide, extras_fields[1:]].value_counts().to_dict()
    overstep = deliveries["extras_type"].eq("Overstep")
    overstep_combos = deliveries.loc[overstep, extras_fields[1:]].value_counts().to_dict()
    append_test(
        tests,
        "wide row pattern",
        "PROBABLE",
        f"Rows={int(wide.sum())}; combinations={wide_combos}",
        "The label matches MCC Law 22's term, and all rows share one stored pattern. Provider encoding is not independently documented.",
    )
    append_test(
        tests,
        "Overstep row patterns",
        "UNRESOLVED",
        f"Rows={int(overstep.sum())}; combinations={overstep_combos}",
        "Do not treat Overstep as a no-ball or legal-delivery indicator without provider confirmation.",
    )

    four = deliveries["is_four"].astype(str).str.lower().eq("true")
    six = deliveries["is_six"].astype(str).str.lower().eq("true")
    runs = pd.to_numeric(deliveries["runs"], errors="coerce")
    four_mismatch = runs.eq(4) & ~four
    six_mismatch = runs.eq(6) & ~six
    append_test(
        tests,
        "Boundary flag relationships",
        "PROBABLE",
        f"All true is_four rows have runs=4: {bool(runs.loc[four].eq(4).all())}; runs=4 with false flag: {int(four_mismatch.sum())}; all true is_six rows have runs=6: {bool(runs.loc[six].eq(6).all())}; runs=6 with false flag: {int(six_mismatch.sum())}.",
        "Flags behave like boundary indicators in the positive direction but are not equivalent to runs=4/6; source convention is unconfirmed.",
        ", ".join(str(int(v)) for v in rows[four_mismatch | six_mismatch]),
    )

    wicket_flag = deliveries["is_wicket"].astype(str).str.lower().eq("true")
    dismissal_counts = deliveries["dismissal_type"].value_counts(dropna=False).to_dict()
    append_test(
        tests,
        "dismissal_type categories",
        "CONFIRMED",
        "; ".join(f"{value_text(k)}={v}" for k, v in dismissal_counts.items()),
        "These are literal source labels. Labels requiring rule interpretation are in the central document.",
    )
    dismissal_id_pairs = (
        deliveries.groupby(
            ["dismissal_type_id", "dismissal_type"],
            dropna=False,
        )
        .size()
        .to_dict()
    )
    append_test(
        tests,
        "dismissal_type_id to dismissal_type pairing",
        "CONFIRMED",
        f"Observed ID/label pairs and frequencies: {dismissal_id_pairs}",
        "The pairings are consistent in this extract; they are not an authoritative provider code dictionary.",
    )
    labels_present = deliveries["dismissal_type"].ne("")
    append_test(
        tests,
        "is_wicket versus dismissal_type presence",
        "CONFIRMED",
        f"nonempty dismissal labels={int(labels_present.sum())}; labels with is_wicket=True={int((labels_present & wicket_flag).sum())}; labels with is_wicket=False={int((labels_present & ~wicket_flag).sum())}.",
        "Observed co-occurrence is consistent in this extract, but does not establish whether is_wicket means team wicket, batter dismissal, or a provider event flag.",
    )
    dismissal_id_present = deliveries["dismissed_player_id"].ne("")
    mismatches = dismissal_id_present.ne(wicket_flag)
    append_test(
        tests,
        "Wicket flag versus dismissed-player ID presence",
        "CONFIRMED",
        f"Disagreement rows={int(mismatches.sum())}: false flag with ID={int((dismissal_id_present & ~wicket_flag).sum())}; true flag without ID={int((~dismissal_id_present & wicket_flag).sum())}.",
        "Presence consistency is objectively testable; its cricket interpretation is not.",
        ", ".join(str(int(v)) for v in rows[mismatches]),
    )
    retired_hurt = deliveries["dismissal_type"].str.casefold().isin(
        {"retired hurt", "retired_hurt"}
    )
    append_test(
        tests,
        "Retired Hurt label",
        "NOT APPLICABLE",
        f"Observed rows with exact case-insensitive label Retired Hurt/Retired_Hurt={int(retired_hurt.sum())}.",
        "No supplied record uses these labels; this does not prove that the provider could never encode the event another way.",
    )

    speed = pd.to_numeric(deliveries["bowl_speed"], errors="coerce")
    append_test(
        tests,
        "bowl_speed distribution",
        "UNRESOLVED",
        f"nonempty={int(speed.notna().sum())}; zero={int(speed.eq(0).sum())}; negative={int(speed.lt(0).sum())}; >200={int(speed.gt(200).sum())}; min={speed.min()}; median={speed.median()}; p99={speed.quantile(.99)}; max={speed.max()}.",
        "Units and zero/negative/outlier conventions cannot be established from the numeric distribution alone.",
        ", ".join(str(int(v)) for v in rows[speed.lt(0) | speed.gt(200)]),
    )

    over_ball = pd.to_numeric(deliveries["over_ball_num"], errors="coerce")
    overid = pd.to_numeric(deliveries["overid"], errors="coerce")
    append_test(
        tests,
        "Over labels and delivery position",
        "UNRESOLVED",
        f"overid range={overid.min()}..{overid.max()}; over_ball_num range={over_ball.min()}..{over_ball.max()}; rows with over_ball_num=13={int(over_ball.eq(13).sum())}.",
        "A position reaching 13 means over_ball_num cannot be used directly as legal-ball count; over labels need provider/rule validation.",
    )
    innings_counts = deliveries["innings"].value_counts().sort_index().to_dict()
    append_test(
        tests,
        "Innings number frequencies by match format",
        "UNRESOLVED",
        f"Counts={deliveries[['match_id','innings']].merge(matches[['match_id','comp_id']], on='match_id').merge(competitions[['comp_id','match_format']], on='comp_id').groupby(['match_format','innings']).size().to_dict()}; overall={innings_counts}.",
        "Innings numbers 3/4 occur in both T20 and T20I. Their exact match-event context (for example a super over) must be verified per match.",
    )

    contiguous_groups = 0
    noncontiguous_groups = 0
    for _, group in deliveries.groupby(["match_id", "innings"], sort=False):
        values = pd.to_numeric(group["innings_ball_num"], errors="coerce").tolist()
        contiguous_groups += 1
        if values != list(range(1, len(values) + 1)):
            noncontiguous_groups += 1
    append_test(
        tests,
        "innings_ball_num source-order continuity",
        "PROBABLE",
        f"{contiguous_groups} match/innings groups checked; noncontiguous groups={noncontiguous_groups}.",
        "The field consistently sequences stored rows from 1; provider documentation and comparison to event chronology are absent.",
    )

    timestamps = pd.to_datetime(
        deliveries["delivery_ist_time"],
        utc=True,
        errors="coerce",
    )
    nonmonotonic = 0
    tied = 0
    for _, group in deliveries.groupby(["match_id", "innings"], sort=False):
        changes = timestamps.loc[group.index].diff()
        nonmonotonic += int(changes.lt(pd.Timedelta(0)).sum())
        tied += int(changes.eq(pd.Timedelta(0)).sum())
    append_test(
        tests,
        "delivery_ist_time parse, suffix and order",
        "UNRESOLVED",
        f"parse failures={int(timestamps.isna().sum())}; all UTC suffix={bool(deliveries['delivery_ist_time'].str.endswith('UTC').all())}; unique timestamps={timestamps.nunique()}; adjacent ties={tied}; within-innings decreases={nonmonotonic}.",
        "UTC is the observed string suffix despite IST in the field name. Timestamp meaning/order is not established; innings_ball_num is the consistent stored sequence.",
    )

    lineup_stats = {
        field: lineups[field].value_counts(dropna=False).to_dict()
        for field in LINEUP_FIELDS
    }
    impact_equal = (
        lineups["is_impact"].astype(str) == lineups["is_impact_off"].astype(str)
    )
    append_test(
        tests,
        "playing_eleven status fields",
        "UNRESOLVED",
        f"Frequencies={lineup_stats}; is_impact and is_impact_off equal on {int(impact_equal.sum())}/{len(lineups)} rows.",
        "Values and co-occurrence are observed, but selection/participation/captain/wicketkeeper/impact semantics and timing are undocumented.",
    )

    zero_awards = matches["man_of_the_match"].astype(str).eq("0")
    append_test(
        tests,
        "Zero-coded player-of-the-match",
        "UNRESOLVED",
        f"Zero rows={int(zero_awards.sum())}; nonzero rows={int((~zero_awards).sum())}.",
        "The zero does not match the supplied mapping as documented in M1; placeholder/award status is not established.",
        ", ".join(str(int(v)) for v in (matches.index[zero_awards] + 2)),
    )

    pd.DataFrame(tests).to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "extracted",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "audit_reports"
        / "rules_validation",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    source_names = [
        "ball_by_ball.csv",
        "matches.csv",
        "playing_eleven.csv",
        "competitions.csv",
        "competition_team_player_mapping.csv",
        "teams.csv",
    ]
    source_paths = {name: args.data_dir / name for name in source_names}
    before_hashes = {
        name: source_hash(path) for name, path in source_paths.items()
    }
    frames = {
        name: read_source(args.data_dir, name) for name in source_names
    }

    field_distributions(frames, args.output_dir / "field_distributions.csv")
    build_delivery_examples(
        frames["ball_by_ball.csv"],
        args.output_dir / "representative_delivery_records.csv",
    )
    build_lineup_examples(
        frames["playing_eleven.csv"],
        args.output_dir / "representative_lineup_records.csv",
    )
    build_match_examples(
        frames["matches.csv"],
        args.output_dir / "representative_match_records.csv",
    )
    build_tests(
        frames["ball_by_ball.csv"],
        frames["matches.csv"],
        frames["playing_eleven.csv"],
        frames["competitions.csv"],
        args.output_dir / "interpretation_tests.csv",
    )
    after_hashes = {
        name: source_hash(path) for name, path in source_paths.items()
    }
    if before_hashes != after_hashes:
        raise RuntimeError("A source CSV changed while the validation ran.")
    pd.DataFrame(
        [
            {"source_csv": name, "sha256": digest}
            for name, digest in before_hashes.items()
        ]
    ).to_csv(
        args.output_dir / "source_sha256.csv",
        index=False,
        encoding="utf-8-sig",
    )
    print(f"Generated rules-validation evidence in: {args.output_dir}")
    for path in sorted(args.output_dir.glob("*.csv")):
        print(f"{path.name}: {sum(1 for _ in path.open(encoding='utf-8-sig')) - 1} rows")
    print("Source CSV hashes were unchanged during execution.")


if __name__ == "__main__":
    main()
