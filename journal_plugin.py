# 文件名: journal_plugin.py
# 核心職責: 【策略記帳與高級可視化復盤插件】完整月度/日期 Dropdown + 滾輪縮放 + 幾何指標還原

import os
import sys
import datetime
import pandas as pd
import pytz
import plotly.graph_objects as go
import streamlit as st

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

tz_ny = pytz.timezone("America/New_York")
tz_my = pytz.timezone("Asia/Kuala_Lumpur")

JOURNAL_CSV = os.path.join(CURRENT_DIR, 'market_data', 'strategy_live_journal.csv')
os.makedirs(os.path.dirname(JOURNAL_CSV), exist_ok=True)

class JournalPlugin:
    def __init__(self, journal_path: str = JOURNAL_CSV):
        self.journal_path = journal_path
        self._init_journal_file()

    def _init_journal_file(self):
        """如果文件不存在或為空，注入標準月度回測樣本數據"""
        needs_init = False
        if not os.path.exists(self.journal_path):
            needs_init = True
        else:
            try:
                df_chk = pd.read_csv(self.journal_path)
                if df_chk.empty:
                    needs_init = True
            except Exception:
                needs_init = True

        if needs_init:
            sample_data = [
                {
                    "trade_id": "#20260906_01", "date": "2026-09-06", "time_et": "06:25", "month": "2026-09",
                    "direction": "🟢 CALL", "strategy": "Strategy 1", "entry": 79985.0, "sl": 79970.0, "tp": 80015.0,
                    "exit_price": 80015.0, "status": "WIN_TP", "net_r": 2.0, "score": 85,
                    "reason": "5M 2B 破底翻放量企穩 + 回踩 RBS 支撐帶", "ema20_1h": 76068.5, "rbs": 79970.0, "sbr": 80020.0
                },
                {
                    "trade_id": "#20260904_02", "date": "2026-09-04", "time_et": "10:15", "month": "2026-09",
                    "direction": "🟢 CALL", "strategy": "Strategy 1", "entry": 487.50, "sl": 486.60, "tp": 489.30,
                    "exit_price": 489.30, "status": "WIN_TP", "net_r": 2.0, "score": 90,
                    "reason": "TD9 衰竭共振 + 2B 破底翻長下影線", "ema20_1h": 485.80, "rbs": 486.20, "sbr": 488.50
                },
                {
                    "trade_id": "#20260904_03", "date": "2026-09-04", "time_et": "11:45", "month": "2026-09",
                    "direction": "🔴 PUT", "strategy": "Strategy 1", "entry": 488.50, "sl": 489.10, "tp": 487.30,
                    "exit_price": 489.10, "status": "LOSS_SL", "net_r": -1.0, "score": 78,
                    "reason": "5M 2B 衝頂誘多失敗，後續大陽突破打損", "ema20_1h": 485.80, "rbs": 486.20, "sbr": 488.50
                },
                {
                    "trade_id": "#20260828_01", "date": "2026-08-28", "time_et": "10:30", "month": "2026-08",
                    "direction": "🟢 CALL", "strategy": "Strategy 1", "entry": 482.00, "sl": 481.20, "tp": 483.60,
                    "exit_price": 483.60, "status": "WIN_TP", "net_r": 2.0, "score": 85,
                    "reason": "回踩日線 EMA20 支撐企穩", "ema20_1h": 480.50, "rbs": 481.20, "sbr": 484.00
                },
                {
                    "trade_id": "#20260715_01", "date": "2026-07-15", "time_et": "10:45", "month": "2026-07",
                    "direction": "🟢 CALL", "strategy": "Strategy 1", "entry": 475.00, "sl": 474.20, "tp": 476.60,
                    "exit_price": 476.60, "status": "WIN_TP", "net_r": 2.0, "score": 88,
                    "reason": "突破昨日最高點 PDH 回踩確認", "ema20_1h": 473.80, "rbs": 474.50, "sbr": 477.00
                }
            ]
            pd.DataFrame(sample_data).to_csv(self.journal_path, index=False)

    def load_journal(self) -> pd.DataFrame:
        if os.path.exists(self.journal_path):
            try:
                return pd.read_csv(self.journal_path)
            except Exception:
                pass
        return pd.DataFrame()

    def evaluate_metrics(self, df: pd.DataFrame) -> dict:
        default_res = {
            "total": 0, "win_rate": 0.0, "rr": 0.0, "exp": 0.0,
            "verdict": "⚪ 樣本累積中", "color": "#8b949e",
            "wins": 0, "losses": 0
        }
        if df.empty or 'net_r' not in df.columns:
            return default_res
        
        wins = len(df[df['net_r'] > 0])
        total = len(df)
        losses = total - wins
        win_rate = (wins / total) * 100 if total > 0 else 0.0
        
        avg_w = df[df['net_r'] > 0]['net_r'].mean() if wins > 0 else 2.0
        avg_l = abs(df[df['net_r'] <= 0]['net_r'].mean()) if losses > 0 else 1.0
        rr = avg_w / avg_l if avg_l > 0 else 2.0
        p_w, p_l = win_rate / 100.0, (100.0 - win_rate) / 100.0
        exp = (p_w * avg_w) - (p_l * avg_l)

        if exp >= 0.35 and win_rate >= 50.0:
            verdict, color = "🟢 WORKABLE (強烈推薦實盤)", "#00E676"
        elif exp > 0.0:
            verdict, color = "🟡 NEUTRAL (觀察微調)", "#ffd700"
        else:
            verdict, color = "🔴 NON-WORKABLE (淘汰)", "#FF5252"

        return {
            "total": total, "win_rate": win_rate, "rr": rr, "exp": exp,
            "verdict": verdict, "color": color, "wins": wins, "losses": losses
        }

    def render_interactive_replay_chart(self, trade_row: pd.Series):
        """Plotly 互動圖表 · 支援滾輪縮放/拖拽"""
        entry_p = float(trade_row.get('entry', 0.0))
        sl_p = float(trade_row.get('sl', 0.0))
        tp_p = float(trade_row.get('tp', 0.0))
        ema20 = float(trade_row.get('ema20_1h', entry_p * 0.98))
        rbs_p = float(trade_row.get('rbs', entry_p * 0.99))
        sbr_p = float(trade_row.get('sbr', entry_p * 1.01))
        is_call = "CALL" in str(trade_row.get('direction', 'CALL'))

        times = [f"T-{i}" for i in range(5, 0, -1)] + ["ENTRY (觸發)"] + [f"T+{i}" for i in range(1, 6)]
        base_prices = [entry_p - (i * 1.2 if is_call else -i * 1.2) for i in range(5, 0, -1)] + [entry_p] + [entry_p + (i * 1.5 if is_call else -i * 1.5) for i in range(1, 6)]
        
        opens = [p - 0.5 for p in base_prices]
        closes = [p + 0.8 if i % 2 == 0 else p - 0.4 for i, p in enumerate(base_prices)]
        highs = [max(o, c) + 1.0 for o, c in zip(opens, closes)]
        lows = [min(o, c) - 1.0 for o, c in zip(opens, closes)]

        fig = go.Figure()

        # 1. 5M K線
        fig.add_trace(go.Candlestick(
            x=times, open=opens, high=highs, low=lows, close=closes,
            increasing_line_color='#00E676', decreasing_line_color='#FF5252',
            increasing_fillcolor='#00E676', decreasing_fillcolor='#FF5252',
            name="5M K線"
        ))

        # 2. 1H EMA20 均線
        fig.add_trace(go.Scatter(
            x=times, y=[ema20] * len(times), mode='lines',
            line=dict(color='#3b82f6', width=2, dash='solid'),
            name=f"1H EMA20 (${ema20:,.2f})"
        ))

        # 3. RBS/SBR 戰區色塊
        fig.add_hrect(y0=rbs_p - 0.3, y1=rbs_p + 0.3, line_width=0, fillcolor="#00E676", opacity=0.12, annotation_text="RBS 支撐戰區", annotation_position="bottom left")
        fig.add_hrect(y0=sbr_p - 0.3, y1=sbr_p + 0.3, line_width=0, fillcolor="#FF5252", opacity=0.12, annotation_text="SBR 阻力戰區", annotation_position="top left")

        # 4. 交易線
        fig.add_hline(y=entry_p, line_dash="dash", line_color="#58a6ff", annotation_text=f"進場: ${entry_p:,.2f}", annotation_position="top right")
        fig.add_hline(y=sl_p, line_dash="dash", line_color="#FF5252", annotation_text=f"止損: ${sl_p:,.2f}", annotation_position="bottom right")
        fig.add_hline(y=tp_p, line_dash="dash", line_color="#00E676", annotation_text=f"2R止盈: ${tp_p:,.2f}", annotation_position="top right")

        fig.update_layout(
            height=340,
            margin=dict(l=10, r=10, t=25, b=10),
            paper_bgcolor="#0d1117",
            plot_bgcolor="#0d1117",
            font=dict(color="#c9d1d9", family="monospace", size=11),
            xaxis=dict(gridcolor="#161b22", showgrid=True, rangeslider=dict(visible=False)),
            yaxis=dict(gridcolor="#161b22", showgrid=True),
            hovermode="x unified",
            dragmode="pan"
        )

        st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': True})

    def render_journal_dashboard(self, code: str, budget_usd: float = 200.0):
        st.markdown("""
        <style>
        .block-container { padding-top: 0.8rem; padding-bottom: 0rem; }
        .metric-banner { background: #0d1117; border: 1px solid #21262d; border-radius: 6px; padding: 6px 12px; margin-bottom: 8px; font-family: monospace; }
        </style>
        """, unsafe_allow_html=True)

        df = self.load_journal()
        is_btc = "BTC" in code.upper()

        # ====== 第 1 層：月份下拉選單 (保證永遠有選項) ======
        base_months = ["2026-09", "2026-08", "2026-07"]
        if not df.empty and 'month' in df.columns:
            existing_m = [str(x) for x in df['month'].dropna().unique()]
            month_list = ["📅 今天 (實盤 Live 進行中)"] + sorted(list(set(base_months + existing_m)), reverse=True)
        else:
            month_list = ["📅 今天 (實盤 Live 進行中)"] + base_months

        col_m1, col_m2 = st.columns([1.8, 3.2])
        with col_m1:
            sel_month = st.selectbox("📅 選擇回測/復盤月份:", month_list, index=1)

        # 依選定月份過濾
        if sel_month == "📅 今天 (實盤 Live 進行中)":
            today_str = datetime.datetime.now(tz_ny).strftime('%Y-%m-%d')
            df_filtered = df[df['date'] == today_str] if not df.empty and 'date' in df.columns else pd.DataFrame()
        else:
            df_filtered = df[df['month'] == sel_month] if not df.empty and 'month' in df.columns else pd.DataFrame()

        m = self.evaluate_metrics(df_filtered)

        with col_m2:
            st.markdown(f"""
            <div class="metric-banner" style="margin-top: 4px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 13px; font-weight: bold; color: {m['color']};">🏆 {m['verdict']}</span>
                    <span style="font-size: 12px; color: #8b949e;">勝率: <b style="color:#ffd700;">{m['win_rate']:.1f}%</b> ({m['wins']}勝/{m['losses']}負) | 盈虧比: <b style="color:#ffd700;">1:{m['rr']:.2f}</b> | 期望值: <b style="color:{m['color']};">{m['exp']:+.2f}R</b></span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        if df_filtered.empty:
            st.info(f"💡 【{sel_month}】暫無已結算訂單，實盤監控中...")
            self._render_audit_log_box(code, is_btc, m, None)
            return

        # ====== 第 2 層：日期與時段訊號過濾 ======
        dates_available = sorted(list(df_filtered['date'].dropna().unique()), reverse=True)
        col_d1, col_d2 = st.columns([2, 3])
        with col_d1:
            sel_date = st.selectbox("📆 選擇交易日:", dates_available)
        
        df_day = df_filtered[df_filtered['date'] == sel_date]

        options = [
            f"{r.get('trade_id', '#--')} | {r.get('time_et', '--')} ET | {r.get('direction', '--')} | 結果: {r.get('status', '--')} ({float(r.get('net_r', 0)):+.1f}R) | 評分: {r.get('score', 0)}分" 
            for _, r in df_day.iterrows()
        ]
        
        with col_d2:
            sel_sig_idx = st.selectbox("🎯 選擇該日訊號做功課:", range(len(options)), format_func=lambda x: options[x])

        selected_row = df_day.iloc[sel_sig_idx]

        # ====== 第 3 層：唯一高階互動復盤畫布 ======
        st.caption("🔍 深度技術面復盤畫布 (支援滑鼠滾輪縮放 / 拖拽 / 疊加 1H EMA20 與 RBS/SBR 戰區)：")
        self.render_interactive_replay_chart(selected_row)

        st.markdown(f"""
        <div style="background: #161b22; border-left: 4px solid #58a6ff; padding: 6px 10px; border-radius: 4px; font-size: 12px; font-family: monospace; color: #c9d1d9; margin-bottom: 8px;">
            💡 <b>技術面推理</b>: {selected_row.get('reason', '無備註')} | 開倉: <b>${float(selected_row.get('entry', 0)):,.2f}</b> | 止損: <b>${float(selected_row.get('sl', 0)):,.2f}</b> | 2R止盈: <b>${float(selected_row.get('tp', 0)):,.2f}</b> | 期權: <b>{'N/A (BTC無期權)' if is_btc else '0DTE ATM'}</b>
        </div>
        """, unsafe_allow_html=True)

        self._render_audit_log_box(code, is_btc, m, selected_row)

    def _render_audit_log_box(self, code: str, is_btc: bool, m: dict, selected_row):
        now_my = datetime.datetime.now(tz_my).strftime('%Y-%m-%d %H:%M:%S MYT')
        now_et = datetime.datetime.now(tz_ny).strftime('%H:%M:%S ET')

        log_text = f"=== 癸水 · 策略狀態與執行診斷日誌 (STATUS & AUDIT LOGS) ===\n"
        log_text += f"[1. 系統通信與時間戳憑證]\n"
        log_text += f"• 查詢時間: {now_my} (美東: {now_et})\n"
        log_text += f"• 監控標的: {code} | 0DTE 期權鏈: {'N/A (BTC無期權)' if is_btc else '🟢 QQQ 啟用'}\n"
        log_text += f"\n[2. 策略可行性模型 (Workability Metrics)]\n"
        log_text += f"• 裁定結論: {m['verdict']} | 樣本: {m['total']} 筆 | 勝率: {m['win_rate']:.1f}%\n"
        log_text += f"• 實現盈虧比: 1:{m['rr']:.2f} | 單筆期望值: {m['exp']:+.2f} R/筆\n"
        if selected_row is not None:
            log_text += f"\n[3. 當前選中復盤訂單]\n"
            log_text += f"• 訂單: {selected_row.get('trade_id', '--')} ({selected_row.get('direction', '--')}) | 淨收益: {float(selected_row.get('net_r', 0)):+.1f}R\n"
            log_text += f"• 技術鏈條: {selected_row.get('reason', '--')}\n"
        log_text += f"===========================================================\n"

        st.code(log_text, language="text")
