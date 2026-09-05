import os
import pandas as pd
import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts

# ==============================================================================
# 獨立圖表渲染插件 (負責數據讀取、指標計算與專業金融圖表呈現)
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
            # 默認計算一條 20 週期均線作為示範
            df['MA20'] = df['close'].rolling(window=20).mean()
            return df
        except Exception as e:
            st.error(f"指標計算異常: {str(e)}")
            return df

    def render_chart(self, code: str, ktype_name: str):
        """渲染專業級 TradingView 交互圖表"""
        try:
            df = self.load_local_data(code, ktype_name)
            if df.empty:
                return

            df = self.calculate_indicators(df)

            candles = []
            ma_data = []

            for _, row in df.iterrows():
                # 處理時間格式，相容日期與時間戳
                time_val = str(row['time_key'])
                if len(time_val) == 10:  # 例如 2026-09-05
                    time_entry = time_val
                else:
                    time_entry = time_val

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

            chart_options = {
                "layout": {
                    "textColor": "#d1d4dc",
                    "background": {"type": "solid", "color": "#131722"}
                },
                "grid": {
                    "vertLines": {"color": "#242732"},
                    "horzLines": {"color": "#242732"}
                },
                "crosshair": {"mode": 1},
                "timeScale": {"timeVisible": True, "secondsVisible": False}
            }

            series_data = [
                {
                    "type": "Candlestick",
                    "data": candles,
                    "options": {
                        "upColor": "#26a69a",
                        "downColor": "#ef5350",
                        "borderVisible": False,
                        "wickUpColor": "#26a69a",
                        "wickDownColor": "#ef5350"
                    }
                },
                {
                    "type": "Line",
                    "data": ma_data,
                    "options": {
                        "color": "#ff9800",
                        "lineWidth": 2,
                        "title": "MA20"
                    }
                }
            ]

            renderLightweightCharts([{"chart": chart_options, "series": series_data}], key=f"chart_{code}_{ktype_name}")

        except Exception as e:
            st.error(f"圖表渲染模塊發生異常: {str(e)}")
