"""
dow_breakdown.py — エッジ別×曜日別 + エッジ別×月別の成績(記述統計・参考)。
曜日別=原資産の各曜日終値→翌終値LONG(コスト込み: FX2pip/指数金5bps)。行名はエッジ名。
月別=各エッジの凍結実装PnLをカレンダー月で集計(2016-2026)。
⚠ 多重比較になるため有意性主張には使わない(正式スキャンは docs/14)。
"""
import importlib.util, json, os
import numpy as np, pandas as pd

def load_mod(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

e13 = load_mod("research/edge13_longhistory_confirm.py", "e13")
e14 = load_mod("research/edge14_breadth_durability.py", "e14")

# ---------- 曜日別(原資産・行名=エッジ名) ----------
def dow_stats(assets, fx, start, end, src="e13"):
    rows = {}
    for w in range(5):
        legs = []
        for a in assets:
            s = e13.daily(a) if src == "e13" else e14.ohlc(a)["close"]
            s = s[(s.index >= start) & (s.index < end)]
            r = s.pct_change().shift(-1)
            c = (2.0*0.01/s) if fx else pd.Series(5e-4, index=s.index)
            d = np.where(s.index.dayofweek == w)[0]
            for i in d:
                if np.isfinite(r.iloc[i]): legs.append(float(r.iloc[i]) - float(c.iloc[i]))
        if not legs: rows[w] = None; continue
        arr = np.array(legs)
        rows[w] = dict(mean_bps=round(arr.mean()*1e4, 2),
                       net_pct=round((np.prod(1+arr)-1)*100, 1), n=len(arr))
    return rows

GROUPS = {
    "v7":              (["USDJPY","EURJPY","GBPJPY"], True, "e13"),
    "v7横展開":         (e14.V7_NEW, True, "e14"),
    "E-Mon":           (["US500","NAS100","GER40"], False, "e13"),
    "E-Mon横展開":      (e14.EMON_NEW, False, "e14"),
    "(参考)XAUUSD":     (["XAUUSD"], False, "e13"),
}
WD = ["月","火","水","木","金"]
out = {"dow": {}, "month": {}}
for label, (g, fx, src) in GROUPS.items():
    out["dow"][label] = {"2016-2026": dow_stats(g, fx, "2016-01-01", "2026-06-01", src),
                         "pre-2016":  dow_stats(g, fx, "1985-01-01", "2016-01-01", src)}

for period in ["2016-2026", "pre-2016"]:
    print(f"\n== 曜日別 {period}: 平均bps/ショット [期間純益%] ==")
    print("| エッジ | " + " | ".join(WD) + " |")
    print("|---|" + "--:|"*5)
    for label in GROUPS:
        r = out["dow"][label][period]
        cells = ["—" if r[w] is None else f"{r[w]['mean_bps']:+.1f} [{r[w]['net_pct']:+.0f}%]" for w in range(5)]
        print(f"| {label} | " + " | ".join(cells) + " |")

# ---------- 月別(エッジPnL・2016-2026) ----------
EDGES = {
    "v7":          e13.v7_proxy(),
    "v7横展開":     e14.monday_legs(e14.V7_NEW, fx=True),
    "E-Mon":       e13.emon(),
    "E-Mon横展開":  e14.monday_legs(e14.EMON_NEW, fx=False),
    "E5":          e13.e5(),
    "v4":          e14.v4_daily_legs(),
    "G3近似(弱)":   e14.fomc_proxy_legs(e14.FOMC_POST),
}
def by_month(s, start="2016-01-01"):
    s = s[s.index >= start]
    return {m: round((float((1+s[s.index.month == m]).prod())-1)*100, 1) for m in range(1, 13)}

for k, s in EDGES.items(): out["month"][k] = by_month(s)
print("\n== 月別(エッジPnL・2016-2026合算 純益%) ==")
print("| 月 | " + " | ".join(EDGES.keys()) + " |")
print("|---|" + "--:|"*len(EDGES))
for m in range(1, 13):
    print(f"| {m}月 | " + " | ".join(f"{out['month'][k][m]:+.1f}" for k in EDGES) + " |")

os.makedirs("research/results", exist_ok=True)
with open("research/results/dow_breakdown.json", "w") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("\n保存: research/results/dow_breakdown.json")
