# 文件名: app.py
# 核心功能: 極簡純數據實戰座艙主入口 (開啟 2 秒平滑自動輪詢)

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
auto_live = sidebar.checkbox("⚡ 開啟實時自動跳動 (每 2 秒)", value=True)

st.title(f"⚡ 癸水 · 0DTE 量化實戰純數據座艙 ({target_code})")

# 局部刷新單元：每 2 秒自動調用最新快照與 5M K 線
@st.fragment(run_every=2 if auto_live else None)
def render_live_cockpit(code: str):
    plugin.render_cockpit(code)

render_live_cockpit(target_code)
