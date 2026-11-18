"""
RR ScoutIQ - Milestone R1.1.1 Investigation 2: Setting DLI Independent Model Comparison.
Evaluates Setting DLI against subsequent forward outcomes (runs, wickets, dot %, bnd %)
using 5-fold match-grouped cross-validation across 5 nested model specifications.
"""

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score, roc_auc_score, brier_score_loss, log_loss
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler


def prepare_setting_dataset(df_legal_fwd: pd.DataFrame) -> pd.DataFrame:
    """Prepares valid setting deliveries with forward 6-ball outcomes and state features."""
    setting = df_legal_fwd[
        (df_legal_fwd["pre_innings_type"] == "Setting")
        & (df_legal_fwd["is_dli_valid"] == True)
        & (df_legal_fwd["window_length"] == 6)  # Strict 6-ball windows
    ].copy()

    setting["t_progression"] = setting["pre_legal_balls_bowled"].clip(0, 120)
    setting["wkt_hand"] = setting["pre_wickets_in_hand"].clip(1, 10)
    setting["crr_clean"] = setting["pre_crr"].fillna(8.0).clip(0.0, 36.0)
    setting["is_pp"] = (setting["pre_match_phase"] == "Powerplay").astype(float)
    setting["is_mid"] = (setting["pre_match_phase"] == "Middle").astype(float)
    setting["is_death"] = (setting["pre_match_phase"] == "Death").astype(float)
    setting["is_over1"] = (setting["overid"] == 1).astype(float)
    setting["has_wkt_loss"] = (setting["fwd_wkts_scaled"] > 0).astype(int)

    return setting


def evaluate_regression_cv(
    X: np.ndarray, y: np.ndarray, groups: np.ndarray, model_label: str, outcome_name: str, n_splits: int = 5
) -> Dict:
    """Evaluates continuous forward outcome prediction using 5-fold GroupKFold cross-validation."""
    gkf = GroupKFold(n_splits=n_splits)
    oof_preds = np.zeros(len(y))

    for train_idx, test_idx in gkf.split(X, y, groups=groups):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train = y[train_idx]

        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        reg = LinearRegression()
        reg.fit(X_train_scaled, y_train)
        oof_preds[test_idx] = reg.predict(X_test_scaled)

    r2 = float(r2_score(y, oof_preds))
    rmse = float(np.sqrt(mean_squared_error(y, oof_preds)))
    mae = float(mean_absolute_error(y, oof_preds))

    return {
        "model_specification": model_label,
        "outcome_metric": outcome_name,
        "out_of_sample_r2": round(r2, 5),
        "out_of_sample_rmse": round(rmse, 4),
        "out_of_sample_mae": round(mae, 4),
    }


def evaluate_wicket_occurrence_cv(
    X: np.ndarray, y_bin: np.ndarray, groups: np.ndarray, model_label: str, n_splits: int = 5
) -> Dict:
    """Evaluates binary wicket occurrence prediction using 5-fold GroupKFold cross-validation."""
    gkf = GroupKFold(n_splits=n_splits)
    oof_probs = np.zeros(len(y_bin))

    for train_idx, test_idx in gkf.split(X, y_bin, groups=groups):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train = y_bin[train_idx]

        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        clf = LogisticRegression(max_iter=500, random_state=42)
        clf.fit(X_train_scaled, y_train)
        oof_probs[test_idx] = clf.predict_proba(X_test_scaled)[:, 1]

    auc = float(roc_auc_score(y_bin, oof_probs))
    brier = float(brier_score_loss(y_bin, oof_probs))
    loss = float(log_loss(y_bin, oof_probs))

    return {
        "model_specification": model_label,
        "outcome_metric": "Wicket Occurrence (P(Wkts >= 1))",
        "roc_auc": round(auc, 4),
        "brier_score": round(brier, 4),
        "log_loss": round(loss, 4),
    }


def run_setting_model_comparison(df_legal_fwd: pd.DataFrame) -> pd.DataFrame:
    """Executes model comparison across specifications A through E for Setting Innings."""
    setting = prepare_setting_dataset(df_legal_fwd)
    groups = setting["match_id"].to_numpy()

    # Features for Specifications A, B, C, D, E
    feat_a = setting[["t_progression", "is_pp", "is_death"]].to_numpy()
    feat_b = setting[["t_progression", "is_pp", "is_death", "wkt_hand"]].to_numpy()
    feat_c = setting[["t_progression", "is_pp", "is_death", "wkt_hand", "crr_clean"]].to_numpy()
    feat_d = setting[["pre_dli"]].to_numpy()
    feat_e = setting[["t_progression", "is_pp", "is_death", "wkt_hand", "crr_clean", "pre_dli"]].to_numpy()

    specs = [
        ("Spec A: Phase & Progression Only", feat_a),
        ("Spec B: Phase, Progression & Wickets Remaining", feat_b),
        ("Spec C: Phase, Progression, Wickets & CRR (Full Raw State)", feat_c),
        ("Spec D: Approved Setting DLI Alone", feat_d),
        ("Spec E: Full Raw State + Setting DLI", feat_e),
    ]

    records = []

    # 1. Forward Runs Scored
    y_runs = setting["fwd_runs_scaled"].to_numpy()
    for name, X_mat in specs:
        res = evaluate_regression_cv(X_mat, y_runs, groups, name, "Fwd 6 Legal Balls Runs")
        records.append(res)

    # 2. Forward Wickets Lost Count
    y_wkts = setting["fwd_wkts_scaled"].to_numpy()
    for name, X_mat in specs:
        res = evaluate_regression_cv(X_mat, y_wkts, groups, name, "Fwd 6 Legal Balls Wickets")
        records.append(res)

    # 3. Forward Dot Ball Percentage
    y_dots = setting["fwd_dot_pct"].to_numpy()
    for name, X_mat in specs:
        res = evaluate_regression_cv(X_mat, y_dots, groups, name, "Fwd 6 Legal Balls Dot %")
        records.append(res)

    # 4. Forward Wicket Occurrence (Binary)
    y_bin = setting["has_wkt_loss"].to_numpy()
    for name, X_mat in specs:
        res = evaluate_wicket_occurrence_cv(X_mat, y_bin, groups, name)
        records.append(res)

    return pd.DataFrame(records)
