# -*- coding: utf-8 -*-
"""docs/244 Q264(2026-11-17 登録・10 セル): 有効の 4 条件(docs/503 のあとの整理)から出した新案 4 つ。
ユーザー 2026-11-17「抽象化して有効無効を定義できますか」→ 4 条件を回答 →「その点を踏まえ新案は出せますか」→ 案 A〜D を提示 →「お願いします」(= 4 案とも登録して実行)。
共通: 「荒れた週」= 前営業日(月曜なら前金曜)の VIX 終値 > 25。夜 = 20 UTC の始値で建て、翌日 13 UTC(指数・債券・金)/ 7 UTC(為替)の始値で決済(Q237 と同じ作り)。費用は q.cost。
(A) 改良系 1 セル: 配備形 Mon4 に「荒れた週の月曜の夜の指数 5 本(NAS100・US500・US30・JP225・UK100 各 0.05 = 合計 0.25)」を足す。判定 = 配備形に対する 3 窓(Sharpe 改善かつ最悪月が悪化しない)。参照 = E1 に足した形・Q237 の A2(2 本)。
(B) 新規 3 セル: 荒れた週の月曜の夜に安全資産を売る。B1 USTBOND / B2 BUND / B3 XAUUSD(金の 1 時間足は 2021〜2025 のみ)。
(C) 新規 3 セル: 荒れた週の月曜の夜に円以外のリスク通貨を買う。C1 AUDUSD / C2 NZDUSD / C3 4 本の束(AUDUSD・NZDUSD・GBPUSD・EURUSD 各 0.25)。
(D) 新規 3 セル: 株価指数が大きく下げた日の米国市場の引け(夏 20・冬 21 UTC)で買い、翌日の寄り後(夏 14・冬 15 UTC)に決済。大きく下げた日 = 引け → 引けの変化率が −1.5 ×(直近 60 日の標準偏差)以下。月〜木に建てる。D1 NAS100 / D2 US500 / D3 2 本の束。
判定(B・C・D)= 新規の標準(探索のプラス月の二項 p < 0.05 /(累積 + 10)・探索 24 か月以上・OOS 平均 > 0・前窓プラス月 ≥ 50%)。
  荒れた週だけの形は取引のある月が少なく標準では判定できない見込みのため、読み方の物差し(事前固定・参照)= 「3 窓とも 1 回の平均がプラス かつ 全期間の t ≥ 3.0」を併記する(NAS100・US500 の月曜の夜は t 3.2・3 窓プラス)。
使い方: cd research && PYTHONPATH=queue:. python3 -W ignore queue/q264_new_ideas_from_four_conditions.py <累積セル数>   出力: results/q264_new_ideas.csv・_std.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
import q237_night_leg_after_high_vix as q237
from q240_weekend_premium_predictions import frame, series
VIX, TH = q237.VIX, q237.TH; PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); H = pd.Timedelta(hours=1); IDX5 = ["NAS100", "US500", "US30", "JP225", "UK100"]
def us_dst(d):
    y = d.year; mar = pd.Timestamp(y, 3, 8); mar += pd.Timedelta(days=(6 - mar.dayofweek) % 7); nov = pd.Timestamp(y, 11, 1); nov += pd.Timedelta(days=(6 - nov.dayofweek) % 7); return mar <= d < nov
def mon_night(sym, exit_hour, side):
    """荒れた週の月曜の夜(20 UTC → 翌日 exit_hour UTC)。side = +1 買い / −1 売り。戻り値 = 費用後の損益(index = 月曜)。"""
    o = load(sym)["open"]; t = o.index[(o.index.hour == 20) & (o.index.dayofweek == 0)]; t2 = t.normalize() + pd.Timedelta(days=1, hours=exit_hour); p0 = o.reindex(t).values; p1 = o.reindex(t2).values; ok = ~np.isnan(p1) & ~np.isnan(p0); d = t.normalize()[ok]
    r = pd.Series(side * (p1[ok] / p0[ok] - 1) - cost(sym, p0[ok]), index=d); v = VIX.reindex(d - pd.Timedelta(days=1), method="ffill").values; r = r[(v > TH)]; return r[r.index >= PRE0]
def drop_night(sym):
    """大きく下げた日の引けで買い、翌日の寄り後に決済(月〜木)。"""
    o = load(sym)["open"]; days = pd.DatetimeIndex(sorted(set(o.index.normalize()))); tc = pd.DatetimeIndex([d + (20 if us_dst(d) else 21) * H for d in days]); pc = pd.Series(o.reindex(tc).values, index=days).dropna(); ret = pc.pct_change(); sd = ret.rolling(60).std().shift(1); sig = (ret <= -1.5 * sd) & (pc.index.dayofweek <= 3)
    d = pc.index[sig.fillna(False).values]; t_in = pd.DatetimeIndex([x + (20 if us_dst(x) else 21) * H for x in d]); t_out = pd.DatetimeIndex([x + pd.Timedelta(days=1) + (14 if us_dst(x) else 15) * H for x in d]); r = trades(sym, t_in, o.reindex(t_in).values, np.ones(len(d)), o.reindex(t_out).values); r.index = r.index.normalize(); return r[r.index >= PRE0]
def desc(x):
    out = {}
    for w, a, b in WIN + (("全期間", PRE0, END),):
        y = x[(x.index >= a) & (x.index <= b)]; out[w] = f"{y.mean() * 1e4:+.1f}({len(y)})" if len(y) else "—"
    t = float(x.mean() / x.std() * np.sqrt(len(x))) if len(x) > 2 and x.std() > 0 else 0.0; ok = all(len(x[(x.index >= a) & (x.index <= b)]) > 0 and x[(x.index >= a) & (x.index <= b)].mean() > 0 for w, a, b in WIN) and t >= 3.0
    return out, round(t, 2), round(float((x > 0).mean()) * 100), ok
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 10; rows = []; P = frame(); B = series(P, "base"); E = series(P, "E1"); bs = {w: stats(B, a, b) for w, a, b in WIN}; es = {w: stats(E, a, b) for w, a, b in WIN}
    def add_idx(basex, syms, w_each):
        out = None; n = None
        for s in syms: x = mon_night(s, 13, 1.0); out = x if out is None else out.add(x, fill_value=0.0); c = pd.Series(1.0, index=x.index); n = c if n is None else n.add(c, fill_value=0.0)
        return basex.add((out / n) * w_each * len(syms), fill_value=0.0).reindex(basex.index.union(out.index)).fillna(0.0).sort_index()          # 足が無い銘柄がある週は、ある銘柄で等分
    for nm, syms, basex, bst, cell in (("A 配備形 + 夜の指数 5 本(合計 0.25)", IDX5, B, bs, True), ("参照: 配備形 + 夜の指数 2 本(Q237 の A2 と同じ作り)", ["NAS100", "US500"], B, bs, False), ("参照: E1 + 夜の指数 5 本", IDX5, E, es, False), ("参照: E1 + 夜の指数 2 本", ["NAS100", "US500"], E, es, False)):
        v = add_idx(basex, syms, 0.25 / len(syms)); vs = {w: stats(v, a, b) for w, a, b in WIN}; ok = all(vs[w][0] > bst[w][0] and vs[w][1] >= bst[w][1] for w, _, _ in WIN)
        rows.append(dict(part="A", cell=nm, counted=cell, 前窓=str(vs["前窓"][:3]), IS=str(vs["IS"][:3]), OOS=str(vs["OOS"][:3]), 全期間="", t="", win="", verdict=("成立" if ok else "不成立") + f"(基準 {bst['前窓'][:2]} / {bst['IS'][:2]} / {bst['OOS'][:2]})"))
    for s in IDX5:
        x = mon_night(s, 13, 1.0); o_, t, wn, ok = desc(x); rows.append(dict(part="A 内訳", cell=f"{s} 月曜の夜(買い)", counted=False, 前窓=o_["前窓"], IS=o_["IS"], OOS=o_["OOS"], 全期間=o_["全期間"], t=t, win=wn, verdict="物差し ○" if ok else "物差し ×"))
    R = Runner("Q264", cum, 9, "results/q264_new_ideas_std.csv"); S = {}
    S["B1 USTBOND 月曜の夜の売り"] = mon_night("USTBOND", 13, -1.0); S["B2 BUND 月曜の夜の売り"] = mon_night("BUND", 13, -1.0); S["B3 XAUUSD 月曜の夜の売り(2021〜2025)"] = mon_night("XAUUSD", 13, -1.0)
    S["C1 AUDUSD 月曜の夜の買い"] = mon_night("AUDUSD", 7, 1.0); S["C2 NZDUSD 月曜の夜の買い"] = mon_night("NZDUSD", 7, 1.0); c3 = None
    for s in ("AUDUSD", "NZDUSD", "GBPUSD", "EURUSD"): x = mon_night(s, 7, 1.0) * 0.25; c3 = x if c3 is None else c3.add(x, fill_value=0.0)
    S["C3 リスク通貨 4 本の束 月曜の夜の買い"] = c3; S["D1 NAS100 大きく下げた日の引け → 翌日の寄り後"] = drop_night("NAS100"); S["D2 US500 大きく下げた日の引け → 翌日の寄り後"] = drop_night("US500"); S["D3 NAS100・US500 の束"] = (drop_night("NAS100") * 0.5).add(drop_night("US500") * 0.5, fill_value=0.0)
    for nm, x in S.items(): R.add("FourCond", "MIX", nm, x)
    DS = R.finish()
    for nm, x in S.items():
        o_, t, wn, ok = desc(x); m = DS[DS.spec == nm].iloc[0]; rows.append(dict(part=nm[0], cell=nm, counted=True, 前窓=o_["前窓"], IS=o_["IS"], OOS=o_["OOS"], 全期間=o_["全期間"], t=t, win=wn, verdict=("通過" if m.passed else f"標準: 不通過(探索 {int(m.is_plus)} / {int(m.is_n)} か月・p {m.p:.2f})") + ("・物差し ○" if ok else "・物差し ×")))
    D = pd.DataFrame(rows); D.to_csv("results/q264_new_ideas.csv", index=False); pd.set_option("display.width", 340); pd.set_option("display.max_colwidth", 90); pd.set_option("display.max_rows", 100)
    print(f"\n== Q264(累積セル {cum} + {N} = {cum + N})。A = Sharpe / 最悪月 % / 累積 %。そのほか = 1 回の平均 bps(回数)・t・勝率 % =="); print(D.to_string(index=False))
