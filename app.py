import streamlit as st
from chart_plugin import ChartPlugin
from audit_comparator_plugin import AuditComparatorPlugin

st.set_page_config(page_title="癸水 · 量化交易座艙", layout="wide", page_icon="⚡")

# 側邊欄配置
st.sidebar.title("⚙️ 座艙控制台")
code = st.sidebar.selectbox("監控標的", ["US.QQQ", "CC.BTCUSD"], index=1)
budget = st.sidebar.number_input("0DTE 單筆預算上限 (USD)", min_value=50.0, max_value=2000.0, value=200.0, step=10.0)

tab1, tab2 = st.tabs(["🚀 實盤射控座艙", "🔍 多源數據交叉審核"])

plugin = ChartPlugin()
audit_plugin = AuditComparatorPlugin()

with tab1:
    plugin.render_cockpit(code, budget_usd=budget)

with tab2:
    audit_plugin.render_audit_dashboard(code)
