import os
import pandas as pd
from futu import OpenQuoteContext, KLType, SubType, RET_OK

# ==============================================================================
# 配置區域 (可根據主子需求調整標的與本地存儲路徑)
# ==============================================================================
HOST = '127.0.0.1'
PORT = 11111
WATCHLIST = ['US.QQQ', 'US.BTC']
DATA_DIR = './market_data'

# ==============================================================================
# 核心數據引擎類 (獨立插件，專注於歷史大週期數據拉取與存儲)
# ==============================================================================
class HistoryDataEngine:
    def __init__(self, host: str = HOST, port: int = PORT, save_dir: str = DATA_DIR):
        self.host = host
        self.port = port
        self.save_dir = save_dir
        self._ensure_dir()

    def _ensure_dir(self):
        try:
            if not os.path.exists(self.save_dir):
                os.makedirs(self.save_dir)
        except Exception as e:
            print(f"【系統提示】創建本地數據目錄失敗: {str(e)}")

    def fetch_and_save_kline(self, code: str, ktype: KLType, count: int = 500) -> bool:
        quote_ctx = None
        ktype_name = "DAY" if ktype == KLType.K_DAY else "WEEK"
        try:
            quote_ctx = OpenQuoteContext(host=self.host, port=self.port)
            
            # 第一步：訂閱 K 線類型
            sub_ret, sub_err = quote_ctx.subscribe([code], [SubType.K_DAY if ktype == KLType.K_DAY else SubType.K_WEEK])
            if sub_ret != RET_OK:
                print(f"【訂閱報錯】標的 {code} 訂閱 {ktype_name} 失敗: {sub_err}")
                return False

            # 第二步：拉取歷史 K 線數據
            ret, data, page_req_key = quote_ctx.get_cur_kline(code, count, ktype)
            if ret != RET_OK:
                print(f"【獲取報錯】標的 {code} 拉取 {ktype_name} 失敗: {data}")
                return False

            # 第三步：數據清洗與標準化
            df = data[['time_key', 'open', 'close', 'high', 'low', 'volume', 'pe_ratio', 'turnover_rate']].copy()
            
            # 第四步：本地落盤存儲
            clean_code = code.replace('.', '_')
            file_path = os.path.join(self.save_dir, f"{clean_code}_{ktype_name}.csv")
            df.to_csv(file_path, index=False)
            print(f"【成功存盤】標的 {code} 的 {ktype_name} 數據已保存至: {file_path}")
            return True

        except Exception as e:
            print(f"【運行異常】處理 {code} 時發生未預期錯誤: {str(e)}")
            return False
        finally:
            if quote_ctx:
                quote_ctx.close()

    def run_batch_sync(self):
        print("【任務啟動】開始同步周線與日線歷史數據基座...")
        for code in WATCHLIST:
            # 同步日線
            self.fetch_and_save_kline(code=code, ktype=KLType.K_DAY, count=500)
            # 同步周線
            self.fetch_and_save_kline(code=code, ktype=KLType.K_WEEK, count=200)
        print("【任務完成】所有標的歷史數據同步完畢。")


if __name__ == '__main__':
    engine = HistoryDataEngine()
    engine.run_batch_sync()
