# 文件名: chart_plugin.py
# 核心功能: 實盤座艙渲染面板與 OpenD 數據通道

import os
import datetime
import pandas as pd
import streamlit as st
from moomoo import OpenQuoteContext, RET_OK, SubType
from strategy_engine import StrategyEngine

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CURRENT_DIR, 'market_data')
os.makedirs(DATA_DIR, exist_ok=True)

class ChartPlugin:
    def __init__(self):
        pass

    def load_or_fetch_5m(self, code: str) -> pd.DataFrame:
        clean_code = code.replace('.', '_')
        file_path = os.path.join(DATA_DIR, f"{clean_code}_5M.csv")
        
        df = pd.DataFrame()
        try:
            quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
            quote_ctx.subscribe([code], [SubType.K_5M], is_first_push=False)
            ret, data, _ = quote_ctx.request_history_kline(
                code=code, start="2026-08-01", end=datetime.datetime.now().strftime("%Y-%m-%d"),
                ktype=moomoo.KLType.K_5M if 'moomoo' in globals() else None, max_count=100
            )
            quote_ctx.close()
            if ret == RET_OK and not data.empty:
                df = data[['time_key', 'open', 'close', 'high', 'low', 'volume']].copy()
                df.to_csv(file_path, index=False)
        except Exception:
            pass
            
        if df.empty and os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path)
            except Exception:
                pass
                
        if df.empty:
            # 保底演示數據
            now = datetime.datetime.now()
            times = [(now - datetime.timedelta(minutes=i*5)).strftime('%Y-%m-%d %H:%M:%S') for i in range(10)][::-1]
            df = pd.DataFrame({
                'time_key': times,
                'open': [718.5 + i*0.1 for i in range(10)],
                'high': [718.8 + i*0.1 for i in range(10)],
                'low': [718.2 + i*0.1 for i in range(10)],
                'close': [718.6 + i*0.1 for i in range(10)],
                'volume': [150.0 + i*5 for i in range(10)]
            })
            
        return StrategyEngine.calculate_indicators(df)

    def render_cockpit(self, code: str, budget_usd: float = 200.0):
        st.markdown(f"### ⚡ 癸水 · 實盤射控座艙 ({code})")
        df = self.load_or_fetch_5m(code)
        
        if df.empty:
            st.warning("⏳ 正在等待行情數據載入...")
            return

        latest = df.iloc[-1]
        eval_res = StrategyEngine.evaluate_signal(latest)

        # 頂部狀態指標
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📌 當前最新價", f"${float(latest['close']):,.2f}")
        c2.metric("📊 VPA 量能倍數", f"{float(latest.get('vol_ratio', 1.0)):.2f}x")
        c3.metric("🎯 戰術信號", eval_res['action'])
        c4.metric("💰 0DTE 預算", f"${budget_usd:.0f} USD")

        st.markdown("---")
        st.markdown("#### 📋 5M K 線與形態診斷表")
        
        display_df = df.tail(8)[['time_key', 'open', 'high', 'low', 'close', 'volume', 'pattern_label']].copy()
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        with st.expander("📋 [診斷日誌] 點擊展開一鍵複製文本塊", expanded=False):
            log_text = f"=== 癸水 · 系統運行日誌 ===\n• 標的: {code}\n• 最新收盤: ${float(latest['close']):,.2f}\n• 形態判定: {latest.get('pattern_label')}\n• 策略信號: {eval_res['action']} (評分: {eval_res['score']})\n==========================="
            st.code(log_text, language="text")
