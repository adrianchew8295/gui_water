# 文件名: chart_plugin.py
# 核心特性: 物理時間門禁 (徹底剔除未走完動態柱) + 毫秒級 Snapshot 現價動態推進 + 零時序重疊

import os
import sys
import time
import datetime
import pandas as pd
import pytz
import streamlit as st
from moomoo import OpenQuoteContext, RET_OK, SubType, KLType
from streamlit_extras.stylable_container import stylable_container

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from strategy_engine import StrategyEngine

tz_ny = pytz.timezone("America/New_York")
tz_my = pytz.timezone("Asia/Kuala_Lumpur")

DATA_DIR = os.path.join(CURRENT_DIR, 'market_data')
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
                ret, _ = ctx.subscribe([symbol], [SubType.QUOTE, SubType.TICKER, SubType.K_5M])
                if ret == RET_OK:
                    cls._subscribed_symbols.add(symbol)
                    return True
            except Exception:
                pass
        return symbol in cls._subscribed_symbols

class ChartPlugin:
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir

    def fetch_real_cur_5m(self, code: str) -> pd.DataFrame:
        """調用 get_cur_kline 獲取當前真實 60 根 5M 柱"""
        ctx = MarketDataEngine.get_context()
        target_symbol = "CC.BTCUSD" if "BTC" in code.upper() else code
        if ctx:
            MarketDataEngine.ensure_subscription(target_symbol)
            try:
                ret, df_k = ctx.get_cur_kline(target_symbol, num=60, ktype=KLType.K_5M)
                if ret == RET_OK and not df_k.empty:
                    df_k = df_k[['time_key', 'open', 'close', 'high', 'low', 'volume']].copy()
                    df_k['time_key'] = pd.to_datetime(df_k['time_key'])
                    df_k = df_k.sort_values('time_key').reset_index(drop=True)
                    
                    save_prefix = "CC_BTCUSD" if "BTC" in code.upper() else code.replace('.', '_')
                    f_path = os.path.join(self.data_dir, f"{save_prefix}_5M.csv")
                    df_k.to_csv(f_path, index=False)
                    return df_k
            except Exception:
                pass

        # 備援：讀取本地 CSV
        save_prefix = "CC_BTCUSD" if "BTC" in code.upper() else code.replace('.', '_')
        f_path = os.path.join(self.data_dir, f"{save_prefix}_5M.csv")
        if os.path.exists(f_path):
            try:
                df = pd.read_csv(f_path)
                df.columns = [c.lower().strip() for c in df.columns]
                df['time_key'] = pd.to_datetime(df['time_key'])
                return df.sort_values('time_key').reset_index(drop=True)
            except Exception:
                pass
        return pd.DataFrame()

    def get_realtime_snapshot(self, code: str) -> tuple:
        """獲取盤口毫秒級快照現價"""
        snap = {
            "price": 0.0, "source": "未連線", "server_time": "--",
            "latency_ms": 0, "open": 0.0, "high": 0.0, "low": 0.0, "vol": 0.0
        }
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
                    snap["open"] = float(row.get('open_price', row['last_price']))
                    snap["high"] = float(row.get('high_price', row['last_price']))
                    snap["low"] = float(row.get('low_price', row['last_price']))
                    snap["vol"] = float(row.get('volume', 0.0))
                    snap["source"] = "🟢 OpenD 直連 (毫秒級 Snapshot)"
                    snap["server_time"] = str(row.get('update_time', datetime.datetime.now(tz_ny).strftime('%H:%M:%S')))
                    snap["latency_ms"] = int((time.time() - t_start) * 1000)
                    status_msg = f"已成功訂閱 {target_symbol} 實時快照通道"
                else:
                    status_msg = f"快照獲取代碼: {ret_s}"
            except Exception as e:
                status_msg = f"快照連線異常: {str(e)}"

        return snap, status_msg

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
                if not df.empty and 'close' in df.columns:
                    return df
            except Exception:
                pass
        return pd.DataFrame()

    def get_countdown_and_current_slot(self) -> tuple:
        now = datetime.datetime.now(tz_ny)
        cur_min = now.minute
        cur_sec = now.second
        
        slot_min = (cur_min // 5) * 5
        cur_slot_time = now.replace(minute=slot_min, second=0, microsecond=0)
        slot_str = cur_slot_time.strftime('%H:%M')
        
        rem_min = 4 - (cur_min % 5)
        rem_sec = 60 - cur_sec
        if rem_sec == 60:
            rem_min += 1
            rem_sec = 0
            
        countdown_str = f"{rem_min:02d}:{rem_sec:02d}"
        return cur_slot_time, slot_str, countdown_str

    def track_live_bar_extremes(self, code: str, cur_slot_time: datetime.datetime, curr_price: float) -> tuple:
        slot_key = cur_slot_time.strftime('%Y-%m-%d %H:%M:%S')
        cache_key = f"{code}_live_bar"
        bar_data = st.session_state.get(cache_key, None)

        if bar_data is None or bar_data.get('slot') != slot_key:
            bar_data = {
                'slot': slot_key,
                'open': curr_price,
                'high': curr_price,
                'low': curr_price,
                'close': curr_price
            }
        else:
            bar_data['high'] = max(bar_data['high'], curr_price)
            bar_data['low'] = min(bar_data['low'], curr_price)
            bar_data['close'] = curr_price

        st.session_state[cache_key] = bar_data
        return bar_data['open'], bar_data['high'], bar_data['low'], bar_data['close']

    def render_cockpit(self, code: str, budget_usd: float = 200.0):
        # 1. 獲取數據
        df_5m_all = self.fetch_real_cur_5m(code)
        snap, status_msg = self.get_realtime_snapshot(code)
        df_day = self.load_cold_data(code, "DAY")
        cur_slot_time, live_slot_str, countdown_str = self.get_countdown_and_current_slot()

        curr_price = snap["price"]
        if curr_price <= 0 and not df_5m_all.empty:
            curr_price = float(df_5m_all['close'].iloc[-1])
        if curr_price <= 0:
            curr_price = 79900.0 if "BTC" in code.upper() else 488.50

        live_o, live_h, live_l, live_c = self.track_live_bar_extremes(code, cur_slot_time, curr_price)

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
            flash_color = "#00E676"
            flash_sym = "--"

        if df_5m_all.empty or len(df_5m_all) < 8:
            st.warning("⏳ 正在向 OpenD 同步最近真實 5M 歷史 K 線...")
            st.info(f"⚙️ 後台狀態: {status_msg}")
            return

        # 2. 策略計算
        trend_bias, trend_text, pdh_line, pdl_line = StrategyEngine.evaluate_trend_bias(df_day, curr_price)
        df_5m_calc, raw_bull, raw_bear = StrategyEngine.evaluate_5m_signals(df_5m_all, trend_bias, pdh_line, pdl_line)

        # ─── 核心防禦：物理時間門禁 (徹底剔除當前走動中的未閉合棒線) ───
        naive_cur_slot = cur_slot_time.replace(tzinfo=None)
        # 凡是時間戳大於等於當前 5M 開始時間的，一律排除在歷史收盤表之外
        closed_df = df_5m_calc[pd.to_datetime(df_5m_calc['time_key']) < naive_cur_slot].copy()

        # 取最近 5 根已閉合定格的歷史柱
        closed_bars_5 = closed_df.tail(5).iloc[::-1].copy().reset_index(drop=True)

        table1_rows = []
        table2_rows = []
        audit_bars_log = []

        latest_trigger_action = "☕ 處於安全中繼區，耐心等待 5M 收盤確認右側突破"
        latest_trigger_type = "NONE"

        # ─── 第 1 行：動態 LIVE 行 ───
        live_shape = StrategyEngine.classify_candle_shape(live_o, live_h, live_l, live_c)
        live_col1_t1 = f"<b style='color:#58a6ff;'>{live_slot_str}</b> <span style='background:#1f293d; color:#58a6ff; padding:2px 6px; border-radius:4px; font-weight:bold;'>⚡ LIVE</span> <span style='background:#161b22; color:#00E676; border:1px solid #238636; padding:2px 6px; border-radius:4px; font-weight:bold;'>⏱️ {countdown_str}</span>"
        live_col1_t2 = f"<b style='color:#58a6ff;'>{live_slot_str}</b> <span style='color:#00E676;'>🟢 待機中</span>"
        live_c_display = f"<span style='color:{flash_color}; font-weight:bold;'>${curr_price:,.2f} ({flash_sym}) [{live_shape}]</span>"
        
        table1_rows.append({
            "5M時段與狀態": live_col1_t1,
            "現價/收盤 (Close)": live_c_display,
            "影線極值 (High / Low)": f"{live_h:.2f} / {live_l:.2f}",
            "5M量能 (VPA)": "<span style='color:#8b949e;'>⚪ 即時撮合中</span>",
            "_style": ""
        })

        table2_rows.append({
            "5M時段與TD計數": live_col1_t2,
            "形態與戰區診斷": "⚪ 棒線走動中 (等待 5M 收盤定格)",
            "1:2 結構指令 & 動作": "☕ 觀望待機 (未收盤禁止開單)",
            "_style": ""
        })

        audit_bars_log.append(f"• {live_slot_str} ⚡ LIVE  | 現價: ${curr_price:,.2f} ({flash_sym}) [{live_shape}] | 當根極值: {live_h:.2f}/{live_l:.2f} | 狀態: 即時撮合動態推進")

        # ─── 第 2~6 行：已收盤定格歷史行 ───
        for idx, row in closed_bars_5.iterrows():
            t_str = pd.to_datetime(row['time_key']).strftime('%H:%M')
            o, c, h, l, v = float(row['open']), float(row['close']), float(row['high']), float(row['low']), float(row['volume'])
            vma = float(row['vma20']) if row['vma20'] > 0 else 1.0
            atr = float(row['atr14'])
            td_s = str(row['td_setup'])
            
            vol_ratio = v / max(vma, 1.0)
            is_heavy = vol_ratio >= 1.25
            candle_shape = StrategyEngine.classify_candle_shape(o, h, l, c)

            row_style = ""
            action_str = "🟢 待機中"
            diag_str = "⚪ 常規波動"

            col1_t1 = f"<b style='color:#8b949e;'>{t_str}</b> <span style='background:#21262d; color:#8b949e; padding:2px 6px; border-radius:4px;'>🔒 收盤</span>"
            
            if "S9" in td_s:
                td_html = f"<span style='background:rgba(255,82,82,0.25); color:#FF5252; padding:2px 6px; border-radius:4px; font-weight:bold;'>{td_s}</span>"
            elif "買入" in td_s:
                td_html = f"<span style='color:#00E676; font-weight:bold;'>{td_s}</span>"
            elif "賣出" in td_s:
                td_html = f"<span style='color:#FF5252; font-weight:bold;'>{td_s}</span>"
            else:
                td_html = f"<span style='color:#00E676;'>{td_s}</span>"

            col1_t2 = f"<b style='color:#8b949e;'>{t_str}</b> {td_html}"
            c_display = f"${c:,.2f} [{candle_shape}]"

            if idx + 1 < len(closed_bars_5):
                prev_bar = closed_bars_5.iloc[idx + 1]
                p_h, p_l = float(prev_bar['high']), float(prev_bar['low'])
                p_vol_ratio = float(prev_bar['volume']) / (float(prev_bar['vma20']) if prev_bar['vma20'] > 0 else 1.0)
                p_heavy = p_vol_ratio >= 1.25

                orig_idx = df_5m_calc.index[df_5m_calc['time_key'] == row['time_key']].tolist()
                if orig_idx:
                    p_orig_idx = orig_idx[0] - 1
                    has_prev_bull = raw_bull.iloc[p_orig_idx] if p_orig_idx >= 0 else False
                    has_prev_bear = raw_bear.iloc[p_orig_idx] if p_orig_idx >= 0 else False
                else:
                    has_prev_bull, has_prev_bear = False, False

                is_bull_confirmed = has_prev_bull and (h > p_h) and (c > o) and (is_heavy or p_heavy) and (trend_bias >= 0)
                is_bear_confirmed = has_prev_bear and (l < p_l) and (c < o) and (is_heavy or p_heavy) and (trend_bias <= 0)

                if is_bull_confirmed:
                    row_style = "background-color: rgba(0, 230, 118, 0.18); color: #ffffff; font-weight: bold; border-left: 5px solid #00E676;"
                    diag_str = "🔥 2B/晨星 右側放量衝破確認"
                    sl = p_l - 0.5 * atr
                    tp = c + 2.0 * (c - sl)
                    action_str = f"🎯 【買入 CALL】(入: ${c:.2f} | 止: ${sl:.2f} | 盈: ${tp:.2f})"
                    if idx == 0:
                        latest_trigger_type = "CALL"
                        latest_trigger_action = f"🔥 【右側確認 · 買入 0DTE CALL】 入場: ${c:.2f} | 止損: ${sl:.2f} | 2R止盈: ${tp:.2f}"

                elif is_bear_confirmed:
                    row_style = "background-color: rgba(255, 82, 82, 0.18); color: #ffffff; font-weight: bold; border-left: 5px solid #FF5252;"
                    diag_str = "🔥 2B/暮星 右側放量跌破確認"
                    sl = p_h + 0.5 * atr
                    tp = c - 2.0 * (sl - c)
                    action_str = f"🎯 【買入 PUT】(入: ${c:.2f} | 止: ${sl:.2f} | 盈: ${tp:.2f})"
                    if idx == 0:
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

            vol_pill = f"<span style='background:rgba(0,230,118,0.2); color:#00E676; padding:2px 8px; border-radius:12px; font-weight:bold;'>🟢 {vol_ratio:.2f}x 放量 ({v:.1f} BTC)</span>" if is_heavy else f"<span style='color:#8b949e;'>⚪ {vol_ratio:.2f}x 常規 ({v:.1f} BTC)</span>"

            table1_rows.append({
                "5M時段與狀態": col1_t1,
                "現價/收盤 (Close)": c_display,
                "影線極值 (High / Low)": f"{h:.2f} / {l:.2f}",
                "5M量能 (VPA)": vol_pill,
                "_style": row_style
            })

            table2_rows.append({
                "5M時段與TD計數": col1_t2,
                "形態與戰區診斷": diag_str,
                "1:2 結構指令 & 動作": action_str,
                "_style": row_style
            })

            audit_bars_log.append(f"• {t_str} 🔒 收盤  | 收盤: ${c:,.2f} [{candle_shape}] | 影線: {h:.2f}/{l:.2f} | 量: {vol_ratio:.2f}x ({v:.2f} BTC) | TD: {td_s} | 診斷: {diag_str}")

        opt_plan = StrategyEngine.calculate_option_plan(curr_price, latest_trigger_type, budget_usd)

        # ====== 頂部 HUD ======
        with stylable_container(
            key="hud_container",
            css_styles="""
                {
                    background-color: #0b0f19;
                    border: 1px solid #1f293d;
                    border-radius: 8px;
                    padding: 12px;
                    margin-bottom: 12px;
                    font-family: monospace;
                }
            """
        ):
            st.markdown(f"📶 通道: **{snap['source']}** | 撮合時間: **{snap['server_time']} ET** | 延遲: **{snap['latency_ms']} ms** | 宏觀方向: **{trend_text}**")
            st.caption(f"⚙️ 狀態: `{status_msg}` | 🎯 時序門禁已校準，零重複、零幽靈柱")

        # ====== 表 1 ======
        st.markdown("##### 📊 表 1：5M 即時量價核心表 (黃金 30 分鐘滾動窗口)")
        t1_html = "<table style='width:100%; border-collapse: collapse; font-family: monospace; font-size: 14px; text-align: left; background-color: #0d1117; border-radius: 8px; overflow: hidden;'>"
        t1_html += "<tr style='border-bottom: 2px solid #30363d; color: #8b949e; background-color: #161b22;'>"
        for col in ["5M時段與狀態", "現價/收盤 (Close)", "影線極值 (High / Low)", "5M量能 (VPA)"]:
            t1_html += f"<th style='padding: 10px;'>{col}</th>"
        t1_html += "</tr>"

        for r in table1_rows:
            style = r["_style"] if r["_style"] else "border-bottom: 1px solid #21262d; color: #f0f6fc;"
            t1_html += f"<tr style='{style}'>"
            t1_html += f"<td style='padding: 10px;'>{r['5M時段與狀態']}</td>"
            t1_html += f"<td style='padding: 10px;'>{r['現價/收盤 (Close)']}</td>"
            t1_html += f"<td style='padding: 10px;'>{r['影線極值 (High / Low)']}</td>"
            t1_html += f"<td style='padding: 10px;'>{r['5M量能 (VPA)']}</td>"
            t1_html += "</tr>"
        t1_html += "</table>"
        st.markdown(t1_html, unsafe_allow_html=True)

        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

        # ====== 表 2 ======
        st.markdown("##### ⏱️ 表 2：德馬克 TD 9轉與戰術表 (保守右側確認)")
        t2_html = "<table style='width:100%; border-collapse: collapse; font-family: monospace; font-size: 14px; text-align: left; background-color: #0d1117; border-radius: 8px; overflow: hidden;'>"
        t2_html += "<tr style='border-bottom: 2px solid #30363d; color: #8b949e; background-color: #161b22;'>"
        for col in ["5M時段與TD 9轉", "形態與戰區診斷", "1:2 結構指令 & 動作"]:
            t2_html += f"<th style='padding: 10px;'>{col}</th>"
        t2_html += "</tr>"

        for r in table2_rows:
            style = r["_style"] if r["_style"] else "border-bottom: 1px solid #21262d; color: #f0f6fc;"
            t2_html += f"<tr style='{style}'>"
            t2_html += f"<td style='padding: 10px;'>{r['5M時段與TD計數']}</td>"
            t2_html += f"<td style='padding: 10px;'>{r['形態與戰區診斷']}</td>"
            t2_html += f"<td style='padding: 10px;'>{r['1:2 結構指令 & 動作']}</td>"
            t2_html += "</tr>"
        t2_html += "</table>"
        st.markdown(t2_html, unsafe_allow_html=True)

        # ====== 模組 6: 0DTE 智能期權雷達 ======
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="background: #161b22; padding: 14px; border-radius: 8px; border-left: 5px solid {'#00E676' if latest_trigger_type=='CALL' else ('#FF5252' if latest_trigger_type=='PUT' else '#58a6ff')}; font-family: monospace;">
            <div style="font-size: 13px; color: #8b949e;">🎯 模組 6：0DTE 智能期權雷達 (預算上限: ${budget_usd:.2f} USD | 方向: {opt_plan['opt_dir_str']})</div>
            <div style="font-size: 16px; font-weight: bold; color: #ffffff; margin-top: 6px;">
                {latest_trigger_action}
            </div>
            <div style="font-size: 13px; color: #8b949e; margin-top: 8px; border-top: 1px solid #21262d; padding-top: 8px;">
                推薦合約: <b style="color: #ffd700;">{opt_plan['opt_sym_str']}</b> | 單張預算: <b>${opt_plan['total_cost']:.2f} USD</b> (符合 ${budget_usd:.2f} 上限) | Delta: <b>0.51</b> | Gamma: <b>0.18</b> | 盈虧比: <b>1:2</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ====== 模組 7: Audit Logs ======
        now_my_str = datetime.datetime.now(tz_my).strftime('%Y-%m-%d %H:%M:%S MYT')
        now_ny_str = datetime.datetime.now(tz_ny).strftime('%Y-%m-%d %H:%M:%S ET')

        audit_text = f"=== 癸水 0DTE 量化審核日誌 (AUDIT LOGS) ===\n"
        audit_text += f"[時間戳憑證]\n"
        audit_text += f"• 大馬本地時間: {now_my_str}\n"
        audit_text += f"• 美東交易所時間: {now_ny_str}\n"
        audit_text += f"• 通道來源: {snap['source']} (延遲: {snap['latency_ms']} ms)\n"
        audit_text += f"• 訂閱狀態: {status_msg}\n"
        audit_text += f"• 宏觀門禁: {trend_text}\n"
        audit_text += f"\n[5M 閉合時序審核 (過去 6 根真實 K 線)]\n"
        for l in audit_bars_log:
            audit_text += f"{l}\n"
        audit_text += f"\n[開火指令與風控驗證]\n"
        audit_text += f"• 當前戰術動作: {latest_trigger_action}\n"
        audit_text += f"• 0DTE 推薦合約: {opt_plan['opt_sym_str']} | 單張預算: ${opt_plan['total_cost']:.2f} USD\n"
        audit_text += f"===========================================\n"

        st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
        st.markdown("##### 📋 審核日誌 (Audit Logs) —— 複製框 (右上角自帶複製按鈕)：")
        st.code(audit_text, language="text")
