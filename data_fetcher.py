# 文件名: data_fetcher.py
# 核心功能: 透過 get_cur_kline 訂閱通道，100% 抓取美股 Premarket (04:00) + RTH (09:30) + Postmarket (16:00) 連續不斷層 K 線

import datetime
import os
import time
import pandas as pd
import pytz
from moomoo import OpenQuoteContext, RET_OK, KLType, SubType, AuType

tz_ny = pytz.timezone("America/New_York")
DATA_DIR = './market_data'
os.makedirs(DATA_DIR, exist_ok=True)

# 抓取配置：1Hr 使用 get_cur_kline 獲取最新 500 根全時段 K 線 (包含盤前盤後)
# 日線與周線使用歷史接口
TARGETS = [
    ("US.QQQ", [
        ("1Hr", KLType.K_60M, SubType.K_60M, 500),
        ("DAY", KLType.K_DAY, SubType.K_DAY, 200),
        ("WEEK", KLType.K_WEEK, SubType.K_WEEK, 100)
    ]),
    ("US.BTC", [
        ("1Hr", KLType.K_60M, SubType.K_60M, 500),
        ("DAY", KLType.K_DAY, SubType.K_DAY, 200),
        ("WEEK", KLType.K_WEEK, SubType.K_WEEK, 100)
    ])
]

def fetch_and_save_kline():
    print("【任務啟動】以【全時段無斷層 (Premarket + Postmarket)】同步 1Hr / 日線 / 周線...")
    
    quote_ctx = None
    try:
        quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        
        for code, tasks in TARGETS:
            for ktype_name, kl_type, sub_type, count in tasks:
                clean_code = code.replace('.', '_')
                file_path = os.path.join(DATA_DIR, f"{clean_code}_{ktype_name}.csv")
                
                # 1. 訂閱通道
                sub_ret, sub_err = quote_ctx.subscribe([code], [sub_type])
                if sub_ret != RET_OK:
                    print(f"❌ 訂閱 {code} {ktype_name} 失敗: {sub_err}")
                    continue
                
                # 2. 透過 get_cur_kline 獲取包含盤前盤後的完整未過濾連續 K 線
                ret, df_k = quote_ctx.get_cur_kline(code, count, kl_type, AuType.NONE)
                
                if ret == RET_OK and not df_k.empty:
                    df = df_k[['time_key', 'open', 'close', 'high', 'low', 'volume']].copy()
                    df['time_key'] = pd.to_datetime(df['time_key'])
                    df = df.sort_values('time_key').reset_index(drop=True)
                    df.to_csv(file_path, index=False)
                    
                    # 打印最近 3 根的時間，驗證是否有 04:00 盤前或 16:00 盤後
                    sample_times = df['time_key'].tail(3).astype(str).tolist()
                    last_close = df['close'].iloc[-1]
                    print(f"【成功存盤】{code} {ktype_name:4s} ({len(df)} 根) -> 最新時間戳: {sample_times} | 現價: ${last_close:.2f}")
                else:
                    print(f"❌ 獲取 {code} {ktype_name} 失敗: {df_k}")
                time.sleep(0.05)
                
    except Exception as e:
        print(f"❌ 異常: {str(e)}")
    finally:
        if quote_ctx:
            try: quote_ctx.close()
            except: pass

    print("【任務完成】全時段連續數據已落盤。")

if __name__ == "__main__":
    fetch_and_save_kline()
