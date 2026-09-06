# 文件名: nq_wave_tab.py
# 核心功能: TradingView 日線波浪 (無 Volume / 支援 Fib 回調切換 / 複雜浪與擴展浪 / AI 分析 Prompt)

import os
import json
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from elliott_wave_engine import ElliottWaveEngine

DATA_DIR = './market_data'

def load_data(symbol: str, timeframe: str) -> pd.DataFrame:
    clean_sym = symbol.replace('.', '_')
    file_path = os.path.join(DATA_DIR, f"{clean_sym}_{timeframe}.csv")
    if not os.path.exists(file_path):
        if "NQ" in symbol:
            file_path = os.path.join(DATA_DIR, f"US_QQQ_{timeframe}.csv")
        elif "QQQ" in symbol:
            file_path = os.path.join(DATA_DIR, f"US_NQmain_{timeframe}.csv")

    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            df.columns = [c.lower().strip() for c in df.columns]
            return df
        except Exception:
            pass
    return pd.DataFrame()

def render_tradingview_wave_chart(df_day: pd.DataFrame, wave_res: dict, show_fib: bool = True):
    if df_day.empty:
        return

    time_col = 'time_key' if 'time_key' in df_day.columns else df_day.columns[0]
    df_day['date_str'] = df_day[time_col].astype(str).str.slice(0, 10)
    df_day = df_day.drop_duplicates(subset=['date_str']).sort_values('date_str').reset_index(drop=True)
    df_plot = df_day.tail(150).copy().reset_index(drop=True)

    candles = []
    for _, r in df_plot.iterrows():
        candles.append({
            'time': str(r['date_str']),
            'open': float(r['open']),
            'high': float(r['high']),
            'low': float(r['low']),
            'close': float(r['close'])
        })

    day_pivots = ElliottWaveEngine.extract_pivots(df_plot, window=4)
    wave_line_data = []
    markers = []
    wave_labels = ["①", "②", "③", "④", "⑤", "ⓐ", "ⓑ", "ⓒ"]

    for idx, p in enumerate(day_pivots):
        t = str(p["time"])[:10]
        pr = float(p["price"])
        wave_line_data.append({'time': t, 'value': pr})
        
        lbl = wave_labels[idx % len(wave_labels)]
        is_peak = p["type"] == "PEAK"
        markers.append({
            'time': t,
            'position': 'aboveBar' if is_peak else 'belowBar',
            'color': '#ffd700',
            'shape': 'arrowDown' if is_peak else 'arrowUp',
            'text': f"{lbl} ${pr:,.1f}"
        })

    candles_json = json.dumps(candles)
    wave_line_json = json.dumps(wave_line_data)
    markers_json = json.dumps(markers)
    fib_levels_json = json.dumps(wave_res.get('fib_levels', {}))
    show_fib_js = "true" if show_fib else "false"

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
        <style>
            html, body {{
                margin: 0; padding: 0; width: 100%; height: 100%;
                background-color: #0d1117; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                overflow: hidden;
            }}
            #tv_chart_container {{ width: 100%; height: 500px; }}
            .legend-bar {{
                position: absolute; top: 12px; left: 16px; z-index: 10;
                font-size: 13px; color: #c9d1d9; font-family: monospace;
                background: rgba(13, 17, 23, 0.85); padding: 5px 12px; border-radius: 4px;
                border: 1px solid #30363d; pointer-events: none;
            }}
        </style>
    </head>
    <body>
        <div class="legend-bar">
            <span style="color:#58a6ff; font-weight:bold;">日線艾略特波浪圖</span>
            <span style="color:#ffd700; margin-left:12px;">─── 黃線: 波浪骨架</span>
            {"<span style='color:#00E676; margin-left:12px;'>── 斐波那契回調線 (已開啟)</span>" if show_fib else "<span style='color:#8b949e; margin-left:12px;'>(Fib 回調線已隱藏)</span>"}
        </div>
        <div id="tv_chart_container"></div>

        <script>
            const chartContainer = document.getElementById('tv_chart_container');
            const chart = LightweightCharts.createChart(chartContainer, {{
                layout: {{
                    background: {{ color: '#0d1117' }},
                    textColor: '#8b949e',
                    fontSize: 12,
                }},
                grid: {{
                    vertLines: {{ color: '#161b22' }},
                    horzLines: {{ color: '#161b22' }},
                }},
                crosshair: {{
                    mode: LightweightCharts.CrosshairMode.Normal,
                    vertLine: {{ color: '#58a6ff', width: 1, style: 3 }},
                    horzLine: {{ color: '#58a6ff', width: 1, style: 3 }},
                }},
                rightPriceScale: {{
                    borderColor: '#21262d',
                    scaleMargins: {{ top: 0.1, bottom: 0.1 }},
                }},
                timeScale: {{
                    borderColor: '#21262d',
                    timeVisible: true,
                    secondsVisible: false,
                }},
                handleScroll: {{ mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: true }},
                handleScale: {{ axisPressedMouseMove: true, mouseWheel: true, pinch: true }},
            }});

            // 1. 純淨 K 線 (無 Volume 副圖干擾)
            const candlestickSeries = chart.addCandlestickSeries({{
                upColor: '#00E676', downColor: '#FF5252',
                borderUpColor: '#00E676', borderDownColor: '#FF5252',
                wickUpColor: '#00E676', wickDownColor: '#FF5252',
            }});
            candlestickSeries.setData({candles_json});
            candlestickSeries.setMarkers({markers_json});

            // 2. 波浪骨架
            const waveLineSeries = chart.addLineSeries({{
                color: '#ffd700',
                lineWidth: 2,
                crosshairMarkerVisible: false,
            }});
            waveLineSeries.setData({wave_line_json});

            // 3. 可切換的斐波那契回調線 (Fibonacci Retracement Lines)
            const showFib = {show_fib_js};
            const fibLevels = {fib_levels_json};
            if (showFib && Object.keys(fibLevels).length > 0) {{
                const colors = {{
                    "0.236": "#ff7b72",
                    "0.382": "#d29922",
                    "0.500": "#58a6ff",
                    "0.618 (黃金位)": "#00E676",
                    "0.786": "#a371f7"
                }};
                for (let key in fibLevels) {{
                    if (key.includes("0.000") || key.includes("1.000")) continue;
                    let pVal = fibLevels[key];
                    let lineCol = colors[key] || "#8b949e";
                    candlestickSeries.createPriceLine({{
                        price: pVal,
                        color: lineCol,
                        lineWidth: 1,
                        lineStyle: LightweightCharts.LineStyle.Dashed,
                        axisLabelVisible: true,
                        title: 'Fib ' + key,
                    }});
                }}
            }}

            window.addEventListener('resize', () => {{
                chart.applyOptions({{ width: chartContainer.clientWidth }});
            }});
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=515)

def render_nq_wave_prediction_dashboard():
    st.markdown("### 🌊 納指 (NQ / QQQ) 艾略特全波浪理論推演中樞")
    st.caption("幾何模型: **Extension 擴展浪 + Complex 複雜修正浪 + Fibonacci 時空回調**")

    df_day = load_data("US.QQQ", "DAY")
    df_1h = load_data("US.QQQ", "1Hr")

    if df_day.empty:
        st.warning("⏳ 尚未檢測到 `US_QQQ_DAY.csv` 數據，請先運行 `python data_fetcher.py`！")
        return

    wave_res = ElliottWaveEngine.analyze_wave_structure(df_day if len(df_day) >= 50 else df_1h)
    curr_price = float(df_day['close'].iloc[-1])

    # 1. 頂部核心狀態指標
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📌 當前基準現價", f"${curr_price:,.2f}")
    m2.metric("🌊 當下波浪定位", wave_res["current_wave"])
    m3.metric("🧬 浪級結構分類", wave_res["complex_type"])
    m4.metric("⏱️ 運行時間跨度", f"{wave_res['time_elapsed_hrs']} 天/棒", f"預期週期 ~{wave_res['expected_duration_hrs']} 棒")

    st.markdown("---")

    # 2. 控制列：Fibonacci 回調線顯示開關 (Toggle Switch)
    c_left, c_right = st.columns([3, 1])
    with c_left:
        st.markdown("#### 📈 TradingView 原生日線波浪圖表")
    with c_right:
        show_fib = st.toggle("📐 顯示斐波那契回調線 (Fib Retracement)", value=True)

    # 渲染純淨 TradingView 圖表 (無 Volume)
    render_tradingview_wave_chart(df_day, wave_res, show_fib=show_fib)

    st.markdown("---")

    # 3. 斐波那契點位與預測目標 Table
    st.markdown("#### 🧭 斐波那契回調位與未來空間推演")
    t1, t2 = st.columns(2)
    with t1:
        if wave_res["fib_levels"]:
            st.markdown("**📐 當前波段 Fibonacci 回調防線**")
            fib_df = pd.DataFrame([
                {"Fib 水位": k, "價格點位 ($)": f"${v:,.2f}"} for k, v in wave_res["fib_levels"].items()
            ])
            st.dataframe(fib_df, use_container_width=True, hide_index=True)
    with t2:
        st.markdown("**🎯 空間目標與風控防禦**")
        st.markdown(f"""
        | 指標項目 | 點位 ($) | 算法依據 |
        | :--- | :--- | :--- |
        | **第 1 目標位 (Target 1)** | **${wave_res['next_target_1']:,.2f}** | 1.0x 對稱推動浪 |
        | **第 2 目標位 (Target 2)** | **${wave_res['next_target_2']:,.2f}** | 1.618x 主升擴展浪 |
        | **結構失效防守位 (SL)** | **${wave_res['invalid_price']:,.2f}** | 艾略特鐵律重疊線 |
        """)

    st.markdown("---")

    # 4. 🤖 AI 智能解讀 Prompt 生成器 (一鍵複製給 AI)
    st.markdown("#### 🤖 專屬 AI 智能分析 Prompt (大白話解讀 + 華爾街科技股新聞連網)")
    st.caption("點擊下方代碼框右上角一鍵複製，貼給 ChatGPT、Claude 或 Gemini 即刻解讀！")

    ai_prompt_text = f"""你現在是華爾街資深宏觀量化策略師與科技股分析專家。請基於以下【納指 QQQ / NQ 日線艾略特波浪實時量化數據】，用通俗易懂的【大白話】為我深度解讀當前盤面，並即時【聯網檢索華爾街最新科技股動態】：

【1. 艾略特波浪量化數據】
• 監控標的: 納斯達克 100 指數 (QQQ / NQ)
• 當前現價: ${curr_price:,.2f}
• 當前波浪階段: {wave_res['current_wave']} ({wave_res['wave_phase']})
• 浪級結構特徵: {wave_res['complex_type']} (擴展倍數: {wave_res['extension_ratio']}x)
• 子浪進展: {wave_res['sub_wave']} (已運行 {wave_res['time_elapsed_hrs']} 根日線 Bar)
• 斐波那契關鍵回調位:
  - Fib 0.382: ${wave_res['fib_levels'].get('0.382', 'N/A')}
  - Fib 0.500: ${wave_res['fib_levels'].get('0.500', 'N/A')}
  - Fib 0.618 (黃金支撐): ${wave_res['fib_levels'].get('0.618 (黃金位)', 'N/A')}
• 目標預測點位: Target 1 = ${wave_res['next_target_1']:,.2f} | Target 2 = ${wave_res['next_target_2']:,.2f}
• 結構失效止損線: ${wave_res['invalid_price']:,.2f}

【2. 請回答以下三個問題（用大白話講，不要講太複雜的術語）】：
1. 【大白話走勢翻譯】：現在到底是在主升衝頂、還是洗盤震盪？接下來 1~3 天最可能怎麼走？如果是普通散戶現在該做多、做空還是觀望？
2. 【華爾街科技股新聞與巨頭動態】：請即刻聯網檢索今天/本週華爾街關於美股科技 7 巨頭（英偉達 NVDA、蘋果 AAPL、微軟 MSFT、谷歌 GOOGL、亞馬遜 AMZN、Meta、特斯拉 TSLA）以及 AI 芯片、存儲板塊的最新重大新聞或機構觀點。
3. 【實戰決策】：結合波浪點位與科技股新聞，給出明確的【0DTE / 波段期權操作計劃】（包含開倉區間、止損防守位與止盈目標）。"""

    st.code(ai_prompt_text, language="markdown")
