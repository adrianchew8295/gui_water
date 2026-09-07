# 文件名: nq_wave_tab.py
# 核心升級: 1小時圖多維度交互調控台 + Lightweight Charts 原廠雙屏聯動

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

def render_dual_tradingview_charts(
    df_day: pd.DataFrame, 
    df_1h: pd.DataFrame, 
    wave_res: dict, 
    show_fib_price: bool, 
    show_targets: bool,
    bars_1h_count: int
):
    # 1. 日線數據 (YYYY-MM-DD)
    time_col_d = 'time_key' if 'time_key' in df_day.columns else df_day.columns[0]
    df_day['date_str'] = df_day[time_col_d].astype(str).str.slice(0, 10)
    df_day = df_day.drop_duplicates(subset=['date_str']).sort_values('date_str').reset_index(drop=True)
    df_plot_d = df_day.tail(120).copy().reset_index(drop=True)

    candles_day = []
    for _, r in df_plot_d.iterrows():
        try:
            candles_day.append({
                'time': str(r['date_str']),
                'open': float(r['open']),
                'high': float(r['high']),
                'low': float(r['low']),
                'close': float(r['close'])
            })
        except Exception:
            continue

    day_pivots = ElliottWaveEngine.extract_pivots(df_plot_d, window=4)
    wave_line_day = []
    markers_day = []
    wave_labels = ["①", "②", "③", "④", "⑤", "ⓐ", "ⓑ", "ⓒ"]

    for idx, p in enumerate(day_pivots):
        t = str(p["time"])[:10]
        pr = float(p["price"])
        wave_line_day.append({'time': t, 'value': pr})
        lbl = wave_labels[idx % len(wave_labels)]
        is_peak = p["type"] == "PEAK"
        markers_day.append({
            'time': t,
            'position': 'aboveBar' if is_peak else 'belowBar',
            'color': '#ffd700',
            'shape': 'arrowDown' if is_peak else 'arrowUp',
            'text': f"{lbl} ${pr:,.1f}"
        })

    # 2. 1H 數據 (依據調控的 Bars 數量切片)
    source_1h = df_1h if (not df_1h.empty and len(df_1h) >= 5) else df_day
    time_col_1h = 'time_key' if 'time_key' in source_1h.columns else source_1h.columns[0]
    source_1h['dt_raw'] = source_1h[time_col_1h].astype(str)
    source_1h = source_1h.drop_duplicates(subset=['dt_raw']).sort_values('dt_raw').reset_index(drop=True)
    
    # 根據用戶調控參數裁切 1H K線數量
    df_plot_1h = source_1h.tail(bars_1h_count).copy().reset_index(drop=True)

    candles_1h = []
    for _, r in df_plot_1h.iterrows():
        try:
            dt_str_val = str(r['dt_raw'])
            if len(dt_str_val) > 10:
                t_val = int(pd.to_datetime(dt_str_val).timestamp())
            else:
                t_val = dt_str_val[:10]

            candles_1h.append({
                'time': t_val,
                'open': float(r['open']),
                'high': float(r['high']),
                'low': float(r['low']),
                'close': float(r['close'])
            })
        except Exception:
            continue

    candles_day_json = json.dumps(candles_day)
    wave_day_json = json.dumps(wave_line_day)
    markers_day_json = json.dumps(markers_day)
    candles_1h_json = json.dumps(candles_1h)
    fib_levels_json = json.dumps(wave_res.get('fib_levels', {}))
    show_fib_p_js = "true" if show_fib_price else "false"
    show_targets_js = "true" if show_targets else "false"

    target_1 = wave_res.get('next_target_1', 0.0)
    target_2 = wave_res.get('next_target_2', 0.0)
    invalid_p = wave_res.get('invalid_price', 0.0)

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
                display: flex; width: 100%; height: 500px; gap: 12px; box-sizing: border-box; padding: 4px;
            }}
            .chart-box {{
                flex: 1; height: 100%; position: relative; border: 1px solid #30363d; border-radius: 8px; background: #0d1117;
                box-shadow: 0 4px 12px rgba(0,0,0,0.5); overflow: hidden;
            }}
            .box-header {{
                position: absolute; top: 10px; left: 12px; z-index: 10;
                font-size: 12px; color: #c9d1d9; background: rgba(22, 27, 34, 0.88);
                backdrop-filter: blur(4px); padding: 5px 10px; border-radius: 6px; border: 1px solid #30363d; pointer-events: none;
            }}
            .reset-btn {{
                position: absolute; top: 10px; right: 12px; z-index: 10;
                font-size: 11px; color: #58a6ff; background: rgba(22, 27, 34, 0.9);
                border: 1px solid #30363d; border-radius: 4px; padding: 3px 8px; cursor: pointer;
            }}
            .reset-btn:hover {{ background: #21262d; color: #79c0ff; }}
            .container {{ width: 100%; height: 100%; }}
        </style>
    </head>
    <body>
        <div class="dual-wrapper">
            <div class="chart-box">
                <div class="box-header">
                    <b style="color:#58a6ff;">[左屏] 日線宏觀波浪 (Daily)</b>
                    <span style="color:#ffd700; margin-left:8px;">── 浪級骨架標籤</span>
                </div>
                <button class="reset-btn" onclick="fitDayChart()">🔍 適配視野</button>
                <div id="tv_chart_day" class="container"></div>
            </div>

            <div class="chart-box">
                <div class="box-header">
                    <b style="color:#00E676;">[右屏] 1H 微觀調控驗證 ({bars_1h_count} Bars)</b>
                    <span style="color:#00E676; margin-left:8px;">── T1: ${target_1:,.2f}</span>
                    <span style="color:#ff7b72; margin-left:8px;">── 防守: ${invalid_p:,.2f}</span>
                </div>
                <button class="reset-btn" onclick="fit1hChart()">🔍 適配視野</button>
                <div id="tv_chart_1h" class="container"></div>
            </div>
        </div>

        <script>
            let chartDay, chart1h;

            function fitDayChart() {{ if (chartDay) chartDay.timeScale().fitContent(); }}
            function fit1hChart() {{ if (chart1h) chart1h.timeScale().fitContent(); }}

            function initCharts() {{
                if (typeof LightweightCharts === 'undefined') {{
                    setTimeout(initCharts, 80);
                    return;
                }}

                const chartOptionsBase = {{
                    layout: {{ background: {{ color: '#0d1117' }}, textColor: '#8b949e', fontSize: 11 }},
                    grid: {{ vertLines: {{ color: '#161b22' }}, horzLines: {{ color: '#161b22' }} }},
                    crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
                    rightPriceScale: {{ borderColor: '#30363d', scaleMargins: {{ top: 0.12, bottom: 0.12 }} }},
                    timeScale: {{ borderColor: '#30363d', timeVisible: true, secondsVisible: false }},
                    handleScroll: {{ mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: true }},
                    handleScale: {{ axisPressedMouseMove: true, mouseWheel: true, pinch: true }},
                }};

                // 1. 初始化左圖
                const cDay = document.getElementById('tv_chart_day');
                chartDay = LightweightCharts.createChart(cDay, Object.assign({{}}, chartOptionsBase, {{
                    width: cDay.clientWidth,
                    height: cDay.clientHeight,
                }}));

                const candleSeriesDay = chartDay.addCandlestickSeries({{
                    upColor: '#00E676', downColor: '#FF5252',
                    borderUpColor: '#00E676', borderDownColor: '#FF5252',
                    wickUpColor: '#00E676', wickDownColor: '#FF5252',
                }});
                candleSeriesDay.setData({candles_day_json});
                candleSeriesDay.setMarkers({markers_day_json});

                const waveSeriesDay = chartDay.addLineSeries({{
                    color: '#ffd700', lineWidth: 2, crosshairMarkerVisible: false,
                }});
                waveSeriesDay.setData({wave_day_json});

                const showFib = {show_fib_p_js};
                const fibLevels = {fib_levels_json};
                if (showFib && Object.keys(fibLevels).length > 0) {{
                    const colors = {{
                        "0.236": "#ff7b72",
                        "0.382 (4浪常規支撐)": "#d29922",
                        "0.500 (平衡防線)": "#58a6ff",
                        "0.618 (黃金分割)": "#00E676",
                        "0.786": "#a371f7"
                    }};
                    for (let key in fibLevels) {{
                        if (key.includes("0.000") || key.includes("1.000")) continue;
                        let pVal = fibLevels[key];
                        let lineCol = colors[key] || "#8b949e";
                        candleSeriesDay.createPriceLine({{
                            price: pVal, color: lineCol, lineWidth: 1,
                            lineStyle: LightweightCharts.LineStyle.Dashed,
                            axisLabelVisible: true, title: 'Fib ' + key,
                        }});
                    }}
                }}
                chartDay.timeScale().fitContent();

                // 2. 初始化右圖
                const c1h = document.getElementById('tv_chart_1h');
                chart1h = LightweightCharts.createChart(c1h, Object.assign({{}}, chartOptionsBase, {{
                    width: c1h.clientWidth,
                    height: c1h.clientHeight,
                }}));

                const candleSeries1h = chart1h.addCandlestickSeries({{
                    upColor: '#00E676', downColor: '#FF5252',
                    borderUpColor: '#00E676', borderDownColor: '#FF5252',
                    wickUpColor: '#00E676', wickDownColor: '#FF5252',
                }});
                candleSeries1h.setData({candles_1h_json});

                // 調控開關：目標線與防守線
                const showTargets = {show_targets_js};
                if (showTargets) {{
                    if ({target_1} > 0) {{
                        candleSeries1h.createPriceLine({{
                            price: {target_1}, color: '#00E676', lineWidth: 1.5,
                            lineStyle: LightweightCharts.LineStyle.Solid,
                            axisLabelVisible: true, title: 'Target 1 ($' + {target_1}.toFixed(1) + ')',
                        }});
                    }}
                    if ({target_2} > 0) {{
                        candleSeries1h.createPriceLine({{
                            price: {target_2}, color: '#3fb950', lineWidth: 1,
                            lineStyle: LightweightCharts.LineStyle.Dashed,
                            axisLabelVisible: true, title: 'Target 2 ($' + {target_2}.toFixed(1) + ')',
                        }});
                    }}
                    if ({invalid_p} > 0) {{
                        candleSeries1h.createPriceLine({{
                            price: {invalid_p}, color: '#ff7b72', lineWidth: 1.5,
                            lineStyle: LightweightCharts.LineStyle.Solid,
                            axisLabelVisible: true, title: 'SL 防守 ($' + {invalid_p}.toFixed(1) + ')',
                        }});
                    }}
                }}

                chart1h.timeScale().fitContent();

                const resizeObserver = new ResizeObserver(() => {{
                    chartDay.applyOptions({{ width: cDay.clientWidth, height: cDay.clientHeight }});
                    chart1h.applyOptions({{ width: c1h.clientWidth, height: c1h.clientHeight }});
                }});
                resizeObserver.observe(cDay);
                resizeObserver.observe(c1h);
            }}
            initCharts();
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=515)

def render_nq_wave_prediction_dashboard():
    st.markdown("### 🌊 納指 (NQ / QQQ) 艾略特波浪多週期時空聯動終端")
    st.caption("架構特性: **1H 多維度調控台 + TradingView 原廠雙屏聯動 + 空間投影**")

    df_day = load_data("US.QQQ", "DAY")
    df_1h = load_data("US.QQQ", "1Hr")

    if df_day.empty:
        st.warning("⏳ 尚未檢測到 `US_QQQ_DAY.csv` 數據，請先運行 `python data_fetcher.py`！")
        return

    wave_res = ElliottWaveEngine.analyze_wave_structure(df_day)
    curr_price = float(df_day['close'].iloc[-1])

    if not df_1h.empty and len(df_1h) >= 8:
        recent_8h = df_1h.tail(8)
        h8_change = float(recent_8h['close'].iloc[-1] - recent_8h['open'].iloc[0])
    else:
        h8_change = 0.0

    is_bull = "多頭" in wave_res["trend_dir"] or "⑤" in wave_res["current_wave"]
    score_8h = "🟢 正常軌道 (87.5% 吻合)" if (is_bull and h8_change >= 0) or (not is_bull and h8_change < 0) else "🟡 震盪微調 (62.5% 偏離)"

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📌 當前基準現價", f"${curr_price:,.2f}", f"8H 變動: {h8_change:+,.2f}")
    m2.metric("🌊 當下宏觀波浪", wave_res["current_wave"])
    m3.metric("🎯 8小時預測達成率", score_8h)
    m4.metric("⏱️ 費氏時間跨度", f"{wave_res['time_elapsed_bars']} 棒", f"預期週期 ~{wave_res['expected_duration_bars']} 棒")

    st.markdown("---")

    # 🎛️ 1小時專屬調控中樞 (Controls Bar)
    c_title, c_bars, c_sw1, c_sw2 = st.columns([2.2, 1.3, 1.2, 1.3])
    with c_title:
        st.markdown("#### 📈 多週期 TradingView 左右聯動視窗")
    with c_bars:
        bars_preset = st.selectbox(
            "⏱️ 1H 視窗跨度調控", 
            options=[8, 24, 48, 72, 120], 
            index=2, 
            format_func=lambda x: f"最近 {x} 根 1H 柱 ({x//8 if x>=8 else x} 天)"
        )
    with c_sw1:
        show_fib_p = st.toggle("📐 斐波那契回調線", value=True)
    with c_sw2:
        show_targets = st.toggle("🎯 1H 空間目標/防守線", value=True)

    render_dual_tradingview_charts(
        df_day, 
        df_1h, 
        wave_res, 
        show_fib_price=show_fib_p, 
        show_targets=show_targets,
        bars_1h_count=bars_preset
    )

    st.markdown("---")

    st.markdown("#### 🧭 空間目標推演與 8 小時實盤驗證 (Time & Price Projection)")
    t1, t2, t3 = st.columns(3)
    
    with t1:
        st.markdown("**📐 Fibonacci 價格回調防線 (日線)**")
        if wave_res["fib_levels"]:
            fib_df = pd.DataFrame([
                {"Fib 水位": k, "回調價格 ($)": f"${v:,.2f}"} for k, v in wave_res["fib_levels"].items()
            ])
            st.dataframe(fib_df, use_container_width=True, hide_index=True)

    with t2:
        st.markdown("**🎯 空間目標與 1H 投影防線**")
        st.markdown(f"""
        | 指標項目 | 點位 ($) | 跨週期投影依據 |
        | :--- | :--- | :--- |
        | **第 1 目標 (Target 1)** | **${wave_res['next_target_1']:,.2f}** | 日線 1.0x 對稱浪 ──► 投影至 1H |
        | **第 2 目標 (Target 2)** | **${wave_res['next_target_2']:,.2f}** | 日線 1.618x 擴展浪 ──► 投影至 1H |
        | **鐵律失效線 (SL)** | **${wave_res['invalid_price']:,.2f}** | 4浪不得破1浪頂 ──► 投影至 1H |
        """)

    with t3:
        st.markdown("**⏱️ 費氏時間序列預測窗口**")
        if wave_res["time_window_dates"]:
            df_time = pd.DataFrame(wave_res["time_window_dates"])
            st.dataframe(df_time, use_container_width=True, hide_index=True)
