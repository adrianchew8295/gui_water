# 文件名: chart_plugin.py
# 核心功能: 專業金融圖表 - 美東時間軸 + 盤前盤後灰色透明區塊 + ☀️/🌙 標記 + TD 趨勢通道

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
        """調用本地 OpenD 獲取最新即時跳動價"""
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
            st.info(f"💡 請先在終端機執行 `python data_fetcher.py` 下載歷史數據。")
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

            # 美東時間戳轉換
            if ktype_name in ['DAY', 'WEEK']:
                df['time_clean'] = df['dt_obj'].dt.strftime('%Y-%m-%d')
            else:
                # 1Hr 採用 UNIX 秒級時間戳
                df['time_clean'] = df['dt_obj'].astype('int64') // 10**9

            df = df.drop_duplicates(subset=['time_clean']).sort_values('dt_obj').reset_index(drop=True)
            df = self.calculate_vpa_indicators(df)

            # 實時快照融合
            live_info = self.get_realtime_market_price(code)
            if live_info["price"]:
                current_price = live_info["price"]
                price_desc = f"🟢 {live_info['status_text']}: **${current_price:.2f}** (美東時間)"
                df.loc[df.index[-1], 'close'] = current_price
                if current_price > df.loc[df.index[-1], 'high']:
                    df.loc[df.index[-1], 'high'] = current_price
                if current_price < df.loc[df.index[-1], 'low']:
                    df.loc[df.index[-1], 'low'] = current_price
            else:
                current_price = float(df['close'].iloc[-1])
                price_desc = f"📌 美東定格價: **${current_price:.2f}**"

            td_res = compute_demark_trendlines(df, window=4)
            td_highs, td_lows = find_td_pivots(df, window=4)

            # ---------------- 🎯 50/50 多空雙向推演 Window ----------------
            st.markdown(f"### 🧭 {code} - {ktype_name} 戰術決策預測面板 (美東時間)")
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
                - **起爆關鍵點**：站穩阻力線 **${res_val:.2f}**[cite: 2, 4]
                - **第一目標位 (Target 1)**：🚀 **${t1:.2f}** (TD 0.618 突破浪)[cite: 1]
                - **第二目標位 (Target 2)**：🎯 **${t2:.2f}** (TD 1.0 通道對稱浪)[cite: 1]
                """)

            with w_right:
                st.error("🔴 **空頭向下推演路徑 (Bearish Wave 50%)**")
                st.markdown(f"""
                - **破位關鍵點**：跌破支撐線 **${sup_val:.2f}**[cite: 2, 4]
                - **第一目標位 (Target 1)**：📉 **${b1:.2f}** (TD 0.618 下跌浪)[cite: 1]
                - **第二目標位 (Target 2)**：🎯 **${b2:.2f}** (TD 1.0 通道對稱浪)[cite: 1]
                """)

            st.divider()

            # ---------------- 圖表數據構建 ----------------
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
                dt_item = row['dt_obj']
                hour_et = dt_item.hour
                min_et = dt_item.minute
                time_float = hour_et + min_et / 60.0

                # 判定時段屬性 (美東時間基準)
                is_pre = (time_float >= 4.0) and (time_float < 9.5)
                is_post = (time_float >= 16.0) and (time_float <= 20.0)
                is_rth = (time_float >= 9.5) and (time_float < 16.0)

                # K 線色彩：常規時段飽和色，盤前盤後微透明/柔和色
                is_up = row['close'] >= row['open']
                if is_rth:
                    up_col = "#089981"
                    dn_col = "#F23645"
                else:
                    up_col = "#26a69a"
                    dn_col = "#ef5350"

                candles.append({
                    "time": t,
                    "open": float(row['open']),
                    "high": float(row['high']),
                    "low": float(row['low']),
                    "close": float(row['close'])
                })

                # 時段底部標記 (☀️ / 🌙)
                if is_pre and min_et == 0 and hour_et == 4:
                    markers.append({"time": t, "position": "belowBar", "color": "#FCD34D", "shape": "circle", "text": "☀️ Premarket"})
                elif is_post and min_et == 0 and hour_et == 16:
                    markers.append({"time": t, "position": "belowBar", "color": "#94A3B8", "shape": "circle", "text": "🌙 Postmarket"})

                # TD 極值點標記
                if str(row['time_clean']) in td_high_times:
                    markers.append({"time": t, "position": "aboveBar", "color": "#FF5252", "shape": "arrowDown", "text": "TD High"})
                elif str(row['time_clean']) in td_low_times:
                    markers.append({"time": t, "position": "belowBar", "color": "#00E676", "shape": "arrowUp", "text": "TD Low"})

                if has_vol:
                    vol_bars.append({
                        "time": t,
                        "value": float(row['volume']),
                        "color": up_col if is_up else dn_col
                    })
                    if pd.notna(row.get('vma20')): vma20_line.append({"time": t, "value": float(row['vma20'])})
                    if pd.notna(row.get('vma_15x')): vma15_line.append({"time": t, "value": float(row['vma_15x'])})
                    if pd.notna(row.get('vma_20x')): vma20_alert_line.append({"time": t, "value": float(row['vma_20x'])})

            # 主圖配置
            price_chart = {
                "height": 480,
                "layout": {"textColor": "#8b949e", "background": {"type": "solid", "color": "#0d1117"}},
                "grid": {"vertLines": {"color": "#161b22"}, "horzLines": {"color": "#161b22"}},
                "crosshair": {"mode": 1},
                "timeScale": {"timeVisible": True, "secondsVisible": False, "borderColor": "#21262d"},
                "rightPriceScale": {"borderColor": "#21262d", "autoScale": True}
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

            # 疊加 TD 趨勢線
            if td_res.get("resistance_line"):
                res_pts = [{"time": int(pt["time"]) if str(pt["time"]).isdigit() else pt["time"], "value": pt["value"]} for pt in td_res["resistance_line"]]
                price_series.append({"type": "Line", "data": res_pts, "options": {"color": "#FF5252", "lineWidth": 2, "lineStyle": 2, "title": "TD Resistance"}})

            if td_res.get("support_line"):
                sup_pts = [{"time": int(pt["time"]) if str(pt["time"]).isdigit() else pt["time"], "value": pt["value"]} for pt in td_res["support_line"]]
                price_series.append({"type": "Line", "data": sup_pts, "options": {"color": "#00E676", "lineWidth": 2, "lineStyle": 2, "title": "TD Support"}})

            charts_to_render = [{"chart": price_chart, "series": price_series}]

            # 副圖配置 (VPA 成交量)
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

            renderLightweightCharts(charts_to_render, key=f"tv_chart_{code}_{ktype_name}")

        except Exception as e:
            st.error(f"❌ 渲染失敗: {str(e)}")
