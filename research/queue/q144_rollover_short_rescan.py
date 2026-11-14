# -*- coding: utf-8 -*-
"""docs/244 Q144(週次アイデア束 #1): ロールオーバー帯(21〜23 UTC 建て)の SHORT セルを現実価格で再走査。
docs/367 の bid アーティファクトの逆: bid 始値は 21〜23 UTC にスプレッド拡大で沈むので、bid→bid で測った SHORT は不利に見えていた。
セル = 銘柄 × 建て {21,22,23} UTC × 保有 {1,2}h の SHORT(月〜金プール・建て曜日 月〜金)。
現実価格: 売り建て = bid 始値、買い戻し = ask 始値、追加コスト 0。ask が 2016〜 の 12 ペアは全窓を現実価格で判定(主系列)。
ask が 2024〜 の銘柄は登録どおり主系列 = bid − 往復 3 pip(§1)で判定し、2024〜26 の現実価格(符号・大きさ)を併記する。
判定は docs/244 §1(Runner: IS 2021-10〜2024-12 の +月二項 p < 0.05/累積・OOS 平均 > 0・前窓 +月率 ≥ 50%)。
銘柄: ask のある 22 のうち USDTRY / USDMXN / USDZAR(前窓が 2018〜・スプレッド数十 pip で §1 のコスト模型が当てはまらない)を除く 19 = 114 セル。
使い方: cd research && python3 queue/q144_rollover_short_rescan.py <累積セル数>"""
import sys, os
from q_common import *
from q_bin_common import load_ask
FULL = ["AUDJPY", "AUDUSD", "CADJPY", "CHFJPY", "EURAUD", "EURGBP", "EURJPY", "GBPJPY", "GBPUSD", "NZDJPY", "USDCHF", "USDJPY"]   # ask 2016〜
PART = ["EURUSD", "GBPAUD", "GER40", "NAS100", "NZDUSD", "US500", "XAUUSD"]                                                        # ask 2024〜
HOURS = (21, 22, 23); HOLDS = (1, 2)

def short_real(sym, h, hold):
    b = load(sym)["open"]; a = load_ask(sym)["open"]; j = pd.concat([b.rename("bid"), a.rename("ask")], axis=1).dropna()
    t = j.index[(j.index.hour == h) & (j.index.dayofweek <= 4)]
    p_in = j.bid.reindex(t).values; p_out = j.ask.reindex(t + pd.Timedelta(hours=hold)).values; ok = ~np.isnan(p_in) & ~np.isnan(p_out)
    return pd.Series(p_in[ok] / p_out[ok] - 1.0, index=t[ok])

def short_bid(sym, h, hold):
    o = load(sym)["open"]; t = o.index[(o.index.hour == h) & (o.index.dayofweek <= 4)]
    return trades(sym, t, o.reindex(t).values, -np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=hold)).values)

def seg(r, a, b):
    s = st(r, a, b); return s["rate"], s["mean"], s["n"]

if __name__ == "__main__":
    cum = int(sys.argv[1]); SYMS = FULL + PART; R = Runner("Q144", cum, len(SYMS) * len(HOURS) * len(HOLDS), "results/q144_rollover_short_rescan.csv"); cmp = []
    for sym in SYMS:
        for h in HOURS:
            for hold in HOLDS:
                rr = short_real(sym, h, hold); rb = short_bid(sym, h, hold); primary = rr if sym in FULL else rb
                R.add("Roll帯 SHORT 現実価格" if sym in FULL else "Roll帯 SHORT bid−3pip(現実 2024〜 併記)", sym, f"SHORT h{h} UTC hold {hold}h Mon-Fri", primary)
                r24 = rr[rr.index >= "2024-01-01"]; b24 = rb[rb.index >= "2024-01-01"]
                cmp.append(dict(symbol=sym, h=h, hold=hold, basis=("real" if sym in FULL else "bid-3pip"),
                                is_rate=seg(primary, IS0, IS1)[0], is_mean_bps=seg(primary, IS0, IS1)[1], oos_mean_bps=seg(primary, OOS0, END)[1], pre_rate=seg(primary, PRE0, IS0)[0],
                                real24_rate=seg(r24, PRE0, END)[0], real24_mean_bps=seg(r24, PRE0, END)[1], bid24_mean_bps=seg(b24, PRE0, END)[1], n24=len(r24)))
    R.finish(); C = pd.DataFrame(cmp); C.to_csv("results/q144_rollover_short_compare.csv", index=False); pd.set_option("display.width", 320)
    print("\n== 現実価格 2024〜26 で 1 取引平均が正のセル(上位 15)==")
    print(C.sort_values("real24_mean_bps", ascending=False).head(15).to_string(index=False))
    print("\n== bid−3pip → 現実価格 の差(2024〜26・bps)の分布: 中央 %.1f / 最大 %.1f" % ((C.real24_mean_bps - C.bid24_mean_bps).median(), (C.real24_mean_bps - C.bid24_mean_bps).max()))
