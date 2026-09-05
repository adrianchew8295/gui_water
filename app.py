# 文件名: app.py
import streamlit as st
from chart_plugin import ChartPlugin

st.set_page_config(page_title="專業行情看板", layout="wide")
st.title("專業量化交易看板")

plugin = ChartPlugin()

sidebar_col = st.sidebar
target_code = sidebar_col.selectbox("選擇標的", ["US.QQQ", "US.BTC"])
target_ktype = sidebar_col.selectbox("選擇週期", ["1Hr", "DAY", "WEEK"])

st.subheader(f"{target_code} - {target_ktype} 走勢與預測通道")

plugin.render_chart(code=target_code, ktype_name=target_ktype)
