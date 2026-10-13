# -*- coding: utf-8 -*-
"""Q142(新規 12 セル・結果を見る前に固定): 月曜以外の暦・イベント族を先物口座の形(日中・16:00 ET 前に決済)で。月曜は除外(既存の月曜族と重ねない)。
A. FOMC 当日の発表前ドリフト(Lucca & Moench 2015 の日中版): 09:00 → 14:00 ET LONG(US500 / NAS100 / US30)
B. 月初 1 営業日目 09:00 → 16:00 ET LONG(3)・月末最終営業日 09:00 → 16:00 ET LONG(3)
C. 四半期末リバランス: 四半期最後の 3 営業日、09:00 → 16:00 ET、向き = −sign(四半期累計 US500 − USTBOND)(3)
コスト 1 bps/往復(先物相当)。窓 PRE 2016〜2021-09 / IS 2021-10〜2024 / OOS 2025〜。標準基準 = IS 月次二項 p < 0.05/9,762・OOS 平均 > 0・PRE 勝率 ≥ 50%。"""
from q_common import *
CST = 1e-4; IDX = ["US500", "NAS100", "US30"]
def et_open(sym):
    o = load(sym)["open"]; x = o.copy(); x.index = x.index.tz_localize("UTC").tz_convert("America/New_York"); return x
E = {s: et_open(s) for s in IDX + ["USTBOND"]}
bd = sorted(set(E["US500"].index[E["US500"].index.hour == 9].normalize()))      # 09:00 ET の足がある日 = 営業日
bd = pd.DatetimeIndex(bd)
def px(sym, d, h):
    t = d + pd.Timedelta(hours=h); return E[sym].get(t)
def cell(sym, dates, h0, h1, direction):
    r = {}
    for d in dates:
        if d.dayofweek == 0: continue
        a, b = px(sym, d, h0), px(sym, d, h1); s = direction(d) if callable(direction) else direction
        if a is None or b is None or not np.isfinite(a) or not np.isfinite(b) or s == 0: continue
        r[d.tz_localize(None)] = s * (b / a - 1) - CST
    return pd.Series(r).sort_index()
fomc = pd.read_csv("data_ext/cb_meetings.csv"); fomc = pd.DatetimeIndex(pd.to_datetime(fomc[fomc.bank == "FOMC"].date)).tz_localize("America/New_York")
m = pd.Series(bd, index=bd).groupby(bd.to_period("M"))
def ny(x):
    x = pd.DatetimeIndex(x); return x.tz_localize("America/New_York") if x.tz is None else x.tz_convert("America/New_York")
first = ny(list(m.min())); last = ny(list(m.max()))
q = pd.Series(bd, index=bd).groupby(bd.to_period("Q"))
qend = ny(sorted(sum([list(g.iloc[-3:]) for _, g in q], [])))
def qdir(d):
    qs = pd.Period(d.tz_localize(None), "Q").start_time.tz_localize("America/New_York")
    def ret(sym):
        s = E[sym]; a = s[(s.index >= qs) & (s.index.hour == 9)]; b = s[(s.index < d) & (s.index.hour == 15)]
        return b.iloc[-1] / a.iloc[0] - 1 if len(a) and len(b) else np.nan
    x = ret("US500") - ret("USTBOND"); return 0 if not np.isfinite(x) else -np.sign(x)
cells = {}
for s in IDX:
    cells[f"A FOMC 当日 09→14 ET LONG {s}"] = cell(s, fomc, 9, 14, 1)
    cells[f"B 月初 1 日目 09→16 ET LONG {s}"] = cell(s, pd.DatetimeIndex(first), 9, 16, 1)
    cells[f"B 月末最終日 09→16 ET LONG {s}"] = cell(s, last, 9, 16, 1)
    cells[f"C 四半期末 3 日 リバランス逆張り {s}"] = cell(s, qend, 9, 16, qdir)
rows = []
for k, r in cells.items():
    def sh(a, b):
        x = r[(r.index >= a) & (r.index <= b)]; return round(float(x.mean() / x.std() * np.sqrt(len(x) / max((b - a).days / 365.25, 0.5) if len(x) else 1)), 2) if len(x) > 5 else np.nan
    sp, si, so = st(r, PRE0, IS0), st(r, IS0, IS1), st(r, OOS0, END)
    rows.append(dict(cell=k, n=len(r), pre_rate=sp["rate"], pre_bps=sp["mean"], is_plus=f"{si['plus']}/{si['n']}", is_bps=si["mean"], is_p=round(si["p"], 4),
                     oos_plus=f"{so['plus']}/{so['n']}", oos_bps=so["mean"], hit_all=round(float((r > 0).mean()), 3),
                     std_pass=bool(si["p"] < 0.05 / 9762 and so["mean"] > 0 and sp["rate"] >= 0.5),
                     sign3=bool(sp["mean"] > 0 and si["mean"] > 0 and so["mean"] > 0)))
R = pd.DataFrame(rows); pd.set_option("display.width", 260); print(R.to_string(index=False)); R.to_csv("results/q142_non_monday_events.csv", index=False)
print("3 窓とも平均 > 0:", int(R.sign3.sum()), "/ 12  標準通過:", int(R.std_pass.sum()))
