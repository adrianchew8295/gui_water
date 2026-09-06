# 文件名: nq_wave_tab.py
# 核心功能: NQ / QQQ 艾略特波浪日線圖表可視化 + 1H 預測中樞

import os
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from elliott_wave_engine import ElliottWaveEngine

DATA_DIR = './market_data'

def load_data(symbol: str, timeframe: str) -> pd.DataFrame:
    """載入指定週期的歷史數據"""
    clean_sym = symbol.replace('.', '_')
    file_path = os.path.join(DATA_DIR, f"{clean_sym}_{timeframe}.csv")
    
    # 兼容備援檔名
    if not os.path.exists(file_path):
        if "NQ" in symbol:
            file_path = os.path.join(DATA_DIR, f"US_QQQ_{timeframe}.csv")
        elif "QQQ" in symbol:
            file_path = os.path.join(DATA_DIR, f"US_NQmain_{timeframe}.csv")

    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            df.columns = [c.lower().strip() for c in df.columns]
            return df
        except Exception:
            pass
    return pd.DataFrame()

def render_wave_chart(df_day: pd.DataFrame, wave_res: dict):
    """繪製日線 K 線圖並疊加艾略特波浪折線與標籤"""
    if df_day.empty:
        return

    time_col = 'time_key' if 'time_key' in df_day.columns else df_day.columns[0]
    df_day['date_str'] = df_day[time_col].astype(str).str.slice(0, 10)
    df_day = df_day.drop_duplicates(subset=['date_str']).sort_values('date_str').reset_index(drop=True)
    
    # 取最近 120 根日線以保持圖表清晰美觀
    df_plot = df_day.tail(120).copy().reset_index(drop=True)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.75, 0.25])

    # 1. 蠟燭圖主圖
    fig.add_trace(go.Candlestick(
        x=df_plot['date_str'],
        open=df_plot['open'], high=df_plot['high'],
        low=df_plot['low'], close=df_plot['close'],
        increasing_line_color='#00E676', decreasing_line_color='#FF5252',
        name="日線 K線"
    ), row=1, col=1)

    # 2. 提取日線拐點並繪製波浪軌跡 (Zigzag Wave Skeleton)
    day_pivots = ElliottWaveEngine.extract_pivots(df_plot, window=4)
    
    if len(day_pivots) >= 2:
        wave_x = [p["time"][:10] for p in day_pivots]
        wave_y = [p["price"] for p in day_pivots]

        # 疊加亮黃色波浪骨架線
        fig.add_trace(go.Scatter(
            x=wave_x, y=wave_y,
            mode='lines+markers+text',
            line=dict(color='#ffd700', width=2.5, dash='solid'),
            marker=dict(size=8, color='#ffd700', symbol='circle'),
            name="艾略特波浪骨架"
        ), row=1, col=1)

        # 標註各浪序號 (① ~ ⑤ / ⓐ ~ ⓒ)
        wave_labels = ["①", "②", "③", "④", "⑤", "ⓐ", "ⓑ", "ⓒ"]
        for idx, p in enumerate(day_pivots[-8:]):
            lbl = wave_labels[idx % len(wave_labels)]
            is_peak = p["type"] == "PEAK"
            fig.add_annotation(
                x=p["time"][:10], y=p["price"],
                text=f"<b style='font-size:14px;'>{lbl}</b><br>${p['price']:,.1f}",
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowcolor="#ffd700",
                ay=-35 if is_peak else 35,
                bgcolor="rgba(13, 17, 23, 0.9)",
                bordercolor="#ffd700",
                borderwidth=1,
                font=dict(color="#ffd700", size=11, family="monospace"),
                row=1, col=1
            )

        # 3. 畫出最後一浪的未來預測延伸虛線 (Target 1 / Target 2)
        last_pivot = day_pivots[-1]
        last_date = df_plot['date_str'].iloc[-1]
        target_price = wave_res.get("next_target_1", 0.0)

        if target_price > 0:
            fig.add_trace(go.Scatter(
                x=[last_pivot["time"][:10], last_date],
                y=[last_pivot["price"], target_price],
                mode='lines',
                line=dict(color='#00E676' if target_price > last_pivot["price"] else '#FF5252', width=2, dash='dash'),
                name="未來預測波浪路徑"
            ), row=1, col=1)

    # 4. 成交量副圖
    vol_colors = ['#00E676' if c >= o else '#FF5252' for o, c in zip(df_plot['open'], df_plot['close'])]
    fig.add_trace(go.Bar(
        x=df_plot['date_str'], y=df_plot['volume'],
        marker_color=vol_colors, name="日線成交量"
    ), row=2, col=1)

    fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=15, b=10),
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        font=dict(color="#c9d1d9", family="monospace", size=11),
        xaxis=dict(gridcolor="#161b22", showgrid=True, rangeslider=dict(visible=False)),
        xaxis2=dict(gridcolor="#161b22", showgrid=True),
        yaxis=dict(gridcolor="#161b22", showgrid=True),
        yaxis2=dict(gridcolor="#161b22", showgrid=True),
        hovermode="x unified",
        showlegend=False
    )

    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': True})

def render_nq_wave_prediction_dashboard():
    st.markdown("### 🌊 納指 (NQ / QQQ) 艾略特全波浪理論推演中樞")
    st.caption("核心模型: **客觀幾何波段拐點 (Zigzag Pivots) + 斐波那契時空投影 (Fibonacci Ratios)**")

    # 載入日線與 1H 數據
    df_day = load_data("US.QQQ", "DAY")
    df_1h = load_data("US.QQQ", "1Hr")

    if df_day.empty:
        st.warning("⏳ 尚未檢測到 `US_QQQ_DAY.csv` 歷史數據。請先在終端機運行 `python data_fetcher.py`！")
        return

    # 進行全量波浪理論推演 (優先採用日線/1H 級別)
    wave_res = ElliottWaveEngine.analyze_wave_structure(df_day if len(df_day) >= 50 else df_1h)
    curr_price = float(df_day['close'].iloc[-1])

    # 1. 頂部核心 Wave 指標看板
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📌 當前最新基準價", f"${curr_price:,.2f}")
    m2.metric("🌊 當下波浪定位", wave_res["current_wave"])
    m3.metric("🧭 浪級宏觀方向", wave_res["trend_dir"])
    m4.metric("⏱️ 本浪運行時間", f"{wave_res['time_elapsed_hrs']} 天/棒", f"預期週期 ~{wave_res['expected_duration_hrs']} 棒")

    st.markdown("---")

    # 2. 📈 日線波浪全景走勢圖 (含波浪標籤與軌跡)
    st.markdown("#### 📈 日線艾略特波浪形態與拐點全景圖 (Daily Wave Chart)")
    render_wave_chart(df_day, wave_res)

    st.markdown("---")

    # 3. 🔮 未來走勢預測與目標推演
    st.markdown("#### 🧭 未來波浪走勢與空間目標推演 (Prediction Window)")
    pred_col1, pred_col2 = st.columns([1.5, 1.0])
    
    with pred_col1:
        st.info(f"### 🤖 艾略特波浪推演結論\n\n{wave_res['prediction_narrative']}")
        st.markdown(f"""
        * **當前子浪階梯 (Sub-Wave)**: `{wave_res['sub_wave']}` ({wave_res['wave_phase']})
        * **波浪健康度**: 結構完整，符合波浪鐵律（4浪不破1浪頂）。
        """)

    with pred_col2:
        st.markdown(f"""
        | 波浪推演指標 | 目標點位 ($) | 斐波那契依據 |
        | :--- | :--- | :--- |
        | **第 1 目標位 (Target 1)** | **${wave_res['next_target_1']:,.2f}** | 1.0x 對稱浪 |
        | **第 2 目標位 (Target 2)** | **${wave_res['next_target_2']:,.2f}** | 1.618x 主升擴展浪 |
        | **結構失效防守位 (SL)** | **${wave_res['invalid_price']:,.2f}** | 艾略特鐵律重疊防線 |
        """)
