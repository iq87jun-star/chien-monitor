# -*- coding: utf-8 -*-
"""docs/322 Q99(診断・セル 0): トパーズ EA11(Fintokei スイング 3,500 万)の現行帳簿 Mon4 ×8 + 指数 Mon 各 1.0 に Roll(5 クロス SHORT・水曜 20 UTC 4h)を
×{0, 1, 2, 3} で足した場合のガード格子。docs/279 §4 の解禁条件(2026-09・2026-10 の JPY6 水曜監視が 2 か月連続で正)を満たしたときの「Roll ×3.0 = D 案」の再計算。
A) Q85 と同じ格子・同じ MC: 研究系列 2021-10〜2026-08、5 日ブロック・5,000 本 × 250 営業日、EA 日次ガード {3,4,5%} × EA 床 {8,9,10%}、
   年別サブサンプル(2022〜2026)の最悪年失格率。採用規則(docs/322 事前指定)= 最悪年でも失格率 ≤ 10% の中で到達率最大。到達 = +8%(P1)。
B) Q133(docs/355)と同じ 10.6 年 MC(2016-01〜2026-07・2 万本・2.8% 全決済ガード・月 2 回で停止)で、今日起点 → 2027-05-31 の P1+P2 到達 / 失格と資金化後(倍率半分)1 年。
出力: results/q99_roll_x3_guard_grid.csv(A の 36 格子)・results/q99_roll_x3_books.csv(B)。配備・manifest・EA は変更しない。"""
import os, sys, json, datetime as dt, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
ROLLS = [0.0, 1.0, 2.0, 3.0]; MON_MULT = 8.0; IDX_MULT = 1.0
# ---------- A) Q85 と同じ格子 ----------
src = open("logic_5y_scorecard.py", encoding="utf-8").read().split("rows = []")[0]
ns = {"__name__": "l5", "__file__": os.path.join(ROOT, "logic_5y_scorecard.py")}; exec(compile(src, "l5", "exec"), ns)
on_bd = ns["on_bd"]; base = ns["base"]; roll = ns["roll"]; mon4 = ns["mon4"]
idx = on_bd(base.mon_cell("NAS100")) + on_bd(base.mon_cell("US500"))
W0, W1 = pd.Timestamp("2021-10-01"), pd.Timestamp("2026-08-31")
def win(s): return s[(s.index >= W0) & (s.index <= W1)]
TARGET = 0.08; DAILY = [0.03, 0.04, 0.05]; FLOOR = [0.08, 0.09, 0.10]
rng = np.random.default_rng(99); N = 5000; BLOCK = 5; DAYS = 250
def mc(s, guard, floor, target, sub=None):
    r = np.asarray(s.values, float); ix = s.index
    if sub is not None: r = r[ix.year == sub]
    r = np.clip(r, -guard, None); nb = len(r) - BLOCK + 1
    if nb < 20: return np.nan, np.nan, None
    st = rng.integers(0, nb, size=(N, DAYS // BLOCK + 1)); p = r[(st[:, :, None] + np.arange(BLOCK)[None, None, :])].reshape(N, -1)[:, :DAYS]
    e = np.cumprod(1 + p, axis=1); hit = e >= 1 + target; dq = e <= 1 - floor
    fh = np.where(hit.any(axis=1), hit.argmax(axis=1), 10**6); fd = np.where(dq.any(axis=1), dq.argmax(axis=1), 10**6)
    reach = (fh < fd) & (fh < 10**6); fail = (fd < fh) & (fd < 10**6)
    return float(reach.mean()), float(fail.mean()), (int(np.median(fh[reach]) + 1) if reach.any() else None)
rows = []
for k in ROLLS:
    s = win(mon4 * MON_MULT + idx * IDX_MULT + roll * k)
    for g in DAILY:
        for f in FLOOR:
            reach, fail, med = mc(s, g, f, TARGET); yr = {}
            for y in range(2022, 2027):
                a, b, _ = mc(s, g, f, TARGET, sub=y); yr[y] = (a, b)
            worst_fail = max(v[1] for v in yr.values() if not np.isnan(v[1])); worst_year = max(yr, key=lambda y: yr[y][1] if not np.isnan(yr[y][1]) else -1)
            eq = (1 + np.clip(s, -g, None)).cumprod(); dd = float((eq / eq.cummax() - 1).min()); ann = float(eq.iloc[-1] ** (252 / len(eq)) - 1)
            rows.append(dict(book=f"Mon4 x{MON_MULT:g} + Idx x{IDX_MULT:g} + Roll x{k:g}", roll_mult=k, daily=g, floor=f, reach=round(reach * 100, 1), fail=round(fail * 100, 1), median_days=med,
                             worst_year=worst_year, worst_year_fail=round(worst_fail * 100, 1), ann=round(ann * 100, 1), max_dd=round(dd * 100, 1),
                             **{f"fail_{y}": round(yr[y][1] * 100, 1) for y in yr}, **{f"reach_{y}": round(yr[y][0] * 100, 1) for y in yr}, current=(k == 0.0 and g == 0.04 and f == 0.09)))
            print(f"Roll x{k:<3g} 日次{g*100:.0f}% 床{f*100:.0f}% | 到達 {reach*100:5.1f} 失格 {fail*100:5.1f} 中央 {med} | 最悪年 {worst_year} 失格 {worst_fail*100:5.1f} | 年率 {ann*100:6.1f} DD {dd*100:6.1f}", flush=True)
df = pd.DataFrame(rows); df.to_csv("results/q99_roll_x3_guard_grid.csv", index=False)
ok = df[df.worst_year_fail <= 10.0]
print(f"\n== A) 可行 {len(ok)}/{len(df)}")
if len(ok): b = ok.sort_values(["reach", "fail"], ascending=[False, True]).iloc[0]; print(f"   採用点 Roll x{b.roll_mult:g} 日次{b.daily*100:.0f}% 床{b.floor*100:.0f}% → 到達 {b.reach} 失格 {b.fail} 最悪年 {b.worst_year_fail}({b.worst_year})")
for k in ROLLS:
    d = df[(df.roll_mult == k) & (df.floor == 0.10)]; print(f"   Roll x{k:g} 床10%: 到達 {d.reach.min()}〜{d.reach.max()} 失格 {d.fail.min()}〜{d.fail.max()} 最悪年 {d.worst_year_fail.min()}〜{d.worst_year_fail.max()}")
# Roll 単独の寄与(同じ窓・年別)
rs = win(roll)
print("   Roll ×1 単独 年別 合計(%):", {y: round(float(rs[rs.index.year == y].sum() * 100), 2) for y in range(2022, 2027)}, "| 窓合計", round(float(rs.sum() * 100), 2))
# ---------- B) Q133 と同じ 10.6 年 MC(2.8% 全決済ガード) ----------
import q129_cfd_prop_expansion as q129
q129.CAL = pd.date_range(pd.Timestamp("2016-01-04"), pd.Timestamp("2026-07-29"), freq="D")
from q129_cfd_prop_expansion import on_cal, roll5
import deployed_book as db
L = lambda f, s: on_cal(db.leg_series(f, s))
mon4c = sum(L("Mon", s) * 0.25 for s in ("AUDJPY", "EURJPY", "GBPJPY", "USDJPY")); idxc = on_cal(base.mon_cell("NAS100")) + on_cal(base.mon_cell("US500")); rollc = on_cal(roll5())
rng2 = np.random.default_rng(33); N2 = 20000; G = 0.028; P0, P1 = pd.Timestamp("2016-01-04"), pd.Timestamp("2026-07-29")
start = dt.date.today(); D = (dt.date(2027, 5, 31) - start).days
try:
    stj = json.load(open("ops_inbox/status.json", encoding="utf-8")); acc = [t for t in stj["terminals"] if str(t.get("account")) == "6104739"][0]
    e0 = float(acc.get("equity") or acc.get("balance")) / 35_000_000   # ops_inbox の最新 equity(無ければ 1.0)
except Exception: e0 = 1.0
print(f"\n== B) 起点 {start} → 2027-05-31({D} 日)・e0 {e0:.4f}")
def paths(c, days):
    r = np.asarray(c[(c.index >= P0) & (c.index <= P1)].values, float); nb = len(r) - BLOCK + 1
    stt = rng2.integers(0, nb, size=(N2, days // BLOCK + 1)); return r[(stt[:, :, None] + np.arange(BLOCK)[None, None, :])].reshape(N2, -1)[:, :days]
def guard(p):
    p = np.clip(p, -G, None); n = p.shape[1] // 21 * 21; w = p[:, :n].reshape(N2, -1, 21); hit = (w <= -G + 1e-12); prior = np.cumsum(hit, axis=2) - hit
    return np.concatenate([np.where(prior >= 2, 0.0, w).reshape(N2, -1), p[:, n:]], axis=1)
def evaluation(c, targets=(0.08, 0.06), mdd=0.10, days=735):
    p = guard(paths(c, days)); e = e0 * np.cumprod(1 + p, axis=1); fl = 1 - mdd; dq = e <= fl; fd = np.where(dq.any(1), dq.argmax(1), 10**6)
    hit1 = e >= 1 + targets[0]; f1 = np.where(hit1.any(1), hit1.argmax(1), 10**6); ok1 = f1 < fd; rd = np.full(N2, 10**6); fdd = np.where(fd < f1, fd + 1, 10**6)
    for i in np.flatnonzero(ok1):
        b2 = e[i, f1[i]]; e2 = e[i, f1[i] + 1:] / b2
        if len(e2) == 0: continue
        hh = np.where(e2 >= 1 + targets[1])[0]; dd = np.where(e2 <= fl)[0]
        if len(dd) and (not len(hh) or dd[0] < hh[0]): fdd[i] = f1[i] + 1 + dd[0] + 1; continue
        if len(hh): rd[i] = f1[i] + 1 + hh[0] + 1
    d = rd[rd < 10**6]; return (rd <= D).mean(), (fdd <= D).mean(), (start + dt.timedelta(days=int(np.median(d))) if len(d) else None), (start + dt.timedelta(days=int(np.quantile(d, .977))) if len(d) else None)
def funded(c, days=252, mdd=0.10):
    p = guard(paths(c, days)); e = np.cumprod(1 + p, axis=1); fl = 1 - mdd; br = (e <= fl).any(1); fin = np.where(br, fl, e[:, -1]); return br.mean(), float(np.mean(fin - 1))
rows2 = []
for k in ROLLS:
    c = mon4c * MON_MULT + idxc * IDX_MULT + rollc * k; r, f, med, p977 = evaluation(c); br, ret = funded(c * 0.5); inc = 35_000_000 / 158 * max(ret, 0) * 0.8 / 12 * 158 / 10000
    rows2.append(dict(book=f"Mon4 x{MON_MULT:g} + Idx x{IDX_MULT:g} + Roll x{k:g}", roll_mult=k, reach=round(r * 100), fail=round(f * 100), median=str(med), p977=str(p977), funded_fail=round(br * 100), funded_ret=round(ret * 100, 1), monthly_man=round(inc), june_exp=round(r * inc)))
    print(f"Roll x{k:<3g} 5月末まで 到達 {r*100:3.0f}% 失格 {f*100:3.0f}% 中央 {med} +2σ {p977} | 資金化後(半分) 失格 {br*100:3.0f}% 期待 {ret*100:+.1f}% 月 {inc:3.0f} 万 → 6 月期待 {r*inc:3.0f} 万", flush=True)
pd.DataFrame(rows2).to_csv("results/q99_roll_x3_books.csv", index=False)
