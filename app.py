# 文件名: app.py
# 核心功能: 癸水 · 量化實戰座艙 (頂部表格每3秒跳動，下方圖表完全鎖定不跳動)

import streamlit as st
from chart_plugin import ChartPlugin

st.set_page_config(page_title="癸水 · 量化實戰座艙", layout="wide")

plugin = ChartPlugin()

# 側邊欄配置
sidebar_col = st.sidebar
sidebar_col.header("🎛️ 控制中樞")
target_code = sidebar_col.selectbox("選擇標的", ["CC.BTCUSD", "US.QQQ"], index=0)
target_ktype = sidebar_col.selectbox("選擇週期", ["5M", "1Hr", "DAY", "WEEK"], index=0)
auto_refresh = sidebar_col.checkbox("⚡ 開啟頂部即時跳動 (每 3 秒)", value=True)

if sidebar_col.button("🔄 同步刷新圖表 K 線"):
    st.rerun()

# 🌟 1. 只有「頂部表格」被放在 Fragment 裡，每 3 秒只刷新這一塊！
@st.fragment(run_every=3 if auto_refresh else None)
def render_live_top_panel(code: str, ktype: str):
    plugin.render_live_monitor_table(code, ktype)

# 渲染頂部即時跳動面板
render_live_top_panel(target_code, target_ktype)

st.divider()

# 🌟 2. 「下方圖表」完全放在 Fragment 外部，不會被 3 秒定時器重繪！
plugin.render_static_chart(target_code, target_ktype)
