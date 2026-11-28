# -*- coding: utf-8 -*-
"""docs/244 Q218(診断・セル 0・2026-11-15 登録): 月曜の円クロス(配備形 Mon4)は 2020 年から何が変わったか。
前期 = 2016-01〜2019-12、後期 = 2020-01〜データ末尾。区切りは事後。規則の検定はしない(記述のみ)。
D1 曜日比較 / D2 時間帯の分解と週末の窓 / D3 通貨別 / D4 年ごとの月曜の損益と束の値上がり / D5 年ごとの環境 / D6 状態別 / D7 年次の相関。
使い方: cd research && python3 -W ignore queue/q218_mon4_what_changed_2020.py   出力: results/q218_mon4_what_changed_2020_*.csv"""
import sys, os
from q_common import *
from q194_mon_own_technical_state_gate import PAIRS, daily_close, states
import q20_wed_swap_carry as q20
CUT = pd.Timestamp("2020-01-01"); HOURS = (4, 6, 8, 10); DN = ["月", "火", "水", "木"]
def era(i): return np.where(i < CUT, "前期 2016〜19", "後期 2020〜")
def shots(sym, dow):
    o = load(sym)["open"]; out = None
    for h in HOURS:
        t = o.index[(o.index.dayofweek == dow) & (o.index.hour == h)]; t2 = t + pd.Timedelta(hours=24); ok = t2.isin(o.index); t, t2 = t[ok], t2[ok]
        r = trades(sym, t, o.reindex(t).values, np.ones(len(t)), o.reindex(t2).values); r.index = r.index.normalize(); out = r if out is None else out.add(r, fill_value=0.0)
    return (out / len(HOURS)).sort_index()
def tstat(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float); return float((a.mean() - b.mean()) / np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b)))
if __name__ == "__main__":
    pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 400)
    S = {(s, d): shots(s, d) for s in PAIRS for d in range(4)}; END_ = max(S[(s, 0)].index.max() for s in PAIRS)
    def basket(d): return pd.DataFrame({s: S[(s, d)] for s in PAIRS}).mean(axis=1, skipna=True)
    B = {d: basket(d) for d in range(4)}
    # D1 曜日比較
    rows = []
    for e in ("前期 2016〜19", "後期 2020〜"):
        x = {d: B[d][era(B[d].index) == e] for d in range(4)}; oth = pd.concat([x[1], x[2], x[3]])
        rows.append(dict(era=e, **{DN[d] + "_bps": round(float(x[d].mean()) * 1e4, 2) for d in range(4)}, **{DN[d] + "_勝率": round(float((x[d] > 0).mean()) * 100, 1) for d in range(4)}, 火木の平均_bps=round(float(oth.mean()) * 1e4, 2), 月曜の上乗せ_bps=round(float(x[0].mean() - oth.mean()) * 1e4, 2), t=round(tstat(x[0], oth), 2), n月=len(x[0])))
    D1 = pd.DataFrame(rows); D1.to_csv("results/q218_mon4_what_changed_2020_d1_weekday.csv", index=False); print("== D1 曜日比較(束・同じ時刻・24 時間・コスト後) =="); print(D1.to_string(index=False))
    # D2 時間帯の分解(コスト前)と週末の窓
    seg = []; SEG = (("週末の窓(金曜の最終足 → 月 04)", None), ("月 04〜07 UTC", (4, 7)), ("月 07〜13 UTC", (7, 13)), ("月 13〜21 UTC", (13, 21)), ("月 21 → 火 04 UTC", (21, 28)))
    for s in PAIRS:
        df = load(s); o = df["open"]; c = df["close"]; mons = sorted(set(o.index[(o.index.dayofweek == 0) & (o.index.hour == 4)].normalize()))
        for d in mons:
            def px(h): t = d + pd.Timedelta(hours=h); return o.get(t, np.nan)
            pf = c[(c.index < d) & (c.index >= d - pd.Timedelta(days=3))]; r = dict(sym=s, d=d)
            r[SEG[0][0]] = (px(4) / pf.iloc[-1] - 1) if len(pf) else np.nan
            for nm, hh in SEG[1:]: r[nm] = px(hh[1]) / px(hh[0]) - 1
            seg.append(r)
    SG = pd.DataFrame(seg).set_index("d"); SG["era"] = era(SG.index); cols = [x[0] for x in SEG]
    D2 = (SG.groupby("era")[cols].mean() * 1e4).round(2); D2["月 04 → 火 04 の合計"] = D2[cols[1:]].sum(axis=1).round(2); D2.to_csv("results/q218_mon4_what_changed_2020_d2_sessions.csv"); print("\n== D2 時間帯の分解(4 通貨の平均・bps・コスト前) =="); print(D2.T.to_string())
    print("通貨別(bps):"); print((SG.groupby(["sym", "era"])[cols].mean() * 1e4).round(1).to_string())
    # D3 通貨別
    rows = []
    for s in PAIRS:
        for e in ("前期 2016〜19", "後期 2020〜"):
            m = S[(s, 0)]; m = m[era(m.index) == e]; o_ = pd.concat([S[(s, d)][era(S[(s, d)].index) == e] for d in (1, 2, 3)])
            rows.append(dict(sym=s, era=e, 月_bps=round(float(m.mean()) * 1e4, 2), 火木_bps=round(float(o_.mean()) * 1e4, 2), 上乗せ_bps=round(float(m.mean() - o_.mean()) * 1e4, 2), t=round(tstat(m, o_), 2)))
    D3 = pd.DataFrame(rows); D3.to_csv("results/q218_mon4_what_changed_2020_d3_pairs.csv", index=False); print("\n== D3 通貨別 =="); print(D3.to_string(index=False))
    # D4 / D5 年ごと
    DC = {s: daily_close(s) for s in PAIRS}; ST = {s: states(s) for s in PAIRS}; yrs = sorted(set(B[0].index.year)); rows = []
    for y in yrs:
        m = B[0][B[0].index.year == y]; oth = pd.concat([B[d][B[d].index.year == y] for d in (1, 2, 3)])
        bh = np.mean([float(DC[s][DC[s].index.year == y].iloc[-1] / DC[s][DC[s].index.year == y].iloc[0] - 1) for s in PAIRS]); vol = np.mean([float(DC[s][DC[s].index.year == y].pct_change().std() * np.sqrt(252)) for s in PAIRS])
        ab = np.mean([float((ST[s].sma200[ST[s].index.year == y] >= 0).mean()) for s in PAIRS]); days = pd.DatetimeIndex(DC["USDJPY"][DC["USDJPY"].index.year == y].index)
        rd = np.mean([float((q20.rate_series(s[:3], days) - q20.rate_series("JPY", days)).mean()) for s in PAIRS])
        rows.append(dict(year=y, 月曜の損益_pct=round(float(m.sum()) * 100, 2), 火木の損益_1日あたり_pct=round(float(oth.sum()) / 3 * 100, 2), 月曜の上乗せ_pct=round(float(m.sum() - oth.sum() / 3) * 100, 2), 束の値上がり_pct=round(bh * 100, 1), 金利差_pp=round(rd, 2), 線の上の割合_pct=round(ab * 100, 0), 値動きの大きさ_pct=round(vol * 100, 1), n=len(m)))
    D4 = pd.DataFrame(rows); D4.to_csv("results/q218_mon4_what_changed_2020_d4_years.csv", index=False); print("\n== D4 / D5 年ごと =="); print(D4.to_string(index=False))
    full = D4[D4.year < D4.year.max()] if D4.n.iloc[-1] < 40 else D4
    print("\n== D7 年次の相関(月曜の損益 / 月曜の上乗せ と各項目・年の数 %d) ==" % len(D4))
    for c_ in ("束の値上がり_pct", "金利差_pp", "線の上の割合_pct", "値動きの大きさ_pct", "火木の損益_1日あたり_pct"): print(f"  {c_}: 月曜の損益 {D4.月曜の損益_pct.corr(D4[c_]):+.2f}(順位 {D4.月曜の損益_pct.corr(D4[c_], method='spearman'):+.2f}) / 月曜の上乗せ {D4.月曜の上乗せ_pct.corr(D4[c_]):+.2f}(順位 {D4.月曜の上乗せ_pct.corr(D4[c_], method='spearman'):+.2f})")
    # D6 状態別
    rows = []
    for s in PAIRS:
        m = S[(s, 0)]; st = ST[s].shift(1).reindex(m.index, method="ffill"); rows.append(pd.DataFrame({"r": m, "below": st.sma200 < 0, "ok": st.sma200.notna(), "wkdn": st.wk < 0, "era": era(m.index), "sym": s}))
    P = pd.concat(rows); P = P[P.ok]; out = []
    for e in ("前期 2016〜19", "後期 2020〜"):
        x = P[P.era == e]
        for lab, mk in (("200 日線の下", x.below), ("200 日線の上", ~x.below), ("前週下落", x.wkdn), ("前週上昇", ~x.wkdn)): out.append(dict(era=e, 状態=lab, n=int(mk.sum()), 割合_pct=round(float(mk.mean()) * 100, 1), 平均_bps=round(float(x[mk].r.mean()) * 1e4, 2), 勝率=round(float((x[mk].r > 0).mean()) * 100, 1)))
    D6 = pd.DataFrame(out); D6.to_csv("results/q218_mon4_what_changed_2020_d6_states.csv", index=False); print("\n== D6 状態別(通貨 × 月曜のプール) =="); print(D6.to_string(index=False))
    # 勝ち負けの大きさ
    print("\n== 月曜の束: 勝率・勝ちの平均・負けの平均・標準偏差(bps) ==")
    for e in ("前期 2016〜19", "後期 2020〜"):
        x = B[0][era(B[0].index) == e]; print(f"  {e}: n {len(x)}・平均 {x.mean() * 1e4:+.2f}・勝率 {(x > 0).mean() * 100:.1f}%・勝ち {x[x > 0].mean() * 1e4:+.1f}・負け {x[x <= 0].mean() * 1e4:+.1f}・標準偏差 {x.std() * 1e4:.1f}・最悪 {x.min() * 1e4:.0f}")
