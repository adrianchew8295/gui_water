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
        
        # 兼容 60M 舊檔名
        if not os.path.exists(file_path) and ktype_name == "1Hr":
            alt_path = os.path.join(self.data_dir, f"{clean_code}_60M.csv")
            if os.path.exists(alt_path):
                file_path = alt_path
        
        if not os.path.exists(file_path):
            st.error(f"❌ 找不到本地數據檔案：`{file_path}`")
            st.info(f"💡 請先在終端機執行 `python data_fetcher.py` 下載 {ktype_name} 歷史數據。")
            return pd.DataFrame()
            
        try:
            df = pd.read_csv(file_path)
            df.columns = [c.lower() for c in df.columns]
            return df
        except Exception as e:
            st.error(f"❌ 讀取數據異常: {str(e)}")
            return pd.DataFrame()

    def calculate_vpa_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or 'volume' not in df.columns:
            return df
        df['vma20'] = df['volume'].rolling(window=20).mean()
        df['vma_15x'] = df['vma20'] * 1.5
        df['vma_20x'] = df['vma20'] * 2.0
        return df

    def render_chart(self, code: str, ktype_name: str):
        df = self.load_local_data(code, ktype_name)
        if df.empty:
            return

        try:
            time_col = 'time_key' if 'time_key' in df.columns else ('date' if 'date' in df.columns else df.columns[0])
            
            # 乾淨時間戳轉換：日/周用 YYYY-MM-DD，1Hr 轉為 int UNIX timestamp
            if ktype_name in ['DAY', 'WEEK']:
                df['time_clean'] = df[time_col].astype(str).str.slice(0, 10)
            else:
                df['time_clean'] = pd.to_datetime(df[time_col]).astype('int64') // 10**9

            df = df.drop_duplicates(subset=['time_clean']).sort_values('time_clean').reset_index(drop=True)
            df = self.calculate_vpa_indicators(df)

            td_res = compute_demark_trendlines(df, window=4)
            td_highs, td_lows = find_td_pivots(df, window=4)
            latest_close = float(df['close'].iloc[-1])

            # ---------------- 🎯 戰術決策預測面板 ----------------
            st.markdown(f"### 🧭 {ktype_name} 戰術決策預測面板 (Tactical Prediction Window)")
            
            w_left, w_right = st.columns(2)
            with w_left:
                st.success(f"🟢 **多頭向上推演路徑 (Bullish Wave 50%)**")
                res_val = td_res.get('curr_res_val')
                t1 = td_res.get('bull_target_1')
                t2 = td_res.get('bull_target_2')
                st.markdown(f"""
                - **起爆關鍵點**：站穩阻力線 **${res_val if res_val else 0:.2f}**
                - **第一目標位 (Target 1)**：🚀 **${t1 if t1 else 0:.2f}** (TD 0.618 突破浪)
                - **第二目標位 (Target 2)**：🎯 **${t2 if t2 else 0:.2f}** (TD 1.0 通道對稱浪)
                """)

            with w_right:
                st.error(f"🔴 **空頭向下推演路徑 (Bearish Wave 50%)**")
                sup_val = td_res.get('curr_sup_val')
                b1 = td_res.get('bear_target_1')
                b2 = td_res.get('bear_target_2')
                st.markdown(f"""
                - **破位關鍵點**：跌破支撐線 **${sup_val if sup_val else 0:.2f}**
                - **第一目標位 (Target 1)**：📉 **${b1 if b1 else 0:.2f}** (TD 0.618 下跌浪)
                - **第二目標位 (Target 2)**：🎯 **${b2 if b2 else 0:.2f}** (TD 1.0 通道對稱浪)
                """)

            st.divider()

            # 數據解析
            candles = []
            markers = []
            vol_bars = []
            vma20_line = []
            vma15_line = []
            vma20_alert_line = []

            td_high_times = {p['time'] for p in td_highs}
            td_low_times = {p['time'] for p in td_lows}
            has_vol = 'volume' in df.columns

            for _, row in df.iterrows():
                t = int(row['time_clean']) if isinstance(row['time_clean'], (int, float)) else str(row['time_clean'])
                
                candles.append({
                    "time": t,
                    "open": float(row['open']),
                    "high": float(row['high']),
                    "low": float(row['low']),
                    "close": float(row['close'])
                })

                if str(row['time_clean']) in td_high_times:
                    markers.append({"time": t, "position": "aboveBar", "color": "#FF5252", "shape": "arrowDown", "text": "TD High"})
                elif str(row['time_clean']) in td_low_times:
                    markers.append({"time": t, "position": "belowBar", "color": "#00E676", "shape": "arrowUp", "text": "TD Low"})

                if has_vol:
                    vol_bars.append({
                        "time": t,
                        "value": float(row['volume']),
                        "color": "#26a69a" if row['close'] >= row['open'] else "#ef5350"
                    })
                    if pd.notna(row.get('vma20')): vma20_line.append({"time": t, "value": float(row['vma20'])})
                    if pd.notna(row.get('vma_15x')): vma15_line.append({"time": t, "value": float(row['vma_15x'])})
                    if pd.notna(row.get('vma_20x')): vma20_alert_line.append({"time": t, "value": float(row['vma_20x'])})

            # 主圖配置
            price_chart = {
                "height": 450,
                "layout": {"textColor": "#8b949e", "background": {"type": "solid", "color": "#0a0e17"}},
                "grid": {"vertLines": {"color": "#161b22"}, "horzLines": {"color": "#161b22"}},
                "crosshair": {"mode": 1},
                "timeScale": {"timeVisible": True, "secondsVisible": False, "borderColor": "#21262d"},
                "rightPriceScale": {"borderColor": "#21262d", "autoScale": True}
            }

            price_series = [
                {
                    "type": "Candlestick",
                    "data": candles,
                    "options": {"upColor": "#26a69a", "downColor": "#ef5350", "borderVisible": False},
                    "markers": markers
                }
            ]

            # 疊加 TD 趨勢線
            if td_res and td_res.get("resistance_line"):
                res_pts = []
                for pt in td_res["resistance_line"]:
                    t_val = int(pt["time"]) if str(pt["time"]).isdigit() else pt["time"]
                    res_pts.append({"time": t_val, "value": pt["value"]})
                price_series.append({"type": "Line", "data": res_pts, "options": {"color": "#FF5252", "lineWidth": 2, "lineStyle": 2, "title": "TD Resistance"}})

            if td_res and td_res.get("support_line"):
                sup_pts = []
                for pt in td_res["support_line"]:
                    t_val = int(pt["time"]) if str(pt["time"]).isdigit() else pt["time"]
                    sup_pts.append({"time": t_val, "value": pt["value"]})
                price_series.append({"type": "Line", "data": sup_pts, "options": {"color": "#00E676", "lineWidth": 2, "lineStyle": 2, "title": "TD Support"}})

            charts_to_render = [{"chart": price_chart, "series": price_series}]

            # 副圖配置
            if has_vol and vol_bars:
                vol_chart = {
                    "height": 160,
                    "layout": {"textColor": "#8b949e", "background": {"type": "solid", "color": "#0a0e17"}},
                    "grid": {"vertLines": {"color": "#161b22"}, "horzLines": {"color": "#161b22"}},
                    "crosshair": {"mode": 1},
                    "timeScale": {"timeVisible": True, "secondsVisible": False, "borderColor": "#21262d"},
                    "rightPriceScale": {"borderColor": "#21262d", "autoScale": True}
                }
                vol_series = [
                    {"type": "Histogram", "data": vol_bars, "options": {"priceFormat": {"type": "volume"}, "priceScaleId": ""}},
                    {"type": "Line", "data": vma20_line, "options": {"color": "#ffffff", "lineWidth": 1, "title": "VMA20"}},
                    {"type": "Line", "data": vma15_line, "options": {"color": "#8b949e", "lineWidth": 1, "lineStyle": 2, "title": "1.5X"}},
                    {"type": "Line", "data": vma20_alert_line, "options": {"color": "#ffd700", "lineWidth": 1, "lineStyle": 2, "title": "2.0X"}}
                ]
                charts_to_render.append({"chart": vol_chart, "series": vol_series})

            renderLightweightCharts(charts_to_render, key=f"tv_chart_{code}_{ktype_name}")

        except Exception as e:
            st.error(f"❌ 渲染失敗: {str(e)}")
