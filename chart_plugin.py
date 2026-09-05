# 文件名: chart_renderer.py
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from trendline_engine import compute_demark_trendlines, find_td_pivots

def render_dual_chart(df_5m: pd.DataFrame, params: dict, trades: list = None, dt_10pm=None, title_text: str = "5M 走势与 TD 趋势通道深度复盘"):
    if df_5m is None or df_5m.empty:
        st.warning("⚠️ 暂无 5M K 线数据可供绘制。")
        return

    # 建立主圖 (K 線 + TD 趨勢線) 與副圖 (成交量 VPA)
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25]
    )

    # 1. 繪製 K 線
    fig.add_trace(
        go.Candlestick(
            x=df_5m.index,
            open=df_5m['Open'],
            high=df_5m['High'],
            low=df_5m['Low'],
            close=df_5m['Close'],
            name="QQQ 5M",
            increasing_line_color='#089981',
            decreasing_line_color='#F23645'
        ),
        row=1, col=1
    )

    # 2. 計算並繪製德馬克趨勢射線 (TD Lines)
    td_data = compute_demark_trendlines(df_5m, window=4)
    if td_data and td_data.get("status") == "success":
        # 阻力射線 (紅/橙色虛線)
        res = td_data.get("resistance")
        if res:
            fig.add_trace(
                go.Scatter(
                    x=[res["p1"]["timestamp"], res["p2"]["timestamp"], res["ext_timestamp"]],
                    y=[res["p1"]["price"], res["p2"]["price"], res["ext_price"]],
                    mode="lines+markers",
                    line=dict(color="#FF5722", width=2, dash="dash"),
                    marker=dict(size=6, symbol="triangle-down"),
                    name=f"TD 阻力線 (${res['ext_price']:.2f})"
                ),
                row=1, col=1
            )

        # 支撐射線 (綠色虛線)
        sup = td_data.get("support")
        if sup:
            fig.add_trace(
                go.Scatter(
                    x=[sup["p1"]["timestamp"], sup["p2"]["timestamp"], sup["ext_timestamp"]],
                    y=[sup["p1"]["price"], sup["p2"]["price"], sup["ext_price"]],
                    mode="lines+markers",
                    line=dict(color="#00E676", width=2, dash="dash"),
                    marker=dict(size=6, symbol="triangle-up"),
                    name=f"TD 支撐線 (${sup['ext_price']:.2f})"
                ),
                row=1, col=1
            )

    # 3. 繪製 1H 戰區關鍵水平線 (SBR / RBS / PDH / PDL)
    if params:
        if "SBR_TOP" in params:
            fig.add_hrect(y0=params["SBR_BOT"], y1=params["SBR_TOP"], fillcolor="rgba(244, 67, 54, 0.15)", line_width=0, row=1, col=1, annotation_text="1H SBR 阻力战区", annotation_position="top left")
        if "RBS_TOP" in params:
            fig.add_hrect(y0=params["RBS_BOT"], y1=params["RBS_TOP"], fillcolor="rgba(76, 175, 80, 0.15)", line_width=0, row=1, col=1, annotation_text="1H RBS 支撑战区", annotation_position="bottom left")
        if "PDH" in params:
            fig.add_hline(y=params["PDH"], line=dict(color="#E2E8F0", width=1, dash="dot"), row=1, col=1, annotation_text="PDH")
        if "PDL" in params:
            fig.add_hline(y=params["PDL"], line=dict(color="#94A3B8", width=1, dash="dot"), row=1, col=1, annotation_text="PDL")

    # 4. 繪製成交量 VPA (副圖)
    vol_col = 'Volume' if 'Volume' in df_5m.columns else ('vol' if 'vol' in df_5m.columns else None)
    if vol_col:
        colors = ['#089981' if c >= o else '#F23645' for o, c in zip(df_5m['Open'], df_5m['Close'])]
        fig.add_trace(
            go.Bar(x=df_5m.index, y=df_5m[vol_col], marker_color=colors, name="成交量"),
            row=2, col=1
        )

    # 圖表樣式配置
    fig.update_layout(
        title=title_text,
        template="plotly_dark",
        height=620,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    st.plotly_chart(fig, use_container_width=True)
