# 文件名: app.py
# 核心職責: 癸水 · 0DTE 量化實戰全能座艙 (還原 3 大舊 Tab + 第 4 Tab 專屬波浪預測獨立頁面)

import streamlit as st
from chart_plugin import ChartPlugin
from audit_comparator_plugin import AuditComparatorPlugin
from journal_plugin import JournalPlugin
from nq_wave_tab import render_nq_wave_prediction_dashboard

st.set_page_config(
    page_title="癸水 · 0DTE量化座艙",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 全域緊湊樣式
st.markdown("""
<style>
    .block-container { padding-top: 0.8rem; padding-bottom: 0rem; max-width: 98%; }
    header { visibility: hidden; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { height: 36px; padding: 0 16px; font-size: 13px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

plugin = ChartPlugin()
audit_plugin = AuditComparatorPlugin()
journal_plugin = JournalPlugin()

# 側邊欄：自由切換 QQQ 與 BTC
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

# 🌟 4 個獨立 Tab 完整歸位：舊的 3 個原封不動 + 艾略特波浪獨立在第 4 頁
tab1, tab2, tab3, tab4 = st.tabs([
    "🚀 實盤射控座艙",
    "🔍 數據真偽審核",
    "📊 策略復盤與記帳",
    "🌊 NQ / QQQ 艾略特波浪預測"
])

# 每 1 秒自動心跳局部刷新
@st.fragment(run_every=1.0)
def render_live_cockpit(code: str, budget: float):
    plugin.render_cockpit(code, budget_usd=budget)

with tab1:
    # 1. 實盤 Live Data + 跳動
    render_live_cockpit(target_code, budget_input)

with tab2:
    # 2. 數據交叉審核
    audit_plugin.render_audit_dashboard(target_code)

with tab3:
    # 3. 完整的策略記帳、回測清單、月曆與打點圖表
    journal_plugin.render_journal_dashboard(target_code, budget_usd=budget_input)

with tab4:
    # 4. 艾略特波浪理論專屬推演與 1H 走勢預測
    render_nq_wave_prediction_dashboard()
