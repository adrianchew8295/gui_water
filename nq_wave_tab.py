# 文件名: nq_wave_tab.py
# 核心功能: 納指 (NQ / QQQ) 日線波浪雙屏對比 (我們的經典波浪 vs SmarterSystems ATR 自適應波浪) + AI Prompt 集成

import os
import json
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from elliott_wave_engine import ElliottWaveEngine

DATA_DIR = './market_data'

def load_data(symbol: str, timeframe: str = "DAY") -> pd.DataFrame:
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

class SmarterWaveAdapter:
    """吸納 SmarterSystems/ElliottWavesEngine 的 ATR 自適應拐點與 3 浪最短否決規則"""
    @staticmethod
    def calculate_smarter_waves(df: pd.DataFrame, atr_mult: float = 1.3) -> tuple:
        if df.empty or len(df) < 20:
            return [], [], {"valid": True, "note": "數據累積中", "alt": "計算中"}

        # 自動防呆相容時間欄位，避免 KeyError: 'date_str'
        if 'date_str' in df.columns:
            dates = df['date_str'].astype(str).str.slice(0, 10).values
        elif 'time_key' in df.columns:
            dates = df['time_key'].astype(str).str.slice(0, 10).values
        elif 'date' in df.columns:
            dates = df['date'].astype(str).str.slice(0, 10).values
        else:
            dates = df.iloc[:, 0].astype(str).str.slice(0, 10).values

        high_col = 'high' if 'high' in df.columns else df.columns[1]
        low_col = 'low' if 'low' in df.columns else df.columns[2]
        close_col = 'close' if 'close' in df.columns else df.columns[3]

        high = df[high_col].astype(float).values
        low = df[low_col].astype(float).values
        close = df[close_col].astype(float).values
        n = len(df)

        # 1. ATR 波動率計算
        tr = np.maximum(high[1:] - low[1:], np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])))
        atr = np.mean(tr[-14:]) if len(tr) >= 14 else (np.mean(tr) if len(tr) > 0 else 2.0)
        threshold = max(atr * atr_mult, 1.5)

        pivots = []
        last_type = None
        last_p = close[0]

        for i in range(1, n):
            h_i, l_i, t_i = high[i], low[i], dates[i]
            if last_type != "PEAK" and (h_i - last_p) >= threshold:
                pivots.append({"index": i, "time": t_i, "price": float(h_i), "type": "PEAK"})
                last_type = "PEAK"
                last_p = h_i
            elif last_type != "VALLEY" and (last_p - l_i) >= threshold:
                pivots.append({"index": i, "time": t_i, "price": float(l_i), "type": "VALLEY"})
                last_type = "VALLEY"
                last_p = l_i

        # 2. 構建折線與標籤數據
        line_data = []
        markers = []
        smarter_labels = ["P1 (起點)", "P2 (一浪頂)", "P3 (二浪底)", "P4 (三浪主升)", "P5 (四浪調整)", "P6 (五浪衝頂)"]

        for idx, p in enumerate(pivots):
            t = str(p["time"])[:10]
            pr = float(p["price"])
            line_data.append({"time": t, "value": pr})
            
            lbl = smarter_labels[idx] if idx < len(smarter_labels) else f"P{idx+1}"
            is_peak = p["type"] == "PEAK"
            markers.append({
                "time": t,
                "position": "aboveBar" if is_peak else "belowBar",
                "color": "#38bdf8",
                "shape": "arrowDown" if is_peak else "arrowUp",
                "text": f"{lbl} ${pr:,.1f}"
            })

        # 3. 鐵律審核 (3浪不能最短)
        audit = {"valid": True, "note": "✅ 符合 Smarter 鐵律", "alt": "主推推動浪 (Primary Count)"}
        if len(pivots) >= 5:
            p_vals = [x["price"] for x in pivots[-5:]]
            w1 = abs(p_vals[1] - p_vals[0])
            w3 = abs(p_vals[3] - p_vals[2])
            w5 = abs(p_vals[4] - p_vals[3])
            if w3 < w1 and w3 < w5:
                audit = {
                    "valid": False,
                    "note": "⚠️ 觸發鐵律否決: 3浪最短",
                    "alt": "切換為複雜修正浪 (Complex ABC)"
                }

        return line_data, markers, audit

def render_dual_tradingview_charts(df_day: pd.DataFrame, wave_res: dict, show_fib_price: bool):
    time_col = 'time_key' if 'time_key' in df_day.columns else df_day.columns[0]
    df_day['date_str'] = df_day[time_col].astype(str).str.slice(0, 10)
    df_day = df_day.drop_duplicates(subset=['date_str']).sort_values('date_str').reset_index(drop=True)
    df_plot = df_day.tail(120).copy().reset_index(drop=True)

    candles = []
    for _, r in df_plot.iterrows():
        try:
            candles.append({
                'time': str(r['date_str']),
                'open': float(r['open']),
                'high': float(r['high']),
                'low': float(r['low']),
                'close': float(r['close'])
            })
        except Exception:
            continue

    # 1. 我們的經典波浪
    day_pivots = ElliottWaveEngine.extract_pivots(df_plot, window=4)
    classic_line = []
    classic_markers = []
    wave_labels = ["①", "②", "③", "④", "⑤", "ⓐ", "ⓑ", "ⓒ"]

    for idx, p in enumerate(day_pivots):
        t = str(p["time"])[:10]
        pr = float(p["price"])
        classic_line.append({'time': t, 'value': pr})
        lbl = wave_labels[idx % len(wave_labels)]
        is_peak = p["type"] == "PEAK"
        classic_markers.append({
            'time': t,
            'position': 'aboveBar' if is_peak else 'belowBar',
            'color': '#ffd700',
            'shape': 'arrowDown' if is_peak else 'arrowUp',
            'text': f"{lbl} ${pr:,.1f}"
        })

    # 2. Smarter ATR 自適應波浪
    smarter_line, smarter_markers, smarter_audit = SmarterWaveAdapter.calculate_smarter_waves(df_plot, atr_mult=1.3)

    candles_json = json.dumps(candles)
    classic_line_json = json.dumps(classic_line)
    classic_markers_json = json.dumps(classic_markers)
    smarter_line_json = json.dumps(smarter_line)
    smarter_markers_json = json.dumps(smarter_markers)
    fib_levels_json = json.dumps(wave_res.get('fib_levels', {}))
    show_fib_p_js = "true" if show_fib_price else "false"

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
        <style>
            html, body {{
                margin: 0; padding: 0; width: 100%; height: 100%;
                background-color: #0d1117; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
                overflow: hidden; user-select: none;
            }}
            .dual-wrapper {{
                display: flex; width: 100%; height: 500px; gap: 10px; box-sizing: border-box; padding: 4px;
            }}
            .chart-box {{
                flex: 1; height: 100%; position: relative; border: 1px solid #30363d; border-radius: 8px; background: #0d1117;
                box-shadow: 0 4px 12px rgba(0,0,0,0.5); overflow: hidden;
            }}
            .box-header {{
                position: absolute; top: 10px; left: 12px; z-index: 10;
                font-size: 12px; color: #c9d1d9; background: rgba(22, 27, 34, 0.92);
                backdrop-filter: blur(4px); padding: 5px 10px; border-radius: 6px; border: 1px solid #30363d; pointer-events: none;
            }}
            .reset-btn {{
                position: absolute; top: 10px; right: 10px; z-index: 10;
                font-size: 11px; color: #58a6ff; background: rgba(22, 27, 34, 0.9);
                border: 1px solid #30363d; border-radius: 4px; padding: 3px 8px; cursor: pointer;
            }}
            .reset-btn:hover {{ background: #21262d; color: #79c0ff; }}
            .container {{ width: 100%; height: 100%; }}
        </style>
    </head>
    <body>
        <div class="dual-wrapper">
            <!-- 左屏: 我們的經典日線波浪 -->
            <div class="chart-box">
                <div class="box-header">
                    <b style="color:#ffd700;">[左屏] 經典艾略特波浪 (Daily)</b>
                    <span style="color:#8b949e; margin-left:6px;">── 5浪幾何骨架</span>
                </div>
                <button class="reset-btn" onclick="fitChart(chartLeft)">🔍 適配</button>
                <div id="tv_chart_left" class="container"></div>
            </div>

            <!-- 右屏: SmarterSystems ATR 自適應浪形 -->
            <div class="chart-box">
                <div class="box-header">
                    <b style="color:#38bdf8;">[右屏] SmarterSystems 自適應 (Daily)</b>
                    <span style="color:#38bdf8; margin-left:6px;">── ATR 拐點 + 鐵律驗證</span>
                </div>
                <button class="reset-btn" onclick="fitChart(chartRight)">🔍 適配</button>
                <div id="tv_chart_right" class="container"></div>
            </div>
        </div>

        <script>
            let chartLeft, chartRight;

            function fitChart(c) {{ if (c) c.timeScale().fitContent(); }}

            function initCharts() {{
                if (typeof LightweightCharts === 'undefined') {{
                    setTimeout(initCharts, 80);
                    return;
                }}

                const baseOpt = {{
                    layout: {{ background: {{ color: '#0d1117' }}, textColor: '#8b949e', fontSize: 11 }},
                    grid: {{ vertLines: {{ color: '#161b22' }}, horzLines: {{ color: '#161b22' }} }},
                    crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
                    rightPriceScale: {{ borderColor: '#30363d', scaleMargins: {{ top: 0.12, bottom: 0.12 }} }},
                    timeScale: {{ borderColor: '#30363d', timeVisible: true, secondsVisible: false }},
                    handleScroll: {{ mouseWheel: true, pressedMouseMove: true }},
                    handleScale: {{ axisPressedMouseMove: true, mouseWheel: true }},
                }};

                // 1. 初始化左圖 (經典波浪)
                const cLeft = document.getElementById('tv_chart_left');
                chartLeft = LightweightCharts.createChart(cLeft, Object.assign({{}}, baseOpt, {{ width: cLeft.clientWidth, height: cLeft.clientHeight }}));
                const csLeft = chartLeft.addCandlestickSeries({{ upColor: '#00E676', downColor: '#FF5252', borderUpColor: '#00E676', borderDownColor: '#FF5252', wickUpColor: '#00E676', wickDownColor: '#FF5252' }});
                csLeft.setData({candles_json});
                csLeft.setMarkers({classic_markers_json});

                const wsLeft = chartLeft.addLineSeries({{ color: '#ffd700', lineWidth: 2, crosshairMarkerVisible: false }});
                wsLeft.setData({classic_line_json});

                const showFib = {show_fib_p_js};
                const fibLevels = {fib_levels_json};
                if (showFib && Object.keys(fibLevels).length > 0) {{
                    for (let key in fibLevels) {{
                        if (key.includes("0.000") || key.includes("1.000")) continue;
                        csLeft.createPriceLine({{ price: fibLevels[key], color: '#8b949e', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: 'Fib ' + key }});
                    }}
                }}
                chartLeft.timeScale().fitContent();

                // 2. 初始化右圖 (Smarter 自適應)
                const cRight = document.getElementById('tv_chart_right');
                chartRight = LightweightCharts.createChart(cRight, Object.assign({{}}, baseOpt, {{ width: cRight.clientWidth, height: cRight.clientHeight }}));
                const csRight = chartRight.addCandlestickSeries({{ upColor: '#00E676', downColor: '#FF5252', borderUpColor: '#00E676', borderDownColor: '#FF5252', wickUpColor: '#00E676', wickDownColor: '#FF5252' }});
                csRight.setData({candles_json});
                csRight.setMarkers({smarter_markers_json});

                const wsRight = chartRight.addLineSeries({{ color: '#38bdf8', lineWidth: 2, crosshairMarkerVisible: false }});
                wsRight.setData({smarter_line_json});
                chartRight.timeScale().fitContent();

                // 3. 視窗尺寸自適應
                const resizeObserver = new ResizeObserver(() => {{
                    chartLeft.applyOptions({{ width: cLeft.clientWidth, height: cLeft.clientHeight }});
                    chartRight.applyOptions({{ width: cRight.clientWidth, height: cRight.clientHeight }});
                }});
                resizeObserver.observe(cLeft);
                resizeObserver.observe(cRight);
            }}
            initCharts();
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=515)
    return smarter_audit

def render_nq_wave_prediction_dashboard():
    st.markdown("### 🌊 納指 (NQ / QQQ) 艾略特波浪日線雙引擎對比終端")
    st.caption("核心架構: **左屏經典波浪骨架 vs 右屏 SmarterSystems ATR 自適應浪形 (1:1 日線對比)**")

    df_day = load_data("US.QQQ", "DAY")
    if df_day.empty:
        st.warning("⏳ 尚未檢測到 `US_QQQ_DAY.csv` 數據，請先運行 `python data_fetcher.py`！")
        return

    # 先為 df_day 生成統一的 date_str 欄位，徹底防止底層與衍生計算報錯
    time_col = 'time_key' if 'time_key' in df_day.columns else df_day.columns[0]
    df_day['date_str'] = df_day[time_col].astype(str).str.slice(0, 10)

    wave_res = ElliottWaveEngine.analyze_wave_structure(df_day)
    curr_price = float(df_day['close'].iloc[-1])

    smarter_line, smarter_markers, smarter_audit = SmarterWaveAdapter.calculate_smarter_waves(df_day.tail(120), atr_mult=1.3)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📌 當前基準現價", f"${curr_price:,.2f}")
    m2.metric("🌊 經典波浪定位", wave_res["current_wave"], f"結構: {wave_res['complex_type']}")
    m3.metric("🧠 Smarter 鐵律審核", "🟢 3浪擴展有效" if smarter_audit["valid"] else "🔴 3浪最短否決", smarter_audit["alt"])
    m4.metric("⏱️ 運行時間跨度", f"{wave_res['time_elapsed_bars']} 棒", f"預期週期 ~{wave_res['expected_duration_bars']} 棒")

    st.markdown("---")

    # 控制列
    c_title, c_sw = st.columns([3, 1])
    with c_title:
        st.markdown("#### 📈 TradingView 雙屏對比 (左: 經典波浪 | 右: Smarter 自適應)")
    with c_sw:
        show_fib_p = st.toggle("📐 顯示斐波那契價格線", value=True)

    # 渲染純日線雙屏圖表
    render_dual_tradingview_charts(df_day, wave_res, show_fib_price=show_fib_p)

    st.markdown("---")

    # 空間目標與對比矩陣
    st.markdown("#### 🧭 空間目標推演與 SmarterSystems 算法對比矩陣")
    t1, t2, t3 = st.columns(3)
    
    with t1:
        st.markdown("**📐 Fibonacci 價格防線 (日線)**")
        if wave_res["fib_levels"]:
            fib_df = pd.DataFrame([
                {"Fib 水位": k, "價格 ($)": f"${v:,.2f}"} for k, v in wave_res["fib_levels"].items()
            ])
            st.dataframe(fib_df, use_container_width=True, hide_index=True)

    with t2:
        st.markdown("**🎯 空間推演目標與防禦線**")
        st.markdown(f"""
        | 指標項目 | 點位 ($) | 算法依據 |
        | :--- | :--- | :--- |
        | **第 1 目標 (Target 1)** | **${wave_res['next_target_1']:,.2f}** | 1.0x 對稱推動浪 |
        | **第 2 目標 (Target 2)** | **${wave_res['next_target_2']:,.2f}** | 1.618x 主升擴展浪 |
        | **鐵律失效線 (SL)** | **${wave_res['invalid_price']:,.2f}** | 4浪不得破1浪頂 |
        """)

    with t3:
        st.markdown("**🧠 SmarterSystems 算法共振裁決**")
        st.info(f"""
        • **狀態判定**: `{smarter_audit['note']}`
        • **路徑指引**: `{smarter_audit['alt']}`
        • **ATR 捕獲拐點**: `{len(smarter_line)} 處`
        • **雙引擎共振**: `{'🟢 雙重確認主升/推進' if smarter_audit['valid'] else '🟡 需防範複雜鋸齒洗盤'}`
        """)

    st.markdown("---")

    # 專屬 AI 智能分析 Prompt
    st.markdown("#### 🤖 專屬 AI 智能分析 Prompt (大白話解讀 + 雙引擎波浪對比 + 華爾街科技股連網)")
    st.caption("點擊下方代碼框右上角一鍵複製，貼給 AI 即刻獲取全盤深度解讀：")

    ai_prompt_text = f"""你現在是華爾街資深宏觀量化策略師與科技股分析專家。請基於以下【納指 QQQ / NQ 日線艾略特波浪雙引擎量化數據（含經典 5 浪骨架 + SmarterSystems ATR 自適應對比）】，用通俗易懂的【大白話】為我深度解讀當前盤面，並即時【聯網檢索華爾街最新科技股動態】：

【1. 艾略特波浪雙引擎量化數據】
• 監控標的: 納斯達克 100 指數 (QQQ / NQ 日線)
• 當前基準現價: ${curr_price:,.2f}
• 經典波浪定位: {wave_res['current_wave']} ({wave_res['wave_phase']})
• 結構特徵: {wave_res['complex_type']} (擴展倍數: {wave_res['extension_ratio']}x)
• SmarterSystems 算法對比核驗:
  - 鐵律核驗狀態: {smarter_audit['note']}
  - 備選路徑狀態: {smarter_audit['alt']}
• 空間目標與防守點位:
  - Target 1 (1.0x 對稱浪) = ${wave_res['next_target_1']:,.2f}
  - Target 2 (1.618x 擴展浪) = ${wave_res['next_target_2']:,.2f}
  - 結構失效防守線 (SL) = ${wave_res['invalid_price']:,.2f}

【2. 請回答以下三個問題（用大白話講，不要用過度複雜的術語）】：
1. 【雙引擎對比大白話解讀】：結合經典波浪與 SmarterSystems 自適應路徑，當前納指是在主升衝頂還是震盪洗盤？接下來 1~3 天該如何應對？
2. 【華爾街科技股新聞與巨頭動態】：請即刻聯網檢索今日華爾街關於美股科技 7 巨頭（英偉達 NVDA、蘋果 AAPL、微軟 MSFT、谷歌 GOOGL、亞馬遜 AMZN、Meta、特斯拉 TSLA）以及 AI 芯片板塊的最新重大新聞與機構評級。
3. 【實戰決策】：給出明確的【0DTE / 短期期權操作計劃】（包含開倉區間、止損防守位與止盈目標）。"""

    st.code(ai_prompt_text, language="markdown")
