# 文件名: app.py
# 核心功能: 癸水 · 量化實戰座艙主入口 (局部 Fragment 3秒平滑跳動，絕不重置圖表)

import streamlit as st
from chart_plugin import ChartPlugin

st.set_page_config(page_title="癸水 · 量化實戰座艙", layout="wide")

plugin = ChartPlugin()

# 側邊欄配置
sidebar_col = st.sidebar
sidebar_col.header("🎛️ 控制中樞")
target_code = sidebar_col.selectbox("選擇標的", ["CC.BTCUSD", "US.QQQ"], index=0)
target_ktype = sidebar_col.selectbox("選擇週期", ["5M", "1Hr", "DAY", "WEEK"], index=0)
auto_refresh = sidebar_col.checkbox("⚡ 開啟實時平滑跳動 (每 3 秒)", value=True)

# 🌟 使用 Streamlit 官方 Fragment 局部單元：只在內部自動刷新，外層絕不全頁重繪
@st.fragment(run_every=3 if auto_refresh else None)
def render_live_dashboard(code: str, ktype: str):
    plugin.render_chart(code=code, ktype_name=ktype)

# 執行渲染
render_live_dashboard(target_code, target_ktype)
