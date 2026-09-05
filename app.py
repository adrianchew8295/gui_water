# 文件名: app.py
# 核心功能: 雙 Tab 實時座艙 (Tab1 圖表分析 + Tab2 最快極速 Flash 實操艙)

import streamlit as st
from chart_plugin import ChartPlugin

st.set_page_config(page_title="癸水 · 量化實戰座艙", layout="wide")

plugin = ChartPlugin()

# 側邊欄控制中樞
sidebar_col = st.sidebar
sidebar_col.header("🎛️ 控制中樞")
target_code = sidebar_col.selectbox("選擇標的", ["CC.BTCUSD", "US.QQQ"], index=0)
target_ktype = sidebar_col.selectbox("選擇圖表週期", ["5M", "1Hr", "DAY", "WEEK"], index=0)
live_speed = sidebar_col.slider("⚡ 實盤刷新頻率 (秒)", min_value=0.5, max_value=3.0, value=0.5, step=0.5)

tab1, tab2 = st.tabs(["📈 圖表分析視圖 (Chart)", "⚡ 實際操作監控艙 (Live Table)"])

with tab1:
    plugin.render_static_chart(target_code, target_ktype)

with tab2:
    # 局部極速刷新單元 (最快 0.5 秒平滑刷新)
    @st.fragment(run_every=live_speed)
    def render_operation_live(code: str):
        plugin.render_flash_cockpit_table(code)
    
    render_operation_live(target_code)
