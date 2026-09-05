# 文件名: chart_plugin.py
# 核心功能: 毫秒級快照 + 完整富途指標 (Trend Bias/2B/Morning Star/Engulfing/1:2 結構盈虧線)

import os
import datetime
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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

    def get_realtime_snapshot_price(self, code: str) -> dict:
        """【極速毫秒通道】獲取最新盤口撮合快照"""
        res = {"price": None, "source": "未連線", "time_str": "", "open": None, "high": None, "low": None, "vol": 0}
        quote_ctx = None
        try:
            quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
            target_symbol = "CC.BTCUSD" if "BTC" in code.upper() else code
            ret, df_snap = quote_ctx.get_market_snapshot([target_symbol])
            if ret == RET_OK and not df_snap.empty:
                row = df_snap.iloc[0]
                res["price"] = float(row['last_price'])
                res["open"] = float(row.get('open_price', row['last_price']))
                res["high"] = float(row.get('high_price', row['last_price']))
                res["low"] = float(row.get('low_price', row['last_price']))
                res["vol"] = float(row.get('volume', 0))
                res["source"] = "🟢 OpenD 毫秒極速快照"
                res["time_str"] = str(row.get('update_time', datetime.datetime.now(tz_ny).strftime('%H:%M:%S.%f')[:-3]))
                return res
        except Exception:
            pass
        finally:
            if quote_ctx:
                try: quote_ctx.close()
                except: pass

        try:
            yf_sym = "BTC-USD" if "BTC" in code.upper() else "QQQ"
            ticker = yf.Ticker(yf_sym)
            fast_p = ticker.fast_info.last_price
            if fast_p:
                res["price"] = float(fast_p)
                res["source"] = "🟡 yfinance 實時"
                res["time_str"] = datetime.datetime.now(tz_ny).strftime('%H:%M:%S')
                return res
        except Exception:
            pass

        return res

    def get_live_data_and_upsert(self, code: str, ktype_name: str) -> tuple:
        """獲取多週期 K 線數據"""
        is_btc = "BTC" in code.upper()
        save_prefix = "CC_BTCUSD" if is_btc else code.replace('.', '_')
        file_path = os.path.join(self.data_dir, f"{save_prefix}_{ktype_name}.csv")

        df_base = pd.DataFrame()
        if os.path.exists(file_path):
            try:
                df_base = pd.read_csv(file_path)
                df_base.columns = [c.lower() for c in df_base.columns]
                df_base['time_key'] = pd.to_datetime(df_base['time_key'])
            except Exception:
                pass

        df_live = pd.DataFrame()
        data_source = "🟢 OpenD 原生實時"

        quote_ctx = None
        try:
            quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
            kl_type = KLType.K_5M if ktype_name == "5M" else (KLType.K_60M if ktype_name == "1Hr" else KLType.K_DAY)
            sub_type = SubType.K_5M if ktype_name == "5M" else (SubType.K_60M if ktype_name == "1Hr" else SubType.K_DAY)
            target_symbol = "CC.BTCUSD" if is_btc else code

            sub_ret, _ = quote_ctx.subscribe([target_symbol], [sub_type])
            if sub_ret == RET_OK:
                ret, df_k = quote_ctx.get_cur_kline(target_symbol, 200, kl_type, AuType.NONE)
                if ret == RET_OK and not df_k.empty:
                    df_live = df_k[['time_key', 'open', 'close', 'high', 'low', 'volume']].copy()
                    df_live['time_key'] = pd.to_datetime(df_live['time_key'])
        except Exception:
            pass
        finally:
            if quote_ctx:
                try: quote_ctx.close()
                except: pass

        if df_live.empty and df_base.empty:
            try:
                yf_sym = "BTC-USD" if is_btc else "QQQ"
                interval_map = {"5M": "5m", "1Hr": "60m", "DAY": "1d", "WEEK": "1wk"}
                period_map = {"5M": "5d", "1Hr": "1mo", "DAY": "1y", "WEEK": "2y"}
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
                    df_live = df_yf[['time_key', 'open', 'close', 'high', 'low', 'volume']].dropna()
                    data_source = "🟡 yfinance 實時接管"
            except Exception:
                pass

        if not df_live.empty:
            if not df_base.empty:
                df_merged = pd.concat([df_base, df_live]).drop_duplicates(subset=['time_key'], keep='last')
            else:
                df_merged = df_live
            df_merged = df_merged.sort_values('time_key').reset_index(drop=True)
            try:
                df_merged.to_csv(file_path, index=False)
            except Exception:
                pass
            return df_merged, data_source

        if not df_base.empty:
            return df_base, "🛡️ 本地歷史快照"

        return pd.DataFrame(), "❌ 無可用數據源"

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """計算 ATR14 波動率"""
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        tr = np.maximum(high - low, np.maximum((high - close).abs(), (low - close).abs()))
        return tr.rolling(window=period).mean().bfill()

    def render_flash_cockpit_table(self, code: str):
        """【Tab 2 專屬】：富途指標全套轉譯 + 毫秒級 Flash 閃爍實戰 Table"""
        snap = self.get_realtime_snapshot_price(code)
        
        # 1. 提取日線計算 TREND_BIAS (自動計算，不手填)
        df_day, _ = self.get_live_data_and_upsert(code, "DAY")
        trend_bias = 0
        trend_label = "⚪ 中立震盪 (0)"
        pdh_line, pdl_line = 0.0, 0.0
        
        if not df_day.empty and len(df_day) >= 2:
            df_day['ema20'] = df_day['close'].ewm(span=20, adjust=False).mean()
            last_day = df_day.iloc[-1]
            prev_day = df_day.iloc[-2]
            pdh_line = float(prev_day['high'])
            pdl_line = float(prev_day['low'])
            if float(last_day['close']) > float(last_day['ema20']):
                trend_bias = 1
                trend_label = "🟢 多頭掌控 (1) [日線>EMA20]"
            elif float(last_day['close']) < float(last_day['ema20']):
                trend_bias = -1
                trend_label = "🔴 空頭掌控 (-1) [日線<EMA20]"

        # 2. 提取 5M 數據並計算形態池與 1:2 結構盈虧
        df_5m, _ = self.get_live_data_and_upsert(code, "5M")
        if df_5m.empty or len(df_5m) < 10:
            st.warning("⚠️ 正在載入 5M 深度盤口數據...")
            return

        live_price = snap["price"] if snap["price"] else float(df_5m['close'].iloc[-1])
        
        # ATR 與 LWMA20 (WMA)
        df_5m['atr14'] = self.calculate_atr(df_5m, 14)
        weights = np.arange(1, 21)
        df_5m['lwma20'] = df_5m['close'].rolling(20).apply(lambda prices: np.dot(prices, weights)/weights.sum(), raw=True)
        df_5m['vol_ma'] = df_5m['volume'].rolling(20).mean()
        
        c_curr = float(df_5m['close'].iloc[-1])
        o_curr = float(df_5m['open'].iloc[-1])
        h_curr = float(df_5m['high'].iloc[-1])
        l_curr = float(df_5m['low'].iloc[-1])
        v_curr = float(df_5m['volume'].iloc[-1])
        vma_curr = float(df_5m['vol_ma'].iloc[-1]) if pd.notna(df_5m['vol_ma'].iloc[-1]) else 1.0
        atr_curr = float(df_5m['atr14'].iloc[-1]) if pd.notna(df_5m['atr14'].iloc[-1]) else 1.0
        
        vol_ratio = v_curr / vma_curr if vma_curr > 0 else 1.0
        vol_heavy = vol_ratio >= 1.25  # 富途放量門禁

        # 前 5 根極值 (REF(LLV, 1) / REF(HHV, 1))
        llv5 = float(df_5m['low'].iloc[-6:-1].min()) if len(df_5m) >= 6 else l_curr
        hhv5 = float(df_5m['high'].iloc[-6:-1].max()) if len(df_5m) >= 6 else h_curr

        # 形態判斷 (Morning Star / Evening Star / Engulfing / 2B)
        prev1 = df_5m.iloc[-2]
        prev2 = df_5m.iloc[-3]
        
        bull_2b = (l_curr < llv5 or (pdl_line > 0 and l_curr < pdl_line)) and (c_curr > llv5) and (c_curr > o_curr)
        bear_2b = (h_curr > hhv5 or (pdh_line > 0 and h_curr > pdh_line)) and (c_curr < hhv5) and (c_curr < o_curr)
        
        bull_engulf = (c_curr > o_curr) and (float(prev1['close']) < float(prev1['open'])) and (c_curr >= float(prev1['open']))
        bear_engulf = (c_curr < o_curr) and (float(prev1['close']) > float(prev1['open'])) and (c_curr <= float(prev1['open']))
        
        bull_star = (float(prev2['close']) < float(prev2['open'])) and (abs(float(prev1['close']) - float(prev1['open'])) <= 0.35 * (float(prev1['high']) - float(prev1['low']))) and (c_curr > o_curr)
        bear_star = (float(prev2['close']) > float(prev2['open'])) and (abs(float(prev1['close']) - float(prev1['open'])) <= 0.35 * (float(prev1['high']) - float(prev1['low']))) and (c_curr < o_curr)

        # 戰術指令判定 (只在 Trend Bias 允許下出信號)
        signal_type = "⚪ 等待形態到位"
        setup_name = "--"
        entry_p, sl_p, tp_p = 0.0, 0.0, 0.0
        action_desc = "區間震盪觀望中，嚴格等待放量與邊界信號"
        flash_bg = "#161b22"

        if bull_2b and vol_heavy and trend_bias >= 0:
            setup_name = "▲▲ 2B 破底翻"
            signal_type = "🟢 觸發 2B 做多 (BUY CALL)"
            entry_p = live_price
            sl_p = l_curr - 0.5 * atr_curr
            tp_p = entry_p + 2.0 * (entry_p - sl_p)
            action_desc = f"🔥 買入 0DTE ATM Call！入場: ${entry_p:.2f} | 止損: ${sl_p:.2f} | 2R止盈: ${tp_p:.2f}"
            flash_bg = "#08492c"
        elif bear_2b and vol_heavy and trend_bias <= 0:
            setup_name = "▼▼ 2B 假突破衝頂"
            signal_type = "🔴 觸發 2B 做空 (BUY PUT)"
            entry_p = live_price
            sl_p = h_curr + 0.5 * atr_curr
            tp_p = entry_p - 2.0 * (sl_p - entry_p)
            action_desc = f"🔥 買入 0DTE ATM Put！入場: ${entry_p:.2f} | 止損: ${sl_p:.2f} | 2R止盈: ${tp_p:.2f}"
            flash_bg = "#4c0d12"
        elif (bull_engulf or bull_star) and vol_heavy and trend_bias >= 0:
            setup_name = "▲ Morning Star / 吞沒"
            signal_type = "🟢 標準做多 (CALL)"
            entry_p = live_price
            sl_p = l_curr - 0.5 * atr_curr
            tp_p = entry_p + 2.0 * (entry_p - sl_p)
            action_desc = f"🔥 形態確認做多！入場: ${entry_p:.2f} | 止損: ${sl_p:.2f} | 2R止盈: ${tp_p:.2f}"
            flash_bg = "#08492c"
        elif (bear_engulf or bear_star) and vol_heavy and trend_bias <= 0:
            setup_name = "▼ Evening Star / 吞沒"
            signal_type = "🔴 標準做空 (PUT)"
            entry_p = live_price
            sl_p = h_curr + 0.5 * atr_curr
            tp_p = entry_p - 2.0 * (sl_p - entry_p)
            action_desc = f"🔥 形態確認做空！入場: ${entry_p:.2f} | 止損: ${sl_p:.2f} | 2R止盈: ${tp_p:.2f}"
            flash_bg = "#4c0d12"

        # 渲染 HTML Flash 動態呼吸閃爍 Table
        now_time = datetime.datetime.now(tz_ny).strftime('%H:%M:%S.%f')[:-4]
        
        flash_html = f"""
        <div style="background-color: {flash_bg}; padding: 16px; border-radius: 8px; border: 1px solid #30363d; margin-bottom: 12px; transition: all 0.2s ease;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 20px; font-weight: bold; color: #58a6ff;">⚡ 毫秒極速實戰座艙 ({code})</span>
                <span style="color: #8b949e; font-size: 13px;">撮合時間 (ET): <b style="color: #e6edf3;">{now_time}</b> | {snap['source']}</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 12px;">
                <div style="background: #0d1117; padding: 10px; border-radius: 6px;">
                    <div style="color: #8b949e; font-size: 12px;">最新撮合現價 (Live)</div>
                    <div style="font-size: 24px; font-weight: bold; color: #ffd700;">${live_price:,.2f}</div>
                </div>
                <div style="background: #0d1117; padding: 10px; border-radius: 6px;">
                    <div style="color: #8b949e; font-size: 12px;">宏觀方向 (Trend Bias)</div>
                    <div style="font-size: 14px; font-weight: bold; margin-top: 4px;">{trend_label}</div>
                </div>
                <div style="background: #0d1117; padding: 10px; border-radius: 6px;">
                    <div style="color: #8b949e; font-size: 12px;">5M 放量門禁 (VOL_HEAVY)</div>
                    <div style="font-size: 15px; font-weight: bold; color: {'#00E676' if vol_heavy else '#8b949e'}; margin-top: 4px;">
                        {vol_ratio:.2f}x ({'🟢 放量達標' if vol_heavy else '⚪ 常規縮量'})
                    </div>
                </div>
                <div style="background: #0d1117; padding: 10px; border-radius: 6px;">
                    <div style="color: #8b949e; font-size: 12px;">形態池確認 (Setup)</div>
                    <div style="font-size: 15px; font-weight: bold; color: #00E5FF; margin-top: 4px;">{setup_name}</div>
                </div>
            </div>
            <div style="margin-top: 12px; background: #0d1117; padding: 12px; border-radius: 6px; border-left: 4px solid {'#00E676' if '做多' in signal_type else ('#FF5252' if '做空' in signal_type else '#8b949e')};">
                <div style="font-size: 13px; color: #8b949e;">🎯 1:2 結構指令 (PART 8 對齊) & 0DTE 開倉動作</div>
                <div style="font-size: 16px; font-weight: bold; color: #ffffff; margin-top: 4px;">{action_desc}</div>
            </div>
        </div>
        """
        st.markdown(flash_html, unsafe_allow_html=True)

    def render_static_chart(self, code: str, ktype_name: str):
        """【Tab 1 專屬】：完全保留原圖表畫布與指標"""
        try:
            df, _ = self.get_live_data_and_upsert(code, ktype_name)
            if df.empty:
                st.error(f"❌ 無法加載 {code} 圖表數據")
                return

            current_price = float(df['close'].iloc[-1])
            df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
            df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
            df['time_clean'] = df['time_key'].dt.strftime('%m-%d %H:%M') if ktype_name in ['5M', '1Hr'] else df['time_key'].dt.strftime('%Y-%m-%d')
            df['vma20'] = df['volume'].rolling(window=20).mean()
            df['vma_15x'] = df['vma20'] * 1.5
            df['vma_20x'] = df['vma20'] * 2.0

            td_res = compute_demark_trendlines(df, window=4)
            df_plot = df.tail(200).copy().reset_index(drop=True)
            
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])

            fig.add_trace(go.Candlestick(
                x=df_plot['time_clean'], open=df_plot['open'], high=df_plot['high'], low=df_plot['low'], close=df_plot['close'],
                name="K線", increasing_line_color="#089981", decreasing_line_color="#F23645"
            ), row=1, col=1)

            fig.add_trace(go.Scatter(x=df_plot['time_clean'], y=df_plot['ema9'], mode='lines', line=dict(color='#00E5FF', width=1.5), name="EMA9"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_plot['time_clean'], y=df_plot['ema20'], mode='lines', line=dict(color='#FFA726', width=1.5), name="EMA20"), row=1, col=1)

            if td_res.get("resistance_line"):
                res_df = pd.DataFrame(td_res["resistance_line"])
                fig.add_trace(go.Scatter(x=df_plot['time_clean'].iloc[-len(res_df):], y=res_df['value'], mode='lines', line=dict(color='#FF5252', width=2, dash='dash'), name="TD 阻力線"), row=1, col=1)

            if td_res.get("support_line"):
                sup_df = pd.DataFrame(td_res["support_line"])
                fig.add_trace(go.Scatter(x=df_plot['time_clean'].iloc[-len(sup_df):], y=sup_df['value'], mode='lines', line=dict(color='#00E676', width=2, dash='dash'), name="TD 支撐線"), row=1, col=1)

            fig.add_hline(
                y=current_price, line=dict(color="#FFD700", width=1.5, dash="dashdot"),
                annotation_text=f"📌 現價: ${current_price:,.2f}", annotation_position="top right",
                annotation_font=dict(color="#FFD700", size=11), row=1, col=1
            )

            bar_colors = ["#089981" if c >= o else "#F23645" for o, c in zip(df_plot['open'], df_plot['close'])]
            fig.add_trace(go.Bar(x=df_plot['time_clean'], y=df_plot['volume'], name="成交量", marker=dict(color=bar_colors)), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_plot['time_clean'], y=df_plot['vma20'], line=dict(color="#ffffff", width=1), name="VMA20"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_plot['time_clean'], y=df_plot['vma_15x'], line=dict(color="#8b949e", width=1, dash="dot"), name="1.5X"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_plot['time_clean'], y=df_plot['vma_20x'], line=dict(color="#ffd700", width=1, dash="dot"), name="2.0X"), row=2, col=1)

            fig.update_xaxes(type='category', rangeslider_visible=False, gridcolor="#161b22")
            fig.update_yaxes(gridcolor="#161b22")
            fig.update_layout(
                height=620, template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                margin=dict(l=10, r=10, t=10, b=10), hovermode="x unified", dragmode="pan", uirevision=f"{code}_{ktype_name}"
            )
            st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True, "displayModeBar": True, "displaylogo": False})
        except Exception as e:
            st.error(f"❌ 圖表模組異常: {str(e)}")
