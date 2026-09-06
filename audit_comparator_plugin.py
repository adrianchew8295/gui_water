# 文件名: audit_comparator_plugin.py
# 核心功能: 【數據真偽交叉審核插件】標註三源 K 線顏色形態 + 逐根比對價差與時間漂移

import datetime
import json
import os
import urllib.request
import pandas as pd
import pytz
import streamlit as st
import yfinance as yf
from moomoo import OpenQuoteContext, RET_OK, KLType, SubType, AuType

tz_ny = pytz.timezone("America/New_York")
tz_my = pytz.timezone("Asia/Kuala_Lumpur")

TIINGO_TOKEN = "bcffe3a5cf7eeef085e405cfa4a3e5691b976217"

class AuditComparatorPlugin:
    def __init__(self, tiingo_token: str = TIINGO_TOKEN):
        self.tiingo_token = tiingo_token

    @staticmethod
    def classify_candle(open_p: float, high_p: float, low_p: float, close_p: float) -> str:
        """K 線顏色與幾何形態解剖"""
        total_range = high_p - low_p
        is_up = close_p >= open_p

        if total_range <= 0.0001:
            return "🟢 青陽漲" if is_up else "🔴 紅陰跌"

        body = abs(close_p - open_p)
        upper_wick = high_p - max(open_p, close_p)
        lower_wick = min(open_p, close_p) - low_p

        if body <= total_range * 0.15:
            return "🟢 十字漲 ⚖️" if is_up else "🔴 十字跌 ⚖️"

        if body >= 0.75 * total_range:
            return "🟢 大陽衝鋒 🚀" if is_up else "🔴 大陰破位 💥"

        if lower_wick >= 1.3 * upper_wick and lower_wick >= 0.30 * total_range:
            return "🟢 鐵錘漲 🔨" if is_up else "🔴 吊頸跌 🪓"

        if upper_wick >= 1.3 * lower_wick and upper_wick >= 0.30 * total_range:
            return "🟢 倒錘漲 🛸" if is_up else "🔴 射星跌 🌠"

        return "🟢 青陽漲" if is_up else "🔴 紅陰跌"

    def fetch_opend_5m(self, code: str) -> pd.DataFrame:
        """獲取 OpenD 5M 數據"""
        target = "CC.BTCUSD" if "BTC" in code.upper() else code
        try:
            ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
            ctx.subscribe([target], [SubType.K_5M, SubType.QUOTE])
            ret, df_k = ctx.get_cur_kline(target, 20, KLType.K_5M, AuType.NONE)
            ctx.close()
            if ret == RET_OK and not df_k.empty:
                df = df_k[['time_key', 'open', 'close', 'high', 'low', 'volume']].copy()
                df['time_key'] = pd.to_datetime(df['time_key'])
                return df.sort_values('time_key').reset_index(drop=True)
        except Exception:
            pass
        return pd.DataFrame()

    def fetch_tiingo_5m(self, symbol: str) -> pd.DataFrame:
        """從 Tiingo IEX / Crypto API 獲取真實 5M 數據"""
        ticker = "BTCUSD" if "BTC" in symbol.upper() else "QQQ"
        if "BTC" in symbol.upper():
            url = f"https://api.tiingo.com/tiingo/crypto/prices?tickers=btcusd&interval=5min&token={self.tiingo_token}"
        else:
            url = f"https://api.tiingo.com/iex/{ticker}/prices?columns=open,high,low,close,volume&resampleFreq=5min&token={self.tiingo_token}"
        
        try:
            req = urllib.request.Request(url, headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if "BTC" in symbol.upper() and data and "priceData" in data[0]:
                    raw_rows = data[0]["priceData"]
                else:
                    raw_rows = data

                if raw_rows:
                    df = pd.DataFrame(raw_rows)
                    time_col = 'date' if 'date' in df.columns else 'time'
                    df['time_key'] = pd.to_datetime(df[time_col]).dt.tz_convert(tz_ny).dt.tz_localize(None)
                    df = df[['time_key', 'open', 'close', 'high', 'low', 'volume']].dropna()
                    return df.sort_values('time_key').reset_index(drop=True)
        except Exception as e:
            st.caption(f"Tiingo 通道提示: {e}")
        return pd.DataFrame()

    def fetch_yfinance_5m(self, symbol: str) -> pd.DataFrame:
        """從 yfinance 獲取 5M 數據"""
        ticker = "BTC-USD" if "BTC" in symbol.upper() else "QQQ"
        try:
            df = yf.download(tickers=ticker, period="1d", interval="5m", prepost=True, progress=False, auto_adjust=False)
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = [c[0].lower() for c in df.columns]
                else:
                    df.columns = [c.lower() for c in df.columns]
                df = df.reset_index()
                dt_col = 'Datetime' if 'Datetime' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
                df['time_key'] = pd.to_datetime(df[dt_col])
                if df['time_key'].dt.tz is None:
                    df['time_key'] = df['time_key'].dt.tz_localize('UTC').dt.tz_convert(tz_ny)
                else:
                    df['time_key'] = df['time_key'].dt.tz_convert(tz_ny)
                df['time_key'] = df['time_key'].dt.tz_localize(None)
                return df[['time_key', 'open', 'close', 'high', 'low', 'volume']].dropna().sort_values('time_key').reset_index(drop=True)
        except Exception:
            pass
        return pd.DataFrame()

    def render_audit_dashboard(self, code: str):
        st.markdown("### 🔍 多源數據真偽交叉審核艙 (Data Audit Engine)")
        st.caption("同時比對 OpenD（富途實盤）、Tiingo（IEX 機構源）與 yfinance（公共源），逐根標註 K 線顏色形態並計算偏差。")

        c1, c2, c3 = st.columns(3)
        c1.info("📡 源 1: Moomoo OpenD (本地網關)")
        c2.info("🌐 源 2: Tiingo API (IEX 專屬通道)")
        c3.info("🟡 源 3: Yahoo Finance (備援通道)")

        with st.spinner("正在對齊三方數據源與形態計算..."):
            df_open = self.fetch_opend_5m(code)
            df_tiin = self.fetch_tiingo_5m(code)
            df_yf = self.fetch_yfinance_5m(code)

        base_df = df_open.tail(6) if not df_open.empty else (df_tiin.tail(6) if not df_tiin.empty else df_yf.tail(6))

        if base_df.empty:
            st.error("❌ 三大數據源暫時無法連接，請檢查網絡或 OpenD 網關狀態。")
            return

        rows = []
        audit_log = []
        now_et = datetime.datetime.now(tz_ny).strftime('%H:%M:%S')

        for _, base_row in base_df.iloc[::-1].iterrows():
            t = base_row['time_key']
            t_str = t.strftime('%H:%M')

            # 1. OpenD 提取
            row_o = df_open[df_open['time_key'] == t] if not df_open.empty else pd.DataFrame()
            if not row_o.empty:
                o_c, o_o, o_h, o_l = float(row_o['close'].values[0]), float(row_o['open'].values[0]), float(row_o['high'].values[0]), float(row_o['low'].values[0])
                shape_open = self.classify_candle(o_o, o_h, o_l, o_c)
                str_open = f"${o_c:,.2f} [{shape_open}]"
            else:
                o_c, str_open, shape_open = None, "無數據", "--"

            # 2. Tiingo 提取
            row_t = df_tiin[df_tiin['time_key'] == t] if not df_tiin.empty else pd.DataFrame()
            if not row_t.empty:
                t_c, t_o, t_h, t_l = float(row_t['close'].values[0]), float(row_t['open'].values[0]), float(row_t['high'].values[0]), float(row_t['low'].values[0])
                shape_tiin = self.classify_candle(t_o, t_h, t_l, t_c)
                str_tiin = f"${t_c:,.2f} [{shape_tiin}]"
            else:
                t_c, str_tiin, shape_tiin = None, "無數據", "--"

            # 3. yfinance 提取
            row_y = df_yf[df_yf['time_key'] == t] if not df_yf.empty else pd.DataFrame()
            if not row_y.empty:
                y_c, y_o, y_h, y_l = float(row_y['close'].values[0]), float(row_y['open'].values[0]), float(row_y['high'].values[0]), float(row_y['low'].values[0])
                shape_yf = self.classify_candle(y_o, y_h, y_l, y_c)
                str_yf = f"${y_c:,.2f} [{shape_yf}]"
            else:
                y_c, str_yf, shape_yf = None, "無數據", "--"

            # 偏差分析
            diff_str = "--"
            if o_c and t_c:
                diff = abs(o_c - t_c)
                diff_str = f"±${diff:.2f}" if diff < 1.0 else f"⚠️ 差 ${diff:.2f}"

            rows.append({
                "時段 (ET)": t_str,
                "OpenD (富途實盤)": str_open,
                "Tiingo IEX": str_tiin,
                "yfinance": str_yf,
                "OpenD vs Tiingo 偏差": diff_str
            })

            audit_log.append(f"• {t_str} ET | OpenD: {str_open} | Tiingo: {str_tiin} | yf: {str_yf} | 偏差: {diff_str}")

        # 渲染審核表格
        df_table = pd.DataFrame(rows)
        st.dataframe(df_table, use_container_width=True, hide_index=True)

        # 輸出帶形態柱體的 Logs 文本框
        now_my = datetime.datetime.now(tz_my).strftime('%Y-%m-%d %H:%M:%S MYT')
        log_text = f"=== 數據跨源交叉審核日誌 (CROSS-SOURCE AUDIT) ===\n"
        log_text += f"• 審核時間: {now_my} (美東: {now_et} ET)\n"
        log_text += f"• 標的代碼: {code} | 形態檢驗: 啟用\n"
        log_text += f"\n[5M 時序逐根對齊 (含 K 線柱體顏色標籤)]\n"
        for l in audit_log:
            log_text += f"{l}\n"
        log_text += f"==============================================\n"

        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        st.caption("📋 交叉審核日誌 (含柱體標籤 - 右上角一鍵複製)：")
        st.code(log_text, language="text")
