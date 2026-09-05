# 文件名: chart_plugin.py
# 核心功能: Plotly 无间隙图表 + 顶部实时行情跳动表格 + 德马克趋势线 + 中文容错

import os
import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pytz
import streamlit as st
import yfinance as yf
from moomoo import OpenQuoteContext, RET_OK, KLType, AuType
from trendline_engine import compute_demark_trendlines

tz_ny = pytz.timezone("America/New_York")
DATA_DIR = './market_data'
os.makedirs(DATA_DIR, exist_ok=True)

class ChartPlugin:
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir

    def get_live_data_and_upsert(self, code: str, ktype_name: str) -> pd.DataFrame:
        """获取最新实时数据流并执行安全 Upsert 合并"""
        clean_code = "US_BTC" if "BTC" in code else code.replace('.', '_')
        file_path = os.path.join(self.data_dir, f"{clean_code}_{ktype_name}.csv")
        
        # 1. 读取本地历史底座
        df_base = pd.DataFrame()
        if os.path.exists(file_path):
            try:
                df_base = pd.read_csv(file_path)
                df_base.columns = [c.lower() for c in df_base.columns]
                df_base['time_key'] = pd.to_datetime(df_base['time_key'])
            except Exception as e:
                st.warning(f"⚠️ 读取本地基底 CSV 提示: {e}")

        # 2. 从 OpenD 抓取最新 Live K 线
        df_live = pd.DataFrame()
        try:
            ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
            kl_type = KLType.K_5M if ktype_name == "5M" else (KLType.K_60M if ktype_name == "1Hr" else KLType.K_DAY)
            ret, df_k = ctx.get_cur_kline(code, 20, kl_type, AuType.NONE)
            ctx.close()
            if ret == RET_OK and not df_k.empty:
                df_live = df_k[['time_key', 'open', 'close', 'high', 'low', 'volume']].copy()
                df_live['time_key'] = pd.to_datetime(df_live['time_key'])
        except Exception as e:
            # 捕获异常但不中断，转由备用处理
            pass

        # 3. 执行无冲突 Upsert 去重合并
        if not df_live.empty:
            if not df_base.empty:
                df_merged = pd.concat([df_base, df_live]).drop_duplicates(subset=['time_key'], keep='last')
            else:
                df_merged = df_live
            df_merged = df_merged.sort_values('time_key').reset_index(drop=True)
            # 安全写回磁盘
            df_merged.to_csv(file_path, index=False)
            return df_merged
        
        return df_base

    def render_live_monitor_table(self, df: pd.DataFrame, code: str):
        """在看板顶部渲染实时行情跳动监控表格"""
        if df.empty:
            st.info("⏳ 正在建立实时行情跳动流...")
            return

        last_row = df.iloc[-1]
        prev_row = df.iloc[-2] if len(df) >= 2 else last_row
        
        chg_pts = last_row['close'] - prev_row['close']
        chg_pct = (chg_pts / prev_row['close']) * 100 if prev_row['close'] != 0 else 0.0

        monitor_data = {
            "监控标的": [code],
            "美东时间 (ET)": [str(last_row['time_key'])],
            "最新现价 (Last)": [f"${last_row['close']:,.2f}"],
            "当根最高 (High)": [f"${last_row['high']:,.2f}"],
            "当根最低 (Low)": [f"${last_row['low']:,.2f}"],
            "当根成交量 (Vol)": [f"{int(last_row['volume']):,}"],
            "瞬时涨跌": [f"{chg_pts:+.2f} ({chg_pct:+.2f}%)"]
        }
        df_monitor = pd.DataFrame(monitor_data)
        st.markdown("##### ⚡ 实时行情跳动监控舱 (Live Data Stream)")
        st.dataframe(df_monitor, use_container_width=True, hide_index=True)

    def render_chart(self, code: str, ktype_name: str):
        try:
            df = self.get_live_data_and_upsert(code, ktype_name)
            if df.empty:
                st.warning(f"⚠️ 无法加载 {code} 历史与实时数据，请检查网络或执行同步。")
                return

            # 渲染顶部实时跳动表格
            self.render_live_monitor_table(df, code)

            # 准备画图数据
            df['time_clean'] = df['time_key'].dt.strftime('%m-%d %H:%M') if ktype_name in ['5M', '1Hr'] else df['time_key'].dt.strftime('%Y-%m-%d')
            df['vma20'] = df['volume'].rolling(window=20).mean()
            df['vma_15x'] = df['vma20'] * 1.5
            df['vma_20x'] = df['vma20'] * 2.0

            td_res = compute_demark_trendlines(df, window=4)

            # 绘制双层画布
            df_plot = df.tail(250).copy().reset_index(drop=True)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])

            # 1. 主图 K 线
            fig.add_trace(go.Candlestick(
                x=df_plot['time_clean'], open=df_plot['open'], high=df_plot['high'], low=df_plot['low'], close=df_plot['close'],
                name="K线", increasing_line_color="#089981", decreasing_line_color="#F23645"
            ), row=1, col=1)

            # 2. TD 趋势线
            if td_res.get("resistance_line"):
                res_df = pd.DataFrame(td_res["resistance_line"])
                fig.add_trace(go.Scatter(
                    x=df_plot['time_clean'].iloc[-len(res_df):], y=res_df['value'],
                    mode='lines', line=dict(color='#FF5252', width=2, dash='dash'), name="TD 阻力线"
                ), row=1, col=1)

            if td_res.get("support_line"):
                sup_df = pd.DataFrame(td_res["support_line"])
                fig.add_trace(go.Scatter(
                    x=df_plot['time_clean'].iloc[-len(sup_df):], y=sup_df['value'],
                    mode='lines', line=dict(color='#00E676', width=2, dash='dash'), name="TD 支撑线"
                ), row=1, col=1)

            # 3. 副图 VPA
            bar_colors = ["#089981" if c >= o else "#F23645" for o, c in zip(df_plot['open'], df_plot['close'])]
            fig.add_trace(go.Bar(x=df_plot['time_clean'], y=df_plot['volume'], name="成交量", marker=dict(color=bar_colors)), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_plot['time_clean'], y=df_plot['vma20'], line=dict(color="#ffffff", width=1), name="VMA20"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_plot['time_clean'], y=df_plot['vma_15x'], line=dict(color="#8b949e", width=1, dash="dot"), name="1.5X"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_plot['time_clean'], y=df_plot['vma_20x'], line=dict(color="#ffd700", width=1, dash="dot"), name="2.0X"), row=2, col=1)

            fig.update_xaxes(type='category', rangeslider_visible=False, gridcolor="#161b22")
            fig.update_yaxes(gridcolor="#161b22")
            fig.update_layout(
                height=600, template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                margin=dict(l=10, r=10, t=10, b=10), hovermode="x unified", dragmode="pan"
            )

            st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True, "displayModeBar": True, "displaylogo": False})

        except Exception as e:
            st.error(f"❌ 图表模块运行异常: {str(e)}（请检查网络连接或 OpenD 状态）")
