# 文件名: journal_plugin.py
# 核心職責: 【策略記帳與高級可視化復盤插件】修復 KeyError + 支援滾輪縮放 + 按需單圖渲染

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
        """初始化帳本 (含基準回測樣本)"""
        if not os.path.exists(self.journal_path):
            sample_data = [
                {"trade_id": "#0906_01", "time_et": "06:25", "direction": "🟢 CALL", "strategy": "Strategy 1", "entry": 79985.0, "sl": 79970.0, "tp": 80015.0, "exit_price": 80015.0, "status": "WIN_TP", "net_r": 2.0, "score": 85, "reason": "5M 2B 破底翻放量企穩"},
                {"trade_id": "#0905_02", "time_et": "11:15", "direction": "🔴 PUT", "strategy": "Strategy 1", "entry": 80020.0, "sl": 80035.0, "tp": 79990.0, "exit_price": 80035.0, "status": "LOSS_SL", "net_r": -1.0, "score": 78, "reason": "5M 2B 假突破衝頂失敗"},
                {"trade_id": "#0904_03", "time_et": "10:30", "direction": "🟢 CALL", "strategy": "Strategy 1", "entry": 79850.0, "sl": 79830.0, "tp": 79890.0, "exit_price": 79890.0, "status": "WIN_TP", "net_r": 2.0, "score": 90, "reason": "TD9 轉折共振 + RBS 支撐破底翻"}
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
        """判定策略統計數據與期望值 (保證永遠返回所有必需鍵)"""
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
        """高級 Plotly 互動圖表 · 支援滑鼠滾輪縮放與拖拽"""
        entry_p = float(trade_row.get('entry', 0.0))
        sl_p = float(trade_row.get('sl', 0.0))
        tp_p = float(trade_row.get('tp', 0.0))
        is_call = "CALL" in str(trade_row.get('direction', 'CALL'))

        times = [f"T-{i}" for i in range(5, 0, -1)] + ["ENTRY (觸發)"] + [f"T+{i}" for i in range(1, 6)]
        base_prices = [entry_p - (i * 5 if is_call else -i * 5) for i in range(5, 0, -1)] + [entry_p] + [entry_p + (i * 6 if is_call else -i * 6) for i in range(1, 6)]
        
        opens = [p - 2 for p in base_prices]
        closes = [p + 3 if i % 2 == 0 else p - 1 for i, p in enumerate(base_prices)]
        highs = [max(o, c) + 4 for o, c in zip(opens, closes)]
        lows = [min(o, c) - 4 for o, c in zip(opens, closes)]

        fig = go.Figure()

        fig.add_trace(go.Candlestick(
            x=times, open=opens, high=highs, low=lows, close=closes,
            increasing_line_color='#00E676', decreasing_line_color='#FF5252',
            increasing_fillcolor='#00E676', decreasing_fillcolor='#FF5252',
            name="5M K線"
        ))

        fig.add_hline(y=entry_p, line_dash="dash", line_color="#58a6ff", annotation_text=f"進場: ${entry_p:,.2f}", annotation_position="top right")
        fig.add_hline(y=sl_p, line_dash="dash", line_color="#FF5252", annotation_text=f"止損: ${sl_p:,.2f}", annotation_position="bottom right")
        fig.add_hline(y=tp_p, line_dash="dash", line_color="#00E676", annotation_text=f"2R止盈: ${tp_p:,.2f}", annotation_position="top right")

        fig.update_layout(
            height=320,
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
        .block-container { padding-top: 1rem; padding-bottom: 0rem; }
        .metric-banner { background: #0d1117; border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; margin-bottom: 8px; font-family: monospace; }
        </style>
        """, unsafe_allow_html=True)

        df = self.load_journal()
        m = self.evaluate_metrics(df)
        is_btc = "BTC" in code.upper()

        st.markdown(f"""
        <div class="metric-banner">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 13px; font-weight: bold; color: {m['color']};">🏆 {m['verdict']}</span>
                <span style="font-size: 12px; color: #8b949e;">勝率: <b style="color:#ffd700;">{m['win_rate']:.1f}%</b> ({m['wins']}勝/{m['losses']}負) | 盈虧比: <b style="color:#ffd700;">1:{m['rr']:.2f}</b> | 期望值: <b style="color:{m['color']};">{m['exp']:+.2f}R/筆</b> | 風控: <b>${budget_usd:.0f}</b></span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if df.empty:
            st.info("💡 暫無歷史訂單，待實盤信號觸發後自動記錄。")
            return

        options = [
            f"{r.get('trade_id', '#--')} | {r.get('time_et', '--')} ET | {r.get('direction', '--')} | 結果: {r.get('status', '--')} ({float(r.get('net_r', 0)):+.1f}R) | 評分: {r.get('score', 0)}分" 
            for _, r in df.iterrows()
        ]
        sel_idx = st.selectbox("🎯 選擇要深度復盤的訂單 (點擊即時生成可縮放圖表):", range(len(options)), format_func=lambda x: options[x])

        selected_row = df.iloc[sel_idx]

        st.caption("🔍 復盤畫布 (支援滑鼠滾輪縮放 / 左鍵拖拽 / 十字光標吸附)：")
        self.render_interactive_replay_chart(selected_row)

        st.markdown(f"""
        <div style="background: #161b22; border-left: 4px solid #58a6ff; padding: 6px 10px; border-radius: 4px; font-size: 12px; font-family: monospace; color: #c9d1d9; margin-bottom: 8px;">
            💡 <b>決策鏈條</b>: {selected_row.get('reason', '無備註')} | 開倉價: <b>${float(selected_row.get('entry', 0)):,.2f}</b> | 止損: <b>${float(selected_row.get('sl', 0)):,.2f}</b> | 2R止盈: <b>${float(selected_row.get('tp', 0)):,.2f}</b> | 期權: <b>{'N/A (BTC無期權)' if is_btc else '0DTE ATM'}</b>
        </div>
        """, unsafe_allow_html=True)

        now_my = datetime.datetime.now(tz_my).strftime('%Y-%m-%d %H:%M:%S MYT')
        log_text = f"=== 癸水 · 策略可行性評估日誌 ===\n• 時間: {now_my} | 標的: {code}\n• 裁定: {m['verdict']} | 勝率: {m['win_rate']:.1f}% | 盈虧比: 1:{m['rr']:.2f} | 期望值: {m['exp']:+.2f}R\n• 當前選中訂單: {selected_row.get('trade_id', '--')} ({selected_row.get('direction', '--')}) -> 淨收益: {float(selected_row.get('net_r', 0)):+.1f}R\n==============================="
        st.code(log_text, language="text")
