# 文件名: chart_plugin.py
# 核心功能: 現價水平動態射線 (Current Price Line) + EMA 趨勢曲線 + TD 德馬克通道 + Plotly 圖表

import os
import datetime
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
        """獲取毫秒級即時盤口快照"""
        res = {"price": None, "source": "未連線", "time_str": ""}
        quote_ctx = None
        try:
            quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
            target_symbol = "CC.BTCUSD" if "BTC" in code.upper() else code
            ret, df_snap = quote_ctx.get_market_snapshot([target_symbol])
            if ret == RET_OK and not df_snap.empty:
                row = df_snap.iloc[0]
                res["price"] = float(row['last_price'])
                res["source"] = "🟢 OpenD 毫秒快照"
                res["time_str"] = str(row.get('update_time', datetime.datetime.now(tz_ny).strftime('%Y-%m-%d %H:%M:%S')))
                return res
        except Exception:
            pass
        finally:
            if quote_ctx:
                try: quote_ctx.close()
                except: pass

        # 備援 yfinance
        try:
            yf_sym = "BTC-USD" if "BTC" in code.upper() else "QQQ"
            ticker = yf.Ticker(yf_sym)
            fast_p = ticker.fast_info.last_price
            if fast_p:
                res["price"] = float(fast_p)
                res["source"] = "🟡 yfinance 實時快照"
                res["time_str"] = datetime.datetime.now(tz_ny).strftime('%Y-%m-%d %H:%M:%S')
                return res
        except Exception:
            pass

        return res

    def get_live_data_and_upsert(self, code: str, ktype_name: str) -> tuple:
        """獲取 K 線並執行安全 Upsert 合併"""
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

    def render_live_monitor_table(self, df: pd.DataFrame, code: str, data_source: str, snap_info: dict):
        """頂部渲染即時跳動監控表格"""
        if df.empty:
            st.info("⏳ 正在建立行情通訊流...")
            return

        last_row = df.iloc[-1]
        prev_row = df.iloc[-2] if len(df) >= 2 else last_row
        
        current_live_price = snap_info["price"] if snap_info["price"] else float(last_row['close'])
        display_source = snap_info["source"] if snap_info["price"] else data_source
        
        chg_pts = current_live_price - prev_row['close']
        chg_pct = (chg_pts / prev_row['close']) * 100 if prev_row['close'] != 0 else 0.0
        now_et_str = datetime.datetime.now(tz_ny).strftime('%Y-%m-%d %H:%M:%S')

        monitor_data = {
            "監控標的": [code],
            "數據通道": [display_source],
            "美東即時時間 (ET)": [now_et_str],
            "最新跳動現價 (Live)": [f"${current_live_price:,.2f}"],
            "5M 當根最高 (High)": [f"${max(last_row['high'], current_live_price):,.2f}"],
            "5M 當根最低 (Low)": [f"${min(last_row['low'], current_live_price):,.2f}"],
            "5M 成交量 (Vol)": [f"{float(last_row['volume']):,.2f}"],
            "即時漲跌幅": [f"{chg_pts:+.2f} ({chg_pct:+.2f}%)"]
        }
        st.markdown("##### ⚡ 實時行情跳動監控艙 (Live Stream Engine)")
        st.dataframe(pd.DataFrame(monitor_data), use_container_width=True, hide_index=True)

    def render_chart(self, code: str, ktype_name: str):
        try:
            df, data_source = self.get_live_data_and_upsert(code, ktype_name)
            if df.empty:
                st.error(f"❌ 暫時無法獲取 {code} 數據，請檢查網絡連接。")
                return

            snap_info = self.get_realtime_snapshot_price(code)
            self.render_live_monitor_table(df, code, data_source, snap_info)

            # 動態現價注入
            current_price = snap_info["price"] if snap_info["price"] else float(df['close'].iloc[-1])
            df.loc[df.index[-1], 'close'] = current_price

            # 指標計算：EMA9 動態短期趨勢線 + EMA20 生命線 + VPA
            df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
            df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
            df['time_clean'] = df['time_key'].dt.strftime('%m-%d %H:%M') if ktype_name in ['5M', '1Hr'] else df['time_key'].dt.strftime('%Y-%m-%d')
            df['vma20'] = df['volume'].rolling(window=20).mean()
            df['vma_15x'] = df['vma20'] * 1.5
            df['vma_20x'] = df['vma20'] * 2.0

            td_res = compute_demark_trendlines(df, window=4)

            df_plot = df.tail(200).copy().reset_index(drop=True)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])

            # 1. 主圖：K 線
            fig.add_trace(go.Candlestick(
                x=df_plot['time_clean'], open=df_plot['open'], high=df_plot['high'], low=df_plot['low'], close=df_plot['close'],
                name="K線", increasing_line_color="#089981", decreasing_line_color="#F23645"
            ), row=1, col=1)

            # 2. 趨勢曲線：EMA9 (短線趨勢) 與 EMA20 (動量生命線)
            fig.add_trace(go.Scatter(
                x=df_plot['time_clean'], y=df_plot['ema9'],
                mode='lines', line=dict(color='#00E5FF', width=1.5), name="EMA9 (短線趨勢)"
            ), row=1, col=1)

            fig.add_trace(go.Scatter(
                x=df_plot['time_clean'], y=df_plot['ema20'],
                mode='lines', line=dict(color='#FFA726', width=1.5), name="EMA20 (生命線)"
            ), row=1, col=1)

            # 3. TD 阻力線與支撐線
            if td_res.get("resistance_line"):
                res_df = pd.DataFrame(td_res["resistance_line"])
                fig.add_trace(go.Scatter(
                    x=df_plot['time_clean'].iloc[-len(res_df):], y=res_df['value'],
                    mode='lines', line=dict(color='#FF5252', width=2, dash='dash'), name="TD 阻力線"
                ), row=1, col=1)

            if td_res.get("support_line"):
                sup_df = pd.DataFrame(td_res["support_line"])
                fig.add_trace(go.Scatter(
                    x=df_plot['time_clean'].iloc[-len(sup_df):], y=sup_df['value'],
                    mode='lines', line=dict(color='#00E676', width=2, dash='dash'), name="TD 支撐線"
                ), row=1, col=1)

            # 4. 🌟 當前現價動態水平線 (Current Price Line)
            fig.add_hline(
                y=current_price,
                line=dict(color="#FFD700", width=1.5, dash="dashdot"),
                annotation_text=f"📌 現價: ${current_price:,.2f}",
                annotation_position="top right",
                annotation_font=dict(color="#FFD700", size=11),
                row=1, col=1
            )

            # 5. 副圖：成交量與 VPA 警戒線
            bar_colors = ["#089981" if c >= o else "#F23645" for o, c in zip(df_plot['open'], df_plot['close'])]
            fig.add_trace(go.Bar(x=df_plot['time_clean'], y=df_plot['volume'], name="成交量", marker=dict(color=bar_colors)), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_plot['time_clean'], y=df_plot['vma20'], line=dict(color="#ffffff", width=1), name="VMA20"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_plot['time_clean'], y=df_plot['vma_15x'], line=dict(color="#8b949e", width=1, dash="dot"), name="1.5X"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_plot['time_clean'], y=df_plot['vma_20x'], line=dict(color="#ffd700", width=1, dash="dot"), name="2.0X"), row=2, col=1)

            fig.update_xaxes(type='category', rangeslider_visible=False, gridcolor="#161b22")
            fig.update_yaxes(gridcolor="#161b22")
            fig.update_layout(
                height=620, template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                margin=dict(l=10, r=10, t=10, b=10), hovermode="x unified", dragmode="pan"
            )

            st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True, "displayModeBar": True, "displaylogo": False})

        except Exception as e:
            st.error(f"❌ 模組渲染異常: {str(e)}")
