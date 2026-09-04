import streamlit as st
import pandas as pd
import time
from futu import *
import streamlit as st
import pandas as pd

# 頁面基礎設置
st.set_page_config(page_title="富途量化終端", layout="wide")

# 嘗試安全導入富途庫
FUTU_AVAILABLE = False
try:
    from futu import *
    FUTU_AVAILABLE = True
except ImportError:
    st.error("系統未檢測到 futu-api 依賴庫。若在雲端運行，請在 GitHub 倉庫添加 requirements.txt 並寫入 futu-api。")

st.title("0DTE 期權與量化實時看板")

# 側邊欄配置
with st.sidebar:
    st.header("連接與標的設置")
    host = st.text_input("OpenD 監聽 IP", value="127.0.0.1")
    port = st.number_input("OpenD 監聽端口", value=11111, step=1)
    target_symbol = st.selectbox("監控標的", ["US.QQQ", "HK.00700", "US.BTC"])
    timeframe = st.selectbox("查看週期", ["5M (實時)", "Daily (日線)", "Weekly (周線)", "Monthly (月線)"])
    connect_btn = st.button("連接 OpenD 獲取數據")

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

# 點擊按鈕觸發
if connect_btn and FUTU_AVAILABLE:
    ktype_map = {
        "5M (實時)": KLType.K_5M,
        "Daily (日線)": KLType.K_DAY,
        "Weekly (周線)": KLType.K_WEEK,
        "Monthly (月線)": KLType.K_MON
    }
    st.info(f"正在獲取 {target_symbol} 數據...")
    df = fetch_kline_data(host, port, target_symbol, ktype_map[timeframe])
    if not df.empty:
        st.success(f"成功獲取 {len(df)} 根 K 線數據")
        st.dataframe(df[['time_key', 'open', 'high', 'low', 'close', 'volume']].tail(20))

# 頁面配置
st.set_page_config(page_title="富途量化終端", layout="wide")

st.title("0DTE 期權與量化實時看板")

# 側邊欄控制
with st.sidebar:
    st.header("連接與標的設置")
    host = st.text_input("OpenD 監聽 IP", value="127.0.0.1")
    port = st.number_input("OpenD 監聽端口", value=11111, step=1)
    target_symbol = st.selectbox("監控標的", ["US.QQQ", "HK.00700", "US.BTC"])
    timeframe = st.selectbox("查看週期", ["5M (實時)", "Daily (日線)", "Weekly (周線)", "Monthly (月線)"])
    connect_btn = st.button("連接 OpenD 獲取數據")

# 週期對應字典
ktype_dict = {
    "5M (實時)": KLType.K_5M,
    "Daily (日線)": KLType.K_DAY,
    "Weekly (周線)": KLType.K_WEEK,
    "Monthly (月線)": KLType.K_MON
}

# 數據獲取函數 (帶異常防護)
def fetch_kline_data(host, port, symbol, ktype, count=500):
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

# 主視窗渲染
if connect_btn:
    st.info(f"正在從 OpenD 獲取 {target_symbol} 的 {timeframe} 數據...")
    df = fetch_kline_data(host, port, target_symbol, ktype_dict[timeframe])
    
    if not df.empty:
        st.success(f"成功獲取 {len(df)} 根 K 線數據")
        
        # 簡單表格預覽 (後續接入金融蠟燭圖)
        st.dataframe(df[['time_key', 'open', 'high', 'low', 'close', 'volume']].tail(20))
