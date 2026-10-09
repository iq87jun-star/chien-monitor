# -*- coding: utf-8 -*-
"""docs/322 §5b Q113(診断・セル 0): 先物プロップ(CME ミクロ)への適合性。
先物プロップの一般規約「日次クローズ(17:00 ET)前にフラット・週末不可・EOD トレーリング DD・一貫性ルール」の下で、既存の族のうち
日中版に落とせるものが IS/OOS で符号を保つかを数える。探索はしない(セルは累積に数えない)。
写像: Mon 指数(US500→MES / NAS100→MNQ / US30→MYM / JP225→(NKD・ミクロなし)) = 月曜 13 or 14 UTC 建て → 同日 20:00 UTC(16:00 ET 前)決済、
      Mon USDJPY(→ 6J/MJY の売り = USDJPY 買い)= 月曜 4/6/8/10 UTC 建て → 同日 20:00 UTC 決済、
      Roll5 USDJPY のみ(水 20→00 UTC)= クローズをまたぐので「オーバーナイト可プランのみ」参考、
      Hold / v4 = 数日〜数週保有のため不可(対象外)。
比較対象は 24h 版(配備形)。コストは q_common(指数 3 bps / FX 3 pip)で先物より保守的。
MC: 50k 口座の典型規約(利益目標 +6% / 日次損失 −2% / EOD トレーリング DD 4% / 一貫性 = 最良日 ≤ 総利益の 50%)を到達時点で判定。"""
import sys, os
from q_common import *
IDX = ["US500", "NAS100", "US30", "JP225"]; EXIT_H = 20
def shot(sym, dow, h_in, h_out_same_day, direction=1.0):
    df = load(sym); o = df["open"]; t = o.index[(o.index.dayofweek == dow) & (o.index.hour == h_in)]
    if h_out_same_day is None: t_out = t + pd.Timedelta(hours=24)
    else: t_out = pd.DatetimeIndex([x.normalize() + pd.Timedelta(hours=h_out_same_day) for x in t])
    r = trades(sym, t, o.reindex(t).values, np.full(len(t), direction), o.reindex(t_out).values); r.index = r.index.normalize(); return r
def row(name, s):
    sp, si, so = st(s, PRE0, IS0), st(s, IS0, IS1), st(s, OOS0, END)
    def sh(a, b):
        x = s[(s.index >= a) & (s.index <= b)]; return round(float(x.mean() / x.std() * np.sqrt(52)), 2) if len(x) > 5 and x.std() > 0 else np.nan
    return dict(cell=name, pre_rate=sp["rate"], is_n=si["n"], is_plus=si["plus"], is_mean_bps=si["mean"], is_p=round(si["p"], 3), is_sharpe=sh(IS0, IS1), oos_n=so["n"], oos_plus=so["plus"], oos_mean_bps=so["mean"], oos_sharpe=sh(OOS0, END),
                sign_ok=bool(si["mean"] > 0 and so["mean"] > 0), std_pass=bool(si["p"] < 0.05 / 9631 and so["mean"] > 0 and sp["rate"] >= 0.5))
rows = []; keep = {}
for sym in IDX:
    for h in (13, 14):
        a = shot(sym, 0, h, None); b = shot(sym, 0, h, EXIT_H)
        rows.append(row(f"Mon {sym} h{h} 24h(配備形)", a)); rows.append(row(f"Mon {sym} h{h} → 20 UTC(日中版)", b)); keep[(sym, h)] = b
# USDJPY → 6J(買い USDJPY)
parts24, partsID = [], []
for h in (4, 6, 8, 10):
    a = shot("USDJPY", 0, h, None); b = shot("USDJPY", 0, h, EXIT_H); parts24.append(a); partsID.append(b)
m24 = pd.concat(parts24, axis=1).mean(axis=1).dropna(); mid = pd.concat(partsID, axis=1).mean(axis=1).dropna()
rows.append(row("Mon USDJPY 4 ショット 24h(配備形)", m24)); rows.append(row("Mon USDJPY 4 ショット → 20 UTC(日中版・6J)", mid))
roll = shot("USDJPY", 2, 20, None); roll_t = load("USDJPY")["open"]; t = roll_t.index[(roll_t.index.dayofweek == 2) & (roll_t.index.hour == 20)]
roll = trades("USDJPY", t, roll_t.reindex(t).values, -np.ones(len(t)), roll_t.reindex(t + pd.Timedelta(hours=4)).values); roll.index = roll.index.normalize()
rows.append(row("Roll5 USDJPY のみ(水 20→00 UTC・クローズまたぎ)", roll))
R = pd.DataFrame(rows); pd.set_option("display.width", 300); R.to_csv("results/q113_futures_prop_fit.csv", index=False); print(R.to_string(index=False))
# ---- 先物プロップ MC(日中版で符号を保つ指数セル + 6J を等ウェイト)----
surv = [k for k, s in keep.items() if row("x", s)["sign_ok"]]; print("\n日中版で IS/OOS とも平均 > 0 の指数セル:", surv)
book = None
for k in surv:
    x = keep[k] / len(surv); book = x if book is None else book.add(x, fill_value=0)
if row("x", mid)["sign_ok"]: book = (book.add(mid, fill_value=0) / 2) if book is not None else mid
BD = pd.bdate_range(IS0, END); u = book.reindex(BD).fillna(0.0) if book is not None else pd.Series(0.0, index=BD)
u = u[u.index <= u.index[u.ne(0).values].max()] if u.ne(0).any() else u
rng = np.random.default_rng(7); N, BLOCK, DAYS = 5000, 5, 250
def mc(c, mult, target=0.06, dll=0.02, mdd=0.04, consist=0.5, trailing="eod"):
    r = np.clip(np.asarray(c.values, float) * mult, -dll, None); nb = len(r) - BLOCK + 1
    stt = rng.integers(0, nb, size=(N, DAYS // BLOCK + 1)); p = r[(stt[:, :, None] + np.arange(BLOCK)[None, None, :])].reshape(N, -1)[:, :DAYS]
    e = np.cumprod(1 + p, axis=1); hwm = np.maximum.accumulate(np.concatenate([np.ones((N, 1)), e[:, :-1]], axis=1), axis=1)
    fl = np.minimum(hwm - mdd, 1.0) if trailing == "eod" else np.full_like(e, 1 - mdd)
    hit = e >= 1 + target; dq = e <= fl; fh = np.where(hit.any(1), hit.argmax(1), 10**6); fd = np.where(dq.any(1), dq.argmax(1), 10**6)
    reach = (fh < fd) & (fh < 10**6); fail = (fd < fh) & (fd < 10**6)
    # 一貫性: 到達時点で最良日の利益 ≤ 総利益 × consist
    cons = np.zeros(N, bool)
    for i in np.flatnonzero(reach):
        q = p[i, :fh[i] + 1]; g = q[q > 0].sum(); cons[i] = (q.max() <= consist * g) if g > 0 else False
    return round(reach.mean() * 100, 1), round(fail.mean() * 100, 1), round((reach & cons).mean() * 100, 1), (int(np.median(fh[reach]) + 1) if reach.any() else None)
print("\n== 先物プロップ MC(50k 典型規約: 目標 +6% / 日次 −2% / EOD トレーリング 4% / 一貫性 50%)==")
if u.ne(0).any():
    for m in (1, 2, 3, 5, 8):
        r, f, rc, med = mc(u, m); x = u * m; mo = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
        print(f"×{m}: 年率 {((1+x).prod()**(252/len(x))-1)*100:5.1f}% 最悪月 {mo.min()*100:5.1f}% 最悪日 {x.min()*100:5.2f}% | 到達 {r}% 失格 {f}% 到達かつ一貫性OK {rc}% 中央 {med} 日")
else: print("(日中版で生き残るセルなし)")
