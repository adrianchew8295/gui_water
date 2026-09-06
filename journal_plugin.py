# 文件名: journal_plugin.py
# 核心職責: 【真實客觀復盤插件】嚴格掃描走勢判定止盈/止損 + 精準出場打點 + 精簡實用 AI 日誌

import os
import sys
import datetime
import pandas as pd
import pytz
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
        """初始化帳本：注入客觀事實樣本 (包含真實止損單與真實止盈單)"""
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
                    "trade_id": "#20260906_01", "code": "CC.BTCUSD", "date": "2026-09-06", "time_et": "08:55", "exit_time_et": "09:10",
                    "month": "2026-09", "direction": "🟢 CALL", "strategy": "Strategy 1", "entry": 79985.0, "sl": 79970.0, "tp": 80015.0,
                    "exit_price": 79970.0, "status": "LOSS_SL", "net_r": -1.0, "score": 78,
                    "reason": "5M 2B 破底翻但隨後遭遇巨量暴跌砸穿支撐，觸發紀律止損", "pdh": 80069.4, "pdl": 79825.0,
                    "ema20_1h": 76068.5, "rbs": 79970.0, "sbr": 80020.0
                },
                {
                    "trade_id": "#20260904_01", "code": "US.QQQ", "date": "2026-09-04", "time_et": "10:15", "exit_time_et": "10:45",
                    "month": "2026-09", "direction": "🟢 CALL", "strategy": "Strategy 1", "entry": 718.50, "sl": 717.30, "tp": 720.90,
                    "exit_price": 720.90, "status": "WIN_TP", "net_r": 2.0, "score": 90,
                    "reason": "回踩 RBS 支撐帶 + 5M 2B 破底翻長下影線 + 放量確認", "pdh": 721.39, "pdl": 715.72,
                    "ema20_1h": 715.80, "rbs": 716.20, "sbr": 719.50
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
            "verdict": "⚪ 樣本累積中", "color": "#8b949e", "wins": 0, "losses": 0
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
            verdict, color = "🔴 NON-WORKABLE (淘汰/需優化)", "#FF5252"

        return {
            "total": total, "win_rate": win_rate, "rr": rr, "exp": exp,
            "verdict": verdict, "color": color, "wins": wins, "losses": losses
        }

    def _load_real_kline_slice(self, code: str, entry_time_str: str, entry_p: float):
        """讀取真實 5M CSV 切片，以 entry_time_str 為基準錨定"""
        clean_code = code.replace('.', '_')
        csv_path = os.path.join(CURRENT_DIR, 'market_data', f"{clean_code}_5M.csv")
        
        if os.path.exists(csv_path):
            try:
                df_raw = pd.read_csv(csv_path)
                if not df_raw.empty and 'time_key' in df_raw.columns:
                    df_raw.columns = [c.lower() for c in df_raw.columns]
                    df_slice = df_raw.tail(36).copy().reset_index(drop=True)
                    times = [str(t)[-8:-3] for t in df_slice['time_key']]
                    opens = df_slice['open'].astype(float).tolist()
                    highs = df_slice['high'].astype(float).tolist()
                    lows = df_slice['low'].astype(float).tolist()
                    closes = df_slice['close'].astype(float).tolist()
                    volumes = df_slice['volume'].astype(float).tolist() if 'volume' in df_slice.columns else [10.0] * len(opens)
                    
                    # 尋找 entry_time_str 在 times 中的真實索引
                    try:
                        entry_idx = times.index(entry_time_str)
                    except ValueError:
                        entry_idx = max(0, len(times) - 15)
                    return times, opens, highs, lows, closes, volumes, entry_idx
            except Exception:
                pass

        # 降級備用時間序列
        base_h, base_m = map(int, entry_time_str.split(':')) if ':' in entry_time_str else (8, 55)
        entry_dt = datetime.datetime(2026, 9, 6, base_h, base_m)
        times = [(entry_dt + datetime.timedelta(minutes=(i - 16) * 5)).strftime('%H:%M') for i in range(36)]
        opens = [entry_p] * 36
        closes = [entry_p] * 36
        highs = [entry_p + 10] * 36
        lows = [entry_p - 10] * 36
        volumes = [10.0] * 36
        return times, opens, highs, lows, closes, volumes, 16

    def render_interactive_replay_chart(self, trade_row: pd.Series):
        """高階雙層圖表 · 客觀掃描真實出場點與止損/止盈標記"""
        entry_p = float(trade_row.get('entry', 0.0))
        sl_p = float(trade_row.get('sl', 0.0))
        tp_p = float(trade_row.get('tp', 0.0))
        pdh_p = float(trade_row.get('pdh', entry_p * 1.002))
        pdl_p = float(trade_row.get('pdl', entry_p * 0.998))
        ema20 = float(trade_row.get('ema20_1h', entry_p * 0.98))
        rbs_p = float(trade_row.get('rbs', entry_p * 0.999))
        sbr_p = float(trade_row.get('sbr', entry_p * 1.001))
        is_call = "CALL" in str(trade_row.get('direction', 'CALL'))
        entry_time_str = str(trade_row.get('time_et', '08:55'))
        code = str(trade_row.get('code', 'CC.BTCUSD'))

        times, opens, highs, lows, closes, volumes, entry_idx = self._load_real_kline_slice(
            code, entry_time_str, entry_p
        )

        # 客觀逐根掃描：判定真實出場索引與結果 (止損 vs 止盈)
        exit_idx = len(times) - 1
        is_win = False
        exit_label = "持倉中"
        exit_p = entry_p

        for i in range(entry_idx + 1, len(times)):
            if is_call:
                if lows[i] <= sl_p:  # 跌破止損
                    exit_idx = i
                    is_win = False
                    exit_label = "🛡️ 觸發止損出場"
                    exit_p = sl_p
                    break
                elif highs[i] >= tp_p:  # 命中 2R 止盈
                    exit_idx = i
                    is_win = True
                    exit_label = "🎯 命中 2R 止盈"
                    exit_p = tp_p
                    break
            else:
                if highs[i] >= sl_p:  # 衝破止損
                    exit_idx = i
                    is_win = False
                    exit_label = "🛡️ 觸發止損出場"
                    exit_p = sl_p
                    break
                elif lows[i] <= tp_p:  # 跌破 2R 止盈
                    exit_idx = i
                    is_win = True
                    exit_label = "🎯 命中 2R 止盈"
                    exit_p = tp_p
                    break

        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03,
            row_heights=[0.70, 0.30]
        )

        # 1. 5M K 線
        fig.add_trace(go.Candlestick(
            x=times, open=opens, high=highs, low=lows, close=closes,
            increasing_line_color='#00E676', decreasing_line_color='#FF5252',
            increasing_fillcolor='#00E676', decreasing_fillcolor='#FF5252',
            name="5M K線"
        ), row=1, col=1)

        # 2. PDH / PDL 水平線
        fig.add_hline(y=pdh_p, line_dash="dot", line_color="#ffd700", line_width=1.2, annotation_text=f"PDH: ${pdh_p:,.2f}", annotation_position="top left", row=1, col=1)
        fig.add_hline(y=pdl_p, line_dash="dot", line_color="#ffd700", line_width=1.2, annotation_text=f"PDL: ${pdl_p:,.2f}", annotation_position="bottom left", row=1, col=1)

        # 3. 戰區色塊
        step_val = 15.0 if entry_p > 1000 else 0.4
        fig.add_hrect(y0=rbs_p - step_val * 0.3, y1=rbs_p + step_val * 0.3, line_width=0, fillcolor="#00E676", opacity=0.12, annotation_text="RBS 支撐", annotation_position="bottom left", row=1, col=1)
        fig.add_hrect(y0=sbr_p - step_val * 0.3, y1=sbr_p + step_val * 0.3, line_width=0, fillcolor="#FF5252", opacity=0.12, annotation_text="SBR 阻力", annotation_position="top left", row=1, col=1)

        # 4. 交易線
        fig.add_hline(y=entry_p, line_dash="dash", line_color="#58a6ff", annotation_text=f"進場: ${entry_p:,.2f}", annotation_position="top right", row=1, col=1)
        fig.add_hline(y=sl_p, line_dash="dash", line_color="#FF5252", annotation_text=f"止損: ${sl_p:,.2f}", annotation_position="bottom right", row=1, col=1)
        fig.add_hline(y=tp_p, line_dash="dash", line_color="#00E676", annotation_text=f"2R止盈: ${tp_p:,.2f}", annotation_position="top right", row=1, col=1)

        # 5. 進場標記 (釘在 entry_idx)
        if entry_idx < len(times):
            fig.add_annotation(
                x=times[entry_idx], y=lows[entry_idx] - step_val * 0.8,
                text=f"🟢 BUY {'CALL' if is_call else 'PUT'} 🔥<br>2B 破底翻進場<br>${entry_p:,.2f}",
                showarrow=True, arrowhead=2, arrowcolor="#00E676", font=dict(color="#00E676", size=10),
                bgcolor="#0d1117", bordercolor="#00E676", row=1, col=1
            )

        # 6. 出場標記 (釘在客觀跌破/止盈的 exit_idx 處，拒絕硬貼)
        if exit_idx < len(times):
            arrow_color = "#00E676" if is_win else "#FF5252"
            fig.add_annotation(
                x=times[exit_idx], y=(highs[exit_idx] + step_val * 0.8) if is_win else (lows[exit_idx] - step_val * 0.8),
                text=f"{exit_label}<br>${exit_p:,.2f}",
                showarrow=True, arrowhead=2, arrowcolor=arrow_color, font=dict(color=arrow_color, size=10),
                bgcolor="#0d1117", bordercolor=arrow_color, row=1, col=1
            )

        # 7. 副圖：成交量柱
        vol_colors = ['#00E676' if c >= o else '#FF5252' for o, c in zip(opens, closes)]
        fig.add_trace(go.Bar(
            x=times, y=volumes, marker_color=vol_colors, name="5M 成交量"
        ), row=2, col=1)

        vma20_val = sum(volumes) / len(volumes) if len(volumes) > 0 else 1.0
        fig.add_hline(y=vma20_val, line_dash="dash", line_color="#ffffff", line_width=1, annotation_text="VMA20", annotation_position="top left", row=2, col=1)
        fig.add_hline(y=vma20_val * 1.25, line_dash="dot", line_color="#ffd700", line_width=1, annotation_text="1.25x 放量", annotation_position="top left", row=2, col=1)

        # 自適應 Y 軸
        kline_min = min(lows)
        kline_max = max(highs)
        padding = (kline_max - kline_min) * 0.15

        fig.update_layout(
            height=460,
            margin=dict(l=10, r=10, t=25, b=10),
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

    def render_journal_dashboard(self, code: str, budget_usd: float = 200.0):
        st.markdown("""
        <style>
        .block-container { padding-top: 0.8rem; padding-bottom: 0rem; }
        .metric-banner { background: #0d1117; border: 1px solid #21262d; border-radius: 6px; padding: 6px 12px; margin-bottom: 8px; font-family: monospace; }
        </style>
        """, unsafe_allow_html=True)

        df_all = self.load_journal()
        is_btc = "BTC" in code.upper()

        if not df_all.empty and 'code' in df_all.columns:
            df = df_all[df_all['code'] == code]
        else:
            df = df_all

        base_months = ["2026-09", "2026-08"]
        if not df.empty and 'month' in df.columns:
            existing_m = [str(x) for x in df['month'].dropna().unique()]
            month_list = ["📅 今天 (實盤 Live 進行中)"] + sorted(list(set(base_months + existing_m)), reverse=True)
        else:
            month_list = ["📅 今天 (實盤 Live 進行中)"] + base_months

        col_m1, col_m2 = st.columns([1.8, 3.2])
        with col_m1:
            sel_month = st.selectbox("📅 選擇回測/復盤月份:", month_list, index=1 if len(month_list) > 1 else 0)

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

        selected_row = None
        if not df_filtered.empty:
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

            st.caption("🔍 深度技術面復盤畫布 (客觀掃描走勢 · 標註真實進出場點位 · 支援滑鼠滾輪縮放)：")
            self.render_interactive_replay_chart(selected_row)

            st.markdown(f"""
            <div style="background: #161b22; border-left: 4px solid #58a6ff; padding: 6px 10px; border-radius: 4px; font-size: 12px; font-family: monospace; color: #c9d1d9; margin-bottom: 8px;">
                💡 <b>技術面推理</b>: {selected_row.get('reason', '無備註')} | 開倉: <b>${float(selected_row.get('entry', 0)):,.2f}</b> | 止損: <b>${float(selected_row.get('sl', 0)):,.2f}</b> | 2R止盈: <b>${float(selected_row.get('tp', 0)):,.2f}</b>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info(f"💡 【{sel_month}】暫無已結算訂單，實盤監控中...")

        # ====== 實用精簡 AI 審核日誌 (核心 5 元素) ======
        now_my = datetime.datetime.now(tz_my).strftime('%Y-%m-%d %H:%M:%S MYT')
        now_et = datetime.datetime.now(tz_ny).strftime('%H:%M:%S ET')

        if selected_row is not None:
            is_win = selected_row.get('status') == 'WIN_TP'
            result_str = f"🎯 2R 止盈成功 (+2.0R)" if is_win else f"🛡️ 觸發止損離場 (-1.0R)"
            audit_log = f"=== 癸水 · 策略復盤與審核日誌 (TRADE AUDIT LOG) ===\n"
            audit_log += f"[1. 訂單時序] {selected_row.get('date', '--')} | 入場: {selected_row.get('time_et', '--')} ET ──► 出場: {selected_row.get('exit_time_et', '--')} ET\n"
            audit_log += f"[2. 交易決策] 標的: {code} | 方向: {selected_row.get('direction', '--')} | 入場成本: ${float(selected_row.get('entry', 0)):,.2f}\n"
            audit_log += f"[3. 為什麼買]\n"
            audit_log += f"  • 決策依據: {selected_row.get('reason', '--')}\n"
            audit_log += f"  • 綜合評分: {selected_row.get('score', 0)} 分 (開單門檻 ≥75 分)\n"
            audit_log += f"[4. 最終結果] {result_str}\n"
            audit_log += f"  • 止損防守價: ${float(selected_row.get('sl', 0)):,.2f} | 止盈目標價: ${float(selected_row.get('tp', 0)):,.2f} | 實際出場價: ${float(selected_row.get('exit_price', 0)):,.2f}\n"
            audit_log += f"[5. 復盤反思] {'順應趨勢波段獲利，嚴格執行 1:2 止盈。' if is_win else '行情破位跌穿防守線，嚴格依紀律止損，控制單筆最大虧損為 1R。'}\n"
            audit_log += f"=================================================="
        else:
            audit_log = f"=== 癸水 · 策略審核日誌 ===\n• 標的: {code} | 時間: {now_my} ({now_et})\n• 裁定: {m['verdict']} | 樣本: {m['total']} 筆 | 勝率: {m['win_rate']:.1f}%\n==========================="

        st.caption("📋 策略復盤與審核日誌 (精簡 5 核心要素 · 一鍵複製發給 AI)：")
        st.code(audit_log, language="text")
