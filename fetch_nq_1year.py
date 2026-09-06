# 文件名: fetch_nq_1year.py
import os
import time
import datetime
import pandas as pd
import pytz
from moomoo import OpenQuoteContext, RET_OK, KLType, AuType

tz_ny = pytz.timezone("America/New_York")
DATA_DIR = './market_data'
os.makedirs(DATA_DIR, exist_ok=True)

def download_1year_data():
    print("🚀 [開始下載] 正在拉取 1 年期 1H 歷史數據...")
    now_ny = datetime.datetime.now(tz_ny)
    end_date = now_ny.strftime("%Y-%m-%d")
    start_date = (now_ny - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    all_dfs = []
    page_req_key = None
    page = 1
    
    while True:
        print(f"[*] 正在拉取第 {page} 頁 1H 數據...")
        ret, data, page_req_key = quote_ctx.request_history_kline(
            code="US.QQQ",
            start=start_date,
            end=end_date,
            ktype=KLType.K_60M,
            autype=AuType.NONE,
            max_count=1000,
            page_req_key=page_req_key
        )
        
        if ret == RET_OK:
            if not data.empty:
                all_dfs.append(data)
                print(f"    -> 成功獲取 {len(data)} 根 K 線")
            if page_req_key is None:
                break
            page += 1
            time.sleep(0.35)
        else:
            print(f"❌ 拉取失敗: {data}")
            break
            
    quote_ctx.close()
    
    if all_dfs:
        df_full = pd.concat(all_dfs, ignore_index=True)
        df_full.columns = [c.lower() for c in df_full.columns]
        df_full = df_full.drop_duplicates(subset=['time_key']).sort_values('time_key').reset_index(drop=True)
        
        file_path_nq = os.path.join(DATA_DIR, "US_NQmain_1Hr.csv")
        file_path_qqq = os.path.join(DATA_DIR, "US_QQQ_1Hr.csv")
        df_full.to_csv(file_path_nq, index=False)
        df_full.to_csv(file_path_qqq, index=False)
        print(f"🎉 成功存檔！已寫入 {len(df_full)} 根 1H K 線至 ./market_data/")
    else:
        print("❌ 未獲取到數據，請確認 OpenD 連線。")

if __name__ == "__main__":
    download_1year_data()
