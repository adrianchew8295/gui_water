# 文件名: app.py
# 核心功能: 癸水量化座艙全模組總裝 (實操艙 + Journal記帳/復盤打點 + 數據審核 + NQ波浪預測)

import streamlit as st
from chart_plugin import ChartPlugin
from journal_plugin import JournalPlugin
from audit_comparator_plugin import AuditComparatorPlugin
from nq_wave_tab import render_nq_wave_prediction_dashboard

st.set_page_config(page_title="癸水 · 量化實戰全能座艙", layout="wide")

# 初始化插件實例
chart_plugin = ChartPlugin()
journal_plugin = JournalPlugin()
audit_plugin = AuditComparatorPlugin()

# 側邊欄標的選擇
with st.sidebar:
    st.markdown("### 🎛️ 控制中心")
    symbol = st.selectbox("🎯 選擇交易標的", ["US.QQQ", "CC.BTCUSD"], index=0)
    budget = st.number_input("💰 0DTE 預算上限 ($)", min_value=50.0, max_value=2000.0, value=200.0, step=50.0)

# 四大核心功能 Tab 全員歸位
tab1, tab2, tab3, tab4 = st.tabs([
    "⚡ 實盤操作監控艙 (Live Cockpit)",
    "📊 策略記帳與逐筆復盤 (Journal & 交易打點)",
    "🔍 多源數據交叉審核 (Audit Logs)",
    "🌊 NQ Main 波浪預測終端 (Elliott Wave)"
])

with tab1:
    # 1. 5M 雙表 + 實盤跳動
    chart_plugin.render_cockpit(symbol, budget_usd=budget)

with tab2:
    # 2. 歷史記帳、月曆回測與帶有買賣點圓球/線條的 Plotly 復盤畫布
    journal_plugin.render_journal_view(symbol)

with tab3:
    # 3. 三源交叉審核
    audit_plugin.render_comparator_view(symbol)

with tab4:
    # 4. 1年期 1H 波浪理論與 1 小時走勢預測中樞
    render_nq_wave_prediction_dashboard()
