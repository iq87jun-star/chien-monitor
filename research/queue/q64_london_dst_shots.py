# -*- coding: utf-8 -*-
"""docs/306 Q64(F21): ロンドン時間に合わせた季節分解。Mon7 × {英国夏時間, 冬時間}(診断・新規 2)+ Mon4 / Mon2 のショット時刻をロンドン現地で固定
{05,07,09,11 ロンドン(= 夏 UTC 4/6/8/10・冬 UTC 5/7/9/11), 04,06,08,10 ロンドン(= 夏 UTC 3/5/7/9・冬 4/6/8/10)} 改良系 4 = 6 セル。使い方: python3 queue/q64_london_dst_shots.py <累積>"""
import sys, os
from q_common import *
from q_cal import mon7, improved
base.DATA = os.path.join(ROOT, "data_202609")
def bst(ts):   # 英国夏時間: 3 月最終日曜 01:00 UTC 〜 10 月最終日曜 01:00 UTC(日付単位で近似)
    y = ts.year; mar = max(d for d in pd.date_range(f"{y}-03-25", f"{y}-03-31") if d.dayofweek == 6); oct_ = max(d for d in pd.date_range(f"{y}-10-25", f"{y}-10-31") if d.dayofweek == 6)
    return mar <= ts.normalize() < oct_
def shots_local(sym, local_hours):
    df = load(sym); o = df["open"]; out = None
    mon = o.index[(o.index.dayofweek == 0)]
    for lh in local_hours:
        t = pd.DatetimeIndex([x for x in mon if x.hour == (lh - 1 if bst(x) else lh)])
        r = trades(sym, t, o.reindex(t).values, np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=24)).values) / len(local_hours); r.index = r.index.normalize()
        out = r if out is None else out.add(r, fill_value=0)
    return out
def shots_utc(sym, hours):
    df = load(sym); o = df["open"]; out = None
    for h in hours:
        t = o.index[(o.index.dayofweek == 0) & (o.index.hour == h)]; r = trades(sym, t, o.reindex(t).values, np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=24)).values) / len(hours); r.index = r.index.normalize()
        out = r if out is None else out.add(r, fill_value=0)
    return out
cum = int(sys.argv[1]); R = Runner("Q64", cum, 6, "results/q64_london_dst_shots.csv")
M7 = mon7(); sel = pd.Series([bst(t) for t in M7.index], index=M7.index)
R.add("Mon7 英国夏時間のみ", "Mon7", "3月最終日曜〜10月最終日曜", M7[sel]); R.add("Mon7 英国冬時間のみ", "Mon7", "それ以外", M7[~sel])
print(f"Mon7 夏時間 平均 {M7[sel].mean()*1e4:.2f} bps (n={int(sel.sum())}) / 冬時間 {M7[~sel].mean()*1e4:.2f} bps (n={int((~sel).sum())})")
W = {"Mon4": {"GBPJPY": .260, "EURJPY": .266, "AUDJPY": .215, "USDJPY": .258}, "Mon2": {"GBPJPY": .537, "AUDJPY": .463}}; imp = []
for nm, w in W.items():
    b = None; v1 = None; v2 = None
    for p, wt in w.items():
        sb = shots_utc(p, (4, 6, 8, 10)) * wt; s1 = shots_local(p, (5, 7, 9, 11)) * wt; s2 = shots_local(p, (4, 6, 8, 10)) * wt
        b = sb if b is None else b.add(sb, fill_value=0); v1 = s1 if v1 is None else v1.add(s1, fill_value=0); v2 = s2 if v2 is None else v2.add(s2, fill_value=0)
    R.add(f"{nm} ロンドン 05/07/09/11 固定(改良系)", nm, "夏 UTC 4/6/8/10・冬 UTC 5/7/9/11", v1); imp.append(dict(comp=nm, variant="London 5/7/9/11", **improved(b, v1)))
    R.add(f"{nm} ロンドン 04/06/08/10 固定(改良系)", nm, "夏 UTC 3/5/7/9・冬 UTC 4/6/8/10", v2); imp.append(dict(comp=nm, variant="London 4/6/8/10", **improved(b, v2)))
R.finish(); pd.set_option("display.width", 300); print("\n== Q64 改良判定 ==\n" + pd.DataFrame(imp).to_string(index=False))
