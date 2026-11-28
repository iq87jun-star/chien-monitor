# -*- coding: utf-8 -*-
"""docs/244 Q204(週次アイデア束 #5・ai-council 2026-11-14 ①・新規 1 セル): RollCHF。
水曜 20:00 UTC の H1 足始値で USDCHF・GBPCHF・AUDCHF・NZDCHF・CADCHF を SHORT、木曜 00:00 UTC の足始値で決済(4 時間・Roll5 と同じ窓)。
門: 相手通貨と CHF の政策金利差(q20 の RATES)が 2.0pp 以上の週のみ。束 = その週に門を満たし 20 時・24 時の足がある銘柄の等加重(コスト後)。該当 0 本の週は取引なし。
判定は docs/244 §1 標準基準(束の月次・二項 p < 0.05 / 累積・IS 月数 ≥ 24・OOS 平均 > 0・前窓 +月率 ≥ 50%)。コスト FX 往復 3pip。
データ: USDCHF・GBPCHF・CADCHF = Dukascopy 〜 2026-08 + FXCM 継ぎ足し(fetch_fxcm.load_spliced)、AUDCHF・NZDCHF = FXCM 公開アーカイブ(H1・BID)。
参考(判定に使わない): ペア別・門を満たした週数・Roll5 との日次相関・欠け週・夏時間 / 冬時間別・門なし・現実価格(bid 建て → ask 決済)。
使い方: cd research && python3 queue/q204_roll_chf_funding_bundle.py <累積セル数>   出力: results/q204_roll_chf_funding_bundle.csv・_ref.csv"""
import sys, os
from q_common import *
from q20_wed_swap_carry import rate_series
from fetch_fxcm import load_spliced, load_fxcm
PAIRS = ["USDCHF", "GBPCHF", "AUDCHF", "NZDCHF", "CADCHF"]; FXCM_ONLY = {"AUDCHF", "NZDCHF"}; ROLL5 = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"]; GATE = 2.0
def bars(sym, ask=False):
    df = load_fxcm(sym, ask) if sym in FXCM_ONLY else load_spliced(sym, ask); df = df[~df.index.duplicated(keep="last")]
    return df[((df.high > df.low) | (df.volume > 0)) & (df.index >= PRE0)]
def leg(sym):
    """水曜 20 UTC 建て SHORT → 木曜 00 UTC 決済(全週)。index = 建て日。戻り値: (コスト後リターン, 水曜 20 時の足がある日, 現実価格のリターン or None)"""
    o = bars(sym)["open"]; t = o.index[(o.index.dayofweek == 2) & (o.index.hour == 20)]; out = o.reindex(t + pd.Timedelta(hours=4)).values
    r = trades(sym, t, o.reindex(t).values, -np.ones(len(t)), out); r.index = r.index.normalize(); real = None
    try:
        a = bars(sym, ask=True)["open"]; ao = a.reindex(t + pd.Timedelta(hours=4)).values; pin = o.reindex(t).values; ok = ~np.isnan(ao) & ~np.isnan(pin)
        real = pd.Series(-(ao[ok] / pin[ok] - 1.0), index=t[ok].normalize())                 # bid で売り建て → ask で買い戻し(追加コストなし)
    except FileNotFoundError: pass
    return r, pd.DatetimeIndex(t.normalize()), real
def bundle(legs, gates):
    df = pd.DataFrame({s: legs[s][gates[s].reindex(legs[s].index).fillna(False).values] for s in legs}); return df.mean(axis=1).dropna(), df
def us_dst(d):
    y = d.year; mar = pd.Timestamp(y, 3, 8); mar += pd.Timedelta(days=(6 - mar.dayofweek) % 7); nov = pd.Timestamp(y, 11, 1); nov += pd.Timedelta(days=(6 - nov.dayofweek) % 7); return mar <= d < nov
WINS = (("前窓", PRE0, IS0 - pd.Timedelta(hours=1)), ("IS", IS0, IS1), ("OOS", OOS0, END))
def wstat(x, a, b):
    s = st(x, a, b); y = x[(x.index >= a) & (x.index <= b)]
    return dict(months=f"{s['plus']}/{s['n']}", mean_bps=s["mean"], trades=s["trades"], win_wk=(round(float((y > 0).mean()) * 100, 1) if len(y) else None), p=(round(s["p"], 4) if s["n"] else None))
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q204", cum, 1, "results/q204_roll_chf_funding_bundle.csv"); L = {}; HAVE = {}; REAL = {}
    for s in PAIRS:
        L[s], HAVE[s], REAL[s] = leg(s); selfcheck(s, bars(s))
    weds = pd.date_range("2016-01-06", L["USDCHF"].index.max(), freq="W-WED"); chf = rate_series("CHF", weds)
    G = {s: (rate_series(s[:3], weds) - chf >= GATE) for s in PAIRS}; B, DF = bundle(L, G)
    R.add("RollCHF", "CHF5", f"Wed 20-00UTC SHORT gate{GATE} 等加重", B); res = R.finish(); ref = []
    print(f"\nデータ末尾: " + " ".join(f"{s} {L[s].index.min().date()}〜{L[s].index.max().date()}" for s in PAIRS))
    # (1)(2)(4) ペア別・門を満たした週数・欠け週
    for s in PAIRS:
        g = G[s]; x = L[s][g.reindex(L[s].index).fillna(False).values]
        for wn, a, b in WINS:
            m = (weds >= a.normalize()) & (weds <= b); elig = weds[m][g[m].values]; miss = [d for d in elig if d not in L[s].index]
            ref.append(dict(item="ペア別(門あり)", sym=s, window=wn, gate_weeks=len(elig), all_weeks=int(m.sum()), missing=len(miss), **wstat(x, a, b)))
    for wn, a, b in WINS:
        m = (weds >= a.normalize()) & (weds <= b); anyg = pd.DataFrame(G)[m].any(axis=1); nb = DF[(DF.index >= a.normalize()) & (DF.index <= b)].notna().sum(axis=1)
        ref.append(dict(item="束(門あり・判定対象)", sym="CHF5", window=wn, gate_weeks=int(anyg.sum()), all_weeks=int(m.sum()), missing=int(anyg.sum() - (nb > 0).sum()), avg_legs=round(float(nb[nb > 0].mean()), 2), **wstat(B, a, b)))
    # (6) 門なし
    Ball = pd.DataFrame(L).mean(axis=1).dropna()
    for wn, a, b in WINS: ref.append(dict(item="束(門なし)", sym="CHF5", window=wn, **wstat(Ball, a, b)))
    # (5) 夏時間 / 冬時間
    dst = pd.Series([us_dst(d) for d in B.index], index=B.index)
    for lab, mm in (("米国夏時間", dst), ("米国冬時間", ~dst)):
        for wn, a, b in WINS: ref.append(dict(item=f"束・{lab}", sym="CHF5", window=wn, **wstat(B[mm.values], a, b)))
    # (3) Roll5 との相関
    r5 = pd.DataFrame({s: leg(s)[0] for s in ROLL5}).mean(axis=1).dropna(); jp = rate_series("JPY", weds)
    r5g = pd.DataFrame({s: leg(s)[0][(rate_series(s[:3], weds) - jp >= GATE).reindex(leg(s)[0].index).fillna(False).values] for s in ROLL5}).mean(axis=1).dropna()
    for nm, rr in (("Roll5(門なし・5 本等分)", r5), ("Roll5(門 2.0pp・該当本の等分)", r5g)):
        for wn, a, b in WINS + (("全期間", PRE0, END),):
            j = pd.concat([B, rr], axis=1, keys=["b", "r"]).dropna(); j = j[(j.index >= a.normalize()) & (j.index <= b)]
            ref.append(dict(item=f"相関: {nm}", sym="CHF5", window=wn, trades=len(j), corr=(round(float(j.b.corr(j.r)), 3) if len(j) > 5 else None), roll5_mean_bps=(round(float(j.r.mean()) * 1e4, 2) if len(j) else None), mean_bps=(round(float(j.b.mean()) * 1e4, 2) if len(j) else None)))
    # (7) 現実価格(ask がある銘柄・期間のみ)
    RD = pd.DataFrame({s: REAL[s][G[s].reindex(REAL[s].index).fillna(False).values] for s in PAIRS if REAL[s] is not None}); Breal = RD.mean(axis=1).dropna()
    for wn, a, b in WINS: ref.append(dict(item="束・現実価格(bid 建て → ask 決済・ask のある銘柄のみ: " + "・".join(RD.columns) + ")", sym="CHF5", window=wn, **wstat(Breal, a, b)))
    for s in RD.columns:
        for wn, a, b in WINS: ref.append(dict(item="ペア別・現実価格", sym=s, window=wn, **wstat(RD[s].dropna(), a, b)))
    RF = pd.DataFrame(ref); RF.to_csv("results/q204_roll_chf_funding_bundle_ref.csv", index=False); pd.set_option("display.width", 300); pd.set_option("display.max_rows", 300); pd.set_option("display.max_columns", 30)
    print("\n== 参考記録 ==\n" + RF.to_string(index=False))
    y = B.groupby(B.index.year).agg(["count", "mean", lambda q: (q > 0).mean()]); y.columns = ["weeks", "mean", "win"]; y["mean"] = (y["mean"] * 1e4).round(2); y["win"] = (y["win"] * 100).round(1); print("\n== 束・年別 ==\n" + y.to_string())
