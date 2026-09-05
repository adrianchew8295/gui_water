# 文件名: chart_plugin.py
# 核心功能: 基於 Plotly 金融時間序列標準架構，自動消除時間軸 Gap + TD 德馬克通道 + VPA 量能副圖

import os
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pytz
import streamlit as st
from moomoo import OpenQuoteContext, RET_OK
from trendline_engine import compute_demark_trendlines, find_td_pivots

tz_ny = pytz.timezone("America/New_York")

class ChartPlugin:
    def __init__(self, data_dir: str = './market_data'):
        self.data_dir = data_dir

    def get_realtime_market_price(self, code: str) -> dict:
        """獲取實時盤口價格快照"""
        res = {"price": None, "status_text": "常規盤"}
        try:
            ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
            ret, df_snap = ctx.get_market_snapshot([code])
            ctx.close()
            if ret == RET_OK and not df_snap.empty:
                row = df_snap.iloc[0]
                res["price"] = float(row['last_price'])
                status = row.get('market_status', '')
                res["status_text"] = f"即時跳動 ({status})" if status else "即時盤口"
        except Exception:
            pass
        return res

    def load_local_data(self, code: str, ktype_name: str) -> pd.DataFrame:
        clean_code = code.replace('.', '_')
        file_path = os.path.join(self.data_dir, f"{clean_code}_{ktype_name}.csv")
        
        if not os.path.exists(file_path):
            st.error(f"❌ 找不到本地數據檔案：`{file_path}`")
            st.info("💡 請先在終端機執行 `python data_fetcher.py` 同步數據。")
            return pd.DataFrame()
            
        try:
            df = pd.read_csv(file_path)
            df.columns = [c.lower() for c in df.columns]
            return df
        except Exception as e:
            st.error(f"❌ 讀取數據異常: {str(e)}")
            return pd.DataFrame()

    def calculate_vpa_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or 'volume' not in df.columns:
            return df
        df['vma20'] = df['volume'].rolling(window=20).mean()
        df['vma_15x'] = df['vma20'] * 1.5
        df['vma_20x'] = df['vma20'] * 2.0
        return df

    def render_chart(self, code: str, ktype_name: str):
        df = self.load_local_data(code, ktype_name)
        if df.empty:
            return

        try:
            time_col = 'time_key' if 'time_key' in df.columns else ('date' if 'date' in df.columns else df.columns[0])
            df['dt_obj'] = pd.to_datetime(df[time_col])
            df = df.sort_values('dt_obj').reset_index(drop=True)
            df['time_str'] = df['dt_obj'].dt.strftime('%Y-%m-%d %H:%M') if ktype_name in ['1Hr', '5M'] else df['dt_obj'].dt.strftime('%Y-%m-%d')
            
            df = self.calculate_vpa_indicators(df)

            # 融合實時現價
            live_info = self.get_realtime_market_price(code)
            if live_info["price"]:
                current_price = live_info["price"]
                price_desc = f"🟢 {live_info['status_text']}: **${current_price:.2f}** (美東時間 ET)"
                df.loc[df.index[-1], 'close'] = current_price
            else:
                current_price = float(df['close'].iloc[-1])
                price_desc = f"📌 美東定格價: **${current_price:.2f}**"

            # 計算 TD 趨勢通道
            td_res = compute_demark_trendlines(df, window=4)
            td_highs, td_lows = find_td_pivots(df, window=4)

            # ---------------- 🎯 50/50 戰術決策面板 ----------------
            st.markdown(f"### 🧭 {code} - {ktype_name} 專業量化走勢 (Plotly 緊湊無間隙引擎)")
            st.markdown(price_desc)

            res_val = td_res.get('curr_res_val') or round(current_price * 1.01, 2)
            sup_val = td_res.get('curr_sup_val') or round(current_price * 0.99, 2)
            channel_h = abs(res_val - sup_val)

            t1 = td_res.get('bull_target_1') or round(res_val + channel_h * 0.618, 2)
            t2 = td_res.get('bull_target_2') or round(res_val + channel_h * 1.0, 2)
            b1 = td_res.get('bear_target_1') or round(sup_val - channel_h * 0.618, 2)
            b2 = td_res.get('bear_target_2') or round(sup_val - channel_h * 1.0, 2)

            w_left, w_right = st.columns(2)
            with w_left:
                st.success("🟢 **多頭向上推演 (Bullish 50%)**")
                st.markdown(f"- **突破點**：`${res_val:.2f}` | **Target 1**: `${t1:.2f}` | **Target 2**: `${t2:.2f}`")
            with w_right:
                st.error("🔴 **空頭向下推演 (Bearish 50%)**")
                st.markdown(f"- **破位點**：`${sup_val:.2f}` | **Target 1**: `${b1:.2f}` | **Target 2**: `${b2:.2f}`")

            st.divider()

            # ---------------- Plotly 雙層畫布架構 ----------------
            fig = make_subplots(
                rows=2, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.03, 
                row_heights=[0.75, 0.25]
            )

            # 1. 主圖：K 線
            fig.add_trace(go.Candlestick(
                x=df['time_str'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name="K線",
                increasing_line_color="#089981",
                decreasing_line_color="#F23645"
            ), row=1, col=1)

            # 2. TD 阻力線與支撐線
            if td_res.get("resistance_line"):
                res_df = pd.DataFrame(td_res["resistance_line"])
                fig.add_trace(go.Scatter(
                    x=df['time_str'].iloc[-len(res_df):],
                    y=res_df['value'],
                    mode='lines',
                    line=dict(color='#FF5252', width=2, dash='dash'),
                    name="TD 阻力線"
                ), row=1, col=1)

            if td_res.get("support_line"):
                sup_df = pd.DataFrame(td_res["support_line"])
                fig.add_trace(go.Scatter(
                    x=df['time_str'].iloc[-len(sup_df):],
                    y=sup_df['value'],
                    mode='lines',
                    line=dict(color='#00E676', width=2, dash='dash'),
                    name="TD 支撐線"
                ), row=1, col=1)

            # 3. 副圖：VPA 量能柱與均量線
            bar_colors = ["#089981" if c >= o else "#F23645" for o, c in zip(df['open'], df['close'])]
            fig.add_trace(go.Bar(
                x=df['time_str'],
                y=df['volume'],
                name="成交量",
                marker=dict(color=bar_colors)
            ), row=2, col=1)

            if 'vma20' in df.columns:
                fig.add_trace(go.Scatter(x=df['time_str'], y=df['vma20'], line=dict(color="#ffffff", width=1), name="VMA20"), row=2, col=1)
                fig.add_trace(go.Scatter(x=df['time_str'], y=df['vma_15x'], line=dict(color="#8b949e", width=1, dash="dot"), name="1.5X 警戒"), row=2, col=1)
                fig.add_trace(go.Scatter(x=df['time_str'], y=df['vma_20x'], line=dict(color="#ffd700", width=1, dash="dot"), name="2.0X 異動"), row=2, col=1)

            # 核心關鍵：將 X 軸設為 'category' 類型，完全消除夜間與週末休市的大片空白 (Gap)
            fig.update_xaxes(type='category', rangeslider_visible=False, gridcolor="#161b22")
            fig.update_yaxes(gridcolor="#161b22")

            fig.update_layout(
                height=650,
                template="plotly_dark",
                paper_bgcolor="#0d1117",
                plot_bgcolor="#0d1117",
                margin=dict(l=10, r=10, t=10, b=10),
                hovermode="x unified",
                dragmode="pan"
            )

            # 渲染圖表 (開啟滑鼠滾輪縮放)
            st.plotly_chart(
                fig, 
                use_container_width=True, 
                config={"scrollZoom": True, "displayModeBar": True, "displaylogo": False}
            )

        except Exception as e:
            st.error(f"❌ 圖表渲染失敗: {str(e)}")
