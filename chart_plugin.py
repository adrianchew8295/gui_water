# 文件名: chart_plugin.py
# 核心特性: 單螢幕極致視野 + 免滾動緊湊單表 + 決策卡置頂 + 1H EMA20 & 2B 當根定罪

import os
import sys
import time
import datetime
import numpy as np
import pandas as pd
import pytz
import streamlit as st
from moomoo import OpenQuoteContext, RET_OK, KLType, SubType, AuType
from streamlit_extras.stylable_container import stylable_container

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from strategy_engine import StrategyEngine

tz_ny = pytz.timezone("America/New_York")
tz_my = pytz.timezone("Asia/Kuala_Lumpur")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'market_data')
os.makedirs(DATA_DIR, exist_ok=True)

class MarketDataEngine:
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
        return StrategyEngine.calculate_atr(df, period)

    def get_realtime_and_kline_data(self, code: str) -> tuple:
        snap = {"price": 0.0, "source": "未連線", "server_time": "--", "latency_ms": 0}
        df_5m = pd.DataFrame()
        status_msg = "正在檢查連線..."
        t_start = time.time()
        target_symbol = "CC.BTCUSD" if "BTC" in code.upper() else code

        ctx = MarketDataEngine.get_context()
        if ctx:
            MarketDataEngine.ensure_subscription(target_symbol)
            try:
                ret_s, df_snap = ctx.get_market_snapshot([target_symbol])
                if ret_s == RET_OK and not df_snap.empty:
                    row = df_snap.iloc[0]
                    snap["price"] = float(row['last_price'])
                    snap["source"] = "🟢 OpenD 直連"
                    snap["server_time"] = str(row.get('update_time', datetime.datetime.now(tz_ny).strftime('%H:%M:%S')))
                    snap["latency_ms"] = int((time.time() - t_start) * 1000)
                    status_msg = f"已訂閱 {target_symbol}"

                ret_k, df_k = ctx.get_cur_kline(target_symbol, 30, KLType.K_5M, AuType.NONE)
                if ret_k == RET_OK and not df_k.empty:
                    df_5m = df_k[['time_key', 'open', 'close', 'high', 'low', 'volume']].copy()
                    df_5m.columns = [c.lower().strip() for c in df_5m.columns]
                    df_5m['time_key'] = pd.to_datetime(df_5m['time_key'])
                    df_5m = df_5m.sort_values('time_key').reset_index(drop=True)
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
                    snap["source"] = "💾 本地緩存"
                except Exception:
                    pass

        return snap, status_msg, df_5m

    def load_cold_data(self, code: str, ktype_name: str) -> pd.DataFrame:
        is_btc = "BTC" in code.upper()
        save_prefix = "CC_BTCUSD" if is_btc else code.replace('.', '_')
        file_path = os.path.join(self.data_dir, f"{save_prefix}_{ktype_name}.csv")
        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path)
                df.columns = [c.lower().strip() for c in df.columns]
                if 'time_key' in df.columns:
                    df['time_key'] = pd.to_datetime(df['time_key'])
                return df
            except Exception:
                pass
        return pd.DataFrame()

    def get_countdown_to_next_5m(self) -> str:
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
        # 注入極致緊湊 CSS，消除空白邊距與滾動條
        st.markdown(
            """
            <style>
                .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; padding-left: 1rem !important; padding-right: 1rem !important; }
                h1, h2, h3, h4, h5 { margin-top: 0px !important; margin-bottom: 4px !important; }
                [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
                [data-testid="stMetricLabel"] { font-size: 0.75rem !important; }
            </style>
            """,
            unsafe_allow_html=True
        )

        snap, status_msg, df_5m = self.get_realtime_and_kline_data(code)
        df_1h = self.load_cold_data(code, "1Hr")
        df_day = self.load_cold_data(code, "DAY")
        countdown_str = self.get_countdown_to_next_5m()

        curr_price = snap["price"]
        if curr_price <= 0 and not df_5m.empty:
            curr_price = float(df_5m['close'].iloc[-1])
        if curr_price <= 0:
            curr_price = 79950.0

        prev_p_key = f"{code}_prev_price"
        prev_p = st.session_state.get(prev_p_key, curr_price)
        st.session_state[prev_p_key] = curr_price

        delta_val = curr_price - prev_p
        flash_color = "#00E676" if delta_val > 0 else ("#FF5252" if delta_val < 0 else "#f0f6fc")
        flash_sym = f"▲ +${delta_val:.2f}" if delta_val > 0 else (f"▼ -${abs(delta_val):.2f}" if delta_val < 0 else "--")

        if df_5m.empty or len(df_5m) < 6:
            st.warning("⏳ 正在等待 5M 數據...")
            return

        # 1. 1H EMA20 門禁
        trend_bias, trend_text, pdh_line, pdl_line = StrategyEngine.evaluate_trend_bias(df_1h, curr_price, df_day)

        # 2. 5M 計算與 2B 定罪
        df_5m_calc, raw_bull_pattern, raw_bear_pattern = StrategyEngine.evaluate_5m_signals(
            df_5m, trend_bias, pdh_line, pdl_line
        )

        bars_5 = df_5m_calc.tail(5).iloc[::-1].copy().reset_index(drop=True)
        table_rows = []
        latest_trigger_action = "☕ 處於安全中繼區，耐心等待 5M 收盤定罪"
        latest_trigger_type = "NONE"

        for idx, row in bars_5.iterrows():
            t_str = pd.to_datetime(row['time_key']).strftime('%H:%M')
            o, c, h, l, v = float(row['open']), float(row['close']), float(row['high']), float(row['low']), float(row['volume'])
            vma = float(row['vma20']) if row['vma20'] > 0 else 1.0
            atr = float(row['atr14'])
            td_s = str(row['td_setup'])
            vol_ratio = v / vma
            is_heavy = vol_ratio >= 1.25

            row_style = ""
            action_str = "⚪ 待機"
            diag_str = "⚪ 常規"

            if idx == 0:
                t_col = f"<b style='color:#58a6ff;'>{t_str}</b> <span style='background:#1f293d; color:#58a6ff; padding:1px 4px; border-radius:3px; font-size:10px;'>LIVE</span>"
                c_display = f"<span style='color:{flash_color}; font-weight:bold;'>${curr_price:,.1f}</span>"
                diag_str = "⚪ 走動中"
                action_str = "☕ 觀望"
            else:
                t_col = f"<b style='color:#8b949e;'>{t_str}</b> <span style='background:#21262d; color:#8b949e; padding:1px 4px; border-radius:3px; font-size:10px;'>🔒</span>"
                c_display = f"${c:,.1f}"

                is_bull_2b = raw_bull_pattern.iloc[df_5m_calc.index[df_5m_calc['time_key'] == row['time_key']][0]]
                is_bear_2b = raw_bear_pattern.iloc[df_5m_calc.index[df_5m_calc['time_key'] == row['time_key']][0]]

                if is_bull_2b and trend_bias >= 0:
                    row_style = "background-color: rgba(0, 230, 118, 0.18); border-left: 4px solid #00E676;"
                    diag_str = "🔥 2B 破底翻"
                    sl = l - 0.5 * atr
                    tp = c + 2.0 * (c - sl)
                    action_str = f"🎯 CALL (止:${sl:.1f}|盈:${tp:.1f})"
                    if idx == 1:
                        latest_trigger_type = "CALL"
                        latest_trigger_action = f"🔥 【買入 0DTE CALL】 入場:${c:.2f} | 止損:${sl:.2f} | 2R止盈:${tp:.2f}"
                elif is_bear_2b and trend_bias <= 0:
                    row_style = "background-color: rgba(255, 82, 82, 0.18); border-left: 4px solid #FF5252;"
                    diag_str = "🔥 2B 假突破"
                    sl = h + 0.5 * atr
                    tp = c - 2.0 * (sl - c)
                    action_str = f"🎯 PUT (止:${sl:.1f}|盈:${tp:.1f})"
                    if idx == 1:
                        latest_trigger_type = "PUT"
                        latest_trigger_action = f"🔥 【買入 0DTE PUT】 入場:${c:.2f} | 止損:${sl:.2f} | 2R止盈:${tp:.2f}"

            vol_pill = f"<span style='color:#00E676; font-weight:bold;'>{vol_ratio:.1f}x</span>" if is_heavy else f"<span style='color:#8b949e;'>{vol_ratio:.1f}x</span>"
            td_pill = f"<span style='color:#FF5252; font-weight:bold;'>{td_s[:4]}</span>" if "合格" in td_s else f"<span style='color:#8b949e;'>{td_s[:4]}</span>"

            table_rows.append({
                "時段": t_col,
                "現價": c_display,
                "極值(H/L)": f"{h:.1f}/{l:.1f}",
                "量能": vol_pill,
                "TD/形態": f"{td_pill} {diag_str}",
                "1:2 動作": action_str,
                "_style": row_style
            })

        # ==========================================
        # 🌟 單螢幕專屬緊湊佈局
        # ==========================================

        # 1. 頂部狀態列 (極簡 4 欄)
        c1, c2, c3, c4 = st.columns(4)
        c1.caption(f"📶 {snap['source']} ({snap['latency_ms']}ms)")
        c2.caption(f"🕒 {snap['server_time']} ET")
        c3.caption(f"🚦 {trend_text[:8]}")
        c4.caption(f"⏱️ 倒數: {countdown_str}")

        # 2. 🎯 置頂決策卡片 (最關鍵執行位)
        opt_plan = StrategyEngine.calculate_option_plan(curr_price, latest_trigger_type, budget_usd)
        card_border = '#00E676' if latest_trigger_type == 'CALL' else ('#FF5252' if latest_trigger_type == 'PUT' else '#58a6ff')

        with stylable_container(
            key="compact_opt_card",
            css_styles=f"""
                {{
                    background: #161b22;
                    padding: 8px 12px;
                    border-radius: 6px;
                    border-left: 4px solid {card_border};
                    font-family: monospace;
                    margin-bottom: 8px;
                }}
            """
        ):
            st.markdown(f"<b style='font-size:13px; color:{card_border};'>{latest_trigger_action}</b>", unsafe_allow_html=True)
            st.caption(f"推薦: **{opt_plan['opt_sym_str']}** | 預算: **${opt_plan['total_cost']:.0f}** | Delta: **0.51** | 盈虧比: **1:2**")

        # 3. 📊 5M 戰情一體寬表 (過去 5 根，高度鎖定)
        with stylable_container(
            key="compact_table_box",
            css_styles="{background-color: #0d1117; border: 1px solid #21262d; border-radius: 6px; padding: 6px;}"
        ):
            t_html = "<table style='width:100%; border-collapse: collapse; font-family: monospace; font-size: 11px;'>"
            t_html += "<tr style='border-bottom: 1px solid #30363d; color: #8b949e; text-align:left;'>"
            t_html += "<th>時段</th><th>現價</th><th>極值(H/L)</th><th>量</th><th>TD/形態</th><th>1:2動作</th></tr>"
            for r in table_rows:
                style = r["_style"] if r["_style"] else "border-bottom: 1px solid #161b22; color: #f0f6fc;"
                t_html += f"<tr style='{style}; padding: 3px 0;'><td>{r['時段']}</td><td>{r['現價']}</td><td>{r['極值(H/L)']}</td><td>{r['量能']}</td><td>{r['TD/形態']}</td><td>{r['1:2 動作']}</td></tr>"
            t_html += "</table>"
            st.markdown(t_html, unsafe_allow_html=True)
