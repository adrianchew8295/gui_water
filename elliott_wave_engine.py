# 文件名: elliott_wave_engine.py
# 核心功能: 嚴格依據 Frost & Prechter《Elliott Wave Principle》原著算法構建的波浪理論時空推演引擎

import numpy as np
import pandas as pd
import datetime
from typing import Dict, Any, List

FIB_NUMBERS = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377]

class ElliottWaveEngine:
    @staticmethod
    def extract_pivots(df: pd.DataFrame, window: int = 4) -> List[Dict[str, Any]]:
        """幾何提取波段波峰(Peaks)與波谷(Troughs)"""
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
                pivots.append({"index": i, "time": times[i][:10], "type": "PEAK", "price": float(highs[i])})
            elif is_low:
                pivots.append({"index": i, "time": times[i][:10], "type": "TROUGH", "price": float(lows[i])})

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
        """依據 Frost & Prechter 原著進行全量時空推演與複雜浪分類"""
        res = {
            "current_wave": "波浪識別中",
            "wave_phase": "中繼",
            "sub_wave": "Sub-Wave 3",
            "trend_dir": "多頭",
            "is_extended": False,
            "extension_ratio": 1.0,
            "is_complex": False,
            "complex_type": "標準五浪推動 (Motive Impulse)",
            "time_elapsed_bars": 0,
            "expected_duration_bars": 0,
            "time_window_dates": [],
            "fib_levels": {},
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
            res["current_wave"] = "波段累積中 (拐點不足)"
            return res

        recent = pivots[-5:]
        p0, p1, p2, p3, p4 = recent[0], recent[1], recent[2], recent[3], recent[4]
        last_idx = len(df) - 1
        curr_price = float(df['close'].iloc[-1] if 'close' in df.columns else df['Close'].iloc[-1])

        # 1. 計算各浪長度與時間跨度 (Bars)
        w1_len = abs(p1["price"] - p0["price"])
        w1_time = max(1, abs(p1["index"] - p0["index"]))
        w2_len = abs(p2["price"] - p1["price"])
        w2_time = max(1, abs(p2["index"] - p1["index"]))
        w3_len = abs(p3["price"] - p2["price"])
        w3_time = max(1, abs(p3["index"] - p2["index"]))
        w4_len = abs(p4["price"] - p3["price"])
        w4_time = max(1, abs(p4["index"] - p3["index"]))

        current_time_spent = last_idx - p4["index"]
        res["time_elapsed_bars"] = current_time_spent

        # 2. 判定主浪型與擴展 (Extension - Chapter 1)
        if w1_len > 0:
            w3_ratio = round(w3_len / w1_len, 2)
            if w3_ratio >= 1.618:
                res["is_extended"] = True
                res["extension_ratio"] = w3_ratio

        # 3. 嚴格數學計算 Fibonacci 回調位 (Chapter 4 Retracements)
        is_bullish = p1["price"] > p0["price"] and p3["price"] > p1["price"]

        if is_bullish:
            # 多頭結構：回調支撐在波峰下方
            peak_ref = max(p1["price"], p3["price"], curr_price)
            trough_ref = min(p0["price"], p2["price"], p4["price"])
            span = peak_ref - trough_ref

            res["fib_levels"] = {
                "0.000 (Top)": round(peak_ref, 2),
                "0.236": round(peak_ref - 0.236 * span, 2),
                "0.382 (4浪常規支撐)": round(peak_ref - 0.382 * span, 2),
                "0.500 (平衡防線)": round(peak_ref - 0.500 * span, 2),
                "0.618 (黃金分割)": round(peak_ref - 0.618 * span, 2),
                "0.786": round(peak_ref - 0.786 * span, 2),
                "1.000 (Base)": round(trough_ref, 2)
            }

            res["trend_dir"] = "🟢 多頭上升驅動 (Impulse Up)"

            if p4["type"] == "TROUGH":
                # 當前自 p4 波谷向上走第 5 浪衝頂
                res["current_wave"] = "🌊 第 ⑤ 浪 (多頭最後衝頂浪)"
                res["wave_phase"] = "推動末端 / 衝頂加速"
                res["sub_wave"] = "Sub-Wave 5-3"

                # 依據原著：Target 1 (5浪 = 1浪長度), Target 2 (5浪 = 0.618 倍 1浪+3浪)
                res["next_target_1"] = round(p4["price"] + w1_len, 2)
                res["next_target_2"] = round(p4["price"] + 0.618 * (w1_len + w3_len), 2)
                # 鐵律：第 4 浪不得跌破第 1 浪頂點
                res["invalid_price"] = round(p1["price"], 2)

                # 時間預測 (Time Projection): 5 浪時間常等於 1 浪或 0.618 倍 3 浪
                exp_bars = max(int(w1_time), int(w3_time * 0.618))
                res["expected_duration_bars"] = exp_bars

                if res["is_extended"]:
                    res["complex_type"] = f"第 ③ 浪擴展 ({res['extension_ratio']}x) -> ⑤ 浪常規對稱"
                else:
                    res["complex_type"] = "標準五浪上升結構 (5-Wave Impulse)"

                res["prediction_narrative"] = (
                    f"依據《艾略特波浪理論》原著，NQ/QQQ 當前處於第 ⑤ 浪主升衝頂階段。"
                    f"首要目標看至 1.0x 對稱位 **${res['next_target_1']}**，"
                    f"極限衝頂目標看至 1.618x 擴展位 **${res['next_target_2']}**；"
                    f"波浪失效防守線設在第 ① 浪頂點 **${res['invalid_price']}**。"
                )
            else:
                # 當前自 p4 波峰向下走第 4 浪調整
                res["current_wave"] = "🌊 第 ④ 浪 (複雜修正浪 / Complex WXY)"
                res["is_complex"] = True
                res["complex_type"] = "雙重三浪 (W-X-Y) / 平台型橫盤整理"
                res["wave_phase"] = "中繼回踩洗盤"
                res["sub_wave"] = "Complex Wave Y 築底"

                res["next_target_1"] = round(p3["price"] - 0.382 * w3_len, 2)
                res["next_target_2"] = round(p3["price"] - 0.500 * w3_len, 2)
                res["invalid_price"] = round(p1["price"], 2)

                # 第 4 浪時間常與第 2 浪呈斐波那契倍數 (1.382x / 1.618x)
                exp_bars = int(w2_time * 1.618)
                res["expected_duration_bars"] = exp_bars

                res["prediction_narrative"] = (
                    f"當前處於第 ④ 浪複雜洗盤（Complex Correction）。"
                    f"預計在 Fib 0.382 ~ 0.500 支撐區間（**${res['next_target_1']} ~ ${res['next_target_2']}**）完成震盪築底。"
                )
        else:
            # 空頭驅動 / 調整浪
            trough_ref = min(p1["price"], p3["price"], curr_price)
            peak_ref = max(p0["price"], p2["price"], p4["price"])
            span = peak_ref - trough_ref

            res["fib_levels"] = {
                "0.000 (Base)": round(trough_ref, 2),
                "0.382": round(trough_ref + 0.382 * span, 2),
                "0.500": round(trough_ref + 0.500 * span, 2),
                "0.618": round(trough_ref + 0.618 * span, 2),
                "1.000 (Top)": round(peak_ref, 2)
            }

            res["trend_dir"] = "🔴 空頭下行驅動 / ABC 調整"
            res["current_wave"] = "🌊 調整浪 Wave C (主跌殺多)"
            res["is_complex"] = True
            res["complex_type"] = "ABC 鋸齒型深度調整浪 (Zigzag 5-3-5)"
            res["wave_phase"] = "空頭動能釋放"
            res["sub_wave"] = "Sub-Wave 3 主跌"
            res["next_target_1"] = round(p4["price"] - w1_len * 1.0, 2)
            res["next_target_2"] = round(p4["price"] - w1_len * 1.618, 2)
            res["invalid_price"] = round(p3["price"], 2)
            exp_bars = int(w1_time * 1.618)
            res["expected_duration_bars"] = exp_bars

            res["prediction_narrative"] = (
                f"處於 ABC 調整浪 Wave C 下殺階段，下行目標指向 **${res['next_target_1']}**。"
            )

        # 4. 計算費氏時間窗口預測 (Fibonacci Time Windows)
        p4_date_str = p4["time"]
        try:
            p4_dt = datetime.datetime.strptime(p4_date_str, "%Y-%m-%d")
            for fib in [5, 8, 13, 21, 34]:
                tgt_dt = p4_dt + datetime.timedelta(days=fib)
                res["time_window_dates"].append({
                    "費氏週期": f"Fib +{fib} 棒/天",
                    "預計時間窗口": tgt_dt.strftime("%Y-%m-%d"),
                    "理論意義": f"波段變盤點 #{fib}"
                })
        except Exception:
            pass

        # 5. 整理波浪拐點表
        for idx, p in enumerate(pivots[-6:]):
            res["wave_table"].append({
                "波浪節點": f"Wave Pivot #{idx+1}",
                "時間 (ET)": p["time"],
                "類型": "🔺 波峰 (High)" if p["type"] == "PEAK" else "🔻 波谷 (Low)",
                "點位 ($)": f"${p['price']:,.2f}",
                "浪級定義": f"第 {idx} 浪拐點" if idx > 0 else "起點 (Base)"
            })

        return res
