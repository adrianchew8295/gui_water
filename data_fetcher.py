# 文件名: data_fetcher.py
# 核心功能: 專門以美東時間 (America/New_York) 抓取包含盤前 (04:00) / 常規 (09:30) / 盤後 (16:00) 的連續 1Hr 數據

import datetime
import os
import time
import pandas as pd
import pytz
from moomoo import OpenQuoteContext, RET_OK, KLType, AuType

tz_ny = pytz.timezone("America/New_York")
DATA_DIR = './market_data'
os.makedirs(DATA_DIR, exist_ok=True)

# 抓取清單：1Hr 抓取最近 30 天 (覆蓋完整盤前 04:00 - 盤後 20:00)
TARGETS = [
    ("US.QQQ", [
        ("1Hr", KLType.K_60M, 30, 800),
        ("DAY", KLType.K_DAY, 250, 200),
        ("WEEK", KLType.K_WEEK, 700, 100)
    ]),
    ("US.BTC", [
        ("1Hr", KLType.K_60M, 30, 800),
        ("DAY", KLType.K_DAY, 250, 200),
        ("WEEK", KLType.K_WEEK, 700, 100)
    ])
]

def fetch_and_save_kline():
    print("【任務啟動】以【美東時區 + 全時段連續 (Extended Hours)】同步數據...")
    now_ny = datetime.datetime.now(tz_ny)
    end_date_str = now_ny.strftime("%Y-%m-%d")

    quote_ctx = None
    try:
        quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        
        for code, tasks in TARGETS:
            for ktype_name, ktype_enum, days_back, count in tasks:
                clean_code = code.replace('.', '_')
                file_path = os.path.join(DATA_DIR, f"{clean_code}_{ktype_name}.csv")
                start_date_str = (now_ny - datetime.timedelta(days=days_back)).strftime("%Y-%m-%d")
                
                ret, df_k, msg = quote_ctx.request_history_kline(
                    code=code,
                    start=start_date_str,
                    end=end_date_str,
                    ktype=ktype_enum,
                    autype=AuType.NONE,
                    max_count=count
                )
                
                if ret == RET_OK and not df_k.empty:
                    df = df_k[['time_key', 'open', 'close', 'high', 'low', 'volume']].copy()
                    df['time_key'] = pd.to_datetime(df['time_key'])
                    df = df.sort_values('time_key').reset_index(drop=True)
                    df.to_csv(file_path, index=False)
                    
                    last_time = df['time_key'].iloc[-1]
                    last_close = df['close'].iloc[-1]
                    print(f"【成功存盤】{code} {ktype_name:4s} ({len(df)} 根) -> 最新時間: {last_time} | 現價: ${last_close:.2f}")
                else:
                    print(f"❌ 拉取 {code} {ktype_name} 失敗: {msg}")
                time.sleep(0.05)
                
    except Exception as e:
        print(f"❌ 異常: {str(e)}")
    finally:
        if quote_ctx:
            try: quote_ctx.close()
            except: pass

    print("【任務完成】全時段連續歷史數據已沉澱至本地備份。")

if __name__ == "__main__":
    fetch_and_save_kline()
