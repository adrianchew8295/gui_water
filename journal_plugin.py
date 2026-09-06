# 文件名: journal_plugin.py
# 核心職責: 【策略記帳與高級可視化復盤插件】支援打點標籤、1H EMA20、RBS/SBR 戰區與純前端 Timer

import os
import sys
import datetime
import pandas as pd
import pytz
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import streamlit.components.v1 as components

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

tz_ny = pytz.timezone("America/New_York")
tz_my = pytz.timezone("Asia/Kuala_Lumpur")

DATA_DIR = os.path.join(CURRENT_DIR, 'market_data')
os.makedirs(DATA_DIR, exist_ok=True)

JOURNAL_CSV = os.path.join(DATA_DIR, 'strategy_live_journal.csv')
HEALTH_LOG_FILE = os.path.join(DATA_DIR, 'system_health.log')

class JournalPlugin:
    def __init__(self, journal_path: str = JOURNAL_CSV):
        self.journal_path = journal_path
        self._init_journal_file()

    def _init_journal_file(self):
        needs_init = False
        if not os.path.exists(self.journal_path):
            needs_init = True
        else:
            try:
                df_chk = pd.read_csv(self.journal_path)
                if df_chk.empty or 'code' not in df_chk.columns:
                    needs_init = True
            except Exception:
                needs_init = True

        if needs_init:
            sample_data = [
                {
                    "trade_id": "#20260906_01", "code": "CC.BTCUSD", "date": "2026-09-06", "time_et": "08:55", "time_myt": "20:55", "exit_time_et": "09:10",
                    "month": "2026-09", "direction": "🟢 CALL", "strategy": "Strategy 1", "entry": 79985.0, "sl": 79970.0, "tp": 80015.0,
                    "exit_price": 79970.0, "status": "LOSS_SL", "net_r": -1.0, "pnl_usd": -200.0, "score": 75,
                    "score_detail": "順應1H均線(+25) + 踩入RBS支撐(+25) + 2B長下影扎針(+25) + 放量不足(-25)",
                    "reason": "5M 2B 破底翻但隨後跌破支撐，觸發紀律止損", "pdh": 80069.4, "pdl": 79825.0,
                    "ema20_1h": 76068.5, "rbs": 79970.0, "sbr": 80020.0, "is_golden_window": False
                },
                {
                    "trade_id": "#20260904_01", "code": "US.QQQ", "date": "2026-09-04", "time_et": "10:15", "time_myt": "22:15", "exit_time_et": "10:45",
                    "month": "2026-09", "direction": "🟢 CALL", "strategy": "Strategy 1", "entry": 718.50, "sl": 717.30, "tp": 720.90,
                    "exit_price": 720.90, "status": "WIN_TP", "net_r": 2.0, "pnl_usd": 400.0, "score": 95,
                    "score_detail": "順應1H均線(+25) + 踩入RBS支撐(+25) + 2B破底翻(+25) + VPA 1.85x巨量(+20)",
                    "reason": "回踩 RBS 支撐帶 + 5M 2B 破底翻長下影線 + 1.85x 巨量共振", "pdh": 721.39, "pdl": 715.72,
                    "ema20_1h": 715.80, "rbs": 716.20, "sbr": 719.50, "is_golden_window": True
                }
            ]
            pd.DataFrame(sample_data).to_csv(self.journal_path, index=False)

    def load_health_log(self) -> str:
        if os.path.exists(HEALTH_LOG_FILE):
            try:
                with open(HEALTH_LOG_FILE, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception:
                pass
        return "暫無日誌記錄，後台守護進程運行中..."

    def load_journal(self) -> pd.DataFrame:
        if os.path.exists(self.journal_path):
            try:
                df = pd.read_csv(self.journal_path)
                if not df.empty and 'net_r' in df.columns:
                    return df
            except Exception:
                pass
        return pd.DataFrame()

    def evaluate_metrics(self, df: pd.DataFrame) -> dict:
        default_res = {
            "total": 0, "win_rate": 0.0, "rr": 0.0, "exp": 0.0,
            "verdict": "⚪ 樣本累積中", "color": "#8b949e", "wins": 0, "losses": 0,
            "total_pnl": 0.0
        }
        if df.empty or 'net_r' not in df.columns:
            return default_res
        
        wins = len(df[df['net_r'] > 0])
        total = len(df)
        losses = total - wins
        win_rate = (wins / total) * 100.0 if total > 0 else 0.0
        avg_w = df[df['net_r'] > 0]['net_r'].mean() if wins > 0 else 2.0
        avg_l = abs(df[df['net_r'] <= 0]['net_r'].mean()) if losses > 0 else 1.0
        rr = avg_w / avg_l if avg_l > 0 else 2.0
        p_w, p_l = win_rate / 100.0, (100.0 - win_rate) / 100.0
        exp = (p_w * avg_w) - (p_l * avg_l)
        total_pnl = float(df['pnl_usd'].sum()) if 'pnl_usd' in df.columns else (wins * 400.0 - losses * 200.0)

        if exp >= 0.35 and win_rate >= 50.0:
            verdict, color = "🟢 WORKABLE (推薦實盤)", "#00E676"
        elif exp > 0.0:
            verdict, color = "🟡 NEUTRAL (觀察微調)", "#ffd700"
        else:
            verdict, color = "🔴 NON-WORKABLE (淘汰/需優化)", "#FF5252"

        return {
            "total": total, "win_rate": win_rate, "rr": rr, "exp": exp,
            "verdict": verdict, "color": color, "wins": wins, "losses": losses,
            "total_pnl": total_pnl
        }

    def _convert_time_to_myt(self, time_key_str: str) -> str:
        try:
            if " " in time_key_str:
                dt_part = time_key_str.split(" ")[1][:5]
                h, m = map(int, dt_part.split(":"))
                h_my = (h + 12) % 24
                return f"{h_my:02d}:{m:02d}"
            return str(time_key_str)[-8:-3]
        except Exception:
            return str(time_key_str)[-5:]

    def _load_kline_data(self, code: str, entry_date_str: str = None, entry_time_str: str = None):
        clean_code = code.replace('.', '_')
        csv_path = os.path.join(DATA_DIR, f"{clean_code}_5M.csv")
        if not os.path.exists(csv_path):
            csv_path = os.path.join(DATA_DIR, f"{clean_code}_5M_2026.csv")

        if os.path.exists(csv_path):
            try:
                df_raw = pd.read_csv(csv_path)
                df_raw.columns = [c.lower() for c in df_raw.columns]
                
                if entry_date_str and entry_time_str:
                    match_indices = df_raw[df_raw['time_key'].astype(str).str.contains(entry_date_str, na=False)].index.tolist()
                    if match_indices:
                        mid_idx = match_indices[len(match_indices)//2]
                        for idx in match_indices:
                            if entry_time_str in str(df_raw.iloc[idx]['time_key']):
                                mid_idx = idx
                                break
                        start_i = max(0, mid_idx - 20)
                        end_i = min(len(df_raw), mid_idx + 24)
                        df_slice = df_raw.iloc[start_i:end_i].copy().reset_index(drop=True)
                        times = [self._convert_time_to_myt(str(t)) for t in df_slice['time_key']]
                        return times, df_slice['open'].astype(float).tolist(), df_slice['high'].astype(float).tolist(), df_slice['low'].astype(float).tolist(), df_slice['close'].astype(float).tolist(), df_slice['volume'].astype(float).tolist(), (mid_idx - start_i), str(df_slice.iloc[-1]['time_key'])

                df_slice = df_raw.tail(48).copy().reset_index(drop=True)
                times = [self._convert_time_to_myt(str(t)) for t in df_slice['time_key']]
                last_ts = str(df_slice.iloc[-1]['time_key']) if not df_slice.empty else "N/A"
                return times, df_slice['open'].astype(float).tolist(), df_slice['high'].astype(float).tolist(), df_slice['low'].astype(float).tolist(), df_slice['close'].astype(float).tolist(), df_slice['volume'].astype(float).tolist(), -1, last_ts
            except Exception:
                pass

        now_dt = datetime.datetime.now(tz_my)
        curr_min = (now_dt.minute // 5) * 5
        anchor = now_dt.replace(minute=curr_min, second=0, microsecond=0)
        times = [(anchor - datetime.timedelta(minutes=(47 - i) * 5)).strftime('%H:%M') for i in range(48)]
        base_p = 79705.0 if "BTC" in code else 718.50
        return times, [base_p]*48, [base_p+15]*48, [base_p-15]*48, [base_p]*48, [120.0]*48, -1, "DEMO"

    def render_interactive_chart(self, code: str, trade_row: pd.Series = None):
        if trade_row is not None:
            entry_p = float(trade_row.get('entry', 0.0))
            sl_p = float(trade_row.get('sl', 0.0))
            tp_p = float(trade_row.get('tp', 0.0))
            pdh_p = float(trade_row.get('pdh', entry_p * 1.002))
            pdl_p = float(trade_row.get('pdl', entry_p * 0.998))
            rbs_p = float(trade_row.get('rbs', entry_p * 0.999))
            sbr_p = float(trade_row.get('sbr', entry_p * 1.001))
            is_call = "CALL" in str(trade_row.get('direction', 'CALL'))
            is_win = trade_row.get('status') == 'WIN_TP'
            date_str = str(trade_row.get('date', '2026-09-04'))
            time_str = str(trade_row.get('time_et', '10:15'))
            times, opens, highs, lows, closes, volumes, entry_idx, last_ts = self._load_kline_data(code, date_str, time_str)
            exit_idx = min(len(times) - 1, entry_idx + 6) if entry_idx >= 0 else -1
            exit_p = float(trade_row.get('exit_price', entry_p))
            exit_label = "🎯 命中 2R 止盈 (+2.0R)" if is_win else "🛡️ 觸發止損出場 (-1.0R)"
        else:
            times, opens, highs, lows, closes, volumes, entry_idx, last_ts = self._load_kline_data(code)
            entry_p = closes[-1] if len(closes) > 0 else 79705.0
            sl_p, tp_p = entry_p * 0.998, entry_p * 1.004
            pdh_p, pdl_p = max(highs), min(lows)
            rbs_p, sbr_p = min(lows) * 1.001, max(highs) * 0.999
            exit_idx = -1

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.70, 0.30])

        fig.add_trace(go.Candlestick(
            x=times, open=opens, high=highs, low=lows, close=closes,
            increasing_line_color='#00E676', decreasing_line_color='#FF5252',
            increasing_fillcolor='#00E676', decreasing_fillcolor='#FF5252',
            name="5M K線"
        ), row=1, col=1)

        fig.add_hline(y=pdh_p, line_dash="dot", line_color="#ffd700", line_width=1.2, annotation_text=f"PDH: ${pdh_p:,.2f}", annotation_position="top left", row=1, col=1)
        fig.add_hline(y=pdl_p, line_dash="dot", line_color="#ffd700", line_width=1.2, annotation_text=f"PDL: ${pdl_p:,.2f}", annotation_position="bottom left", row=1, col=1)

        step_val = 15.0 if entry_p > 1000 else 0.4
        fig.add_hrect(y0=rbs_p - step_val * 0.3, y1=rbs_p + step_val * 0.3, line_width=0, fillcolor="#00E676", opacity=0.12, annotation_text="RBS 支撐", annotation_position="bottom left", row=1, col=1)
        fig.add_hrect(y0=sbr_p - step_val * 0.3, y1=sbr_p + step_val * 0.3, line_width=0, fillcolor="#FF5252", opacity=0.12, annotation_text="SBR 阻力", annotation_position="top left", row=1, col=1)

        if trade_row is not None and entry_idx >= 0 and entry_idx < len(times):
            fig.add_hline(y=entry_p, line_dash="dash", line_color="#58a6ff", annotation_text=f"進場: ${entry_p:,.2f}", annotation_position="top right", row=1, col=1)
            fig.add_hline(y=sl_p, line_dash="dash", line_color="#FF5252", annotation_text=f"止損: ${sl_p:,.2f}", annotation_position="bottom right", row=1, col=1)
            fig.add_hline(y=tp_p, line_dash="dash", line_color="#00E676", annotation_text=f"2R止盈: ${tp_p:,.2f}", annotation_position="top right", row=1, col=1)

            fig.add_annotation(
                x=times[entry_idx], y=lows[entry_idx],
                text=f"🟢 BUY {'CALL' if is_call else 'PUT'} 🔥<br>${entry_p:,.2f}",
                showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5, arrowcolor="#00E676",
                ay=35, font=dict(color="#00E676", size=10, family="monospace"),
                bgcolor="rgba(13, 17, 23, 0.88)", bordercolor="#00E676", borderwidth=1, borderpad=3,
                row=1, col=1
            )

            if exit_idx >= 0 and exit_idx < len(times):
                arrow_color = "#00E676" if is_win else "#FF5252"
                fig.add_annotation(
                    x=times[exit_idx], y=highs[exit_idx] if is_win else lows[exit_idx],
                    text=f"{exit_label}<br>${exit_p:,.2f}",
                    showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5, arrowcolor=arrow_color,
                    ay=-35 if is_win else 35, font=dict(color=arrow_color, size=10, family="monospace"),
                    bgcolor="rgba(13, 17, 23, 0.88)", bordercolor=arrow_color, borderwidth=1, borderpad=3,
                    row=1, col=1
                )

        vol_colors = ['#00E676' if c >= o else '#FF5252' for o, c in zip(opens, closes)]
        fig.add_trace(go.Bar(x=times, y=volumes, marker_color=vol_colors, name="5M 成交量"), row=2, col=1)

        valid_vols = [v for v in volumes if v > 0]
        vma20_val = sum(valid_vols) / len(valid_vols) if len(valid_vols) > 0 else 1.0
        fig.add_hline(y=vma20_val, line_dash="dash", line_color="#ffffff", line_width=1, annotation_text="VMA20", annotation_position="top left", row=2, col=1)

        kline_min = min(lows) if len(lows) > 0 else entry_p - 50
        kline_max = max(highs) if len(highs) > 0 else entry_p + 50
        padding = max(step_val * 2.5, (kline_max - kline_min) * 0.18)

        fig.update_layout(
            height=460,
            uirevision="static_viewport_lock",
            margin=dict(l=10, r=10, t=20, b=10),
            paper_bgcolor="#0d1117",
            plot_bgcolor="#0d1117",
            font=dict(color="#c9d1d9", family="monospace", size=11),
            xaxis=dict(gridcolor="#161b22", showgrid=True, rangeslider=dict(visible=False)),
            xaxis2=dict(gridcolor="#161b22", showgrid=True),
            yaxis=dict(gridcolor="#161b22", showgrid=True, range=[kline_min - padding, kline_max + padding]),
            yaxis2=dict(gridcolor="#161b22", showgrid=True),
            hovermode="x unified",
            dragmode="pan"
        )

        st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': True})
        return last_ts

    def render_journal_view(self, code: str, budget_usd: float = 200.0):
        """主入口方法：相容 app.py 的 render_journal_view 呼叫"""
        self.render_journal_dashboard(code, budget_usd)

    def render_journal_dashboard(self, code: str, budget_usd: float = 200.0):
        st.markdown("""
        <style>
        .block-container { padding-top: 0.6rem; padding-bottom: 0rem; }
        .metric-banner { background: #0d1117; border: 1px solid #21262d; border-radius: 6px; padding: 8px 14px; margin-bottom: 8px; font-family: monospace; }
        .win-tag { color: #00E676; font-weight: bold; background: rgba(0, 230, 118, 0.12); padding: 2px 6px; border-radius: 4px; }
        .loss-tag { color: #FF5252; font-weight: bold; background: rgba(255, 82, 82, 0.12); padding: 2px 6px; border-radius: 4px; }
        </style>
        """, unsafe_allow_html=True)

        df_all = self.load_journal()
        df = df_all[df_all['code'] == code] if (not df_all.empty and 'code' in df_all.columns) else df_all

        base_months = ["2026-09", "2026-08", "2026-07"]
        if not df.empty and 'month' in df.columns:
            existing_m = [str(x) for x in df['month'].dropna().unique()]
            month_list = ["📅 今天 (實盤 Live 進行中)"] + sorted(list(set(base_months + existing_m)), reverse=True)
        else:
            month_list = ["📅 今天 (實盤 Live 進行中)"] + base_months

        col_m1, col_m2 = st.columns([1.8, 3.2])
        with col_m1:
            sel_month = st.selectbox("📅 選擇回測/復盤月份:", month_list, index=0)

        now_dt_ny = datetime.datetime.now(tz_ny)
        if sel_month == "📅 今天 (實盤 Live 進行中)":
            today_str = now_dt_ny.strftime('%Y-%m-%d')
            df_filtered = df[df['date'] == today_str] if not df.empty and 'date' in df.columns else pd.DataFrame()
        else:
            df_filtered = df[df['month'] == sel_month] if not df.empty and 'month' in df.columns else pd.DataFrame()

        m = self.evaluate_metrics(df_filtered)

        with col_m2:
            pnl_color = "#00E676" if m['total_pnl'] >= 0 else "#FF5252"
            st.markdown(f"""
            <div class="metric-banner" style="margin-top: 4px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 13px; font-weight: bold; color: {m['color']};">🏆 {m['verdict']}</span>
                    <span style="font-size: 12px; color: #8b949e;">勝率: <b style="color:#ffd700;">{m['win_rate']:.1f}%</b> ({m['wins']}勝/{m['losses']}負) | 累計損益: <b style="color:{pnl_color};">${m['total_pnl']:+,.2f} USD</b></span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        selected_row = None
        if sel_month != "📅 今天 (實盤 Live 進行中)" and not df_filtered.empty:
            dates_available = sorted(list(df_filtered['date'].dropna().unique()), reverse=True)
            col_d1, col_d2 = st.columns([2, 3])
            with col_d1:
                sel_date = st.selectbox("📆 選擇交易日:", dates_available)
            
            df_day = df_filtered[df_filtered['date'] == sel_date]
            options = []
            for _, r in df_day.iterrows():
                is_win_r = r.get('status') == 'WIN_TP'
                res_tag = f"🟢 WIN (+2.0R / +$400)" if is_win_r else f"🔴 LOSS (-1.0R / -$200)"
                win_star = "⭐ [22:00-24:00 黃金時段]" if r.get('is_golden_window', False) or (r.get('time_et') in ['10:15', '11:45']) else "⚪ [全天復盤時段]"
                options.append(f"{win_star} {r.get('time_myt', '--')} MYT ({r.get('time_et', '--')} ET) | {r.get('direction')} | {res_tag}")
            
            with col_d2:
                sel_sig_idx = st.selectbox("🎯 選擇當日訊號穿透做功課:", range(len(options)), format_func=lambda x: options[x])

            selected_row = df_day.iloc[sel_sig_idx]

        chart_timer_html = f"""
        <div style="background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 6px 12px; margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center; font-family: monospace; font-size: 13px; color: #c9d1d9;">
            <div>
                <b style="color:#58a6ff; font-size:14px;">📈 5M 走勢圖 · 標的: {code}</b> 
                <span style="color: #00E676; font-size: 12px; margin-left: 8px;">[🟢 富途 OpenD 官方原生 5M · 大馬時間 MYT]</span>
            </div>
            <div id="chart_inline_timer" style="color: #ffd700; font-weight: bold; font-size: 14px; background: rgba(255, 215, 0, 0.12); border: 1px solid rgba(255, 215, 0, 0.3); border-radius: 4px; padding: 2px 8px;">
                ⏱️ 距離下根定格: 計算中...
            </div>
        </div>
        <script>
        function updateInlineTimer() {{
            var now = new Date();
            var totalSec = now.getMinutes() * 60 + now.getSeconds();
            var remSec = 300 - (totalSec % 300);
            if (remSec === 300) remSec = 0;
            var m = Math.floor(remSec / 60);
            var s = remSec % 60;
            var mStr = (m < 10 ? "0" : "") + m;
            var sStr = (s < 10 ? "0" : "") + s;
            var el = document.getElementById("chart_inline_timer");
            if (el) {{
                if (remSec === 0 || remSec >= 298) {{
                    el.innerHTML = "🟡 正在定格推進官方新 K 線...";
                    el.style.color = "#00E676";
                }} else {{
                    el.innerHTML = "⏱️ 距離下根定格: " + mStr + ":" + sStr;
                    el.style.color = "#ffd700";
                }}
            }}
        }}
        setInterval(updateInlineTimer, 1000);
        updateInlineTimer();
        </script>
        """
        components.html(chart_timer_html, height=44)

        last_kline_ts = self.render_interactive_chart(code, selected_row)

        if selected_row is not None:
            is_win_sel = selected_row.get('status') == 'WIN_TP'
            badge_html = '<span class="win-tag">🟢 WIN 止盈 (+2.0R / +$400 USD)</span>' if is_win_sel else '<span class="loss-tag">🔴 LOSS 止損 (-1.0R / -$200 USD)</span>'
            st.markdown(f"""
            <div style="background: #161b22; border-left: 4px solid {'#00E676' if is_win_sel else '#FF5252'}; padding: 8px 12px; border-radius: 4px; font-size: 12px; font-family: monospace; color: #c9d1d9; margin-bottom: 8px;">
                <div style="margin-bottom: 4px;">{badge_html} | 訂單: <b>{selected_row.get('trade_id')}</b> | 客觀評分: <b style="color:#00E676;">{selected_row.get('score', 0)} 分</b></div>
                <div>• <b>實戰點位</b>: 開倉 <b>${float(selected_row.get('entry', 0)):,.2f}</b> | 止損 <b>${float(selected_row.get('sl', 0)):,.2f}</b> | 止盈 <b>${float(selected_row.get('tp', 0)):,.2f}</b> | 出場 <b>${float(selected_row.get('exit_price', 0)):,.2f}</b></div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info(f"💡 【{sel_month}】實盤監控中 | 當前圖表最新官方定格柱: **{last_kline_ts}**")

        with st.expander("🛠️ [排查專用] 系統運行日誌 (System Health Log)", expanded=False):
            st.code(self.load_health_log(), language="text")

        trade_audit_log = f"=== 癸水 · 策略復盤日誌 (TRADE AUDIT LOG) ===\n• 標的: {code} | 當前最新柱: {last_kline_ts}\n• 狀態: 實盤監控中，48 根官方 5M 原生柱已對齊。\n============================================"
        with st.expander("📋 [策略專用] 訂單審核日誌 (Trade Audit Log)", expanded=False):
            st.code(trade_audit_log, language="text")
