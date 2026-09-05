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
            latest_close = df['close'].iloc[-1]

            # ---------------- 🎯 視覺化交易決策 Window ----------------
            st.markdown("### 🧭 戰術決策預測面板 (Tactical Prediction Window)")
            
            w_left, w_right = st.columns(2)
            with w_left:
                st.success("🟢 **多頭向上推演路徑 (Bullish Wave 50%)**")
                st.markdown(f"""
                - **起爆關鍵點**：站穩阻力線 **${td_res['curr_res_val'] or 0:.2f}**[cite: 2, 4]
                - **第一目標位 (Target 1)**：🚀 **${td_res['bull_target_1'] or 0:.2f}** (TD 0.618 突破浪)[cite: 1]
                - **第二目標位 (Target 2)**：🎯 **${td_res['bull_target_2'] or 0:.2f}** (TD 1.0 通道對稱浪)[cite: 1]
                - **防守止損 (SL)**：回跌跌破現價下方 1H 均線
                """)

            with w_right:
                st.error("🔴 **空頭向下推演路徑 (Bearish Wave 50%)**")
                st.markdown(f"""
                - **破位關鍵點**：跌破支撐線 **${td_res['curr_sup_val'] or 0:.2f}**[cite: 2, 4]
                - **第一目標位 (Target 1)**：📉 **${td_res['bear_target_1'] or 0:.2f}** (TD 0.618 下跌浪)[cite: 1]
                - **第二目標位 (Target 2)**：🎯 **${td_res['bear_target_2'] or 0:.2f}** (TD 1.0 通道對稱浪)[cite: 1]
                - **防守止損 (SL)**：反彈衝破現價上方 1H 均線[cite: 2]
                """)

            st.divider()

            # ---------------- 圖表繪製 ----------------
            candles = []
            markers = []
            vol_bars = []
            td_high_times = {p['time'] for p in td_highs}
            td_low_times = {p['time'] for p in td_lows}

            for _, row in df.iterrows():
                t = str(row['time_clean'])
                candles.append({
                    "time": t, "open": float(row['open']), "high": float(row['high']),
                    "low": float(row['low']), "close": float(row['close'])
                })
                if t in td_high_times:
                    markers.append({"time": t, "position": "aboveBar", "color": "#FF5252", "shape": "arrowDown", "text": "TD High"})
                elif t in td_low_times:
                    markers.append({"time": t, "position": "belowBar", "color": "#00E676", "shape": "arrowUp", "text": "TD Low"})

                if 'volume' in df.columns:
                    vol_bars.append({
                        "time": t, "value": float(row['volume']),
                        "color": "#26a69a" if row['close'] >= row['open'] else "#ef5350"
                    })

            price_chart = {
                "height": 450,
                "layout": {"textColor": "#8b949e", "background": {"type": "solid", "color": "#0a0e17"}},
                "grid": {"vertLines": {"color": "#161b22"}, "horzLines": {"color": "#161b22"}},
                "crosshair": {"mode": 1},
                "timeScale": {"timeVisible": True, "borderColor": "#21262d"},
                "rightPriceScale": {"borderColor": "#21262d", "autoScale": True}
            }

            price_series = [{"type": "Candlestick", "data": candles, "options": {"upColor": "#26a69a", "downColor": "#ef5350", "borderVisible": False}, "markers": markers}]
            if td_res.get("resistance_line"):
                price_series.append({"type": "Line", "data": td_res["resistance_line"], "options": {"color": "#FF5252", "lineWidth": 2, "lineStyle": 2, "title": "TD Resistance"}})
            if td_res.get("support_line"):
                price_series.append({"type": "Line", "data": td_res["support_line"], "options": {"color": "#00E676", "lineWidth": 2, "lineStyle": 2, "title": "TD Support"}})

            charts_to_render = [{"chart": price_chart, "series": price_series}]
            if vol_bars:
                vol_chart = {
                    "height": 160,
                    "layout": {"textColor": "#8b949e", "background": {"type": "solid", "color": "#0a0e17"}},
                    "grid": {"vertLines": {"color": "#161b22"}, "horzLines": {"color": "#161b22"}},
                    "crosshair": {"mode": 1},
                    "timeScale": {"timeVisible": True, "borderColor": "#21262d"},
                    "rightPriceScale": {"borderColor": "#21262d", "autoScale": True}
                }
                charts_to_render.append({"chart": vol_chart, "series": [{"type": "Histogram", "data": vol_bars, "options": {"priceFormat": {"type": "volume"}, "priceScaleId": ""}}]})

            renderLightweightCharts(charts_to_render, key=f"tv_{code}_{ktype_name}")

        except Exception as e:
            st.error(f"❌ 渲染失敗: {str(e)}")
