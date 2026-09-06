# 文件名: backtest_runner.py
# 核心職責: 【真實客觀回測引擎】修正 2B 波段極值算法 + 1H EMA20 宏觀門禁 + 1:2 向後掃描客觀判定

import os
import sys
import pandas as pd
import numpy as np

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MARKET_DATA_DIR = os.path.join(CURRENT_DIR, 'market_data')
JOURNAL_CSV = os.path.join(MARKET_DATA_DIR, 'strategy_live_journal.csv')

def run_objective_backtest(code: str = "US.QQQ"):
    clean_code = code.replace('.', '_')
    csv_file = os.path.join(MARKET_DATA_DIR, f"{clean_code}_5M_2026.csv")
    if not os.path.exists(csv_file):
        csv_file = os.path.join(MARKET_DATA_DIR, f"{clean_code}_5M.csv")
        
    if not os.path.exists(csv_file):
        print(f"[!] 找不到 {code} 的歷史數據檔案，請先運行 fetch_2026_full.py 拉取數據。")
        return

    print(f"\n[*] 正在加載數據源: {csv_file}")
    df = pd.read_csv(csv_file)
    df.columns = [c.lower() for c in df.columns]
    df['time_key'] = pd.to_datetime(df['time_key'])
    df = df.sort_values('time_key').reset_index(drop=True)
    
    # 確保數值格式
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col in df.columns:
            df[col] = df[col].astype(float)
            
    print(f"[*] 成功加載 {len(df)} 根真實 5M K線 (時間區間: {df['time_key'].iloc[0]} 至 {df['time_key'].iloc[-1]})")

    # 技術指標計算
    df['vma20'] = df['volume'].rolling(20).mean().fillna(df['volume'])
    df['ema20_1h'] = df['close'].ewm(span=240, adjust=False).mean()  # 1H EMA20 映射
    
    trades = []
    lookback = 12  # 過去 1 小時 (12 根 5M) 的局部波段高低點
    i = lookback + 2
    n = len(df)
    
    while i < n - 18:
        curr = df.iloc[i]
        prev = df.iloc[i-1]
        
        # 1. 過去 1 小時的波段極值 (排除 curr 與 prev，徹底解決數學矛盾)
        swing_low = df['low'].iloc[i-lookback:i-1].min()
        swing_high = df['high'].iloc[i-lookback:i-1].max()
        
        # 2. 量能驗證
        vol_ratio = curr['volume'] / curr['vma20'] if curr['vma20'] > 0 else 1.0
        is_vol_valid = vol_ratio >= 1.15  # 放量確認
        
        # 3. 2B 形態判定
        # 做多 2B: 曾跌破 swing_low，但當根收盤強勢拉回 swing_low 之上且收陽
        bull_2b = (min(curr['low'], prev['low']) < swing_low) and (curr['close'] > swing_low) and (curr['close'] > curr['open'])
        # 做空 2B: 曾衝破 swing_high，但當根收盤跌回 swing_high 之下且收陰
        bear_2b = (max(curr['high'], prev['high']) > swing_high) and (curr['close'] < swing_high) and (curr['close'] < curr['open'])
        
        # 4. 宏觀趨勢門禁
        # 順勢優先：價格在 1H EMA20 之上偏多，之下偏空
        ema_val = curr['ema20_1h']
        trend_match = (bull_2b and curr['close'] >= ema_val * 0.995) or (bear_2b and curr['close'] <= ema_val * 1.005)
        
        if (bull_2b or bear_2b) and is_vol_valid and trend_match:
            is_call = bull_2b
            direction = "🟢 CALL" if is_call else "🔴 PUT"
            entry_p = round(float(curr['close']), 2)
            entry_time = curr['time_key']
            
            # 結構風控點位 (1:2 R:R)
            step_atr = max(0.4 if entry_p < 1000 else 8.0, abs(curr['high'] - curr['low']))
            if is_call:
                sl_p = round(min(curr['low'], prev['low']) - 0.1 * step_atr, 2)
                risk = max(0.3 if entry_p < 1000 else 6.0, entry_p - sl_p)
                tp_p = round(entry_p + 2.0 * risk, 2)
            else:
                sl_p = round(max(curr['high'], prev['high']) + 0.1 * step_atr, 2)
                risk = max(0.3 if entry_p < 1000 else 6.0, sl_p - entry_p)
                tp_p = round(entry_p - 2.0 * risk, 2)
                
            # 5. 向後客觀掃描價格走勢 (先碰 SL 還是 TP)
            exit_time = None
            exit_price = None
            status = "TIMEOUT"
            net_r = 0.0
            
            for f in range(i + 1, min(i + 36, n)):
                f_row = df.iloc[f]
                if is_call:
                    if f_row['low'] <= sl_p:
                        status = "LOSS_SL"
                        net_r = -1.0
                        exit_price = sl_p
                        exit_time = f_row['time_key']
                        break
                    elif f_row['high'] >= tp_p:
                        status = "WIN_TP"
                        net_r = 2.0
                        exit_price = tp_p
                        exit_time = f_row['time_key']
                        break
                else:
                    if f_row['high'] >= sl_p:
                        status = "LOSS_SL"
                        net_r = -1.0
                        exit_price = sl_p
                        exit_time = f_row['time_key']
                        break
                    elif f_row['low'] <= tp_p:
                        status = "WIN_TP"
                        net_r = 2.0
                        exit_price = tp_p
                        exit_time = f_row['time_key']
                        break
                        
            if status in ["WIN_TP", "LOSS_SL"]:
                t_date = entry_time.strftime('%Y-%m-%d')
                t_month = entry_time.strftime('%Y-%m')
                t_time_et = entry_time.strftime('%H:%M')
                t_exit_et = exit_time.strftime('%H:%M') if exit_time else "--:--"
                
                trade_dict = {
                    "trade_id": f"#{entry_time.strftime('%Y%m%d_%H%M')}",
                    "code": code,
                    "date": t_date,
                    "month": t_month,
                    "time_et": t_time_et,
                    "exit_time_et": t_exit_et,
                    "direction": direction,
                    "strategy": "Strategy 1",
                    "entry": entry_p,
                    "sl": sl_p,
                    "tp": tp_p,
                    "exit_price": exit_price,
                    "status": status,
                    "net_r": net_r,
                    "score": 85 if vol_ratio >= 1.5 else 78,
                    "reason": f"5M 2B {'破底翻' if is_call else '衝頂誘多'} (刺穿波段極值拉回) + {vol_ratio:.2f}x 放量確認",
                    "ema20_1h": round(float(curr['ema20_1h']), 2),
                    "pdh": round(swing_high, 2),
                    "pdl": round(swing_low, 2),
                    "rbs": sl_p if is_call else entry_p,
                    "sbr": entry_p if is_call else sl_p
                }
                trades.append(trade_dict)
                i = f + 1  # 跳過持倉期
                continue
        i += 1
        
    df_res = pd.DataFrame(trades)
    if not df_res.empty:
        # 合併至帳本 CSV
        if os.path.exists(JOURNAL_CSV):
            try:
                df_old = pd.read_csv(JOURNAL_CSV)
                df_res = pd.concat([df_old, df_res]).drop_duplicates(subset=['trade_id', 'code']).reset_index(drop=True)
            except Exception:
                pass
        df_res.to_csv(JOURNAL_CSV, index=False)
        wins = len(df_res[df_res['net_r'] > 0])
        total = len(df_res)
        wr = (wins / total) * 100 if total > 0 else 0
        print(f"=======================================================")
        print(f"🎉 [客觀回測成功] {code} 總計捕捉到 {len(trades)} 筆真實交易訊號！")
        print(f"• 歷史勝率: {wr:.1f}% ({wins}勝 / {total-wins}負)")
        print(f"• 數據庫已更新至: {JOURNAL_CSV}")
        print(f"=======================================================\n")
    else:
        print(f"[!] {code} 在現有切片數據中未觸發開倉條件。")

if __name__ == "__main__":
    run_objective_backtest("US.QQQ")
    run_objective_backtest("CC.BTCUSD")
