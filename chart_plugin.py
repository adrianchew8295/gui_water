import os
import pandas as pd
import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts

class ChartPlugin:
    def __init__(self, data_dir: str = './market_data'):
        self.data_dir = data_dir

    def load_local_data(self, code: str, ktype_name: str) -> pd.DataFrame:
        clean_code = code.replace('.', '_')
        file_path = os.path.join(self.data_dir, f"{clean_code}_{ktype_name}.csv")
        
        if not os.path.exists(file_path):
            st.error(f"❌ 找不到本地數據檔案：`{file_path}`")
            st.info("💡 請先在終端機執行 `python data_fetcher.py` 下載歷史 K 線數據！")
            return pd.DataFrame()
            
        try:
            df = pd.read_csv(file_path)
            # 欄位統一轉為小寫相容
            df.columns = [c.lower() for c in df.columns]
            return df
        except Exception as e:
            st.error(f"❌ 讀取數據異常: {str(e)}")
            return pd.DataFrame()

    def render_chart(self, code: str, ktype_name: str):
        df = self.load_local_data(code, ktype_name)
        if df.empty:
            return

        try:
            # 整理時間欄位 (相容 time_key / date)
            time_col = 'time_key' if 'time_key' in df.columns else ('date' if 'date' in df.columns else df.columns[0])
            df['time_clean'] = df[time_col].astype(str).str.slice(0, 10)
            df = df.drop_duplicates(subset=['time_clean']).sort_values('time_clean')

            candles = []
            for _, row in df.iterrows():
                candles.append({
                    "time": str(row['time_clean']),
                    "open": float(row['open']),
                    "high": float(row['high']),
                    "low": float(row['low']),
                    "close": float(row['close'])
                })

            if not candles:
                st.warning("⚠️ K 線轉換後為空，請檢查 CSV 數據內容。")
                return

            chart_options = {
                "height": 550,
                "layout": {
                    "textColor": "#d1d4dc",
                    "background": {"type": "solid", "color": "#131722"}
                },
                "grid": {
                    "vertLines": {"color": "#242732"},
                    "horzLines": {"color": "#242732"}
                },
                "crosshair": {"mode": 1},
                "timeScale": {
                    "timeVisible": True,
                    "secondsVisible": False,
                    "borderColor": "#2b2b43"
                },
                "rightPriceScale": {
                    "borderColor": "#2b2b43",
                    "autoScale": True
                },
                "handleScroll": {
                    "mouseWheel": True,
                    "pressedMouseMove": True,
                    "horzTouchDrag": True,
                    "vertTouchDrag": True
                },
                "handleScale": {
                    "axisPressedMouseMove": True,
                    "mouseWheel": True,
                    "pinch": True
                }
            }

            series_data = [
                {
                    "type": "Candlestick",
                    "data": candles,
                    "options": {
                        "upColor": "#089981",
                        "downColor": "#f23645",
                        "borderVisible": False,
                        "wickUpColor": "#089981",
                        "wickDownColor": "#f23645"
                    }
                }
            ]

            renderLightweightCharts([{"chart": chart_options, "series": series_data}], key=f"tv_{code}_{ktype_name}")

        except Exception as e:
            st.error(f"❌ 圖表渲染失敗: {str(e)}")
