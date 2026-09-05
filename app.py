# 文件名: app.py
# 核心功能: 極簡高頻純數據座艙 (100% 原生組件，絕不白屏)

import streamlit as st
from chart_plugin import ChartPlugin

st.set_page_config(
    page_title="癸水 · 量化實戰座艙",
    page_icon="⚡",
    layout="wide"
)

plugin = ChartPlugin()

# 側邊欄控制
sidebar = st.sidebar
sidebar.header("🎛️ 控制中樞")
target_code = sidebar.selectbox("選擇監控標的", ["CC.BTCUSD", "US.QQQ"], index=0)
live_speed = sidebar.slider("⚡ 實盤刷新頻率 (秒)", min_value=0.5, max_value=3.0, value=1.0, step=0.5)

st.title(f"⚡ 癸水 · 0DTE 量化實戰純數據座艙 ({target_code})")

# 局部極速刷新
@st.fragment(run_every=live_speed)
def render_live_cockpit(code: str):
    plugin.render_cockpit(code)

render_live_cockpit(target_code)
