# 文件名: strategy_engine.py
# 核心功能: 策略獨立大腦 (形態識別、VPA 放量、均線門禁與 1:2 結構)

import numpy as np
import pandas as pd

class StrategyEngine:
    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or len(df) < 5:
            return df
        
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        
        # 基礎均線與成交量均線
        df['sma20'] = df['close'].rolling(window=min(20, len(df))).mean()
        df['vma20'] = df['volume'].rolling(window=min(20, len(df))).mean()
        df['vol_ratio'] = df['volume'] / df['vma20'].replace(0, 1)
        
        # 多空形態與 2B 判定
        patterns = []
        for i in range(len(df)):
            o = float(df['open'].iloc[i])
            c = float(df['close'].iloc[i])
            h = float(df['high'].iloc[i])
            l = float(df['low'].iloc[i])
            vr = float(df['vol_ratio'].iloc[i])
            
            body = abs(c - o)
            upper_shadow = h - max(o, c)
            lower_shadow = min(o, c) - l
            
            if c > o:
                if vr >= 1.25 and lower_shadow > body * 1.5:
                    patterns.append("[🟢 鐵錘漲 🔨]")
                elif vr >= 1.25:
                    patterns.append("[🟢 大陽衝鋒 🚀]")
                else:
                    patterns.append("[🟢 青陽漲]")
            elif c < o:
                if vr >= 1.25 and upper_shadow > body * 1.5:
                    patterns.append("[🔴 射星跌 🌠]")
                elif vr >= 1.25:
                    patterns.append("[🔴 大陰破位 💥]")
                else:
                    patterns.append("[🔴 紅陰跌]")
            else:
                patterns.append("[⚪ 青十字 ⚖️]")
                
        df['pattern_label'] = patterns
        return df

    @staticmethod
    def evaluate_signal(row: pd.Series) -> dict:
        vr = float(row.get('vol_ratio', 1.0))
        c = float(row.get('close', 0.0))
        
        if vr >= 1.25 and "🟢" in str(row.get('pattern_label', '')):
            return {
                "action": "🟢 BUY CALL",
                "score": 90,
                "reason": f"量能放大 {vr:.2f}x 且多頭形態確認",
                "entry": c,
                "sl": round(c * 0.998, 2),
                "tp": round(c * 1.004, 2)
            }
        elif vr >= 1.25 and "🔴" in str(row.get('pattern_label', '')):
            return {
                "action": "🔴 BUY PUT",
                "score": 90,
                "reason": f"量能放大 {vr:.2f}x 且空頭形態確認",
                "entry": c,
                "sl": round(c * 1.002, 2),
                "tp": round(c * 0.996, 2)
            }
        else:
            return {
                "action": "⚪ 觀望等待",
                "score": 50,
                "reason": "常規波動，量能未達 1.25x 門禁",
                "entry": c,
                "sl": round(c * 0.998, 2),
                "tp": round(c * 1.004, 2)
            }
