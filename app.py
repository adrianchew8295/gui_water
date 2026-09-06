# 文件名: app.py 片段
import streamlit as st
from chart_plugin import ChartPlugin
from nq_wave_tab import render_nq_wave_prediction_dashboard

st.set_page_config(page_title="癸水 · 量化實戰座艙", layout="wide")

plugin = ChartPlugin()

# 劃分三個 Tab
tab1, tab2, tab3 = st.tabs([
    "📈 圖表分析視圖 (Chart)", 
    "⚡ 實際操作監控艙 (Live Table)",
    "🌊 NQ Main 波浪預測終端 (Elliott Wave)"
])

with tab1:
    plugin.render_static_chart("US.QQQ", "1Hr")

with tab2:
    plugin.render_flash_cockpit_table("US.QQQ")

with tab3:
    # 專屬 NQ Main 1年期 1H 波浪分析與預測面板
    render_nq_wave_prediction_dashboard()
