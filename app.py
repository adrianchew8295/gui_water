# 文件名: app.py
# 核心功能: 癸水 · 量化实战座舱主入口 (支持 3 秒自动轮询，看到表格跳动)

import time
import streamlit as st
from chart_plugin import ChartPlugin

st.set_page_config(page_title="癸水 · 量化实战座舱", layout="wide")

plugin = ChartPlugin()

# 侧边栏配置
sidebar_col = st.sidebar
sidebar_col.header("🎛️ 控制中枢")
target_code = sidebar_col.selectbox("选择标的", ["CC.BTCUSD", "US.QQQ"], index=0)
target_ktype = sidebar_col.selectbox("选择周期", ["5M", "1Hr", "DAY", "WEEK"], index=0)

auto_refresh = sidebar_col.checkbox("⚡ 开启实时跳动轮询 (每 3 秒刷新)", value=False)

# 主视口渲染
plugin.render_chart(code=target_code, ktype_name=target_ktype)

# 自动刷新轮询机制
if auto_refresh:
    time.sleep(3)
    st.rerun()
