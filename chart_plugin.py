# 文件名: chart_plugin.py
import os
import pandas as pd
import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts
from trendline_engine import compute_demark_trendlines, find_td_pivots

class ChartPlugin:
    def __init__(self, data_dir: str = './market_data'):
        self.data_dir = data_dir

    def load_local_data(self, code: str, ktype_name: str) -> pd.DataFrame:
        clean_code = code.replace('.', '_')
        file_path = os.path.join(self.data_dir, f"{clean_code}_{ktype_name}.csv")
        
        if not os.path.exists(file_path):
            st.error(f"❌ 找不到本地數據檔案：`{file_path}`")
            st.info("💡 請先在終端機執行 `python data_fetcher.py` 同步歷史 K 線數據。")
            return pd.DataFrame()
            
        try:
            df = pd.read_csv(file_path)
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
            time_col = 'time_key' if 'time_key' in df.columns else ('date' if 'date' in df.columns else df.columns[0])
            df['time_clean'] = df[time_col].astype(str).str.slice(0, 10)
            df = df.drop_duplicates(subset=['time_clean']).sort_values('time_clean').reset_index(drop=True)

            td_res = compute_demark_trendlines(df, window=4)
            td_highs, td_lows = find_td_pivots(df, window=4)

            c1, c2, c3 = st.columns(3)
            latest_close = df['close'].iloc[-1]
            c1.metric("📌 最新收盤價", f"${latest_close:.2f}")
            c2.metric("🔴 TD 動態阻力線 (Resistance)", f"${td_res['curr_res_val']:.2f}" if (td_res and td_res.get('curr_res_val')) else "計算中")
            c3.metric("🟢 TD 動態支撐線 (Support)", f"${td_res['curr_sup_val']:.2f}" if (td_res and td_res.get('curr_sup_val')) else "計算中")

            candles = []
            markers = []
            
            td_high_times = {p['time'] for p in td_highs}
            td_low_times = {p['time'] for p in td_lows}

            for _, row in df.iterrows():
                t = str(row['time_clean'])
                candles.append({
                    "time": t,
                    "open": float(row['open']),
                    "high": float(row['high']),
                    "low": float(row['low']),
                    "close": float(row['close'])
                })

                if t in td_high_times:
                    markers.append({"time": t, "position": "aboveBar", "color": "#FF5252", "shape": "arrowDown", "text": "TD High"})
                elif t in td_low_times:
                    markers.append({"time": t, "position": "belowBar", "color": "#00E676", "shape": "arrowUp", "text": "TD Low"})

            chart_options = {
                "height": 580,
                "layout": {
                    "textColor": "#d1d4dc",
                    "background": {"type": "solid", "color": "#131722"}
                },
                "grid": {
                    "vertLines": {"color": "#242732"},
                    "horzLines": {"color": "#242732"}
                },
                "crosshair": {"mode": 1},
                "timeScale": {"timeVisible": True, "secondsVisible": False, "borderColor": "#2b2b43"},
                "rightPriceScale": {"borderColor": "#2b2b43", "autoScale": True},
                "handleScroll": {"mouseWheel": True, "pressedMouseMove": True, "horzTouchDrag": True, "vertTouchDrag": True},
                "handleScale": {"axisPressedMouseMove": True, "mouseWheel": True, "pinch": True}
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
                    },
                    "markers": markers
                }
            ]

            if td_res and td_res.get("resistance_line"):
                series_data.append({
                    "type": "Line",
                    "data": td_res["resistance_line"],
                    "options": {
                        "color": "#FF5252",
                        "lineWidth": 2,
                        "lineStyle": 2,
                        "title": "TD Resistance"
                    }
                })

            if td_res and td_res.get("support_line"):
                series_data.append({
                    "type": "Line",
                    "data": td_res["support_line"],
                    "options": {
                        "color": "#00E676",
                        "lineWidth": 2,
                        "lineStyle": 2,
                        "title": "TD Support"
                    }
                })

            renderLightweightCharts([{"chart": chart_options, "series": series_data}], key=f"tv_{code}_{ktype_name}")

        except Exception as e:
            st.error(f"❌ 圖表渲染失敗: {str(e)}")
