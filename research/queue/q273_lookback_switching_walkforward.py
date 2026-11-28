# -*- coding: utf-8 -*-
"""docs/244 Q273(2026-11-23 登録「登録して実行」扱い・セル 16): 学習期間(10 年・5 年・3 年・1 年・6 か月)を月ごとに切り替えて最適を作る。
ユーザー 2026-11-23「10年最適 5年 3年 1年 6ヶ月を1ヶ月単位で切替ながら最適解を作りたいです」。
データ: 2003 年から日足がある 8 銘柄の Dukascopy 日足(〜2025-12)+ 2026 年分は data_live(Yahoo)の日次の騰落でつなぐ。評価の終わり 2026-10-31。
レグ 15 本(式は recentfit_screen と同じ): Mon 7(円クロス 3・指数 4)/ Hold 5 / TSMOM 3。コスト: FX 往復 3 pip・指数 IDX_COST・保有系は月初 5 bps + 買い持ちのスワップ(金 月 −52 bps・指数 年 −5%)。
「最適」: D1 = docs/174 の固定ルール(得点の上位 4 本・逆ボラ・上限 40%)/ D2 = 学習期間の Sharpe が最大の重み(買いのみ・上限 40%)。
毎月: 月初に直前 120・60・36・12・6 か月で最適を作り、その月は重みを固定。型: 固定 5(10 年 = 基準)/ 切り替え K = 3・6・12(直前 K か月の実際の成績の Sharpe が最も高い学習期間・同点は長いほう)/ 混ぜる(5 分の 1 ずつ)。
評価: 2014-01〜2026-10(前半 〜2019-12・後半 2020-01〜)。判定: 前半・後半の両方で Sharpe が基準 + 0.10 以上、かつ変動をそろえた最悪月が基準より悪くない → 変更候補。
参照(判定しない): 15 本を逆ボラで全部持つ / 後から一番良い学習期間を選ぶ / Mon 7 本だけ / スワップ 0 / 入れ替えの量 / 2026-11 月初の中身。
D2 の実装の細部(登録の範囲内): 候補は学習期間の平均がプラスのレグだけ。候補が 3 本未満のときは上限を 1 ÷ 本数に緩める。凸な形(分散を最小・平均の合計 = 1)で解く。
使い方: cd research && python3 -W ignore queue/q273_lookback_switching_walkforward.py <累積セル数>   出力: results/q273_lookback_switching.csv・results/q273_lookback_switching_picks.csv"""
import os, sys
import numpy as np, pandas as pd
from scipy.optimize import minimize
HERE = os.path.dirname(os.path.abspath(__file__)); RES = os.path.dirname(HERE); os.chdir(RES); sys.path.insert(0, RES)
import recentfit_screen as base
IDX_COST = base.IDX_COST; END = pd.Timestamp("2026-10-31"); BD = pd.bdate_range("2003-01-01", END)
FX = ["EURJPY", "GBPJPY", "USDJPY"]; IDX = ["NAS100", "US500", "JP225", "UK100"]; HOLD = ["XAUUSD", "US500", "NAS100", "JP225", "UK100"]; TS = ["XAUUSD", "US500", "NAS100"]
LS = [120, 60, 36, 12, 6]; LN = {120: "10 年", 60: "5 年", 36: "3 年", 12: "1 年", 6: "6 か月"}; KS = [3, 6, 12]
T0, E0, E1, EM = pd.Timestamp("2013-01-01"), pd.Timestamp("2014-01-01"), END, pd.Timestamp("2020-01-01")
MONTHS = pd.date_range(T0, "2026-10-01", freq="MS"); TOP_K, MAX_FAM, W_CAP, MIN_ACT = 4, 2, 0.40, 15

def load(sym):
    k = pd.read_csv(f"data_dukascopy/{sym}_day.csv"); k["d"] = pd.to_datetime(k["timestamp"]).dt.normalize(); k = k.drop_duplicates("d", keep="last").set_index("d").sort_index()
    k = k[(k["close"] > 0) & (k.index.dayofweek < 5) & (k["high"] > k["low"])][["open", "high", "low", "close"]]   # 値動きのない行(休場の埋め)を除く。出来高 0 では除かない(指数の 2013 年以前は出来高の欄が 0 だが価格は入っている)
    l = pd.read_csv(f"data_live/{sym}_rf.csv"); l["t"] = pd.to_datetime(l["timestamp"], errors="coerce"); l = l.dropna(subset=["t"]).sort_values("t"); l["d"] = (l["t"] + pd.Timedelta(hours=2)).dt.floor("D")
    l = l.groupby("d").last()[["open", "high", "low", "close"]]; l = l[l.index.dayofweek < 5]
    cut = k.index[-1]; ratio = float(k["close"].iloc[-1]) / float(l["close"][:cut].iloc[-1]); tail = l[(l.index > cut) & (l.index <= END)] * ratio
    return pd.concat([k, tail]).sort_index(), len(tail)
def on_bd(s): return s.groupby(s.index.normalize()).sum().reindex(BD).fillna(0.0)
def mon(D, sym, pips=3.0):
    o2o = D["open"].shift(-1) / D["open"] - 1.0; c = IDX_COST[sym] if sym in IDX_COST else pips * 0.01 / D["open"]
    return (o2o - c)[D.index.dayofweek == 0].dropna()
def firsts(s): return pd.Series(s.index, index=s.index).groupby(pd.PeriodIndex(s.index, freq="M")).min().values
def hold(D, swap_d):
    s = D["close"].pct_change().dropna(); s.loc[s.index.isin(firsts(s))] -= 5e-4; return s + swap_d
def tsmom(D, swap_d):
    px = D["close"].resample("ME").last().dropna(); sig = sum(np.sign(px.pct_change(lb)) for lb in (1, 3, 6, 12)); pos = np.sign(sig).shift(1); pos.index = pos.index.to_period("M")
    s = D["close"].pct_change().dropna(); coef = pos.reindex(pd.PeriodIndex(s.index, freq="M")).fillna(0.0).values
    out = pd.Series(s.values * coef + np.where(coef > 0, swap_d, 0.0), index=s.index); out.loc[out.index.isin(firsts(out))] -= 5e-4; return out
def cells(DD, swap=True, pips=3.0):
    C = {}; sw = lambda s: ((-52e-4 / 21.0) if s == "XAUUSD" else (-0.05 / 252.0)) if swap else 0.0
    for s in FX + IDX: C[("Mon", s)] = on_bd(mon(DD[s], s, pips))
    for s in HOLD: C[("Hold", s)] = on_bd(hold(DD[s], sw(s)))
    for s in TS: C[("TSMOM", s)] = on_bd(tsmom(DD[s], sw(s)))
    R = pd.DataFrame(C); R.columns = [f"{f} {s}" for f, s in C]; return R

def pick_d1(Rw):
    sc = {}
    for n in Rw.columns:
        x = Rw[n].values; a = x[x != 0.0]
        if len(a) < MIN_ACT or a.std(ddof=1) <= 0 or np.prod(1 + x) - 1 <= 0: continue
        sc[n] = (a.mean() / a.std(ddof=1) * np.sqrt(len(a)), a.std(ddof=1))
    picked, fam, used = [], {}, set()
    for n in sorted(sc, key=lambda k: sc[k][0], reverse=True):
        f, s = n.split(" ")
        if s in used or fam.get(f, 0) >= MAX_FAM: continue
        picked.append(n); used.add(s); fam[f] = fam.get(f, 0) + 1
        if len(picked) == TOP_K: break
    w = pd.Series(0.0, index=Rw.columns)
    if picked:
        iv = np.array([1.0 / sc[n][1] for n in picked]); iv = np.minimum(iv / iv.sum(), W_CAP); w[picked] = iv / iv.sum()
    return w
def pick_d2(Rw):
    w = pd.Series(0.0, index=Rw.columns); mu = Rw.mean() * 1e4; ok = [n for n in Rw.columns if mu[n] > 0 and (Rw[n] != 0).sum() >= MIN_ACT]
    if not ok: return w
    k = len(ok); cap = max(W_CAP, 1.0 / k); m = mu[ok].values; S = np.cov(Rw[ok].values.T * 1e2).reshape(k, k) + 1e-10 * np.eye(k)
    if k == 1: w[ok] = 1.0; return w
    cons = [{"type": "eq", "fun": lambda y: m @ y - 1.0, "jac": lambda y: m}, {"type": "ineq", "fun": lambda y: cap * y.sum() - y, "jac": lambda y: cap * np.ones((k, k)) - np.eye(k)}]
    y0 = np.ones(k) / (m.sum()); r = minimize(lambda y: y @ S @ y, y0, jac=lambda y: 2 * S @ y, bounds=[(0, None)] * k, constraints=cons, method="SLSQP", options={"maxiter": 500, "ftol": 1e-12})
    y = np.clip(r.x, 0, None)
    if not r.success or y.sum() <= 0: y = np.ones(k)
    w[ok] = y / y.sum(); return w
def pick_iv(Rw):
    w = pd.Series(0.0, index=Rw.columns)
    for n in Rw.columns:
        x = Rw[n].values; a = x[x != 0.0]
        if len(a) >= MIN_ACT and a.std(ddof=1) > 0: w[n] = 1.0 / a.std(ddof=1)
    return w / w.sum() if w.sum() > 0 else w

def sharpe(x): return float(x.mean() / x.std() * np.sqrt(252)) if x.std() > 0 else 0.0
def stats(x):
    eq = (1 + x).cumprod(); mon_ = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1); yrs = len(x) / 252.0
    return dict(ann=round((eq.iloc[-1] ** (1 / yrs) - 1) * 100, 2), vol=round(x.std() * np.sqrt(252) * 100, 2), sharpe=round(sharpe(x), 2), max_dd=round((eq / eq.cummax() - 1).min() * 100, 1), worst_month=round(mon_.min() * 100, 2), pos_months=round((mon_ > 0).mean() * 100, 0))
def seg(x, a, b): return x[(x.index >= a) & (x.index <= b)]
def walk(R, picker):
    """月ごとに各学習期間の重みを作る。返り値: W[L] = 月 × レグの重み、P[L] = 日次の成績(2013-01〜)。"""
    W = {L: [] for L in LS}
    for t in MONTHS:
        for L in LS: W[L].append(picker(R[(R.index >= t - pd.DateOffset(months=L)) & (R.index < t)]))
    W = {L: pd.DataFrame(W[L], index=MONTHS) for L in LS}; mk = pd.PeriodIndex(R.index, freq="M"); P = {}
    for L in LS:
        Wd = W[L].copy(); Wd.index = Wd.index.to_period("M"); Wd = Wd.reindex(mk); Wd.index = R.index; P[L] = (R * Wd).sum(axis=1)[R.index >= T0]
    return W, P
def arms(R, picker):
    W, P = walk(R, picker); A = {f"固定 {LN[L]}": P[L] for L in LS}; CH = {}; TO = {f"固定 {LN[L]}": float(W[L].diff().abs().sum(axis=1).iloc[1:].mean() / 2) for L in LS}
    ev = [t for t in MONTHS if t >= E0]
    for K in KS:
        out = []; ch = []; wl = []
        for t in ev:
            best, bs = None, -np.inf
            for L in LS:
                s = sharpe(seg(P[L], t - pd.DateOffset(months=K), t - pd.Timedelta(days=1)))
                if s > bs: best, bs = L, s
            out.append(seg(P[best], t, t + pd.offsets.MonthEnd(0))); ch.append(best); wl.append(W[best].loc[t])
        A[f"切り替え(直前 {K} か月)"] = pd.concat(out); CH[K] = pd.Series(ch, index=ev); TO[f"切り替え(直前 {K} か月)"] = float(pd.DataFrame(wl).diff().abs().sum(axis=1).iloc[1:].mean() / 2)
    A["混ぜる(5 分の 1 ずつ)"] = sum(P[L] for L in LS) / len(LS); TO["混ぜる(5 分の 1 ずつ)"] = float((sum(W[L] for L in LS) / len(LS)).diff().abs().sum(axis=1).iloc[1:].mean() / 2)
    orc = []
    for t in ev:
        m = {L: (1 + seg(P[L], t, t + pd.offsets.MonthEnd(0))).prod() for L in LS}; orc.append(seg(P[max(m, key=m.get)], t, t + pd.offsets.MonthEnd(0)))
    A["参照: 後から一番良い学習期間を選ぶ"] = pd.concat(orc)
    return {k: seg(v, E0, E1) for k, v in A.items()}, CH, TO, W
def table(A, TO, uni, dn, judged):
    b = A["固定 10 年"]; bs = {p: sharpe(seg(b, a, c)) for p, (a, c) in PER.items()}; bw = stats(b)["worst_month"]; rows = []
    for nm, x in A.items():
        st = stats(x); k = b.std() / x.std() if x.std() > 0 else 0.0; sv = stats(x * k); r = dict(universe=uni, definition=dn, arm=nm, **st, ann_volmatched=sv["ann"], worst_month_volmatched=sv["worst_month"], max_dd_volmatched=sv["max_dd"], turnover=round(TO.get(nm, np.nan) * 100, 0))
        for p, (a, c) in PER.items(): r[f"sharpe_{p}"] = round(sharpe(seg(x, a, c)), 2); r[f"ann_{p}"] = stats(seg(x, a, c))["ann"]
        is_cell = judged and nm != "固定 10 年" and not nm.startswith("参照")
        r["cells"] = 1 if is_cell else 0
        r["verdict"] = ("変更候補" if (r["sharpe_前半"] >= round(bs["前半"], 2) + 0.10 and r["sharpe_後半"] >= round(bs["後半"], 2) + 0.10 and r["worst_month_volmatched"] >= bw) else "現行どおり") if nm != "固定 10 年" and not nm.startswith("参照") else ("基準" if nm == "固定 10 年" else "—")
        rows.append(r)
    return rows
PER = {"前半": (E0, EM - pd.Timedelta(days=1)), "後半": (EM, E1)}

if __name__ == "__main__":
    cum = int(sys.argv[1]); N = 16; DD = {}; nt = {}
    for s in sorted(set(FX + IDX + HOLD + TS)): DD[s], nt[s] = load(s)
    print("データ: 銘柄ごとの 開始・終了・日数・2026 年のつなぎ日数", {s: (str(D.index[0].date()), str(D.index[-1].date()), len(D), nt[s]) for s, D in DD.items()}, flush=True)
    # 照合: Mon GBPJPY(往復 2 pip)の年別と、Yahoo 版(data_202609)との月次の相関
    base.DATA = os.path.join(RES, "data_202609"); R2 = cells(DD, swap=False, pips=2.0); mm = lambda x: x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
    g = R2["Mon GBPJPY"]; print("照合 Mon GBPJPY 往復 2 pip の年別 %(docs/290: 2022 +8.0・2023 +7.4・2024 +3.4・2025 +4.5):", {y: round(((1 + g[g.index.year == y]).prod() - 1) * 100, 1) for y in range(2022, 2026)})
    for nm, y in (("Mon GBPJPY", base.mon_cell("GBPJPY")), ("Mon USDJPY", base.mon_cell("USDJPY")), ("Mon NAS100", base.mon_cell("NAS100")), ("Hold XAUUSD", base.hold_cell("XAUUSD")), ("Hold US500", base.hold_cell("US500"))):
        a = mm(seg(R2[nm], pd.Timestamp("2016-02-01"), pd.Timestamp("2025-12-31"))); b_ = mm(seg(on_bd(y), pd.Timestamp("2016-02-01"), pd.Timestamp("2025-12-31"))); print(f"  月次の相関 {nm}: {np.corrcoef(a.values, b_.values)[0, 1]:.2f}(2016-02〜2025-12 の合計 % 本検証 {((1 + a).prod() - 1) * 100:+.1f} / Yahoo 版 {((1 + b_).prod() - 1) * 100:+.1f})")
    R = cells(DD); RS0 = cells(DD, swap=False); MONC = [c for c in R.columns if c.startswith("Mon ")]
    print("\nレグごとの成績(倍率 1・コストとスワップ後・年率 %): 2004〜2013 / 2014〜2019 / 2020〜2026-10・Sharpe(2014〜)")
    for c in R.columns: print(f"  {c:14s} {stats(seg(R[c], pd.Timestamp('2004-01-01'), pd.Timestamp('2013-12-31')))['ann']:+6.1f} / {stats(seg(R[c], E0, EM - pd.Timedelta(days=1)))['ann']:+6.1f} / {stats(seg(R[c], EM, E1))['ann']:+6.1f}・{sharpe(seg(R[c], E0, E1)):+.2f}")
    rows = []; picks = []; DEFS = (("D1 上位 4 本(いまの選び方)", pick_d1), ("D2 Sharpe 最大の重み", pick_d2))
    for uni, RR, judged in (("15 本(判定)", R, True), ("参照: Mon 7 本だけ", R[MONC], False), ("参照: スワップ 0", RS0, False)):
        for dn, pk in DEFS:
            A, CH, TO, W = arms(RR, pk)
            if uni.startswith("15"):
                Wiv = pd.DataFrame([pick_iv(RR[(RR.index >= t - pd.DateOffset(months=12)) & (RR.index < t)]) for t in MONTHS], index=MONTHS.to_period("M")).reindex(pd.PeriodIndex(RR.index, freq="M")); Wiv.index = RR.index
                A["参照: 選ばずに 15 本を逆ボラで持つ"] = seg((RR * Wiv).sum(axis=1), E0, E1)
                for K in KS: picks.append(dict(kind="切り替えで選ばれた学習期間の月数", definition=dn, arm=f"直前 {K} か月", detail=" / ".join(f"{LN[L]} {int((CH[K] == L).sum())}" for L in LS) + f"・切り替えた回数 {int((CH[K] != CH[K].shift()).sum() - 1)}(全 {len(CH[K])} か月)"))
                t1 = pd.Timestamp("2026-11-01")
                for L in LS:
                    w = pk(RR[(RR.index >= t1 - pd.DateOffset(months=L)) & (RR.index < t1)]); picks.append(dict(kind="2026-11 月初の中身", definition=dn, arm=f"学習 {LN[L]}", detail=" / ".join(f"{n} {w[n] * 100:.0f}%" for n in w[w > 0.005].sort_values(ascending=False).index) or "持たない"))
                for L in LS:
                    f = (W[L] > 0.005).mean().sort_values(ascending=False); picks.append(dict(kind="選ばれた月の割合(2013-01〜2026-10)", definition=dn, arm=f"学習 {LN[L]}", detail=" / ".join(f"{n} {v * 100:.0f}%" for n, v in f[f > 0.10].items())))
            rows += table(A, TO, uni, dn, judged); print("done", uni, dn, flush=True)
    D = pd.DataFrame(rows); D.to_csv("results/q273_lookback_switching.csv", index=False); PK = pd.DataFrame(picks); PK.to_csv("results/q273_lookback_switching_picks.csv", index=False); assert int(D.cells.sum()) == N, D.cells.sum()
    pd.set_option("display.width", 330); pd.set_option("display.max_rows", 400); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 200)
    print(f"\n== Q273(累積セル {cum} + {N} = {cum + N}・評価 {E0.date()}〜{E1.date()}・倍率 1) =="); print(D.to_string(index=False))
    print("\n== 中身 =="); print(PK.to_string(index=False))
    j = D[D.cells == 1]; print(f"\n判定: 変更候補 {int((j.verdict == '変更候補').sum())} / {len(j)} 件"); print(j[j.verdict == "変更候補"][["definition", "arm", "sharpe_前半", "sharpe_後半", "worst_month_volmatched"]].to_string(index=False))
