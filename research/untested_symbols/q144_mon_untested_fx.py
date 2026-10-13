# -*- coding: utf-8 -*-
"""Q144(新規 8 セル・結果前に固定): Mon 効果(配備 Mon4 と同形 = 月曜 4/6/8/10 UTC の 4 ショット・各 24h・平均)を未検証の通貨に。
仮説: 月曜は安全通貨(JPY・CHF)が売られ、高金利通貨が買われる。セル: EURCHF / GBPCHF / CADCHF LONG(CHF 売り)・AUDCAD / NZDCAD / AUDNZD LONG(対照)・USDMXN / USDZAR SHORT(新興国通貨買い)。
コスト q_common(FX 3 pip・保守)。窓 PRE 2016〜2021-09 / IS 2021-10〜2024 / OOS 2025〜。標準 = IS p < 0.05/9,776・OOS > 0・PRE 勝率 ≥ 50%。Mon4(GBPJPY/EURJPY/AUDJPY/USDJPY 同形)との週次相関も出す。"""
from q_common import *
def mon4shot(sym, d):
    o = load(sym)["open"]; parts = []
    for h in (4, 6, 8, 10):
        t = o.index[(o.index.dayofweek == 0) & (o.index.hour == h)]
        r = trades(sym, t, o.reindex(t).values, np.full(len(t), d), o.reindex(t + pd.Timedelta(hours=24)).values); r.index = r.index.normalize(); parts.append(r)
    return pd.concat(parts, axis=1).mean(axis=1).dropna()
ref = pd.concat([mon4shot(s, 1) for s in ["GBPJPY", "EURJPY", "AUDJPY", "USDJPY"]], axis=1).mean(axis=1)
cells = [("EURCHF", 1), ("GBPCHF", 1), ("CADCHF", 1), ("AUDCAD", 1), ("NZDCAD", 1), ("AUDNZD", 1), ("USDMXN", -1), ("USDZAR", -1)]
rows = []
for s, d in cells:
    r = mon4shot(s, d)
    def sh(a, b):
        x = r[(r.index >= a) & (r.index <= b)]; return round(float(x.mean() / x.std() * np.sqrt(52)), 2) if len(x) > 10 else np.nan
    sp, si, so = st(r, PRE0, IS0), st(r, IS0, IS1), st(r, OOS0, END); j = r.index.intersection(ref.index)
    rows.append(dict(cell=f"Mon4 形 {s} {'LONG' if d > 0 else 'SHORT'}", n=len(r), pre_rate=sp["rate"], pre_bps=sp["mean"], pre_sh=sh(PRE0, IS0),
                     is_plus=f"{si['plus']}/{si['n']}", is_bps=si["mean"], is_p=round(si["p"], 4), is_sh=sh(IS0, IS1), oos_plus=f"{so['plus']}/{so['n']}", oos_bps=so["mean"], oos_sh=sh(OOS0, END),
                     corr_mon4=round(float(np.corrcoef(r[j], ref[j])[0, 1]), 2), sign3=bool(sp["mean"] > 0 and si["mean"] > 0 and so["mean"] > 0),
                     std_pass=bool(si["p"] < 0.05 / 9776 and so["mean"] > 0 and sp["rate"] >= 0.5)))
R = pd.DataFrame(rows); pd.set_option("display.width", 260); print(R.to_string(index=False)); R.to_csv("results/q144_mon_untested_fx.csv", index=False)
x = ref; print("参照 Mon4 円クロス:", {k: round(float(x[(x.index >= a) & (x.index <= b)].mean() * 1e4), 2) for k, (a, b) in {"PRE": (PRE0, IS0), "IS": (IS0, IS1), "OOS": (OOS0, END)}.items()}, "bps")
