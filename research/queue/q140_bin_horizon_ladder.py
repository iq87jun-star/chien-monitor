# -*- coding: utf-8 -*-
"""Q140(docs/244 §1b・48 セル): 既知アノマリーの判定時刻の階段。
A) 月曜 7 時 JST(= 日曜 22 UTC)HIGH の円クロス 6 本 × 保有 {2,3,4,6,8,23}h = 36
B) 毎日 7 時 JST(= 前日 22 UTC・判定日 月〜金)HIGH の 1H 家族 4 本 × 保有 {2,3,4}h = 12
使い方: cd research && python3 queue/q140_bin_horizon_ladder.py <累積セル数>"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from q_bin_common import *
MON = ["EURJPY", "AUDJPY", "NZDJPY", "GBPJPY", "CADJPY", "CHFJPY"]; DAILY = ["EURGBP", "CHFJPY", "EURJPY", "USDCHF"]
if __name__ == "__main__":
    cum = int(sys.argv[1]); rows = []; N = len(MON) * 6 + len(DAILY) * 3; alpha = 0.05 / (cum + N)
    for sym in MON:
        for h in (2, 3, 4, 6, 8, 23):
            w = outcomes(sym, 6, 22, h, high=True); rows.append(dict(family="A_Mon7JST_HIGH", symbol=sym, hold_h=h, **judge(w, h, alpha)))
    for sym in DAILY:
        for h in (2, 3, 4):
            w = outcomes(sym, None, 22, h, high=True, dows=[6, 0, 1, 2, 3]); rows.append(dict(family="B_daily7JST_HIGH", symbol=sym, hold_h=h, **judge(w, h, alpha)))
    # 参考(セルに数えない): 1H と 23H の既知値(別ブランチの再現確認)
    for sym in ("EURJPY", "GBPJPY"):
        w = outcomes(sym, 6, 22, 1, high=True); d = judge(w, 1, alpha); print(f"参考 {sym} Mon 1H: IS WR {d['wr_is']} (BE {d['be']}) OOS {d['wr_oos']}")
    finish("Q140", cum, rows, "results/q140_bin_horizon_ladder.csv")
