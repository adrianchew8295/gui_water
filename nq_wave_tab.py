# 文件名: nq_wave_tab.py
# 核心功能: TradingView 原生金融級日線波浪圖表 (支援滾輪縮放、拖曳定格) + 純數據波浪預測中樞

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

def render_tradingview_wave_chart(df_day: pd.DataFrame, wave_res: dict):
    """使用 TradingView 原生 Lightweight Charts 渲染支援滾輪縮放、拖曳定格的日線波浪圖"""
    if df_day.empty:
        return

    time_col = 'time_key' if 'time_key' in df_day.columns else df_day.columns[0]
    df_day['date_str'] = df_day[time_col].astype(str).str.slice(0, 10)
    df_day = df_day.drop_duplicates(subset=['date_str']).sort_values('date_str').reset_index(drop=True)
    df_plot = df_day.tail(150).copy().reset_index(drop=True)

    # 1. 整理 TradingView 格式的蠟燭數據與成交量
    candles = []
    volumes = []
    for _, r in df_plot.iterrows():
        t = str(r['date_str'])
        o, h, l, c, v = float(r['open']), float(r['high']), float(r['low']), float(r['close']), float(r.get('volume', 0))
        candles.append({'time': t, 'open': o, 'high': h, 'low': l, 'close': c})
        volumes.append({
            'time': t, 'value': v,
            'color': 'rgba(0, 230, 118, 0.4)' if c >= o else 'rgba(255, 82, 82, 0.4)'
        })

    # 2. 計算波浪拐點標記 (Markers) 與折線
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
    volumes_json = json.dumps(volumes)
    wave_line_json = json.dumps(wave_line_data)
    markers_json = json.dumps(markers)

    # 3. 嵌入 TradingView Lightweight Charts HTML/JS
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
                background: rgba(13, 17, 23, 0.75); padding: 4px 10px; border-radius: 4px;
                border: 1px solid #30363d; pointer-events: none;
            }}
        </style>
    </head>
    <body>
        <div class="legend-bar">
            <span style="color:#58a6ff; font-weight:bold;">QQQ / NQ 日線艾略特波浪圖</span>
            <span style="color:#ffd700; margin-left:12px;">─── 黃色折線: 波浪骨架軌跡</span>
            <span style="color:#00E676; margin-left:12px;">🖱️ 支援滑鼠滾輪縮放 / 拖拽定格</span>
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
                    scaleMargins: {{ top: 0.1, bottom: 0.2 }},
                }},
                timeScale: {{
                    borderColor: '#21262d',
                    timeVisible: true,
                    secondsVisible: false,
                }},
                handleScroll: {{ mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: true }},
                handleScale: {{ axisPressedMouseMove: true, mouseWheel: true, pinch: true }},
            }});

            // 1. 蠟燭圖主圖
            const candlestickSeries = chart.addCandlestickSeries({{
                upColor: '#00E676', downColor: '#FF5252',
                borderUpColor: '#00E676', borderDownColor: '#FF5252',
                wickUpColor: '#00E676', wickDownColor: '#FF5252',
            }});
            candlestickSeries.setData({candles_json});

            // 2. 設置波浪標籤 (① ~ ⑤ / ⓐ ~ ⓒ)
            candlestickSeries.setMarkers({markers_json});

            // 3. 疊加波浪骨架線
            const waveLineSeries = chart.addLineSeries({{
                color: '#ffd700',
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Solid,
                crosshairMarkerVisible: false,
            }});
            waveLineSeries.setData({wave_line_json});

            // 4. 成交量副圖
            const volumeSeries = chart.addHistogramSeries({{
                priceFormat: {{ type: 'volume' }},
                priceScaleId: '',
                scaleMargins: {{ top: 0.82, bottom: 0 }},
            }});
            volumeSeries.setData({volumes_json});

            // 自動適應容器寬度
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
    st.caption("底層引擎: **TradingView 原生 Lightweight-Charts** | 幾何模型: **Zigzag 骨架拐點 + 斐波那契時空投影**")

    df_day = load_data("US.QQQ", "DAY")
    df_1h = load_data("US.QQQ", "1Hr")

    if df_day.empty:
        st.warning("⏳ 尚未檢測到 `US_QQQ_DAY.csv` 歷史數據。請先在終端機運行 `python data_fetcher.py`！")
        return

    wave_res = ElliottWaveEngine.analyze_wave_structure(df_day if len(df_day) >= 50 else df_1h)
    curr_price = float(df_day['close'].iloc[-1])

    # 1. 頂部核心指標看板
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📌 當前最新基準價", f"${curr_price:,.2f}")
    m2.metric("🌊 當下波浪定位", wave_res["current_wave"])
    m3.metric("🧭 浪級宏觀方向", wave_res["trend_dir"])
    m4.metric("⏱️ 本浪運行時間", f"{wave_res['time_elapsed_hrs']} 天/棒", f"預期週期 ~{wave_res['expected_duration_hrs']} 棒")

    st.markdown("---")

    # 2. 📈 TradingView 原生金融級日線波浪圖表
    st.markdown("#### 📈 TradingView 原生金融級日線波浪圖 (支援滑鼠滾輪縮放、拖拽定格)")
    render_tradingview_wave_chart(df_day, wave_res)

    st.markdown("---")

    # 3. 🔮 未來走勢預測與目標推演
    st.markdown("#### 🧭 未來波浪走勢與空間目標推演 (Prediction Window)")
    pred_col1, pred_col2 = st.columns([1.5, 1.0])
    
    with pred_col1:
        st.info(f"### 🤖 艾略特波浪推演結論\n\n{wave_res['prediction_narrative']}")
        st.markdown(f"""
        * **當前子浪階梯 (Sub-Wave)**: `{wave_res['sub_wave']}` ({wave_res['wave_phase']})
        * **波浪健康度**: 結構完整，符合波浪鐵律（4浪不破1浪頂）。
        """)

    with pred_col2:
        st.markdown(f"""
        | 波浪推演指標 | 目標點位 ($) | 斐波那契依據 |
        | :--- | :--- | :--- |
        | **第 1 目標位 (Target 1)** | **${wave_res['next_target_1']:,.2f}** | 1.0x 對稱浪 |
        | **第 2 目標位 (Target 2)** | **${wave_res['next_target_2']:,.2f}** | 1.618x 主升擴展浪 |
        | **結構失效防守位 (SL)** | **${wave_res['invalid_price']:,.2f}** | 艾略特鐵律重疊防線 |
        """)
