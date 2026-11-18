"""
RR ScoutIQ — Milestone M5.2 Delivery Alignment Engine
Module: src/m5_enrichment/delivery_alignment.py

Provides deterministic, auditable delivery sequence alignment between
local provider deliveries and Cricsheet JSON deliveries.
Supports:
1. CLEAN_VALIDATED: Exact 1-to-1 sequential matching across all regulation innings.
2. SAFE_REGULATION_ONLY: Matches 13613 and 21176 where Super Overs are excluded.
3. SAFE_MINOR_OMISSION: Matches 14130 and 14164 where specific documented Over 14
   omissions are reconciled with zero sequence drift.
4. QUARANTINED_INCOMPATIBLE: Strict automated safeguard blocking quarantined fixtures.
"""

from enum import Enum
from typing import Dict, Any, List, Tuple, Optional
import pandas as pd


class QuarantinedMatchError(Exception):
    """Raised when an attempt is made to align or enrich a quarantined fixture."""
    pass


class AlignmentStrategy(Enum):
    CLEAN_VALIDATED = "CLEAN_VALIDATED"
    REGULATION_ONLY = "SAFE_REGULATION_ONLY"
    MINOR_OMISSION = "SAFE_MINOR_OMISSION"
    QUARANTINED = "QUARANTINED_INCOMPATIBLE"


QUARANTINED_MATCH_IDS = {32618, 37349, 37352, 46250, 50504}


class DeliveryAlignmentEngine:
    """Deterministic sequence alignment engine between local and Cricsheet delivery streams."""

    @staticmethod
    def extract_cricsheet_innings_deliveries(
        cdata: Dict[str, Any],
        is_regulation_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Extracts and flattens Cricsheet deliveries into an indexed list of delivery objects.
        If is_regulation_only is True, skips Super Overs (innings > 2 or super_over == True).
        """
        deliveries = []
        global_idx = 0
        
        for inn_idx, inn_obj in enumerate(cdata.get("innings", []), start=1):
            is_so = inn_obj.get("super_over", False) or inn_idx > 2
            if is_regulation_only and is_so:
                # Omit Super Over deliveries for regulation-only matches per documented scope
                continue
                
            batting_team = inn_obj.get("team")
            overs = inn_obj.get("overs", [])
            for over_obj in overs:
                over_num = over_obj.get("over")  # 0-indexed over number
                for b_idx, d_dict in enumerate(over_obj.get("deliveries", []), start=1):
                    global_idx += 1
                    deliveries.append({
                        "innings": inn_idx,
                        "is_super_over": is_so,
                        "batting_team": batting_team,
                        "over_0based": over_num,
                        "over_1based": over_num + 1,
                        "ball_in_over": b_idx,
                        "cricsheet_delivery_index": global_idx,
                        "raw_delivery": d_dict
                    })
        return deliveries

    @classmethod
    def align_match_deliveries(
        cls,
        local_match_id: int,
        cdata: Dict[str, Any],
        local_df: pd.DataFrame,
        warning_disposition: Optional[str] = None
    ) -> List[Tuple[pd.Series, Dict[str, Any], Dict[str, Any]]]:
        """
        Aligns local delivery rows with Cricsheet delivery dictionaries.
        
        Returns:
            List of tuples: (local_row_series, cricsheet_delivery_dict, alignment_meta)
        Raises:
            QuarantinedMatchError if match is quarantined.
            ValueError if delivery counts or alignments cannot be resolved.
        """
        if local_match_id in QUARANTINED_MATCH_IDS or warning_disposition == "QUARANTINED_INCOMPATIBLE":
            raise QuarantinedMatchError(
                f"Match {local_match_id} is QUARANTINED_INCOMPATIBLE and must not be enriched."
            )

        # Sort local deliveries deterministically
        if "match_id" in local_df.columns and (local_df["match_id"] != local_match_id).any():
            loc_match = local_df[local_df["match_id"] == local_match_id]
        else:
            loc_match = local_df
        loc_sorted = loc_match.sort_values(
            by=["innings", "overid", "over_ball_num"]
        ).reset_index(drop=True)

        is_reg_only = (warning_disposition == "SAFE_REGULATION_ONLY") or (local_match_id in {13613, 21176})
        cric_deliveries = cls.extract_cricsheet_innings_deliveries(cdata, is_regulation_only=is_reg_only)
        cric_df = pd.DataFrame(cric_deliveries)

        aligned_pairs: List[Tuple[pd.Series, Dict[str, Any], Dict[str, Any]]] = []

        # --- BRANCH 1: MINOR OMISSION MATCHES (14130 & 14164) ---
        if local_match_id in {14130, 14164} or warning_disposition == "SAFE_MINOR_OMISSION":
            aligned_pairs = cls._align_minor_omission_match(local_match_id, loc_sorted, cric_deliveries)

        # --- BRANCH 2: REGULATION-ONLY MATCHES (13613 & 21176) ---
        elif is_reg_only:
            aligned_pairs = cls._align_clean_sequential(
                local_match_id, loc_sorted, cric_deliveries, strategy=AlignmentStrategy.REGULATION_ONLY
            )

        # --- BRANCH 3: STANDARD CLEAN VALIDATED MATCHES ---
        else:
            aligned_pairs = cls._align_clean_sequential(
                local_match_id, loc_sorted, cric_deliveries, strategy=AlignmentStrategy.CLEAN_VALIDATED
            )

        # Invariant check: every local delivery must have an aligned counterpart
        if len(aligned_pairs) != len(loc_sorted):
            raise ValueError(
                f"Match {local_match_id}: Aligned pairs count ({len(aligned_pairs)}) "
                f"does not match local delivery count ({len(loc_sorted)})."
            )

        return aligned_pairs

    @classmethod
    def _align_clean_sequential(
        cls,
        local_match_id: int,
        loc_df: pd.DataFrame,
        cric_deliveries: List[Dict[str, Any]],
        strategy: AlignmentStrategy
    ) -> List[Tuple[pd.Series, Dict[str, Any], Dict[str, Any]]]:
        """Aligns clean matches innings-by-innings in sequential 1-to-1 order."""
        cric_df = pd.DataFrame(cric_deliveries)
        aligned = []

        local_innings_list = sorted(loc_df["innings"].unique())
        for inn in local_innings_list:
            loc_inn = loc_df[loc_df["innings"] == inn].reset_index(drop=True)
            cric_inn = cric_df[cric_df["innings"] == inn].reset_index(drop=True)

            if len(loc_inn) != len(cric_inn):
                raise ValueError(
                    f"Match {local_match_id} Innings {inn}: Delivery count mismatch "
                    f"(Local: {len(loc_inn)}, Cricsheet: {len(cric_inn)})."
                )

            for idx in range(len(loc_inn)):
                l_row = loc_inn.iloc[idx]
                c_del = cric_inn.iloc[idx]
                meta = {
                    "alignment_strategy": strategy.value,
                    "omitted_cricsheet_event": False,
                    "cricsheet_over": c_del["over_1based"],
                    "cricsheet_ball": c_del["ball_in_over"],
                    "cricsheet_delivery_index": c_del["cricsheet_delivery_index"],
                    "is_super_over": c_del["is_super_over"]
                }
                aligned.append((l_row, c_del["raw_delivery"], meta))

        return aligned

    @classmethod
    def _align_minor_omission_match(
        cls,
        local_match_id: int,
        loc_df: pd.DataFrame,
        cric_deliveries: List[Dict[str, Any]]
    ) -> List[Tuple[pd.Series, Dict[str, Any], Dict[str, Any]]]:
        """
        Applies verified deterministic over-level mapping for matches 14130 and 14164.
        """
        cric_df = pd.DataFrame(cric_deliveries)
        aligned = []

        for inn in sorted(loc_df["innings"].unique()):
            loc_inn = loc_df[loc_df["innings"] == inn].reset_index(drop=True)
            cric_inn = cric_df[cric_df["innings"] == inn].reset_index(drop=True)

            # Check if this innings has the known omission
            if local_match_id == 14130 and inn == 1:
                # Innings 1: Over 14 local has 5 balls; Cricsheet has 6 balls (ball 3 KL Rahul single omitted)
                over14_map = {1: 1, 2: 2, 3: 4, 4: 5, 5: 6}
                cls._align_over_mapped_innings(
                    loc_inn, cric_inn, omission_over=14, over_map=over14_map, aligned=aligned
                )
            elif local_match_id == 14130 and inn == 2:
                # Innings 2: Over 14 local has 6 balls; Cricsheet has 7 balls (ball 4 Tilak Varma 2 runs omitted)
                over14_map = {1: 1, 2: 2, 3: 3, 4: 5, 5: 6, 6: 7}
                cls._align_over_mapped_innings(
                    loc_inn, cric_inn, omission_over=14, over_map=over14_map, aligned=aligned
                )
            elif local_match_id == 14164 and inn == 1:
                # Innings 1: Over 14 local has 5 balls; Cricsheet has 6 balls (ball 5 Washington Sundar single omitted)
                over14_map = {1: 1, 2: 2, 3: 3, 4: 4, 5: 6}
                cls._align_over_mapped_innings(
                    loc_inn, cric_inn, omission_over=14, over_map=over14_map, aligned=aligned
                )
            elif local_match_id == 14164 and inn == 2:
                # Innings 2: Exactly 95 balls, identical ball-for-ball
                for idx in range(len(loc_inn)):
                    l_row = loc_inn.iloc[idx]
                    c_del = cric_inn.iloc[idx]
                    meta = {
                        "alignment_strategy": AlignmentStrategy.MINOR_OMISSION.value,
                        "omitted_cricsheet_event": False,
                        "cricsheet_over": c_del["over_1based"],
                        "cricsheet_ball": c_del["ball_in_over"],
                        "cricsheet_delivery_index": c_del["cricsheet_delivery_index"],
                        "is_super_over": False
                    }
                    aligned.append((l_row, c_del["raw_delivery"], meta))
            else:
                raise ValueError(f"Unexpected minor omission configuration for match {local_match_id} inn {inn}")

        return aligned

    @classmethod
    def _align_over_mapped_innings(
        cls,
        loc_inn: pd.DataFrame,
        cric_inn: pd.DataFrame,
        omission_over: int,
        over_map: Dict[int, int],
        aligned: List[Tuple[pd.Series, Dict[str, Any], Dict[str, Any]]]
    ):
        """Aligns an innings containing a single known omitted over."""
        max_over = max(loc_inn["overid"].max(), cric_inn["over_1based"].max())
        for o in range(1, max_over + 1):
            l_o = loc_inn[loc_inn["overid"] == o].reset_index(drop=True)
            c_o = cric_inn[cric_inn["over_1based"] == o].reset_index(drop=True)

            if o != omission_over:
                if len(l_o) != len(c_o):
                    raise ValueError(f"Unexpected mismatch in Over {o}: local {len(l_o)} vs cric {len(c_o)}")
                for idx in range(len(l_o)):
                    l_row = l_o.iloc[idx]
                    c_del = c_o.iloc[idx]
                    meta = {
                        "alignment_strategy": AlignmentStrategy.MINOR_OMISSION.value,
                        "omitted_cricsheet_event": False,
                        "cricsheet_over": c_del["over_1based"],
                        "cricsheet_ball": c_del["ball_in_over"],
                        "cricsheet_delivery_index": c_del["cricsheet_delivery_index"],
                        "is_super_over": False
                    }
                    aligned.append((l_row, c_del["raw_delivery"], meta))
            else:
                # Omission over with explicit mapping
                for l_idx, c_target_ball in over_map.items():
                    l_row = l_o[l_o["over_ball_num"] == l_idx].iloc[0]
                    c_del = c_o[c_o["ball_in_over"] == c_target_ball].iloc[0]
                    meta = {
                        "alignment_strategy": AlignmentStrategy.MINOR_OMISSION.value,
                        "omitted_cricsheet_event": True,
                        "cricsheet_over": c_del["over_1based"],
                        "cricsheet_ball": c_del["ball_in_over"],
                        "cricsheet_delivery_index": c_del["cricsheet_delivery_index"],
                        "is_super_over": False
                    }
                    aligned.append((l_row, c_del["raw_delivery"], meta))
