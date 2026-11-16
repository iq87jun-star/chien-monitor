# -*- coding: utf-8 -*-
"""docs/244 Q252(診断・セル 0・2026-11-16 登録): スワップを入れても決済の切り替え(E1)が勝つか。Q233 の口座モデルに、月曜の夜を持ち越した建玉へのスワップを加える。
スワップ = (通貨 − 円の政策金利差)/ 360 × 水準(1.0 = 理論値・0.5)。NY の引け(夏 21 UTC・冬 22 UTC)をまたいだ建玉にだけ付ける(それより前の損切り・20 UTC 決済には付けない)。
形 = 現行(24h)・E1・E2。場面 = スワップの付く口座の Q233 の行。モデル・開始残高・乱数・判定は Q233 と同じ(前半をそのまま読み込み、経路にスワップを足すだけ)。
使い方: cd research && python3 -W ignore queue/q252_exit_switch_with_swap.py <A|B>   出力: results/q252_swap_funded.csv / _eval.csv"""
import os, sys
PART = sys.argv[1] if len(sys.argv) > 1 else "A"; HERE = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(HERE, "q233_exit_switch_line_vs_vix_account_model.py"), encoding="utf-8").read().split("\n# ---------------- (A) 本口座後")[0]; n3 = {"__name__": "q233_head", "__file__": os.path.join(HERE, "q233_exit_switch_line_vs_vix_account_model.py")}; exec(compile(_src, "q233_head", "exec"), n3)
np, pd, q = n3["np"], n3["pd"], n3["q"]; norm_items, account_items, acct, make_fac, build_full, roll_week, sim_funded, sim_eval, one_week_stats, MODE, PM, NP, table_x, paths_fac, K, MON4 = (n3[k] for k in ("norm_items", "account_items", "acct", "make_fac", "build_full", "roll_week", "sim_funded", "sim_eval", "one_week_stats", "MODE", "PM", "NP", "table_x", "paths_fac", "K", "MON4"))
sys.path.insert(0, HERE)
from q20_wed_swap_carry import rate_series
SW = {"f": 0.0}; _C = {}
def us_dst(d):
    y = d.year; mar = pd.Timestamp(y, 3, 8); mar += pd.Timedelta(days=(6 - mar.dayofweek) % 7); nov = pd.Timestamp(y, 11, 1); nov += pd.Timedelta(days=(6 - nov.dayofweek) % 7); return mar <= d < nov
def table_s(sym, idx):
    """table_x の結果に、NY の引けをまたいだ月曜の建玉へのスワップ(1 晩)を足す。指数とスワップ水準 0 はそのまま。"""
    if idx or SW["f"] == 0.0: return table_x(sym, idx)
    key = (sym, MODE["k"], SW["f"])
    if key in _C: return _C[key]
    M, res = table_x(sym, False); Rk = res[K]; mark = Rk["mark"].copy(); worst = Rk["worst"].copy(); r = Rk["r"].copy(); stop = Rk["stop"]; dts = pd.DatetimeIndex(M.date.values)
    ud = pd.DatetimeIndex(sorted(set(dts))); diff = (rate_series(sym[:3], ud) - rate_series("JPY", ud)).fillna(0.0).reindex(dts).values; n = 0
    for i, d in enumerate(dts):
        off = 17 if us_dst(d) else 18                                    # 04:00 UTC 起点。21:00 UTC = 17、22:00 UTC = 18
        if stop[i] <= off: continue
        s = SW["f"] * diff[i] / 100.0 / 360.0; r[i] += s; mark[i, off:] += s; worst[i, off:] += s; n += 1
    res2 = dict(res); res2[K] = dict(Rk, mark=mark, worst=worst, r=r); _C[key] = (M, res2); print(f"  [スワップ ×{SW['f']}] {sym} {MODE['k']}: {n} / {len(M)} ショットに付与・平均 {np.mean(SW['f'] * diff / 360.0) * 100:.2f} bps / 晩", flush=True); return _C[key]
paths_fac.__globals__["table"] = table_s
MODES = (("現行(24h)", None), ("E1", "E1"), ("E2", "E2")); FS = (1.0, 0.5)
def fund_ok(b, v): return bool((v.s10 >= b.s10 + 3.0 and v.p10 >= b.p10) or (v.p10 >= b.p10 + 3.0 and v.s10 >= b.s10 - 1.0 and v.w2s5 >= b.w2s5 - 1.0))
def ev_ok(b, v): return bool(all(v[f"reach_{w}"] >= b[f"reach_{w}"] - 1.0 and v[f"fail_{w}"] <= b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")) and any(v[f"reach_{w}"] >= b[f"reach_{w}"] + 2.0 or v[f"fail_{w}"] <= b[f"fail_{w}"] - 2.0 for w in ("W1", "W2")))
pd.set_option("display.width", 300); pd.set_option("display.max_rows", 400); pd.set_option("display.max_columns", 40)
if PART == "A":
    A = [("FTMO 50k ×2", "521100397", None, None, False, False, 0.5, 0.01, 3.75, 0.0), ("宝くじ", "531343523", None, None, True, False, 0.5, 0.005, 4.0, 0.0), ("1-Step", "531466484", None, "acct", True, True, None, 0.01, 2.43, 0.0), ("FN 14074882", "14074882", None, (0.024, "A"), True, False, 0.5, 0.01, 4.0, 0.0)]
    rows = []
    for nm, key, itov, capov, skew, trail, lo, pad, mm, rw in A:
        items, cap, g = norm_items(key); cap = cap if capov == "acct" else capov; fac = make_fac(items, skew, lo)
        for f in FS + ((0.0,) if nm == "宝くじ" else ()):
            for mn, md in MODES:
                SW["f"] = f; MODE["k"] = md; T, dates = build_full(items, cap, g, fac, mm); MODE["k"] = None; SW["f"] = 0.0; call = np.arange(len(dates)); c2 = call[np.array([d < PM for d in dates])]; add = np.zeros(len(dates))
                r = dict(acct=nm, swap=f, mode=mn, **one_week_stats(T, dates))
                for tag in ("lo", "cl"):
                    m = sim_funded(T[tag], add, call, 0.10, pad, trail, 520, NP); m2 = sim_funded(T[tag], add, c2, 0.10, pad, trail, 260, 10000); r.update({f"s1_{tag}": m[52][0], f"s5_{tag}": m[260][0], f"s10_{tag}": m[520][0], f"p5_{tag}": m[260][1], f"p10_{tag}": m[520][1], f"w2s5_{tag}": m2[260][0], f"w2p5_{tag}": m2[260][1]})
                rows.append(r)
        print("A done", nm, flush=True)
    D = pd.DataFrame(rows)
    for c in ("s1", "s5", "s10", "p5", "p10", "w2s5", "w2p5"): D[c] = D[[f"{c}_lo", f"{c}_cl"]].min(axis=1).round(1)
    D["verdict"] = ""
    for (nm, f), x in D.groupby(["acct", "swap"], sort=False):
        for i in x.index[1:]: D.loc[i, "verdict"] = "変更候補" if fund_ok(x.iloc[0], D.loc[i]) else "現行どおり"
    D.to_csv("results/q252_swap_funded.csv", index=False); print("\n== 本口座後(存続 1 / 5 / 10 年 %・2016〜21 年のみ 5 年存続・累計出金 5 / 10 年 %・2016〜21 年のみ 5 年出金) =="); print(D[["acct", "swap", "mode", "wk_mean_cl", "wk_sd_cl", "s1", "s5", "s10", "w2s5", "p5", "p10", "w2p5", "verdict"]].to_string(index=False))
else:
    B = [("FTMO 0397", "521100397", "いま", 6.0, False, False, None, False, 54835 / 5e4 - 1, 0.10, 0.01, None), ("FTMO 7058", "531407058", "いま", 6.0, False, False, None, False, 53683 / 5e4 - 1, 0.10, 0.01, None), ("FTMO 50k", "521100397", "次", 6.0, False, True, 0.5, False, 0.0, 0.05, 0.01, None),
         ("宝くじ", "531343523", "いま", 8.0, True, False, 0.5, False, 97354 / 1e5 - 1, 0.10, 0.005, None), ("宝くじ", "531343523", "次", 8.0, True, True, 0.5, False, 0.0, 0.05, 0.005, None), ("1-Step", "531466484", "いま", None, True, False, None, True, 102722 / 1e5 - 1, 0.10, 0.01, "acct"),
         ("FN 14074882", "14074882", "いま", 4.0, True, False, None, False, 93966 / 1e5 - 1, 0.08, 0.003, None), ("FN 14074882", "14074882", "次", 4.0, True, False, None, False, 0.0, 0.05, 0.003, None)]
    rows = []
    for nm, key, stage, mm, skew, tilt, smin, trail, start, target, pad0, capm in B:
        items, cap, g = norm_items(key); cap = cap if capm == "acct" else None
        if mm is None: _, it0, _, _ = account_items(acct(key)); mm = sum(w for s, i, w in it0 if not i)
        fac = make_fac(items, skew, 0.5 if tilt else None)
        for f in FS:
            for mn, md in MODES:
                SW["f"] = f; MODE["k"] = md; T, dates = build_full(items, cap, g, fac, mm); MODE["k"] = None; SW["f"] = 0.0; r = dict(acct=nm, stage=stage, swap=f, mode=mn, **one_week_stats(T, dates))
                for wn, sel in (("W1", np.array([d >= PM for d in dates])), ("W2", np.array([d < PM for d in dates]))):
                    cols = np.arange(len(dates))[sel]; rr = [sim_eval(T[tag], cols, start, target, 0.10, pad0, smin, trail) for tag in ("lo", "cl")]
                    r[f"reach_{wn}"] = round(min(x[0] for x in rr), 1); r[f"fail_{wn}"] = round(max(x[1] for x in rr), 1); r[f"weeks_{wn}"] = max((x[2] or 0) for x in rr)
                rows.append(r)
        print("B done", nm, stage, flush=True)
    D = pd.DataFrame(rows); D["verdict"] = ""
    for (nm, st, f), x in D.groupby(["acct", "stage", "swap"], sort=False):
        for i in x.index[1:]: D.loc[i, "verdict"] = "変更候補" if ev_ok(x.iloc[0], D.loc[i]) else "現行どおり"
    D.to_csv("results/q252_swap_eval.csv", index=False); print("\n== 評価中(到達 % / 失格 % / 中央の週数) =="); print(D[["acct", "stage", "swap", "mode", "wk_mean_cl", "wk_sd_cl", "reach_W1", "fail_W1", "weeks_W1", "reach_W2", "fail_W2", "weeks_W2", "verdict"]].to_string(index=False))
