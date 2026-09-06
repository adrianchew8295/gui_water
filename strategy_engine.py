# 文件名: strategy_engine.py
# 核心職責: 【獨立策略大腦】VPA 多空對稱形態分類、Trend Bias 門禁、2B 假突破、TD 9 轉、0DTE 期權換算

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
        """依據彭博 Bloomberg 標準計算德馬克 TD Setup (1~9 轉)"""
        setup_type = ["🟢 待機中"] * len(df)
        if len(df) < 5:
            return setup_type

        buy_count = 0
        sell_count = 0
        for i in range(4, len(df)):
            curr_c = df['close'].iloc[i]
            ref_c = df['close'].iloc[i - 4]
            if curr_c < ref_c:
                buy_count += 1
                sell_count = 0
                setup_type[i] = f"🟢 買入 S{buy_count}" if buy_count < 9 else "🔥 買入 S9轉"
            elif curr_c > ref_c:
                sell_count += 1
                buy_count = 0
                setup_type[i] = f"🔴 賣出 S{sell_count}" if sell_count < 9 else "⚡ 賣出 S9轉"
            else:
                buy_count = 0
                sell_count = 0
                setup_type[i] = "🟢 待機中"
        return setup_type

    @staticmethod
    def classify_candle_shape(open_p: float, high_p: float, low_p: float, close_p: float) -> str:
        """
        【VPA 核心經典形態 · 多空對稱分類】
        🟢 青色 (收盤 >= 開盤 / 多頭偏向) | 🔴 紅色 (收盤 < 開盤 / 空頭偏向)
        """
        total_range = high_p - low_p
        is_up = close_p >= open_p

        # 1. 無振幅或極窄十字
        if total_range <= 0.0001:
            return "🟢 青陽漲" if is_up else "🔴 紅陰跌"

        body = abs(close_p - open_p)
        upper_wick = high_p - max(open_p, close_p)
        lower_wick = min(open_p, close_p) - low_p

        # 2. 實體極窄 (≤ 15% 振幅) -> 長腿十字星
        if body <= total_range * 0.15:
            return "🟢 十字漲 ⚖️" if is_up else "🔴 十字跌 ⚖️"

        # 3. 長上影線形態 (上影線 ≥ 2 倍實體)
        if upper_wick >= 2.0 * body and lower_wick <= 0.20 * total_range:
            return "🟢 倒錘漲 🛸" if is_up else "🔴 射星跌 🌠"

        # 4. 長下影線形態 (下影線 ≥ 2 倍實體)
        if lower_wick >= 2.0 * body and upper_wick <= 0.20 * total_range:
            return "🟢 鐵錘漲 🔨" if is_up else "🔴 吊頸跌 🪓"

        # 5. 實體大陽 / 大陰 (實體佔比 ≥ 75%)
        if body >= 0.75 * total_range:
            return "🟢 大陽衝鋒 🚀" if is_up else "🔴 大陰破位 💥"

        # 6. 常規 K 線
        return "🟢 青陽漲" if is_up else "🔴 紅陰跌"

    @staticmethod
    def evaluate_trend_bias(df_day: pd.DataFrame, curr_price: float) -> tuple:
        """【模組：宏觀方向門禁】"""
        trend_bias = 1
        trend_text = "🟢 +1 (多頭控盤 [日線>EMA20])"
        pdh_line = curr_price * 1.008
        pdl_line = curr_price * 0.992

        if not df_day.empty and len(df_day) >= 2:
            df_day['ema20'] = df_day['close'].ewm(span=20, adjust=False).mean()
            last_d = df_day.iloc[-1]
            prev_d = df_day.iloc[-2]
            pdh_line = float(prev_d.get('high', curr_price * 1.008))
            pdl_line = float(prev_d.get('low', curr_price * 0.992))
            if float(last_d['close']) >= float(last_d['ema20']):
                trend_bias = 1
                trend_text = "🟢 +1 (多頭控盤 [日線>EMA20])"
            else:
                trend_bias = -1
                trend_text = "🔴 -1 (空頭壓制 [日線<EMA20])"

        return trend_bias, trend_text, pdh_line, pdl_line

    @staticmethod
    def evaluate_5m_signals(df_5m: pd.DataFrame, trend_bias: int, pdh_line: float, pdl_line: float) -> tuple:
        """【模組：5M 戰術信號與 2B 形態診斷】"""
        df = df_5m.copy()
        df['vma20'] = df['volume'].rolling(20).mean().bfill()
        df['atr14'] = StrategyEngine.calculate_atr(df, 14)
        df['td_setup'] = StrategyEngine.compute_td_setup(df)

        llv5 = df['low'].rolling(5).min().shift(1).bfill()
        hhv5 = df['high'].rolling(5).max().shift(1).bfill()

        # 2B 假突破 (RAW 形態)
        bull_2b_raw = ((df['low'] < llv5) | (df['low'] < pdl_line)) & (df['close'] > llv5) & (df['close'] >= df['open'])
        bear_2b_raw = ((df['high'] > hhv5) | (df['high'] > pdh_line)) & (df['close'] < hhv5) & (df['close'] < df['open'])

        c1, o1 = df['close'].shift(1), df['open'].shift(1)
        c2, o2 = df['close'].shift(2), df['open'].shift(2)
        h1, l1 = df['high'].shift(1), df['low'].shift(1)

        bull_engulf = (df['close'] >= df['open']) & (c1 < o1) & (df['close'] >= o1) & (df['open'] <= c1)
        bear_engulf = (df['close'] < df['open']) & (c1 > o1) & (df['close'] <= o1) & (df['open'] >= c1)

        bull_star = (c2 < o2) & ((c1 - o1).abs() <= 0.35 * (h1 - l1)) & (df['close'] >= df['open']) & (df['close'] >= (o2 + c2) / 2)
        bear_star = (c2 > o2) & ((c1 - o1).abs() <= 0.35 * (h1 - l1)) & (df['close'] < df['open']) & (df['close'] <= (o2 + c2) / 2)

        raw_bull_pattern = bull_2b_raw | bull_engulf | bull_star
        raw_bear_pattern = bear_2b_raw | bear_engulf | bear_star

        return df, raw_bull_pattern, raw_bear_pattern

    @staticmethod
    def calculate_option_plan(curr_price: float, trigger_type: str, budget_usd: float = 200.0) -> dict:
        """【模組：0DTE 期權智能換算】"""
        strike_atm = round(curr_price)
        est_option_price = 1.45
        total_cost = est_option_price * 100

        opt_dir_str = "🟢 CALL 多單" if trigger_type != "PUT" else "🔴 PUT 空單"
        opt_sym_str = f"QQQ {strike_atm} {'CALL' if trigger_type != 'PUT' else 'PUT'}"

        return {
            "strike_atm": strike_atm,
            "total_cost": total_cost,
            "opt_dir_str": opt_dir_str,
            "opt_sym_str": opt_sym_str
        }
