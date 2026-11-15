# -*- coding: utf-8 -*-
"""docs/244 Q220(改良系・8 セル・2026-11-15 登録): 月曜の円クロスの時間帯の案を、線による縮小(下 1.0・上 0.5)を掛けた形でやり直す。
時間帯: 配備形 = 4/6/8/10 UTC 建て × 24h。T1 = {0,2,4,6} UTC × 24h。T2 = 07 → 16 UTC 単発。T3 = 4/6/8/10 → 同日 20 UTC。T4 = 4/6/8/10 → +12h。
線: 日足 EMA50・日足 SMA200(月曜より前の最後の確定日足・未計算は 1.0)。4 通貨各 0.25・往復 3 pip。
判定 = 同じ線の縮小を掛けた配備形の時間帯に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。
使い方: cd research && python3 -W ignore queue/q220_mon4_timing_with_tilt.py <累積セル数>   出力: results/q220_mon4_timing_with_tilt.csv"""
import sys, os
from q_common import *
from q147_roll_rate_diff_gate import stats
from q194_mon_own_technical_state_gate import PAIRS
from q216_mon4_ema_state import dist
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END))
TIMING = {"配備形 4/6/8/10 × 24h": [(h, h + 24) for h in (4, 6, 8, 10)], "T1 前倒し 0/2/4/6 × 24h": [(h, h + 24) for h in (0, 2, 4, 6)], "T2 ロンドン時間だけ 07 → 16": [(7, 16)],
          "T3 4/6/8/10 → 同日 20": [(h, 20) for h in (4, 6, 8, 10)], "T4 4/6/8/10 → 12 時間後": [(h, h + 12) for h in (4, 6, 8, 10)]}
def leg(sym, pairs_):
    o = load(sym)["open"]; mons = pd.DatetimeIndex(sorted(set(o.index[o.index.dayofweek == 0].normalize()))); out = None
    for h0, h1 in pairs_:
        t = mons + pd.Timedelta(hours=h0); t2 = mons + pd.Timedelta(hours=h1); ok = t.isin(o.index) & t2.isin(o.index); t, t2 = t[ok], t2[ok]
        r = trades(sym, t, o.reindex(t).values, np.ones(len(t)), o.reindex(t2).values); r.index = r.index.normalize(); out = r if out is None else out.add(r, fill_value=0.0)
    return (out / len(pairs_)).sort_index()
if __name__ == "__main__":
    cum = int(sys.argv[1]); N = 8; L = {(s, k): leg(s, v) for s in PAIRS for k, v in TIMING.items()}; rows = []
    def comp(k, line):
        out = None
        for s in PAIRS:
            x = L[(s, k)]
            if line: d = dist(s, 50 if line == "EMA50" else 200, x.index, "ema" if line == "EMA50" else "sma"); x = x * np.where(d.isna(), 1.0, np.where(d < 0, 1.0, 0.5))
            out = (x * 0.25) if out is None else out.add(x * 0.25, fill_value=0.0)
        return out
    for line in (None, "EMA50", "SMA200"):
        b = comp("配備形 4/6/8/10 × 24h", line); bs = {w: stats(b, a, c) for w, a, c in WIN}
        rows.append(dict(line=line or "縮小なし", timing="配備形 4/6/8/10 × 24h", PRE=bs["前窓"], IS=bs["IS"], OOS=bs["OOS"], cell=False, sharpe_up_3win=None, improved=None))
        for k in list(TIMING)[1:]:
            v = comp(k, line); vs = {w: stats(v, a, c) for w, a, c in WIN}
            rows.append(dict(line=line or "縮小なし", timing=k, PRE=vs["前窓"], IS=vs["IS"], OOS=vs["OOS"], cell=bool(line), sharpe_up_3win=bool(all(vs[w][0] > bs[w][0] for w, _, _ in WIN)), improved=bool(all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN))))
    D = pd.DataFrame(rows); D.to_csv("results/q220_mon4_timing_with_tilt.csv", index=False); pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 300)
    C = D[D.cell]; assert len(C) == N
    print(f"Q220: cells={N} cum_before={cum} cum_after={cum + N} improved={int(C.improved.sum())}/{N}(EMA50 {int(C[C.line == 'EMA50'].improved.sum())}/4・SMA200 {int(C[C.line == 'SMA200'].improved.sum())}/4)  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)")
    print(D.to_string(index=False))
