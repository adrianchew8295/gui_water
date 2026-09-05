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

    def get_realtime_market_price(self, code: str) -> dict:
        """調用 OpenD 快照接口獲取包含盤前/盤後的當下跳動現價"""
        res = {"price": None, "status_text": "常規收盤"}
        try:
            ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
            ret, df_snap = ctx.get_market_snapshot([code])
            ctx.close()
            if ret == RET_OK and not df_snap.empty:
                row = df_snap.iloc[0]
                res["price"] = float(row['last_price'])
                # 判定當前時段 (盤前 Premarket / 盤後 Postmarket / 常規 Regular)
                market_status = row.get('market_status', '')
                res["status_text"] = f"即時跳動價 ({market_status})" if market_status else "即時盤口價"
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

            # 獲取最新實時盤前/盤後價格快照
            live_info = self.get_realtime_market_price(code)
            real_live_price = live_info["price"]
            
            # 若獲取到即時跳動價，更新最後一筆 K 線 Close 與 High/Low
            if real_live_price:
                current_price = real_live_price
                price_status_desc = f"🟢 {live_info['status_text']}: **${current_price:.2f}**"
                # 即時動態修正最後一根 K 線
                df.loc[df.index[-1], 'close'] = current_price
                if current_price > df.loc[df.index[-1], 'high']:
                    df.loc[df.index[-1], 'high'] = current_price
                if current_price < df.loc[df.index[-1], 'low']:
                    df.loc[df.index[-1], 'low'] = current_price
            else:
                current_price = float(df['close'].iloc[-1])
                price_status_desc = f"📌 歷史定格價: **${current_price:.2f}**"

            td_res = compute_demark_trendlines(df, window=4)
            td_highs, td_lows = find_td_pivots(df, window=4)

            # ---------------- 🎯 50/50 雙向多空路徑推演 Window ----------------
            st.markdown(f"### 🧭 {code} - {ktype_name} 戰術決策預測面板")
            st.markdown(price_status_desc)

            res_val = td_res.get('curr_res_val') if td_res.get('curr_res_val') else round(current_price * 1.01, 2)
            sup_val = td_res.get('curr_sup_val') if td_res.get('curr_sup_val') else round(current_price * 0.99, 2)
            channel_h = abs(res_val - sup_val)

            t1 = td_res.get('bull_target_1') or round(res_val + channel_h * 0.618, 2)
            t2 = td_res.get('bull_target_2') or round(res_val + channel_h * 1.0, 2)
            b1 = td_res.get('bear_target_1') or round(sup_val - channel_h * 0.618, 2)
            b2 = td_res.get('bear_target_2') or round(sup_val - channel_h * 1.0, 2)

            w_left, w_right = st.columns(2)
            with w_left:
                st.success("🟢 **多頭向上推演路徑 (Bullish Wave 50%)**")
                st.markdown(f"""
                - **起爆關鍵點**：站穩阻力線 **${res_val:.2f}**[cite: 2, 4]
                - **第一目標位 (Target 1)**：🚀 **${t1:.2f}** (TD 0.618 突破浪)
                - **第二目標位 (Target 2)**：🎯 **${t2:.2f}** (TD 1.0 對稱通道)[cite: 1]
                """)

            with w_right:
                st.error("🔴 **空頭向下推演路徑 (Bearish Wave 50%)**")
                st.markdown(f"""
                - **破位關鍵點**：跌破支撐線 **${sup_val:.2f}**[cite: 2, 4]
                - **第一目標位 (Target 1)**：📉 **${b1:.2f}** (TD 0.618 下跌浪)[cite: 1]
                - **第二目標位 (Target 2)**：🎯 **${b2:.2f}** (TD 1.0 對稱通道)[cite: 1]
                """)

            st.divider()

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
