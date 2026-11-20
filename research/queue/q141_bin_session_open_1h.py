# -*- coding: utf-8 -*-
"""Q141(docs/244 §1b・64 セル): 他市場オープン直後 1 時間の方向。
8 ペア × 建て {06(フランクフルト 15 時 JST), 07(ロンドン 16 時), 13(NY 22 時), 14(NY 23 時)} UTC × {HIGH, LOW}・保有 1h・月〜金プール。
ロールオーバー帯外なので bid 評価が主、ミッド(2024〜)を併記(docs/367 §4)。使い方: cd research && python3 queue/q141_bin_session_open_1h.py <累積セル数>"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from q_bin_common import *
PAIRS = ["EURUSD", "GBPUSD", "EURGBP", "USDCHF", "EURCHF", "USDJPY", "EURJPY", "GBPJPY"]; HOURS = [6, 7, 13, 14]
if __name__ == "__main__":
    cum = int(sys.argv[1]); rows = []; N = len(PAIRS) * len(HOURS) * 2; alpha = 0.05 / (cum + N); WD = [0, 1, 2, 3, 4]
    for sym in PAIRS:
        for h in HOURS:
            for high in (True, False):
                w = outcomes(sym, None, h, 1, high=high, dows=WD); d = judge(w, 1, alpha)
                d.update(judge_mid(outcomes_mid(sym, None, h, 1, high=high, dows=WD), 1, alpha))
                rows.append(dict(family="session_open_1h", symbol=sym, h_utc=h, dir="HIGH" if high else "LOW", **d))
    finish("Q141", cum, rows, "results/q141_bin_session_open_1h.csv")
