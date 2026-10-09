# -*- coding: utf-8 -*-
"""docs/322 §5b Q112(診断・セル 0): 暗号資産プロップへの適合性。研究系列(ETHUSD Mon4 / v4 BTCUSD / Hold BTCUSD)を暗号資産専用の
「帳簿」に組み、各社の規約(目標・DD の型・日次上限・2 段階)を MC(5 日ブロック・250 日・5000 本)に当てて到達率・失格率を出す。
系列: ETHUSD Mon4 = H1 4/6/8/10 UTC 建て → 24h(docs/244 のコスト 15 bps)、v4 BTCUSD = deployed_book の v4(日足・最大 8 日)、Hold BTCUSD = hold_cell(月初 5 bps)。
暦日(土日含む)で合成。規約の数値は本スクリプトの RULES に外から与える(docs/331 の調査値)。"""
import sys, os, json
from q_common import *
base.DATA = os.path.join(ROOT, "data_202609"); import deployed_book as db
def eth_mon4():
    df = load("ETHUSD"); o = df["open"]; out = None
    for h in (4, 6, 8, 10):
        t = o.index[(o.index.dayofweek == 0) & (o.index.hour == h)]
        r = trades("ETHUSD", t, o.reindex(t).values, np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=24)).values) / 4; r.index = r.index.normalize()
        out = r if out is None else out.add(r, fill_value=0)
    return out
CAL = pd.date_range(IS0, pd.Timestamp("2026-07-29"), freq="D")
def on_cal(x): return x.groupby(x.index.normalize()).sum().reindex(CAL).fillna(0.0)
legs = {"MonETH": on_cal(eth_mon4()), "v4BTC": on_cal(db.leg_series("v4", "BTCUSD")), "HoldBTC": on_cal(base.hold_cell("BTCUSD"))}
BOOKS = {"A: Mon ETH のみ": {"MonETH": 1.0}, "B: Mon ETH 0.41 + v4 BTC 0.59(14166201 の比)": {"MonETH": 0.41, "v4BTC": 0.59}, "C: B + Hold BTC 0.3": {"MonETH": 0.41, "v4BTC": 0.59, "HoldBTC": 0.3}}
rng = np.random.default_rng(11); N, BLOCK, DAYS = 5000, 5, 250
def mc(c, mult, R):
    """R: dict(target=[p1,(p2)], mdd, dd_type in {static, trail_eq, trail_bal_eod}, dll, max_days)"""
    r = np.clip(np.asarray(c.values, float) * mult, -R["dll"], None); nb = len(r) - BLOCK + 1; md = R.get("max_days", DAYS); L = md * (2 if len(R["target"]) > 1 else 1)
    stt = rng.integers(0, nb, size=(N, L // BLOCK + 1)); p = r[(stt[:, :, None] + np.arange(BLOCK)[None, None, :])].reshape(N, -1)[:, :L]
    e = np.cumprod(1 + p, axis=1); hwm = np.maximum.accumulate(np.concatenate([np.ones((N, 1)), e[:, :-1]], axis=1), axis=1)
    if R["dd_type"] == "static": fl = np.full_like(e, 1 - R["mdd"])
    elif R["dd_type"] == "trail_eq": fl = np.minimum(hwm - R["mdd"], 1.0) if R.get("lock_at_initial", True) else hwm - R["mdd"]
    else: fl = np.minimum(hwm - R["mdd"], 1.0)
    dq = e <= fl; fd = np.where(dq.any(1), dq.argmax(1), 10**6)
    hit1 = e >= 1 + R["target"][0]; f1 = np.where(hit1.any(1), hit1.argmax(1), 10**6); ok1 = (f1 < fd) & (f1 < md)
    if len(R["target"]) == 1: return round(ok1.mean() * 100, 1), round(((fd < f1) & (fd < md)).mean() * 100, 1), (int(np.median(f1[ok1]) + 1) if ok1.any() else None)
    # 2 段階: 通過翌日から基準リセット(静的 DD は新基準、トレーリングは継続)
    ok2 = np.zeros(N, bool); fail = (fd < f1) & (fd < md); days = []
    for i in np.flatnonzero(ok1):
        b2 = e[i, f1[i]]; e2 = e[i, f1[i] + 1:] / b2
        if len(e2) == 0: continue
        h2 = np.maximum.accumulate(np.concatenate([[1.0], e2[:-1]])); fl2 = np.full_like(e2, 1 - R["mdd"]) if R["dd_type"] == "static" else np.minimum(h2 - R["mdd"], 1.0)
        hh = np.where(e2 >= 1 + R["target"][1])[0]; dd = np.where(e2 <= fl2)[0]
        if len(dd) and (not len(hh) or dd[0] < hh[0]): fail[i] = True; continue
        if len(hh) and hh[0] < md: ok2[i] = True; days.append(f1[i] + 1 + hh[0] + 1)
    return round(ok2.mean() * 100, 1), round(fail.mean() * 100, 1), (int(np.median(days)) if days else None)
def st5(x):
    eq = (1 + x).cumprod(); mo = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1); yrs = (x.index[-1] - x.index[0]).days / 365.25
    return dict(cagr=round((eq.iloc[-1] ** (1 / yrs) - 1) * 100, 1), dd=round(float((eq / eq.cummax() - 1).min()) * 100, 1), wm=round(float(mo.min()) * 100, 1), wd=round(float(x.min()) * 100, 2), plus=f"{int((mo > 0).sum())}/{len(mo)}", sh=round(float(x.mean() / x.std() * np.sqrt(365)), 2))
if __name__ == "__main__":
    RULES = json.load(open(sys.argv[1], encoding="utf-8")) if len(sys.argv) > 1 else {
        "仮1: 1段階 目標10% 静的DD10% 日次5%": dict(target=[0.10], mdd=0.10, dd_type="static", dll=0.05),
        "仮2: 2段階 8%/5% 静的DD10% 日次5%": dict(target=[0.08, 0.05], mdd=0.10, dd_type="static", dll=0.05),
        "仮3: 1段階 目標8% トレーリングDD6% 日次4%": dict(target=[0.08], mdd=0.06, dd_type="trail_eq", dll=0.04)}
    rows = []; pd.set_option("display.width", 300)
    for bk, w in BOOKS.items():
        u = sum(legs[k] * v for k, v in w.items())
        for m in (1, 2, 3, 4):
            x = u * m; s = st5(x); rec = dict(book=bk, mult=m, **s)
            for rn, R in RULES.items(): r, f, med = mc(u, m, R); rec[f"{rn} 到達"] = r; rec[f"{rn} 失格"] = f; rec[f"{rn} 中央日"] = med
            rows.append(rec)
    D = pd.DataFrame(rows); D.to_csv("results/q112_crypto_prop_fit.csv", index=False); print(D.to_string(index=False))
    for k, s in legs.items(): print(k, "IS/OOS:", st(s, IS0, IS1)["mean"], st(s, OOS0, END)["mean"], "bps/日(暦日平均)")
