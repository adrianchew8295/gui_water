# 文件名: nq_wave_tab.py
# 核心功能: 1年期數據波浪理論專屬推演看板 (免 K 線純數據座艙)

import streamlit as st
import pandas as pd
import os
from elliott_wave_engine import ElliottWaveEngine

def load_nq_1year_data(data_dir: str = './market_data') -> pd.DataFrame:
    file_path = os.path.join(data_dir, "US_NQmain_1Hr.csv")
    if not os.path.exists(file_path):
        file_path = os.path.join(data_dir, "US_QQQ_1Hr.csv")
    
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            df.columns = [c.lower().strip() for c in df.columns]
            return df
        except Exception:
            pass
    return pd.DataFrame()

def render_nq_wave_prediction_dashboard():
    st.markdown("## 🌊 NQ Main / QQQ 艾略特全波浪理論預測中樞 (1H 級別推演)")
    st.caption("標的: **US.NQmain (納指主力鏡像)** | 數據跨度: **1 年期 1H 歷史序列** | 核心算法: **Elliott Wave + 斐波那契時空對稱**")

    df_nq = load_nq_1year_data()
    if df_nq.empty or len(df_nq) < 50:
        st.warning("⏳ 尚未檢測到 1Hr 歷史數據。請先在終端機運行 `python fetch_nq_1year.py` 下載數據！")
        return

    wave_res = ElliottWaveEngine.analyze_wave_structure(df_nq)
    curr_price = float(df_nq['close'].iloc[-1])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📌 當前基準價", f"${curr_price:,.2f}")
    m2.metric("🌊 當前波浪定位", wave_res["current_wave"])
    m3.metric("🧭 宏觀浪級方向", wave_res["trend_dir"])
    m4.metric("⏱️ 本浪運行時間", f"{wave_res['time_elapsed_hrs']} 小時", f"預期週期 ~{wave_res['expected_duration_hrs']}H")

    st.markdown("---")

    st.markdown("### 🧭 接下來 1 小時走勢與波浪路徑預測 (Prediction Window)")
    pred_col1, pred_col2 = st.columns([1.6, 1.0])
    
    with pred_col1:
        st.info(f"### 🤖 艾略特波浪推演結論\n\n{wave_res['prediction_narrative']}")
        st.markdown(f"""
        * **當前子浪階梯**: `{wave_res['sub_wave']}` ({wave_res['wave_phase']})
        * **時間對稱性**: 已運行 **{wave_res['time_elapsed_hrs']} 根 1H Bar**，距時間窗口拐點尚有 **{max(0, wave_res['expected_duration_hrs'] - wave_res['time_elapsed_hrs'])} 小時**。
        """)

    with pred_col2:
        st.markdown(f"""
        | 波浪推演指標 | 預測目標點位 ($) | 理論依據 |
        | :--- | :--- | :--- |
        | **第 1 目標位 (Target 1)** | **${wave_res['next_target_1']:,.2f}** | 斐波那契 1.0x 對稱浪 |
        | **第 2 目標位 (Target 2)** | **${wave_res['next_target_2']:,.2f}** | 1.618x 主升擴展浪 |
        | **結構失效防守位 (SL)** | **${wave_res['invalid_price']:,.2f}** | 艾略特波浪鐵律重疊線 |
        """)

    st.markdown("---")

    st.markdown("### 📋 波浪關鍵拐點計數表 (Wave Pivots & Logs)")
    if wave_res["wave_table"]:
        st.dataframe(pd.DataFrame(wave_res["wave_table"]), use_container_width=True, hide_index=True)
