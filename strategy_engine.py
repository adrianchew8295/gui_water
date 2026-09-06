# 文件名: strategy_engine.py
# 核心職責: 【獨立策略大腦】1H EMA20 日內門禁 + 2B頂底假突破 + VPA雙色形態 + 0DTE智能換算

import numpy as np
import pandas as pd

class StrategyEngine:
    """量化策略計算中樞"""

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """計算 ATR14 波動率"""
        if len(df) < 2:
            return pd.Series([1.0] * len(df))
        high = df['high']
        low = df['low']
        close = df['close'].shift(1).bfill()
        tr = np.maximum(high - low, np.maximum((high - close).abs(), (low - close).abs()))
        return tr.rolling(window=period).mean().bfill()

    @staticmethod
    def compute_td_setup(df: pd.DataFrame) -> list:
        """依據彭博 Bloomberg 標準計算德馬克 TD Setup (含 Qualifier 資格過濾)"""
        setup_type = ["🟢 待機中"] * len(df)
        if len(df) < 9:
            return setup_type

        buy_count = 0
        sell_count = 0
        for i in range(4, len(df)):
            curr_c = df['close'].iloc[i]
            ref_c = df['close'].iloc[i - 4]
            
            if curr_c < ref_c:
                buy_count += 1
                sell_count = 0
                if buy_count < 9:
                    setup_type[i] = f"🟢 買入 S{buy_count}"
                elif buy_count == 9:
                    low8, low9 = df['low'].iloc[i-1], df['low'].iloc[i]
                    low6, low7 = df['low'].iloc[i-3], df['low'].iloc[i-2]
                    if (low8 < min(low6, low7)) or (low9 < min(low6, low7)):
                        setup_type[i] = "🔥 買入 S9轉 (合格)"
                    else:
                        setup_type[i] = "⚪ 買入 S9轉 (未達標)"
                    buy_count = 0
            elif curr_c > ref_c:
                sell_count += 1
                buy_count = 0
                if sell_count < 9:
                    setup_type[i] = f"🔴 賣出 S{sell_count}"
                elif sell_count == 9:
                    high8, high9 = df['high'].iloc[i-1], df['high'].iloc[i]
                    high6, high7 = df['high'].iloc[i-3], df['high'].iloc[i-2]
                    if (high8 > max(high6, high7)) or (high9 > max(high6, high7)):
                        setup_type[i] = "⚡ 賣出 S9轉 (合格)"
                    else:
                        setup_type[i] = "⚪ 賣出 S9轉 (未達標)"
                    sell_count = 0
            else:
                buy_count = 0
                sell_count = 0
                setup_type[i] = "🟢 待機中"
                
        return setup_type

    @staticmethod
    def classify_candle_shape(open_p: float, high_p: float, low_p: float, close_p: float) -> str:
        """【精準 K 線解剖與顏色判定】"""
        total_range = high_p - low_p
        is_up = close_p >= open_p

        if total_range <= 0.0001:
            return "🟢 青陽漲" if is_up else "🔴 紅陰跌"

        body = abs(close_p - open_p)
        upper_wick = high_p - max(open_p, close_p)
        lower_wick = min(open_p, close_p) - low_p

        if body <= total_range * 0.15:
            return "🟢 十字漲 ⚖️" if is_up else "🔴 十字跌 ⚖️"

        if body >= 0.75 * total_range:
            return "🟢 大陽衝鋒 🚀" if is_up else "🔴 大陰破位 💥"

        if lower_wick >= 1.3 * upper_wick and lower_wick >= 0.30 * total_range:
            return "🟢 鐵錘漲 🔨" if is_up else "🔴 吊頸跌 🪓"

        if upper_wick >= 1.3 * lower_wick and upper_wick >= 0.30 * total_range:
            return "🟢 倒錘漲 🛸" if is_up else "🔴 射星跌 🌠"

        return "🟢 青陽漲" if is_up else "🔴 紅陰跌"

    @staticmethod
    def evaluate_trend_bias(df_1h: pd.DataFrame, curr_price: float, df_day: pd.DataFrame = None) -> tuple:
        """
        【模組：1H 日內級別方向門禁】
        由 1 小時圖 EMA20 決定日內主控權
        """
        trend_bias = 0
        trend_text = "⚪ 0 (中立震盪)"
        pdh_line = curr_price * 1.008
        pdl_line = curr_price * 0.992

        # 提取昨日極值（PDH/PDL 仍由日線或 1H 歷史提供）
        if df_day is not None and not df_day.empty and len(df_day) >= 2:
            prev_d = df_day.iloc[-2]
            pdh_line = float(prev_d.get('high', curr_price * 1.008))
            pdl_line = float(prev_d.get('low', curr_price * 0.992))

        # 1H EMA20 計算門禁
        if df_1h is not None and not df_1h.empty and len(df_1h) >= 20:
            df_1h_calc = df_1h.copy()
            df_1h_calc['ema20'] = df_1h_calc['close'].ewm(span=20, adjust=False).mean()
            last_h = df_1h_calc.iloc[-1]
            h_close = float(last_h['close'])
            h_ema20 = float(last_h['ema20'])

            if h_close >= h_ema20:
                trend_bias = 1
                trend_text = f"🟢 +1 (1H多頭控盤 [1H收>{h_ema20:.2f}])"
            else:
                trend_bias = -1
                trend_text = f"🔴 -1 (1H空頭壓制 [1H收<{h_ema20:.2f}])"

        return trend_bias, trend_text, pdh_line, pdl_line

    @staticmethod
    def evaluate_5m_signals(df_5m: pd.DataFrame, trend_bias: int, pdh_line: float, pdl_line: float) -> tuple:
        """【模組：5M 戰術信號與 2B 頂底真理診斷】"""
        df = df_5m.copy()
        df['vma20'] = df['volume'].rolling(20).mean().bfill()
        df['atr14'] = StrategyEngine.calculate_atr(df, 14)
        df['td_setup'] = StrategyEngine.compute_td_setup(df)

        llv5 = df['low'].rolling(5).min().shift(1).bfill()
        hhv5 = df['high'].rolling(5).max().shift(1).bfill()

        # 看跌 2B 假突破 (衝高遇阻回落 -> 買 PUT)
        bear_2b_raw = ((df['high'] > hhv5) | (df['high'] > pdh_line)) & (df['close'] < hhv5)
        
        # 看多 2B 假突破 (探底破底翻拉回 -> 買 CALL)
        bull_2b_raw = ((df['low'] < llv5) | (df['low'] < pdl_line)) & (df['close'] > llv5)

        c1, o1 = df['close'].shift(1), df['open'].shift(1)
        c2, o2 = df['close'].shift(2), df['open'].shift(2)
        h1, l1 = df['high'].shift(1), df['low'].shift(1)

        bull_star = (c2 < o2) & ((c1 - o1).abs() <= 0.35 * (h1 - l1)) & (df['close'] > df['open']) & (df['close'] >= (o2 + c2) / 2)
        bear_star = (c2 > o2) & ((c1 - o1).abs() <= 0.35 * (h1 - l1)) & (df['close'] < df['open']) & (df['close'] <= (o2 + c2) / 2)

        raw_bull_pattern = bull_2b_raw | bull_star
        raw_bear_pattern = bear_2b_raw | bear_star

        return df, raw_bull_pattern, raw_bear_pattern

    @staticmethod
    def calculate_option_plan(curr_price: float, trigger_type: str, budget_usd: float = 200.0) -> dict:
        """【模組：0DTE 期權智能換算】"""
        strike_atm = round(curr_price)
        est_option_price = 1.45
        total_cost = est_option_price * 100

        opt_dir_str = "🟢 CALL 多單" if trigger_type == "CALL" else ("🔴 PUT 空單" if trigger_type == "PUT" else "⚪ 待機觀望")
        opt_sym_str = f"QQQ {strike_atm} {'CALL' if trigger_type != 'PUT' else 'PUT'}"

        return {
            "strike_atm": strike_atm,
            "total_cost": total_cost,
            "opt_dir_str": opt_dir_str,
            "opt_sym_str": opt_sym_str
        }
