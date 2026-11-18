"""
RR ScoutIQ - Milestone R1.1 Investigation 1: Chase Win-Rate Construct Validity.
Compares DLI against baseline predictive models of chase win rate using 5-fold match-grouped cross-validation.
Evaluates Log Loss, Brier Score, ROC-AUC, PR-AUC, and Expected Calibration Error (ECE).
"""

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score, average_precision_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler


def compute_expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Computes Expected Calibration Error (ECE) with equal-width probability bins."""
    bin_limits = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)

    for i in range(n_bins):
        low, high = bin_limits[i], bin_limits[i + 1]
        mask = (y_prob >= low) & (y_prob < high if i < n_bins - 1 else y_prob <= high)
        bin_n = np.sum(mask)
        if bin_n > 0:
            bin_acc = np.mean(y_true[mask])
            bin_conf = np.mean(y_prob[mask])
            ece += (bin_n / n) * np.abs(bin_acc - bin_conf)

    return float(ece)


def prepare_chase_dataset(df_state: pd.DataFrame, matches_df: pd.DataFrame) -> pd.DataFrame:
    """Prepares valid chase deliveries with terminal win/loss targets and state features."""
    chase = df_state[
        (df_state["pre_innings_type"] == "Chase")
        & (df_state["is_dli_valid"] == True)
        & (df_state["ext_is_legal_delivery"] == True)
    ].copy()

    # Join match win target
    matches_sub = matches_df[["match_id", "win_team_id"]].drop_duplicates()
    chase = chase.merge(matches_sub, on="match_id", how="left")
    chase["chase_won"] = (chase["batting_team_id"] == chase["win_team_id"]).astype(int)

    # Derived state features
    chase["rrr_clean"] = chase["pre_rrr"].fillna(8.0).clip(0.0, 36.0)
    chase["wkt_hand_clean"] = chase["pre_wickets_in_hand"].clip(1, 10)
    chase["balls_rem_clean"] = chase["pre_legal_balls_rem"].clip(1, 120)
    chase["runs_req_clean"] = chase["pre_runs_required"].clip(0, 300)
    chase["curr_score_clean"] = chase["pre_score"].clip(0, 300)
    chase["target_clean"] = chase["pre_target"].clip(1, 350)
    chase["is_pp"] = (chase["pre_match_phase"] == "Powerplay").astype(int)
    chase["is_mid"] = (chase["pre_match_phase"] == "Middle").astype(int)
    chase["is_death"] = (chase["pre_match_phase"] == "Death").astype(int)

    return chase


def evaluate_model_cv(
    X: np.ndarray, y: np.ndarray, groups: np.ndarray, model_name: str, n_splits: int = 5
) -> Dict:
    """Evaluates a classification model using GroupKFold cross-validation grouped on match_id."""
    gkf = GroupKFold(n_splits=n_splits)

    oof_probs = np.zeros(len(y))

    for train_idx, test_idx in gkf.split(X, y, groups=groups):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train = y[train_idx]

        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        clf = LogisticRegression(max_iter=1000, random_state=42)
        clf.fit(X_train_scaled, y_train)

        # Prob of chase win (class 1)
        probs = clf.predict_proba(X_test_scaled)[:, 1]
        oof_probs[test_idx] = probs

    # Compute overall out-of-sample metrics
    loss = float(log_loss(y, oof_probs))
    brier = float(brier_score_loss(y, oof_probs))
    roc_auc = float(roc_auc_score(y, oof_probs))
    pr_auc = float(average_precision_score(y, oof_probs))
    ece = compute_expected_calibration_error(y, oof_probs, n_bins=10)

    return {
        "model_name": model_name,
        "log_loss": round(loss, 4),
        "brier_score": round(brier, 4),
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "expected_calibration_error": round(ece, 4),
    }


def run_chase_baseline_comparison(df_state: pd.DataFrame, matches_df: pd.DataFrame) -> pd.DataFrame:
    """Runs 5 candidate models on identical chase population to test incremental construct validity."""
    chase_df = prepare_chase_dataset(df_state, matches_df)
    y = chase_df["chase_won"].to_numpy()
    groups = chase_df["match_id"].to_numpy()

    # Define feature sets
    feat_m1 = chase_df[["rrr_clean"]].to_numpy()
    feat_m2 = chase_df[["wkt_hand_clean", "balls_rem_clean"]].to_numpy()
    feat_m3 = chase_df[["rrr_clean", "wkt_hand_clean", "balls_rem_clean", "runs_req_clean", "is_pp", "is_death"]].to_numpy()
    feat_m4 = chase_df[["pre_dli"]].to_numpy()
    feat_m5 = chase_df[["rrr_clean", "wkt_hand_clean", "balls_rem_clean", "runs_req_clean", "is_pp", "is_death", "pre_dli"]].to_numpy()

    results = []
    results.append(evaluate_model_cv(feat_m1, y, groups, "Baseline 1: RRR Alone"))
    results.append(evaluate_model_cv(feat_m2, y, groups, "Baseline 2: Wickets & Balls Remaining"))
    results.append(evaluate_model_cv(feat_m3, y, groups, "Baseline 3: Full Raw State Variables (No DLI)"))
    results.append(evaluate_model_cv(feat_m4, y, groups, "Baseline 4: Approved DLI Alone"))
    results.append(evaluate_model_cv(feat_m5, y, groups, "Baseline 5: Full Raw State Variables + DLI"))

    df_res = pd.DataFrame(results)

    # Compute incremental metric differences vs Full Raw State
    base3_loss = df_res.loc[df_res["model_name"] == "Baseline 3: Full Raw State Variables (No DLI)", "log_loss"].values[0]
    base3_auc = df_res.loc[df_res["model_name"] == "Baseline 3: Full Raw State Variables (No DLI)", "roc_auc"].values[0]

    df_res["delta_log_loss_vs_raw_state"] = (df_res["log_loss"] - base3_loss).round(4)
    df_res["delta_auc_vs_raw_state"] = (df_res["roc_auc"] - base3_auc).round(4)
    df_res["incremental_information_detected"] = df_res["delta_log_loss_vs_raw_state"] < -0.005

    return df_res
