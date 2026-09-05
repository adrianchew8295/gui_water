import os
import pandas as pd
import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts

# ==============================================================================
# 專業級金融圖表渲染插件 (升級版：全屏高幀率流暢交互)
# ==============================================================================
class ChartPlugin:
    def __init__(self, data_dir: str = './market_data'):
        self.data_dir = data_dir

    def load_local_data(self, code: str, ktype_name: str) -> pd.DataFrame:
        """從本地數據庫讀取指定的歷史數據"""
        try:
            clean_code = code.replace('.', '_')
            file_path = os.path.join(self.data_dir, f"{clean_code}_{ktype_name}.csv")
            if not os.path.exists(file_path):
                st.warning(f"未找到本地數據文件：{file_path}，請先運行數據引擎同步數據。")
                return pd.DataFrame()
            df = pd.read_csv(file_path)
            return df
        except Exception as e:
            st.error(f"讀取本地數據異常: {str(e)}")
            return pd.DataFrame()

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """技術指標計算通道 (預留給麥語言轉譯指標)"""
        try:
            if df.empty:
                return df
            df['MA20'] = df['close'].rolling(window=20).mean()
            return df
        except Exception as e:
            st.error(f"指標計算異常: {str(e)}")
            return df

    def render_chart(self, code: str, ktype_name: str):
        """渲染媲美專業終端的高級圖表"""
        try:
            df = self.load_local_data(code, ktype_name)
            if df.empty:
                return

            df = self.calculate_indicators(df)

            candles = []
            ma_data = []

            for _, row in df.iterrows():
                time_entry = str(row['time_key'])
                candles.append({
                    "time": time_entry,
                    "open": float(row['open']),
                    "high": float(row['high']),
                    "low": float(row['low']),
                    "close": float(row['close'])
                })

                if 'MA20' in row and pd.notna(row['MA20']):
                    ma_data.append({
                        "time": time_entry,
                        "value": float(row['MA20'])
                    })

            # 高級金融終端配置 (開啟極致絲滑滾輪與手勢交互)
            chart_options = {
                "height": 650,
                "layout": {
                    "textColor": "#d1d4dc",
                    "background": {"type": "solid", "color": "#0d1117"},
                    "fontSize": 12,
                    "fontFamily": "Roboto, sans-serif"
                },
                "grid": {
                    "vertLines": {"color": "#161b22", "style": 1},
                    "horzLines": {"color": "#161b22", "style": 1}
                },
                "crosshair": {
                    "mode": 1,
                    "vertLine": {"color": "#758696", "width": 1, "style": 3, "labelBackgroundColor": "#21262d"},
                    "horzLine": {"color": "#758696", "width": 1, "style": 3, "labelBackgroundColor": "#21262d"}
                },
                "timeScale": {
                    "timeVisible": True,
                    "secondsVisible": False,
                    "borderColor": "#30363d",
                    "barSpacing": 10,
                    "minBarSpacing": 2
                },
                "rightPriceScale": {
                    "borderColor": "#30363d",
                    "autoScale": True,
                    "scaleMargins": {"top": 0.1, "bottom": 0.1}
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
                },
                {
                    "type": "Line",
                    "data": ma_data,
                    "options": {
                        "color": "#2962ff",
                        "lineWidth": 2,
                        "title": "MA20",
                        "priceLineVisible": False
                    }
                }
            ]

            renderLightweightCharts([{"chart": chart_options, "series": series_data}], key=f"pro_chart_{code}_{ktype_name}")

        except Exception as e:
            st.error(f"圖表渲染模塊發生異常: {str(e)}")
