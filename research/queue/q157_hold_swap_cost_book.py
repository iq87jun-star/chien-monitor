# -*- coding: utf-8 -*-
"""docs/400 Q157(診断・セル 0): Hold のスワップ(docs/398 §2c 実測: FTMO XAU −52・GER40 −49・FN 非アドオン XAU −76 bps/月・swap-free 0)を
研究系列(recentfit_screen.hold_cell の swap_bps_m)と帳簿 MC(portfolio_sim: 口座の swap_xau_bps_m)に入れた影響。
(1) 現行 config(docs/399 切替後)をスワップ無し / 有りで比較。(2) Hold XAU を持つ 3 口座(1-Step 531466484・宝くじ 531343523・FN 14074882)の
Hold XAU 重み {現行, 半分, 0, Mon 置換(同名目を Mon 族へ)} をスワップ込みで比較(口座の期待出金・失格・帳簿の 10.6 年 Sharpe)。
(3) docs/290 の Hold 行(5 年・名目 ×1)にスワップ込みの列(XAU −52 / −76・GER40 −49)。
使い方: cd research && python3 -W ignore queue/q157_hold_swap_cost_book.py → results/q157_*.csv"""
import os, sys, json, copy
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
import forward.portfolio_sim as ps
from forward.portfolio_sim import run_portfolio, summarize, book, R, legs
N, SEED = 6000, 44
def sharpe(spec, sw):
    x = R(book(spec, sw)); return float(x.mean() / x.std() * np.sqrt(252)) if x.std() > 0 else 0.0
def annual(spec, sw):
    x = R(book(spec, sw)); return float(x.mean() * 252 * 100)
def row(res, nm, lab, extra):
    jpy, pct = res["per"][nm]; st = res["stats"][nm]
    return dict(account=nm, variant=lab, pay_mean_man=jpy.mean() / 1e4, pay_med_man=float(np.median(jpy)) / 1e4, zero=(jpy <= 0).mean() * 100, reach=st["reach"] * 100,
                fail=st["fail"] * 100, fail_funded_of_reached=st["fail_funded_of_reached"] * 100, **extra)
def main():
    cfg = json.load(open(os.path.join(ROOT, "config", "portfolio_current.json"), encoding="utf-8"))
    # (1) 無し / 有り
    c0 = copy.deepcopy(cfg)
    for a in c0["accounts"]: a.pop("swap_xau_bps_m", None)
    out = []
    for lab, c in [("swap_off", c0), ("swap_on", cfg)]:
        res = run_portfolio(c, N=N, seed=SEED); s = summarize(res, lab)
        print(f"{lab:<8} 合計: 期待 {s['mean']:.0f} 万 | −1σ {s['p16']:.0f} | 中央 {s['p50']:.0f} | 0 の確率 {s['p0']*100:.0f}%")
        for a in c["accounts"]:
            nm = a["name"]; sw = a.get("swap_xau_bps_m", 0.0)
            if ps.hold_xau_notional(a["funded"]) == 0 and ps.hold_xau_notional(a["eval"]) == 0: continue
            out.append(row(res, nm, lab, dict(swap=sw, xau_eval=ps.hold_xau_notional(a["eval"]), xau_funded=ps.hold_xau_notional(a["funded"]), total_mean=s["mean"], total_p16=s["p16"],
                                              sharpe_eval=sharpe(a["eval"], sw), sharpe_funded=sharpe(a["funded"], sw), ann_funded=annual(a["funded"], sw))))
    D1 = pd.DataFrame(out); pd.set_option("display.width", 260); print(D1.round(2).to_string(index=False)); D1.to_csv(os.path.join(ROOT, "results", "q157_swap_onoff.csv"), index=False)
    # (2) Hold XAU 重みの変形(スワップ込み)
    def variants(a):
        ev, fu = a["eval"], a["funded"]; V = []
        if "a9" in ev:   # EA9: a9 = a9_noxau + holdxau/3
            for lab, fx in (("現行", 1.0), ("半分", 0.5), ("0", 0.0)):
                V.append((lab, {"a9_noxau": ev["a9"], "holdxau": round(ev["a9"] / 3 * fx, 4), "mon4": ev["mon4"]}, {"a9_noxau": fu["a9"], "holdxau": round(fu["a9"] / 3 * fx, 4), "mon4": fu["mon4"]}))
            V.append(("Mon 置換", {"a9_noxau": ev["a9"], "mon4": round(ev["mon4"] + ev["a9"] / 3, 4)}, {"a9_noxau": fu["a9"], "mon4": round(fu["mon4"] + fu["a9"] / 3, 4)}))
        else:
            key = "mon4" if "mon4" in ev else "mon3"
            for lab, fx in (("現行", 1.0), ("半分", 0.5), ("0", 0.0)):
                V.append((lab, {**ev, "holdxau": round(ev["holdxau"] * fx, 4)}, {**fu, "holdxau": round(fu["holdxau"] * fx, 4)}))
            e2 = {k: v for k, v in ev.items() if k != "holdxau"}; f2 = {k: v for k, v in fu.items() if k != "holdxau"}
            e2[key] = round(e2.get(key, 0) + ev["holdxau"], 4); f2[key] = round(f2.get(key, 0) + fu["holdxau"], 4); V.append(("Mon 置換", e2, f2))
        return V
    out2 = []
    for a0 in cfg["accounts"]:
        if ps.hold_xau_notional(a0["funded"]) == 0 and ps.hold_xau_notional(a0["eval"]) == 0: continue
        for lab, ev, fu in variants(a0):
            c = copy.deepcopy(cfg)
            for a in c["accounts"]:
                if a["name"] == a0["name"]: a["eval"] = ev; a["funded"] = fu; sw = a.get("swap_xau_bps_m", 0.0)
            res = run_portfolio(c, N=N, seed=SEED); s = summarize(res, lab)
            out2.append(row(res, a0["name"], lab, dict(eval=json.dumps(ev, ensure_ascii=False), funded=json.dumps(fu, ensure_ascii=False), total_mean=s["mean"], total_p16=s["p16"],
                                                      sharpe_eval=sharpe(ev, sw), sharpe_funded=sharpe(fu, sw), ann_funded=annual(fu, sw))))
            r = out2[-1]; print(f"{a0['name']:<20} {lab:<6} 期待 {r['pay_mean_man']:5.1f} 万/月 0率 {r['zero']:3.0f}% 到達 {r['reach']:5.1f}% 失格 {r['fail']:5.1f}%(資金化後 {r['fail_funded_of_reached']:5.1f}) Sharpe 評価 {r['sharpe_eval']:.2f} 資金化後 {r['sharpe_funded']:.2f} 年率(資金化後) {r['ann_funded']:5.1f}% | 全体 {s['mean']:.0f} / −1σ {s['p16']:.0f}")
    D2 = pd.DataFrame(out2); D2.to_csv(os.path.join(ROOT, "results", "q157_hold_xau_weight.csv"), index=False)
    # (3) docs/290 の Hold 行にスワップ込みの列
    import recentfit_screen as base
    A, B = pd.Timestamp("2021-10-01"), pd.Timestamp("2026-08-31"); BD = pd.bdate_range(A, B)
    def on_bd(x): return x.groupby(x.index.normalize()).sum().reindex(BD).fillna(0.0)
    rows = []
    for nm, sws in (("XAUUSD", (0, -52, -76)), ("GER40", (0, -49)), ("UK100", (0,)), ("WTI", (0,))):
        for sw in sws:
            x = on_bd(base.hold_cell(nm, sw)); x = x[(x.index >= A) & (x.index <= B)]; eq = (1 + x).cumprod(); mon = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
            rec = dict(symbol=nm, swap_bps_m=sw)
            for y in range(2021, 2027): rec[str(y)] = round(((1 + x[x.index.year == y]).prod() - 1) * 100, 1)
            rec.update(cum5y=round((eq.iloc[-1] - 1) * 100, 1), max_dd=round((eq / eq.cummax() - 1).min() * 100, 1), worst_month=round(mon.min() * 100, 1), pos_months=f"{int((mon > 0).sum())}/{int((mon != 0).sum())}", sharpe=round(x.mean() / x.std() * np.sqrt(252), 2))
            rows.append(rec)
    D3 = pd.DataFrame(rows); print(D3.to_string(index=False)); D3.to_csv(os.path.join(ROOT, "results", "q157_hold_5y_swap.csv"), index=False)
    print("saved results/q157_swap_onoff.csv, q157_hold_xau_weight.csv, q157_hold_5y_swap.csv")
if __name__ == "__main__": main()
