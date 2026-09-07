# 文件名: nq_wave_tab.py
# 核心功能: 納指 (NQ / QQQ) 日線雙屏波浪對比 (經典5浪 vs Wave 3 Estudio 專用主升推演) + AI Prompt 集成

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

class Wave3EstudioAdapter:
    """
    轉譯 elliott-wave3-estudio (Pine Script) 核心算法:
    專案專注於 Wave 3 主升浪捕捉、1.618x / 2.618x 擴展目標推演與動能突破驗證
    """
    @staticmethod
    def calculate_wave3_estudio(df: pd.DataFrame) -> tuple:
        if df.empty or len(df) < 20:
            return [], [], {"status": "數據累積中", "t1": 0.0, "t2": 0.0, "sl": 0.0, "valid": False}

        # 1. 提取時間與價格序列
        if 'date_str' in df.columns:
            dates = df['date_str'].astype(str).str.slice(0, 10).values
        elif 'time_key' in df.columns:
            dates = df['time_key'].astype(str).str.slice(0, 10).values
        else:
            dates = df.iloc[:, 0].astype(str).str.slice(0, 10).values

        high = df['high'].astype(float).values
        low = df['low'].astype(float).values
        close = df['close'].astype(float).values
        n = len(df)

        # 2. 幾何拐點提取 (提取候選波段)
        pivots = []
        for i in range(3, n - 3):
            if high[i] == max(high[i-3:i+4]):
                pivots.append({"index": i, "time": dates[i], "price": high[i], "type": "PEAK"})
            elif low[i] == min(low[i-3:i+4]):
                pivots.append({"index": i, "time": dates[i], "price": low[i], "type": "VALLEY"})

        # 清洗同向頂底
        clean_p = []
        for p in pivots:
            if not clean_p:
                clean_p.append(p)
            else:
                if clean_p[-1]["type"] != p["type"]:
                    clean_p.append(p)
                else:
                    if p["type"] == "PEAK" and p["price"] > clean_p[-1]["price"]:
                        clean_p[-1] = p
                    elif p["type"] == "VALLEY" and p["price"] < clean_p[-1]["price"]:
                        clean_p[-1] = p

        line_data = []
        markers = []

        if len(clean_p) < 4:
            return line_data, markers, {"status": "波段積累中", "t1": 0.0, "t2": 0.0, "sl": 0.0, "valid": False}

        # 取最近 4 個關鍵點作為 W0, W1, W2, W3
        p0, p1, p2, p3 = clean_p[-4], clean_p[-3], clean_p[-2], clean_p[-1]
        
        # 構建折線
        for p in [p0, p1, p2, p3]:
            line_data.append({"time": str(p["time"])[:10], "value": float(p["price"])})

        w1_len = abs(p1["price"] - p0["price"])
        curr_p = close[-1]
        
        # 判定多頭 Wave 3 Estudio 形態
        is_bull_w3 = p1["price"] > p0["price"] and p2["price"] > p0["price"]
        
        if is_bull_w3:
            t1_1618 = round(p2["price"] + 1.618 * w1_len, 2)
            t2_2618 = round(p2["price"] + 2.618 * w1_len, 2)
            sl_price = round(p2["price"], 2)
            
            markers.append({"time": str(p0["time"])[:10], "position": "belowBar", "color": "#a855f7", "shape": "circle", "text": f"W0 ${p0['price']:,.1f}"})
            markers.append({"time": str(p1["time"])[:10], "position": "aboveBar", "color": "#a855f7", "shape": "arrowDown", "text": f"W1 頂 ${p1['price']:,.1f}"})
            markers.append({"time": str(p2["time"])[:10], "position": "belowBar", "color": "#00E676", "shape": "arrowUp", "text": f"W2 啟動底 ${p2['price']:,.1f}"})
            
            # W3 進行中標註
            if curr_p > p1["price"]:
                markers.append({"time": str(p3["time"])[:10], "position": "aboveBar", "color": "#f59e0b", "shape": "circle", "text": f"🔥 W3 主升加速 (${p3['price']:,.1f})"})
                status_text = "🔥 W3 超級主升浪爆發中 (突破 W1 頂)"
            else:
                markers.append({"time": str(p3["time"])[:10], "position": "aboveBar", "color": "#38bdf8", "shape": "circle", "text": f"W3 醞釀中 (${p3['price']:,.1f})"})
                status_text = "⚡ W3 蓄勢醞釀中 (即將衝擊 W1 頂)"

            audit = {
                "status": status_text,
                "t1": t1_1618,
                "t2": t2_2618,
                "sl": sl_price,
                "valid": True,
                "w1_len": round(w1_len, 2),
                "w3_ratio": round(abs(curr_p - p2["price"]) / w1_len if w1_len > 0 else 1.0, 2)
            }
        else:
            t1_1618 = round(p2["price"] - 1.618 * w1_len, 2)
            t2_2618 = round(p2["price"] - 2.618 * w1_len, 2)
            sl_price = round(p2["price"], 2)
            audit = {
                "status": "🔴 空頭 C 浪 / 下跌 3 浪釋放",
                "t1": t1_1618,
                "t2": t2_2618,
                "sl": sl_price,
                "valid": True,
                "w1_len": round(w1_len, 2),
                "w3_ratio": round(abs(p2["price"] - curr_p) / w1_len if w1_len > 0 else 1.0, 2)
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

    # 1. 我們的經典日線波浪
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

    # 2. Wave 3 Estudio 專用主升推演
    w3_line, w3_markers, w3_audit = Wave3EstudioAdapter.calculate_wave3_estudio(df_plot)

    candles_json = json.dumps(candles)
    classic_line_json = json.dumps(classic_line)
    classic_markers_json = json.dumps(classic_markers)
    w3_line_json = json.dumps(w3_line)
    w3_markers_json = json.dumps(w3_markers)
    fib_levels_json = json.dumps(wave_res.get('fib_levels', {}))
    show_fib_p_js = "true" if show_fib_price else "false"

    t1_val = w3_audit.get("t1", 0.0)
    t2_val = w3_audit.get("t2", 0.0)
    sl_val = w3_audit.get("sl", 0.0)

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

            <!-- 右屏: Wave 3 Estudio 專用主升推演 -->
            <div class="chart-box">
                <div class="box-header">
                    <b style="color:#a855f7;">[右屏] Elliott Wave 3 Estudio</b>
                    <span style="color:#00E676; margin-left:6px;">T1(1.618x): ${t1_val:,.1f}</span>
                    <span style="color:#ff7b72; margin-left:6px;">SL: ${sl_val:,.1f}</span>
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

                // 2. 初始化右圖 (Wave 3 Estudio)
                const cRight = document.getElementById('tv_chart_right');
                chartRight = LightweightCharts.createChart(cRight, Object.assign({{}}, baseOpt, {{ width: cRight.clientWidth, height: cRight.clientHeight }}));
                const csRight = chartRight.addCandlestickSeries({{ upColor: '#00E676', downColor: '#FF5252', borderUpColor: '#00E676', borderDownColor: '#FF5252', wickUpColor: '#00E676', wickDownColor: '#FF5252' }});
                csRight.setData({candles_json});
                csRight.setMarkers({w3_markers_json});

                const wsRight = chartRight.addLineSeries({{ color: '#a855f7', lineWidth: 2.5, crosshairMarkerVisible: false }});
                wsRight.setData({w3_line_json});

                // 標註 Wave 3 專用 1.618x 與 2.618x 目標線
                if ({t1_val} > 0) {{
                    csRight.createPriceLine({{ price: {t1_val}, color: '#00E676', lineWidth: 1.5, lineStyle: LightweightCharts.LineStyle.Solid, axisLabelVisible: true, title: 'W3 T1 (1.618x $' + {t1_val}.toFixed(1) + ')' }});
                }}
                if ({t2_val} > 0) {{
                    csRight.createPriceLine({{ price: {t2_val}, color: '#f59e0b', lineWidth: 1.5, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: 'W3 T2 (2.618x $' + {t2_val}.toFixed(1) + ')' }});
                }}
                if ({sl_val} > 0) {{
                    csRight.createPriceLine({{ price: {sl_val}, color: '#ff7b72', lineWidth: 1.5, lineStyle: LightweightCharts.LineStyle.Solid, axisLabelVisible: true, title: 'W3 失效防守 ($' + {sl_val}.toFixed(1) + ')' }});
                }}

                chartRight.timeScale().fitContent();

                // 3. 自適應 Resize
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
    return w3_audit

def render_nq_wave_prediction_dashboard():
    st.markdown("### 🌊 納指 (NQ / QQQ) 艾略特波浪雙引擎終端 (經典 5 浪 vs Wave 3 Estudio)")
    st.caption("核心架構: **左屏經典波浪骨架 vs 右屏 Elliott Wave 3 Estudio 主升動能模型 (1:1 日線對比)**")

    df_day = load_data("US.QQQ", "DAY")
    if df_day.empty:
        st.warning("⏳ 尚未檢測到 `US_QQQ_DAY.csv` 數據，請先運行 `python data_fetcher.py`！")
        return

    time_col = 'time_key' if 'time_key' in df_day.columns else df_day.columns[0]
    df_day['date_str'] = df_day[time_col].astype(str).str.slice(0, 10)

    wave_res = ElliottWaveEngine.analyze_wave_structure(df_day)
    curr_price = float(df_day['close'].iloc[-1])

    w3_line, w3_markers, w3_audit = Wave3EstudioAdapter.calculate_wave3_estudio(df_day.tail(120))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📌 當前基準現價", f"${curr_price:,.2f}")
    m2.metric("🌊 經典波浪定位", wave_res["current_wave"], f"結構: {wave_res['complex_type']}")
    m3.metric("🚀 Wave 3 Estudio 狀態", w3_audit.get("status", "運算中"))
    m4.metric("🎯 3浪擴展倍數", f"{w3_audit.get('w3_ratio', 1.0)}x", f"1浪基數: ${w3_audit.get('w1_len', 0.0):,.1f}")

    st.markdown("---")

    # 控制列
    c_title, c_sw = st.columns([3, 1])
    with c_title:
        st.markdown("#### 📈 TradingView 雙屏對比 (左: 經典 5 浪 | 右: Wave 3 Estudio 專用主升)")
    with c_sw:
        show_fib_p = st.toggle("📐 顯示斐波那契價格線", value=True)

    # 渲染純日線雙屏圖表
    render_dual_tradingview_charts(df_day, wave_res, show_fib_price=show_fib_p)

    st.markdown("---")

    # 空間目標與對比矩陣
    st.markdown("#### 🧭 空間目標推演與 Wave 3 Estudio 算法對比矩陣")
    t1, t2, t3 = st.columns(3)
    
    with t1:
        st.markdown("**📐 Fibonacci 價格防線 (經典日線)**")
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
        st.markdown("**🚀 Wave 3 Estudio 專案推演矩陣**")
        st.info(f"""
        • **主升狀態**: `{w3_audit.get('status', '運算中')}`
        • **W3 Target 1 (1.618x)**: `${w3_audit.get('t1', 0.0):,.2f}`
        • **W3 Target 2 (2.618x)**: `${w3_audit.get('t2', 0.0):,.2f}`
        • **W3 結構失效線 (SL)**: `${w3_audit.get('sl', 0.0):,.2f}`
        """)

    st.markdown("---")

    # 專屬 AI 智能分析 Prompt
    st.markdown("#### 🤖 專屬 AI 智能分析 Prompt (大白話解讀 + Wave 3 主升共振 + 華爾街科技股連網)")
    st.caption("點擊下方代碼框右上角一鍵複製，貼給 AI 即刻獲取全盤深度解讀：")

    ai_prompt_text = f"""你現在是華爾街資深宏觀量化策略師與科技股分析專家。請基於以下【納指 QQQ / NQ 日線艾略特波浪雙引擎量化數據（含經典 5 浪骨架 + Elliott Wave 3 Estudio 專用主升浪推演）】，用通俗易懂的【大白話】為我深度解讀當前盤面，並即時【聯網檢索華爾街最新科技股動態】：

【1. 艾略特波浪雙引擎量化數據】
• 監控標的: 納斯達克 100 指數 (QQQ / NQ 日線)
• 當前基準現價: ${curr_price:,.2f}
• 經典波浪定位: {wave_res['current_wave']} ({wave_res['wave_phase']})
• 經典結構特徵: {wave_res['complex_type']} (擴展倍數: {wave_res['extension_ratio']}x)
• Wave 3 Estudio 專用主升推演:
  - 3浪運行狀態: {w3_audit.get('status', '運算中')}
  - 當前 3 浪推升倍數: {w3_audit.get('w3_ratio', 1.0)}x (基準 1 浪幅度: ${w3_audit.get('w1_len', 0.0):,.2f})
  - 3浪 Target 1 (1.618x 擴展) = ${w3_audit.get('t1', 0.0):,.2f}
  - 3浪 Target 2 (2.618x 極限) = ${w3_audit.get('t2', 0.0):,.2f}
  - 3浪 啟動失效防守線 (SL) = ${w3_audit.get('sl', 0.0):,.2f}

【2. 請回答以下三個問題（用大白話講，不要用過度複雜的術語）】：
1. 【雙引擎對比大白話解讀】：結合經典波浪與 Wave 3 Estudio 模型，當前納指是否處於勝率與空間最大的主升浪階段？接下來 1~3 天該如何應對？
2. 【華爾街科技股新聞與巨頭動態】：請即刻聯網檢索今日華爾街關於美股科技 7 巨頭（英偉達 NVDA、蘋果 AAPL、微軟 MSFT、谷歌 GOOGL、亞馬遜 AMZN、Meta、特斯拉 TSLA）以及 AI 芯片板塊的最新重大新聞與機構評級。
3. 【實戰決策】：給出明確的【0DTE / 短期期權操作計劃】（包含開倉區間、止損防守位與止盈目標）。"""

    st.code(ai_prompt_text, language="markdown")
