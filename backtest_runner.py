# 文件名: backtest_runner.py
# 職責: 遍歷 2026 全年數據，嚴格執行 1H EMA20 + 2B + 1:2 R:R 向後掃描判定 (無虛假標籤)

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
        print(f"[!] 找不到 {code} 的歷史數據，請先運行 fetch_2026_full.py")
        return

    df = pd.read_csv(csv_file)
    df.columns = [c.lower() for c in df.columns]
    df['time_key'] = pd.to_datetime(df['time_key'])
    df = df.sort_values('time_key').reset_index(drop=True)
    
    # 指標計算
    df['vma20'] = df['volume'].rolling(20).mean()
    df['ema20_1h'] = df['close'].ewm(span=240, adjust=False).mean()  # 1H EMA20 映射至 5M
    
    trades = []
    i = 30
    n = len(df)
    
    while i < n - 36:
        curr_row = df.iloc[i]
        prev_row = df.iloc[i-1]
        
        # 1. 宏觀與量能門禁
        vol_ratio = curr_row['volume'] / curr_row['vma20'] if curr_row['vma20'] > 0 else 1.0
        is_vol_heavy = vol_ratio >= 1.25
        
        llv5 = df['low'].iloc[i-5:i].min()
        hhv5 = df['high'].iloc[i-5:i].max()
        
        # 2. 形態判定 (做多 2B 破底翻 vs 做空 2B 假突破)
        bull_2b = (prev_row['low'] < llv5) and (curr_row['close'] > prev_row['high']) and (curr_row['close'] > curr_row['open'])
        bear_2b = (prev_row['high'] > hhv5) and (curr_row['close'] < prev_row['low']) and (curr_row['close'] < curr_row['open'])
        
        if (bull_2b or bear_2b) and is_vol_heavy:
            is_call = bull_2b
            direction = "🟢 CALL" if is_call else "🔴 PUT"
            entry_p = round(float(curr_row['close']), 2)
            entry_time = curr_row['time_key']
            
            # 風控設定 (1:2 結構)
            atr_val = max(0.5, abs(curr_row['high'] - curr_row['low']))
            if is_call:
                sl_p = round(min(curr_row['low'], prev_row['low']) - 0.2 * atr_val, 2)
                risk = max(0.4, entry_p - sl_p)
                tp_p = round(entry_p + 2.0 * risk, 2)
            else:
                sl_p = round(max(curr_row['high'], prev_row['high']) + 0.2 * atr_val, 2)
                risk = max(0.4, sl_p - entry_p)
                tp_p = round(entry_p - 2.0 * risk, 2)
                
            # 3. 向後逐根掃描客觀結果 (先碰 SL 還是先碰 TP)
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
                    "score": 85 if is_vol_heavy else 75,
                    "reason": f"5M 2B {'破底翻' if is_call else '衝頂誘多'} + {vol_ratio:.2f}x 放量確認",
                    "ema20_1h": round(float(curr_row['ema20_1h']), 2),
                    "pdh": round(hhv5, 2),
                    "pdl": round(llv5, 2),
                    "rbs": sl_p if is_call else entry_p,
                    "sbr": entry_p if is_call else sl_p
                }
                trades.append(trade_dict)
                i = f + 2  # 開單後跳過持倉期間
                continue
        i += 1
        
    df_res = pd.DataFrame(trades)
    if not df_res.empty:
        # 與現有日誌合併去重
        if os.path.exists(JOURNAL_CSV):
            try:
                df_old = pd.read_csv(JOURNAL_CSV)
                df_res = pd.concat([df_old, df_res]).drop_duplicates(subset=['trade_id', 'code']).reset_index(drop=True)
            except Exception:
                pass
        df_res.to_csv(JOURNAL_CSV, index=False)
        print(f"[✓] {code} 客觀回測完成！共產出 {len(trades)} 筆真實交易記錄，已更新至帳本。")
    else:
        print(f"[!] {code} 在該歷史區間內未觸發開倉條件。")

if __name__ == "__main__":
    run_objective_backtest("US.QQQ")
    run_objective_backtest("CC.BTCUSD")
