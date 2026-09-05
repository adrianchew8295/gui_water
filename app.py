# 文件名: app.py
# 核心功能: 癸水 · 0DTE 量化實戰座艙主入口 (5分鐘定時平滑推進，零噪音)

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
target_code = sidebar.selectbox("選擇監控標的", ["CC.BTCUSD", "US.QQQ"], index=0)
budget_input = sidebar.number_input("💰 0DTE 單筆預算上限 (USD)", min_value=50.0, max_value=2000.0, value=200.0, step=50.0)
refresh_rate = sidebar.selectbox("⏱️ 看板檢查週期", ["每 5 秒檢查換棒", "每 10 秒檢查換棒", "手動刷新"], index=0)

st.title(f"⚡ 癸水 · 0DTE 量化實戰純數據座艙 ({target_code})")

# 定時局部刷新 (每 5 秒檢查是否有新閉合 5M 柱)
run_interval = 5 if "5" in refresh_rate else (10 if "10" in refresh_rate else None)

@st.fragment(run_every=run_interval)
def render_main_cockpit(code: str, budget: float):
    plugin.render_cockpit(code, budget_usd=budget)

render_main_cockpit(target_code, budget_input)
