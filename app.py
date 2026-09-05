# 文件名: app.py
# 核心功能: 極簡高頻純數據實戰座艙主入口 (0 繪圖負擔，毫秒級平滑跳動)

import streamlit as st
from chart_plugin import ChartPlugin

st.set_page_config(
    page_title="癸水 · 量化實戰座艙",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

plugin = ChartPlugin()

# 側邊欄控制
sidebar = st.sidebar
sidebar.header("🎛️ 控制中樞")
target_code = sidebar.selectbox("選擇監控標的", ["CC.BTCUSD", "US.QQQ"], index=0)
live_speed = sidebar.slider("⚡ 實盤刷新頻率 (秒)", min_value=0.5, max_value=2.0, value=0.5, step=0.5)

st.title("⚡ 癸水 · 0DTE 量化實戰純數據座艙")

# 局部極速刷新，無整頁閃動與繪圖負擔
@st.fragment(run_every=live_speed)
def render_live_cockpit(code: str):
    plugin.render_cockpit(code)

render_live_cockpit(target_code)
