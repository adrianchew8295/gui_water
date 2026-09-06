# 文件名: strategy_engine.py
# 核心職責: 【散戶實戰大腦】1H EMA20日內門禁 + 5M邊界2B當根定罪 + TD 9轉資格認證 + 0DTE極簡風控

import numpy as np
import pandas as pd

class StrategyEngine:
    """量化策略計算中樞"""

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """計算 ATR14 波動率"""
        if len(df) < 2:
            return pd.Series([1.0] * len(df))
        high = df['high'] if 'high' in df.columns else df['High']
        low = df['low'] if 'low' in df.columns else df['Low']
        close = df['close'] if 'close' in df.columns else df['Close']
        close_prev = close.shift(1).bfill()
        tr = np.maximum(high - low, np.maximum((high - close_prev).abs(), (low - close_prev).abs()))
        return tr.rolling(window=period).mean().bfill()

    @staticmethod
    def compute_td_setup(df: pd.DataFrame) -> list:
        """依據彭博 Bloomberg 標準計算德馬克 TD Setup (含 Qualifier 資格過濾)"""
        setup_type = ["🟢 待機中"] * len(df)
        if len(df) < 9:
            return setup_type

        close = df['close'] if 'close' in df.columns else df['Close']
        low = df['low'] if 'low' in df.columns else df['Low']
        high = df['high'] if 'high' in df.columns else df['High']

        buy_count = 0
        sell_count = 0
        for i in range(4, len(df)):
            curr_c = close.iloc[i]
            ref_c = close.iloc[i - 4]
            
            # --- TD Buy Setup 計數 (買入衰竭) ---
            if curr_c < ref_c:
                buy_count += 1
                sell_count = 0
                if buy_count < 9:
                    setup_type[i] = f"🟢 買入 S{buy_count}"
                elif buy_count == 9:
                    # Qualifier: 第8根或第9根的 Low 必須跌破第6根和第7根的 Low
                    low8 = low.iloc[i - 1]
                    low9 = low.iloc[i]
                    low6 = low.iloc[i - 3]
                    low7 = low.iloc[i - 2]
                    
                    if (low8 < min(low6, low7)) or (low9 < min(low6, low7)):
                        setup_type[i] = "🔥 買入 S9轉 (合格)"
                    else:
                        setup_type[i] = "⚪ 買入 S9轉 (未達標)"
                    buy_count = 0
            # --- TD Sell Setup 計數 (賣出衰竭) ---
            elif curr_c > ref_c:
                sell_count += 1
                buy_count = 0
                if sell_count < 9:
                    setup_type[i] = f"🔴 賣出 S{sell_count}"
                elif sell_count == 9:
                    # Qualifier: 第8根或第9根的 High 必須升破第6根和第7根的 High
                    high8 = high.iloc[i - 1]
                    high9 = high.iloc[i]
                    high6 = high.iloc[i - 3]
                    high7 = high.iloc[i - 2]
                    
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
        由 1 小時圖 EMA20 決定日內多空主控權
        """
        trend_bias = 0
        trend_text = "⚪ 0 (1H 中立震盪)"
        pdh_line = curr_price * 1.008
        pdl_line = curr_price * 0.992

        # 提取昨日極值 (PDH / PDL)
        if df_day is not None and not df_day.empty and len(df_day) >= 2:
            prev_d = df_day.iloc[-2]
            high_col = 'high' if 'high' in prev_d else 'High'
            low_col = 'low' if 'low' in prev_d else 'Low'
            pdh_line = float(prev_d.get(high_col, curr_price * 1.008))
            pdl_line = float(prev_d.get(low_col, curr_price * 0.992))

        # 1H EMA20 計算
        if df_1h is not None and not df_1h.empty and len(df_1h) >= 20:
            df_1h_calc = df_1h.copy()
            close_col = 'close' if 'close' in df_1h_calc.columns else 'Close'
            df_1h_calc['ema20'] = df_1h_calc[close_col].ewm(span=20, adjust=False).mean()
            last_h = df_1h_calc.iloc[-1]
            h_close = float(last_h[close_col])
            h_ema20 = float(last_h['ema20'])

            if h_close >= h_ema20:
                trend_bias = 1
                trend_text = f"🟢 +1 (1H 多頭控盤 [1H收>{h_ema20:.2f}])"
            else:
                trend_bias = -1
                trend_text = f"🔴 -1 (1H 空頭壓制 [1H收<{h_ema20:.2f}])"

        return trend_bias, trend_text, pdh_line, pdl_line

    @staticmethod
    def evaluate_5m_signals(df_5m: pd.DataFrame, trend_bias: int, pdh_line: float, pdl_line: float, 
                            rbs_top: float = 0.0, sbr_bot: float = 0.0) -> tuple:
        """
        【模組：5M 戰術信號與 2B 邊界當根定罪】
        """
        df = df_5m.copy()
        vol_col = 'volume' if 'volume' in df.columns else 'Volume'
        close_col = 'close' if 'close' in df.columns else 'Close'
        open_col = 'open' if 'open' in df.columns else 'Open'
        high_col = 'high' if 'high' in df.columns else 'High'
        low_col = 'low' if 'low' in df.columns else 'Low'

        df['vma20'] = df[vol_col].rolling(20).mean().bfill()
        df['atr14'] = StrategyEngine.calculate_atr(df, 14)
        df['td_setup'] = StrategyEngine.compute_td_setup(df)

        # 動態支撐與阻力錨點（1H 戰區 或 昨日極值）
        sup_anchor = rbs_top if rbs_top > 0 else pdl_line
        res_anchor = sbr_bot if sbr_bot > 0 else pdh_line

        # 5M 做多 2B (破底翻)：盤中跌破邊界，收盤拉回邊界線上，且收盤 >= 開盤
        bull_2b_raw = (df[low_col] < sup_anchor) & (df[close_col] > sup_anchor) & (df[close_col] >= df[open_col])

        # 5M 做空 2B (假突破衝頂)：盤中衝破邊界，收盤跌回邊界線下，且收盤 < 開盤
        bear_2b_raw = (df[high_col] > res_anchor) & (df[close_col] < res_anchor) & (df[close_col] < df[open_col])

        # 晨星 / 暮星形態輔助
        c1, o1 = df[close_col].shift(1), df[open_col].shift(1)
        c2, o2 = df[close_col].shift(2), df[open_col].shift(2)
        h1, l1 = df[high_col].shift(1), df[low_col].shift(1)

        bull_star = (c2 < o2) & ((c1 - o1).abs() <= 0.35 * (h1 - l1)) & (df[close_col] >= df[open_col]) & (df[close_col] >= (o2 + c2) / 2)
        bear_star = (c2 > o2) & ((c1 - o1).abs() <= 0.35 * (h1 - l1)) & (df[close_col] < df[open_col]) & (df[close_col] <= (o2 + c2) / 2)

        raw_bull_pattern = bull_2b_raw | bull_star
        raw_bear_pattern = bear_2b_raw | bear_star

        return df, raw_bull_pattern, raw_bear_pattern

    @staticmethod
    def calculate_option_plan(curr_price: float, trigger_type: str, budget_usd: float = 200.0) -> dict:
        """【模組：0DTE 期權極簡風控換算】"""
        strike_atm = round(curr_price)
        est_option_price = 1.45  # 基準平值估價
        total_cost = est_option_price * 100

        opt_dir_str = "🟢 CALL 多單" if trigger_type == "CALL" else ("🔴 PUT 空單" if trigger_type == "PUT" else "⚪ 待機觀望")
        opt_sym_str = f"QQQ {strike_atm} {'CALL' if trigger_type != 'PUT' else 'PUT'}"

        return {
            "strike_atm": strike_atm,
            "total_cost": total_cost,
            "opt_dir_str": opt_dir_str,
            "opt_sym_str": opt_sym_str
        }
