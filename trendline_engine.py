# 文件名: trendline_engine.py
# 核心功能: 德马克 TD 趋势线算法 (含安全边界检测，防止 IndexError / ZeroDivisionError)

import pandas as pd
import numpy as np

def find_td_pivots(df: pd.DataFrame, window: int = 4):
    """提取 TD High 与 TD Low 极值点"""
    td_highs, td_lows = [], []
    if df.empty or len(df) < (window * 2 + 1):
        return td_highs, td_lows

    highs = df['high'].values
    lows = df['low'].values
    times = df['time_clean'].values if 'time_clean' in df.columns else df.index.values

    for i in range(window, len(df) - window):
        # TD High: 当期最高价严格大于前后 window 根
        if all(highs[i] > highs[i - k] for k in range(1, window + 1)) and \
           all(highs[i] > highs[i + k] for k in range(1, window + 1)):
            td_highs.append({"index": i, "time": times[i], "value": float(highs[i])})

        # TD Low: 当期最低价严格小于前后 window 根
        if all(lows[i] < lows[i - k] for k in range(1, window + 1)) and \
           all(lows[i] < lows[i + k] for k in range(1, window + 1)):
            td_lows.append({"index": i, "time": times[i], "value": float(lows[i])})

    return td_highs, td_lows

def compute_demark_trendlines(df: pd.DataFrame, window: int = 4) -> dict:
    """计算最新德马克动态阻力线、支撑线及 50/50 目标推演"""
    res = {
        "resistance_line": [], "support_line": [],
        "curr_res_val": None, "curr_sup_val": None,
        "bull_target_1": None, "bull_target_2": None,
        "bear_target_1": None, "bear_target_2": None
    }
    
    if df.empty or len(df) < (window * 2 + 1):
        return res

    td_highs, td_lows = find_td_pivots(df, window)
    last_idx = len(df) - 1
    times = df['time_clean'].values if 'time_clean' in df.columns else df.index.values

    # 1. 阻力线 (连接最近两个 TD High)
    if len(td_highs) >= 2:
        p1, p2 = td_highs[-2], td_highs[-1]
        x1, y1 = p1["index"], p1["value"]
        x2, y2 = p2["index"], p2["value"]
        if x2 != x1:
            slope = (y2 - y1) / (x2 - x1)
            curr_val = y2 + slope * (last_idx - x2)
            res["curr_res_val"] = round(float(curr_val), 2)
            res["resistance_line"] = [
                {"time": p1["time"], "value": y1},
                {"time": p2["time"], "value": y2},
                {"time": times[last_idx], "value": res["curr_res_val"]}
            ]

    # 2. 支撑线 (连接最近两个 TD Low)
    if len(td_lows) >= 2:
        p1, p2 = td_lows[-2], td_lows[-1]
        x1, y1 = p1["index"], p1["value"]
        x2, y2 = p2["index"], p2["value"]
        if x2 != x1:
            slope = (y2 - y1) / (x2 - x1)
            curr_val = y2 + slope * (last_idx - x2)
            res["curr_sup_val"] = round(float(curr_val), 2)
            res["support_line"] = [
                {"time": p1["time"], "value": y1},
                {"time": p2["time"], "value": y2},
                {"time": times[last_idx], "value": res["curr_sup_val"]}
            ]

    # 3. 50/50 空间测算
    if res["curr_res_val"] and res["curr_sup_val"]:
        h = abs(res["curr_res_val"] - res["curr_sup_val"])
        res["bull_target_1"] = round(res["curr_res_val"] + h * 0.618, 2)
        res["bull_target_2"] = round(res["curr_res_val"] + h * 1.0, 2)
        res["bear_target_1"] = round(res["curr_sup_val"] - h * 0.618, 2)
        res["bear_target_2"] = round(res["curr_sup_val"] - h * 1.0, 2)

    return res
