# 文件名: app.py
import streamlit as st
from chart_plugin import ChartPlugin
from nq_wave_tab import render_nq_wave_prediction_dashboard

st.set_page_config(page_title="癸水 · 量化實戰座艙", layout="wide")

plugin = ChartPlugin()

tab1, tab2, tab3 = st.tabs([
    "📈 圖表分析視圖 (Chart)", 
    "⚡ 實際操作監控艙 (Live Table)",
    "🌊 NQ Main 波浪預測終端 (Elliott Wave)"
])

with tab1:
    # 呼叫正確的圖表渲染方法
    plugin.render_chart("US.QQQ", "1Hr")

with tab2:
    # 呼叫實盤操作監控艙
    plugin.render_cockpit("US.QQQ")

with tab3:
    # NQ Main / QQQ 1年期波浪推演終端
    render_nq_wave_prediction_dashboard()
