# 文件名: chart_plugin.py
import os
import pandas as pd
import streamlit as st
from streamlit_lightweight_charts import renderLightweightCharts
from moomoo import OpenQuoteContext, RET_OK
from trendline_engine import compute_demark_trendlines, find_td_pivots

class ChartPlugin:
    def __init__(self, data_dir: str = './market_data'):
        self.data_dir = data_dir

    def get_live_snapshot_price(self, code: str) -> float:
        """從本地 OpenD 獲取包含盤前/盤後的最新真實跳動價格"""
        try:
            ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
            ret, df_snap = ctx.get_market_snapshot([code])
            ctx.close()
            if ret == RET_OK and not df_snap.empty:
                return float(df_snap.iloc[0]['last_price'])
        except Exception:
            pass
        return None

    def load_local_data(self, code: str, ktype_name: str) -> pd.DataFrame:
        clean_code = code.replace('.', '_')
        file_path = os.path.join(self.data_dir, f"{clean_code}_{ktype_name}.csv")
        
        if not os.path.exists(file_path) and ktype_name == "1Hr":
            alt_path = os.path.join(self.data_dir, f"{clean_code}_60M.csv")
            if os.path.exists(alt_path):
                file_path = alt_path

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
            
            if ktype_name in ['DAY', 'WEEK']:
                df['time_clean'] = df[time_col].astype(str).str.slice(0, 10)
            else:
                df['time_clean'] = pd.to_datetime(df[time_col]).astype('int64') // 10**9

            df = df.drop_duplicates(subset=['time_clean']).sort_values('time_clean').reset_index(drop=True)

            td_res = compute_demark_trendlines(df, window=4)
            td_highs, td_lows = find_td_pivots(df, window=4)
            
            # 優先獲取盤後跳動快照價，若 OpenD 未開則讀取歷史最新收盤價
            live_price = self.get_live_snapshot_price(code)
            current_price = live_price if live_price else float(df['close'].iloc[-1])
            price_tag = "🔴 盤前/盤後即時跳動價" if live_price else "📌 常規時段歷史收盤價"

            # ---------------- 🎯 實時多空波浪推演 Window ----------------
            st.markdown(f"### 🧭 {code} - {ktype_name} 戰術決策預測面板")
            st.caption(f"{price_tag}：**${current_price:.2f}**")
            
            w_left, w_right = st.columns(2)
            with w_left:
                st.success("🟢 **多頭向上推演路徑 (Bullish Wave 50%)**")
                res_val = td_res.get('curr_res_val') or current_price * 1.01
                t1 = td_res.get('bull_target_1') or res_val * 1.015
                t2 = td_res.get('bull_target_2') or res_val * 1.03
                st.markdown(f"""
                - **起爆關鍵點**：站穩阻力線 **${res_val:.2f}**
                - **第一目標位 (Target 1)**：🚀 **${t1:.2f}** (TD 0.618 浪)
                - **第二目標位 (Target 2)**：🎯 **${t2:.2f}** (TD 1.0 通道對稱浪)
                """)

            with w_right:
                st.error("🔴 **空頭向下推演路徑 (Bearish Wave 50%)**")
                sup_val = td_res.get('curr_sup_val') or current_price * 0.99
                b1 = td_res.get('bear_target_1') or sup_val * 0.985
                b2 = td_res.get('bear_target_2') or sup_val * 0.97
                st.markdown(f"""
                - **破位關鍵點**：跌破支撐線 **${sup_val:.2f}**
                - **第一目標位 (Target 1)**：📉 **${b1:.2f}** (TD 0.618 浪)
                - **第二目標位 (Target 2)**：🎯 **${b2:.2f}** (TD 1.0 通道對稱浪)
                """)

            st.divider()

            # 渲染 K 線與 TD 趨勢射線
            candles = []
            markers = []
            vol_bars = []
            td_high_times = {p['time'] for p in td_highs}
            td_low_times = {p['time'] for p in td_lows}
            has_vol = 'volume' in df.columns

            for _, row in df.iterrows():
                t = int(row['time_clean']) if isinstance(row['time_clean'], (int, float)) else str(row['time_clean'])
                candles.append({
                    "time": t, "open": float(row['open']), "high": float(row['high']),
                    "low": float(row['low']), "close": float(row['close'])
                })
                if str(row['time_clean']) in td_high_times:
                    markers.append({"time": t, "position": "aboveBar", "color": "#FF5252", "shape": "arrowDown", "text": "TD High"})
                elif str(row['time_clean']) in td_low_times:
                    markers.append({"time": t, "position": "belowBar", "color": "#00E676", "shape": "arrowUp", "text": "TD Low"})

                if has_vol:
                    vol_bars.append({
                        "time": t, "value": float(row['volume']),
                        "color": "#26a69a" if row['close'] >= row['open'] else "#ef5350"
                    })

            price_chart = {
                "height": 450,
                "layout": {"textColor": "#8b949e", "background": {"type": "solid", "color": "#0a0e17"}},
                "grid": {"vertLines": {"color": "#161b22"}, "horzLines": {"color": "#161b22"}},
                "crosshair": {"mode": 1},
                "timeScale": {"timeVisible": True, "secondsVisible": False, "borderColor": "#21262d"},
                "rightPriceScale": {"borderColor": "#21262d", "autoScale": True}
            }

            price_series = [{"type": "Candlestick", "data": candles, "options": {"upColor": "#26a69a", "downColor": "#ef5350", "borderVisible": False}, "markers": markers}]
            
            if td_res.get("resistance_line"):
                res_pts = [{"time": int(pt["time"]) if str(pt["time"]).isdigit() else pt["time"], "value": pt["value"]} for pt in td_res["resistance_line"]]
                price_series.append({"type": "Line", "data": res_pts, "options": {"color": "#FF5252", "lineWidth": 2, "lineStyle": 2, "title": "TD Resistance"}})

            if td_res.get("support_line"):
                sup_pts = [{"time": int(pt["time"]) if str(pt["time"]).isdigit() else pt["time"], "value": pt["value"]} for pt in td_res["support_line"]]
                price_series.append({"type": "Line", "data": sup_pts, "options": {"color": "#00E676", "lineWidth": 2, "lineStyle": 2, "title": "TD Support"}})

            charts_to_render = [{"chart": price_chart, "series": price_series}]

            if has_vol and vol_bars:
                vol_chart = {
                    "height": 160,
                    "layout": {"textColor": "#8b949e", "background": {"type": "solid", "color": "#0a0e17"}},
                    "grid": {"vertLines": {"color": "#161b22"}, "horzLines": {"color": "#161b22"}},
                    "crosshair": {"mode": 1},
                    "timeScale": {"timeVisible": True, "secondsVisible": False, "borderColor": "#21262d"},
                    "rightPriceScale": {"borderColor": "#21262d", "autoScale": True}
                }
                vol_series = [{"type": "Histogram", "data": vol_bars, "options": {"priceFormat": {"type": "volume"}, "priceScaleId": ""}}]
                charts_to_render.append({"chart": vol_chart, "series": vol_series})

            renderLightweightCharts(charts_to_render, key=f"tv_chart_{code}_{ktype_name}")

        except Exception as e:
            st.error(f"❌ 渲染失敗: {str(e)}")
