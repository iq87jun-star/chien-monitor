# -*- coding: utf-8 -*-
"""docs/244 Q234(診断・セル 0・2026-11-15 登録): 今日の候補をすべて適用した場合のまとめ。
(a) FN Instant: 現行 / E1(前金曜 VIX ≤ 25 の週は円クロスを全通貨 20 UTC・25 超は 24h)/ V1(指数を US30 + JP225 の F に差し替え)/ E1 + V1。モデルは Q222・Q230・Q231 第 2 段と同じ。
(b) Q233 の結果(results/q233_exit_switch_*.csv)を口座ごとに「到達率(2 窓の平均)の積 × 本口座後 10 年累計出金」でつなぐ。現行 / すべて適用(E1 を全場面)/ 規則どおり候補の場面だけ適用。金額は balance_jpy を掛けた参考値(分配前)。
使い方: cd research && python3 -W ignore queue/q234_apply_all_summary.py   出力: results/q234_apply_all_instant.csv・_chain.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
import q_common as q
_src = open(os.path.join(HERE, "q208_funded_non_monday_legs.py"), encoding="utf-8").read().split("\nrows = []\nfor a in cfg")[0]; n8 = {"__name__": "q208_head", "__file__": os.path.join(HERE, "q208_funded_non_monday_legs.py")}; exec(compile(_src, "q208_head", "exec"), n8)
cfg, table0, account_items, paths_fac, weak_flags, states_h1, WFN, build, P0, PM, P1 = (n8[k] for k in ("cfg", "table", "account_items", "paths_fac", "weak_flags", "states_h1", "WFN", "build", "P0", "PM", "P1"))
LV = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.625, 0.75, 0.875, 1.0]); n8["GRID"] = LV; NP = 20000; K = paths_fac.__globals__["K"]; X20 = 16
EXIT = {"fx": False, "idx": False}; _MX = {}; _FL = {}
_V = pd.read_csv("data_ext/VIX_History.csv"); _V["d"] = pd.to_datetime(_V["DATE"]); VIX = _V.set_index("d")["CLOSE"].sort_index().astype(float)
def hot(d):
    v = VIX.reindex([pd.Timestamp(d) - pd.Timedelta(days=3)], method="ffill").values[0]; return bool(v == v and v > 25)
def flags_of(s, idx):
    if (s, idx) not in _FL:
        dts = [pd.Timestamp(d) for d in table0(s, idx)[0].date.unique()]; hit, valid = weak_flags(s, states_h1, dts, WFN); _FL[(s, idx)] = {d: bool(h and v) for d, h, v in zip(dts, hit, valid)}
    return _FL[(s, idx)]
def table_x(sym, idx):
    if not EXIT["idx" if idx else "fx"]: return table0(sym, idx)
    mode = EXIT["idx" if idx else "fx"]
    if (sym, idx, mode) in _MX: return _MX[(sym, idx, mode)]
    M, res = table0(sym, idx); Rk = res[K]; weak = flags_of(sym, idx); o = q.load(sym)["open"]; mark = Rk["mark"].copy(); worst = Rk["worst"].copy(); r = Rk["r"].copy(); stop = Rk["stop"].copy(); n_ch = 0
    for i, (d, t, off) in enumerate(zip(M.date.values, M.t.values, M.off.values)):
        d = pd.Timestamp(d); t = pd.Timestamp(t)
        if (hot(d) if mode == "E1" else weak.get(d, False)) or stop[i] < X20 or off >= X20: continue
        e = o.get(t, np.nan); o20 = o.get(d + pd.Timedelta(hours=20), np.nan)
        if e != e or o20 != o20: continue
        r20 = float(o20) / float(e) - 1 - float(q.cost(sym, [float(e)])[0]); mark[i, X20:] = r20; worst[i, X20:] = r20; r[i] = r20; stop[i] = X20; n_ch += 1
    res2 = dict(res); res2[K] = dict(Rk, mark=mark, worst=worst, r=r, stop=stop); _MX[(sym, idx, mode)] = (M, res2); print(f"  [20 UTC 決済 {mode}] {sym}: {n_ch} / {len(M)} ショット", flush=True); return _MX[(sym, idx, mode)]
paths_fac.__globals__["table"] = table_x
a = [x for x in cfg["accounts"] if "11988011" in x["name"]][0]; aid, items, cap, g = account_items(a); mdd = float(a["mdd"]); tot = sum(w for s, i, w in items); START = 20338.37 / 2e4 - 1; ARM = 0.02; KEEP = 0.10; MM = 1.875
print("Instant の構成:", [(s, i, round(w / tot * MM, 4)) for s, i, w in items], "cap", cap, "guard", g)
fxs = [(s, w) for s, i, w in items if not i]; ixs = [(s, w) for s, i, w in items if i]; SWAP = {"NAS100": "US30", "US500": "JP225"}
def fac_state(s, idx, lo): return {d: (1.0 if wk else lo) for d, wk in flags_of(s, idx).items()}
def sim(T, cols, smin, weeks, n_paths, seed=187):
    pnl, fired = T[0][:, cols], T[1][:, cols]; n = pnl.shape[1]; rng = np.random.default_rng(seed); c = np.full(n_paths, START); hwm = np.full(n_paths, max(START, 0.0)); alive = np.ones(n_paths, bool); fires = np.zeros(n_paths, int); paid = np.zeros(n_paths); out = {}
    for w in range(weeks):
        if w % 4 == 0:
            fires[:] = 0
            if w > 0: pay = np.where(alive, np.maximum(c - KEEP, 0.0), 0.0); paid += pay; c = c - pay
        floor = np.minimum(hwm - mdd, 0.0); idx = rng.integers(0, n, n_paths); s = np.clip((c - floor) / mdd, smin, 1.0); gi = np.abs(LV[None, :] - s[:, None]).argmin(axis=1)
        act = alive & (fires < 2); c = c + np.where(act, pnl[gi, idx], 0.0); fires += np.where(act, fired[gi, idx], 0); alive &= ~(c <= floor + ARM); hwm = np.maximum(hwm, c)
        if w + 1 in (52, 260, 520): out[w + 1] = (float(alive.mean()) * 100, float(paid.mean()) * 100)
    return out
# 形: (表示名, 指数の銘柄の差し替え, 指数に F を掛けるか, 円クロスの線の上を 20 UTC 決済にするか)
V = [("現行", False, False, False), ("E1 円クロスの決済を VIX で切り替え", False, False, "E1"), ("V1 指数を US30 + JP225 の F に差し替え", True, True, False), ("E1 + V1(すべて適用)", True, True, "E1")]
rows = []
for nm, swap, fidx, m3 in V:
    it = [(s, False, w / tot * MM) for s, w in fxs] + [((SWAP[s] if swap else s), True, w / tot * MM) for s, w in ixs]; fac = {(s, False): fac_state(s, False, 0.5) for s, w in fxs}
    if fidx: fac.update({(s, True): fac_state(s, True, 0.5) for s, i, w in it if i})
    EXIT["fx"] = m3; EXIT["idx"] = fidx; T, dates = build(lambda lv: paths_fac([(sy, ix, w * lv) for sy, ix, w in it], cap, fac, P0, P1), g, None); EXIT["fx"] = EXIT["idx"] = False; dates = pd.DatetimeIndex(dates); call = np.arange(len(dates)); c2 = call[dates < PM]
    r = dict(variant=nm, weeks=len(dates), wk_mean=round(float(T["cl"][0][-1].mean()) * 100, 3), wk_sd=round(float(T["cl"][0][-1].std()) * 100, 3), guard_lo=round(float((T["lo"][1][-1] > 0).mean()) * 100, 2))
    for tag in ("lo", "cl"):
        m = sim(T[tag], call, 0.5, 520, NP); m2 = sim(T[tag], c2, 0.5, 260, 10000); r.update({f"s1_{tag}": m[52][0], f"s5_{tag}": m[260][0], f"s10_{tag}": m[520][0], f"p5_{tag}": m[260][1], f"p10_{tag}": m[520][1], f"w2s5_{tag}": m2[260][0], f"w2p5_{tag}": m2[260][1]})
    rows.append(r); print("done", nm, flush=True)
D = pd.DataFrame(rows)
for k in ("s1", "s5", "s10", "p5", "p10", "w2s5", "w2p5"): D[k] = D[[f"{k}_lo", f"{k}_cl"]].min(axis=1).round(1)
b = D.iloc[0]; D["verdict"] = ["—"] + [("変更候補" if ((v.s10 >= b.s10 + 3.0 and v.p10 >= b.p10) or (v.p10 >= b.p10 + 3.0 and v.s10 >= b.s10 - 1.0 and v.w2s5 >= b.w2s5 - 1.0)) else "現行どおり") for _, v in D.iloc[1:].iterrows()]
D.to_csv("results/q234_apply_all_instant.csv", index=False); pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 60)
print(D[["variant", "weeks", "wk_mean", "wk_sd", "guard_lo", "s1", "s5", "s10", "w2s5", "p5", "p10", "w2p5", "verdict"]].to_string(index=False))

# ---------------- (b) 口座ごとのつなぎ ----------------
import json
CF = json.load(open("config/portfolio_current.json")); BAL = {a["name"]: a["balance_jpy"] for a in CF["accounts"]}
FA = pd.read_csv("results/q233_exit_switch_funded.csv"); EV = pd.read_csv("results/q233_exit_switch_eval.csv"); PK = pd.read_csv("results/q233_exit_switch_pick.csv")
for k in ("s10", "p10", "w2s5", "w2p5"): FA[k] = FA[[f"{k}_lo", f"{k}_cl"]].min(axis=1)
M0, M1 = "現行(全通貨 24h)", "E1(VIX ≤ 25 は全通貨 20 UTC)"
def ev(acct, stage, mode): x = EV[(EV.acct == acct) & (EV.stage == stage) & (EV["mode"] == mode)].iloc[0]; return (x.reach_W1 + x.reach_W2) / 200.0, (x.fail_W1 + x.fail_W2) / 2.0
def fu(acct, mode): x = FA[(FA.acct == acct) & (FA["mode"] == mode)].iloc[0]; return x.s10, x.p10
def cand(part, scene): v = PK[(PK.part.str.strip() == part) & (PK.scene == scene)].verdict.iloc[0]; return v.startswith("変更候補")
# 口座, config 名, [(評価の acct, stage)], 本口座後の構成名
CH = [("FTMO 0397", "FTMO 50k 521100397", [("FTMO 0397", "いま"), ("FTMO 50k", "次")], "FTMO 50k ×2"), ("FTMO 7058", "FTMO 50k 531407058", [("FTMO 7058", "いま"), ("FTMO 50k", "次")], "FTMO 50k ×2"),
      ("宝くじ", "宝くじ 531343523", [("宝くじ", "いま"), ("宝くじ", "次")], "宝くじ"), ("1-Step", "1-Step 531466484", [("1-Step", "いま")], "1-Step"),
      ("トパーズ", "トパーズ 6104739", [("トパーズ", "いま"), ("トパーズ", "次(6 倍)")], "トパーズ"), ("ルビー", "ルビー 6104736", [("ルビー", "いま"), ("ルビー", "次(6.3 倍)")], "ルビー / パール"),
      ("パール", "パール 6071612", [("パール", "いま"), ("パール", "次")], "ルビー / パール"), ("FN 14074882", "FN 14074882", [("FN 14074882", "いま"), ("FN 14074882", "次")], "FN 14074882")]
out = []
for nm, cn, stages, fn in CH:
    r = dict(acct=nm, balance_man=BAL[cn] / 1e4)
    for tag, pick in (("現行", lambda part, scene: M0), ("すべて適用", lambda part, scene: M1), ("候補のみ", lambda part, scene: (M1 if cand(part, scene) else M0))):
        p = 1.0; fl = []
        for a_, st in stages: rc, f_ = ev(a_, st, pick("B 評価中", f"{a_}・{st}")); p *= rc; fl.append(f_)
        s10, p10 = fu(fn, pick("A 本口座後", fn)); r.update({f"{tag}_通過率%": round(p * 100, 1), f"{tag}_評価の失格%": "・".join(f"{x:.0f}" for x in fl), f"{tag}_10年存続%": round(s10, 1), f"{tag}_10年出金%": round(p10, 1), f"{tag}_期待出金%": round(p * p10, 1), f"{tag}_期待出金_万円": round(p * p10 / 100 * BAL[cn] / 1e4, 0)})
    out.append(r)
b, all_ = D.iloc[0], D.iloc[3]; BI = BAL["FN Instant 11988011"] / 1e4; ri = {"acct": "FN Instant(本番中)", "balance_man": BI}
for tag, x in (("現行", b), ("すべて適用", all_), ("候補のみ", all_)): ri.update({f"{tag}_通過率%": 100.0, f"{tag}_10年存続%": x.s10, f"{tag}_10年出金%": x.p10, f"{tag}_期待出金%": x.p10, f"{tag}_期待出金_万円": round(x.p10 / 100 * BI, 0)})
out.append(ri); C = pd.DataFrame(out); tot = {"acct": "合計(FN 14166201 を除く)", "balance_man": C.balance_man.sum()}
for tag in ("現行", "すべて適用", "候補のみ"): tot[f"{tag}_期待出金_万円"] = C[f"{tag}_期待出金_万円"].sum()
C = pd.concat([C, pd.DataFrame([tot])], ignore_index=True); C.to_csv("results/q234_apply_all_chain.csv", index=False)
print("\n== (b) 口座ごとのつなぎ(到達率 = 2 窓の平均。出金は額面比 %・分配前。金額は参考値) ==")
for tag in ("現行", "すべて適用", "候補のみ"): print(f"-- {tag} --"); print(C[["acct", "balance_man"] + [c for c in C.columns if c.startswith(tag + "_")]].to_string(index=False))
x0, x1 = fu("FN 14166201", M0), fu("FN 14166201", M1); print(f"\nFN 14166201(通過した場合の本口座後): 現行 10 年存続 {x0[0]:.1f}%・出金 +{x0[1]:.1f}% → E1 {x1[0]:.1f}%・+{x1[1]:.1f}%")
