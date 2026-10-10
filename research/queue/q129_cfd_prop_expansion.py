# -*- coding: utf-8 -*-
"""docs/322 §5j Q129(診断・セル 0): CFD プロップの 4 社目候補。各社の規約(results/q129_rules.json・docs/348 の調査値)に当方の 3 帳簿を当てて MC(5 日ブロック・250 日・5,000 本)。
帳簿: H = Hold/Roll(トパーズ型: Hold UK100 0.73 + WTI 0.23 + BTC 0.31 + ETH 0.21 + Roll5 5 クロス ×1.0・週末持ち越し必須)、M = Mon 4 クロス ×3.3(EA3 型・月曜 24h)、A = EA9 A案(Hold XAU + Mon GBPJPY + Mon NAS100 等ウェイト ×1.5・週末持ち越し必須)。
規約 JSON: {"業者: プラン": {"target": [p1,(p2)], "mdd": 0.10, "dd_type": "static|trail_eq|trail_bal_eod", "dll": 0.05, "weekend": true, "ea": true, "fee_100k": 500, "split": 0.8, "max_days": 250}}
使い方: cd research && python3 queue/q129_cfd_prop_expansion.py results/q129_rules.json"""
import sys, os, json
from q_common import *
base.DATA = os.path.join(ROOT, "data_202609"); import deployed_book as db
CAL = pd.date_range(IS0, pd.Timestamp("2026-07-29"), freq="D")
def on_cal(x): return x.groupby(x.index.normalize()).sum().reindex(CAL).fillna(0.0)
def roll5():
    out = None
    for sym in ("USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"):
        o = load(sym)["open"]; t = o.index[(o.index.dayofweek == 2) & (o.index.hour == 20)]
        r = trades(sym, t, o.reindex(t).values, -np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=4)).values) * 0.2; r.index = r.index.normalize()
        out = r if out is None else out.add(r, fill_value=0)
    return out
def books():
    H = (on_cal(base.hold_cell("UK100")) * 0.73 + on_cal(base.hold_cell("WTI")) * 0.23 + on_cal(base.hold_cell("BTCUSD")) * 0.31 + on_cal(base.hold_cell("ETHUSD")) * 0.21 + on_cal(roll5()) * 1.0)
    M = sum(on_cal(db.leg_series("Mon", s)) * 0.25 for s in ("AUDJPY", "EURJPY", "GBPJPY", "USDJPY")) * 3.3
    A = (on_cal(base.hold_cell("XAUUSD")) + on_cal(db.leg_series("Mon", "GBPJPY")) + on_cal(base.mon_cell("NAS100"))) / 3 * 1.5
    return {"H: Hold/Roll(トパーズ型・週末必須)": (H, True), "M: Mon 4 クロス ×3.3(EA3 型)": (M, False), "A: EA9 A案 ×1.5(Hold XAU・週末必須)": (A, True)}
rng = np.random.default_rng(11); N, BLOCK, DAYS = 5000, 5, 250
def mc(c, R):
    r = np.clip(np.asarray(c.values, float), -R["dll"], None); nb = len(r) - BLOCK + 1; md = R.get("max_days", DAYS); L = md * (2 if len(R["target"]) > 1 else 1)
    stt = rng.integers(0, nb, size=(N, L // BLOCK + 1)); p = r[(stt[:, :, None] + np.arange(BLOCK)[None, None, :])].reshape(N, -1)[:, :L]
    e = np.cumprod(1 + p, axis=1); hwm = np.maximum.accumulate(np.concatenate([np.ones((N, 1)), e[:, :-1]], axis=1), axis=1)
    if R["dd_type"] == "static": fl = np.full_like(e, 1 - R["mdd"])
    else: fl = np.minimum(hwm - R["mdd"], 1.0)
    dq = e <= fl; fd = np.where(dq.any(1), dq.argmax(1), 10**6)
    hit1 = e >= 1 + R["target"][0]; f1 = np.where(hit1.any(1), hit1.argmax(1), 10**6); ok1 = (f1 < fd) & (f1 < md)
    if len(R["target"]) == 1: return round(ok1.mean() * 100, 1), round(((fd < f1) & (fd < md)).mean() * 100, 1), (int(np.median(f1[ok1]) + 1) if ok1.any() else None)
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
    return dict(ann=round((eq.iloc[-1] ** (1 / yrs) - 1) * 100, 1), dd=round(float((eq / eq.cummax() - 1).min()) * 100, 1), wm=round(float(mo.min()) * 100, 1), wd=round(float(x.min()) * 100, 2), plus=f"{int((mo > 0).sum())}/{len(mo)}")
if __name__ == "__main__":
    RULES = json.load(open(sys.argv[1], encoding="utf-8")); B = books(); rows = []
    print("== 帳簿(5 年窓・暦日)=="); [print(k, st5(v)) for k, (v, _) in B.items()]
    for firm, R in RULES.items():
        for bk, (c, need_weekend) in B.items():
            if not R.get("ea", True) or (need_weekend and not R.get("weekend", True)): rows.append(dict(firm=firm, book=bk, reach=None, fail=None, days=None, ev_per_fee=None, note="規約不可")); continue
            reach, fail, days = mc(c, R); ann = st5(c)["ann"] / 100
            ev = (reach / 100) * 100000 * ann * R.get("split", 0.8) / max(R.get("fee_100k", 500), 1)   # 到達率 × 100k × 年率 × 分配 ÷ 審査料
            rows.append(dict(firm=firm, book=bk, reach=reach, fail=fail, days=days, ev_per_fee=round(ev, 1), note=""))
    D = pd.DataFrame(rows); pd.set_option("display.width", 300); print("\n== 規約 × 帳簿 MC(到達 % / 失格 % / 中央日数 / 期待手取り÷審査料)==\n" + D.to_string(index=False)); D.to_csv("results/q129_cfd_prop_expansion.csv", index=False)
