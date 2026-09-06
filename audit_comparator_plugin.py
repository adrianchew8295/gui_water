# 文件名: audit_comparator_plugin.py
# 核心功能: 【數據真偽交叉審核插件】OpenD vs Tiingo IEX vs yfinance 5M 逐根比對

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
        """從 Tiingo IEX API 獲取真實 5M 數據"""
        ticker = "BTCUSD" if "BTC" in symbol.upper() else "QQQ"
        # 加密貨幣走 Tiingo Crypto，美股走 IEX
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
            st.caption(f"Tiingo 連線提示: {e}")
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
        st.caption("同時比對 OpenD（富途實盤）、Tiingo（IEX 機構源）與 yfinance（公共源），逐根排查價差與時間漂移。")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.info("📡 源 1: Moomoo OpenD (本地網關)")
        with col2:
            st.info("🌐 源 2: Tiingo API (IEX 專屬通道)")
        with col3:
            st.info("🟡 源 3: Yahoo Finance (備援通道)")

        with st.spinner("正在對齊三方數據源..."):
            df_open = self.fetch_opend_5m(code)
            df_tiin = self.fetch_tiingo_5m(code)
            df_yf = self.fetch_yfinance_5m(code)

        # 構建對比表
        rows = []
        audit_log = []
        now_et = datetime.datetime.now(tz_ny).strftime('%H:%M:%S')

        # 以 OpenD 的最近 5 根為基準時間軸
        base_df = df_open.tail(5) if not df_open.empty else (df_tiin.tail(5) if not df_tiin.empty else df_yf.tail(5))

        if base_df.empty:
            st.error("❌ 三大數據源暫時無法連接，請檢查網絡。")
            return

        for _, base_row in base_df.iterrows():
            t = base_row['time_key']
            t_str = t.strftime('%H:%M')

            # 抓取各源在該時段的 Close
            p_open = df_open[df_open['time_key'] == t]['close'].values[0] if (not df_open.empty and len(df_open[df_open['time_key'] == t]) > 0) else None
            p_tiin = df_tiin[df_tiin['time_key'] == t]['close'].values[0] if (not df_tiin.empty and len(df_tiin[df_tiin['time_key'] == t]) > 0) else None
            p_yf = df_yf[df_yf['time_key'] == t]['close'].values[0] if (not df_yf.empty and len(df_yf[df_yf['time_key'] == t]) > 0) else None

            diff_str = "--"
            if p_open and p_tiin:
                diff = abs(p_open - p_tiin)
                diff_str = f"±${diff:.2f}" if diff < 1.0 else f"⚠️ 差 ${diff:.2f}"

            rows.append({
                "時段 (ET)": t_str,
                "OpenD 現價": f"${p_open:,.2f}" if p_open else "無數據",
                "Tiingo IEX": f"${p_tiin:,.2f}" if p_tiin else "無數據",
                "yfinance": f"${p_yf:,.2f}" if p_yf else "無數據",
                "OpenD vs Tiingo 價差": diff_str
            })

            audit_log.append(f"• {t_str} ET | OpenD: {p_open} | Tiingo: {p_tiin} | yf: {p_yf} | 偏差: {diff_str}")

        df_table = pd.DataFrame(rows)
        st.dataframe(df_table, use_container_width=True, hide_index=True)

        # 輸出審核日誌代碼塊
        now_my = datetime.datetime.now(tz_my).strftime('%Y-%m-%d %H:%M:%S MYT')
        log_text = f"=== 數據跨源交叉審核日誌 (CROSS-SOURCE AUDIT) ===\n"
        log_text += f"• 審核時間: {now_my} (美東: {now_et} ET)\n"
        log_text += f"• 標的代碼: {code} | Tiingo 通道: 啟用\n"
        log_text += f"\n[5M 時序逐根對齊]\n"
        for l in audit_log:
            log_text += f"{l}\n"
        log_text += f"==============================================\n"

        st.caption("📋 交叉審核日誌 (一鍵複製)：")
        st.code(log_text, language="text")
