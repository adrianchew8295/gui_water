# 文件名: trendline_engine.py
# 作用: 依據 Tom DeMark TD Lines 算法客觀量化計算支撐與阻力趨勢線

import numpy as np
import pandas as pd

def find_td_pivots(df: pd.DataFrame, window: int = 4):
    if df is None or len(df) < (2 * window + 1):
        return [], []

    high_col = 'High' if 'High' in df.columns else 'high'
    low_col = 'Low' if 'Low' in df.columns else 'low'

    highs = df[high_col].values
    lows = df[low_col].values
    n = len(df)
    
    td_highs = [] # (index_pos, timestamp, price)
    td_lows = []  # (index_pos, timestamp, price)
    
    for i in range(window, n - window):
        # 判定 TD High: 當前高點大於前後 window 根的高點
        if all(highs[i] >= highs[i - j] for j in range(1, window + 1)) and \
           all(highs[i] >= highs[i + j] for j in range(1, window + 1)):
            td_highs.append((i, df.index[i], highs[i]))
            
        # 判定 TD Low: 當前低點小於前後 window 根的低點
        if all(lows[i] <= lows[i - j] for j in range(1, window + 1)) and \
           all(lows[i] <= lows[i + j] for j in range(1, window + 1)):
            td_lows.append((i, df.index[i], lows[i]))
            
    return td_highs, td_lows

def compute_demark_trendlines(df: pd.DataFrame, window: int = 4):
    if df is None or len(df) < (window * 2 + 5):
        return None
        
    td_highs, td_lows = find_td_pivots(df, window=window)
    n = len(df)
    current_idx = n - 1
    
    res = {
        "status": "success",
        "resistance": None,
        "support": None,
        "curr_res_val": None,
        "curr_sup_val": None
    }
    
    # 1. 阻力趨勢線 (取最後兩個 TD High 頂點向最新 K 線延伸)
    if len(td_highs) >= 2:
        p1, p2 = td_highs[-2], td_highs[-1]
        i1, t1, y1 = p1
        i2, t2, y2 = p2
        if i2 > i1:
            slope_res = (y2 - y1) / (i2 - i1)
            curr_res = y2 + slope_res * (current_idx - i2)
            res["resistance"] = {
                "p1": {"timestamp": t1, "price": float(y1)},
                "p2": {"timestamp": t2, "price": float(y2)},
                "ext_timestamp": df.index[current_idx],
                "ext_price": float(curr_res),
                "slope": float(slope_res)
            }
            res["curr_res_val"] = round(curr_res, 2)
        
    # 2. 支撐趨勢線 (取最後兩個 TD Low 底點向最新 K 線延伸)
    if len(td_lows) >= 2:
        p1, p2 = td_lows[-2], td_lows[-1]
        i1, t1, y1 = p1
        i2, t2, y2 = p2
        if i2 > i1:
            slope_sup = (y2 - y1) / (i2 - i1)
            curr_sup = y2 + slope_sup * (current_idx - i2)
            res["support"] = {
                "p1": {"timestamp": t1, "price": float(y1)},
                "p2": {"timestamp": t2, "price": float(y2)},
                "ext_timestamp": df.index[current_idx],
                "ext_price": float(curr_sup),
                "slope": float(slope_sup)
            }
            res["curr_sup_val"] = round(curr_sup, 2)
        
    return res
