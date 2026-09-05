# 文件名: chart_plugin.py
# 核心功能: 多週期 (Day/1Hr/5M) 綜合戰略分析 + 現價位置雷達 + 0DTE 扳機 Table

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

    def render_live_monitor_table(self, code: str, ktype_name: str):
        """頂部快速即時報價表格"""
        snap_info = self.get_realtime_snapshot_price(code)
        is_btc = "BTC" in code.upper()
        save_prefix = "CC_BTCUSD" if is_btc else code.replace('.', '_')
        file_path = os.path.join(self.data_dir, f"{save_prefix}_{ktype_name}.csv")
        
        last_close, last_high, last_low, last_vol = 0.0, 0.0, 0.0, 0.0
        if os.path.exists(file_path):
            try:
                df_temp = pd.read_csv(file_path)
                last_row = df_temp.iloc[-1]
                last_close = float(last_row['close'])
                last_high = float(last_row['high'])
                last_low = float(last_row['low'])
                last_vol = float(last_row['volume'])
            except Exception:
                pass

        current_live_price = snap_info["price"] if snap_info["price"] else last_close
        display_source = snap_info["source"] if snap_info["price"] else "🟢 數據通訊中"
        chg_pts = (current_live_price - last_close) if last_close > 0 else 0.0
        chg_pct = (chg_pts / last_close) * 100 if last_close > 0 else 0.0
        now_et_str = datetime.datetime.now(tz_ny).strftime('%Y-%m-%d %H:%M:%S')

        monitor_data = {
            "監控標的": [code],
            "通道狀態": [display_source],
            "紐約時間 (ET)": [now_et_str],
            "最新跳動現價": [f"${current_live_price:,.2f}"],
            "當根最高價": [f"${max(last_high, current_live_price):,.2f}"],
            "當根最低價": [f"${min(last_low, current_live_price):,.2f}"],
            "當根量能": [f"{last_vol:,.2f}"],
            "瞬時漲跌": [f"{chg_pts:+.2f} ({chg_pct:+.2f}%)"]
        }
        st.dataframe(pd.DataFrame(monitor_data), use_container_width=True, hide_index=True)

    def render_operation_signals_table(self, code: str):
        """【實戰操作主艙】：整合 Day 大局、1Hr 戰區與 5M 扳機"""
        # 1. 抓取三週期數據
        df_day, _ = self.get_live_data_and_upsert(code, "DAY")
        df_1hr, _ = self.get_live_data_and_upsert(code, "1Hr")
        df_5m, _ = self.get_live_data_and_upsert(code, "5M")

        snap_info = self.get_realtime_snapshot_price(code)
        live_price = snap_info["price"] if snap_info["price"] else (float(df_5m['close'].iloc[-1]) if not df_5m.empty else 0.0)

        # ====== 模組 A：日線 (Day) 與 1小時 (1Hr) 大級別趨勢分析 ======
        st.markdown("#### 🗺️ 第一步：多週期大局戰略定位（Day & 1Hr 宏觀背景）")
        
        day_bias = "區間震盪"
        pdh_val, pdl_val = 0.0, 0.0
        if not df_day.empty and len(df_day) >= 2:
            prev_day = df_day.iloc[-2]
            curr_day = df_day.iloc[-1]
            pdh_val = float(prev_day['high'])
            pdl_val = float(prev_day['low'])
            df_day['ema20'] = df_day['close'].ewm(span=20, adjust=False).mean()
            if float(curr_day['close']) > float(df_day['ema20'].iloc[-1]):
                day_bias = "🟢 多頭掌控 (日線在 EMA20 上方，回踩做多勝率高)"
            else:
                day_bias = "🔴 空頭承壓 (日線在 EMA20 下方，逢高做空勝率高)"

        hr_res, hr_sup = 0.0, 0.0
        hr_status = "1Hr 通道計算中"
        if not df_1hr.empty:
            td_1h = compute_demark_trendlines(df_1hr, window=4)
            hr_res = td_1h.get('curr_res_val') or (live_price * 1.01)
            hr_sup = td_1h.get('curr_sup_val') or (live_price * 0.99)
            if live_price >= hr_res - 0.5:
                hr_status = "⚠️ 逼近 1Hr 阻力天花板"
            elif live_price <= hr_sup + 0.5:
                hr_status = "🛡️ 逼近 1Hr 支撐地板"
            else:
                hr_status = "⚪ 處於 1Hr 中間震盪區（不可盲目追單）"

        macro_data = {
            "週期": ["日線圖 (Day - 全局主方向)", "1小時圖 (1Hr - 日內戰區範圍)"],
            "戰略判斷": [day_bias, hr_status],
            "上方關鍵天花板 (阻力)": [f"昨日高點 PDH: ${pdh_val:,.2f}" if pdh_val > 0 else "--", f"1Hr TD 阻力: ${hr_res:,.2f}"],
            "下方關鍵地板 (支撐)": [f"昨日低點 PDL: ${pdl_val:,.2f}" if pdl_val > 0 else "--", f"1Hr TD 支撐: ${hr_sup:,.2f}"]
        }
        st.dataframe(pd.DataFrame(macro_data), use_container_width=True, hide_index=True)

        st.divider()

        # ====== 模組 B：現價相對位置與 5M 微觀操作指令 ======
        st.markdown(f"#### 🎯 第二步：現價位置與 5M 實際操作指令（現價: :green[**${live_price:,.2f}**]）")

        vol_ratio = 1.0
        td_count_str = "TD 計數中"
        if not df_5m.empty:
            df_5m['vma20'] = df_5m['volume'].rolling(window=20).mean()
            last_5m = df_5m.iloc[-1]
            vma = last_5m['vma20'] if pd.notna(last_5m.get('vma20')) and last_5m['vma20'] > 0 else 1.0
            vol_ratio = float(last_5m['volume']) / vma
            td_5m = compute_demark_trendlines(df_5m, window=4)
            td_res_5m = td_5m.get('curr_res_val') or hr_res
            td_sup_5m = td_5m.get('curr_sup_val') or hr_sup
        else:
            td_res_5m = hr_res
            td_sup_5m = hr_sup

        dist_res = td_res_5m - live_price
        dist_sup = live_price - td_sup_5m

        # 判定操作指令與具體動作建議
        if dist_res <= 0.35 and vol_ratio >= 1.5:
            tactical_state = "🔴 【衝頂阻力 + 放量受阻】"
            action_guidance = "🔥 動作：準備在券商買入 0DTE ATM Put（做空），止損設在剛才最高點上方 $0.30"
        elif dist_sup <= 0.35 and vol_ratio >= 1.5:
            tactical_state = "🟢 【踩線地板 + 放量拉回】"
            action_guidance = "🔥 動作：準備在券商買入 0DTE ATM Call（做多），止損設在剛才最低點下方 $0.30"
        elif dist_res <= 0.35 or dist_sup <= 0.35:
            tactical_state = "🟡 【已進入戰區邊界】"
            action_guidance = "👀 動作：價格已到邊界！盯緊 5M 是否放量或刺穿收回，量能一出立刻跟進"
        else:
            tactical_state = "⚪ 【處於半山腰無效區】"
            action_guidance = f"☕ 動作：現價距離天花板還有 ${dist_res:.2f}，距離地板還有 ${dist_sup:.2f}。耐心等待價格到位，嚴禁在半山腰開倉！"

        op_data = {
            "最新跳動現價": [f"${live_price:,.2f}"],
            "距離上方阻力": [f"${dist_res:+.2f} (${td_res_5m:,.2f})"],
            "距離下方支撐": [f"${dist_sup:+.2f} (${td_sup_5m:,.2f})"],
            "5M 量能狀態": [f"{vol_ratio:.2f}x ({'⚡ 放量異動' if vol_ratio >= 1.5 else '常規量'})"],
            "當前戰況": [tactical_state],
            "你現在該執行的具體動作": [action_guidance]
        }
        st.dataframe(pd.DataFrame(op_data), use_container_width=True, hide_index=True)

    def render_static_chart(self, code: str, ktype_name: str):
        """Tab 1：Plotly 專業圖表視圖"""
        try:
            df, _ = self.get_live_data_and_upsert(code, ktype_name)
            if df.empty:
                st.error(f"❌ 暫時無法獲取 {code} 數據")
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
            st.error(f"❌ 圖表模組渲染異常: {str(e)}")
