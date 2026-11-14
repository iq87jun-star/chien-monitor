# -*- coding: utf-8 -*-
"""docs/244 Q205(改良系・2 セル・2026-11-14 登録「登録して実行」): 水曜ロール(Roll5・金利差門 2.0pp)× 200 日線の状態で数量を変える。
ベース = 水曜 20:00 UTC 始値で USDJPY・EURJPY・GBPJPY・AUDJPY・CADJPY を SHORT → 木曜 00:00 UTC 始値で決済・5 本等分・通貨別の政策金利差 2.0pp 未満の本は 0(紙上 RollGateB2 の形)。
状態 = 通貨ごとに、建て日より前の最後の確定日足(H1 終値を +2 時間ずらして束ねた日足)で 終値 < SMA200 なら「下」。未計算の期間は 1.0 倍。
(A) 下で売る = 下 1.0 倍・上 0.5 倍。(B) 上で売る = 上 1.0 倍・下 0.5 倍。判定 = §1 改良系(IS・OOS の両方で Sharpe 改善 かつ 最悪月が悪化しない)。
データ = Dukascopy(〜2026-08)+ FXCM 継ぎ足し。使い方: cd research && python3 queue/q205_roll5_sma200_state.py <累積セル数>   出力: results/q205_roll5_sma200_state.csv・_ref.csv"""
import sys, os
from q_common import *
from q20_wed_swap_carry import rate_series
from q147_roll_rate_diff_gate import stats, improved
from fetch_fxcm import load_spliced
PAIRS = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"]; GATE = 2.0; PRE1 = IS0 - pd.Timedelta(hours=1)
def bars(sym):
    df = load_spliced(sym); df = df[~df.index.duplicated(keep="last")]; return df[((df.high > df.low) | (df.volume > 0)) & (df.index >= PRE0)]
def leg(sym):
    o = bars(sym)["open"]; t = o.index[(o.index.dayofweek == 2) & (o.index.hour == 20)]
    r = trades(sym, t, o.reindex(t).values, -np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=4)).values); r.index = r.index.normalize(); return r
def below200(sym, dates):
    """建て日より前の最後の確定日足で 終値 < SMA200 か。戻り値: (下か[bool], 計算済みか[bool])"""
    c = bars(sym)["close"]; d = (c.index + pd.Timedelta(hours=2)).normalize(); x = c.groupby(d).last(); x = x[x.index.dayofweek < 5]
    s = (x / x.rolling(200).mean() - 1).shift(1).reindex(pd.DatetimeIndex(dates), method="ffill"); return (s < 0).fillna(False).values, s.notna().values
def welch(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 5 or len(b) < 5: return None
    return round(float((a.mean() - b.mean()) / np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))), 2)
def roll5_sma200(variant="B"):
    """紙上候補 RollSma200B(docs/444): Roll5(門 2.0pp・5 本等分)で、200 日線の上の通貨 1.0 倍・下の通貨 0.5 倍(variant "A" は逆)。index = 建て日(水曜)。"""
    L = {s: leg(s) for s in PAIRS}; days = pd.DatetimeIndex(sorted(set().union(*[set(L[s].index) for s in PAIRS]))); jp = rate_series("JPY", days); out = {}
    for s in PAIRS:
        lo, ok = below200(s, days); f = np.where(ok & (lo if variant == "B" else ~lo), 0.5, 1.0)
        out[s] = L[s] * (rate_series(s[:3], days) - jp >= GATE).reindex(L[s].index).fillna(False).astype(float) * pd.Series(f, index=days).reindex(L[s].index)
    return pd.DataFrame(out).fillna(0.0).sum(axis=1) / len(PAIRS)
if __name__ == "__main__":
    cum = int(sys.argv[1]); N = 2; L = {s: leg(s) for s in PAIRS}; days = pd.DatetimeIndex(sorted(set().union(*[set(L[s].index) for s in PAIRS]))); jp = rate_series("JPY", days)
    G = {s: (rate_series(s[:3], days) - jp >= GATE) for s in PAIRS}; ST = {s: below200(s, days) for s in PAIRS}
    def fam(fac):  # fac(下か, 計算済みか) → 倍率
        df = pd.DataFrame({s: L[s] * G[s].reindex(L[s].index).fillna(False).astype(float) * pd.Series(fac(*ST[s]), index=days).reindex(L[s].index) for s in PAIRS}).fillna(0.0); return df.sum(axis=1) / len(PAIRS)
    base_ = fam(lambda lo, ok: np.ones(len(lo)))
    A = fam(lambda lo, ok: np.where(ok & ~lo, 0.5, 1.0)); B = fam(lambda lo, ok: np.where(ok & lo, 0.5, 1.0)); rows = []
    assert np.allclose(B.values, roll5_sma200("B").reindex(B.index).values) and np.allclose(A.values, roll5_sma200("A").reindex(A.index).values)
    for nm, v in (("A 下で売る(下 1.0・上 0.5)", A), ("B 上で売る(上 1.0・下 0.5)", B)):
        r = improved(base_, v); rows.append(dict(cell=nm, base_PRE=r["base_PRE"], var_PRE=r["var_PRE"], base_IS=r["base_IS"], var_IS=r["var_IS"], base_OOS=r["base_OOS"], var_OOS=r["var_OOS"], improved=r["ok"]))
    D = pd.DataFrame(rows); D.to_csv("results/q205_roll5_sma200_state.csv", index=False); pd.set_option("display.width", 300); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 300)
    print(f"Q205: cells={N} cum_before={cum} cum_after={cum + N} improved={int(D.improved.sum())}/{N}  データ末尾 {days.max().date()}  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)")
    print(D.to_string(index=False))
    # 参考: 状態別の分解(本ごとの損益をプール)
    ref = []; WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END))
    for gl, gated in (("門 2.0pp あり", True), ("門なし", False)):
        P = []
        for s in PAIRS:
            lo, ok = ST[s]; x = pd.DataFrame({"r": L[s], "lo": pd.Series(lo, index=days).reindex(L[s].index), "ok": pd.Series(ok, index=days).reindex(L[s].index), "g": G[s].reindex(L[s].index).fillna(False)}); x["sym"] = s; P.append(x[(x.g | (not gated)) & x.ok])
        P = pd.concat(P)
        for wn, a, b in WIN:
            w = P[(P.index >= a) & (P.index <= b)]; lo_, hi_ = w[w.lo.astype(bool)].r, w[~w.lo.astype(bool)].r
            ref.append(dict(gate=gl, sym="5 本プール", window=wn, n_below=len(lo_), mean_below_bps=round(float(lo_.mean()) * 1e4, 2) if len(lo_) else None, win_below=round(float((lo_ > 0).mean()) * 100, 1) if len(lo_) else None,
                            n_above=len(hi_), mean_above_bps=round(float(hi_.mean()) * 1e4, 2) if len(hi_) else None, win_above=round(float((hi_ > 0).mean()) * 100, 1) if len(hi_) else None, welch_t_below_minus_above=welch(lo_, hi_)))
            if gated:
                for s in PAIRS:
                    ws = w[w.sym == s]; l2, h2 = ws[ws.lo.astype(bool)].r, ws[~ws.lo.astype(bool)].r
                    ref.append(dict(gate=gl, sym=s, window=wn, n_below=len(l2), mean_below_bps=round(float(l2.mean()) * 1e4, 2) if len(l2) else None, win_below=round(float((l2 > 0).mean()) * 100, 1) if len(l2) else None,
                                    n_above=len(h2), mean_above_bps=round(float(h2.mean()) * 1e4, 2) if len(h2) else None, win_above=round(float((h2 > 0).mean()) * 100, 1) if len(h2) else None, welch_t_below_minus_above=welch(l2, h2)))
        allw = P; lo_, hi_ = allw[allw.lo.astype(bool)].r, allw[~allw.lo.astype(bool)].r
        ref.append(dict(gate=gl, sym="5 本プール", window="全期間", n_below=len(lo_), mean_below_bps=round(float(lo_.mean()) * 1e4, 2), win_below=round(float((lo_ > 0).mean()) * 100, 1), n_above=len(hi_), mean_above_bps=round(float(hi_.mean()) * 1e4, 2), win_above=round(float((hi_ > 0).mean()) * 100, 1), welch_t_below_minus_above=welch(lo_, hi_)))
    RF = pd.DataFrame(ref); RF.to_csv("results/q205_roll5_sma200_state_ref.csv", index=False); print("\n== 参考: 状態別(本ごと・コスト後) ==\n" + RF.to_string(index=False))
