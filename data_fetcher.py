# 文件名: data_fetcher.py
# 核心功能: 專業三級容災數據中樞 (OpenD 優先 -> yfinance 接管 -> 本地快照兜底)
# 嚴格統一標準: 美東紐約時區 (America/New_York) + 不復權真實價格 + 包含盤前盤後全時段

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
    ("US.QQQ", "QQQ", [
        ("1Hr", KLType.K_60M, "60m", 30, 800),
        ("DAY", KLType.K_DAY, "1d", 250, 200),
        ("WEEK", KLType.K_WEEK, "1wk", 700, 100)
    ]),
    ("US.BTC", "BTC-USD", [
        ("1Hr", KLType.K_60M, "60m", 30, 800),
        ("DAY", KLType.K_DAY, "1d", 250, 200),
        ("WEEK", KLType.K_WEEK, "1wk", 700, 100)
    ])
]

def fetch_from_opend(code: str, ktype_enum: KLType, days_back: int, count: int) -> pd.DataFrame:
    """Tier 1: 嘗試從本地 OpenD 獲取數據"""
    quote_ctx = None
    try:
        now_ny = datetime.datetime.now(tz_ny)
        start_date = (now_ny - datetime.timedelta(days=days_back)).strftime("%Y-%m-%d")
        end_date = now_ny.strftime("%Y-%m-%d")
        
        quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        ret, df_k, msg = quote_ctx.request_history_kline(
            code=code,
            start=start_date,
            end=end_date,
            ktype=ktype_enum,
            autype=AuType.NONE,
            max_count=count
        )
        if ret == RET_OK and not df_k.empty:
            df = df_k[['time_key', 'open', 'close', 'high', 'low', 'volume']].copy()
            df['time_key'] = pd.to_datetime(df['time_key'])
            return df
    except Exception as e:
        print(f"⚠️ OpenD 通道跳過 ({code}): {e}")
    finally:
        if quote_ctx:
            try: quote_ctx.close()
            except: pass
    return pd.DataFrame()

def fetch_from_yfinance(yf_symbol: str, yf_interval: str, days_back: int) -> pd.DataFrame:
    """Tier 2: 備援接管 - 透過 yfinance 抓取美東時間全時段數據 (含盤前盤後)"""
    try:
        now_ny = datetime.datetime.now(tz_ny)
        start_dt = now_ny - datetime.timedelta(days=days_back)
        
        # yfinance 開啟 prepost=True 下載包含盤前盤後的完整走勢
        df = yf.download(
            tickers=yf_symbol,
            start=start_dt.strftime("%Y-%m-%d"),
            end=(now_ny + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
            interval=yf_interval,
            prepost=True,
            progress=False,
            auto_adjust=False
        )
        if not df.empty:
            # 處理 MultiIndex 欄位結構
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0].lower() for col in df.columns]
            else:
                df.columns = [c.lower() for c in df.columns]

            # 轉換為美東時間並統一格式
            df = df.reset_index()
            date_col = 'Datetime' if 'Datetime' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
            
            df['time_key'] = pd.to_datetime(df[date_col])
            if df['time_key'].dt.tz is None:
                df['time_key'] = df['time_key'].dt.tz_localize('UTC').dt.tz_convert(tz_ny)
            else:
                df['time_key'] = df['time_key'].dt.tz_convert(tz_ny)
                
            # 去除時區偏移量字串，保持標準 datetime 格式
            df['time_key'] = df['time_key'].dt.tz_localize(None)

            clean_df = df[['time_key', 'open', 'close', 'high', 'low', 'volume']].copy()
            clean_df = clean_df.dropna().sort_values('time_key').reset_index(drop=True)
            return clean_df
    except Exception as e:
        print(f"⚠️ yfinance 備援失敗 ({yf_symbol}): {e}")
    return pd.DataFrame()

def sync_unified_market_data():
    print("【三級容災引擎啟動】執行 OpenD -> yfinance -> 本地快照 互補拉取...")
    
    for opend_code, yf_sym, tasks in TARGETS:
        for ktype_name, opend_ktype, yf_interval, days_back, count in tasks:
            clean_code = opend_code.replace('.', '_')
            file_path = os.path.join(DATA_DIR, f"{clean_code}_{ktype_name}.csv")
            
            df_result = pd.DataFrame()
            data_source = ""
            
            # 1. 優先嘗試 Tier 1: OpenD
            df_result = fetch_from_opend(opend_code, opend_ktype, days_back, count)
            if not df_result.empty:
                data_source = "🟢 OpenD 原生"
            
            # 2. 若 OpenD 失敗或無數據，切換 Tier 2: yfinance 備援接管
            if df_result.empty:
                print(f"🔄 正在為 {opend_code} {ktype_name} 啟動 yfinance 備援接管...")
                df_result = fetch_from_yfinance(yf_sym, yf_interval, days_back)
                if not df_result.empty:
                    data_source = "🟡 yfinance 備援"
            
            # 3. 處理存盤與校驗
            if not df_result.empty:
                df_result['time_key'] = pd.to_datetime(df_result['time_key'])
                df_result = df_result.sort_values('time_key').drop_duplicates(subset=['time_key']).reset_index(drop=True)
                df_result.to_csv(file_path, index=False)
                
                last_time = df_result['time_key'].iloc[-1]
                last_close = float(df_result['close'].iloc[-1])
                print(f"【成功落盤】{opend_code} {ktype_name:4s} [{data_source}] ({len(df_result)} 根) -> 最新: {last_time} | 現價: ${last_close:.2f}")
            else:
                # 4. Tier 3: 本地歷史 CSV 兜底
                if os.path.exists(file_path):
                    print(f"🛡️ {opend_code} {ktype_name} 啟用本地快照兜底防禦。")
                else:
                    print(f"❌ {opend_code} {ktype_name} 三級通道均無可用數據。")
            
            time.sleep(0.05)

    print("【任務完成】全市場多源互補數據同步完畢。")

if __name__ == "__main__":
    sync_unified_market_data()
