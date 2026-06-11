"""
yearly_breakdown.py — 全エッジの年度別成績(記述統計・参考表示用)。
edge13/edge14 の凍結実装をそのまま再利用(新しい主張・最適化なし)。
v7/E-Mon/E5=edge13正準窓 / v4=edge14逐語移植 / S-Jul=7月US500+NAS100 / G3=日足近似(弱・注記必須)。
"""
import importlib.util, os, json
import numpy as np, pandas as pd

def load_mod(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

e13 = load_mod("research/edge13_longhistory_confirm.py", "e13")
e14 = load_mod("research/edge14_breadth_durability.py", "e14")

def yearly(s):
    out = {}
    for y in sorted(set(s.index.year)):
        b = s[s.index.year == y]
        out[int(y)] = round((float((1+b).prod())-1)*100, 1)
    return out

def sjul():
    legs = {}
    for a in ["US500", "NAS100"]:
        d = e13.daily(a); m = d.groupby(d.index.to_period("M")).last()
        r = m.pct_change()
        for p, v in r.items():
            if p.month == 7 and np.isfinite(v):
                legs.setdefault(p.year, []).append(v - 5e-4)
    return {y: round(float(np.mean(v))*100, 1) for y, v in sorted(legs.items())}

series = {
    "v7(円月曜3クロス)":  e13.v7_proxy(),
    "v7新4クロス(H14c)":  e14.monday_legs(e14.V7_NEW, fx=True),
    "E-Mon(株指月曜)":    e13.emon(),
    "E-Mon新3指数(H14d)": e14.monday_legs(e14.EMON_NEW, fx=False),
    "E5(多資産TSMOM)":    e13.e5(),
    "v4(k≥4合議)":        e14.v4_daily_legs(),
    "G3近似(日足・弱)":   e14.fomc_proxy_legs(e14.FOMC_PRE + e14.FOMC_POST),
}
tab = {k: yearly(s) for k, s in series.items()}
tab["S-Jul(7月のみ)"] = sjul()

years = list(range(2016, 2027))
cols = list(tab.keys())
print("年度別純益%(2016-2026・素サイズ・Yahoo近似)")
print("| 年 | " + " | ".join(cols) + " |")
print("|---|" + "--:|"*len(cols))
for y in years:
    print(f"| {y} | " + " | ".join(str(tab[c].get(y, "—")) for c in cols) + " |")

print("\nE5 単独の長期(2001-2015):")
print({y: v for y, v in tab["E5(多資産TSMOM)"].items() if y < 2016})
print("\nv4 参考pre-2016(現行レジーム外・5年毎は docs/86):")
print({y: v for y, v in tab["v4(k≥4合議)"].items() if 2010 <= y < 2016})

os.makedirs("research/results", exist_ok=True)
with open("research/results/yearly_breakdown.json", "w") as f:
    json.dump(tab, f, ensure_ascii=False, indent=1)
print("\n保存: research/results/yearly_breakdown.json")
