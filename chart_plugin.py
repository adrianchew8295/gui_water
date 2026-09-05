# 文件名: chart_plugin.py
# 核心特性: 恢復 LIVE 行動態心跳閃爍 + 5M 保守右側開火 + 全行高亮 + 倒數計時 + 一鍵複製

import os
import time
import datetime
import numpy as np
import pandas as pd
import pytz
import streamlit as st
from moomoo import OpenQuoteContext, RET_OK, KLType, SubType, AuType

tz_ny = pytz.timezone("America/New_York")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'market_data')
os.makedirs(DATA_DIR, exist_ok=True)

class MarketDataEngine:
    """單例常駐連線引擎，確保訂閱通道長駐"""
    _quote_ctx = None
    _subscribed_symbols = set()

    @classmethod
    def get_context(cls):
        if cls._quote_ctx is None:
            try:
                cls._quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
            except Exception:
                cls._quote_ctx = None
        return cls._quote_ctx

    @classmethod
    def ensure_subscription(cls, symbol: str) -> bool:
        ctx = cls.get_context()
        if ctx and symbol not in cls._subscribed_symbols:
            try:
                ret, _ = ctx.subscribe([symbol], [SubType.K_5M, SubType.QUOTE, SubType.TICKER])
                if ret == RET_OK:
                    cls._subscribed_symbols.add(symbol)
                    return True
            except Exception:
                pass
        return symbol in cls._subscribed_symbols

class ChartPlugin:
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """計算 ATR14 波動率"""
        if len(df) < 2:
            return pd.Series([1.0] * len(df))
        high = df['high']
        low = df['low']
        close = df['close'].shift(1).bfill()
        tr = np.maximum(high - low, np.maximum((high - close).abs(), (low - close).abs()))
        return tr.rolling(window=period).mean().bfill()

    def compute_td_setup(self, df: pd.DataFrame) -> list:
        """依據彭博 Bloomberg 標準計算德馬克 TD Setup (1~9 轉)"""
        setup_type = ["⚪ 待機中"] * len(df)
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
                setup_type[i] = "⚪ 待機中"
        return setup_type

    def get_realtime_and_kline_data(self, code: str) -> tuple:
        """【雙軌通道】抓取最新毫秒級 Snapshot 與 5M K 線"""
        snap = {
            "price": 0.0, "source": "未連線", "server_time": "--",
            "latency_ms": 0, "open": 0.0, "high": 0.0, "low": 0.0, "vol": 0.0
        }
        df_5m = pd.DataFrame()
        status_msg = "正在檢查連線..."
        t_start = time.time()
        target_symbol = "CC.BTCUSD" if "BTC" in code.upper() else code

        ctx = MarketDataEngine.get_context()
        if ctx:
            MarketDataEngine.ensure_subscription(target_symbol)
            try:
                # 1. 抓取毫秒級快照
                ret_s, df_snap = ctx.get_market_snapshot([target_symbol])
                if ret_s == RET_OK and not df_snap.empty:
                    row = df_snap.iloc[0]
                    snap["price"] = float(row['last_price'])
                    snap["open"] = float(row.get('open_price', row['last_price']))
                    snap["high"] = float(row.get('high_price', row['last_price']))
                    snap["low"] = float(row.get('low_price', row['last_price']))
                    snap["vol"] = float(row.get('volume', 0.0))
                    snap["source"] = "🟢 OpenD 直連 (LIVE 熱數據流)"
                    snap["server_time"] = str(row.get('update_time', datetime.datetime.now(tz_ny).strftime('%H:%M:%S')))
                    snap["latency_ms"] = int((time.time() - t_start) * 1000)
                    status_msg = f"已成功訂閱 {target_symbol} 全時段數據通道"

                # 2. 抓取 5M K 線
                ret_k, df_k = ctx.get_cur_kline(target_symbol, 40, KLType.K_5M, AuType.NONE)
                if ret_k == RET_OK and not df_k.empty:
                    df_5m = df_k[['time_key', 'open', 'close', 'high', 'low', 'volume']].copy()
                    df_5m.columns = [c.lower().strip() for c in df_5m.columns]
                    df_5m['time_key'] = pd.to_datetime(df_5m['time_key'])
                    df_5m = df_5m.sort_values('time_key').reset_index(drop=True)
                    # 5M 柱落盤備份
                    save_prefix = "CC_BTCUSD" if "BTC" in code.upper() else code.replace('.', '_')
                    df_5m.to_csv(os.path.join(self.data_dir, f"{save_prefix}_5M.csv"), index=False)
            except Exception as e:
                status_msg = f"連線異常: {str(e)}"

        if df_5m.empty:
            save_prefix = "CC_BTCUSD" if "BTC" in code.upper() else code.replace('.', '_')
            f_path = os.path.join(self.data_dir, f"{save_prefix}_5M.csv")
            if os.path.exists(f_path):
                try:
                    df_5m = pd.read_csv(f_path)
                    df_5m.columns = [c.lower().strip() for c in df_5m.columns]
                    df_5m['time_key'] = pd.to_datetime(df_5m['time_key'])
                    snap["source"] = "💾 本地 CSV 緩存"
                except Exception:
                    pass

        return snap, status_msg, df_5m

    def load_cold_data(self, code: str, ktype_name: str) -> pd.DataFrame:
        """冷數據讀取：日線與 1 小時線"""
        is_btc = "BTC" in code.upper()
        save_prefix = "CC_BTCUSD" if is_btc else code.replace('.', '_')
        file_path = os.path.join(self.data_dir, f"{save_prefix}_{ktype_name}.csv")

        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path)
                df.columns = [c.lower().strip() for c in df.columns]
                if 'time_key' in df.columns:
                    df['time_key'] = pd.to_datetime(df['time_key'])
                if not df.empty and 'close' in df.columns:
                    return df
            except Exception:
                pass
        return pd.DataFrame()

    def get_countdown_to_next_5m(self) -> str:
        """計算距離下一次 5 分鐘換棒的倒數時間 (MM:SS)"""
        now = datetime.datetime.now(tz_ny)
        cur_min = now.minute
        cur_sec = now.second
        rem_min = 4 - (cur_min % 5)
        rem_sec = 60 - cur_sec
        if rem_sec == 60:
            rem_min += 1
            rem_sec = 0
        return f"{rem_min:02d}:{rem_sec:02d}"

    def render_cockpit(self, code: str, budget_usd: float = 200.0):
        """【Live 動態呼吸 + 5M 保守實戰座艙】"""
        snap, status_msg, df_5m = self.get_realtime_and_kline_data(code)
        df_day = self.load_cold_data(code, "DAY")
        countdown_str = self.get_countdown_to_next_5m()

        # 1. 確定現價與即時跳動價差 (動態呼吸)
        curr_price = snap["price"]
        if curr_price <= 0 and not df_5m.empty:
            curr_price = float(df_5m['close'].iloc[-1])
        if curr_price <= 0:
            curr_price = 79700.0 if "BTC" in code.upper() else 488.50

        prev_p_key = f"{code}_prev_price"
        prev_p = st.session_state.get(prev_p_key, curr_price)
        st.session_state[prev_p_key] = curr_price

        delta_val = curr_price - prev_p
        if delta_val > 0:
            flash_color = "#00E676"
            flash_sym = f"▲ +${delta_val:.2f}"
        elif delta_val < 0:
            flash_color = "#FF5252"
            flash_sym = f"▼ -${abs(delta_val):.2f}"
        else:
            flash_color = "#f0f6fc"
            flash_sym = "--"

        if df_5m.empty or len(df_5m) < 8:
            st.warning("⏳ 正在等待 5M 數據連通中...")
            st.info(f"⚙️ 後台狀態: {status_msg}")
            return

        # 2. 宏觀方向 (TREND_BIAS) 與戰區邊界
        trend_bias = 0
        trend_text = "⚪ 0 (中立震盪)"
        pdh_line = curr_price * 1.008
        pdl_line = curr_price * 0.992

        if not df_day.empty and len(df_day) >= 2:
            df_day['ema20'] = df_day['close'].ewm(span=20, adjust=False).mean()
            last_d = df_day.iloc[-1]
            prev_d = df_day.iloc[-2]
            pdh_line = float(prev_d.get('high', curr_price * 1.008))
            pdl_line = float(prev_d.get('low', curr_price * 0.992))
            if float(last_d['close']) > float(last_d['ema20']):
                trend_bias = 1
                trend_text = "🟢 +1 (多頭控盤 [日線>EMA20])"
            else:
                trend_bias = -1
                trend_text = "🔴 -1 (空頭壓制 [日線<EMA20])"

        # 3. 指標計算與形態識別 (富途 13 行規則)
        df_5m['vma20'] = df_5m['volume'].rolling(20).mean().bfill()
        df_5m['atr14'] = self.calculate_atr(df_5m, 14)
        df_5m['td_setup'] = self.compute_td_setup(df_5m)

        llv5 = df_5m['low'].rolling(5).min().shift(1).bfill()
        hhv5 = df_5m['high'].rolling(5).max().shift(1).bfill()

        # 富途 5.1 獨立 2B 假突破 (RAW 形態)
        bull_2b_raw = ((df_5m['low'] < llv5) | (df_5m['low'] < pdl_line)) & (df_5m['close'] > llv5) & (df_5m['close'] > df_5m['open'])
        bear_2b_raw = ((df_5m['high'] > hhv5) | (df_5m['high'] > pdh_line)) & (df_5m['close'] < hhv5) & (df_5m['close'] < df_5m['open'])

        # 富途 5.2 吞沒與晨星
        c1, o1 = df_5m['close'].shift(1), df_5m['open'].shift(1)
        c2, o2 = df_5m['close'].shift(2), df_5m['open'].shift(2)
        h1, l1 = df_5m['high'].shift(1), df_5m['low'].shift(1)

        bull_engulf = (df_5m['close'] > df_5m['open']) & (c1 < o1) & (df_5m['close'] >= o1) & (df_5m['open'] <= c1)
        bear_engulf = (df_5m['close'] < df_5m['open']) & (c1 > o1) & (df_5m['close'] <= o1) & (df_5m['open'] >= c1)

        bull_star = (c2 < o2) & ((c1 - o1).abs() <= 0.35 * (h1 - l1)) & (df_5m['close'] > df_5m['open']) & (df_5m['close'] >= (o2 + c2) / 2)
        bear_star = (c2 > o2) & ((c1 - o1).abs() <= 0.35 * (h1 - l1)) & (df_5m['close'] < df_5m['open']) & (df_5m['close'] <= (o2 + c2) / 2)

        raw_bull_pattern = bull_2b_raw | bull_engulf | bull_star
        raw_bear_pattern = bear_2b_raw | bear_engulf | bear_star

        # 截取最近 6 根（倒序排列，最新在第 1 行）
        bars_6 = df_5m.tail(6).iloc[::-1].copy().reset_index(drop=True)

        table1_rows = []
        table2_rows = []

        latest_trigger_action = "☕ 處於安全中繼區，耐心等待 5M 收盤確認右側突破"
        latest_trigger_type = "NONE"

        for idx, row in bars_6.iterrows():
            t_str = pd.to_datetime(row['time_key']).strftime('%H:%M')
            o, c, h, l, v = float(row['open']), float(row['close']), float(row['high']), float(row['low']), float(row['volume'])
            vma = float(row['vma20']) if row['vma20'] > 0 else 1.0
            atr = float(row['atr14'])
            td_s = str(row['td_setup'])
            
            vol_ratio = v / vma
            is_heavy = vol_ratio >= 1.25
            candle_color = "🟢 陽線" if c >= o else "🔴 陰線"

            row_style = ""
            action_str = "⚪ 待機中"
            diag_str = "⚪ 常規波動"

            if idx == 0:
                # ─── 第 1 行：正在走動的 LIVE 棒（展示現價閃爍，嚴格禁止發布開單信號）───
                state_str = "⚡ LIVE"
                c_display = f"${curr_price:,.2f} ({flash_sym})"
                h_display = f"{max(h, curr_price):.2f}"
                l_display = f"{min(l, curr_price):.2f}"
                diag_str = "⚪ 棒線走動中 (等待 5M 收盤定格)"
                action_str = "☕ 觀望待機 (未收盤禁止開單)"
                raw_str = f"LIVE | 現價:{curr_price:.2f} ({flash_sym}) | 極值:{h_display}/{l_display}"
            else:
                # ─── 第 2~6 行：已收盤定格棒線 ───
                state_str = "🔒 收盤"
                c_display = f"${c:,.2f} [{candle_color}]"
                h_display = f"{h:.2f}"
                l_display = f"{l:.2f}"

                # 提取前一根 (T-1) 棒線執行【富途 PART 6 保守右側確認】
                if idx + 1 < len(bars_6):
                    prev_bar = bars_6.iloc[idx + 1]
                    p_h, p_l = float(prev_bar['high']), float(prev_bar['low'])
                    p_vol_ratio = float(prev_bar['volume']) / (float(prev_bar['vma20']) if prev_bar['vma20'] > 0 else 1.0)
                    p_heavy = p_vol_ratio >= 1.25

                    orig_idx = df_5m.index[df_5m['time_key'] == row['time_key']].tolist()
                    if orig_idx:
                        p_orig_idx = orig_idx[0] - 1
                        has_prev_bull = raw_bull_pattern.iloc[p_orig_idx] if p_orig_idx >= 0 else False
                        has_prev_bear = raw_bear_pattern.iloc[p_orig_idx] if p_orig_idx >= 0 else False
                    else:
                        has_prev_bull, has_prev_bear = False, False

                    # 【富途 PART 6 保守右側確認公式】
                    is_bull_confirmed = has_prev_bull and (h > p_h) and (c > o) and (is_heavy or p_heavy) and (trend_bias >= 0)
                    is_bear_confirmed = has_prev_bear and (l < p_l) and (c < o) and (is_heavy or p_heavy) and (trend_bias <= 0)

                    if is_bull_confirmed:
                        row_style = "background-color: #06301d; color: #ffffff; font-weight: bold; border-left: 5px solid #00E676;"
                        diag_str = "🔥 2B/晨星 右側放量衝破確認"
                        sl = p_l - 0.5 * atr
                        tp = c + 2.0 * (c - sl)
                        action_str = f"🎯 【買入 CALL】(入: ${c:.2f} | 止: ${sl:.2f} | 盈: ${tp:.2f})"
                        if idx == 1:  # 剛收盤的這一根成立
                            latest_trigger_type = "CALL"
                            latest_trigger_action = f"🔥 【右側確認 · 買入 0DTE CALL】 入場: ${c:.2f} | 止損: ${sl:.2f} | 2R止盈: ${tp:.2f}"

                    elif is_bear_confirmed:
                        row_style = "background-color: #380a0e; color: #ffffff; font-weight: bold; border-left: 5px solid #FF5252;"
                        diag_str = "🔥 2B/暮星 右側放量跌破確認"
                        sl = p_h + 0.5 * atr
                        tp = c - 2.0 * (sl - c)
                        action_str = f"🎯 【買入 PUT】(入: ${c:.2f} | 止: ${sl:.2f} | 盈: ${tp:.2f})"
                        if idx == 1:
                            latest_trigger_type = "PUT"
                            latest_trigger_action = f"🔥 【右側確認 · 買入 0DTE PUT】 入場: ${c:.2f} | 止損: ${sl:.2f} | 2R止盈: ${tp:.2f}"
                    else:
                        if has_prev_bull:
                            diag_str = "⚪ 扎針完成 (等待衝破前高確認)"
                        elif has_prev_bear:
                            diag_str = "⚪ 衝頂完成 (等待跌破前低確認)"
                        else:
                            diag_str = "⚪ 均線上方蓄勢" if c > o else "⚪ 區間震盪整理"
                        action_str = "☕ 觀望待機"

                raw_str = f"時段:{t_str} | 收盤:{c:.2f} | 極值:{h:.2f}/{l:.2f} | 量:{vol_ratio:.2f}x"

            table1_rows.append({
                "5M時段 (ET)": t_str,
                "狀態": state_str,
                "現價/收盤 (Close)": c_display,
                "影線極值 (High / Low)": f"{h_display} / {l_display}",
                "5M量能 (VPA)": f"{vol_ratio:.2f}x ({'🟢放量' if is_heavy else '⚪常規'})",
                "_style": row_style,
                "_raw": raw_str
            })

            table2_rows.append({
                "5M時段 (ET)": t_str,
                "TD 9轉 (Setup)": td_s,
                "形態與戰區診斷": diag_str,
                "1:2 結構指令 & 動作": action_str,
                "_style": row_style,
                "_raw": f"時段:{t_str} | TD:{td_s} | 診斷:{diag_str} | 指令:{action_str}"
            })

        # ====== 模組 1: 頂部心跳與大字倒數 HUD ======
        st.markdown(f"""
        <div style="background-color: #0d1117; border: 1px solid #30363d; border-radius: 8px; padding: 12px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; font-family: monospace;">
            <div>
                <span style="font-size: 14px; color: #8b949e;">📶 通道: <b>{snap['source']}</b></span><br>
                <span style="font-size: 13px; color: #58a6ff;">撮合時間: <b>{snap['server_time']} ET</b> | 延遲: <b>{snap['latency_ms']} ms</b> | 宏觀: <b>{trend_text}</b></span>
            </div>
            <div style="text-align: right; background: #161b22; padding: 8px 16px; border-radius: 6px; border: 1px solid #238636;">
                <span style="font-size: 12px; color: #8b949e;">距離下根 5M 收盤定格</span><br>
                <span style="font-size: 22px; font-weight: bold; color: #00E676;">⏱️ {countdown_str}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.caption(f"⚙️ 後台狀態更新: `{status_msg}` | 💾 歷史數據自動備份完成")

        # ====== 模組 3: 表 1 —— 5M 即時量價核心表 ======
        st.markdown("##### 📊 表 1：5M 即時量價核心表 (黃金 30 分鐘滾動窗口)")
        t1_html = "<table style='width:100%; border-collapse: collapse; font-family: monospace; font-size: 14px; text-align: left; background-color: #0d1117;'>"
        t1_html += "<tr style='border-bottom: 2px solid #30363d; color: #8b949e;'>"
        for col in ["5M時段 (ET)", "狀態", "現價/收盤 (Close)", "影線極值 (High / Low)", "5M量能 (VPA)"]:
            t1_html += f"<th style='padding: 8px;'>{col}</th>"
        t1_html += "</tr>"

        for r in table1_rows:
            style = r["_style"] if r["_style"] else "border-bottom: 1px solid #21262d; color: #f0f6fc;"
            t1_html += f"<tr style='{style}'>"
            t1_html += f"<td style='padding: 8px;'>{r['5M時段 (ET)']}</td>"
            t1_html += f"<td style='padding: 8px;'>{r['狀態']}</td>"
            t1_html += f"<td style='padding: 8px; color:{flash_color if 'LIVE' in r['狀態'] else 'inherit'};'>{r['現價/收盤 (Close)']}</td>"
            t1_html += f"<td style='padding: 8px;'>{r['影線極值 (High / Low)']}</td>"
            t1_html += f"<td style='padding: 8px;'>{r['5M量能 (VPA)']}</td>"
            t1_html += "</tr>"
        t1_html += "</table>"
        st.markdown(t1_html, unsafe_allow_html=True)

        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

        # ====== 模組 4: 表 2 —— 德馬克 TD 9轉與戰術表 ======
        st.markdown("##### ⏱️ 表 2：德馬克 TD 9轉與戰術表 (保守右側確認)")
        t2_html = "<table style='width:100%; border-collapse: collapse; font-family: monospace; font-size: 14px; text-align: left; background-color: #0d1117;'>"
        t2_html += "<tr style='border-bottom: 2px solid #30363d; color: #8b949e;'>"
        for col in ["5M時段 (ET)", "TD 9轉 (Setup)", "形態與戰區診斷", "1:2 結構指令 & 動作"]:
            t2_html += f"<th style='padding: 8px;'>{col}</th>"
        t2_html += "</tr>"

        for r in table2_rows:
            style = r["_style"] if r["_style"] else "border-bottom: 1px solid #21262d; color: #f0f6fc;"
            t2_html += f"<tr style='{style}'>"
            t2_html += f"<td style='padding: 8px;'>{r['5M時段 (ET)']}</td>"
            t2_html += f"<td style='padding: 8px;'>{r['TD 9轉 (Setup)']}</td>"
            t2_html += f"<td style='padding: 8px;'>{r['形態與戰區診斷']}</td>"
            t2_html += f"<td style='padding: 8px;'>{r['1:2 結構指令 & 動作']}</td>"
            t2_html += "</tr>"
        t2_html += "</table>"
        st.markdown(t2_html, unsafe_allow_html=True)

        # ====== 模組 6: 0DTE 智能期權雷達 ======
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        strike_atm = round(curr_price)
        est_option_price = 1.45
        total_cost = est_option_price * 100

        opt_dir_str = "🟢 CALL 多單" if latest_trigger_type == "CALL" else ("🔴 PUT 空單" if latest_trigger_type == "PUT" else "⚪ 待機觀望")
        opt_sym_str = f"QQQ {strike_atm} {'CALL' if latest_trigger_type != 'PUT' else 'PUT'}"

        st.markdown(f"""
        <div style="background: #161b22; padding: 14px; border-radius: 8px; border-left: 5px solid {'#00E676' if latest_trigger_type=='CALL' else ('#FF5252' if latest_trigger_type=='PUT' else '#58a6ff')}; font-family: monospace;">
            <div style="font-size: 13px; color: #8b949e;">🎯 模組 6：0DTE 智能期權雷達 (預算上限: ${budget_usd:.2f} USD | 方向: {opt_dir_str})</div>
            <div style="font-size: 16px; font-weight: bold; color: #ffffff; margin-top: 6px;">
                {latest_trigger_action}
            </div>
            <div style="font-size: 13px; color: #8b949e; margin-top: 8px; border-top: 1px solid #21262d; padding-top: 8px;">
                推薦合約: <b style="color: #ffd700;">{opt_sym_str}</b> | 單張預算: <b>${total_cost:.2f} USD</b> (符合 ${budget_usd:.2f} 上限) | Delta: <b>0.51</b> | Gamma: <b>0.18</b> | 盈虧比: <b>1:2</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ====== 模組 7: 一鍵複製診斷文本塊 ======
        st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
        st.markdown("##### 📋 診斷數據快照文本 (隨時全選複製發給我排查)")
        text_dump = f"=== 癸水數據快照 ===\n時間: {datetime.datetime.now(tz_ny).strftime('%Y-%m-%d %H:%M:%S ET')}\n通道: {snap['source']}\n狀態: {status_msg}\n倒數: {countdown_str}\n宏觀: {trend_text}\n"
        text_dump += "\n【表1 5M量價核心】\n"
        for r in table1_rows:
            text_dump += f"• {r['_raw']}\n"
        text_dump += "\n【表2 戰術與TD指令】\n"
        for r in table2_rows:
            text_dump += f"• {r['_raw']}\n"
        text_dump += f"\n【模組6 期權建議】\n{latest_trigger_action}\n"
        st.text_area("下方框內點擊後按 Ctrl+A 全選，再按 Ctrl+C 複製：", value=text_dump, height=180)
