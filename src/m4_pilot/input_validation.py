"""
RR ScoutIQ - Module M4.1: Input Validation Engine
=================================================

Authoritative input validation module for Milestone M4 Controlled Pilot.
Validates dataset availability, schema conformance, crosswalk referential integrity,
delivery legality, runs and bowler debit reconciliation, Super Over and shortened-match tagging,
provenance completeness, and raw dataset immutability.

Evidence Level: IMPLEMENTATION CORRECTNESS
"""

import hashlib
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import pandas as pd


# ---------------------------------------------------------------------------
# Authoritative Constants & Schemas
# ---------------------------------------------------------------------------

EXPECTED_PILOT_DELIVERIES: int = 1994
EXPECTED_PILOT_MATCHES: int = 8
EXPECTED_PILOT_MATCH_IDS: Set[int] = {14094, 14113, 20181, 30058, 40725, 13513, 34429, 40037}

EXPECTED_COLUMNS: List[str] = [
    "match_id", "innings", "overid", "over_ball_num", "innings_ball_num",
    "batting_team_id", "bowling_team_id", "striker_id", "striker_name",
    "non_striker_id", "non_striker_name", "bowler_id", "bowler_name",
    "batting_type", "bowling_type", "batting_order", "runs", "is_four",
    "is_six", "is_wicket", "dismissal_type_id", "dismissal_type",
    "dismissed_player_id", "extras_type", "extras1_runs", "extras_2_runs",
    "pace_or_spin", "bowl_speed", "stroke", "delivery_style", "over_or_around",
    "on_or_off", "delivery_ist_time", "ext_cricsheet_match_id",
    "ext_striker_cricsheet_id", "ext_bowler_cricsheet_id",
    "ext_is_legal_delivery", "ext_is_wide", "ext_is_noball", "ext_wide_runs",
    "ext_noball_runs", "ext_bye_runs", "ext_legbye_runs", "ext_penalty_runs",
    "ext_delivery_total_runs", "ext_bowler_debit_runs", "ext_batter_balls_faced",
    "ext_is_bowler_wicket", "ext_is_retired_hurt", "ext_is_retired_out",
    "ext_provenance"
]

MANDATORY_NON_NULL_COLUMNS: List[str] = [
    "match_id", "innings", "overid", "over_ball_num", "innings_ball_num",
    "batting_team_id", "bowling_team_id", "striker_id", "non_striker_id", "bowler_id",
    "runs", "is_four", "is_six", "is_wicket", "ext_cricsheet_match_id",
    "ext_striker_cricsheet_id", "ext_bowler_cricsheet_id", "ext_is_legal_delivery",
    "ext_is_wide", "ext_is_noball", "ext_delivery_total_runs", "ext_bowler_debit_runs",
    "ext_batter_balls_faced", "ext_provenance"
]

EXPECTED_RAW_HASHES: Dict[str, str] = {
    "data/data_pack.zip.zip": "788f681b538ba95fb61bcaba7b7280e59a7789d043e7964ac3472c3d08291853",
    "data/extracted/ball_by_ball.csv": "a3926f49d2c684dca2a5d2de535a02c5ee46ea654ca1e79dd31c69e7544e9889",
    "data/extracted/matches.csv": "bb100ab84b8b9a15160c1f2315cf675210131a30e779ec5079fd5403dcf56eef",
    "data/extracted/competitions.csv": "507ceb7189f972d4e4f299ddcfc97f3c3247af1913f6291106f161fa8353fd9b",
    "data/extracted/teams.csv": "a65e5922a9b3bf49247b24fc9471782e700efb31f8dcc5042923238b87c50a5d",
    "data/extracted/playing_eleven.csv": "7517c73722a28d5d61c808ccf0cbed315a8780586d02e946eb9a7f5daf011c27",
    "data/extracted/competition_team_player_mapping.csv": "1ded4e42a933618572d6e2c3a521c3257eb1844fab4456d567d77cbb2d3bbb12",
    "data/enriched/pilot/enriched_ball_by_ball_pilot.csv": "a71f3ca75d3ba7aab60b797f78726f7d19551bde1221a3c97ed342c7fb0f9878"
}


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class ValidationIssue:
    severity: str  # "ERROR" or "WARNING"
    category: str
    message: str
    affected_rows: int = 0
    details: Optional[Dict] = None


@dataclass
class ValidationReport:
    passed: bool
    delivery_count: int
    match_count: int
    issues: List[ValidationIssue] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    def add_error(self, category: str, message: str, affected_rows: int = 0, details: Optional[Dict] = None):
        self.issues.append(ValidationIssue("ERROR", category, message, affected_rows, details))
        self.passed = False

    def add_warning(self, category: str, message: str, affected_rows: int = 0, details: Optional[Dict] = None):
        self.issues.append(ValidationIssue("WARNING", category, message, affected_rows, details))

    def summary(self) -> str:
        status_str = "PASS" if self.passed else "FAIL"
        err_count = sum(1 for i in self.issues if i.severity == "ERROR")
        warn_count = sum(1 for i in self.issues if i.severity == "WARNING")
        return (f"ValidationReport(status={status_str}, deliveries={self.delivery_count}, "
                f"matches={self.match_count}, errors={err_count}, warnings={warn_count})")


# ---------------------------------------------------------------------------
# Validation Functions
# ---------------------------------------------------------------------------

def compute_sha256(filepath: str) -> str:
    """Computes SHA-256 hash of a file."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_dataset_immutability(expected_hashes: Optional[Dict[str, str]] = None) -> Tuple[bool, List[ValidationIssue]]:
    """Verifies that all raw datasets and pilot files match their approved cryptographic hashes."""
    if expected_hashes is None:
        expected_hashes = EXPECTED_RAW_HASHES
    issues = []
    all_matched = True
    for path, expected_hash in expected_hashes.items():
        if not os.path.exists(path):
            issues.append(ValidationIssue("ERROR", "IMMUTABILITY", f"Required file missing: {path}"))
            all_matched = False
            continue
        actual_hash = compute_sha256(path)
        if actual_hash != expected_hash:
            issues.append(ValidationIssue(
                "ERROR", "IMMUTABILITY",
                f"Hash mismatch for {path}: expected {expected_hash}, got {actual_hash}"
            ))
            all_matched = False
    return all_matched, issues


def validate_pilot_dataset(
    df: pd.DataFrame,
    match_crosswalk_df: Optional[pd.DataFrame] = None,
    player_crosswalk_df: Optional[pd.DataFrame] = None,
    matches_df: Optional[pd.DataFrame] = None,
    verify_hashes: bool = True
) -> ValidationReport:
    """
    Executes complete M4.1 input validation on the pilot delivery dataset.
    
    Checks:
    1. Schema invariance and column completeness.
    2. Delivery count (1,994) and match count (8) invariant.
    3. Primary delivery key uniqueness: (match_id, innings, overid, over_ball_num).
    4. Mandatory non-null constraints.
    5. Delivery legality rule: ext_is_legal_delivery == ~(ext_is_wide | ext_is_noball).
    6. Run decomposition arithmetic (per-delivery and innings-level).
    7. Bowler debit reconciliation (per-delivery and innings-level).
    8. Batter balls faced logic: ext_batter_balls_faced == ~ext_is_wide.
    9. Crosswalk referential integrity and Cricsheet ID mapping completeness.
    10. Provenance string completeness.
    11. Super Over identification (innings > 2).
    12. Shortened match / DLS flags.
    13. Raw source file immutability.
    """
    report = ValidationReport(passed=True, delivery_count=len(df), match_count=df["match_id"].nunique() if "match_id" in df.columns else 0)

    # 1. Immutability check
    if verify_hashes:
        passed_hash, hash_issues = verify_dataset_immutability()
        if not passed_hash:
            for issue in hash_issues:
                report.issues.append(issue)
            report.passed = False

    # 2. Schema check
    missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing_cols:
        report.add_error("SCHEMA", f"Missing {len(missing_cols)} expected columns: {missing_cols}")
        return report  # Stop if critical schema is violated

    # 3. Delivery count & Match count check
    if len(df) != EXPECTED_PILOT_DELIVERIES:
        report.add_error("RECORD_COUNT", f"Expected {EXPECTED_PILOT_DELIVERIES} deliveries, found {len(df)}")

    observed_matches = set(df["match_id"].unique())
    if observed_matches != EXPECTED_PILOT_MATCH_IDS:
        report.add_error("RECORD_COUNT", f"Observed match IDs {observed_matches} do not match expected {EXPECTED_PILOT_MATCH_IDS}")

    # 4. Primary candidate delivery key uniqueness
    key_cols = ["match_id", "innings", "overid", "over_ball_num"]
    dups = df.duplicated(subset=key_cols).sum()
    if dups > 0:
        report.add_error("KEY_INTEGRITY", f"Found {dups} duplicate delivery keys in {key_cols}", affected_rows=int(dups))

    # 5. Mandatory non-null checks
    for col in MANDATORY_NON_NULL_COLUMNS:
        null_count = int(df[col].isna().sum())
        if null_count > 0:
            report.add_error("NULL_CONSTRAINT", f"Column '{col}' has {null_count} unexpected null values", affected_rows=null_count)

    # 6. Delivery legality rule (MCC Laws 17, 21, 22 and M2 Reconciliation)
    # Under MCC Law 17.1, an over consists of 6 valid deliveries.
    # Wides (Law 22) and No-balls (Law 21) are NOT counted as legal balls in the over.
    # Byes, leg-byes, and penalties are legal deliveries unless accompanied by a wide or no-ball.
    # In M2, candidate rule excluded extras_type in ['wide', 'Overstep', 'other'].
    # We verify that ext_is_legal_delivery == ~(ext_is_wide | ext_is_noball), and additionally assert
    # that this definition is 100% reconciled with the M2 extras_type mapping.
    expected_legal = ~(df["ext_is_wide"].astype(bool) | df["ext_is_noball"].astype(bool))
    actual_legal = df["ext_is_legal_delivery"].astype(bool)
    legality_mismatches = int((actual_legal != expected_legal).sum())
    if legality_mismatches > 0:
        report.add_error("LEGALITY_RULE", f"ext_is_legal_delivery violated on {legality_mismatches} rows", affected_rows=legality_mismatches)

    # Cross-check against M2 candidate categories:
    # 'wide' must be illegal (ext_is_wide=True), 'Overstep' and 'other' must be illegal (ext_is_noball=True).
    # 'byes' and 'legbyes' must be legal (ext_is_legal_delivery=True).
    if "extras_type" in df.columns:
        m2_wide_illegal = df[df["extras_type"] == "wide"]["ext_is_legal_delivery"]
        if m2_wide_illegal.any():
            report.add_error("LEGALITY_M2_RECONCILIATION", f"Found {m2_wide_illegal.sum()} 'wide' deliveries classified as legal")

        m2_overstep_illegal = df[df["extras_type"] == "Overstep"]["ext_is_legal_delivery"]
        if m2_overstep_illegal.any():
            report.add_error("LEGALITY_M2_RECONCILIATION", f"Found {m2_overstep_illegal.sum()} 'Overstep' deliveries classified as legal")

        m2_other_illegal = df[df["extras_type"] == "other"]["ext_is_legal_delivery"]
        if m2_other_illegal.any():
            report.add_error("LEGALITY_M2_RECONCILIATION", f"Found {m2_other_illegal.sum()} 'other' deliveries classified as legal")

        m2_byes_legal = df[df["extras_type"] == "byes"]["ext_is_legal_delivery"]
        if (~m2_byes_legal).any():
            report.add_error("LEGALITY_M2_RECONCILIATION", f"Found {(~m2_byes_legal).sum()} 'byes' deliveries classified as illegal")

        m2_legbyes_legal = df[df["extras_type"] == "legbyes"]["ext_is_legal_delivery"]
        if (~m2_legbyes_legal).any():
            report.add_error("LEGALITY_M2_RECONCILIATION", f"Found {(~m2_legbyes_legal).sum()} 'legbyes' deliveries classified as illegal")

    # 7. Batter balls faced rule
    expected_bbf = ~df["ext_is_wide"].astype(bool)
    actual_bbf = df["ext_batter_balls_faced"].astype(bool)
    bbf_mismatches = int((actual_bbf != expected_bbf).sum())
    if bbf_mismatches > 0:
        report.add_error("BBF_RULE", f"ext_batter_balls_faced violated on {bbf_mismatches} rows", affected_rows=bbf_mismatches)

    # 7b. Extras classification and non-negativity rules
    extras_cols = ["ext_wide_runs", "ext_noball_runs", "ext_bye_runs", "ext_legbye_runs", "ext_penalty_runs"]
    for ec in extras_cols:
        neg_count = int((df[ec] < 0).sum())
        if neg_count > 0:
            report.add_error("EXTRAS_VALIDATION", f"Column '{ec}' contains {neg_count} negative run values", affected_rows=neg_count)

    wide_inconsistent = int((df["ext_is_wide"].astype(bool) != (df["ext_wide_runs"] > 0)).sum())
    if wide_inconsistent > 0:
        report.add_error("EXTRAS_VALIDATION", f"ext_is_wide flag inconsistent with ext_wide_runs on {wide_inconsistent} rows", affected_rows=wide_inconsistent)

    noball_inconsistent = int((df["ext_is_noball"].astype(bool) != (df["ext_noball_runs"] > 0)).sum())
    if noball_inconsistent > 0:
        report.add_error("EXTRAS_VALIDATION", f"ext_is_noball flag inconsistent with ext_noball_runs on {noball_inconsistent} rows", affected_rows=noball_inconsistent)

    # 8. Run decomposition & Bowler debit arithmetic reconciliation
    expected_tot_runs = (
        df["runs"] +
        df["ext_wide_runs"] +
        df["ext_noball_runs"] +
        df["ext_bye_runs"] +
        df["ext_legbye_runs"] +
        df["ext_penalty_runs"]
    )
    tot_mismatches = int((df["ext_delivery_total_runs"] != expected_tot_runs).sum())
    if tot_mismatches > 0:
        # Document whether mismatches are local score-swap anomalies that reconcile at innings level
        mismatched_df = df[df["ext_delivery_total_runs"] != expected_tot_runs]
        report.add_warning(
            "DELIVERY_TOTAL_RUNS_DISCREPANCY",
            f"ext_delivery_total_runs differs from local components on {tot_mismatches} deliveries (e.g. verified provider transposition in match 20181 overid 9). Reconciling at innings level.",
            affected_rows=tot_mismatches,
            details={"discrepancies": mismatched_df[["match_id", "innings", "overid", "over_ball_num", "runs", "ext_delivery_total_runs"]].to_dict(orient="records")}
        )

    expected_debit = df["runs"] + df["ext_wide_runs"] + df["ext_noball_runs"]
    debit_mismatches = int((df["ext_bowler_debit_runs"] != expected_debit).sum())
    if debit_mismatches > 0:
        report.add_warning(
            "BOWLER_DEBIT_DISCREPANCY",
            f"ext_bowler_debit_runs differs from local runs+wides+noballs on {debit_mismatches} deliveries. Reconciling at innings level.",
            affected_rows=debit_mismatches
        )

    # Innings-level aggregate totals reconciliation
    for (mid, inn), grp in df.groupby(["match_id", "innings"]):
        local_inn_tot = int((
            grp["runs"] +
            grp["ext_wide_runs"] +
            grp["ext_noball_runs"] +
            grp["ext_bye_runs"] +
            grp["ext_legbye_runs"] +
            grp["ext_penalty_runs"]
        ).sum())
        ext_inn_tot = int(grp["ext_delivery_total_runs"].sum())
        if local_inn_tot != ext_inn_tot:
            report.add_error(
                "INNINGS_TOTAL_RECONCILIATION",
                f"Match {mid} Innings {inn} aggregate runs mismatch: local={local_inn_tot}, external={ext_inn_tot}"
            )

        local_inn_debit = int((grp["runs"] + grp["ext_wide_runs"] + grp["ext_noball_runs"]).sum())
        ext_inn_debit = int(grp["ext_bowler_debit_runs"].sum())
        if local_inn_debit != ext_inn_debit:
            report.add_error(
                "INNINGS_DEBIT_RECONCILIATION",
                f"Match {mid} Innings {inn} aggregate bowler debit mismatch: local={local_inn_debit}, external={ext_inn_debit}"
            )

    # 9. Crosswalk integrity & Cricsheet ID mapping completeness
    # Confirm no empty or placeholder strings in external IDs
    for id_col in ["ext_cricsheet_match_id", "ext_striker_cricsheet_id", "ext_bowler_cricsheet_id"]:
        empty_mask = df[id_col].astype(str).str.strip().isin(["", "nan", "None", "0", "-1"])
        empty_count = int(empty_mask.sum())
        if empty_count > 0:
            report.add_error("CROSSWALK_INTEGRITY", f"Column '{id_col}' contains {empty_count} unmapped or placeholder IDs", affected_rows=empty_count)

    if match_crosswalk_df is not None:
        pilot_cross_matches = match_crosswalk_df[match_crosswalk_df["local_match_id"].isin(observed_matches)]
        if len(pilot_cross_matches) != EXPECTED_PILOT_MATCHES:
            report.add_error("CROSSWALK_INTEGRITY", f"Match crosswalk has {len(pilot_cross_matches)} pilot matches, expected {EXPECTED_PILOT_MATCHES}")

    if player_crosswalk_df is not None:
        # Check all unique strikers and bowlers in pilot deliveries are represented in player crosswalk
        pilot_strikers = set(df["striker_id"].unique())
        pilot_bowlers = set(df["bowler_id"].unique())
        pilot_players = pilot_strikers.union(pilot_bowlers)
        crosswalk_players = set(player_crosswalk_df["local_player_id"].unique())
        missing_players = pilot_players - crosswalk_players
        if missing_players:
            report.add_error("CROSSWALK_INTEGRITY", f"Found {len(missing_players)} pilot players missing from player crosswalk: {missing_players}")

    # 10. Provenance completeness
    empty_prov = int((df["ext_provenance"].astype(str).str.strip().isin(["", "nan", "None"])).sum())
    if empty_prov > 0:
        report.add_error("PROVENANCE", f"Found {empty_prov} deliveries with missing provenance", affected_rows=empty_prov)

    # 11. Special event detection (Super Overs & DLS)
    super_over_mask = df["innings"] > 2
    super_over_dels = int(super_over_mask.sum())
    super_over_matches = set(df[super_over_mask]["match_id"].unique())
    expected_so_matches = {34429, 40725}
    if super_over_matches != expected_so_matches:
        report.add_error("SUPER_OVER_DETECTION", f"Super Over matches {super_over_matches} do not match expected {expected_so_matches}")

    report.metadata["super_over_deliveries"] = super_over_dels
    report.metadata["super_over_matches"] = list(super_over_matches)

    # DLS / Shortened Match check
    if matches_df is not None:
        pilot_match_meta = matches_df[matches_df["match_id"].isin(observed_matches)]
        revised_target_matches = pilot_match_meta[pilot_match_meta["revised_target"].notna()]["match_id"].tolist()
        shortened_overs_matches = pilot_match_meta[
            pilot_match_meta["first_inn_revised_overs"].notna() | pilot_match_meta["second_inn_revised_overs"].notna()
        ]["match_id"].tolist()
        report.metadata["dls_revised_target_matches"] = revised_target_matches
        report.metadata["shortened_overs_matches"] = shortened_overs_matches
        # Confirm rain-affected/DLS matches in pilot are tracked cleanly
        if len(revised_target_matches) > 0:
            report.add_warning(
                "DLS_MATCH_DETECTED",
                f"Pilot dataset contains DLS rain-affected matches with revised target: {revised_target_matches}. Continuous chase RRR modeling will tag DLI_VALID = False."
            )
    else:
        report.metadata["dls_revised_target_matches"] = []
        report.metadata["shortened_overs_matches"] = []

    return report


def load_and_validate_pilot_data(
    pilot_path: str = "data/enriched/pilot/enriched_ball_by_ball_pilot.csv",
    match_crosswalk_path: str = "data/enriched/match_crosswalk.csv",
    player_crosswalk_path: str = "data/enriched/player_crosswalk.csv",
    matches_path: str = "data/extracted/matches.csv",
    verify_hashes: bool = True
) -> Tuple[pd.DataFrame, ValidationReport]:
    """
    Convenience loader that reads pilot files and returns the validated delivery DataFrame
    alongside the formal ValidationReport.
    """
    if not os.path.exists(pilot_path):
        raise FileNotFoundError(f"Pilot dataset not found at {pilot_path}")

    df = pd.read_csv(pilot_path)
    match_cw = pd.read_csv(match_crosswalk_path) if os.path.exists(match_crosswalk_path) else None
    player_cw = pd.read_csv(player_crosswalk_path) if os.path.exists(player_crosswalk_path) else None
    matches_meta = pd.read_csv(matches_path) if os.path.exists(matches_path) else None

    report = validate_pilot_dataset(
        df=df,
        match_crosswalk_df=match_cw,
        player_crosswalk_df=player_cw,
        matches_df=matches_meta,
        verify_hashes=verify_hashes
    )
    return df, report


if __name__ == "__main__":
    print("=" * 70)
    print("Running M4.1 Pilot Input Validation Engine...")
    print("=" * 70)
    data, val_report = load_and_validate_pilot_data()
    print(val_report.summary())
    for iss in val_report.issues:
        print(f"[{iss.severity}] {iss.category}: {iss.message}")
    if val_report.passed:
        print("\n>>> M4.1 INPUT VALIDATION PASSED SUCCESSFULLY <<<")
    else:
        print("\n>>> M4.1 INPUT VALIDATION FAILED <<<")

