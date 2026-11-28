# -*- coding: utf-8 -*-
"""docs/244 Q278(2026-11-24 登録「登録して実行」扱い・セル 359): 月曜の円クロスの細部(建てる時刻・持つ時間・損切り・利確)を総当たりし、本口座の物差しで順位を付ける。
ユーザー 2026-11-24「利益が出てる口座を本番口座のイメージで…細いディテールを変えて、ランキング上位のものから手法を採用していきたいです」。
口座の物差し: FTMO 50k の本口座後の構成(Mon4 3.75 倍・200 日線の上 0.5 倍・縮小の下限 0.25・ガード 4%・全停止 −9%・4 週ごとに全額出金)。計算は Q223・Q230 と同じ(q233 の頭を使う)。
細部(360 通り): 建てる時刻 {4-6-8-10(現行), 4, 6, 8, 10, 12 UTC} × 持つ時間 {12, 16, 20, 24(現行), 28} × 損切り {2, 3(現行), 4 × ATR24} × 利確 {なし(現行), 2, 3, 4 × ATR24}。
経路は月曜 04:00 UTC からの 37 点(既存と同じ格子)。損切りは 1 時間足の安値、利確は高値で判定。同じ 1 時間に重なったら損切りが先。
出す数字: 全期間の s10・p10、期間別(① 2021-08 以降 ② 2016-11〜2021-07)の s5・p5。安値判定と終値判定の悪い方。
採用の候補: ①② の両方で「p5 ≥ 現行 + 3 かつ s5 ≥ 現行 − 1」または「s5 ≥ 現行 + 3 かつ p5 ≥ 現行」、かつ 1 段だけ違う隣の設定の半分以上が同じ条件を満たす。
照合: 現行の設定で既存の計算(build_full)と表が一致。
使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q278_mon_detail_grid_funded_ranking.py <累積セル数>   出力: results/q278_mon_detail_grid.csv"""
import os, sys, itertools, time
_ARGV = list(sys.argv)
HERE = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(HERE, "q233_exit_switch_line_vs_vix_account_model.py"), encoding="utf-8").read().split("\n# ---------------- (A) 本口座後")[0]; n3 = {"__name__": "q233_head", "__file__": os.path.join(HERE, "q233_exit_switch_line_vs_vix_account_model.py")}; exec(compile(_src, "q233_head", "exec"), n3)
np, pd, q = n3["np"], n3["pd"], n3["q"]; norm_items, make_fac, build_full, sim_funded, run_guard, PM, P0, P1, LV = (n3[k] for k in ("norm_items", "make_fac", "build_full", "sim_funded", "run_guard", "PM", "P0", "P1", "LV"))
PF0 = n3["paths_fac"]; GLOB = PF0.__globals__; G = GLOB["G"]; us_dst = GLOB["us_dst"]; ORIG_TABLE = GLOB["table"]; K0 = GLOB["K"]
ENTRY = {"4-6-8-10(現行)": (4, 6, 8, 10), "4": (4,), "6": (6,), "8": (8,), "10": (10,), "12": (12,)}; HOLDS = (12, 16, 20, 24, 28); SLS = (2.0, 3.0, 4.0); TPS = (None, 2.0, 3.0, 4.0); BASE = ("4-6-8-10(現行)", 24, 3.0, None)
EORDER = ["4", "6", "8", "10", "12"]
# ---------- 月曜ごとの素材(銘柄ごとに 1 回だけ作る) ----------
_RAW = {}
def raw(sym):
    if sym in _RAW: return _RAW[sym]
    df = q.load(sym); atr = q.atr24(df); pip = q.base.pip_size(sym); mondays = pd.DatetimeIndex(sorted(set(df.index[df.index.dayofweek == 0].normalize()))); out = []
    for d in mondays:
        g0 = d + pd.Timedelta(hours=4); grid = pd.date_range(g0, periods=G + 25, freq="h"); sub = df.loc[g0:grid[-1]]
        if len(sub) == 0: continue
        out.append(dict(d=d, grid=grid, o=sub["open"].reindex(grid).values, lo=sub["low"].reindex(grid).values, hi=sub["high"].reindex(grid).values, c=sub["close"].reindex(grid).values, atr=np.array([atr.get(t, np.nan) for t in grid[:10]])))
    _RAW[sym] = (out, pip); return _RAW[sym]
_TV = {}
def table_v(sym, var):
    """var = (建てる時刻の組, 持つ時間, 損切りの倍率, 利確の倍率 or None)。戻り値は既存の table と同じ形 + close(決済の添字)。"""
    key = (sym, var)
    if key in _TV: return _TV[key]
    hours, H, k, tp = var; R, pip = raw(sym); meta = []; rr, st, cz, mk, wo = [], [], [], [], []
    for x in R:
        o_, lo_, hi_, c_ = x["o"], x["lo"], x["hi"], x["c"]
        for h in hours:
            a = h - 4; b = a + H; at = x["atr"][a] if a < len(x["atr"]) else np.nan
            if np.isnan(o_[a]) or np.isnan(o_[b]) or np.isnan(at): continue
            e = float(o_[a]); c = float(q.cost(sym, [e])[0]); cl = pd.Series(c_[a:b]).ffill().fillna(e).values; lw = np.where(np.isnan(lo_[a:b]), cl, lo_[a:b]); hw = np.where(np.isnan(hi_[a:b]), cl, hi_[a:b])
            sd = max(k * float(at), 10 * pip); hs = np.where(lw <= e - sd)[0]; js = int(hs[0]) if len(hs) else 10**6
            if tp is None: jt = 10**6; td = np.nan
            else: td = tp * float(at); ht = np.where(hw >= e + td)[0]; jt = int(ht[0]) if len(ht) else 10**6
            if js <= jt and js < 10**6: j = js; r = -sd / e - c
            elif jt < js: j = jt; r = td / e - c
            else: j = -1; r = float(o_[b]) / e - 1 - c
            m = cl / e - 1 - c; w = lw / e - 1 - c
            if j >= 0: m[j:] = r; w[j:] = r
            mark = np.zeros(G); worst = np.zeros(G); n_in = min(b, G) - a; mark[a:a + n_in] = m[:n_in]; worst[a:a + n_in] = w[:n_in]
            if b < G: mark[b:] = r; worst[b:] = r
            meta.append((x["d"], x["grid"][a], a, len(hours))); rr.append(r); st.append(a + j if j >= 0 else 10**6); cz.append(min(a + j if j >= 0 else 10**6, a + H)); mk.append(mark); wo.append(worst)
    M = pd.DataFrame(meta, columns=["date", "t", "off", "nshots"]); _TV[key] = (M, dict(r=np.array(rr), stop=np.array(st, dtype=float), close=np.array(cz, dtype=int), mark=np.array(mk), worst=np.array(wo))); return _TV[key]
VAR = {"v": BASE}
def paths_v(items, cap, fac, p0, p1):
    """既存の paths_fac と同じ。為替は VAR の細部の表を使い、決済の添字は表の close(= 損切り・利確・時間切れの早い方)。指数は既存の表のまま。cap は使わない(None のみ)。"""
    assert cap is None; var = (ENTRY[VAR["v"][0]],) + tuple(VAR["v"][1:]); parts = []; TB = {}
    for s, idxf, w in items:
        if idxf: Mt, res = ORIG_TABLE(s, True); Rk = dict(res[K0]); Rk["close"] = np.minimum(Rk["stop"], Mt["off"].values + 24).astype(int)
        else: Mt, Rk = table_v(s, var)
        TB[f"{s}|{idxf}"] = Rk; p = Mt.copy(); p["w"] = w / p.nshots
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
def evaluate(items, g, fac, mult, pad, add=None, npaths=20000):
    T, dates = build_full(items, None, g, fac, mult); call = np.arange(len(dates)); c1 = call[np.array([d >= PM for d in dates])]; c2 = call[np.array([d < PM for d in dates])]; ad = np.zeros(len(dates)) if add is None else add(dates); r = {}
    for tag in ("lo", "cl"):
        m = sim_funded(T[tag], ad, call, 0.10, pad, False, 520, npaths); a = sim_funded(T[tag], ad, c1, 0.10, pad, False, 260, 10000); b = sim_funded(T[tag], ad, c2, 0.10, pad, False, 260, 10000)
        r[tag] = dict(s10=m[520][0], p10=m[520][1], s5=m[260][0], p5=m[260][1], s5a=a[260][0], p5a=a[260][1], s5b=b[260][0], p5b=b[260][1], wk_mean=float(T[tag][0][-1].mean()) * 100, wk_sd=float(T[tag][0][-1].std()) * 100, guard=float((T[tag][1][-1] > 0).mean()) * 100)
    out = {k: round(min(r["lo"][k], r["cl"][k]), 2) for k in ("s10", "p10", "s5", "p5", "s5a", "p5a", "s5b", "p5b")}; out.update(wk_mean=round(r["cl"]["wk_mean"], 3), wk_sd=round(r["cl"]["wk_sd"], 3), guard=round(max(r["lo"]["guard"], r["cl"]["guard"]), 2)); return out, T
def win_ok(v, b, sfx): return bool((v["p5" + sfx] >= b["p5" + sfx] + 3.0 and v["s5" + sfx] >= b["s5" + sfx] - 1.0) or (v["s5" + sfx] >= b["s5" + sfx] + 3.0 and v["p5" + sfx] >= b["p5" + sfx]))
def neighbors(v):
    e, H, k, tp = v; out = []
    if e in EORDER:
        i = EORDER.index(e); out += [(EORDER[j], H, k, tp) for j in (i - 1, i + 1) if 0 <= j < len(EORDER)]
        if e in ("6", "8"): out.append((BASE[0], H, k, tp))
    else: out += [("6", H, k, tp), ("8", H, k, tp)]
    i = HOLDS.index(H); out += [(e, HOLDS[j], k, tp) for j in (i - 1, i + 1) if 0 <= j < len(HOLDS)]
    i = SLS.index(k); out += [(e, H, SLS[j], tp) for j in (i - 1, i + 1) if 0 <= j < len(SLS)]
    i = TPS.index(tp); out += [(e, H, k, TPS[j]) for j in (i - 1, i + 1) if 0 <= j < len(TPS)]
    return out
if __name__ == "__main__":
    cum = int(_ARGV[1]); key = "521100397"; items, cap, g = norm_items(key); fac = make_fac(items, False, 0.5); MULT, PAD = 3.75, 0.01
    T0, d0 = build_full(items, None, g, fac, MULT)                       # 既存の計算(現行)
    n3["paths_fac"] = paths_v; VAR["v"] = BASE; b, Tb = evaluate(items, g, fac, MULT, PAD)
    same = all(np.allclose(T0[tag][i], Tb[tag][i]) for tag in ("lo", "cl") for i in range(3)); print(f"照合: 現行の設定の表が既存の計算と一致 = {same}・現行 {b}(既存: s10 96.3・p10 +69.9)", flush=True); assert same
    rows = []; t0 = time.time(); grid = list(itertools.product(ENTRY, HOLDS, SLS, TPS)); res = {}
    for n, v in enumerate(grid):
        VAR["v"] = v; r, _ = evaluate(items, g, fac, MULT, PAD); res[v] = r
        if n % 40 == 0: print(f"  {n} / {len(grid)}・{time.time() - t0:.0f} 秒", flush=True)
    okb = {v: (win_ok(r, b, "a") and win_ok(r, b, "b")) for v, r in res.items()}
    for v, r in res.items():
        nb = [x for x in neighbors(v) if x in res]; share = float(np.mean([okb[x] for x in nb])) if nb else 0.0; isb = (v == BASE)
        rows.append(dict(entry=v[0], hold=v[1], sl=v[2], tp=("なし" if v[3] is None else v[3]), **r, ok_w1=win_ok(r, b, "a"), ok_w2=win_ok(r, b, "b"), nb_share=round(share, 2), cells=0 if isb else 1, verdict="基準" if isb else ("変更候補" if (okb[v] and share >= 0.5) else "現行どおり")))
    D = pd.DataFrame(rows); D["rank_all"] = D["p10"].where(D["s10"] >= b["s10"] - 1.0).rank(ascending=False, method="min"); D["rank_w1"] = D["p5a"].where(D["s5a"] >= b["s5a"] - 1.0).rank(ascending=False, method="min"); D["rank_w2"] = D["p5b"].where(D["s5b"] >= b["s5b"] - 1.0).rank(ascending=False, method="min")
    D.to_csv("results/q278_mon_detail_grid.csv", index=False); assert int(D.cells.sum()) == 359
    pd.set_option("display.width", 330); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 400)
    cols = ["entry", "hold", "sl", "tp", "s10", "p10", "s5a", "p5a", "s5b", "p5b", "wk_mean", "wk_sd", "guard", "ok_w1", "ok_w2", "nb_share", "rank_all", "rank_w1", "rank_w2", "verdict"]
    print(f"\n== Q278(累積セル {cum} + 359 = {cum + 359}・FTMO 50k 本口座後・現行 = {BASE}) =="); print("現行:", D[D.verdict == "基準"][cols].to_string(index=False))
    print("\n全期間の順位 上位 20(s10 が現行 − 1 以上・p10 の大きい順):"); print(D.sort_values("rank_all").head(20)[cols].to_string(index=False))
    print("\n① 2021-08 以降の順位 上位 20 と、② での順位:"); print(D.sort_values("rank_w1").head(20)[cols].to_string(index=False))
    print("\n② 2016-11〜2021-07 の順位 上位 20 と、① での順位:"); print(D.sort_values("rank_w2").head(20)[cols].to_string(index=False))
    both = D.dropna(subset=["rank_w1", "rank_w2"]); from scipy.stats import spearmanr
    print(f"\n順位の相関(①の p5 と ②の p5・全 {len(D)} 通り): Spearman {spearmanr(D['p5a'], D['p5b'])[0]:.2f}・s5 どうし {spearmanr(D['s5a'], D['s5b'])[0]:.2f}。① の上位 20 の ② での順位の中央 {D.sort_values('rank_w1').head(20)['rank_w2'].median()}・現行の順位: 全期間 {int(D[D.verdict == '基準'].rank_all.iloc[0])}・① {int(D[D.verdict == '基準'].rank_w1.iloc[0])}・② {int(D[D.verdict == '基準'].rank_w2.iloc[0])}(順位の対象 {int(D.rank_all.notna().sum())} / {int(D.rank_w1.notna().sum())} / {int(D.rank_w2.notna().sum())} 通り)")
    print(f"① を満たす {int(D.ok_w1.sum())}・② を満たす {int(D.ok_w2.sum())}・両方 {int((D.ok_w1 & D.ok_w2).sum())}・変更候補 {int((D.verdict == '変更候補').sum())} / 359")
    for dim in ("entry", "hold", "sl", "tp"):
        print(f"\n細部ごとの平均({dim}):"); print(D.groupby(dim, sort=False)[["s10", "p10", "s5a", "p5a", "s5b", "p5b", "wk_mean", "guard"]].mean().round(1).assign(ok両方=D.groupby(dim, sort=False).apply(lambda x: int((x.ok_w1 & x.ok_w2).sum()))).to_string())
    C = D[D.verdict == "変更候補"].sort_values("p10", ascending=False)
    if len(C):
        print("\n変更候補:"); print(C[cols].to_string(index=False))
        # 参照: トパーズの本口座後(月曜 3.0 倍 + 指数 + ロール 4.5 倍・SKEW・200 日線 0.5・ガード 2.8%)での確認
        itT, capT, gT = norm_items("6104739"); facT = make_fac(itT, True, 0.5); addf = lambda dates: n3["roll_week"](dates, 4.5, gT); VAR["v"] = BASE; bt, _ = evaluate(itT, gT, facT, 3.0, 0.01, add=addf); print("\n参照: トパーズの本口座後・現行", bt)
        for _, c in C.head(10).iterrows():
            v = (c.entry, int(c.hold), float(c.sl), None if c.tp == "なし" else float(c.tp)); VAR["v"] = v; rt, _ = evaluate(itT, gT, facT, 3.0, 0.01, add=addf); print("  ", v, rt, "→ ①", win_ok(rt, bt, "a"), "②", win_ok(rt, bt, "b"))
    else: print("\n変更候補なし")
