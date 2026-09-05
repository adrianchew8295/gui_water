# 文件名: app.py
# 核心功能: 癸水 · 量化實戰座艙 (雙 Tab 架構：Tab1 保留原圖表，Tab2 實際操作信號艙)

import streamlit as st
from chart_plugin import ChartPlugin

st.set_page_config(page_title="癸水 · 量化實戰座艙", layout="wide")

plugin = ChartPlugin()

# 側邊欄控制
sidebar_col = st.sidebar
sidebar_col.header("🎛️ 控制中樞")
target_code = sidebar_col.selectbox("選擇標的", ["CC.BTCUSD", "US.QQQ"], index=0)
target_ktype = sidebar_col.selectbox("選擇週期", ["5M", "1Hr", "DAY", "WEEK"], index=0)
auto_refresh = sidebar_col.checkbox("⚡ 開啟 3 秒實時平滑輪詢", value=True)

if sidebar_col.button("🔄 手動刷新圖表 K 線"):
    st.rerun()

# 🌟 劃分兩個 Tab：完全保留原圖 + 新增實戰操作 Tab
tab1, tab2 = st.tabs(["📈 圖表分析視圖 (Chart)", "⚡ 實際操作監控艙 (Live Table)"])

with tab1:
    # 頂部即時報價表格 (3秒輪詢)
    @st.fragment(run_every=3 if auto_refresh else None)
    def render_tab1_top(code: str, ktype: str):
        plugin.render_live_monitor_table(code, ktype)
    
    render_tab1_top(target_code, target_ktype)
    st.divider()
    # 完整保留原本的帶圖代碼與畫布
    plugin.render_static_chart(target_code, target_ktype)

with tab2:
    st.subheader("🎯 5分鐘日內 0DTE 實際操作信號面板")
    
    # 實操 Table 局部刷新 (3秒跳動計算信號)
    @st.fragment(run_every=3 if auto_refresh else None)
    def render_tab2_operation(code: str):
        st.markdown("##### 🚦 5M 即時戰術扳機與開倉指令")
        plugin.render_operation_signals_table(code)
        
        st.divider()
        st.markdown("##### ⚡ 盤口現價與成交量動態")
        plugin.render_live_monitor_table(code, "5M")
    
    render_tab2_operation(target_code)
