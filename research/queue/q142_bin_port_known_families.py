# -*- coding: utf-8 -*-
"""Q142(docs/244 §1b・12 セル): こちらで検証済みの家族のバイナリー移植。
1) XAUUSD 木曜 07 JST(= 水曜 22 UTC)→ 翌 06 JST(23h)HIGH = 1
2) US500 / NAS100 / US30: 月曜 07 JST(= 日曜 22 UTC)→ 翌 06 JST(23h)HIGH = 3、月曜 22 時 JST(= 13 UTC)→ 05 時 JST(= 20 UTC・7h)HIGH = 3
3) Roll: USDJPY / EURJPY / GBPJPY / AUDJPY / CADJPY 水曜 20 UTC → 00 UTC(4h)LOW = 5
20〜23 UTC 建て(1・2 の 23h・3)はミッド必須(docs/367 §4)。使い方: cd research && python3 queue/q142_bin_port_known_families.py <累積セル数>"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from q_bin_common import *
if __name__ == "__main__":
    cum = int(sys.argv[1]); rows = []; N = 12; alpha = 0.05 / (cum + N)
    def cell(fam, sym, dow, h, hold, high, roll_band):
        d = judge(outcomes(sym, dow, h, hold, high=high), hold, alpha); d.update(judge_mid(outcomes_mid(sym, dow, h, hold, high=high), hold, alpha))
        d["mid_required"] = roll_band
        if roll_band: d["passed"] = bool(d["passed"] and d["passed_mid"])    # ロールオーバー帯は両方
        rows.append(dict(family=fam, symbol=sym, dow_utc=dow, h_utc=h, hold_h=hold, dir="HIGH" if high else "LOW", **d))
    cell("Thu_XAU_23h", "XAUUSD", 2, 22, 23, True, True)
    for sym in ("US500", "NAS100", "US30"):
        cell("Mon_idx_23h", sym, 6, 22, 23, True, True); cell("Mon_idx_intra_13to20", sym, 0, 13, 7, True, False)
    for sym in ("USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"):
        cell("Wed_Roll_LOW_20to00", sym, 2, 20, 4, False, True)
    finish("Q142", cum, rows, "results/q142_bin_port_known_families.csv")
