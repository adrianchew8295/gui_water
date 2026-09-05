# 文件名: trendline_engine.py
# 核心功能: 依據 Tom DeMark TD Lines 算法計算阻力線、支撐線與 50/50 多空目標投影

from typing import Dict, List, Tuple, Any
import numpy as np
import pandas as pd

def find_td_pivots(df: pd.DataFrame, window: int = 4) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    td_highs, td_lows = [], []
    if df is None or len(df) < (2 * window + 1):
        return td_highs, td_lows

    high_col = 'high' if 'high' in df.columns else 'High'
    low_col = 'low' if 'low' in df.columns else 'Low'
    time_col = 'time_clean' if 'time_clean' in df.columns else ('time_key' if 'time_key' in df.columns else df.columns[0])

    highs, lows = df[high_col].values, df[low_col].values
    times = df[time_col].astype(str).values
    n = len(df)

    for i in range(window, n - window):
        curr_high = highs[i]
        curr_low = lows[i]

        if np.all(curr_high >= highs[i - window : i]) and np.all(curr_high >= highs[i + 1 : i + window + 1]):
            td_highs.append({"bar_idx": i, "time": str(times[i]), "price": float(curr_high)})

        if np.all(curr_low <= lows[i - window : i]) and np.all(curr_low <= lows[i + 1 : i + window + 1]):
            td_lows.append({"bar_idx": i, "time": str(times[i]), "price": float(curr_low)})

    return td_highs, td_lows

def compute_demark_trendlines(df: pd.DataFrame, window: int = 4) -> Dict[str, Any]:
    res = {
        "status": "fail",
        "resistance_line": [],
        "support_line": [],
        "curr_res_val": None,
        "curr_sup_val": None,
        "bull_target_1": None,
        "bull_target_2": None,
        "bear_target_1": None,
        "bear_target_2": None
    }
    if df is None or len(df) < (2 * window + 1):
        return res

    td_highs, td_lows = find_td_pivots(df, window=window)
    last_idx = len(df) - 1
    time_col = 'time_clean' if 'time_clean' in df.columns else ('time_key' if 'time_key' in df.columns else df.columns[0])
    times = df[time_col].astype(str).values

    # 計算阻力線
    if len(td_highs) >= 2:
        p1, p2 = td_highs[-2], td_highs[-1]
        dx, dy = p2["bar_idx"] - p1["bar_idx"], p2["price"] - p1["price"]
        if dx > 0:
            slope = dy / dx
            curr_res_val = p2["price"] + slope * (last_idx - p2["bar_idx"])
            res["curr_res_val"] = round(curr_res_val, 2)
            res["resistance_line"] = [{"time": str(times[i]), "value": round(float(p1["price"] + slope * (i - p1["bar_idx"])), 2)} for i in range(p1["bar_idx"], last_idx + 1)]

    # 計算支撐線
    if len(td_lows) >= 2:
        p1, p2 = td_lows[-2], td_lows[-1]
        dx, dy = p2["bar_idx"] - p1["bar_idx"], p2["price"] - p1["price"]
        if dx > 0:
            slope = dy / dx
            curr_sup_val = p2["price"] + slope * (last_idx - p2["bar_idx"])
            res["curr_sup_val"] = round(curr_sup_val, 2)
            res["support_line"] = [{"time": str(times[i]), "value": round(float(p1["price"] + slope * (i - p1["bar_idx"])), 2)} for i in range(p1["bar_idx"], last_idx + 1)]

    # 德馬克突破目標價量化投影 (TD Target Projections)
    if res["curr_res_val"] and res["curr_sup_val"]:
        channel_height = abs(res["curr_res_val"] - res["curr_sup_val"])
        res["bull_target_1"] = round(res["curr_res_val"] + channel_height * 0.618, 2)
        res["bull_target_2"] = round(res["curr_res_val"] + channel_height * 1.0, 2)
        res["bear_target_1"] = round(res["curr_sup_val"] - channel_height * 0.618, 2)
        res["bear_target_2"] = round(res["curr_sup_val"] - channel_height * 1.0, 2)
        res["status"] = "success"

    return res
