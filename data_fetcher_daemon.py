# 文件名: data_fetcher_daemon.py
# 核心職責: 【獨立後台守護進程 · 每 5 分鐘收盤定格時拉取 48 根官方原生 5M 柱並寫入 CSV】

import os
import time
import datetime
import pandas as pd
import pytz

tz_my = pytz.timezone("Asia/Kuala_Lumpur")
tz_ny = pytz.timezone("America/New_York")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gui_water', 'market_data')
os.makedirs(DATA_DIR, exist_ok=True)
HEALTH_LOG_FILE = os.path.join(DATA_DIR, 'system_health.log')

def log_health(msg: str):
    now_my = datetime.datetime.now(tz_my).strftime('%Y-%m-%d %H:%M:%S MYT')
    line = f"[{now_my}] {msg}\n"
    lines = []
    if os.path.exists(HEALTH_LOG_FILE):
        try:
            with open(HEALTH_LOG_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            lines = []
    lines.append(line)
    if len(lines) > 30:
        lines = lines[-30:]
    try:
        with open(HEALTH_LOG_FILE, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    except Exception:
        pass

def fetch_and_save(code="CC.BTCUSD"):
    try:
        from futu import OpenQuoteContext, KLType, SubType, AuType
        ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        ctx.subscribe([code], [SubType.K_5M])
        # 抓取 48 根 (4小時) 官方原生不復權 5M 柱
        ret, df = ctx.get_cur_kline(code, 48, KLType.K_5M, AuType.NONE)
        ctx.close()
        if ret == 0 and not df.empty:
            df.columns = [c.lower() for c in df.columns]
            clean_code = code.replace('.', '_')
            csv_path = os.path.join(DATA_DIR, f"{clean_code}_5M.csv")
            df.to_csv(csv_path, index=False)
            last_bar_time = df.iloc[-1]['time_key']
            last_close = df.iloc[-1]['close']
            log_health(f"🟢 [官方 5M 對齊成功] 標的: {code} | 最新收盤柱: {last_bar_time} | 最新價: ${last_close:,.2f} | 共 48 根")
            print(f"[{datetime.datetime.now(tz_my).strftime('%H:%M:%S')}] 官方數據寫入成功: {last_bar_time} (收盤: ${last_close:,.2f})")
        else:
            log_health(f"🟡 [請求等待中] 標的: {code} | ret: {ret}")
    except Exception as e:
        log_health(f"🔴 [連線異常] {str(e)}")

if __name__ == "__main__":
    print("🚀 5M 官方原生數據守護進程啟動中 (48 根跨度 · 100% 對齊 Moomoo)...")
    fetch_and_save("CC.BTCUSD")
    while True:
        now = datetime.datetime.now(tz_my)
        curr_sec = now.minute * 60 + now.second
        rem_sec = 300 - (curr_sec % 300)
        if rem_sec == 300:
            rem_sec = 0
        
        # 換棒後等待 2.5 秒，確保伺服器完成封裝
        sleep_time = rem_sec + 2.5
        time.sleep(sleep_time)
        fetch_and_save("CC.BTCUSD")
