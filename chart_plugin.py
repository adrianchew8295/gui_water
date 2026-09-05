# 文件名: chart_plugin.py
import os
import pandas as pd
import pytz
import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts
from moomoo import OpenQuoteContext, RET_OK
from trendline_engine import compute_demark_trendlines, find_td_pivots

tz_ny = pytz.timezone("America/New_York")

class ChartPlugin:
    def __init__(self, data_dir: str = './market_data'):
        self.data_dir = data_dir

    def get_realtime_market_price(self, code: str) -> dict:
        res = {"price": None, "status_text": "常規盤"}
        try:
            ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
            ret, df_snap = ctx.get_market_snapshot([code])
            ctx.close()
            if ret == RET_OK and not df_snap.empty:
                row = df_snap.iloc[0]
                res["price"] = float(row['last_price'])
                status = row.get('market_status', '')
                res["status_text"] = f"即時跳動 ({status})" if status else "即時盤口"
        except Exception:
            pass
        return res

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
            df['dt_obj'] = pd.to_datetime(df[time_col])
            df = df.sort_values('dt_obj').reset_index(drop=True)
            df = self.calculate_vpa_indicators(df)

            live_info = self.get_realtime_market_price(code)
            if live_info["price"]:
                current_price = live_info["price"]
                price_desc = f"🟢 {live_info['status_text']}: **${current_price:.2f}** (美東時間 ET)"
                df.loc[df.index[-1], 'close'] = current_price
            else:
                current_price = float(df['close'].iloc[-1])
                price_desc = f"📌 美東定格價: **${current_price:.2f}**"

            # 德馬克計算通道
            td_res = compute_demark_trendlines(df, window=4)
            td_highs, td_lows = find_td_pivots(df, window=4)

            # ---------------- 🎯 50/50 戰術決策預測面板 ----------------
            st.markdown(f"### 🧭 {code} - {ktype_name} 戰術決策預測面板 (美東時間 ET)")
            st.markdown(price_desc)

            res_val = td_res.get('curr_res_val') or round(current_price * 1.01, 2)
            sup_val = td_res.get('curr_sup_val') or round(current_price * 0.99, 2)
            channel_h = abs(res_val - sup_val)

            t1 = td_res.get('bull_target_1') or round(res_val + channel_h * 0.618, 2)
            t2 = td_res.get('bull_target_2') or round(res_val + channel_h * 1.0, 2)
            b1 = td_res.get('bear_target_1') or round(sup_val - channel_h * 0.618, 2)
            b2 = td_res.get('bear_target_2') or round(sup_val - channel_h * 1.0, 2)

            w_left, w_right = st.columns(2)
            with w_left:
                st.success("🟢 **多頭向上推演路徑 (Bullish Wave 50%)**")
                st.markdown(f"""
                - **起爆關鍵點**：站穩阻力線 **${res_val:.2f}**[cite: 2]
                - **第一目標位 (Target 1)**：🚀 **${t1:.2f}** (TD 0.618 突破浪)
                - **第二目標位 (Target 2)**：🎯 **${t2:.2f}** (TD 1.0 對稱通道)[cite: 1]
                """)

            with w_right:
                st.error("🔴 **空頭向下推演路徑 (Bearish Wave 50%)**")
                st.markdown(f"""
                - **破位關鍵點**：跌破支撐線 **${sup_val:.2f}**[cite: 2]
                - **第一目標位 (Target 1)**：📉 **${b1:.2f}** (TD 0.618 下跌浪)[cite: 1]
                - **第二目標位 (Target 2)**：🎯 **${b2:.2f}** (TD 1.0 對稱通道)[cite: 1]
                """)

            st.divider()

            candles = []
            markers = []
            vol_bars = []
            vma20_line = []
            vma15_line = []
            vma20_alert_line = []

            has_vol = 'volume' in df.columns
            td_high_times = {str(p['time']) for p in td_highs}
            td_low_times = {str(p['time']) for p in td_lows}

            for idx, row in df.iterrows():
                dt_item = row['dt_obj']
                
                # 統一時間格式：日線用字串，1Hr用物件格式以緊密對齊消除 Gap
                if ktype_name in ['DAY', 'WEEK']:
                    t_val = dt_item.strftime('%Y-%m-%d')
                else:
                    t_val = {
                        "year": int(dt_item.year),
                        "month": int(dt_item.month),
                        "day": int(dt_item.day),
                        "hour": int(dt_item.hour),
                        "minute": int(dt_item.minute)
                    }

                candles.append({
                    "time": t_val,
                    "open": float(row['open']),
                    "high": float(row['high']),
                    "low": float(row['low']),
                    "close": float(row['close'])
                })

                t_str_key = str(row[time_col])
                if t_str_key in td_high_times:
                    markers.append({"time": t_val, "position": "aboveBar", "color": "#FF5252", "shape": "arrowDown", "text": "TD High"})
                elif t_str_key in td_low_times:
                    markers.append({"time": t_val, "position": "belowBar", "color": "#00E676", "shape": "arrowUp", "text": "TD Low"})

                if has_vol:
                    vol_bars.append({
                        "time": t_val,
                        "value": float(row['volume']),
                        "color": "#089981" if row['close'] >= row['open'] else "#F23645"
                    })
                    if pd.notna(row.get('vma20')): vma20_line.append({"time": t_val, "value": float(row['vma20'])})
                    if pd.notna(row.get('vma_15x')): vma15_line.append({"time": t_val, "value": float(row['vma_15x'])})
                    if pd.notna(row.get('vma_20x')): vma20_alert_line.append({"time": t_val, "value": float(row['vma_20x'])})

            price_chart = {
                "height": 500,
                "layout": {"textColor": "#8b949e", "background": {"type": "solid", "color": "#0d1117"}},
                "grid": {"vertLines": {"color": "#161b22"}, "horzLines": {"color": "#161b22"}},
                "crosshair": {"mode": 1},
                "timeScale": {
                    "timeVisible": True,
                    "secondsVisible": False,
                    "borderColor": "#21262d",
                    "fixLeftEdge": True,
                    "fixRightEdge": True
                },
                "rightPriceScale": {"borderColor": "#21262d", "autoScale": True},
                "handleScroll": {"mouseWheel": True, "pressedMouseMove": True, "horzTouchDrag": True, "vertTouchDrag": True},
                "handleScale": {"axisPressedMouseMove": True, "mouseWheel": True, "pinch": True}
            }

            price_series = [
                {
                    "type": "Candlestick",
                    "data": candles,
                    "options": {
                        "upColor": "#089981",
                        "downColor": "#F23645",
                        "borderVisible": False,
                        "wickUpColor": "#089981",
                        "wickDownColor": "#F23645"
                    },
                    "markers": markers
                }
            ]

            charts_to_render = [{"chart": price_chart, "series": price_series}]

            if has_vol and vol_bars:
                vol_chart = {
                    "height": 160,
                    "layout": {"textColor": "#8b949e", "background": {"type": "solid", "color": "#0d1117"}},
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

            renderLightweightCharts(charts_to_render, key=f"tv_chart_final_{code}_{ktype_name}")

        except Exception as e:
            st.error(f"❌ 渲染失敗: {str(e)}")
