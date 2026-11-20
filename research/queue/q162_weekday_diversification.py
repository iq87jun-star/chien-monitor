# -*- coding: utf-8 -*-
"""Q162(診断・セル 0・2026-11-07 ユーザー「今行えますか」): 月曜偏りの訂正案 — 週末持ち越し可の 5 口座で Mon を f 倍に下げ、
空いた日次リスク枠(5 年の最悪日を現状と同じに保つ)を通過済みの Hold UK100/WTI(14166201 と同じ比 0.491:0.153)へ振り替える。
比較: B(EA 実レグ・現状)/ D7(Mon ×0.7)/ D5(Mon ×0.5)。指標: 族別リスク寄与・曜日別分散・口座間相関・合計月利、口座別 MC(到達・失格・出金・初回・30 か月期待)。
対象外: FTMO 50k 2 口座(週末不可・Roll はスワップ口座不可 → Mon 専用口座として据え置き)、FN 14166201(既に非 Mon)、FN 14074882(スワップ口座で指数 Hold の金融費用が未計測)、Instant(Hold 不可・docs/176 §7.8.2)。
使い方: cd research && python3 -W ignore queue/q162_weekday_diversification.py   出力: results/q162_weekday_diversification.csv"""
import os, sys, json, copy
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); os.chdir(ROOT)
src = open(os.path.join(ROOT, "forward", "account_cards.py"), encoding="utf-8").read().split("rows_a, rows_m = [], []")[0]
ns = {"__name__": "ac", "__file__": os.path.join(ROOT, "forward", "account_cards.py")}; exec(compile(src, "account_cards_head", "exec"), ns)
import numpy as np, pandas as pd
EA_LEGS, S, ea_book, cfg, mc, daily_window, mdd_daily = ns["EA_LEGS"], ns["S"], ns["ea_book"], ns["cfg"], ns["mc"], ns["daily_window"], ns["mdd_daily"]
SWING = {"531466484", "531343523", "6104736", "6104739", "6071612"}
HOLD_RATIO = {"hold:UK100": 0.491, "hold:WTI": 0.153}
def cur_legs(a):
    aid = a["name"].split()[-1]; return EA_LEGS[aid]["funded" if a.get("funded_now") else "eval"]
def rescale(lg, f, w):
    """Mon(mon:*・nas・spx)を f 倍、Hold UK100/WTI を w 倍で追加(既存分に加算)。"""
    out = {}
    for k, v in lg.items(): out[k] = v * f if (k.startswith("mon:") or k in ("nas", "spx")) else v
    for k, v in HOLD_RATIO.items(): out[k] = out.get(k, 0.0) + v * w
    return out
def worst_day(lg, sw): return float(daily_window(ea_book(lg, sw)).min())
def solve_w(lg, f, sw):
    """最悪日を現状と同じにする Hold 重み w(2 分法)。"""
    tgt = worst_day(lg, sw); lo, hi = 0.0, 30.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if worst_day(rescale(lg, f, mid), sw) < tgt: hi = mid
        else: lo = mid
    return lo
def solve_w2(lg, f, sw):
    """最悪日と 5 年の日次最大 DD の両方を現状以下に保つ Hold 重み w(2 分法。どちらかが先に当たる)。"""
    rd0 = daily_window(ea_book(lg, sw)); tw, tm = float(rd0.min()), mdd_daily(rd0); lo, hi = 0.0, 30.0
    for _ in range(50):
        mid = (lo + hi) / 2; rd = daily_window(ea_book(rescale(lg, f, mid), sw))
        if float(rd.min()) < tw or mdd_daily(rd) < tm: hi = mid
        else: lo = mid
    return lo
def legs_txt(lg): return " + ".join(f"{k} ×{w:.2f}" for k, w in lg.items() if w > 1e-9)
def portfolio(legs_by_acc):
    tot = None; fam = {}; rets = {}
    for a in cfg["accounts"]:
        lg = legs_by_acc[a["name"]]; sw = a.get("swap_xau_bps_m", 0.0); bal = a["balance_jpy"]
        s = daily_window(ea_book(lg, sw)); rets[a["name"]] = s; tot = s * bal if tot is None else tot + s * bal
        for k, w in lg.items():
            f = "Mon円" if k.startswith("mon:") else ("Mon指数" if k in ("nas", "spx") else ("Brk" if k == "brk" else ("Roll" if k == "roll4" else ("v4" if k.startswith("v4:") else "Hold"))))
            fam[f] = fam.get(f, 0) + daily_window(S(k)) * w * bal
    v = tot.var(); rc = {f: float(np.cov(x, tot)[0, 1] / v) for f, x in fam.items()}
    dow = (tot.groupby(tot.index.dayofweek).apply(lambda x: (x ** 2).sum()) / (tot ** 2).sum())
    c = pd.DataFrame(rets).corr().values; avg_corr = float(c[np.triu_indices(len(c), 1)].mean())
    tb = sum(a["balance_jpy"] for a in cfg["accounts"]); m = (1 + tot / tb).resample("ME").prod() - 1; eq = (1 + m).cumprod()
    return dict(rc_mon=rc.get("Mon円", 0) + rc.get("Mon指数", 0), rc_hold=rc.get("Hold", 0), rc_other=1 - rc.get("Mon円", 0) - rc.get("Mon指数", 0) - rc.get("Hold", 0), var_mon=float(dow.get(0, 0)), avg_corr=avg_corr,
                m_mean=float(m.mean()), m_worst=float(m.min()), m_mdd=float((eq / eq.cummax() - 1).min()), d_mdd=mdd_daily(tot / tb), m_sharpe=float(m.mean() / m.std() * np.sqrt(12)))
scen = {"B 現状": {a["name"]: dict(cur_legs(a)) for a in cfg["accounts"]}}
notes = {}
for lab, f, both in (("D7 Mon×0.7", 0.7, False), ("D5 Mon×0.5", 0.5, False), ("E7 Mon×0.7 DD制約", 0.7, True), ("E5 Mon×0.5 DD制約", 0.5, True)):
    d = {}
    for a in cfg["accounts"]:
        aid = a["name"].split()[-1]; lg = cur_legs(a); sw = a.get("swap_xau_bps_m", 0.0)
        if aid in SWING:
            w = (solve_w2 if both else solve_w)(lg, f, sw); d[a["name"]] = rescale(lg, f, w); notes[(lab, a["name"])] = f"Hold UK100/WTI ×{w:.2f}(UK100 {0.491*w:.2f}・WTI {0.153*w:.2f})"
        else: d[a["name"]] = dict(lg); notes[(lab, a["name"])] = "据え置き"
    scen[lab] = d
print("=== 帳簿全体 ===")
P = {lab: portfolio(d) for lab, d in scen.items()}
pt = pd.DataFrame(P).T; print((pt * 100).round(1).to_string())
print("\n=== 口座別 MC(6,000 経路・30 か月・portfolio_sim と同じ規則) ===")
rows = []
for lab, d in scen.items():
    for a in cfg["accounts"]:
        lg = d[a["name"]]; same = (lab != "B 現状") and lg == scen["B 現状"][a["name"]]
        if same: r = next(x for x in rows if x["scenario"] == "B 現状" and x["account"] == a["name"]); r = dict(r); r["scenario"] = lab; r["legs_note"] = "据え置き(B と同じ)"; rows.append(r); continue
        b = copy.deepcopy(a); fn = a.get("funded_now", False)
        if fn: b["eval"] = lg; b["funded"] = lg
        else:   # 資金化後も同じ比率で縮める(評価 → 資金化の倍率比は EA_LEGS の比を保つ)
            aid = a["name"].split()[-1]; ratio = {k: EA_LEGS[aid]["funded"].get(k, 0) / v if v else 0 for k, v in EA_LEGS[aid]["eval"].items()}
            rf = {k: v * (ratio.get(k) if ratio.get(k) else (list(ratio.values())[0])) for k, v in lg.items()}; b["eval"] = lg; b["funded"] = rf
        s = mc(b); sw = a.get("swap_xau_bps_m", 0.0); rd = daily_window(ea_book(lg, sw))
        rows.append(dict(scenario=lab, account=a["name"], legs=legs_txt(lg), legs_note=notes.get((lab, a["name"]), "現状"), worst_day=float(rd.min()), mdd_d=mdd_daily(rd), m_mean=float(((1 + rd).resample("ME").prod() - 1).mean()),
                         p_reach=s["p_reach"], p_fail=s["p_fail"], p_pay=s["p_pay"], t_med=s["t_med"], a_med=s["a_med"], c12_med=s["c12_med"], c30_mean=s["c30_mean"]))
        print(lab, a["name"], "done", flush=True)
df = pd.DataFrame(rows); df.to_csv("results/q162_weekday_diversification.csv", index=False)
pd.set_option("display.width", 260); pd.set_option("display.max_columns", 30)
show = df.assign(最悪日=(df.worst_day * 100).round(1), DD=(df.mdd_d * 100).round(1), 月利=(df.m_mean * 100).round(2), 到達=(df.p_reach * 100).round(0), 失格=(df.p_fail * 100).round(0), 出金=(df.p_pay * 100).round(0),
                 初回額万=(df.a_med / 1e4).round(1), 累計12万=(df.c12_med / 1e4).round(0), 期待30万=(df.c30_mean / 1e4).round(0))[["scenario", "account", "legs_note", "最悪日", "DD", "月利", "到達", "失格", "出金", "t_med", "初回額万", "累計12万", "期待30万"]]
print(show.to_string(index=False))
print("\n30 か月期待 合計(万円):", df.groupby("scenario").c30_mean.sum().div(1e4).round(0).to_dict())
pt.to_csv("results/q162_weekday_diversification_portfolio.csv")
