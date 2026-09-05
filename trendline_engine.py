# ==========================================
# 檔案 1: trendline_engine.py
# 核心功能: 德馬克 TD Lines 算法獨立計算引擎
# ==========================================

from typing import Dict, List, Tuple, Any, Optional
import pandas as pd
import numpy as np


def find_td_pivots(
    df: pd.DataFrame, 
    window: int = 4
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    識別 TD Supply Points (頂點) 與 TD Demand Points (底點)
    
    規則:
    - TD High: 當前最高價大於前後各 window 根 K 線的最高價
    - TD Low:  當前最低價小於前後各 window 根 K 線的最低價
    """
    td_highs: List[Dict[str, Any]] = []
    td_lows: List[Dict[str, Any]] = []

    if df is None or len(df) < (2 * window + 1):
        return td_highs, td_lows

    # 確保標準列名存在
    high_col = "High" if "High" in df.columns else "high"
    low_col = "Low" if "Low" in df.columns else "low"
    
    if high_col not in df.columns or low_col not in df.columns:
        return td_highs, td_lows

    highs = df[high_col].values
    lows = df[low_col].values
    index_vals = df.index.tolist()

    total_len = len(df)

    # 左右各保留 window 根 K 線進行比對
    for i in range(window, total_len - window):
        curr_high = highs[i]
        curr_low = lows[i]

        left_highs = highs[i - window : i]
        right_highs = highs[i + 1 : i + window + 1]

        left_lows = lows[i - window : i]
        right_lows = lows[i + 1 : i + window + 1]

        # TD High 判定
        if np.all(curr_high > left_highs) and np.all(curr_high > right_highs):
            td_highs.append({
                "bar_idx": i,
                "timestamp": index_vals[i],
                "price": float(curr_high)
            })

        # TD Low 判定
        if np.all(curr_low < left_lows) and np.all(curr_low < right_lows):
            td_lows.append({
                "bar_idx": i,
                "timestamp": index_vals[i],
                "price": float(curr_low)
            })

    return td_highs, td_lows


def compute_demark_trendlines(
    df: pd.DataFrame, 
    window: int = 4
) -> Dict[str, Any]:
    """
    計算最新一組 TD 阻力線與支撐線及其延伸到當前最新 K 線的動態點位
    """
    result: Dict[str, Any] = {
        "status": "fail",
        "resistance": None,
        "support": None,
        "curr_res_val": None,
        "curr_sup_val": None
    }

    if df is None or len(df) < (2 * window + 1):
        return result

    td_highs, td_lows = find_td_pivots(df, window=window)
    last_bar_idx = len(df) - 1
    last_timestamp = df.index[-1]

    # 計算阻力線 (需要最近的 2 個 TD High)
    if len(td_highs) >= 2:
        p1 = td_highs[-2]
        p2 = td_highs[-1]
        
        dx = p2["bar_idx"] - p1["bar_idx"]
        dy = p2["price"] - p1["price"]
        
        if dx > 0:
            slope = dy / dx
            curr_res_val = p2["price"] + slope * (last_bar_idx - p2["bar_idx"])
            
            result["resistance"] = {
                "p1": p1,
                "p2": p2,
                "slope": float(slope),
                "ext_bar_idx": last_bar_idx,
                "ext_timestamp": last_timestamp,
                "ext_price": float(curr_res_val)
            }
            result["curr_res_val"] = float(curr_res_val)

    # 計算支撐線 (需要最近的 2 個 TD Low)
    if len(td_lows) >= 2:
        p1 = td_lows[-2]
        p2 = td_lows[-1]
        
        dx = p2["bar_idx"] - p1["bar_idx"]
        dy = p2["price"] - p1["price"]
        
        if dx > 0:
            slope = dy / dx
            curr_sup_val = p2["price"] + slope * (last_bar_idx - p2["bar_idx"])
            
            result["support"] = {
                "p1": p1,
                "p2": p2,
                "slope": float(slope),
                "ext_bar_idx": last_bar_idx,
                "ext_timestamp": last_timestamp,
                "ext_price": float(curr_sup_val)
            }
            result["curr_sup_val"] = float(curr_sup_val)

    if result["resistance"] is not None or result["support"] is not None:
        result["status"] = "success"

    return result
