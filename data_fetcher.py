# 文件名: data_fetcher.py
import datetime
import os
import time
import pytz
from moomoo import OpenQuoteContext, RET_OK, KLType, AuType

tz_ny = pytz.timezone("America/New_York")
DATA_DIR = './market_data'
os.makedirs(DATA_DIR, exist_ok=True)

TARGETS = [
    ("US.QQQ", [("DAY", KLType.K_DAY, 120), ("WEEK", KLType.K_WEEK, 60), ("1Hr", KLType.K_60M, 240)]),
    ("US.BTC", [("DAY", KLType.K_DAY, 120), ("WEEK", KLType.K_WEEK, 60), ("1Hr", KLType.K_60M, 240)])
]

def fetch_and_save_kline():
    print("【任務啟動】開始同步 1Hr / 日線 / 周線 歷史數據基座...")
    today = datetime.datetime.now(tz_ny).date()
    start_date = (today - datetime.timedelta(days=180)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")

    for code, tasks in TARGETS:
        for ktype_name, ktype_enum, count in tasks:
            clean_code = code.replace('.', '_')
            file_path = os.path.join(DATA_DIR, f"{clean_code}_{ktype_name}.csv")
            
            quote_ctx = None
            try:
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
                    df_k.to_csv(file_path, index=False)
                    print(f"【成功存盤】標的 {code} 的 {ktype_name} 數據已保存至: {file_path}")
                else:
                    print(f"❌ 拉取 {code} {ktype_name} 失敗: {msg}")
            except Exception as e:
                print(f"❌ 異常: {e}")
            finally:
                if quote_ctx:
                    try: quote_ctx.close()
                    except: pass
            time.sleep(0.1)

    print("【任務完成】所有週期歷史數據同步完畢。")

if __name__ == "__main__":
    fetch_and_save_kline()
