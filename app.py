# 文件名: app.py
# 核心功能: 癸水 · 0DTE 量化實戰座艙主入口 (每 1 秒更新倒數計時，整點換棒無延遲)

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

st.title(f"⚡ 癸水 · 0DTE 量化實戰純數據座艙 ({target_code})")

# 每 1 秒局部刷新頂部倒數計時與換棒偵測 (極速、零負載)
@st.fragment(run_every=1.0)
def render_main_cockpit(code: str, budget: float):
    plugin.render_cockpit(code, budget_usd=budget)

render_main_cockpit(target_code, budget_input)
