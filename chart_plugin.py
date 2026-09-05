# 文件名: chart_plugin.py
# 核心特性: 零阻塞秒級渲染 + 預判雷達 + 富途指標 1:2 結構 (純數據座艙)

import os
import time
import datetime
import numpy as np
import pandas as pd
import pytz
import streamlit as st
from moomoo import OpenQuoteContext, RET_OK

tz_ny = pytz.timezone("America/New_York")

# 絕對路徑防呆定位
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'market_data')
os.makedirs(DATA_DIR, exist_ok=True)

class ChartPlugin:
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """計算 ATR14 波動率"""
        if len(df) < 2:
            return pd.Series([1.0] * len(df))
        high = df['high']
        low = df['low']
        close = df['close'].shift(1).bfill()
        tr = np.maximum(high - low, np.maximum((high - close).abs(), (low - close).abs()))
        return tr.rolling(window=period).mean().bfill()

    def get_realtime_snapshot(self, code: str) -> dict:
        """極速非阻塞快照"""
        res = {
            "price": 0.0, "source": "未連線", "server_time": "--",
            "latency_ms": 0, "open": 0.0, "high": 0.0, "low": 0.0, "vol": 0.0
        }
        t_start = time.time()
        target_symbol = "CC.BTCUSD" if "BTC" in code.upper() else code

        quote_ctx = None
        try:
            quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
            ret, df_snap = quote_ctx.get_market_snapshot([target_symbol])
            if ret == RET_OK and not df_snap.empty:
                row = df_snap.iloc[0]
                res["price"] = float(row['last_price'])
                res["open"] = float(row.get('open_price', row['last_price']))
                res["high"] = float(row.get('high_price', row['last_price']))
                res["low"] = float(row.get('low_price', row['last_price']))
                res["vol"] = float(row.get('volume', 0.0))
                res["source"] = "🟢 OpenD 直連"
                res["server_time"] = str(row.get('update_time', datetime.datetime.now(tz_ny).strftime('%H:%M:%S.%f')[:-3]))
                res["latency_ms"] = int((time.time() - t_start) * 1000)
                return res
        except Exception:
            pass
        finally:
            if quote_ctx:
                try: quote_ctx.close()
                except: pass

        res["source"] = "🟡 本地保底數據"
        res["server_time"] = datetime.datetime.now(tz_ny).strftime('%H:%M:%S')
        res["latency_ms"] = int((time.time() - t_start) * 1000)
        return res

    def load_safe_kline(self, code: str, ktype_name: str) -> pd.DataFrame:
        """純本地讀取 CSV，絕不阻塞"""
        is_btc = "BTC" in code.upper()
        save_prefix = "CC_BTCUSD" if is_btc else code.replace('.', '_')
        file_path = os.path.join(self.data_dir, f"{save_prefix}_{ktype_name}.csv")

        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path)
                df.columns = [c.lower().strip() for c in df.columns]
                if 'time_key' in df.columns:
                    df['time_key'] = pd.to_datetime(df['time_key'])
                if not df.empty and 'close' in df.columns:
                    return df
            except Exception:
                pass

        # 預設保底數據
        base_p = 79700.0 if is_btc else 488.0
        now = datetime.datetime.now(tz_ny)
        dummy_times = [now - datetime.timedelta(minutes=5 * i) for i in range(20)][::-1]
        dummy_df = pd.DataFrame({
            'time_key': dummy_times,
            'open': [base_p + np.sin(i) * 5 for i in range(20)],
            'high': [base_p + np.sin(i) * 5 + 3 for i in range(20)],
            'low': [base_p + np.sin(i) * 5 - 3 for i in range(20)],
            'close': [base_p + np.sin(i) * 5 + 1 for i in range(20)],
            'volume': [1000.0 + i * 50 for i in range(20)]
        })
        return dummy_df

    def render_cockpit(self, code: str):
        """【主座艙渲染】：純原生組件，秒出結果"""
        snap = self.get_realtime_snapshot(code)
        df_day = self.load_safe_kline(code, "DAY")
        df_1h = self.load_safe_kline(code, "1Hr")
        df_5m = self.load_safe_kline(code, "5M")

        # 1. 現價計算
        live_price = snap["price"]
        if live_price <= 0 and not df_5m.empty:
            live_price = float(df_5m['close'].iloc[-1])
        if live_price <= 0:
            live_price = 79700.0 if "BTC" in code.upper() else 488.0

        # 2. 宏觀方向 (TREND_BIAS)
        trend_bias = 0
        trend_bias_str = "⚪ 0 (中立震盪)"
        pdh_line, pdl_line = live_price * 1.008, live_price * 0.992

        if not df_day.empty and len(df_day) >= 2:
            df_day['ema20'] = df_day['close'].ewm(span=20, adjust=False).mean()
            last_day = df_day.iloc[-1]
            prev_day = df_day.iloc[-2]
            pdh_line = float(prev_day.get('high', live_price * 1.008))
            pdl_line = float(prev_day.get('low', live_price * 0.992))
            if float(last_day['close']) > float(last_day['ema20']):
                trend_bias = 1
                trend_bias_str = "🟢 1 (多頭控盤 [日線>EMA20])"
            else:
                trend_bias = -1
                trend_bias_str = "🔴 -1 (空頭壓制 [日線<EMA20])"

        # 3. 天花板與地板 (SBR / RBS)
        hr_res = pdh_line
        hr_sup = pdl_line
        if not df_1h.empty and len(df_1h) >= 5:
            hr_res = float(df_1h['high'].tail(20).max())
            hr_sup = float(df_1h['low'].tail(20).min())

        dist_res = hr_res - live_price
        dist_sup = live_price - hr_sup

        # 4. 5M 量能門禁與形態判定
        vol_ratio = 1.0
        vol_heavy = False
        bar_time_str = datetime.datetime.now(tz_ny).strftime('%Y-%m-%d %H:%M')
        atr_val = live_price * 0.003

        bull_2b, bear_2b = False, False

        if not df_5m.empty and len(df_5m) >= 5:
            bar_time_str = str(df_5m['time_key'].iloc[-1])
            df_5m['vma20'] = df_5m['volume'].rolling(20).mean()
            df_5m['atr14'] = self.calculate_atr(df_5m, 14)

            last_5m = df_5m.iloc[-1]
            c_curr, o_curr = float(last_5m['close']), float(last_5m['open'])
            h_curr, l_curr = float(last_5m['high']), float(last_5m['low'])
            v_curr = float(last_5m['volume'])
            vma_curr = float(last_5m['vma20']) if pd.notna(last_5m.get('vma20')) and last_5m['vma20'] > 0 else 1.0
            
            vol_ratio = v_curr / vma_curr
            vol_heavy = vol_ratio >= 1.25

            llv5 = float(df_5m['low'].iloc[-6:-1].min()) if len(df_5m) >= 6 else l_curr
            hhv5 = float(df_5m['high'].iloc[-6:-1].max()) if len(df_5m) >= 6 else h_curr

            bull_2b = (l_curr < llv5 or l_curr < pdl_line) and (c_curr > llv5) and (c_curr > o_curr)
            bear_2b = (h_curr > hhv5 or h_curr > pdh_line) and (c_curr < hhv5) and (c_curr < o_curr)

        # 5. 1:2 結構預案
        plan_sell_sl = hr_res + 0.5 * atr_val
        plan_sell_tp = hr_res - 2.0 * (plan_sell_sl - hr_res)
        plan_buy_sl = hr_sup - 0.5 * atr_val
        plan_buy_tp = hr_sup + 2.0 * (hr_sup - plan_buy_sl)

        tactical_sig = "⚪ 待機中"
        action_detail = f"☕ 處於安全中繼區 (距天花板差 ${dist_res:+.2f}，距地板差 ${dist_sup:+.2f})。嚴禁半山腰開單，耐心等待觸碰戰區"

        if bull_2b and vol_heavy and trend_bias >= 0:
            tactical_sig = "🟢 觸發 2B 破底翻做多"
            sl = live_price - 0.5 * atr_val
            tp = live_price + 2.0 * (live_price - sl)
            action_detail = f"🔥 【立即買入 Call】入: ${live_price:,.2f} | 止: ${sl:,.2f} | 2R盈: ${tp:,.2f}"
        elif bear_2b and vol_heavy and trend_bias <= 0:
            tactical_sig = "🔴 觸發 2B 假突破衝頂做空"
            sl = live_price + 0.5 * atr_val
            tp = live_price - 2.0 * (sl - live_price)
            action_detail = f"🔥 【立即買入 Put】入: ${live_price:,.2f} | 止: ${sl:,.2f} | 2R盈: ${tp:,.2f}"
        elif dist_res <= (live_price * 0.002):
            tactical_sig = "🟡 進入阻力埋伏圈"
            action_detail = f"👀 價格已逼近天花板 (${hr_res:,.2f})！正在等待 5M 刺穿衝頂且放量 ≥ 1.25x 立即做空"
        elif dist_sup <= (live_price * 0.002):
            tactical_sig = "🟡 進入支撐埋伏圈"
            action_detail = f"👀 價格已逼近地板 (${hr_sup:,.2f})！正在等待 5M 扎針破底翻且放量 ≥ 1.25x 立即做多"

        # ====== 畫面渲染 (純 Streamlit 官方原生組件) ======
        st.success(f"📶 數據通道: **{snap['source']}** | 撮合時間: **{snap['server_time']} ET** | 延遲: **{snap['latency_ms']} ms** | 📅 5M 棒線: **{bar_time_str}**")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("最新現價 (Live)", f"${live_price:,.2f}")
        col2.metric("宏觀方向 (Trend Bias)", trend_bias_str)
        col3.metric("5M 量能門禁", f"{vol_ratio:.2f}x", "🟢 放量達標" if vol_heavy else "⚪ 常規縮量")
        col4.metric("戰術信號", tactical_sig)

        st.divider()

        st.markdown("##### 🎯 預判雷達 (清楚掌握上下邊界與 1:2 預案)")
        radar_df = pd.DataFrame({
            "戰區方向": ["🔴 上方阻力 (天花板 / SBR)", "🟢 下方支撐 (地板 / RBS)"],
            "關鍵點位": [f"${hr_res:,.2f}", f"${hr_sup:,.2f}"],
            "距離現價差額": [f"${dist_res:+.2f}", f"${dist_sup:+.2f}"],
            "觸發預案 (1:2 結構)": [
                f"觸碰放量買 Put (入: ${hr_res:,.2f} | 止: ${plan_sell_sl:,.2f} | 盈: ${plan_sell_tp:,.2f})",
                f"踩線放量買 Call (入: ${hr_sup:,.2f} | 止: ${plan_buy_sl:,.2f} | 盈: ${plan_buy_tp:,.2f})"
            ]
        })
        st.dataframe(radar_df, use_container_width=True, hide_index=True)

        st.info(f"**🎯 0DTE 操作指示**：{action_detail}")
