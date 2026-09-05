# 文件名: app.py
# 核心功能: 極簡純數據實戰座艙主入口 (0 網絡阻塞，秒級即時加載)

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

if sidebar.button("🔄 立即刷新最新行情", use_container_width=True):
    st.rerun()

st.title(f"⚡ 癸水 · 0DTE 量化實戰純數據座艙 ({target_code})")

# 直接執行渲染，絕無死鎖
plugin.render_cockpit(target_code)
