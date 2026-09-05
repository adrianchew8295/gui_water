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

    def calculate_vpa_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            if df.empty:
                return df
            
            # 1. 均量基准与机构警戒线
            df['VMA20'] = df['volume'].rolling(window=20).mean()
            df['VMA_15X'] = df['VMA20'] * 1.5
            df['VMA_20X'] = df['VMA20'] * 2.0

            # 2. K线多空判定
            df['IS_UP'] = df['close'] >= df['open']
            df['IS_DN'] = df['close'] < df['open']

            # 3. 量能异动分层计算
            df['VOL_15X'] = (df['volume'] >= df['VMA_15X']) & (df['volume'] < df['VMA_20X'])
            df['VOL_20X'] = df['volume'] >= df['VMA_20X']

            # 4. 多空放量触发条件
            df['BULL_15'] = df['IS_UP'] & df['VOL_15X']
            df['BEAR_15'] = df['IS_DN'] & df['VOL_15X']
            df['BULL_20'] = df['IS_UP'] & df['VOL_20X']
            df['BEAR_20'] = df['IS_DN'] & df['VOL_20X']

            return df
        except Exception as e:
            st.error(f"量能指標計算失敗: {str(e)}")
            return df

    def render_chart(self, code: str, ktype_name: str):
        try:
            df = self.load_local_data(code, ktype_name)
            if df.empty:
                return

            df['time_clean'] = df['time_key'].astype(str).str.slice(0, 10)
            df = df.drop_duplicates(subset=['time_clean']).sort_values('time_clean')
            df = self.calculate_vpa_indicators(df)

            candles = []
            vol_bars = []
            vma20_line = []
            vma15_line = []
            vma20_alert_line = []
            vol_markers = []

            for _, row in df.iterrows():
                t = str(row['time_clean'])
                
                # 主圖純 K 線數據
                candles.append({
                    "time": t,
                    "open": float(row['open']),
                    "high": float(row['high']),
                    "low": float(row['low']),
                    "close": float(row['close'])
                })

                # 副圖成交量柱
                vol_color = "rgba(8, 153, 129, 0.6)" if row['IS_UP'] else "rgba(242, 54, 69, 0.6)"
                vol_bars.append({
                    "time": t,
                    "value": float(row['volume']),
                    "color": vol_color
                })

                # 均量線與警戒線
                if pd.notna(row['VMA20']):
                    vma20_line.append({"time": t, "value": float(row['VMA20'])})
                if pd.notna(row['VMA_15X']):
                    vma15_line.append({"time": t, "value": float(row['VMA_15X'])})
                if pd.notna(row['VMA_20X']):
                    vma20_alert_line.append({"time": t, "value": float(row['VMA_20X'])})

                # 異動打點訊號全部移至副圖成交量柱上方
                if row['BULL_20']:
                    vol_markers.append({"time": t, "position": "aboveBar", "color": "#089981", "shape": "arrowUp", "text": "▲▲ 巨量"})
                elif row['BULL_15']:
                    vol_markers.append({"time": t, "position": "aboveBar", "color": "#00bcd4", "shape": "arrowUp", "text": "▲ 异动"})
                elif row['BEAR_20']:
                    vol_markers.append({"time": t, "position": "aboveBar", "color": "#f23645", "shape": "arrowDown", "text": "▼▼ 巨量"})
                elif row['BEAR_15']:
                    vol_markers.append({"time": t, "position": "aboveBar", "color": "#ff5252", "shape": "arrowDown", "text": "▼ 异动"})

            # 主圖配置 (純淨無雜質)
            price_chart_options = {
                "height": 450,
                "layout": {"textColor": "#d1d4dc", "background": {"type": "solid", "color": "#131722"}},
                "grid": {"vertLines": {"color": "#242732"}, "horzLines": {"color": "#242732"}},
                "crosshair": {"mode": 1},
                "timeScale": {"timeVisible": True, "secondsVisible": False, "borderColor": "#2b2b43"},
                "rightPriceScale": {"borderColor": "#2b2b43", "autoScale": True},
                "handleScroll": {"mouseWheel": True, "pressedMouseMove": True, "horzTouchDrag": True, "vertTouchDrag": True},
                "handleScale": {"axisPressedMouseMove": True, "mouseWheel": True, "pinch": True}
            }

            price_series = [
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

            # 副圖成交量配置 (承載所有異動訊號)
            volume_chart_options = {
                "height": 220,
                "layout": {"textColor": "#d1d4dc", "background": {"type": "solid", "color": "#131722"}},
                "grid": {"vertLines": {"color": "#242732"}, "horzLines": {"color": "#242732"}},
                "crosshair": {"mode": 1},
                "timeScale": {"timeVisible": True, "secondsVisible": False, "borderColor": "#2b2b43"},
                "rightPriceScale": {"borderColor": "#2b2b43", "autoScale": True},
                "handleScroll": {"mouseWheel": True, "pressedMouseMove": True, "horzTouchDrag": True, "vertTouchDrag": True},
                "handleScale": {"axisPressedMouseMove": True, "mouseWheel": True, "pinch": True}
            }

            volume_series = [
                {
                    "type": "Histogram",
                    "data": vol_bars,
                    "options": {"priceFormat": {"type": "volume"}, "priceScaleId": ""},
                    "markers": vol_markers
                },
                {
                    "type": "Line",
                    "data": vma20_line,
                    "options": {"color": "#ffffff", "lineWidth": 1, "title": "VMA20"}
                },
                {
                    "type": "Line",
                    "data": vma15_line,
                    "options": {"color": "#888888", "lineWidth": 1, "lineStyle": 2, "title": "1.5X"}
                },
                {
                    "type": "Line",
                    "data": vma20_alert_line,
                    "options": {"color": "#ffd700", "lineWidth": 1, "lineStyle": 2, "title": "2.0X"}
                }
            ]

            renderLightweightCharts([
                {"chart": price_chart_options, "series": price_series},
                {"chart": volume_chart_options, "series": volume_series}
            ], key=f"vpa_{code}_{ktype_name}")

        except Exception as e:
            st.error(f"圖表渲染失敗: {str(e)}")
