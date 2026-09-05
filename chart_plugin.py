# 文件名: chart_plugin.py
# 核心功能: 專業金融圖表 - 主圖(K線 + TD趨勢線 + 極值點) + 副圖(VPA成交量 + 均量線 + 量能異動打點)

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

    def calculate_vpa_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            if df.empty or 'volume' not in df.columns:
                return df
            
            # 1. 均量基准与机构警戒线
            df['vma20'] = df['volume'].rolling(window=20).mean()
            df['vma_15x'] = df['vma20'] * 1.5
            df['vma_20x'] = df['vma20'] * 2.0

            # 2. K线多空判定
            df['is_up'] = df['close'] >= df['open']
            df['is_dn'] = df['close'] < df['open']

            # 3. 量能异动分层计算
            df['vol_15x'] = (df['volume'] >= df['vma_15x']) & (df['volume'] < df['vma_20x'])
            df['vol_20x'] = df['volume'] >= df['vma_20x']

            # 4. 多空放量触发条件
            df['bull_15'] = df['is_up'] & df['vol_15x']
            df['bear_15'] = df['is_dn'] & df['vol_15x']
            df['bull_20'] = df['is_up'] & df['vol_20x']
            df['bear_20'] = df['is_dn'] & df['vol_20x']

            return df
        except Exception as e:
            st.error(f"量能指標計算失敗: {str(e)}")
            return df

    def render_chart(self, code: str, ktype_name: str):
        df = self.load_local_data(code, ktype_name)
        if df.empty:
            return

        try:
            time_col = 'time_key' if 'time_key' in df.columns else ('date' if 'date' in df.columns else df.columns[0])
            df['time_clean'] = df[time_col].astype(str).str.slice(0, 10)
            df = df.drop_duplicates(subset=['time_clean']).sort_values('time_clean').reset_index(drop=True)

            # 計算 VPA 量能指標
            df = self.calculate_vpa_indicators(df)

            # 計算 TD 趨勢線與極值點
            td_res = compute_demark_trendlines(df, window=4)
            td_highs, td_lows = find_td_pivots(df, window=4)

            # 頂部狀態列
            c1, c2, c3 = st.columns(3)
            latest_close = df['close'].iloc[-1]
            c1.metric("📌 最新收盤價", f"${latest_close:.2f}")
            c2.metric("🔴 TD 動態阻力線 (Resistance)", f"${td_res['curr_res_val']:.2f}" if (td_res and td_res.get('curr_res_val')) else "計算中")
            c3.metric("🟢 TD 動態支撐線 (Support)", f"${td_res['curr_sup_val']:.2f}" if (td_res and td_res.get('curr_sup_val')) else "計算中")

            # 數據結構準備
            candles = []
            price_markers = []
            vol_bars = []
            vma20_line = []
            vma15_line = []
            vma20_alert_line = []

            td_high_times = {p['time'] for p in td_highs}
            td_low_times = {p['time'] for p in td_lows}

            has_vol = 'volume' in df.columns

            for _, row in df.iterrows():
                t = str(row['time_clean'])
                
                # 主圖 K 線
                candles.append({
                    "time": t,
                    "open": float(row['open']),
                    "high": float(row['high']),
                    "low": float(row['low']),
                    "close": float(row['close'])
                })

                # 主圖 TD 極值標記
                if t in td_high_times:
                    price_markers.append({"time": t, "position": "aboveBar", "color": "#FF5252", "shape": "arrowDown", "text": "TD High"})
                elif t in td_low_times:
                    price_markers.append({"time": t, "position": "belowBar", "color": "#00E676", "shape": "arrowUp", "text": "TD Low"})

                # 副圖成交量與警戒線
                if has_vol:
                    vol_val = float(row['volume'])
                    is_up = row.get('is_up', row['close'] >= row['open'])
                    vol_color = "#26a69a" if is_up else "#ef5350"
                    
                    vol_bars.append({
                        "time": t,
                        "value": vol_val,
                        "color": vol_color
                    })

                    if pd.notna(row.get('vma20')):
                        vma20_line.append({"time": t, "value": float(row['vma20'])})
                    if pd.notna(row.get('vma_15x')):
                        vma15_line.append({"time": t, "value": float(row['vma_15x'])})
                    if pd.notna(row.get('vma_20x')):
                        vma20_alert_line.append({"time": t, "value": float(row['vma_20x'])})

            # --- 1. 主圖配置 (價格走勢 + TD 趨勢線) ---
            price_chart_options = {
                "height": 450,
                "layout": {"textColor": "#8b949e", "background": {"type": "solid", "color": "#0a0e17"}},
                "grid": {"vertLines": {"color": "#161b22"}, "horzLines": {"color": "#161b22"}},
                "crosshair": {"mode": 1},
                "timeScale": {"timeVisible": True, "secondsVisible": False, "borderColor": "#21262d"},
                "rightPriceScale": {"borderColor": "#21262d", "autoScale": True},
                "handleScroll": {"mouseWheel": True, "pressedMouseMove": True, "horzTouchDrag": True, "vertTouchDrag": True},
                "handleScale": {"axisPressedMouseMove": True, "mouseWheel": True, "pinch": True}
            }

            price_series = [
                {
                    "type": "Candlestick",
                    "data": candles,
                    "options": {
                        "upColor": "#26a69a",
                        "downColor": "#ef5350",
                        "borderVisible": False,
                        "wickUpColor": "#26a69a",
                        "wickDownColor": "#ef5350"
                    },
                    "markers": price_markers
                }
            ]

            # 疊加 TD 阻力與支撐趨勢線
            if td_res and td_res.get("resistance_line"):
                price_series.append({
                    "type": "Line",
                    "data": td_res["resistance_line"],
                    "options": {"color": "#FF5252", "lineWidth": 2, "lineStyle": 2, "title": "TD Resistance"}
                })

            if td_res and td_res.get("support_line"):
                price_series.append({
                    "type": "Line",
                    "data": td_res["support_line"],
                    "options": {"color": "#00E676", "lineWidth": 2, "lineStyle": 2, "title": "TD Support"}
                })

            charts_to_render = [{"chart": price_chart_options, "series": price_series}]

            # --- 2. 副圖配置 (VPA 成交量與均量線) ---
            if has_vol and vol_bars:
                volume_chart_options = {
                    "height": 180,
                    "layout": {"textColor": "#8b949e", "background": {"type": "solid", "color": "#0a0e17"}},
                    "grid": {"vertLines": {"color": "#161b22"}, "horzLines": {"color": "#161b22"}},
                    "crosshair": {"mode": 1},
                    "timeScale": {"timeVisible": True, "secondsVisible": False, "borderColor": "#21262d"},
                    "rightPriceScale": {"borderColor": "#21262d", "autoScale": True},
                    "handleScroll": {"mouseWheel": True, "pressedMouseMove": True, "horzTouchDrag": True, "vertTouchDrag": True},
                    "handleScale": {"axisPressedMouseMove": True, "mouseWheel": True, "pinch": True}
                }

                volume_series = [
                    {
                        "type": "Histogram",
                        "data": vol_bars,
                        "options": {"priceFormat": {"type": "volume"}, "priceScaleId": ""}
                    },
                    {
                        "type": "Line",
                        "data": vma20_line,
                        "options": {"color": "#ffffff", "lineWidth": 1, "title": "VMA20"}
                    },
                    {
                        "type": "Line",
                        "data": vma15_line,
                        "options": {"color": "#8b949e", "lineWidth": 1, "lineStyle": 2, "title": "1.5X"}
                    },
                    {
                        "type": "Line",
                        "data": vma20_alert_line,
                        "options": {"color": "#ffd700", "lineWidth": 1, "lineStyle": 2, "title": "2.0X"}
                    }
                ]
                charts_to_render.append({"chart": volume_chart_options, "series": volume_series})

            renderLightweightCharts(charts_to_render, key=f"tv_combined_{code}_{ktype_name}")

        except Exception as e:
            st.error(f"❌ 圖表渲染失敗: {str(e)}")
