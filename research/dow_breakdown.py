"""
dow_breakdown.py — 資産バスケット別×曜日別の成績(記述統計・参考)。
各曜日の終値→翌営業日終値LONG・コスト込み(FX=2pip, 指数/金=5bps)。edge13/14キャッシュを再利用。
⚠ 5曜日×バスケットの多重比較になるため有意性主張には使わない(docs/14のDOWスキャンが正式版)。
"""
import importlib.util, json, os
import numpy as np, pandas as pd

def load_mod(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

e13 = load_mod("research/edge13_longhistory_confirm.py", "e13")
e14 = load_mod("research/edge14_breadth_durability.py", "e14")

def dow_stats(assets, fx, start, end, src="e13"):
    """曜日別: 平均bps/ショット(コスト込み)と純益%。"""
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
        net = (np.prod(1+arr)-1)*100
        rows[w] = dict(mean_bps=round(arr.mean()*1e4, 2), net_pct=round(net, 1), n=len(arr))
    return rows

GROUPS = {
    "円3クロス(v7原資産)":   (["USDJPY","EURJPY","GBPJPY"], True, "e13"),
    "JPY新4クロス":          (e14.V7_NEW, True, "e14"),
    "株指3(E-Mon原資産)":    (["US500","NAS100","GER40"], False, "e13"),
    "株指新3(JP/UK/FR)":     (e14.EMON_NEW, False, "e14"),
    "金(XAUUSD)":            (["XAUUSD"], False, "e13"),
}
WD = ["月","火","水","木","金"]
out = {}
for label, (g, fx, src) in GROUPS.items():
    out[label] = {"2016-2026": dow_stats(g, fx, "2016-01-01", "2026-06-01", src),
                  "pre-2016":  dow_stats(g, fx, "1985-01-01", "2016-01-01", src)}

for period in ["2016-2026", "pre-2016"]:
    print(f"\n== {period} 平均bps/ショット(コスト込み)・[10年/期間 純益%] ==")
    print("| バスケット | " + " | ".join(WD) + " |")
    print("|---|" + "--:|"*5)
    for label in GROUPS:
        r = out[label][period]
        cells = []
        for w in range(5):
            v = r[w]
            cells.append("—" if v is None else f"{v['mean_bps']:+.1f} [{v['net_pct']:+.0f}%]")
        print(f"| {label} | " + " | ".join(cells) + " |")

os.makedirs("research/results", exist_ok=True)
with open("research/results/dow_breakdown.json", "w") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("\n保存: research/results/dow_breakdown.json")
