# -*- coding: utf-8 -*-
"""Q143(docs/244 §1b・1 セル・ユーザー「登録」2026-10-21): バイナリー Roll — 水曜 20→00 UTC(木曜 05→09 JST)円クロス LOW の家族プール。
USDJPY / EURJPY / GBPJPY / AUDJPY / CADJPY の勝敗を 1 本に連結して判定(docs/368 §3 の提案。仮説の単位を銘柄 → 家族に変えた別セル。基準は §1b のまま)。
20 UTC 建てはロールオーバー帯なのでミッド(2024〜)も必須(docs/367 §4)。使い方: cd research && python3 queue/q143_bin_roll_family_pool.py <累積セル数>"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from q_bin_common import *
PAIRS = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"]
if __name__ == "__main__":
    cum = int(sys.argv[1]); alpha = 0.05 / (cum + 1)
    w = pd.concat([outcomes(s, 2, 20, 4, high=False) for s in PAIRS]).sort_index()
    wm = pd.concat([x for x in (outcomes_mid(s, 2, 20, 4, high=False) for s in PAIRS) if x is not None]).sort_index()
    d = judge(w, 4, alpha); d.update(judge_mid(wm, 4, alpha)); d["mid_required"] = True; d["passed"] = bool(d["passed"] and d["passed_mid"])
    # 参考: 前窓を年別に(前窓 WR > BE の条件がどの年で崩れるか)
    pre = w[(w.index >= PRE0) & (w.index < IS0)]; by = pre.groupby(pre.index.year).agg(["count", "mean"]); by["mean"] = (by["mean"] * 100).round(1)
    print("前窓 年別 n / WR:\n" + by.to_string())
    finish("Q143", cum, [dict(family="Wed_Roll_LOW_pool5", symbol="+".join(PAIRS), h_utc=20, hold_h=4, dir="LOW", **d)], "results/q143_bin_roll_family_pool.csv")
