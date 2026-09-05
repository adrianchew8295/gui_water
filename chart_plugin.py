# 文件名: chart_plugin.py
# 核心功能: 穩定防白屏引擎 + 毫秒級快照 + 預判雷達 + 富途指標 1:2 結構 (純數據座艙)

import os
import time
import datetime
import numpy as np
import pandas as pd
import pytz
import streamlit as st
import yfinance as yf
from moomoo import OpenQuoteContext, RET_OK, KLType, SubType, AuType
from trendline_engine import compute_demark_trendlines

tz_ny = pytz.timezone("America/New_York")
DATA_DIR = './market_data'
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
        """【極速毫秒快照】只查一筆現價，耗時小於 15ms"""
        res = {
            "price": 0.0, "source": "未連線", "server_time": "--",
            "latency_ms": 0, "open": 0.0, "high": 0.0, "low": 0.0, "vol": 0.0
        }
        t_start = time.time()
        target_symbol = "CC.BTCUSD" if "BTC" in code.upper() else code

        # 1. 優先嘗試 OpenD
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
                res["source"] = "🟢 OpenD 毫秒直連"
                res["server_time"] = str(row.get('update_time', datetime.datetime.now(tz_ny).strftime('%H:%M:%S.%f')[:-3]))
                res["latency_ms"] = int((time.time() - t_start) * 1000)
                return res
        except Exception:
            pass
        finally:
            if quote_ctx:
                try: quote_ctx.close()
                except: pass

        # 2. 備用通道 yfinance
        try:
            yf_sym = "BTC-USD" if "BTC" in code.upper() else "QQQ"
            fast_p = yf.Ticker(yf_sym).fast_info.last_price
            if fast_p:
                res["price"] = float(fast_p)
                res["source"] = "🟡 yfinance 實時備援"
                res["server_time"] = datetime.datetime.now(tz_ny).strftime('%H:%M:%S')
                res["latency_ms"] = int((time.time() - t_start) * 1000)
                return res
        except Exception:
            pass

        return res

    def load_local_or_fetch(self, code: str, ktype_name: str) -> pd.DataFrame:
        """安全加載 K 線，本地有的直接讀，絕不高頻重複向網絡請求"""
        is_btc = "BTC" in code.upper()
        save_prefix = "CC_BTCUSD" if is_btc else code.replace('.', '_')
        file_path = os.path.join(self.data_dir, f"{save_prefix}_{ktype_name}.csv")

        # 優先讀取本地已有的 CSV
        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path)
                df.columns = [c.lower() for c in df.columns]
                df['time_key'] = pd.to_datetime(df['time_key'])
                if not df.empty:
                    return df
            except Exception:
                pass

        # 若本地沒有，安全拉取一次
        try:
            yf_sym = "BTC-USD" if is_btc else "QQQ"
            interval_map = {"5M": "5m", "1Hr": "60m", "DAY": "1d"}
            period_map = {"5M": "5d", "1Hr": "1mo", "DAY": "1y"}
            df_yf = yf.download(
                tickers=yf_sym, period=period_map.get(ktype_name, "5d"),
                interval=interval_map.get(ktype_name, "5m"), prepost=True, progress=False, auto_adjust=False
            )
            if not df_yf.empty:
                df_yf.columns = [c[0].lower() if isinstance(df_yf.columns, pd.MultiIndex) else c.lower() for c in df_yf.columns]
                df_yf = df_yf.reset_index()
                dt_col = 'Datetime' if 'Datetime' in df_yf.columns else ('Date' if 'Date' in df_yf.columns else df_yf.columns[0])
                df_yf['time_key'] = pd.to_datetime(df_yf[dt_col])
                if df_yf['time_key'].dt.tz is None:
                    df_yf['time_key'] = df_yf['time_key'].dt.tz_localize('UTC').dt.tz_convert(tz_ny)
                else:
                    df_yf['time_key'] = df_yf['time_key'].dt.tz_convert(tz_ny)
                df_yf['time_key'] = df_yf['time_key'].dt.tz_localize(None)
                clean_df = df_yf[['time_key', 'open', 'close', 'high', 'low', 'volume']].dropna().sort_values('time_key').reset_index(drop=True)
                clean_df.to_csv(file_path, index=False)
                return clean_df
        except Exception:
            pass

        return pd.DataFrame()

    def render_cockpit(self, code: str):
        """【主座艙渲染】：全防禦 Try-Catch，確保絕對不白屏"""
        try:
            # 1. 抓取即時快照
            snap = self.get_realtime_snapshot(code)
            
            # 2. 讀取數據 (讀取本地快照，極速零延遲)
            df_day = self.load_local_or_fetch(code, "DAY")
            df_1h = self.load_local_or_fetch(code, "1Hr")
            df_5m = self.load_local_or_fetch(code, "5M")

            # 確定現價
            last_close = float(df_5m['close'].iloc[-1]) if not df_5m.empty else (float(df_day['close'].iloc[-1]) if not df_day.empty else 0.0)
            live_price = snap["price"] if snap["price"] > 0 else last_close

            if live_price == 0.0:
                st.warning("⏳ 正在建立數據通信，請稍候 1~2 秒...")
                return

            # 3. 計算 TREND_BIAS (日線大門)
            trend_bias = 0
            trend_text = "⚪ 0 (中立震盪)"
            pdh_line, pdl_line = live_price * 1.01, live_price * 0.99
            
            if not df_day.empty and len(df_day) >= 2:
                df_day['ema20'] = df_day['close'].ewm(span=20, adjust=False).mean()
                last_day = df_day.iloc[-1]
                prev_day = df_day.iloc[-2]
                pdh_line = float(prev_day['high'])
                pdl_line = float(prev_day['low'])
                if float(last_day['close']) > float(last_day['ema20']):
                    trend_bias = 1
                    trend_text = "🟢 1 (多頭控盤 [日線>EMA20])"
                else:
                    trend_bias = -1
                    trend_text = "🔴 -1 (空頭壓制 [日線<EMA20])"

            # 4. 計算 1H 關鍵天花板與地板
            hr_res = pdh_line if pdh_line > 0 else (live_price * 1.01)
            hr_sup = pdl_line if pdl_line > 0 else (live_price * 0.99)
            if not df_1h.empty and len(df_1h) >= 10:
                try:
                    td_1h = compute_demark_trendlines(df_1h, window=4)
                    hr_res = td_1h.get('curr_res_val') or hr_res
                    hr_sup = td_1h.get('curr_sup_val') or hr_sup
                except Exception:
                    pass

            # 5. 計算 5M 量能與形態池
            vol_ratio = 1.0
            vol_heavy = False
            atr_val = live_price * 0.003
            bar_time_str = datetime.datetime.now(tz_ny).strftime('%Y-%m-%d %H:%M')

            bull_2b, bear_2b = False, False
            bull_star, bear_star = False, False

            if not df_5m.empty and len(df_5m) >= 6:
                bar_time_str = str(df_5m['time_key'].iloc[-1])
                df_5m['atr14'] = self.calculate_atr(df_5m, 14)
                df_5m['vol_ma'] = df_5m['volume'].rolling(20).mean()
                
                last_5m = df_5m.iloc[-1]
                prev_5m = df_5m.iloc[-2]
                prev2_5m = df_5m.iloc[-3]

                c_curr = float(last_5m['close'])
                o_curr = float(last_5m['open'])
                h_curr = float(last_5m['high'])
                l_curr = float(last_5m['low'])
                v_curr = float(last_5m['volume'])
                vma_curr = float(last_5m['vol_ma']) if pd.notna(last_5m.get('vol_ma')) and last_5m['vol_ma'] > 0 else 1.0
                atr_val = float(last_5m['atr14']) if pd.notna(last_5m.get('atr14')) else atr_val

                vol_ratio = v_curr / vma_curr
                vol_heavy = vol_ratio >= 1.25

                llv5 = float(df_5m['low'].iloc[-6:-1].min())
                hhv5 = float(df_5m['high'].iloc[-6:-1].max())

                bull_2b = (l_curr < llv5 or l_curr < pdl_line) and (c_curr > llv5) and (c_curr > o_curr)
                bear_2b = (h_curr > hhv5 or h_curr > pdh_line) and (c_curr < hhv5) and (c_curr < o_curr)
                bull_star = (float(prev2_5m['close']) < float(prev2_5m['open'])) and (abs(float(prev_5m['close']) - float(prev_5m['open'])) <= 0.35 * (float(prev_5m['high']) - float(prev_5m['low']))) and (c_curr > o_curr)
                bear_star = (float(prev2_5m['close']) > float(prev2_5m['open'])) and (abs(float(prev_5m['close']) - float(prev_5m['open'])) <= 0.35 * (float(prev_5m['high']) - float(prev_5m['low']))) and (c_curr < o_curr)

            # 6. 空間距離與 1:2 結構指令判定
            dist_res = hr_res - live_price
            dist_sup = live_price - hr_sup

            plan_sell_sl = hr_res + 0.5 * atr_val
            plan_sell_tp = hr_res - 2.0 * (plan_sell_sl - hr_res)
            plan_buy_sl = hr_sup - 0.5 * atr_val
            plan_buy_tp = hr_sup + 2.0 * (hr_sup - plan_buy_sl)

            tactical_signal = "⚪ 待機中"
            action_plan = f"☕ 處於安全中繼區（距天花板差 ${dist_res:.2f}，距地板差 ${dist_sup:.2f}）。嚴禁在半山腰開單，耐心等待觸碰戰區"
            border_color = "#30363d"
            flash_bg = "#0d1117"

            if bull_2b and vol_heavy and trend_bias >= 0:
                tactical_signal = "🟢 觸發 2B 破底翻做多"
                sl = live_price - 0.5 * atr_val
                tp = live_price + 2.0 * (live_price - sl)
                action_plan = f"🔥 【立即執行】買入 0DTE ATM Call！入: ${live_price:,.2f} | 止損: ${sl:,.2f} | 2R止盈: ${tp:,.2f}"
                border_color = "#00E676"
                flash_bg = "#06301d"
            elif bear_2b and vol_heavy and trend_bias <= 0:
                tactical_signal = "🔴 觸發 2B 假突破衝頂做空"
                sl = live_price + 0.5 * atr_val
                tp = live_price - 2.0 * (sl - live_price)
                action_plan = f"🔥 【立即執行】買入 0DTE ATM Put！入: ${live_price:,.2f} | 止損: ${sl:,.2f} | 2R止盈: ${tp:,.2f}"
                border_color = "#FF5252"
                flash_bg = "#380a0e"
            elif bull_star and vol_heavy and trend_bias >= 0:
                tactical_signal = "🟢 觸發晨星做多"
                sl = live_price - 0.5 * atr_val
                tp = live_price + 2.0 * (live_price - sl)
                action_plan = f"🔥 【立即執行】形態做多！入: ${live_price:,.2f} | 止損: ${sl:,.2f} | 2R止盈: ${tp:,.2f}"
                border_color = "#00E676"
                flash_bg = "#06301d"
            elif bear_star and vol_heavy and trend_bias <= 0:
                tactical_signal = "🔴 觸發暮星做空"
                sl = live_price + 0.5 * atr_val
                tp = live_price - 2.0 * (sl - live_price)
                action_plan = f"🔥 【立即執行】形態做空！入: ${live_price:,.2f} | 止損: ${sl:,.2f} | 2R止盈: ${tp:,.2f}"
                border_color = "#FF5252"
                flash_bg = "#380a0e"
            elif dist_res <= (live_price * 0.002):
                tactical_signal = "🟡 進入阻力埋伏圈"
                action_plan = f"👀 價格已逼近天花板 (${hr_res:,.2f})！盯緊 5M 刺穿衝頂 + 量能 ≥ 1.25x 立即買 Put"
                border_color = "#FFD700"
            elif dist_sup <= (live_price * 0.002):
                tactical_signal = "🟡 進入支撐埋伏圈"
                action_plan = f"👀 價格已逼近地板 (${hr_sup:,.2f})！盯緊 5M 扎針拉回 + 量能 ≥ 1.25x 立即買 Call"
                border_color = "#FFD700"

            # ====== 渲染 HTML 結構化純數據座艙 ======
            cockpit_html = f"""
            <div style="background-color: {flash_bg}; padding: 18px; border-radius: 10px; border: 2px solid {border_color}; margin-bottom: 15px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
                <!-- 模組 1: 頂部真實性心跳與數據憑證 -->
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #21262d; padding-bottom: 10px;">
                    <div style="font-size: 18px; font-weight: bold; color: #58a6ff;">
                        ⚡ 癸水 · 極速純數據實戰座艙 ({code})
                    </div>
                    <div style="font-size: 13px; color: #8b949e;">
                        {snap['source']} | 延遲: <b style="color: #00E676;">{snap['latency_ms']}ms</b> | 撮合時間: <b style="color: #ffd700;">{snap['server_time']}</b> | 💾 CSV已同步
                    </div>
                </div>
                
                <div style="font-size: 12px; color: #8b949e; margin-top: 6px;">
                    📅 5M 數據時段: <b style="color: #f0f6fc;">{bar_time_str} ET</b>
                </div>

                <!-- 模組 2: 核心跳動與宏觀戰區 -->
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 15px;">
                    <div style="background: #161b22; padding: 12px; border-radius: 6px;">
                        <div style="color: #8b949e; font-size: 12px;">最新現價 (Live Tick)</div>
                        <div style="font-size: 24px; font-weight: bold; color: #ffd700; margin-top: 4px;">${live_price:,.2f}</div>
                    </div>
                    <div style="background: #161b22; padding: 12px; border-radius: 6px;">
                        <div style="color: #8b949e; font-size: 12px;">宏觀方向 (Trend Bias)</div>
                        <div style="font-size: 14px; font-weight: bold; color: #f0f6fc; margin-top: 8px;">{trend_text}</div>
                    </div>
                    <div style="background: #161b22; padding: 12px; border-radius: 6px;">
                        <div style="color: #8b949e; font-size: 12px;">5M 放量門禁 (VOL_HEAVY)</div>
                        <div style="font-size: 15px; font-weight: bold; color: {'#00E676' if vol_heavy else '#8b949e'}; margin-top: 6px;">
                            {vol_ratio:.2f}x ({'🟢 放量達標' if vol_heavy else '⚪ 常規縮量'})
                        </div>
                    </div>
                    <div style="background: #161b22; padding: 12px; border-radius: 6px;">
                        <div style="color: #8b949e; font-size: 12px;">戰術狀態 (Tactical)</div>
                        <div style="font-size: 15px; font-weight: bold; color: #00E5FF; margin-top: 6px;">{tactical_signal}</div>
                    </div>
                </div>

                <!-- 模組 3: 預判雷達 (Prediction Radar) -->
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px;">
                    <div style="background: #161b22; padding: 12px; border-radius: 6px; border-left: 4px solid #FF5252;">
                        <div style="color: #ff7b72; font-size: 12px; font-weight: bold;">🔴 上方做空埋伏圈 (SBR / 天花板)</div>
                        <div style="font-size: 15px; color: #f0f6fc; margin-top: 4px;">
                            關鍵點位: <b>${hr_res:,.2f}</b> | 還差: <b style="color: #ff7b72;">${dist_res:+.2f}</b>
                        </div>
                        <div style="font-size: 12px; color: #8b949e; margin-top: 4px;">
                            預案: 觸碰放量買 Put (入: ${hr_res:,.2f} | 止: ${plan_sell_sl:,.2f} | 2R盈: ${plan_sell_tp:,.2f})
                        </div>
                    </div>
                    <div style="background: #161b22; padding: 12px; border-radius: 6px; border-left: 4px solid #00E676;">
                        <div style="color: #7ee787; font-size: 12px; font-weight: bold;">🟢 下方做多埋伏圈 (RBS / 地板)</div>
                        <div style="font-size: 15px; color: #f0f6fc; margin-top: 4px;">
                            關鍵點位: <b>${hr_sup:,.2f}</b> | 還差: <b style="color: #7ee787;">${dist_sup:+.2f}</b>
                        </div>
                        <div style="font-size: 12px; color: #8b949e; margin-top: 4px;">
                            預案: 踩線放量買 Call (入: ${hr_sup:,.2f} | 止: ${plan_buy_sl:,.2f} | 2R盈: ${plan_buy_tp:,.2f})
                        </div>
                    </div>
                </div>

                <!-- 模組 4: 1:2 結構執行動作與 0DTE 指令 -->
                <div style="margin-top: 14px; background: #161b22; padding: 14px; border-radius: 6px; border-left: 5px solid {border_color};">
                    <div style="font-size: 12px; color: #8b949e;">🎯 當前具體執行指令 (Action Plan & 0DTE 扳機)</div>
                    <div style="font-size: 15px; font-weight: bold; color: #ffffff; margin-top: 4px;">
                        {action_plan}
                    </div>
                </div>
            </div>
            """
            st.markdown(cockpit_html, unsafe_allow_html=True)
            
        except Exception as e:
            st.error(f"❌ 座艙運算防護觸發: {str(e)}")
