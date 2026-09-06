# 文件名: app.py
# 核心功能: 癸水 · 0DTE 量化實戰座艙主入口 (原生可收縮側邊欄 + 標的自由切換 + 緊湊專業 UI)

import streamlit as st
from chart_plugin import ChartPlugin
from audit_comparator_plugin import AuditComparatorPlugin
from journal_plugin import JournalPlugin

st.set_page_config(
    page_title="癸水 · 0DTE座艙",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"  # 預設展開，左上角保留原生箭頭可隨時點擊收縮
)

# 全域緊湊樣式 (保留原生 Sidebar 收縮按鈕)
st.markdown("""
<style>
    .block-container { padding-top: 1.2rem; padding-bottom: 0rem; max-width: 98%; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { height: 36px; padding: 0 16px; font-size: 13px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

plugin = ChartPlugin()
audit_plugin = AuditComparatorPlugin()
journal_plugin = JournalPlugin()

# 側邊欄控制中樞 (可隨時點擊左上角收起)
sidebar = st.sidebar
sidebar.header("🎛️ 控制中樞")
target_code = sidebar.selectbox("選擇監控標的", ["US.QQQ", "CC.BTCUSD"], index=0)
budget_input = sidebar.number_input("💰 0DTE 單筆預算 (USD)", min_value=50.0, max_value=5000.0, value=200.0, step=50.0)

# 頂部狀態列
st.markdown(f"""
<div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #21262d; padding-bottom: 6px; margin-bottom: 8px; font-family: monospace;">
    <span style="font-size: 15px; font-weight: bold; color: #58a6ff;">⚡ 癸水 · 0DTE 量化射控座艙 <span style="font-size: 12px; color: #8b949e;">({target_code})</span></span>
    <span style="font-size: 12px; color: #8b949e;">單筆預算: <b style="color: #ffd700;">${budget_input:.0f} USD</b> | 模式: <b>實盤前向驗證</b></span>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs([
    "🚀 實盤射控座艙",
    "🔍 數據真偽審核",
    "📊 策略復盤與記帳"
])

@st.fragment(run_every=1.0)
def render_live_cockpit(code: str, budget: float):
    plugin.render_cockpit(code, budget_usd=budget)

with tab1:
    render_live_cockpit(target_code, budget_input)

with tab2:
    audit_plugin.render_audit_dashboard(target_code)

with tab3:
    journal_plugin.render_journal_dashboard(target_code, budget_usd=budget_input)
