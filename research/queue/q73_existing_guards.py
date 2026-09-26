# -*- coding: utf-8 -*-
"""docs/312 Q73(F30): 既存ガードの検証。a) 年末年始フィルター(12/20〜1/3): Mon7・Roll5 × {該当のみ, 除外(改良系)} = 4。
b) スプレッド上位 10%(Dukascopy H1 の ask−bid・月曜 04:00 UTC 始値・ペア別 IS 90 分位): Mon7 × {のみ, 除外(改良系)} = 2。計 6 セル。"""
import sys, os
from q_common import *
from q_cal import mon7, improved
from q20_wed_swap_carry import rate_series
base.DATA = os.path.join(ROOT, "data_202609")
def yearend(t): return (t.month == 12 and t.day >= 20) or (t.month == 1 and t.day <= 3)
M7 = mon7(); R5 = None
for sym in ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"]:
    df = load(sym); o = df["open"]; days = pd.DatetimeIndex(sorted(set(df.index.normalize()))); carry = rate_series(sym[:3], days) - rate_series("JPY", days)
    t = o.index[(o.index.dayofweek == 2) & (o.index.hour == 20)]; cy = carry.reindex(t.normalize()).values; t = t[(cy >= 1.0) & ~np.isnan(cy)]
    r = trades(sym, t, o.reindex(t).values, -np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=4)).values); r.index = r.index.normalize(); r = r / 5
    R5 = r if R5 is None else R5.add(r, fill_value=0)
cum = int(sys.argv[1]); R = Runner("Q73", cum, 6, "results/q73_existing_guards.csv"); imp = []
for nm, s in (("Mon7", M7), ("Roll5", R5)):
    sel = pd.Series([yearend(t) for t in s.index], index=s.index)
    R.add("年末年始 12/20-1/3 のみ", nm, "既存フィルター期間", s[sel]); ex = s[~sel]; R.add("年末年始 除外(改良系)", nm, "既存フィルター", ex)
    imp.append(dict(cell=f"{nm} 年末年始", n=int(sel.sum()), mean_sel=round(float(s[sel].mean()) * 1e4, 2), mean_rest=round(float(s[~sel].mean()) * 1e4, 2), **improved(s, ex)))
# スプレッド
SP = {}
for p in base.MON_FX:
    b = load(p); a = pd.read_csv(f"data_dukascopy/{p}_hour_ask.csv.gz"); a["t"] = pd.to_datetime(a["timestamp"]); a = a.set_index("t").sort_index(); a = a[~a.index.duplicated(keep="last")]
    t = b.index[(b.index.dayofweek == 0) & (b.index.hour == 4)]; sp = (a["open"].reindex(t) - b["open"].reindex(t)) / base.pip_size(p); SP[p] = pd.Series(sp.values, index=t.normalize()).dropna()
thr = {p: SP[p][(SP[p].index >= IS0) & (SP[p].index <= IS1)].quantile(0.9) for p in base.MON_FX}
wide = pd.Series([any((t in SP[p].index) and SP[p][t] > thr[p] for p in base.MON_FX) for t in M7.index], index=M7.index)
R.add("スプレッド上位10% のみ", "Mon7", "いずれかのペアで 04:00 スプレッド > IS 90分位", M7[wide]); exw = M7[~wide]; R.add("スプレッド上位10% 除外(改良系)", "Mon7", "該当月曜を建てない", exw)
imp.append(dict(cell="Mon7 スプレッド上位10%", n=int(wide.sum()), mean_sel=round(float(M7[wide].mean()) * 1e4, 2), mean_rest=round(float(M7[~wide].mean()) * 1e4, 2), **improved(M7, exw)))
print("IS 90分位スプレッド(pip):", {p: round(float(v), 2) for p, v in thr.items()})
R.finish(); pd.set_option("display.width", 300); print("\n== Q73 ==\n" + pd.DataFrame(imp).to_string(index=False))
