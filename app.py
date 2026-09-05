import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# 頁面基礎設置
st.set_page_config(page_title="富途量化終端", layout="wide")

# 嘗試安全導入富途庫
FUTU_AVAILABLE = False
try:
    from futu import *
    FUTU_AVAILABLE = True
except ImportError:
    st.error("系統未檢測到 futu-api 依賴庫。請先執行 pip install futu-api 安裝。")

st.title("0DTE 期權與量化實時看板")

# 側邊欄配置
with st.sidebar:
    st.header("連接與標的設置")
    host = st.text_input("OpenD 監聽 IP", value="127.0.0.1")
    port = st.number_input("OpenD 監聽端口", value=11111, step=1)
    target_symbol = st.selectbox("監控標的", ["US.QQQ", "HK.00700", "US.BTC"])
    timeframe = st.selectbox("查看週期", ["5M (實時)", "Daily (日線)", "Weekly (周線)", "Monthly (月線)"])
    auto_refresh = st.checkbox("開啟實時刷新 (5秒)", value=False)
    load_btn = st.button("手動獲取/刷新數據")

# 數據獲取邏輯
def fetch_kline_data(host, port, symbol, ktype, count=500):
    if not FUTU_AVAILABLE:
        st.warning("請先安裝依賴庫再嘗試連接。")
        return pd.DataFrame()
    
    quote_ctx = None
    try:
        quote_ctx = OpenQuoteContext(host=host, port=port)
        ret, data = quote_ctx.get_cur_kline(symbol, count, ktype)
        if ret == RET_OK:
            return data
        else:
            st.error(f"獲取數據失敗: {data}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"連接異常: {str(e)}")
        return pd.DataFrame()
    finally:
        if quote_ctx:
            quote_ctx.close()

# 繪製自適應蠟燭圖
def plot_candlestick(df, title):
    fig = go.Figure(data=[go.Candlestick(
        x=df['time_key'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name="K線"
    )])
    fig.update_layout(
        title=title,
        yaxis_title="價格",
        xaxis_title="時間",
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        height=650,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return fig

# 運行主流程
if (load_btn or auto_refresh) and FUTU_AVAILABLE:
    ktype_map = {
        "5M (實時)": KLType.K_5M,
        "Daily (日線)": KLType.K_DAY,
        "Weekly (周線)": KLType.K_WEEK,
        "Monthly (月線)": KLType.K_MON
    }
    
    df = fetch_kline_data(host, port, target_symbol, ktype_map[timeframe])
    
    if not df.empty:
        fig = plot_candlestick(df, f"{target_symbol} - {timeframe}")
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"最後更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        st.warning("暫無數據，請確認 OpenD 是否登錄並處於運行狀態。")
