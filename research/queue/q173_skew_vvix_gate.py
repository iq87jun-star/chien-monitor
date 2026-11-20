# -*- coding: utf-8 -*-
"""docs/244 Q173(改良系・新規 6 セル・2026-11-08 ユーザー「SKEW/VVIX 門を登録して今行って」): オプション市場の門。
前金曜(無ければ直前営業日)の CBOE SKEW / VVIX の終値が、直近 252 営業日の 80 分位以上の月曜は見送る規則(skip)が、配備形の
Mon US500 24h・Mon NAS100 24h(13 UTC 建て 24h)・Mon4 円クロス(4/6/8/10 UTC 建て 24h・等ウェイト)を docs/244 §1 の改良系基準
(IS・OOS の両方で Sharpe 改善 かつ 最悪月が悪化しない)で上回るか。セル = 3 系列 × {SKEW, VVIX} = 6。参照(判定に使わない): 半減(half)・VIX > 25 の同型・90 分位。
データ: data_ext/SKEW_History.csv(1990〜)・VVIX_History.csv(2006〜)・VIX_History.csv。
使い方: cd research && python3 queue/q173_skew_vvix_gate.py <累積>   出力: results/q173_skew_vvix_gate.csv・_levels.csv"""
import sys
from q_common import *
from q114_mon_index_intraday import shot, stats, improved
def series(path, col):
    V = pd.read_csv(path); V["d"] = pd.to_datetime(V["DATE"]); return V.set_index("d")[col].sort_index().astype(float)
G = {"SKEW": series("data_ext/SKEW_History.csv", "SKEW"), "VVIX": series("data_ext/VVIX_History.csv", "VVIX"), "VIX": series("data_ext/VIX_History.csv", "CLOSE")}
def pct_rank(v, win=252): return v.rolling(win).apply(lambda w: (w[:-1] < w[-1]).mean(), raw=True)
PR = {k: pct_rank(v) for k, v in G.items() if k != "VIX"}
def norm(v):
    v = v.dropna(); v.index = pd.DatetimeIndex(v.index).normalize(); return v.groupby(v.index).sum()
def gate(s, key, q=0.8, mode="skip"):
    ref = PR[key] if key in PR else G[key]; prev = ref.reindex(s.index - pd.Timedelta(days=3), method="ffill").values   # 前金曜(月曜 − 3 日)の値・無ければ直前
    hi = prev > q
    return s[~hi] if mode == "skip" else s * np.where(hi, 0.5, 1.0)
def mon4_skew_gated(q=0.8):
    """紙上候補 MonSkewGate(docs/409): 配備形 Mon4(等ウェイト)から、前金曜の SKEW が 252 日 q 分位超の月曜を除いた系列。"""
    b = sum(norm(base.mon_cell(s)) * 0.25 for s in ("GBPJPY", "EURJPY", "AUDJPY", "USDJPY")).dropna(); return gate(b[b.index >= PRE0], "SKEW", q, "skip")
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q173", cum, 6, "results/q173_skew_vvix_gate.csv"); rows = []
    B = {"Mon US500 24h": shot("US500", 13, None), "Mon NAS100 24h": shot("NAS100", 13, None), "Mon4 円クロス": sum(norm(base.mon_cell(s)) * 0.25 for s in ("GBPJPY", "EURJPY", "AUDJPY", "USDJPY")).dropna()}
    for nm, b in B.items():
        b = b[b.index >= PRE0]
        for key, q, mode in (("SKEW", 0.8, "skip"), ("VVIX", 0.8, "skip"), ("SKEW", 0.8, "half"), ("VVIX", 0.8, "half"), ("SKEW", 0.9, "skip"), ("VVIX", 0.9, "skip"), ("VIX", 25.0, "skip")):
            v = gate(b, key, q, mode); im = improved(b, v); cell = (q == 0.8 and mode == "skip" and key != "VIX")
            if cell: R.add("オプション門 × 配備形", nm, f"前金曜 {key} が 252 日 80 分位超の月曜は見送り", v)
            sk = b[(b.index >= IS0)]; skipped = int(len(sk) - len(gate(sk, key, q, "skip")))
            rows.append(dict(series=nm, gate=key, q=q, mode=mode, cell="セル" if cell else "参照", n_skipped_IS_OOS=skipped, n_IS_OOS=len(sk), **im))
    R.finish(); D = pd.DataFrame(rows); D.to_csv("results/q173_skew_vvix_gate_levels.csv", index=False); pd.set_option("display.width", 300)
    print("\n== Q173 改良判定(base/var = (Sharpe, 最悪月%, 累積%)) ==\n" + D.to_string(index=False)); print("\n改良成立(セル):", int(D[D.cell == "セル"].ok.sum()), "/ 6")
    # 参考: 見送った月曜の平均リターン(門が「悪い月曜」を当てているか)
    print("\n== 見送り月曜の平均 bps(IS+OOS・コスト後) ==")
    for nm, b in B.items():
        b = b[b.index >= IS0]
        for key in ("SKEW", "VVIX"):
            prev = PR[key].reindex(b.index - pd.Timedelta(days=3), method="ffill").values; hi = prev > 0.8
            print(f"{nm:14s} {key}: 見送り {int(hi.sum())} 週 平均 {b[hi].mean()*1e4:+.1f} bps / 残り {int((~hi).sum())} 週 平均 {b[~hi].mean()*1e4:+.1f} bps")
