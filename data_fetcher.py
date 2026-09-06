# 文件名: data_fetcher.py
# 核心功能: 專為 QQQ 打造的多週期歷史數據引擎 (Weekly, Daily, 1Hr, 5M)

import os
import time
import datetime
import pandas as pd
import pytz
from moomoo import OpenQuoteContext, RET_OK, KLType, AuType

tz_ny = pytz.timezone("America/New_York")
DATA_DIR = './market_data'
os.makedirs(DATA_DIR, exist_ok=True)

TARGET_CODE = "US.QQQ"

def fetch_qqq_multi_timeframe():
    print(f"🚀 [多週期數據引擎] 開始拉取 {TARGET_CODE} 的完整歷史基座...")
    
    try:
        quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    except Exception as e:
        print(f"❌ 無法連接 OpenD，請確認本地網關是否已啟動並登入！錯誤: {e}")
        return

    now_ny = datetime.datetime.now(tz_ny)
    end_date = now_ny.strftime("%Y-%m-%d")
    
    # 時間跨度定義
    start_date_1yr = (now_ny - datetime.timedelta(days=365)).strftime("%Y-%m-%d") # 周線、日線、1小時 (1年)
    start_date_10d = (now_ny - datetime.timedelta(days=15)).strftime("%Y-%m-%d")  # 5分鐘 (最近10-15天高頻)

    timeframes = [
        {"name": "WEEK (週線)", "ktype": KLType.K_WEEK, "start": start_date_1yr, "suffix": "_WEEK.csv"},
        {"name": "DAY (日線)", "ktype": KLType.K_DAY, "start": start_date_1yr, "suffix": "_DAY.csv"},
        {"name": "1Hr (1小時)", "ktype": KLType.K_60M, "start": start_date_1yr, "suffix": "_1Hr.csv"},
        {"name": "5M (5分鐘)", "ktype": KLType.K_5M, "start": start_date_10d, "suffix": "_5M.csv"}
    ]

    clean_code = TARGET_CODE.replace('.', '_')

    for tf in timeframes:
        print(f"\n[*] 正在拉取 {TARGET_CODE} 專屬 {tf['name']} 數據...")
        all_dfs = []
        page_req_key = None
        page = 1
        
        while True:
            ret, data, page_req_key = quote_ctx.request_history_kline(
                code=TARGET_CODE,
                start=tf["start"],
                end=end_date,
                ktype=tf["ktype"],
                autype=AuType.NONE,
                max_count=1000,
                page_req_key=page_req_key
            )
            
            if ret == RET_OK:
                if not data.empty:
                    all_dfs.append(data)
                    print(f"    -> 成功獲取第 {page} 頁 ({len(data)} 根 K 線)")
                if page_req_key is None:
                    break
                page += 1
                time.sleep(0.3)
            else:
                print(f"❌ {tf['name']} 拉取失敗: {data}")
                break
                
        if all_dfs:
            df_full = pd.concat(all_dfs, ignore_index=True)
            df_full.columns = [c.lower() for c in df_full.columns]
            df_full = df_full.drop_duplicates(subset=['time_key']).sort_values('time_key').reset_index(drop=True)
            
            file_path = os.path.join(DATA_DIR, f"{clean_code}{tf['suffix']}")
            df_full.to_csv(file_path, index=False)
            print(f"✅ {tf['name']} 存檔成功！已寫入 {len(df_full)} 根 K 線至: {file_path}")
        else:
            print(f"⚠️ {tf['name']} 未獲取到有效數據。")

    quote_ctx.close()
    print("\n🎉 [多週期數據引擎] QQQ 四大週期歷史基座全部落盤完畢！")

if __name__ == "__main__":
    fetch_qqq_multi_timeframe()
