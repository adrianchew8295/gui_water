# 文件名: live_stream_engine.py
# 核心功能: 基於 OpenD Push Handler 監聽 1Hr (及未來 5M) 實時 K 線流，自動合成盤前/盤後數據

import os
import threading
import time
import pandas as pd
from moomoo import OpenQuoteContext, CurKlineHandlerBase, KLType, SubType, RET_OK

DATA_DIR = './market_data'
os.makedirs(DATA_DIR, exist_ok=True)

class RealtimeKlineHandler(CurKlineHandlerBase):
    def __init__(self, code: str, ktype_name: str):
        super().__init__()
        self.code = code
        self.ktype_name = ktype_name
        self.clean_code = code.replace('.', '_')
        self.file_path = os.path.join(DATA_DIR, f"{self.clean_code}_{self.ktype_name}.csv")

    def on_recv_rsp(self, rsp_pb):
        ret_code, df_k = super().on_recv_rsp(rsp_pb)
        if ret_code == RET_OK and not df_k.empty:
            df_k = df_k[['time_key', 'open', 'close', 'high', 'low', 'volume']].copy()
            df_k['time_key'] = pd.to_datetime(df_k['time_key'])
            
            # 若本地已有 CSV，進行去重合併 (Upsert)
            if os.path.exists(self.file_path):
                try:
                    df_old = pd.read_csv(self.file_path)
                    df_old['time_key'] = pd.to_datetime(df_old['time_key'])
                    df_all = pd.concat([df_old, df_k]).drop_duplicates(subset=['time_key'], keep='last')
                    df_all = df_all.sort_values('time_key').reset_index(drop=True)
                    df_all.to_csv(self.file_path, index=False)
                except Exception as e:
                    print(f"❌ 追加 K 線異常: {e}")
            else:
                df_k.to_csv(self.file_path, index=False)
            
            last_t = df_k['time_key'].iloc[-1]
            last_c = df_k['close'].iloc[-1]
            print(f"⚡ [Push 流推送] {self.code} {self.ktype_name} 收到新 K 線: {last_t} | 現價: ${last_c:.2f}")

def start_push_stream_service(target_code="US.QQQ"):
    """後台線程啟動 OpenD Push 監聽器"""
    def _worker():
        ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        handler_1h = RealtimeKlineHandler(target_code, "1Hr")
        ctx.set_handler(handler_1h)
        
        # 訂閱 1 小時 K 線推送
        ret, err = ctx.subscribe([target_code], [SubType.K_60M])
        if ret == RET_OK:
            print(f"✅ [Push Handler] 成功訂閱 {target_code} 1Hr 全時段推送通道。")
        else:
            print(f"❌ 訂閱推送失敗: {err}")
            
        while True:
            time.sleep(1)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

if __name__ == "__main__":
    print("啟動 Push Handler 獨立測試...")
    start_push_stream_service("US.QQQ")
    while True:
        time.sleep(1)
