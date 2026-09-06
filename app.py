# 文件名: app.py
import streamlit as st
from chart_plugin import ChartPlugin
from nq_wave_tab import render_nq_wave_prediction_dashboard

st.set_page_config(page_title="癸水 · 量化實戰座艙", layout="wide")

plugin = ChartPlugin()

tab1, tab2 = st.tabs([
    "⚡ 實際操作監控艙 (Live Cockpit)",
    "🌊 NQ Main 波浪預測終端 (Elliott Wave)"
])

with tab1:
    # 呼叫正確的實操監控座艙方法
    plugin.render_cockpit("US.QQQ", budget_usd=200.0)

with tab2:
    # 呼叫 1年期波浪推演與 1H 走勢預測面板
    render_nq_wave_prediction_dashboard()
