# 文件名: data_fetcher.py
# 核心功能: 全週期歷史基座同步器 (WEEK, DAY, 5M, 以及全時段 1Hr 重採樣)

import os
import time
import datetime
import pandas as pd
import pytz
import yfinance as yf
from moomoo import OpenQuoteContext, RET_OK, KLType, AuType, SubType

tz_ny = pytz.timezone("America/New_York")
DATA_DIR = './market_data'
os.makedirs(DATA_DIR, exist_ok=True)

TARGETS = [
    {"code": "US.QQQ", "yf_sym": "QQQ", "name": "納指 ETF"},
    {"code": "CC.BTCUSD", "yf_sym": "BTC-USD", "name": "比特幣"}
]

def fetch_history_opend(quote_ctx, code: str, ktype: KLType, days_back: int, count: int) -> pd.DataFrame:
    now_ny = datetime.datetime.now(tz_ny)
    start_str = (now_ny - datetime.timedelta(days=days_back)).strftime("%Y-%m-%d")
    end_str = now_ny.strftime("%Y-%m-%d")
    try:
        ret, df_k, msg = quote_ctx.request_history_kline(
            code=code, start=start_str, end=end_str, ktype=ktype, autype=AuType.NONE, max_count=count
        )
        if ret == RET_OK and not df_k.empty:
            df = df_k[['time_key', 'open', 'close', 'high', 'low', 'volume']].copy()
            df['time_key'] = pd.to_datetime(df['time_key'])
            return df.sort_values('time_key').reset_index(drop=True)
    except Exception:
        pass
    return pd.DataFrame()

def fetch_5m_full_stream(quote_ctx, code: str, yf_sym: str) -> pd.DataFrame:
    """抓取包含盤前盤後的 5M 數據 (優先 OpenD，備援 yfinance)"""
    # 1. 嘗試 OpenD 5M
    now_ny = datetime.datetime.now(tz_ny)
    start_str = (now_ny - datetime.timedelta(days=20)).strftime("%Y-%m-%d")
    end_str = now_ny.strftime("%Y-%m-%d")
    try:
        quote_ctx.subscribe([code], [SubType.K_5M])
        time.sleep(0.3)
        ret, df_k, _ = quote_ctx.request_history_kline(
            code=code, start=start_str, end=end_str, ktype=KLType.K_5M, autype=AuType.NONE, max_count=3000
        )
        if ret == RET_OK and not df_k.empty:
            df = df_k[['time_key', 'open', 'close', 'high', 'low', 'volume']].copy()
            df['time_key'] = pd.to_datetime(df['time_key'])
            return df.sort_values('time_key').reset_index(drop=True)
    except Exception:
        pass

    # 2. 備援 yfinance 5M
    try:
        df_yf = yf.download(tickers=yf_sym, period="1mo", interval="5m", prepost=True, progress=False, auto_adjust=False)
        if not df_yf.empty:
            df_yf.columns = [c[0].lower() if isinstance(df_yf.columns, pd.MultiIndex) else c.lower() for c in df_yf.columns]
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

def run_sync():
    print("🚀 【全週期數據同步啟動】正在獲取 WEEK, DAY, 1Hr, 5M 全量連續基座...")
    quote_ctx = None
    try:
        quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    except Exception as e:
        print(f"⚠️ OpenD 未連線或離線: {e}，將啟用 yfinance 備援...")

    for item in TARGETS:
        code = item["code"]
        clean_code = code.replace('.', '_')
        yf_sym = item["yf_sym"]
        print(f"\n[*] 正在同步標的: {code} ({item['name']})")

        # 1. 抓取 5M 全時段原始流
        df_5m = fetch_5m_full_stream(quote_ctx, code, yf_sym) if quote_ctx else pd.DataFrame()
        if not df_5m.empty:
            df_5m.to_csv(os.path.join(DATA_DIR, f"{clean_code}_5M.csv"), index=False)
            print(f"  ✅ [5M 落盤成功] {len(df_5m)} 根 (含盤前盤後)")

            # 2. 本地重採樣為全時段連續 1Hr
            df_temp = df_5m.copy().set_index('time_key')
            df_1h = df_temp.resample('1h', closed='left', label='left').agg({
                'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
            }).dropna().reset_index()
            df_1h.to_csv(os.path.join(DATA_DIR, f"{clean_code}_1Hr.csv"), index=False)
            print(f"  ✅ [1Hr 重採樣成功] {len(df_1h)} 根 (連續不跳空)")
        else:
            print(f"  ❌ 5M / 1Hr 拉取失敗")

        # 3. 日線 (DAY)
        df_day = fetch_history_opend(quote_ctx, code, KLType.K_DAY, 365, 250) if quote_ctx else pd.DataFrame()
        if not df_day.empty:
            df_day.to_csv(os.path.join(DATA_DIR, f"{clean_code}_DAY.csv"), index=False)
            print(f"  ✅ [DAY 日線落盤] {len(df_day)} 根")

        # 4. 週線 (WEEK)
        df_week = fetch_history_opend(quote_ctx, code, KLType.K_WEEK, 750, 100) if quote_ctx else pd.DataFrame()
        if not df_week.empty:
            df_week.to_csv(os.path.join(DATA_DIR, f"{clean_code}_WEEK.csv"), index=False)
            print(f"  ✅ [WEEK 週線落盤] {len(df_week)} 根")

    if quote_ctx:
        try: quote_ctx.close()
        except: pass
    print("\n🎉 【數據同步完畢】所有 CSV 檔案已沉澱至 ./market_data/！")

if __name__ == "__main__":
    run_sync()
