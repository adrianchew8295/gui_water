# 文件名: data_fetcher.py
# 核心功能: 一鍵下載 5M (全時段)、1Hr (全時段重採樣)、DAY (日線)、WEEK (週線) 數據庫

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

def fetch_history_opend(code: str, ktype_enum: KLType, days_back: int, count: int) -> pd.DataFrame:
    """從 OpenD 抓取大級別歷史日線與周線"""
    quote_ctx = None
    try:
        now_ny = datetime.datetime.now(tz_ny)
        start_str = (now_ny - datetime.timedelta(days=days_back)).strftime("%Y-%m-%d")
        end_str = now_ny.strftime("%Y-%m-%d")
        
        quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        ret, df_k, msg = quote_ctx.request_history_kline(
            code=code,
            start=start_str,
            end=end_str,
            ktype=ktype_enum,
            autype=AuType.NONE,
            max_count=count
        )
        if ret == RET_OK and not df_k.empty:
            df = df_k[['time_key', 'open', 'close', 'high', 'low', 'volume']].copy()
            df['time_key'] = pd.to_datetime(df['time_key'])
            return df.sort_values('time_key').reset_index(drop=True)
    except Exception as e:
        print(f"⚠️ OpenD 歷史拉取異常 ({code}): {e}")
    finally:
        if quote_ctx:
            try: quote_ctx.close()
            except: pass
    return pd.DataFrame()

def fetch_5m_opend_or_yf(code: str, yf_sym: str) -> pd.DataFrame:
    """抓取 5M 原始數據 (含 04:00-20:00 盤前盤後)"""
    # 優先 OpenD 5M
    quote_ctx = None
    try:
        now_ny = datetime.datetime.now(tz_ny)
        start_str = (now_ny - datetime.timedelta(days=20)).strftime("%Y-%m-%d")
        end_str = now_ny.strftime("%Y-%m-%d")
        quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        ret, df_k, msg = quote_ctx.request_history_kline(
            code=code,
            start=start_str,
            end=end_str,
            ktype=KLType.K_5M,
            autype=AuType.NONE,
            max_count=3000
        )
        if ret == RET_OK and not df_k.empty:
            df = df_k[['time_key', 'open', 'close', 'high', 'low', 'volume']].copy()
            df['time_key'] = pd.to_datetime(df['time_key'])
            return df.sort_values('time_key').reset_index(drop=True)
    except Exception:
        pass
    finally:
        if quote_ctx:
            try: quote_ctx.close()
            except: pass

    # yfinance 備援 5M
    try:
        df_yf = yf.download(tickers=yf_sym, period="1mo", interval="5m", prepost=True, progress=False, auto_adjust=False)
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
    except Exception:
        pass
    return pd.DataFrame()

def sync_all_timeframes():
    print("【任務啟動】同步全市場全週期數據 (5M / 1Hr / DAY / WEEK)...")
    
    for code, yf_sym in TARGETS:
        clean_code = code.replace('.', '_')

        # 1. 下載並保存 5M (全時段)
        df_5m = fetch_5m_opend_or_yf(code, yf_sym)
        if not df_5m.empty:
            df_5m.to_csv(os.path.join(DATA_DIR, f"{clean_code}_5M.csv"), index=False)
            print(f"✅ [5M 落盤] {code} ({len(df_5m)} 根)")
            
            # 2. 5M 自動重採樣為 1Hr 並落盤
            df_5m_temp = df_5m.copy().set_index('time_key')
            df_1h = df_5m_temp.resample('1h', closed='left', label='left').agg({
                'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
            }).dropna().reset_index()
            df_1h.to_csv(os.path.join(DATA_DIR, f"{clean_code}_1Hr.csv"), index=False)
            print(f"✅ [1Hr 重採樣落盤] {code} ({len(df_1h)} 根)")
        else:
            print(f"❌ {code} 5M 拉取失敗")

        # 3. 下載並保存 DAY (日線 250 根)
        df_day = fetch_history_opend(code, KLType.K_DAY, 365, 250)
        if not df_day.empty:
            df_day.to_csv(os.path.join(DATA_DIR, f"{clean_code}_DAY.csv"), index=False)
            print(f"✅ [DAY 落盤] {code} ({len(df_day)} 根)")
        else:
            # 備援 yfinance 日線
            try:
                df_day_yf = yf.download(tickers=yf_sym, period="1y", interval="1d", progress=False, auto_adjust=False)
                if not df_day_yf.empty:
                    df_day_yf.columns = [c[0].lower() if isinstance(df_day_yf.columns, pd.MultiIndex) else c.lower() for c in df_day_yf.columns]
                    df_day_yf = df_day_yf.reset_index()
                    dt_col = 'Date' if 'Date' in df_day_yf.columns else df_day_yf.columns[0]
                    df_day_yf['time_key'] = pd.to_datetime(df_day_yf[dt_col]).dt.strftime('%Y-%m-%d')
                    df_day_yf[['time_key', 'open', 'close', 'high', 'low', 'volume']].to_csv(os.path.join(DATA_DIR, f"{clean_code}_DAY.csv"), index=False)
                    print(f"✅ [DAY 備援落盤] {code} ({len(df_day_yf)} 根)")
            except Exception:
                pass

        # 4. 下載並保存 WEEK (週線 100 根)
        df_week = fetch_history_opend(code, KLType.K_WEEK, 750, 100)
        if not df_week.empty:
            df_week.to_csv(os.path.join(DATA_DIR, f"{clean_code}_WEEK.csv"), index=False)
            print(f"✅ [WEEK 落盤] {code} ({len(df_week)} 根)")
        else:
            # 備援 yfinance 週線
            try:
                df_wk_yf = yf.download(tickers=yf_sym, period="2y", interval="1wk", progress=False, auto_adjust=False)
                if not df_wk_yf.empty:
                    df_wk_yf.columns = [c[0].lower() if isinstance(df_wk_yf.columns, pd.MultiIndex) else c.lower() for c in df_wk_yf.columns]
                    df_wk_yf = df_wk_yf.reset_index()
                    dt_col = 'Date' if 'Date' in df_wk_yf.columns else df_wk_yf.columns[0]
                    df_wk_yf['time_key'] = pd.to_datetime(df_wk_yf[dt_col]).dt.strftime('%Y-%m-%d')
                    df_wk_yf[['time_key', 'open', 'close', 'high', 'low', 'volume']].to_csv(os.path.join(DATA_DIR, f"{clean_code}_WEEK.csv"), index=False)
                    print(f"✅ [WEEK 備援落盤] {code} ({len(df_wk_yf)} 根)")
            except Exception:
                pass

        time.sleep(0.1)

    print("【任務完成】5M、1Hr、DAY、WEEK 全週期數據均已生成完畢。")

if __name__ == "__main__":
    sync_all_timeframes()
