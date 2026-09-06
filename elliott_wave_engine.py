# 文件名: elliott_wave_engine.py
# 核心功能: 艾略特波浪理論客觀量化 (波浪計數 + 時間週期 + 1H 走勢預測)

import numpy as np
import pandas as pd
from typing import Dict, Any, List

class ElliottWaveEngine:
    @staticmethod
    def extract_pivots(df: pd.DataFrame, window: int = 5) -> List[Dict[str, Any]]:
        """透過幾何算法客觀提取波段波峰(Highs)與波谷(Lows)"""
        pivots = []
        if df.empty or len(df) < (window * 2 + 1):
            return pivots

        high_col = 'high' if 'high' in df.columns else 'High'
        low_col = 'low' if 'low' in df.columns else 'Low'
        time_col = 'time_key' if 'time_key' in df.columns else df.columns[0]

        highs = df[high_col].values
        lows = df[low_col].values
        times = df[time_col].astype(str).values
        n = len(df)

        for i in range(window, n - window):
            is_high = np.all(highs[i] >= highs[i - window : i]) and np.all(highs[i] >= highs[i + 1 : i + window + 1])
            is_low = np.all(lows[i] <= lows[i - window : i]) and np.all(lows[i] <= lows[i + 1 : i + window + 1])

            if is_high:
                pivots.append({"index": i, "time": times[i], "type": "PEAK", "price": float(highs[i])})
            elif is_low:
                pivots.append({"index": i, "time": times[i], "type": "TROUGH", "price": float(lows[i])})

        # 過濾同向連續點，保留交替頂底
        clean_pivots = []
        for p in pivots:
            if not clean_pivots:
                clean_pivots.append(p)
            else:
                if clean_pivots[-1]["type"] != p["type"]:
                    clean_pivots.append(p)
                else:
                    if p["type"] == "PEAK" and p["price"] > clean_pivots[-1]["price"]:
                        clean_pivots[-1] = p
                    elif p["type"] == "TROUGH" and p["price"] < clean_pivots[-1]["price"]:
                        clean_pivots[-1] = p

        return clean_pivots

    @classmethod
    def analyze_wave_structure(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """全面波浪理論分析：判定當前在 Wave 幾，並推演時間與點位"""
        res = {
            "current_wave": "波浪形態識別中",
            "wave_phase": "中繼",
            "sub_wave": "Sub-Wave 3",
            "trend_dir": "多頭",
            "time_elapsed_hrs": 0,
            "expected_duration_hrs": 0,
            "next_target_1": 0.0,
            "next_target_2": 0.0,
            "invalid_price": 0.0,
            "prediction_narrative": "",
            "wave_table": []
        }

        if df.empty or len(df) < 50:
            return res

        pivots = cls.extract_pivots(df, window=4)
        if len(pivots) < 5:
            res["current_wave"] = "波段積累中 (點位不足)"
            return res

        recent = pivots[-5:]
        p0, p1, p2, p3, p4 = recent[0], recent[1], recent[2], recent[3], recent[4]
        curr_price = float(df['close'].iloc[-1] if 'close' in df.columns else df['Close'].iloc[-1])
        last_idx = len(df) - 1

        # 計算波長與時間跨度 (Bars = 1H)
        w1_len = abs(p1["price"] - p0["price"])
        w1_time = abs(p1["index"] - p0["index"])
        
        w2_len = abs(p2["price"] - p1["price"])
        w2_time = abs(p2["index"] - p1["index"])

        w3_len = abs(p3["price"] - p2["price"])
        w3_time = abs(p3["index"] - p2["index"])

        w4_len = abs(p4["price"] - p3["price"])
        w4_time = abs(p4["index"] - p3["index"])

        current_time_spent = last_idx - p4["index"]
        res["time_elapsed_hrs"] = current_time_spent

        # 判定五浪推動 vs ABC調整
        is_bullish = p1["price"] > p0["price"] and p3["price"] > p1["price"]
        
        if is_bullish:
            res["trend_dir"] = "🟢 多頭上升驅動浪 (Impulse Up)"
            # 當前從 p4 啟動：若 p4 是波谷，當前正在走第 5 浪衝頂
            if p4["type"] == "TROUGH":
                res["current_wave"] = "🌊 第 ⑤ 浪 (最後衝頂推動浪)"
                res["wave_phase"] = "推動末端 / 衝頂加速"
                res["sub_wave"] = "Mini 5-3 (子浪主升)"
                
                # 斐波那契推算：第 5 浪通常等於第 1 浪長度，或 0.618 倍 (1浪+3浪)
                res["next_target_1"] = round(p4["price"] + w1_len, 2)
                res["next_target_2"] = round(p4["price"] + 0.618 * (w1_len + w3_len), 2)
                res["invalid_price"] = round(p1["price"], 2) # 4浪不應破1浪頂
                res["expected_duration_hrs"] = int(w1_time * 1.2)

                res["prediction_narrative"] = (
                    f"根據波浪時間與空間對稱性，NQ Main 當前處於第 ⑤ 浪衝頂階段。"
                    f"接下來 1 小時預計維持慣性上攻，首要目標看至 **{res['next_target_1']}**，"
                    f"極限衝頂目標 **{res['next_target_2']}**；若 1H 收盤跌破 **{res['invalid_price']}** 則波浪結構失效轉入 ABC 調整。"
                )
            else:
                # p4 是波峰，當前正在走第 4 浪回踩
                res["current_wave"] = "🌊 第 ④ 浪 (回踩修復浪)"
                res["wave_phase"] = "中繼回踩"
                res["sub_wave"] = "Sub-Wave C 衰竭"
                res["next_target_1"] = round(p3["price"] - 0.382 * w3_len, 2)
                res["next_target_2"] = round(p3["price"] - 0.500 * w3_len, 2)
                res["invalid_price"] = round(p1["price"], 2)
                res["expected_duration_hrs"] = int(w2_time * 1.382)

                res["prediction_narrative"] = (
                    f"NQ Main 當前正處於第 ④ 浪回踩中。接下來 1 小時將尋求 0.382/0.50 支撐，"
                    f"預計在 **{res['next_target_1']} ~ {res['next_target_2']}** 區間企穩，為隨後的第 ⑤ 浪主升蓄勢。"
                )
        else:
            # 空頭下跌浪 / 調整浪
            res["trend_dir"] = "🔴 空頭下行驅動浪 / ABC 調整"
            res["current_wave"] = "🌊 調整浪 Wave C (主跌殺多)"
            res["wave_phase"] = "空頭釋放"
            res["sub_wave"] = "Sub-Wave 3 主跌"
            res["next_target_1"] = round(p4["price"] - w1_len * 1.618, 2)
            res["next_target_2"] = round(p4["price"] - w1_len * 2.618, 2)
            res["invalid_price"] = round(p3["price"], 2)
            res["expected_duration_hrs"] = int(w1_time * 1.618)
            res["prediction_narrative"] = (
                f"NQ Main 處於 ABC 調整浪的 Wave C 下殺。接下來 1 小時將加速尋底，"
                f"空頭空間指向 **{res['next_target_1']}**，反彈突破 **{res['invalid_price']}** 則結構重置。"
            )

        # 整理歷史五浪節奏表
        for idx, p in enumerate(pivots[-6:]):
            res["wave_table"].append({
                "波浪節點": f"Wave Pivot #{idx+1}",
                "時間 (ET)": p["time"],
                "類型": "🔺 波峰 (High)" if p["type"] == "PEAK" else "🔻 波谷 (Low)",
                "點位 ($)": f"{p['price']:,.2f}",
                "浪級定義": f"第 {idx} 浪拐點" if idx > 0 else "起點 (Base)"
            })

        return res
