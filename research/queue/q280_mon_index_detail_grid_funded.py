# -*- coding: utf-8 -*-
"""docs/244 Q280(2026-11-24 登録「登録して実行」・セル 191): 月曜の指数(NAS100・US500)の細部を総当たりし、本口座の物差しで順位を付ける。
口座の物差し: トパーズの本口座後の構成(円クロス 3.0 倍 + 指数 + ロール 4.5 倍・SKEW・200 日線の上 0.5 倍・縮小の下限 0.25・ガード 2.8%)。計算は Q278 と同じ部品(q278 のモジュール)。円クロスは現行のまま。
指数の細部(192 通り): 建てる時刻 {寄り付き後の最初の正時(現行), その 2 時間前, 8 UTC, 4 UTC} × 持つ時間 {6, 12, 18, 24(現行)} × 損切り {2, 3(現行), 4 × ATR24} × 利確 {なし(現行), 2, 3, 4 × ATR24}。
順位・採用の線は Q278 と同じ。照合: 現行の設定で既存の計算と表が一致。
使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q280_mon_index_detail_grid_funded.py <累積セル数>   出力: results/q280_mon_index_detail_grid.csv"""
import os, sys, itertools, time
_ARGV = list(sys.argv)
import q278_mon_detail_grid_funded_ranking as m
np, pd, q, n3 = m.np, m.pd, m.q, m.n3; G = m.G; us_dst = m.us_dst
ENT = ("寄り付き(現行)", "寄り付きの 2 時間前", "8 UTC", "4 UTC"); HOLDS = (6, 12, 18, 24); SLS = (2.0, 3.0, 4.0); TPS = (None, 2.0, 3.0, 4.0); BASE = ("寄り付き(現行)", 24, 3.0, None); EORD = ["4 UTC", "8 UTC", "寄り付きの 2 時間前", "寄り付き(現行)"]
def hour_of(ent, d):
    o = 14 if us_dst(d) else 15
    return {"寄り付き(現行)": o, "寄り付きの 2 時間前": o - 2, "8 UTC": 8, "4 UTC": 4}[ent]
_RAW = {}
def raw(sym):
    if sym in _RAW: return _RAW[sym]
    df = q.load(sym); atr = q.atr24(df); mondays = pd.DatetimeIndex(sorted(set(df.index[df.index.dayofweek == 0].normalize()))); out = []
    for d in mondays:
        g0 = d + pd.Timedelta(hours=4); grid = pd.date_range(g0, periods=G + 25, freq="h"); sub = df.loc[g0:grid[-1]]
        if len(sub) == 0: continue
        out.append(dict(d=d, grid=grid, o=sub["open"].reindex(grid).values, lo=sub["low"].reindex(grid).values, hi=sub["high"].reindex(grid).values, c=sub["close"].reindex(grid).values, atr=np.array([atr.get(t, np.nan) for t in grid[:14]])))
    _RAW[sym] = out; return out
_TI = {}
def table_i(sym, var):
    key = (sym, var)
    if key in _TI: return _TI[key]
    ent, H, k, tp = var; meta = []; rr, st, cz, mk, wo = [], [], [], [], []
    for x in raw(sym):
        o_, lo_, hi_, c_ = x["o"], x["lo"], x["hi"], x["c"]; h = hour_of(ent, x["d"]); a = h - 4; b = a + H; at = x["atr"][a]
        if np.isnan(o_[a]) or np.isnan(o_[b]) or np.isnan(at): continue
        e = float(o_[a]); c = float(q.cost(sym, [e])[0]); cl = pd.Series(c_[a:b]).ffill().fillna(e).values; lw = np.where(np.isnan(lo_[a:b]), cl, lo_[a:b]); hw = np.where(np.isnan(hi_[a:b]), cl, hi_[a:b])
        sd = k * float(at); hs = np.where(lw <= e - sd)[0]; js = int(hs[0]) if len(hs) else 10**6
        if tp is None: jt = 10**6; td = np.nan
        else: td = tp * float(at); ht = np.where(hw >= e + td)[0]; jt = int(ht[0]) if len(ht) else 10**6
        if js <= jt and js < 10**6: j = js; r = -sd / e - c
        elif jt < js: j = jt; r = td / e - c
        else: j = -1; r = float(o_[b]) / e - 1 - c
        mm_ = cl / e - 1 - c; w = lw / e - 1 - c
        if j >= 0: mm_[j:] = r; w[j:] = r
        mark = np.zeros(G); worst = np.zeros(G); n_in = min(b, G) - a; mark[a:a + n_in] = mm_[:n_in]; worst[a:a + n_in] = w[:n_in]
        if b < G: mark[b:] = r; worst[b:] = r
        meta.append((x["d"], x["grid"][a], a, 1)); rr.append(r); st.append(a + j if j >= 0 else 10**6); cz.append(min(a + j if j >= 0 else 10**6, a + H)); mk.append(mark); wo.append(worst)
    M = pd.DataFrame(meta, columns=["date", "t", "off", "nshots"]); _TI[key] = (M, dict(r=np.array(rr), stop=np.array(st, dtype=float), close=np.array(cz, dtype=int), mark=np.array(mk), worst=np.array(wo))); return _TI[key]
VAR = {"v": BASE}; FXVAR = (m.ENTRY[m.BASE[0]],) + tuple(m.BASE[1:])
def paths_x(items, cap, fac, p0, p1):
    """Q278 の paths_v と同じ。為替は現行の細部、指数は VAR の細部の表。"""
    assert cap is None; parts = []; TB = {}
    for s, idxf, w in items:
        Mt, Rk = table_i(s, VAR["v"]) if idxf else m.table_v(s, FXVAR); TB[f"{s}|{idxf}"] = Rk; p = Mt.copy(); p["w"] = w / p.nshots
        if (s, idxf) in fac: p["w"] = p.w * p.date.map(lambda d: fac[(s, idxf)].get(d, 1.0)).values
        p["close"] = Rk["close"]; p["i"] = np.arange(len(p)); p["key"] = f"{s}|{idxf}"; parts.append(p)
    S = pd.concat(parts); S = S[(S.date >= p0) & (S.date <= p1)].sort_values(["date", "t"]).reset_index(drop=True); out = []
    for d, g in S.groupby("date"):
        gb = (21 if us_dst(d) else 22) - 4; tot = {"lo": np.zeros(G), "cl": np.zeros(G)}; met = {"lo": np.zeros(G), "cl": np.zeros(G)}
        for key, gg in g.groupby("key"):
            Rk = TB[key]
            for i, wf, close in zip(gg.i.values, gg.w.values, gg.close.values):
                if wf == 0: continue
                for tag, arr in (("lo", Rk["worst"][i]), ("cl", Rk["mark"][i])):
                    a = arr * wf; tot[tag] += a; bb = a.copy()
                    if close < gb: bb[gb:] = 0.0
                    met[tag] += bb
        out.append(dict(d=d, gb=gb, tot=tot, met=met, fin=float(tot["cl"][-1])))
    return out
def neighbors(v):
    e, H, k, tp = v; out = []
    i = EORD.index(e); out += [(EORD[j], H, k, tp) for j in (i - 1, i + 1) if 0 <= j < len(EORD)]
    i = HOLDS.index(H); out += [(e, HOLDS[j], k, tp) for j in (i - 1, i + 1) if 0 <= j < len(HOLDS)]
    i = SLS.index(k); out += [(e, H, SLS[j], tp) for j in (i - 1, i + 1) if 0 <= j < len(SLS)]
    i = TPS.index(tp); out += [(e, H, k, TPS[j]) for j in (i - 1, i + 1) if 0 <= j < len(TPS)]
    return out
if __name__ == "__main__":
    cum = int(_ARGV[1]); items, cap, g = m.norm_items("6104739"); fac = m.make_fac(items, True, 0.5); MULT, PAD = 3.0, 0.01; addf = lambda dates: n3["roll_week"](dates, 4.5, g)
    T0, d0 = m.build_full(items, None, g, fac, MULT)                       # 既存の計算(現行)
    n3["paths_fac"] = paths_x; VAR["v"] = BASE; b, Tb = m.evaluate(items, g, fac, MULT, PAD, add=addf)
    same = all(np.allclose(T0[tag][i], Tb[tag][i]) for tag in ("lo", "cl") for i in range(3)); print(f"照合: 現行の設定の表が既存の計算と一致 = {same}・現行 {b}", flush=True); assert same
    res = {}; t0 = time.time(); grid = list(itertools.product(ENT, HOLDS, SLS, TPS))
    for n, v in enumerate(grid):
        VAR["v"] = v; r, _ = m.evaluate(items, g, fac, MULT, PAD, add=addf); res[v] = r
        Mi, Ri = table_i("NAS100", v); Mu, Ru = table_i("US500", v); sel = lambda M_: (M_.date >= m.P0) & (M_.date <= m.P1); res[v]["idx_mean_bps"] = round(float((Ri["r"][sel(Mi).values].mean() + Ru["r"][sel(Mu).values].mean()) / 2) * 1e4, 2)
        if n % 40 == 0: print(f"  {n} / {len(grid)}・{time.time() - t0:.0f} 秒", flush=True)
    okb = {v: (m.win_ok(r, b, "a") and m.win_ok(r, b, "b")) for v, r in res.items()}; rows = []
    for v, r in res.items():
        nb = [x for x in neighbors(v) if x in res]; share = float(np.mean([okb[x] for x in nb])) if nb else 0.0; isb = (v == BASE)
        rows.append(dict(entry=v[0], hold=v[1], sl=v[2], tp=("なし" if v[3] is None else v[3]), **r, ok_w1=m.win_ok(r, b, "a"), ok_w2=m.win_ok(r, b, "b"), nb_share=round(share, 2), cells=0 if isb else 1, verdict="基準" if isb else ("変更候補" if (okb[v] and share >= 0.5) else "現行どおり")))
    D = pd.DataFrame(rows); D["rank_all"] = D["p10"].where(D["s10"] >= b["s10"] - 1.0).rank(ascending=False, method="min"); D["rank_w1"] = D["p5a"].where(D["s5a"] >= b["s5a"] - 1.0).rank(ascending=False, method="min"); D["rank_w2"] = D["p5b"].where(D["s5b"] >= b["s5b"] - 1.0).rank(ascending=False, method="min")
    D.to_csv("results/q280_mon_index_detail_grid.csv", index=False); assert int(D.cells.sum()) == 191
    pd.set_option("display.width", 330); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 300)
    cols = ["entry", "hold", "sl", "tp", "idx_mean_bps", "s10", "p10", "s5a", "p5a", "s5b", "p5b", "guard", "ok_w1", "ok_w2", "nb_share", "rank_all", "rank_w1", "rank_w2", "verdict"]
    print(f"\n== Q280(累積セル {cum} + 191 = {cum + 191}・トパーズ 本口座後・現行 = {BASE}) =="); print("現行:", D[D.verdict == "基準"][cols].to_string(index=False))
    print("\n全期間の順位 上位 15:"); print(D.sort_values("rank_all").head(15)[cols].to_string(index=False))
    print("\n① の順位 上位 10:"); print(D.sort_values("rank_w1").head(10)[cols].to_string(index=False)); print("\n② の順位 上位 10:"); print(D.sort_values("rank_w2").head(10)[cols].to_string(index=False))
    from scipy.stats import spearmanr
    bb = D[D.verdict == "基準"].iloc[0]; print(f"\n順位の相関(①②の p5): {spearmanr(D['p5a'], D['p5b'])[0]:.2f}・現行の順位: 全期間 {bb.rank_all} / ① {bb.rank_w1} / ② {bb.rank_w2}(対象 {int(D.rank_all.notna().sum())} / {int(D.rank_w1.notna().sum())} / {int(D.rank_w2.notna().sum())})・p10 の幅 {D.p10.min():.1f}〜{D.p10.max():.1f}・s10 の幅 {D.s10.min():.1f}〜{D.s10.max():.1f}")
    print(f"① を満たす {int(D.ok_w1.sum())}・② を満たす {int(D.ok_w2.sum())}・両方 {int((D.ok_w1 & D.ok_w2).sum())}・変更候補 {int((D.verdict == '変更候補').sum())} / 191")
    for dim in ("entry", "hold", "sl", "tp"):
        print(f"\n細部ごとの平均({dim}):"); print(D.groupby(dim, sort=False)[["idx_mean_bps", "s10", "p10", "s5a", "p5a", "s5b", "p5b"]].mean().round(1).to_string())
    C = D[D.verdict == "変更候補"].sort_values("p10", ascending=False); print("\n変更候補:" if len(C) else "\n変更候補なし"); print(C[cols].to_string(index=False) if len(C) else "")
