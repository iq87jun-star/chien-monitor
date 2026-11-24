# -*- coding: utf-8 -*-
"""docs/244 Q281(2026-11-24 登録「登録して実行」・セル 9): 月曜の指数を早く建てる形を、評価中の口座の到達・失格で確かめる。
口座: トパーズ いまの段階 / トパーズ 次の段階(Q233 と同じ計算 = build_full + sim_eval)、1-Step いまの状態(Q271 と同じ口座モデル = q276 のモジュールの episode・金あり)。
型: 指数の建て方 = 8 UTC・24 時間 / 8 UTC・18 時間 / 寄り付きの 2 時間前・24 時間(損切り 3.0・利確なし)。円クロスは現行のまま(既存の表)。基準 = 現行。
判定: Q233 の ev_ok。提案に進める条件: 主の型(8 UTC・24 時間)が 3 口座すべてで悪化せず、少なくとも 1 口座で ev_ok。
照合: 現行の設定で既存の計算と表が一致・1-Step の現行が Q271 の行と一致。
使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q281_mon_index_early_entry_eval_accounts.py <累積セル数>   出力: results/q281_mon_index_early_entry_eval.csv"""
import os, sys
_ARGV = list(sys.argv)
import q280_mon_index_detail_grid_funded as x
import q276_v4_reversal_account_model as e
m = x.m; np, pd, q, n3, n5 = m.np, m.pd, m.q, m.n3, e.n5; G = m.G; us_dst = m.us_dst
VARS = (("8 UTC・24 時間", ("8 UTC", 24, 3.0, None)), ("8 UTC・18 時間", ("8 UTC", 18, 3.0, None)), ("寄り付きの 2 時間前・24 時間", ("寄り付きの 2 時間前", 24, 3.0, None))); VAR = {"v": x.BASE}
_RK = {}
def risk_of(sym, var):
    """table_i と同じ順・同じ条件で、1 回ごとのリスク(損切りの幅 ÷ 建値 + コスト)を返す。"""
    if (sym, var) in _RK: return _RK[(sym, var)]
    ent, H, k, tp = var; out = []
    for r in x.raw(sym):
        a = x.hour_of(ent, r["d"]) - 4; b = a + H; at = r["atr"][a]
        if np.isnan(r["o"][a]) or np.isnan(r["o"][b]) or np.isnan(at): continue
        en = float(r["o"][a]); out.append(k * float(at) / en + float(q.cost(sym, [en])[0]))
    _RK[(sym, var)] = np.array(out); return _RK[(sym, var)]
def make_paths(orig_table, K0):
    def paths_y(items, cap, fac, p0, p1):
        """既存の paths_fac と同じ(cap つき)。為替は既存の表、指数は VAR の細部の表。"""
        parts = []; TB = {}
        for s, idxf, w in items:
            if idxf: Mt, R0 = x.table_i(s, VAR["v"]); Rk = dict(R0); Rk["risk"] = risk_of(s, VAR["v"])
            else: Mt, res = orig_table(s, False); Rk = dict(res[K0]); Rk["close"] = np.minimum(Rk["stop"], Mt["off"].values + 24).astype(int)
            TB[f"{s}|{idxf}"] = Rk; p = Mt.copy(); p["w"] = w / p.nshots
            if (s, idxf) in fac: p["w"] = p.w * p.date.map(lambda d: fac[(s, idxf)].get(d, 1.0)).values
            p["risk_w"] = p.w * Rk["risk"]; p["stop"] = Rk["stop"]; p["close"] = Rk["close"]; p["i"] = np.arange(len(p)); p["key"] = f"{s}|{idxf}"; parts.append(p)
        S = pd.concat(parts); S = S[(S.date >= p0) & (S.date <= p1)].sort_values(["date", "t"]).reset_index(drop=True); f = np.ones(len(S))
        if cap:
            C, V = cap
            for d, g in S.groupby("date"):
                used = []
                for i in g.index:
                    r = S.risk_w[i]
                    if r <= 0: f[i] = 0.0; continue
                    room = C - sum(xx for stp, xx in used if V == "B" or stp > S.off[i]); fi = 1.0 if r <= room else (room / r if room >= 0.1 * r else 0.0); f[i] = fi; used.append((S.stop[i], r * fi))
        S["wf"] = S.w * f; out = []
        for d, g in S.groupby("date"):
            gb = (21 if us_dst(d) else 22) - 4; tot = {"lo": np.zeros(G), "cl": np.zeros(G)}; met = {"lo": np.zeros(G), "cl": np.zeros(G)}
            for key, gg in g.groupby("key"):
                Rk = TB[key]
                for i, wf, close in zip(gg.i.values, gg.wf.values, gg.close.values):
                    if wf == 0: continue
                    for tag, arr in (("lo", Rk["worst"][i]), ("cl", Rk["mark"][i])):
                        a = arr * wf; tot[tag] += a; bb = a.copy()
                        if close < gb: bb[gb:] = 0.0
                        met[tag] += bb
            out.append(dict(d=d, gb=gb, tot=tot, met=met, fin=float(tot["cl"][-1])))
        return out
    return paths_y
def ev_ok(b, v): return bool(all(v[f"reach_{w}"] >= b[f"reach_{w}"] - 1.0 and v[f"fail_{w}"] <= b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")) and any(v[f"reach_{w}"] >= b[f"reach_{w}"] + 2.0 or v[f"fail_{w}"] <= b[f"fail_{w}"] - 2.0 for w in ("W1", "W2")))
def not_worse(b, v): return bool(all(v[f"reach_{w}"] >= b[f"reach_{w}"] - 1.0 and v[f"fail_{w}"] <= b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")))
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 9; rows = []
    # ---------- トパーズ(Q233 と同じ計算) ----------
    PF0 = n3["paths_fac"]; PY3 = make_paths(m.ORIG_TABLE, m.K0); sim_eval = n3["sim_eval"]
    for stage, mm, skew, tilt, smin, start, target in (("トパーズ いまの段階", 8.0, False, False, None, 36438662 / 35e6 - 1, 0.08), ("トパーズ 次の段階(6 倍)", 6.0, True, True, 0.5, 0.0, 0.06)):
        items, cap, g = m.norm_items("6104739"); fac = m.make_fac(items, skew, 0.5 if tilt else None)
        def run(var):
            VAR["v"] = var; T, dates = m.build_full(items, None, g, fac, mm); r = {}
            for wn, sel in (("W1", np.array([d >= m.PM for d in dates])), ("W2", np.array([d < m.PM for d in dates]))):
                cols = np.arange(len(dates))[sel]; rr = [sim_eval(T[tag], cols, start, target, 0.10, 0.01, smin, False) for tag in ("lo", "cl")]; r[f"reach_{wn}"] = round(min(z[0] for z in rr), 1); r[f"fail_{wn}"] = round(max(z[1] for z in rr), 1); r[f"weeks_{wn}"] = max((z[2] or 0) for z in rr)
            return r, T
        n3["paths_fac"] = PF0; T0, _ = m.build_full(items, None, g, fac, mm); n3["paths_fac"] = PY3; b, Tb = run(x.BASE)
        same = all(np.allclose(T0[tag][i], Tb[tag][i]) for tag in ("lo", "cl") for i in range(3)); print(f"照合 {stage}: 現行の表が既存の計算と一致 = {same}・現行 {b}", flush=True); assert same
        rows.append(dict(acct=stage, variant="現行(寄り付き・24 時間)", cells=0, verdict="基準", not_worse=True, **b))
        for nm, var in VARS:
            v, _ = run(var); rows.append(dict(acct=stage, variant=nm, cells=1, verdict="変更候補" if ev_ok(b, v) else "現行どおり", not_worse=not_worse(b, v), **v)); print(f"  {stage} {nm}: {v}", flush=True)
    # ---------- 1-Step(Q271 と同じ口座モデル・金あり) ----------
    PFE = n5["paths_fac"]; GE = PFE.__globals__; PY5 = make_paths(GE["table"], GE["K"]); key = "531466484"
    items, cap, g = e.norm_items(key); _, it0, _, _ = e.account_items(e.acct(key)); mm = sum(w for s, i, w in it0 if not i); fac = e.make_fac(items, True, None)
    okA = ~np.isnan(e.GA["A"][2]); idx = np.arange(e.W); STARTS = {"W1": [s for s in idx if e.MONS[s] >= e.PM and s + 52 <= e.W and okA[s]], "W2": [s for s in idx if e.MONS[s] < e.PM and s + 52 <= e.W and e.MONS[s + 51] < e.PM and okA[s]]}
    kw = dict(start=97826.72 / 1e5 - 1, target=0.10, mdd=0.10, pad=0.01, smin=None, trail=True, g=g, swm=-52.0, wg0=0.36, carry0=0.0, wg_re=0.36, integ=True)
    def run1(var, pf):
        VAR["v"] = var; n5["paths_fac"] = pf; e.MODE["k"] = None; ML0 = e.mon_levels(items, cap, fac, mm, [e.TOP]); ML = {li: ML0[e.TOP] for li in range(len(e.LV))}; e.setup(102813.25 / 1e5 - 1, 2); r = e.one(ML, STARTS, kw, 0.0); return {k: r[k] for k in r if not k.startswith("v4")}
    b0 = run1(x.BASE, PFE); b = run1(x.BASE, PY5); print(f"照合 1-Step: 既存の計算 {b0} / 今回の現行 {b}(Q271: 92.9 / 7.1・30.6 / 55.1)一致 = {b0 == b}", flush=True); assert b0 == b
    rows.append(dict(acct="1-Step いまの状態", variant="現行(寄り付き・24 時間)", cells=0, verdict="基準", not_worse=True, **b))
    for nm, var in VARS:
        v = run1(var, PY5); rows.append(dict(acct="1-Step いまの状態", variant=nm, cells=1, verdict="変更候補" if ev_ok(b, v) else "現行どおり", not_worse=not_worse(b, v), **v)); print(f"  1-Step {nm}: {v}", flush=True)
    D = pd.DataFrame(rows); D.to_csv("results/q281_mon_index_early_entry_eval.csv", index=False); assert int(D.cells.sum()) == N
    pd.set_option("display.width", 300); pd.set_option("display.max_columns", 30); pd.set_option("display.max_colwidth", 40)
    print(f"\n== Q281(累積セル {cum} + {N} = {cum + N}・到達 % / 失格 % / 到達までの週・W1 = 2021-08 以降・W2 = 2016-11〜2021-07) =="); print(D[["acct", "variant", "reach_W1", "fail_W1", "weeks_W1", "reach_W2", "fail_W2", "weeks_W2", "not_worse", "verdict"]].to_string(index=False))
    main = D[D.variant == "8 UTC・24 時間"]; ok = bool(main.not_worse.all() and (main.verdict == "変更候補").any())
    print(f"\n判定: 変更候補 {int((D.verdict == '変更候補').sum())} / {N} 件。主の型(8 UTC・24 時間): 悪化しない口座 {int(main.not_worse.sum())} / 3・ev_ok {int((main.verdict == '変更候補').sum())} / 3 → 提案に進める条件を{'満たす' if ok else '満たさない'}")
