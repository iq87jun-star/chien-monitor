# -*- coding: utf-8 -*-
"""docs/365 Q139(改良系・8 セル): Mon4 → Mon5。月曜の円クロス LONG に「週明け 日曜 22 UTC(月曜 07:00 JST・東京オープン)」のショットを足す/h4 と置き換える。
決済は月曜 20 UTC(21 UTC のスプレッド帯を避ける・docs/233)。外部提案(別ブランチ claude/zaption-check-m776m7)の照合 docs/365 から登録(ユーザー「登録」2026-10-20)。
基準: docs/244 §1 改良系 — IS(2021-10〜2024-12)・OOS(2025-01〜)の両方で Sharpe 改善 かつ 最悪月が悪化しない。ベース = 既存 Mon4(h4/6/8/10 UTC 建て → 24h 後決済・等ウェイト)。
セル: 4 通貨(EURJPY / AUDJPY / NZDJPY / GBPJPY)× {A: h4 を Sun22→Mon20 に置換, B: Sun22→Mon20 を 5 本目として追加}。
H1 Dukascopy・コストは q_common(FX 往復 3pip)。紙上フォワード用に shot_sun22() を paper_forward.CANDIDATES("MonSun22")から呼ぶ。
使い方: cd research && python3 queue/q139_mon_sun22.py <累積セル数>"""
import sys, os
from q_common import *
PAIRS = ["EURJPY", "AUDJPY", "NZDJPY", "GBPJPY"]; EXIT_H = 20

def shot_sun22(sym, exit_h=EXIT_H):
    """日曜 22 UTC 建て(LONG)→ 月曜 exit_h UTC 決済。index は建て日(日曜)を月曜に正規化。"""
    df = load(sym); o = df["open"]; t = o.index[(o.index.dayofweek == 6) & (o.index.hour == 22)]
    t_out = pd.DatetimeIndex([x.normalize() + pd.Timedelta(hours=24 + exit_h) for x in t])
    r = trades(sym, t, o.reindex(t).values, np.ones(len(t)), o.reindex(t_out).values); r.index = (r.index + pd.Timedelta(days=1)).normalize(); return r

def shot_mon(sym, h_in):
    df = load(sym); o = df["open"]; t = o.index[(o.index.dayofweek == 0) & (o.index.hour == h_in)]
    r = trades(sym, t, o.reindex(t).values, np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=24)).values); r.index = r.index.normalize(); return r

def mon4(sym, hours=(4, 6, 8, 10)):
    return pd.concat([shot_mon(sym, h) for h in hours], axis=1).mean(axis=1).dropna()

def stats(s, a, b):
    x = s[(s.index >= a) & (s.index <= b)]; m = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
    return (round(float(x.mean() / x.std() * np.sqrt(52)), 2) if len(x) > 5 and x.std() > 0 else 0.0), round(float(m.min()) * 100, 2), round(float((1 + x).prod() - 1) * 100, 1)

def improved(b, v):
    bi, bo, gi, go = stats(b, IS0, IS1), stats(b, OOS0, END), stats(v, IS0, IS1), stats(v, OOS0, END)
    return dict(base_IS=bi, var_IS=gi, base_OOS=bo, var_OOS=go, ok=bool(gi[0] > bi[0] and go[0] > bo[0] and gi[1] >= bi[1] and go[1] >= bo[1]))

if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q139", cum, len(PAIRS) * 2, "results/q139_mon_sun22.csv"); rows = []
    for sym in PAIRS:
        base_ = mon4(sym); s22 = shot_sun22(sym)
        varA = pd.concat([s22, shot_mon(sym, 6), shot_mon(sym, 8), shot_mon(sym, 10)], axis=1).mean(axis=1).dropna()
        varB = pd.concat([s22] + [shot_mon(sym, h) for h in (4, 6, 8, 10)], axis=1).mean(axis=1).dropna()
        for tag, v in (("A_replace_h4", varA), ("B_add_5th", varB)):
            R.add("Mon5 週明けショット(改良系)", sym, f"Sun22→Mon20 {tag}(ベース Mon4 h4/6/8/10 24h)", v)
            d = improved(base_, v); rows.append(dict(symbol=sym, variant=tag, n_in=int(((s22.index >= IS0) & (s22.index <= IS1)).sum()), **d))
    R.finish(); pd.set_option("display.width", 300); D = pd.DataFrame(rows); D.to_csv("results/q139_mon_sun22_levels.csv", index=False)
    print("\n== Q139 改良判定(Sharpe, 最悪月 %, 累積 %)==\n" + D.to_string(index=False)); print("\n改良成立:", int(D.ok.sum()), "/ 8")
