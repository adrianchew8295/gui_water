# 文件名: app.py
import streamlit as st
from chart_plugin import ChartPlugin

st.set_page_config(page_title="癸水 · 量化實戰座艙", layout="wide")

plugin = ChartPlugin()

sidebar_col = st.sidebar
target_code = sidebar_col.selectbox("選擇標的", ["US.QQQ", "US.BTC"])
target_ktype = sidebar_col.selectbox("選擇週期", ["5M", "1Hr", "DAY", "WEEK"])

plugin.render_chart(code=target_code, ktype_name=target_ktype)
