# 文件名: app.py
# 核心功能: 癸水量化座艙主入口 (零阻塞、純淨解耦)

import streamlit as st
from chart_plugin import ChartPlugin

st.set_page_config(
    page_title="癸水 · 0DTE量化座艙",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

plugin = ChartPlugin()

sidebar = st.sidebar
sidebar.header("🎛️ 控制中樞")
target_code = sidebar.selectbox("選擇監控標的", ["US.QQQ", "CC.BTCUSD"], index=0)
budget_input = sidebar.number_input("💰 0DTE 單筆預算上限 (USD)", min_value=50.0, max_value=2000.0, value=200.0, step=50.0)

if sidebar.button("🔄 立即重新整理", use_container_width=True):
    st.rerun()

# 渲染實盤座艙
plugin.render_cockpit(target_code, budget_usd=budget_input)
