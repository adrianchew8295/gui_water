# 文件名: app.py
# 核心功能: 癸水 · 0DTE 量化實戰座艙主入口 (緊湊專業 UI + 零空間浪費 + 1 秒心跳)

import streamlit as st
from chart_plugin import ChartPlugin
from audit_comparator_plugin import AuditComparatorPlugin
from journal_plugin import JournalPlugin

st.set_page_config(
    page_title="癸水 · 0DTE座艙",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"  # 預設收起側邊欄，釋放最大主視野
)

# 全域緊湊樣式注入 (消滅大標題留白)
st.markdown("""
<style>
    .block-container { padding-top: 0.8rem; padding-bottom: 0rem; max-width: 98%; }
    header { visibility: hidden; } /* 隱藏 Streamlit 頂部預設空白條 */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { height: 36px; padding: 0 16px; font-size: 13px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

plugin = ChartPlugin()
audit_plugin = AuditComparatorPlugin()
journal_plugin = JournalPlugin()

sidebar = st.sidebar
sidebar.header("🎛️ 控制中樞")
target_code = sidebar.selectbox("選擇監控標的", ["CC.BTCUSD", "US.QQQ"], index=0)
budget_input = sidebar.number_input("💰 0DTE 單筆預算 (USD)", min_value=50.0, max_value=5000.0, value=200.0, step=50.0)

# 頂部超緊湊標題列 (僅 15px 高度)
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
