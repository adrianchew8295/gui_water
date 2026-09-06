# 文件名: chart_plugin.py
# 核心特性: streamlit-extras Grid 網格分段 + 1H EMA20 門禁 + 5M 2B 當根定罪 + 0DTE 風控

import os
import time
import datetime
import numpy as np
import pandas as pd
import pytz
import streamlit as st
from moomoo import OpenQuoteContext, RET_OK, KLType, SubType, AuType

# 引入 streamlit-extras 核心佈局組件
from streamlit_extras.grid import grid
from streamlit_extras.stylable_container import stylable_container

tz_ny = pytz.timezone("America/New_York")
tz_my = pytz.timezone("Asia/Kuala_Lumpur")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'market_data')
os.makedirs(DATA_DIR, exist_ok=True)

class MarketDataEngine:
    """單例常駐連線引擎"""
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
        if len(df) < 2:
            return pd.Series([1.0] * len(df))
        high = df['high']
        low = df['low']
        close = df['close'].shift(1).bfill()
        tr = np.maximum(high - low, np.maximum((high - close).abs(), (low - close).abs()))
        return tr.rolling(window=period).mean().bfill()

    def compute_td_setup(self, df: pd.DataFrame) -> list:
        """依據彭博 Bloomberg 標準計算德馬克 TD Setup (含 Qualifier 資格認證)"""
        setup_type = ["⚪ 待機中"] * len(df)
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
                setup_type[i] = "⚪ 待機中"
        return setup_type

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
                    snap["source"] = "🟢 OpenD 直連 (熱數據流)"
                    snap["server_time"] = str(row.get('update_time', datetime.datetime.now(tz_ny).strftime('%H:%M:%S')))
                    snap["latency_ms"] = int((time.time() - t_start) * 1000)
                    status_msg = f"已訂閱 {target_symbol} 實時通道"

                ret_k, df_k = ctx.get_cur_kline(target_symbol, 40, KLType.K_5M, AuType.NONE)
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
                    snap["source"] = "💾 本地 CSV 緩存"
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
        snap, status_msg, df_5m = self.get_realtime_and_kline_data(code)
        df_1h = self.load_cold_data(code, "1Hr")
        df_day = self.load_cold_data(code, "DAY")
        countdown_str = self.get_countdown_to_next_5m()

        curr_price = snap["price"]
        if curr_price <= 0 and not df_5m.empty:
            curr_price = float(df_5m['close'].iloc[-1])
        if curr_price <= 0:
            curr_price = 79700.0 if "BTC" in code.upper() else 488.50

        prev_p_key = f"{code}_prev_price"
        prev_p = st.session_state.get(prev_p_key, curr_price)
        st.session_state[prev_p_key] = curr_price

        delta_val = curr_price - prev_p
        flash_color = "#00E676" if delta_val > 0 else ("#FF5252" if delta_val < 0 else "#f0f6fc")
        flash_sym = f"▲ +${delta_val:.2f}" if delta_val > 0 else (f"▼ -${abs(delta_val):.2f}" if delta_val < 0 else "--")

        if df_5m.empty or len(df_5m) < 8:
            st.warning("⏳ 正在等待 5M 數據連通中...")
            st.info(f"⚙️ 後台狀態: {status_msg}")
            return

        # 1. 宏觀方向門禁：1H EMA20
        trend_bias = 0
        trend_text = "⚪ 0 (1H中立震盪)"
        pdh_line = curr_price * 1.008
        pdl_line = curr_price * 0.992

        if not df_day.empty and len(df_day) >= 2:
            prev_d = df_day.iloc[-2]
            pdh_line = float(prev_d.get('high', curr_price * 1.008))
            pdl_line = float(prev_d.get('low', curr_price * 0.992))

        if not df_1h.empty and len(df_1h) >= 20:
            df_1h['ema20'] = df_1h['close'].ewm(span=20, adjust=False).mean()
            last_h = df_1h.iloc[-1]
            if float(last_h['close']) >= float(last_h['ema20']):
                trend_bias = 1
                trend_text = f"🟢 +1 (1H多頭 [收>{float(last_h['ema20']):.2f}])"
            else:
                trend_bias = -1
                trend_text = f"🔴 -1 (1H空頭 [收<{float(last_h['ema20']):.2f}])"

        # 2. 5M 計算與 2B 當根定罪
        df_5m['vma20'] = df_5m['volume'].rolling(20).mean().bfill()
        df_5m['atr14'] = self.calculate_atr(df_5m, 14)
        df_5m['td_setup'] = self.compute_td_setup(df_5m)

        bull_2b_raw = (df_5m['low'] < pdl_line) & (df_5m['close'] > pdl_line) & (df_5m['close'] >= df_5m['open'])
        bear_2b_raw = (df_5m['high'] > pdh_line) & (df_5m['close'] < pdh_line) & (df_5m['close'] < df_5m['open'])

        bars_6 = df_5m.tail(6).iloc[::-1].copy().reset_index(drop=True)
        table1_rows = []
        table2_rows = []
        audit_bars_log = []

        latest_trigger_action = "☕ 處於安全中繼區，耐心等待 5M 收盤定罪"
        latest_trigger_type = "NONE"

        for idx, row in bars_6.iterrows():
            t_str = pd.to_datetime(row['time_key']).strftime('%H:%M')
            o, c, h, l, v = float(row['open']), float(row['close']), float(row['high']), float(row['low']), float(row['volume'])
            vma = float(row['vma20']) if row['vma20'] > 0 else 1.0
            atr = float(row['atr14'])
            td_s = str(row['td_setup'])
            vol_ratio = v / vma
            is_heavy = vol_ratio >= 1.25

            row_style = ""
            action_str = "⚪ 待機中"
            diag_str = "⚪ 常規波動"

            if idx == 0:
                col1_t1 = f"<b style='color:#58a6ff;'>{t_str}</b> <span style='background:#1f293d; color:#58a6ff; padding:2px 6px; border-radius:4px; font-weight:bold;'>⚡ LIVE</span>"
                col1_t2 = f"<b style='color:#58a6ff;'>{t_str}</b> <span style='color:#8b949e;'>{td_s}</span>"
                c_display = f"<span style='color:{flash_color}; font-weight:bold;'>${curr_price:,.2f} ({flash_sym})</span>"
                h_display = f"{max(h, curr_price):.2f}"
                l_display = f"{min(l, curr_price):.2f}"
                diag_str = "⚪ 走動中 (等 5M 收盤)"
                action_str = "☕ 觀望待機"
                audit_log_line = f"• {t_str} ⚡ LIVE  | 現價: ${curr_price:,.2f} | 影線: {h_display}/{l_display} | 量: {vol_ratio:.2f}x | TD: {td_s}"
            else:
                col1_t1 = f"<b style='color:#8b949e;'>{t_str}</b> <span style='background:#21262d; color:#8b949e; padding:2px 6px; border-radius:4px;'>🔒 收盤</span>"
                td_html = f"<span style='background:rgba(255,82,82,0.25); color:#FF5252; padding:2px 6px; border-radius:4px; font-weight:bold;'>{td_s}</span>" if "合格" in td_s else f"<span style='color:#8b949e;'>{td_s}</span>"
                col1_t2 = f"<b style='color:#8b949e;'>{t_str}</b> {td_html}"
                c_display = f"${c:,.2f}"
                h_display, l_display = f"{h:.2f}", f"{l:.2f}"

                is_bull_2b = bull_2b_raw.iloc[df_5m.index[df_5m['time_key'] == row['time_key']][0]]
                is_bear_2b = bear_2b_raw.iloc[df_5m.index[df_5m['time_key'] == row['time_key']][0]]

                if is_bull_2b and trend_bias >= 0:
                    row_style = "background-color: rgba(0, 230, 118, 0.18); border-left: 5px solid #00E676;"
                    diag_str = "🔥 2B 破底翻 (當根插針收回)"
                    sl = l - 0.5 * atr
                    tp = c + 2.0 * (c - sl)
                    action_str = f"🎯 買 CALL (入: ${c:.2f} | 止: ${sl:.2f} | 盈: ${tp:.2f})"
                    if idx == 1:
                        latest_trigger_type = "CALL"
                        latest_trigger_action = f"🔥 【買入 0DTE CALL】 入場: ${c:.2f} | 止損: ${sl:.2f} | 2R止盈: ${tp:.2f}"

                elif is_bear_2b and trend_bias <= 0:
                    row_style = "background-color: rgba(255, 82, 82, 0.18); border-left: 5px solid #FF5252;"
                    diag_str = "🔥 2B 假突破 (當根衝高回落)"
                    sl = h + 0.5 * atr
                    tp = c - 2.0 * (sl - c)
                    action_str = f"🎯 買 PUT (入: ${c:.2f} | 止: ${sl:.2f} | 盈: ${tp:.2f})"
                    if idx == 1:
                        latest_trigger_type = "PUT"
                        latest_trigger_action = f"🔥 【買入 0DTE PUT】 入場: ${c:.2f} | 止損: ${sl:.2f} | 2R止盈: ${tp:.2f}"

                audit_log_line = f"• {t_str} 🔒 收盤  | 收盤: ${c:,.2f} | 影線: {h_display}/{l_display} | 量: {vol_ratio:.2f}x | TD: {td_s} | 診斷: {diag_str}"

            vol_pill = f"<span style='background:rgba(0,230,118,0.2); color:#00E676; padding:2px 8px; border-radius:12px; font-weight:bold;'>🟢 {vol_ratio:.2f}x</span>" if is_heavy else f"<span style='color:#8b949e;'>⚪ {vol_ratio:.2f}x</span>"

            table1_rows.append({"時段": col1_t1, "現價/收盤": c_display, "極值(H/L)": f"{h_display}/{l_display}", "量能(VPA)": vol_pill, "_style": row_style})
            table2_rows.append({"時段與TD": col1_t2, "形態與戰區": diag_str, "1:2 指令動作": action_str, "_style": row_style})
            audit_bars_log.append(audit_log_line)

        # ==========================================
        # 🌟 核心分段：STREAMLIT-EXTRAS GRID LAYOUT
        # ==========================================

        # 【分段 1：頂部狀態 4 欄網格】
        status_grid = grid(4, vertical_align="center")
        with status_grid:
            st.metric("📶 連線通道", snap['source'], f"{snap['latency_ms']} ms")
            st.metric("🕒 美東撮合時間", f"{snap['server_time']} ET")
            st.metric("🚦 1H EMA20 門禁", trend_text)
            st.metric("⏱️ 5M 換棒倒數", countdown_str)

        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

        # 【分段 2：雙表並排/獨立網格 (1.1 : 1.0)】
        tables_grid = grid([1.1, 1.0], vertical_align="top")

        with tables_grid:
            # 左網格：表 1 量價核心表
            with stylable_container(key="t1_box", css_styles="{background-color: #0d1117; border: 1px solid #21262d; border-radius: 8px; padding: 12px;}"):
                st.markdown("##### 📊 5M 即時量價核心表")
                t1_html = "<table style='width:100%; border-collapse: collapse; font-family: monospace; font-size: 13px;'>"
                t1_html += "<tr style='border-bottom: 2px solid #30363d; color: #8b949e;'><th>時段</th><th>現價/收盤</th><th>極值(H/L)</th><th>量能</th></tr>"
                for r in table1_rows:
                    style = r["_style"] if r["_style"] else "border-bottom: 1px solid #161b22; color: #f0f6fc;"
                    t1_html += f"<tr style='{style}'><td>{r['時段']}</td><td>{r['現價/收盤']}</td><td>{r['極值(H/L)']}</td><td>{r['量能(VPA)']}</td></tr>"
                t1_html += "</table>"
                st.markdown(t1_html, unsafe_allow_html=True)

            # 右網格：表 2 TD9 與 2B 診斷表
            with stylable_container(key="t2_box", css_styles="{background-color: #0d1117; border: 1px solid #21262d; border-radius: 8px; padding: 12px;}"):
                st.markdown("##### ⏱️ 德馬克 TD 9轉與 2B 診斷")
                t2_html = "<table style='width:100%; border-collapse: collapse; font-family: monospace; font-size: 13px;'>"
                t2_html += "<tr style='border-bottom: 2px solid #30363d; color: #8b949e;'><th>時段與TD</th><th>形態診斷</th><th>1:2 動作</th></tr>"
                for r in table2_rows:
                    style = r["_style"] if r["_style"] else "border-bottom: 1px solid #161b22; color: #f0f6fc;"
                    t2_html += f"<tr style='{style}'><td>{r['時段與TD']}</td><td>{r['形態與戰區']}</td><td>{r['1:2 指令動作']}</td></tr>"
                t2_html += "</table>"
                st.markdown(t2_html, unsafe_allow_html=True)

        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

        # 【分段 3：0DTE 期權射控決策卡片網格 (1 欄通欄)】
        strike_atm = round(curr_price)
        total_cost = 1.45 * 100
        opt_dir_str = "🟢 CALL 多單" if latest_trigger_type == "CALL" else ("🔴 PUT 空單" if latest_trigger_type == "PUT" else "⚪ 待機觀望")
        opt_sym_str = f"QQQ {strike_atm} {'CALL' if latest_trigger_type != 'PUT' else 'PUT'}"

        with stylable_container(
            key="opt_radar_box",
            css_styles=f"""
                {{
                    background: #161b22;
                    padding: 16px;
                    border-radius: 8px;
                    border-left: 5px solid {'#00E676' if latest_trigger_type=='CALL' else ('#FF5252' if latest_trigger_type=='PUT' else '#58a6ff')};
                    font-family: monospace;
                }}
            """
        ):
            st.markdown(f"🎯 **模組 6：0DTE 智能期權雷達 (預算上限: ${budget_usd:.2f} USD | 方向: {opt_dir_str})**")
            st.markdown(f"### {latest_trigger_action}")
            st.caption(f"推薦合約: **{opt_sym_str}** | 單張預算: **${total_cost:.2f} USD** | Delta: **0.51** | 盈虧比: **1:2**")

        # 【分段 4：審核日誌 Audit Logs 複製網格】
        now_my_str = datetime.datetime.now(tz_my).strftime('%Y-%m-%d %H:%M:%S MYT')
        now_ny_str = datetime.datetime.now(tz_ny).strftime('%Y-%m-%d %H:%M:%S ET')

        audit_text = f"=== 癸水 0DTE 量化審核日誌 (AUDIT LOGS) ===\n"
        audit_text += f"• 大馬本地時間: {now_my_str} | 美東時間: {now_ny_str}\n"
        audit_text += f"• 通道來源: {snap['source']} (延遲: {snap['latency_ms']} ms) | 宏觀門禁: {trend_text}\n"
        audit_text += f"\n[5M 閉合時序 (過去 6 根)]\n"
        for l in audit_bars_log:
            audit_text += f"{l}\n"
        audit_text += f"\n• 戰術動作: {latest_trigger_action} | 推薦: {opt_sym_str}\n"
        audit_text += f"===========================================\n"

        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        st.caption("📋 審核日誌 (Audit Logs - 右上角自帶一鍵複製)：")
        st.code(audit_text, language="text")
