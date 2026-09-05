# 文件名: data_fetcher.py
# 核心功能: 專門負責連接 OpenD 網關，以真實原始價格 (AuType.NONE) 同步 1Hr / 日線 / 周線 數據

import datetime
import os
import time
import pytz
from moomoo import OpenQuoteContext, RET_OK, KLType, AuType

tz_ny = pytz.timezone("America/New_York")
DATA_DIR = './market_data'
os.makedirs(DATA_DIR, exist_ok=True)

# 抓取清單：配置充足的歷史根數，確保涵蓋到當前 9 月最新交易日
TARGETS = [
    ("US.QQQ", [
        ("DAY", KLType.K_DAY, 250),      # 日線 250 根 (約 1 年)
        ("WEEK", KLType.K_WEEK, 100),    # 周線 100 根 (約 2 年)
        ("1Hr", KLType.K_60M, 600)       # 1小時 600 根 (約最近 45-60 天)
    ]),
    ("US.BTC", [
        ("DAY", KLType.K_DAY, 250),
        ("WEEK", KLType.K_WEEK, 100),
        ("1Hr", KLType.K_60M, 600)
    ])
]

def fetch_and_save_kline():
    print("【任務啟動】開始以【真實原始價格 (AuType.NONE)】同步歷史數據基座...")
    today = datetime.datetime.now(tz_ny).date()
    # 設置起點覆蓋足夠的時間窗口
    start_date = (today - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")

    for code, tasks in TARGETS:
        for ktype_name, ktype_enum, count in tasks:
            clean_code = code.replace('.', '_')
            file_path = os.path.join(DATA_DIR, f"{clean_code}_{ktype_name}.csv")
            
            quote_ctx = None
            try:
                quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
                
                # 請求歷史 K 線 (不復權以確保與盤口真實現價一致)
                ret, df_k, msg = quote_ctx.request_history_kline(
                    code=code,
                    start=start_date,
                    end=end_date,
                    ktype=ktype_enum,
                    autype=AuType.NONE,
                    max_count=count
                )
                
                if ret == RET_OK and not df_k.empty:
                    df_k = df_k[['time_key', 'open', 'close', 'high', 'low', 'volume']]
                    df_k.to_csv(file_path, index=False)
                    last_time = df_k['time_key'].iloc[-1]
                    last_close = df_k['close'].iloc[-1]
                    print(f"【成功存盤】{code} {ktype_name:4s} -> 最新記錄: {last_time} | 價格: ${last_close:.2f}")
                else:
                    print(f"❌ 拉取 {code} {ktype_name} 失敗: {msg}")
            except Exception as e:
                print(f"❌ 異常: {str(e)}")
            finally:
                if quote_ctx:
                    try:
                        quote_ctx.close()
                    except:
                        pass
            time.sleep(0.1)

    print("【任務完成】所有週期數據已落盤沉澱至本地備份。")

if __name__ == "__main__":
    fetch_and_save_kline()
