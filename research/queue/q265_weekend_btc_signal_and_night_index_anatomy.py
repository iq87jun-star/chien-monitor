# -*- coding: utf-8 -*-
"""docs/244 Q265(2026-11-17 登録「登録して実行」・8 セル + 診断): 直した条件から出した 3 案。
ユーザー 2026-11-17「何か他に新案ありますか」→ 案 E・F・G を提示 →「登録して実行」(3 案とも)。
(E) 週末のあいだのビットコインの値動きを物差しにする(改良系 3 セル)。
    週末の BTC = BTCUSD の金曜 21 UTC → 日曜 21 UTC の変化率。「大きく下げた週」= 自分の直近 52 週(その週を除く・26 週以上)の下位 20%。BTC の 1 時間足は 2018-01 から。
    Ea = 配備形 Mon4 で、BTC が大きく下げた週だけ 24 時間・それ以外は同日 20 UTC。Eb = VIX > 25 または BTC が大きく下げた週は 24 時間(E1 に足す形)。
    Ec = 配備形に、BTC が大きく下げた週の月曜の夜の指数 5 本(各 0.05)を足す(VIX の代わりに BTC で決める形)。
    判定 = 配備形に対する 3 窓(Sharpe 改善かつ最悪月が悪化しない)。物差しのある期間だけで比べる。Eb は E1 に対しても見る(参照)。
(F) 診断(セル 0): 荒れた週の月曜の夜の指数 5 本を時間帯で分ける(20 → 00 UTC・00 → 07 UTC・07 → 13 UTC・参考 13 → 20 UTC)。費用なしの平均と t。
(G) 夜の指数を欧州・アジアにも広げる(5 セル): GER40・EUSTX50・AUS200・HK50 の荒れた週の月曜の夜(20 UTC → 翌日 13 UTC)= 4 セル(判定は新規の標準 + 物差し: 3 窓プラスかつ t ≥ 3.0)。
    G5 = 配備形 + 夜の指数 9 本(合計 0.25)= 改良系 1 セル(配備形に対する 3 窓)。
使い方: cd research && PYTHONPATH=queue:. python3 -W ignore queue/q265_weekend_btc_signal_and_night_index_anatomy.py <累積セル数>   出力: results/q265_btc_and_night.csv・_anatomy.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
import q237_night_leg_after_high_vix as q237
from q240_weekend_premium_predictions import frame, series
VIX, TH = q237.VIX, q237.TH; PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); H = pd.Timedelta(hours=1); IDX5 = ["NAS100", "US500", "US30", "JP225", "UK100"]; IDX4 = ["GER40", "EUSTX50", "AUS200", "HK50"]
def btc_weekend():
    o = load("BTCUSD")["open"]; mons = pd.date_range("2018-01-08", o.index.max().normalize(), freq="7D"); mons = mons[mons.dayofweek == 0]; a = np.array([o.asof(d - pd.Timedelta(days=3) + 21 * H) for d in mons]); b = np.array([o.asof(d - pd.Timedelta(days=1) + 21 * H) for d in mons])
    r = pd.Series(b / a - 1, index=mons).dropna(); rk = r.rolling(53, min_periods=27).apply(lambda w: (w[:-1] < w[-1]).mean(), raw=True); return r, rk
def night_all(sym, exit_hour=13):
    """全月曜の夜(20 UTC → 翌日 exit_hour UTC)の買い・費用後。index = 月曜。"""
    o = load(sym)["open"]; t = o.index[(o.index.hour == 20) & (o.index.dayofweek == 0)]; t2 = t.normalize() + pd.Timedelta(days=1, hours=exit_hour); p0 = o.reindex(t).values; p1 = o.reindex(t2).values; ok = ~np.isnan(p1) & ~np.isnan(p0); r = pd.Series(p1[ok] / p0[ok] - 1 - cost(sym, p0[ok]), index=t.normalize()[ok]); return r[r.index >= PRE0]
def hotflag(idx): return pd.Series(VIX.reindex(pd.DatetimeIndex(idx) - pd.Timedelta(days=3), method="ffill").values > TH, index=idx)
def bundle_night(syms, flag, total=0.25):
    out = None; n = None
    for s in syms:
        x = night_all(s); x = x[flag.reindex(x.index).fillna(False).values]; out = x if out is None else out.add(x, fill_value=0.0); c = pd.Series(1.0, index=x.index); n = c if n is None else n.add(c, fill_value=0.0)
    return (out / n) * total
def desc(x):
    o_ = {}
    for w, a, b in WIN + (("全期間", PRE0, END),):
        y = x[(x.index >= a) & (x.index <= b)]; o_[w] = f"{y.mean() * 1e4:+.1f}({len(y)})" if len(y) else "—"
    t = float(x.mean() / x.std() * np.sqrt(len(x))) if len(x) > 2 and x.std() > 0 else 0.0; ok = all(len(x[(x.index >= a) & (x.index <= b)]) > 0 and x[(x.index >= a) & (x.index <= b)].mean() > 0 for w, a, b in WIN) and t >= 3.0; return o_, round(t, 2), ok
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 8; rows = []; P = frame(); BW, RK = btc_weekend(); low = (RK <= 0.2); start0 = RK.dropna().index.min(); d_ = pd.DatetimeIndex(P.index); P["btc_low"] = low.reindex(d_).fillna(False).values; P["btc_r"] = BW.reindex(d_).values
    def ser(mask, e1=False): return pd.Series(np.where(mask, P.r24, P.r20) * P.f.values * 0.25, index=P.index).groupby(level=0).sum()
    B = series(P, "base"); E1 = series(P, "E1"); cut = lambda x: x[x.index >= start0]; W2 = (("前窓", start0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); bs = {w: stats(cut(B), a, b) for w, a, b in W2}; es = {w: stats(cut(E1), a, b) for w, a, b in W2}
    print(f"BTC の物差しの開始 {start0.date()}・大きく下げた週 {int(low.sum())} / {int(RK.notna().sum())}・VIX 25 超の週との重なり {int((low & hotflag(low.index)).sum())}・基準 {bs}・E1 {es}")
    wk = P.groupby(level=0).first(); wk = wk[wk.index >= start0]
    for nm, mask, ref in (("Ea BTC が週末に大きく下げた週だけ 24h", P.btc_low.values, bs), ("Eb VIX > 25 または BTC が大きく下げた週は 24h", P.hot.values | P.btc_low.values, bs)):
        v = cut(ser(mask)); vs = {w: stats(v, a, b) for w, a, b in W2}; ok = all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in W2); oke = all(vs[w][0] > es[w][0] and vs[w][1] >= es[w][1] for w, _, _ in W2)
        rows.append(dict(part="E", cell=nm, 前窓=str(vs["前窓"][:3]), IS=str(vs["IS"][:3]), OOS=str(vs["OOS"][:3]), verdict=("成立" if ok else "不成立") + f"・E1 を 3 窓で上回る = {oke}", note=f"基準 {bs['前窓'][:2]} / {bs['IS'][:2]} / {bs['OOS'][:2]}・E1 {es['前窓'][:2]} / {es['IS'][:2]} / {es['OOS'][:2]}"))
    for nm, flag in (("Ec 配備形 + BTC が大きく下げた週の月曜の夜の指数 5 本", low), ("参照: 配備形 + VIX > 25 の週の夜の指数 5 本(同じ期間)", hotflag(low.index)), ("参照: 配備形 + (VIX > 25 または BTC)の週の夜の指数 5 本", low | hotflag(low.index))):
        nb = bundle_night(IDX5, flag); v = cut(B.add(nb, fill_value=0.0)); vs = {w: stats(v, a, b) for w, a, b in W2}; ok = all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in W2)
        rows.append(dict(part="E", cell=nm, 前窓=str(vs["前窓"][:3]), IS=str(vs["IS"][:3]), OOS=str(vs["OOS"][:3]), verdict="成立" if ok else "不成立", note=f"夜の週数 {int((nb != 0).sum())}"))
    # 数値化: 円クロスの夜(20 UTC → 24h)と指数の夜を、BTC × VIX で分ける
    night_fx = ((P.r24 - P.r20) * 1.0).groupby(level=0).mean(); night_ix = bundle_night(IDX5, pd.Series(True, index=low.index), 1.0); hf = hotflag(low.index); ref = []
    for g, m in (("BTC 大きく下げた × VIX > 25", low & hf), ("BTC 大きく下げた × VIX ≤ 25", low & ~hf), ("BTC それ以外 × VIX > 25", ~low & hf & RK.notna()), ("BTC それ以外 × VIX ≤ 25", ~low & ~hf & RK.notna())):
        d = m[m].index; a = night_fx.reindex(d).dropna(); b = night_ix.reindex(d).dropna(); ref.append(dict(table="E 数値化", group=g, weeks=len(d), fx_night_bps=round(float(a.mean()) * 1e4, 1) if len(a) else None, fx_t=round(float(a.mean() / a.std() * np.sqrt(len(a))), 2) if len(a) > 2 else None, idx_night_bps=round(float(b.mean()) * 1e4, 1) if len(b) else None, idx_t=round(float(b.mean() / b.std() * np.sqrt(len(b))), 2) if len(b) > 2 else None))
    R = Runner("Q265G", cum, 4, "results/q265_night_other_indices_std.csv"); S = {}
    for s in IDX4:
        x = night_all(s); x = x[hotflag(x.index).values]; S[s] = x; R.add("NightIdxEU_AS", s, f"G {s} 荒れた週の月曜の夜の買い", x)
    DS = R.finish()
    for s, x in S.items():
        o_, t, ok = desc(x); m = DS[DS.symbol == s].iloc[0]; rows.append(dict(part="G", cell=f"G {s} 荒れた週の月曜の夜の買い", 前窓=o_["前窓"], IS=o_["IS"], OOS=o_["OOS"], verdict=("標準: 通過" if m.passed else f"標準: 不通過(探索 {int(m.is_plus)} / {int(m.is_n)} か月)") + ("・物差し ○" if ok else "・物差し ×"), note=f"全期間 {o_['全期間']}・t {t}・勝率 {100 * (x > 0).mean():.0f}%"))
    hfP = hotflag(B.index); bs0 = {w: stats(B, a, b) for w, a, b in WIN}
    for nm, syms, cell in (("G5 配備形 + 夜の指数 9 本(合計 0.25)", IDX5 + IDX4, True), ("参照: 配備形 + 夜の指数 5 本", IDX5, False)):
        v = B.add(bundle_night(syms, hfP.reindex(pd.date_range("2016-01-04", "2026-12-28", freq="7D")).fillna(False) if False else hotflag(pd.date_range("2016-01-04", "2026-12-28", freq="7D"))), fill_value=0.0); vs = {w: stats(v, a, b) for w, a, b in WIN}; ok = all(vs[w][0] > bs0[w][0] and vs[w][1] >= bs0[w][1] for w, _, _ in WIN)
        rows.append(dict(part="G", cell=nm, 前窓=str(vs["前窓"][:3]), IS=str(vs["IS"][:3]), OOS=str(vs["OOS"][:3]), verdict="成立" if ok else "不成立", note=f"基準 {bs0['前窓'][:2]} / {bs0['IS'][:2]} / {bs0['OOS'][:2]}"))
    # (F) 時間帯の内訳(費用なし)
    for s in IDX5:
        o = load(s)["open"]; mons = o.index[(o.index.hour == 20) & (o.index.dayofweek == 0)].normalize(); mons = mons[mons >= PRE0]; hf5 = hotflag(mons)
        for grp, sel in (("荒れた週", hf5.values), ("静かな週", ~hf5.values)):
            d = mons[sel]; r_ = dict(table="F 時間帯", group=f"{s}・{grp}", weeks=len(d))
            for seg, (h0, h1) in (("20→00", (20, 24)), ("00→07", (24, 31)), ("07→13", (31, 37)), ("13→20(参考)", (37, 44))):
                x = pd.Series(o.reindex(d + h1 * H).values / o.reindex(d + h0 * H).values - 1).dropna(); r_[seg] = f"{x.mean() * 1e4:+.1f}(t {x.mean() / x.std() * np.sqrt(len(x)):.1f})" if len(x) > 2 else "—"
            ref.append(r_)
    D = pd.DataFrame(rows); RF = pd.DataFrame(ref); D.to_csv("results/q265_btc_and_night.csv", index=False); RF.to_csv("results/q265_btc_and_night_anatomy.csv", index=False)
    pd.set_option("display.width", 340); pd.set_option("display.max_colwidth", 110); pd.set_option("display.max_rows", 100)
    print(f"\n== Q265(累積セル {cum} + {N} = {cum + N}) =="); print(D.to_string(index=False)); print("\n== 数値化・時間帯 =="); print(RF.fillna("").to_string(index=False))
    c = pd.DataFrame({"btc": BW, "fxnight": night_fx, "mon": B}).dropna(); print("\nBTC の週末の変化率との相関: 月曜の円クロス(配備形)", round(c.btc.corr(c.mon), 2), "・円クロスの夜", round(c.btc.corr(c.fxnight), 2), "・年ごとの月曜との相関:", {int(y): round(g.btc.corr(g.mon), 2) for y, g in c.groupby(c.index.year)})
