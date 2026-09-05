# 文件名: chart_plugin.py
# 核心功能: 5M 專業實戰圖表 (Plotly 無間隙排布 + PMH/PML 水平位 + VPA 均量副圖)

import os
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pytz
import streamlit as st
from moomoo import OpenQuoteContext, RET_OK
from trendline_engine import compute_demark_trendlines

tz_ny = pytz.timezone("America/New_York")

class ChartPlugin:
    def __init__(self, data_dir: str = './market_data'):
        self.data_dir = data_dir

    def get_realtime_market_price(self, code: str) -> dict:
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
            st.info("💡 請先在終端機執行 `python data_fetcher.py` 同步 5M 數據。")
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

    def calculate_pm_levels(self, df: pd.DataFrame):
        """提取今日盤前極值 (PMH 04:00-09:30) 與昨日極值 (PDH/PDL)"""
        levels = {"pmh": None, "pml": None, "pdh": None, "pdl": None}
        if df.empty:
            return levels
        
        df['date'] = df['dt_obj'].dt.date
        unique_dates = sorted(df['date'].unique())
        
        if len(unique_dates) >= 2:
            prev_date = unique_dates[-2]
            prev_day_df = df[df['date'] == prev_date]
            levels["pdh"] = round(float(prev_day_df['high'].max()), 2)
            levels["pdl"] = round(float(prev_day_df['low'].min()), 2)

        curr_date = unique_dates[-1]
        today_df = df[df['date'] == curr_date]
        
        # 盤前區間: 04:00 ~ 09:30
        pm_df = today_df[(today_df['dt_obj'].dt.hour >= 4) & 
                         ((today_df['dt_obj'].dt.hour < 9) | ((today_df['dt_obj'].dt.hour == 9) & (today_df['dt_obj'].dt.minute <= 30)))]
        
        if not pm_df.empty:
            levels["pmh"] = round(float(pm_df['high'].max()), 2)
            levels["pml"] = round(float(pm_df['low'].min()), 2)
            
        return levels

    def render_chart(self, code: str, ktype_name: str):
        df = self.load_local_data(code, ktype_name)
        if df.empty:
            return

        try:
            time_col = 'time_key' if 'time_key' in df.columns else df.columns[0]
            df['dt_obj'] = pd.to_datetime(df[time_col])
            df = df.sort_values('dt_obj').reset_index(drop=True)
            df['time_str'] = df['dt_obj'].dt.strftime('%m-%d %H:%M')
            
            df = self.calculate_vpa_indicators(df)
            levels = self.calculate_pm_levels(df)

            live_info = self.get_realtime_market_price(code)
            current_price = live_info["price"] or float(df['close'].iloc[-1])

            # ---------------- 🎯 5M 盤前/盤中戰略關鍵位 HUD ----------------
            st.markdown(f"### ⚡ {code} - 5分鐘 (5M) 即時戰區看板 (美東時間 ET)")
            st.markdown(f"🟢 即時盤口現價: **${current_price:.2f}**")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🌅 盤前最高 (PMH)", f"${levels['pmh']}" if levels['pmh'] else "計算中")
            c2.metric("🌅 盤前最低 (PML)", f"${levels['pml']}" if levels['pml'] else "計算中")
            c3.metric("📅 昨日最高 (PDH)", f"${levels['pdh']}" if levels['pdh'] else "計算中")
            c4.metric("📅 昨日最低 (PDL)", f"${levels['pdl']}" if levels['pdl'] else "計算中")

            st.divider()

            # 只渲染最近 300 根 5M 柱子，保證圖表響應極速
            df_plot = df.tail(300).copy().reset_index(drop=True)

            fig = make_subplots(
                rows=2, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.03, 
                row_heights=[0.75, 0.25]
            )

            # 主圖：5M K 線
            fig.add_trace(go.Candlestick(
                x=df_plot['time_str'],
                open=df_plot['open'],
                high=df_plot['high'],
                low=df_plot['low'],
                close=df_plot['close'],
                name="5M K線",
                increasing_line_color="#089981",
                decreasing_line_color="#F23645"
            ), row=1, col=1)

            # 疊加 PMH / PML 水平線
            if levels["pmh"]:
                fig.add_hline(y=levels["pmh"], line=dict(color="#FFD700", width=1.5, dash="dash"), annotation_text="PMH (盤前高)", row=1, col=1)
            if levels["pml"]:
                fig.add_hline(y=levels["pml"], line=dict(color="#00E5FF", width=1.5, dash="dash"), annotation_text="PML (盤前低)", row=1, col=1)

            # 副圖：VPA 量能
            bar_colors = ["#089981" if c >= o else "#F23645" for o, c in zip(df_plot['open'], df_plot['close'])]
            fig.add_trace(go.Bar(
                x=df_plot['time_str'],
                y=df_plot['volume'],
                name="5M 成交量",
                marker=dict(color=bar_colors)
            ), row=2, col=1)

            fig.add_trace(go.Scatter(x=df_plot['time_str'], y=df_plot['vma20'], line=dict(color="#ffffff", width=1), name="VMA20"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_plot['time_str'], y=df_plot['vma_15x'], line=dict(color="#8b949e", width=1, dash="dot"), name="1.5X 警戒"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_plot['time_str'], y=df_plot['vma_20x'], line=dict(color="#ffd700", width=1, dash="dot"), name="2.0X 巨量"), row=2, col=1)

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

            st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True, "displayModeBar": True, "displaylogo": False})

        except Exception as e:
            st.error(f"❌ 5M 圖表渲染失敗: {str(e)}")
