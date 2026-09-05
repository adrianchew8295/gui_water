import os
import pandas as pd
import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts

class ChartPlugin:
    def __init__(self, data_dir: str = './market_data'):
        self.data_dir = data_dir

    def load_local_data(self, code: str, ktype_name: str) -> pd.DataFrame:
        try:
            clean_code = code.replace('.', '_')
            file_path = os.path.join(self.data_dir, f"{clean_code}_{ktype_name}.csv")
            if not os.path.exists(file_path):
                st.warning(f"未找到本地數據文件：{file_path}，請先同步數據。")
                return pd.DataFrame()
            df = pd.read_csv(file_path)
            return df
        except Exception as e:
            st.error(f"讀取數據失敗: {str(e)}")
            return pd.DataFrame()

    def render_chart(self, code: str, ktype_name: str):
        try:
            df = self.load_local_data(code, ktype_name)
            if df.empty:
                return

            df['time_clean'] = df['time_key'].astype(str).str.slice(0, 10)
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

            chart_options = {
                "height": 600,
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
            st.error(f"圖表渲染失敗: {str(e)}")
