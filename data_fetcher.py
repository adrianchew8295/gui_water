# 文件名: data_fetcher.py
# 核心功能: 抓取 5M/1M 全時段原始數據 (04:00-20:00)，本地 Back-Resampling 合成無跳空 1Hr K 線

import datetime
import os
import time
import pandas as pd
import pytz
import yfinance as yf
from moomoo import OpenQuoteContext, RET_OK, KLType, AuType

tz_ny = pytz.timezone("America/New_York")
DATA_DIR = './market_data'
os.makedirs(DATA_DIR, exist_ok=True)

TARGETS = [
    ("US.QQQ", "QQQ"),
    ("US.BTC", "BTC-USD")
]

def fetch_5m_raw(code: str, yf_sym: str, days_back: int = 30) -> pd.DataFrame:
    """優先嘗試從 OpenD 抓取 5M 全時段數據，若無則切換 yfinance 備援"""
    now_ny = datetime.datetime.now(tz_ny)
    start_str = (now_ny - datetime.timedelta(days=days_back)).strftime("%Y-%m-%d")
    end_str = now_ny.strftime("%Y-%m-%d")
    
    # 1. OpenD 嘗試
    quote_ctx = None
    try:
        quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        ret, df_k, msg = quote_ctx.request_history_kline(
            code=code,
            start=start_str,
            end=end_str,
            ktype=KLType.K_5M,
            autype=AuType.NONE,
            max_count=3500
        )
        if ret == RET_OK and not df_k.empty:
            df = df_k[['time_key', 'open', 'close', 'high', 'low', 'volume']].copy()
            df['time_key'] = pd.to_datetime(df['time_key'])
            return df.sort_values('time_key').reset_index(drop=True)
    except Exception as e:
        print(f"⚠️ OpenD 5M 跳過: {e}")
    finally:
        if quote_ctx:
            try: quote_ctx.close()
            except: pass

    # 2. yfinance 備援 (開啟 prepost 抓取 04:00~20:00)
    try:
        print(f"🔄 啟用 yfinance 備援拉取 {yf_sym} 5M 全時段數據...")
        df_yf = yf.download(
            tickers=yf_sym,
            period="1mo",
            interval="5m",
            prepost=True,
            progress=False,
            auto_adjust=False
        )
        if not df_yf.empty:
            if isinstance(df_yf.columns, pd.MultiIndex):
                df_yf.columns = [c[0].lower() for c in df_yf.columns]
            else:
                df_yf.columns = [c.lower() for c in df_yf.columns]
            df_yf = df_yf.reset_index()
            dt_col = 'Datetime' if 'Datetime' in df_yf.columns else ('Date' if 'Date' in df_yf.columns else df_yf.columns[0])
            df_yf['time_key'] = pd.to_datetime(df_yf[dt_col])
            
            if df_yf['time_key'].dt.tz is None:
                df_yf['time_key'] = df_yf['time_key'].dt.tz_localize('UTC').dt.tz_convert(tz_ny)
            else:
                df_yf['time_key'] = df_yf['time_key'].dt.tz_convert(tz_ny)
            df_yf['time_key'] = df_yf['time_key'].dt.tz_localize(None)

            clean_df = df_yf[['time_key', 'open', 'close', 'high', 'low', 'volume']].dropna()
            return clean_df.sort_values('time_key').reset_index(drop=True)
    except Exception as e:
        print(f"⚠️ yfinance 5M 備援失敗: {e}")
        
    return pd.DataFrame()

def resample_5m_to_1hr(df_5m: pd.DataFrame) -> pd.DataFrame:
    """將 5M 數據在本地精確重採樣為 1Hr K 線 (包含盤前 04:00 與盤後 16:00)"""
    if df_5m.empty:
        return pd.DataFrame()
    
    df = df_5m.copy()
    df.set_index('time_key', inplace=True)
    
    # 依 1 小時重採樣聚合
    agg_rules = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }
    df_1h = df.resample('1h', closed='left', label='left').agg(agg_rules).dropna().reset_index()
    return df_1h

def sync_pipeline():
    print("【任務啟動】以 5M 原始層為基座，執行 Back-Resampling 合成...")
    
    for code, yf_sym in TARGETS:
        clean_code = code.replace('.', '_')
        
        # 1. 抓取 5M 原始數據
        df_5m = fetch_5m_raw(code, yf_sym, days_back=30)
        if df_5m.empty:
            print(f"❌ 無法獲取 {code} 5M 數據")
            continue
            
        file_5m = os.path.join(DATA_DIR, f"{clean_code}_5M.csv")
        df_5m.to_csv(file_5m, index=False)
        print(f"✅ [5M 落盤] {code} 共 {len(df_5m)} 根 5 分鐘 K 線")

        # 2. 本地 Back-Resampling 聚合為 1Hr
        df_1h = resample_5m_to_1hr(df_5m)
        file_1h = os.path.join(DATA_DIR, f"{clean_code}_1Hr.csv")
        df_1h.to_csv(file_1h, index=False)
        
        # 驗證輸出重採樣後的最新時間與數量
        last_t = df_1h['time_key'].iloc[-1]
        last_c = df_1h['close'].iloc[-1]
        print(f"🚀 [1Hr 重採樣成功] {code} 共 {len(df_1h)} 根連續 K 線 -> 最新時間: {last_t} | 價格: ${last_c:.2f}")
        
        time.sleep(0.1)

    print("【任務完成】數據層已完成 5M/1Hr 落地。")

if __name__ == "__main__":
    sync_pipeline()
