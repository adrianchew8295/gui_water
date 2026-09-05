# 文件名: chart_plugin.py
# 核心功能: 鎖定真實比特幣 (CC.BTCUSD / BTC-USD 79,600+ 價格) + 實時跳動監控艙 + Plotly 圖表

import os
import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pytz
import streamlit as st
import yfinance as yf
from moomoo import OpenQuoteContext, RET_OK, KLType, AuType
from trendline_engine import compute_demark_trendlines

tz_ny = pytz.timezone("America/New_York")
DATA_DIR = './market_data'
os.makedirs(DATA_DIR, exist_ok=True)

class ChartPlugin:
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir

    def get_live_data_and_upsert(self, code: str, ktype_name: str) -> pd.DataFrame:
        """獲取真實 BTC/QQQ 行情流，包含 yfinance 備援機制"""
        is_btc = "BTC" in code.upper()
        save_prefix = "CC_BTCUSD" if is_btc else code.replace('.', '_')
        file_path = os.path.join(self.data_dir, f"{save_prefix}_{ktype_name}.csv")

        # 1. 讀取本地歷史底座 (若有)
        df_base = pd.DataFrame()
        if os.path.exists(file_path):
            try:
                df_base = pd.read_csv(file_path)
                df_base.columns = [c.lower() for c in df_base.columns]
                df_base['time_key'] = pd.to_datetime(df_base['time_key'])
                # 如果舊快取數據價格異常（小於 1000 的假 BTC），直接拋棄
                if is_btc and not df_base.empty and df_base['close'].iloc[-1] < 1000:
                    df_base = pd.DataFrame()
            except Exception:
                pass

        # 2. 優先嘗試 OpenD
        df_live = pd.DataFrame()
        try:
            ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
            kl_type = KLType.K_5M if ktype_name == "5M" else (KLType.K_60M if ktype_name == "1Hr" else KLType.K_DAY)
            target_symbol = "CC.BTCUSD" if is_btc else code
            ret, df_k = ctx.get_cur_kline(target_symbol, 200, kl_type, AuType.NONE)
            ctx.close()
            if ret == RET_OK and not df_k.empty:
                df_live = df_k[['time_key', 'open', 'close', 'high', 'low', 'volume']].copy()
                df_live['time_key'] = pd.to_datetime(df_live['time_key'])
        except Exception:
            pass

        # 3. 若 OpenD 未取到加密流，切換 yfinance 抓取真比特幣 (BTC-USD)
        if df_live.empty and df_base.empty:
            try:
                yf_sym = "BTC-USD" if is_btc else "QQQ"
                interval_map = {"5M": "5m", "1Hr": "60m", "DAY": "1d", "WEEK": "1wk"}
                period_map = {"5M": "5d", "1Hr": "1mo", "DAY": "1y", "WEEK": "2y"}
                
                df_yf = yf.download(
                    tickers=yf_sym,
                    period=period_map.get(ktype_name, "5d"),
                    interval=interval_map.get(ktype_name, "5m"),
                    progress=False,
                    auto_adjust=False
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
            except Exception:
                pass

        # 4. 安全 Upsert 去重合併
        if not df_live.empty:
            if not df_base.empty:
                df_merged = pd.concat([df_base, df_live]).drop_duplicates(subset=['time_key'], keep='last')
            else:
                df_merged = df_live
            df_merged = df_merged.sort_values('time_key').reset_index(drop=True)
            df_merged.to_csv(file_path, index=False)
            return df_merged

        return df_base

    def render_live_monitor_table(self, df: pd.DataFrame, code: str):
        """頂部渲染實時跳動監控表格"""
        if df.empty:
            st.info("⏳ 正在建立實時行情跳動流...")
            return

        last_row = df.iloc[-1]
        prev_row = df.iloc[-2] if len(df) >= 2 else last_row
        
        chg_pts = last_row['close'] - prev_row['close']
        chg_pct = (chg_pts / prev_row['close']) * 100 if prev_row['close'] != 0 else 0.0

        monitor_data = {
            "監控標的": [code],
            "美東時間 (ET)": [str(last_row['time_key'])],
            "最新現價 (Last)": [f"${last_row['close']:,.2f}"],
            "當根最高 (High)": [f"${last_row['high']:,.2f}"],
            "當根最低 (Low)": [f"${last_row['low']:,.2f}"],
            "當根成交量 (Vol)": [f"{float(last_row['volume']):,.3f}"],
            "瞬時漲跌": [f"{chg_pts:+.2f} ({chg_pct:+.2f}%)"]
        }
        df_monitor = pd.DataFrame(monitor_data)
        st.markdown("##### ⚡ 實時行情跳動監控艙 (Live Data Stream)")
        st.dataframe(df_monitor, use_container_width=True, hide_index=True)

    def render_chart(self, code: str, ktype_name: str):
        try:
            df = self.get_live_data_and_upsert(code, ktype_name)
            if df.empty:
                st.warning(f"⚠️ 無法載入 {code} 數據，請確認網絡或 OpenD 狀態。")
                return

            self.render_live_monitor_table(df, code)

            df['time_clean'] = df['time_key'].dt.strftime('%m-%d %H:%M') if ktype_name in ['5M', '1Hr'] else df['time_key'].dt.strftime('%Y-%m-%d')
            df['vma20'] = df['volume'].rolling(window=20).mean()
            df['vma_15x'] = df['vma20'] * 1.5
            df['vma_20x'] = df['vma20'] * 2.0

            td_res = compute_demark_trendlines(df, window=4)

            df_plot = df.tail(250).copy().reset_index(drop=True)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])

            # 主圖 K 線
            fig.add_trace(go.Candlestick(
                x=df_plot['time_clean'], open=df_plot['open'], high=df_plot['high'], low=df_plot['low'], close=df_plot['close'],
                name="K線", increasing_line_color="#089981", decreasing_line_color="#F23645"
            ), row=1, col=1)

            # TD 趨勢線
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

            # 副圖成交量
            bar_colors = ["#089981" if c >= o else "#F23645" for o, c in zip(df_plot['open'], df_plot['close'])]
            fig.add_trace(go.Bar(x=df_plot['time_clean'], y=df_plot['volume'], name="成交量", marker=dict(color=bar_colors)), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_plot['time_clean'], y=df_plot['vma20'], line=dict(color="#ffffff", width=1), name="VMA20"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_plot['time_clean'], y=df_plot['vma_15x'], line=dict(color="#8b949e", width=1, dash="dot"), name="1.5X"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df_plot['time_clean'], y=df_plot['vma_20x'], line=dict(color="#ffd700", width=1, dash="dot"), name="2.0X"), row=2, col=1)

            fig.update_xaxes(type='category', rangeslider_visible=False, gridcolor="#161b22")
            fig.update_yaxes(gridcolor="#161b22")
            fig.update_layout(
                height=600, template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                margin=dict(l=10, r=10, t=10, b=10), hovermode="x unified", dragmode="pan"
            )

            st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True, "displayModeBar": True, "displaylogo": False})

        except Exception as e:
            st.error(f"❌ 模組異常: {str(e)}")
