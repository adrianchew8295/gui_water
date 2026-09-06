# 文件名: app.py
# 職責: 癸水 · 量化實戰全能座艙 (實操艙 + 記帳復盤 + 數據審核 + NQ波浪預測)

import streamlit as st
from chart_plugin import ChartPlugin
from journal_plugin import JournalPlugin
from audit_comparator_plugin import AuditComparatorPlugin
from nq_wave_tab import render_nq_wave_prediction_dashboard

st.set_page_config(
    page_title="癸水 · 量化實戰全能座艙",
    page_icon="⚡",
    layout="wide"
)

# 初始化插件實例
chart_plugin = ChartPlugin()
journal_plugin = JournalPlugin()
audit_plugin = AuditComparatorPlugin()

# 側邊欄控制
with st.sidebar:
    st.markdown("### 🎛️ 控制中樞")
    symbol = st.selectbox("🎯 選擇交易標的", ["US.QQQ", "CC.BTCUSD"], index=0)
    budget = st.number_input("💰 0DTE 預算上限 ($)", min_value=50.0, max_value=2000.0, value=200.0, step=50.0)

# 四大核心功能 Tab
tab1, tab2, tab3, tab4 = st.tabs([
    "⚡ 實盤操作監控艙 (Live Cockpit)",
    "📊 策略記帳與逐筆復盤 (Journal & 交易打點)",
    "🔍 多源數據交叉審核 (Audit Logs)",
    "🌊 NQ Main 波浪預測終端 (Elliott Wave)"
])

with tab1:
    chart_plugin.render_cockpit(symbol, budget_usd=budget)

with tab2:
    journal_plugin.render_journal_view(symbol)

with tab3:
    audit_plugin.render_comparator_view(symbol)

with tab4:
    render_nq_wave_prediction_dashboard()
