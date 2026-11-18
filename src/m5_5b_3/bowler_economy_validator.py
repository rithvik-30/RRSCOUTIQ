"""
RR ScoutIQ — Milestone M5.5-B.3: Context-Aggregated Bowler Economy Validator
Module: src/m5_5b_3/bowler_economy_validator.py

Corrects the fundamental defect in M5.5-B.2 validation:
Instead of evaluating single deliveries (0, 6, 12, 24, 36 RPO),
this module aggregates validation outcomes at the proper statistical unit:
bowler x match x phase (spell/phase spell).

Numerator: All debited runs (including wides and no-balls)
Denominator: Legal deliveries in spell (must be > 0)
"""

import math
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from src.m5_5b_2.remediation_engine_b2 import calculate_bowler_economy


def aggregate_bowler_spells(
    df: pd.DataFrame
) -> pd.DataFrame:
    """
    Aggregates delivery data to bowler x match x phase spells.
    Calculates exact Law-compliant economy rate and legal exposure.
    """
    spells = []
    
    # Group by bowler_id, match_id, pre_match_phase
    grp_cols = ["bowler_id", "match_id", "pre_match_phase"]
    for (bid, mid, phase), b_delivs in df.groupby(grp_cols):
        stats = calculate_bowler_economy(b_delivs)
        
        # Bowler name
        bname = b_delivs["bowler_name"].iloc[0] if "bowler_name" in b_delivs.columns else str(bid)
        
        # Modal pressure tier in spell
        modal_tier = b_delivs["pre_pressure_tier"].mode().iloc[0] if "pre_pressure_tier" in b_delivs.columns else "Tier 2: Medium"
        
        spells.append({
            "bowler_id": bid,
            "bowler_name": bname,
            "match_id": mid,
            "phase": phase,
            "modal_tier": modal_tier,
            "total_deliveries": stats["total_deliveries"],
            "legal_balls": stats["legal_balls"],
            "bowler_debit_runs": stats["bowler_debit_runs"],
            "wides_count": stats["wides_count"],
            "noballs_count": stats["noballs_count"],
            "actual_economy": stats["economy_rate"],
            "is_valid_spell": stats["legal_balls"] > 0
        })
        
    return pd.DataFrame(spells)


def evaluate_spell_economy_predictions(
    df_spells: pd.DataFrame,
    predictions: np.ndarray,
    model_name: str
) -> Dict[str, Any]:
    """
    Evaluates economy predictions on valid spells (legal_balls > 0).
    Computes exposure-weighted RMSE and unweighted RMSE.
    """
    valid_mask = df_spells["is_valid_spell"] & np.isfinite(df_spells["actual_economy"])
    valid_spells = df_spells[valid_mask].copy()
    y_true = valid_spells["actual_economy"].values
    y_pred = predictions[valid_mask]
    weights = valid_spells["legal_balls"].values / valid_spells["legal_balls"].sum()
    
    unweighted_rmse = float(np.sqrt(np.mean((y_pred - y_true) ** 2)))
    weighted_rmse = float(np.sqrt(np.sum(weights * ((y_pred - y_true) ** 2))))
    mean_bias = float(np.mean(y_pred - y_true))
    
    return {
        "model": model_name,
        "valid_spells_count": len(valid_spells),
        "total_legal_balls": int(valid_spells["legal_balls"].sum()),
        "unweighted_rmse": unweighted_rmse,
        "weighted_rmse": weighted_rmse,
        "mean_prediction_bias": mean_bias
    }
