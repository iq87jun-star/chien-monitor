# -*- coding: utf-8 -*-
"""docs/244 Q148(16 セル・基準の確認): Mon4 全セル(GBPJPY/EURJPY/AUDJPY/USDJPY × 月曜 h4/6/8/10 UTC 建て LONG → 24h 後決済)を
現実価格(建て = ask 始値・決済 = bid 始値・追加コスト 0)で再判定する。従来(docs/229)は bid→bid − 往復 3 pip の仮定。
ask は docs/372 の納品(2016-01〜2026-09・11 ペア)。USDJPY は納品外で ask 2024-01〜 のみ → 前窓なし(基準上は合格不能・参考)。
判定は docs/244 §1 の新規セル基準(Runner: IS 2021-10〜2024-12 の +月二項 p < 0.05/累積、OOS 平均 > 0、前窓 +月率 ≥ 50%)。
併記: 従来仮定(bid−3pip)の同セル・両者の 1 取引平均(pip)・実効往復スプレッド(pip)。
使い方: cd research && python3 queue/q148_mon4_realprice_recheck.py <累積セル数>"""
import sys, os
from q_common import *
from q_bin_common import load_ask
PAIRS = ["GBPJPY", "EURJPY", "AUDJPY", "USDJPY"]; HOURS = (4, 6, 8, 10)

def shot_real(sym, h_in):
    b = load(sym)["open"]; a = load_ask(sym)["open"]; j = pd.concat([b.rename("bid"), a.rename("ask")], axis=1).dropna()
    t = j.index[(j.index.dayofweek == 0) & (j.index.hour == h_in)]
    p_in = j.ask.reindex(t).values; p_out = j.bid.reindex(t + pd.Timedelta(hours=24)).values; ok = ~np.isnan(p_in) & ~np.isnan(p_out)
    r = pd.Series(p_out[ok] / p_in[ok] - 1.0, index=t[ok]); r.index = r.index.normalize()
    sp = pd.Series((j.ask - j.bid).reindex(t[ok]).values / base.pip_size(sym), index=r.index)   # 建て時のスプレッド(pip)
    sp_out = pd.Series(((j.ask - j.bid).reindex(t[ok] + pd.Timedelta(hours=24)).values) / base.pip_size(sym), index=r.index)
    return r, sp, sp_out

def shot_bid(sym, h_in):
    o = load(sym)["open"]; t = o.index[(o.index.dayofweek == 0) & (o.index.hour == h_in)]
    r = trades(sym, t, o.reindex(t).values, np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=24)).values); r.index = r.index.normalize(); return r

def pip_mean(r, sym, a, b):
    x = r[(r.index >= a) & (r.index <= b)]; return round(float(x.mean()) / base.pip_size(sym) * 1.0 * 100, 1) if len(x) else float("nan")  # 対数近似: ret/pip_size ≈ pip/価格 → ×価格は省略(比較用に bps 表示)

if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q148", cum, len(PAIRS) * len(HOURS), "results/q148_mon4_realprice_recheck.csv"); cmp = []
    for sym in PAIRS:
        for h in HOURS:
            rr, sp_in, sp_out = shot_real(sym, h); rb = shot_bid(sym, h)
            R.add("Mon4 現実価格(ask 建て・bid 決済)", sym, f"Mon h{h} 24h LONG real", rr)
            si_r, so_r, sp_r = st(rr, IS0, IS1), st(rr, OOS0, END), st(rr, PRE0, IS0); si_b, so_b, sp_b = st(rb, IS0, IS1), st(rb, OOS0, END), st(rb, PRE0, IS0)
            cmp.append(dict(symbol=sym, h=h, n_real=len(rr), real_from=str(rr.index.min().date()),
                            pre_rate_real=sp_r["rate"], pre_rate_bid=sp_b["rate"], is_rate_real=si_r["rate"], is_rate_bid=si_b["rate"], is_mean_bps_real=si_r["mean"], is_mean_bps_bid=si_b["mean"], p_real=si_r["p"], p_bid=si_b["p"],
                            oos_rate_real=so_r["rate"], oos_rate_bid=so_b["rate"], oos_mean_bps_real=so_r["mean"], oos_mean_bps_bid=so_b["mean"],
                            spread_in_med_pip=round(float(sp_in[(sp_in.index >= IS0)].median()), 2), spread_out_med_pip=round(float(sp_out[(sp_out.index >= IS0)].median()), 2),
                            rt_spread_med_pip=round(float((sp_in + sp_out)[(sp_in.index >= IS0)].median()), 2)))
    R.finish(); C = pd.DataFrame(cmp); C.to_csv("results/q148_mon4_realprice_compare.csv", index=False); pd.set_option("display.width", 320)
    print("\n== 現実価格 vs 従来仮定(bid−3pip)==\n" + C.to_string(index=False))
