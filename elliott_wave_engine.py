# 文件名: elliott_wave_engine.py
# 核心功能: 艾略特波浪高階量化 (主升浪/擴展浪 Extension/複雜調整浪 Complex/Fib 回調)

import numpy as np
import pandas as pd
from typing import Dict, Any, List

class ElliottWaveEngine:
    @staticmethod
    def extract_pivots(df: pd.DataFrame, window: int = 4) -> List[Dict[str, Any]]:
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
        res = {
            "current_wave": "波浪形態識別中",
            "wave_phase": "中繼",
            "sub_wave": "Sub-Wave 3",
            "trend_dir": "多頭",
            "is_extended": False,
            "extension_ratio": 1.0,
            "is_complex": False,
            "complex_type": "標準驅動浪",
            "time_elapsed_hrs": 0,
            "expected_duration_hrs": 0,
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
            res["current_wave"] = "波段積累中 (點位不足)"
            return res

        recent = pivots[-5:]
        p0, p1, p2, p3, p4 = recent[0], recent[1], recent[2], recent[3], recent[4]
        last_idx = len(df) - 1
        curr_price = float(df['close'].iloc[-1] if 'close' in df.columns else df['Close'].iloc[-1])

        # 計算主要波段長度
        w1_len = abs(p1["price"] - p0["price"])
        w1_time = abs(p1["index"] - p0["index"])
        w2_len = abs(p2["price"] - p1["price"])
        w3_len = abs(p3["price"] - p2["price"])
        w4_len = abs(p4["price"] - p3["price"])

        current_time_spent = last_idx - p4["index"]
        res["time_elapsed_hrs"] = current_time_spent

        # 計算最近一輪主浪的斐波那契回調水位 (Fib Retracement Levels)
        fib_base_high = max(p3["price"], p1["price"], curr_price)
        fib_base_low = min(p0["price"], p2["price"], p4["price"])
        diff = fib_base_high - fib_base_low

        res["fib_levels"] = {
            "0.000 (Top)": round(fib_base_high, 2),
            "0.236": round(fib_base_high - 0.236 * diff, 2),
            "0.382": round(fib_base_high - 0.382 * diff, 2),
            "0.500": round(fib_base_high - 0.500 * diff, 2),
            "0.618 (黃金位)": round(fib_base_high - 0.618 * diff, 2),
            "0.786": round(fib_base_high - 0.786 * diff, 2),
            "1.000 (Base)": round(fib_base_low, 2)
        }

        # 判定擴展浪 (Extension Wave: 3浪 >= 1.618倍 1浪)
        if w1_len > 0:
            w3_ratio = w3_len / w1_len
            if w3_ratio >= 1.618:
                res["is_extended"] = True
                res["extension_ratio"] = round(w3_ratio, 2)

        # 判定複雜浪 (Complex Wave / ABC / 橫盤修復)
        is_bullish = p1["price"] > p0["price"] and p3["price"] > p1["price"]
        
        if is_bullish:
            res["trend_dir"] = "🟢 多頭上升驅動浪 (Impulse Up)"
            if p4["type"] == "TROUGH":
                if res["is_extended"]:
                    res["current_wave"] = "🌊 第 ⑤ 浪 (強勢擴展衝頂浪)"
                    res["complex_type"] = f"第 3 浪已擴展 ({res['extension_ratio']}x) -> 5 浪加速衝刺"
                else:
                    res["current_wave"] = "🌊 第 ⑤ 浪 (常規衝頂浪)"
                    res["complex_type"] = "標準 5 浪結構推動"

                res["wave_phase"] = "推動末端 / 衝頂加速"
                res["sub_wave"] = "Sub-Wave 5-3 (子浪加速)"
                res["next_target_1"] = round(p4["price"] + w1_len, 2)
                res["next_target_2"] = round(p4["price"] + 0.618 * (w1_len + w3_len), 2)
                res["invalid_price"] = round(p1["price"], 2)
                res["expected_duration_hrs"] = int(w1_time * 1.2)
                res["prediction_narrative"] = (
                    f"當前處於第 ⑤ 浪衝頂階段。" +
                    (f"前期第 ③ 浪走出 **{res['extension_ratio']} 倍超級擴展浪**，多頭動能強勁！" if res["is_extended"] else "") +
                    f"首要目標指向 **${res['next_target_1']}**，擴展目標 **${res['next_target_2']}**；防守破位點為 **${res['invalid_price']}**。"
                )
            else:
                res["current_wave"] = "🌊 第 ④ 浪 (複雜修正浪 / Complex WXY)"
                res["is_complex"] = True
                res["complex_type"] = "橫盤三角收斂 / 平台型複雜修正"
                res["wave_phase"] = "中繼回調洗盤"
                res["sub_wave"] = "Complex Wave C / Y 築底"
                res["next_target_1"] = round(p3["price"] - 0.382 * w3_len, 2)
                res["next_target_2"] = round(p3["price"] - 0.500 * w3_len, 2)
                res["invalid_price"] = round(p1["price"], 2)
                res["expected_duration_hrs"] = int(w1_time * 1.618)
                res["prediction_narrative"] = (
                    f"當前處於第 ④ 浪複雜洗盤（Complex Correction）。預計在 Fib 0.382 ~ 0.50 支撐區（**${res['next_target_1']} ~ ${res['next_target_2']}**）完成震盪築底，隨後開啟第 ⑤ 浪。"
                )
        else:
            res["trend_dir"] = "🔴 空頭下行驅動浪 / ABC 調整"
            res["current_wave"] = "🌊 調整浪 Wave C (主跌殺多)"
            res["is_complex"] = True
            res["complex_type"] = "ABC 鋸齒型深度調整浪"
            res["wave_phase"] = "空頭釋放"
            res["sub_wave"] = "Sub-Wave 3 主跌"
            res["next_target_1"] = round(p4["price"] - w1_len * 1.618, 2)
            res["next_target_2"] = round(p4["price"] - w1_len * 2.618, 2)
            res["invalid_price"] = round(p3["price"], 2)
            res["expected_duration_hrs"] = int(w1_time * 1.618)
            res["prediction_narrative"] = (
                f"處於 ABC 調整浪的 Wave C 下殺。空間指向 **${res['next_target_1']}**，反彈突破 **${res['invalid_price']}** 則結構失效。"
            )

        for idx, p in enumerate(pivots[-6:]):
            res["wave_table"].append({
                "波浪節點": f"Wave Pivot #{idx+1}",
                "時間": p["time"][:10],
                "類型": "🔺 波峰 (High)" if p["type"] == "PEAK" else "🔻 波谷 (Low)",
                "點位 ($)": f"{p['price']:,.2f}",
                "浪級定義": f"第 {idx} 浪拐點" if idx > 0 else "起點 (Base)"
            })

        return res
