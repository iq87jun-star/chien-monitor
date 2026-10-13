# -*- coding: utf-8 -*-
"""docs/349 §9a〜§9c: 全口座の同時シミュレーション(同じ相場経路・10.6 年・5 日ブロック)。
評価 → 資金化(額面から再出発)→ 資金化後は倍率を戻し、余裕比例 k・保持率 keep・毎月出金(超過分 × pay_frac)。
口座の定義は research/config/portfolio_current.json。使い方: from forward.portfolio_sim import run_portfolio"""
import os, sys, json, datetime as dt
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, "queue")); os.chdir(ROOT)
import q129_cfd_prop_expansion as q129
q129.CAL = pd.date_range(pd.Timestamp("2016-01-04"), pd.Timestamp("2026-07-29"), freq="D")
from q_common import *
base.DATA = os.path.join(ROOT, "data_202609"); import deployed_book as db
from q129_cfd_prop_expansion import on_cal, roll5
L = lambda f, s: on_cal(db.leg_series(f, s))
FX = 158.0; P0, P1 = pd.Timestamp("2016-01-04"), pd.Timestamp("2026-07-29")
_LEGS = None
def legs():
    global _LEGS
    if _LEGS is None:
        mon4 = sum(L("Mon", s) * 0.25 for s in ("AUDJPY", "EURJPY", "GBPJPY", "USDJPY")); nas = on_cal(base.mon_cell("NAS100")); spx = on_cal(base.mon_cell("US500"))
        holdxau = on_cal(base.hold_cell("XAUUSD")); roll = on_cal(roll5())
        _LEGS = dict(mon4=mon4, bplan=L("Mon", "GBPJPY") * 0.374 + L("Mon", "AUDJPY") * 0.322 + L("v4", "USDJPY") * 0.304, idx=nas + spx, holdxau=holdxau, roll=roll,
                     hold_uw=L("Hold", "UK100") * 0.491 + L("Hold", "WTI") * 0.153, btc=L("v4nfx", "BTCUSD") * 0.211, mon3=L("Mon", "EURJPY") * 0.333 + L("Mon", "USDJPY") * 0.333 + L("Mon", "NZDJPY") * 0.334,
                     a9=(holdxau + L("Mon", "GBPJPY") + nas) / 3, instG=L("Mon", "GBPJPY") * 0.537 * 4 + L("Mon", "AUDJPY") * 0.463 * 4 + (nas + spx) * 0.125 * 4)
    return _LEGS
def book(spec):
    """spec: {"mon4": 8, "idx": 1.0, ...} → 日次リターン系列"""
    lg = legs(); return sum(lg[k] * w for k, w in spec.items())
def R(c): return np.asarray(c[(c.index >= P0) & (c.index <= P1)].values, float)
def run_portfolio(cfg, N=6000, seed=44, months_after=12, verbose=False):
    """cfg = portfolio_current.json 形式。戻り: dict(total=月平均出金の配列(円), per={口座: (配列(円), 配列(残高比))}, m0)"""
    g = cfg["global"]; k, keep, pf = g["k"], g["keep"], g.get("pay_frac", 1.0); start = pd.Timestamp(g["start"]); d0 = (pd.Timestamp(g["income_from"]) - start).days
    DAYS = int(d0 * 250 / 365) + 21 * months_after + 21; BLOCK = 5; rng = np.random.default_rng(seed)
    T = len(R(legs()["mon4"])); nb = T - BLOCK + 1; stt = rng.integers(0, nb, size=(N, DAYS // BLOCK + 1)); IDX = (stt[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(N, -1)[:, :DAYS]
    m0 = int(d0 * 250 / 365) // 21; months = DAYS // 21; per = {}
    for a in cfg["accounts"]:
        if not a.get("active", True): continue
        ce = R(book(a["eval"]))[IDX]; cf = R(book(a["funded"]))[IDX]; e0 = a["e0"]; tg = a["targets"]; mdd = a["mdd"]; dll = a["dll"]; bal = a["balance_jpy"]
        kk = a.get("k", k); kp = a.get("keep", keep); fn = a.get("funded_now", False); trail = a.get("trail", False)
        e = np.full(N, e0); basel = np.ones(N); stage = np.zeros(N, int); funded = np.full(N, fn); failed = np.zeros(N, bool); hwm = np.full(N, e0); paid = np.zeros((N, months))
        for t in range(DAYS):
            act = ~failed; fl = np.minimum(hwm - mdd, 1.0) if (trail and not fn) else basel * (1 - mdd)
            if trail and fn: fl = basel * (1 - mdd)
            f = np.where(funded, np.clip(1 + kk * ((e - fl) / basel - mdd) / mdd, 1.0, 1 + kk), 1.0)
            ret = np.clip(np.where(funded, cf[:, t] * f, ce[:, t]), -dll, None); e = np.where(act, e * (1 + ret), e); hwm = np.maximum(hwm, e); failed |= act & (e <= fl)
            if not fn:
                for s in range(len(tg)):
                    hit = act & ~failed & ~funded & (stage == s) & (e >= basel * (1 + tg[s]))
                    if s == len(tg) - 1: funded |= hit; e[hit] = 1.0; basel[hit] = 1.0; hwm[hit] = 1.0
                    else: stage[hit] = s + 1; basel[hit] = e[hit]
            if (t + 1) % 21 == 0:
                m = (t + 1) // 21 - 1; w = np.where(funded & ~failed, np.maximum(e - basel * (1 + kp), 0.0) * pf, 0.0); paid[:, m] = w * bal * 0.8; e -= w
        win = paid[:, m0:m0 + months_after]; per[a["name"]] = (win.mean(axis=1), win.mean(axis=1) / bal)
    total = sum(v[0] for v in per.values()); return dict(total=total, per=per, m0=m0)
def summarize(res, label=""):
    q = lambda x, p: float(np.quantile(x, p)); t = res["total"] / 1e4
    out = dict(label=label, mean=t.mean(), p023=q(t, .023), p16=q(t, .16), p50=q(t, .5), p84=q(t, .84), p977=q(t, .977), p0=(t <= 0).mean(), p30=(t < 30).mean())
    return out
if __name__ == "__main__":
    cfg = json.load(open(os.path.join(ROOT, "config", "portfolio_current.json"), encoding="utf-8")); res = run_portfolio(cfg); s = summarize(res, "current")
    print(f"合計 月平均出金(円・6 月以降 12 か月): 期待 {s['mean']:.0f} 万 | −2σ {s['p023']:.0f} | −1σ {s['p16']:.0f} | 中央 {s['p50']:.0f} | +1σ {s['p84']:.0f} | +2σ {s['p977']:.0f} | 0 の確率 {s['p0']*100:.0f}%")
    for nm, (jpy, pct) in res["per"].items():
        qq = lambda p: float(np.quantile(pct, p)) * 100
        print(f"  {nm:<28} 期待 {pct.mean()*100:5.2f}%/月 ({jpy.mean()/1e4:5.1f} 万) | −2σ {qq(.023):5.2f} | −1σ {qq(.16):5.2f} | 中央 {qq(.5):5.2f} | +1σ {qq(.84):5.2f} | +2σ {qq(.977):5.2f} | 0 の確率 {(pct<=0).mean()*100:3.0f}%")
