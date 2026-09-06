# 文件名: app.py
# 核心功能: 癸水 · 0DTE 量化實戰座艙主入口 (三 Tab 獨立解耦 + 每 1 秒心跳局部刷新)

import streamlit as st
from chart_plugin import ChartPlugin
from audit_comparator_plugin import AuditComparatorPlugin
from journal_plugin import JournalPlugin

st.set_page_config(
    page_title="癸水 · 0DTE量化座艙",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

plugin = ChartPlugin()
audit_plugin = AuditComparatorPlugin()
journal_plugin = JournalPlugin()

sidebar = st.sidebar
sidebar.header("🎛️ 控制中樞")
target_code = sidebar.selectbox("選擇監控標的", ["CC.BTCUSD", "US.QQQ"], index=0)
budget_input = sidebar.number_input("💰 0DTE 單筆預算上限 (USD)", min_value=50.0, max_value=5000.0, value=200.0, step=50.0)

st.title(f"⚡ 癸水 · 0DTE 量化實戰純數據座艙 ({target_code})")

tab1, tab2, tab3 = st.tabs([
    "🚀 實盤射控座艙",
    "🔍 數據真偽審核",
    "📊 策略回測與記帳"
])

# 每 1 秒自動局部心跳刷新
@st.fragment(run_every=1.0)
def render_live_cockpit(code: str, budget: float):
    plugin.render_cockpit(code, budget_usd=budget)

with tab1:
    render_live_cockpit(target_code, budget_input)

with tab2:
    audit_plugin.render_audit_dashboard(target_code)

with tab3:
    journal_plugin.render_journal_dashboard(target_code, budget_usd=budget_input)
