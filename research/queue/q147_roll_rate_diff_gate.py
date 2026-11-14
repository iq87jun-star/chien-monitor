# -*- coding: utf-8 -*-
"""docs/244 Q147(週次アイデア束 #1・6 セル・改良系): Roll(水曜 20→00 UTC 円クロス 5 本 SHORT・等分)の停止条件 = 金利差ゲート。
docs/369: Roll は 2016〜17・2021 で逆向き、2018〜19・2022〜 で強い(金利差仮説)。
ベース = ゲートなし(EA の実装どおり毎週水曜に 5 本)。変形 = 金利差 < 閾値の週は建てない(その本は 0)。
 A「5 本等分」: 日米金利差 = FRED DGS2(米 2 年・日次)− 日本の政策金利(q20 の RATES。日本 2 年国債は FRED/Yahoo に無いので政策金利で代用)を 5 本共通に適用
 B「本数別」: 各通貨の政策金利 − 日本の政策金利(q20 RATES・docs/275 の研究系列と同じ定義)を本ごとに適用
閾値 {1.0, 1.5, 2.0}% × {A, B} = 6 セル。判定 = docs/244 §1 改良系: IS(2021-10〜2024-12)・OOS(2025-01〜)の両方で Sharpe 改善 かつ 最悪月が悪化しない。前窓(2016〜2021-09)は参考。
コスト往復 3 pip(q_common)。使い方: cd research && python3 queue/q147_roll_rate_diff_gate.py <累積セル数>"""
import sys, os
from q_common import *
from q20_wed_swap_carry import rate_series
PAIRS = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"]; THR = (1.0, 1.5, 2.0)

def dgs2():
    d = pd.read_csv("data_ext/dgs2_fred.csv"); d.columns = ["date", "v"]; d["date"] = pd.to_datetime(d["date"]); d["v"] = pd.to_numeric(d["v"], errors="coerce")
    return d.set_index("date")["v"].ffill()

def leg(sym):
    """水曜 20 UTC 建て SHORT → 00 UTC 決済(全週)。index = 建て日(水曜)に正規化。"""
    o = load(sym)["open"]; t = o.index[(o.index.dayofweek == 2) & (o.index.hour == 20)]
    r = trades(sym, t, o.reindex(t).values, -np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=4)).values); r.index = r.index.normalize(); return r

def family(legs, gates):
    """5 本の等分(ゲートで外れた本は 0)。gates[sym] = 建て日 → bool。"""
    df = pd.DataFrame({s: legs[s] * gates[s].reindex(legs[s].index).fillna(False).astype(float) for s in PAIRS}).fillna(0.0)
    return df.sum(axis=1) / len(PAIRS)

def stats(s, a, b):
    x = s[(s.index >= a) & (s.index <= b)]; m = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
    return (round(float(x.mean() / x.std() * np.sqrt(52)), 2) if len(x) > 5 and x.std() > 0 else 0.0), round(float(m.min()) * 100, 2), round(float((1 + x).prod() - 1) * 100, 1), int((x != 0).sum())

def improved(b, v):
    bi, bo, gi, go = stats(b, IS0, IS1), stats(b, OOS0, END), stats(v, IS0, IS1), stats(v, OOS0, END)
    return dict(base_IS=bi, var_IS=gi, base_OOS=bo, var_OOS=go, base_PRE=stats(b, PRE0, IS0), var_PRE=stats(v, PRE0, IS0), ok=bool(gi[0] > bi[0] and go[0] > bo[0] and gi[1] >= bi[1] and go[1] >= bo[1]))

if __name__ == "__main__":
    cum = int(sys.argv[1]); N = 6; legs = {s: leg(s) for s in PAIRS}; days = pd.DatetimeIndex(sorted(set().union(*[set(legs[s].index) for s in PAIRS])))
    us = dgs2().reindex(days, method="ffill"); jp = rate_series("JPY", days); diff_us = us - jp
    pol = {s: rate_series(s[:3], days) - jp for s in PAIRS}
    base = family(legs, {s: pd.Series(True, index=days) for s in PAIRS}); rows = []
    for thr in THR:
        gA = {s: (diff_us >= thr) for s in PAIRS}; gB = {s: (pol[s] >= thr) for s in PAIRS}
        for tag, g in (("A_5本等分_日米", gA), ("B_本数別_通貨別", gB)):
            v = family(legs, g); d = improved(base, v); rows.append(dict(thr=thr, gate=tag, **d))
    R = pd.DataFrame(rows); R.to_csv("results/q147_roll_rate_diff_gate.csv", index=False); pd.set_option("display.width", 320)
    print(f"Q147: cells={N} cum_before={cum} cum_after={cum+N} 改良成立={int(R.ok.sum())}/{N}")
    print("(Sharpe, 最悪月 %, 累積 %, 取引週数)"); print(R.to_string(index=False))
    print("\n日米金利差(DGS2 − 日本政策金利)の年平均:", {y: round(float(diff_us[diff_us.index.year == y].mean()), 2) for y in range(2016, 2027)})
