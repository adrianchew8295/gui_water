# 文件名: data_fetcher.py
# 核心功能: 使用 get_cur_kline 倒推獲取當前 2026 年 9 月最新 K 線，徹底解決 1 月截斷問題

import os
import time
import pandas as pd
from moomoo import OpenQuoteContext, RET_OK, KLType, SubType

DATA_DIR = './market_data'
os.makedirs(DATA_DIR, exist_ok=True)

# 抓取清單：配置獲取最新 N 根 K 線 (由現在往過去倒推)
TARGETS = [
    ("US.QQQ", [
        ("1Hr", KLType.K_60M, SubType.K_60M, 300),   # 最新 300 根 1 小時 K 線 (覆蓋最近 40 天直至當下)
        ("DAY", KLType.K_DAY, SubType.K_DAY, 200),    # 最新 200 根日線
        ("WEEK", KLType.K_WEEK, SubType.K_WEEK, 100)  # 最新 100 根周線
    ]),
    ("US.BTC", [
        ("1Hr", KLType.K_60M, SubType.K_60M, 300),
        ("DAY", KLType.K_DAY, SubType.K_DAY, 200),
        ("WEEK", KLType.K_WEEK, SubType.K_WEEK, 100)
    ])
]

def fetch_and_save_kline():
    print("【任務啟動】以【get_cur_kline 倒推模式】同步 2026 年 9 月最新數據基座...")
    
    quote_ctx = None
    try:
        quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        
        for code, tasks in TARGETS:
            for ktype_name, kl_type, sub_type, count in tasks:
                clean_code = code.replace('.', '_')
                file_path = os.path.join(DATA_DIR, f"{clean_code}_{ktype_name}.csv")
                
                # 1. 訂閱相應 K 線類型
                sub_ret, sub_err = quote_ctx.subscribe([code], [sub_type])
                if sub_ret != RET_OK:
                    print(f"❌ 訂閱 {code} {ktype_name} 失敗: {sub_err}")
                    continue
                
                # 2. 獲取最新倒推 K 線 (保證抓到 9 月最新跳動)
                ret, df_k = quote_ctx.get_cur_kline(code, count, kl_type)
                
                if ret == RET_OK and not df_k.empty:
                    df_clean = df_k[['time_key', 'open', 'close', 'high', 'low', 'volume']].copy()
                    df_clean.to_csv(file_path, index=False)
                    last_time = df_clean['time_key'].iloc[-1]
                    last_close = df_clean['close'].iloc[-1]
                    print(f"【成功存盤】{code} {ktype_name:4s} -> 最新記錄: {last_time} | 最新價: ${last_close:.2f}")
                else:
                    print(f"❌ 獲取 {code} {ktype_name} 失敗: {df_k}")
                
                time.sleep(0.05)
                
    except Exception as e:
        print(f"❌ 運行異常: {str(e)}")
    finally:
        if quote_ctx:
            try:
                quote_ctx.close()
            except:
                pass

    print("【任務完成】2026 年 9 月最新真實數據同步完畢。")

if __name__ == "__main__":
    fetch_and_save_kline()
