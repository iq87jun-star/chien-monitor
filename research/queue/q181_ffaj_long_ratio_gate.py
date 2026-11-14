# -*- coding: utf-8 -*-
"""docs/244 Q181(改良系・6 セル・2026-11-12 登録「登録して実行してください」): 金融先物取引業協会の店頭 FX 月次統計の買い比率による月曜円クロスの見送りフィルター。
信号 = ペア別 L(M) = 買建 ÷(売建 + 買建)・月末値(results/q180_ffaj_positions.csv・2026-11-12 取得)。既知 = 翌月 21 日(M+1 の 21 日〜M+2 の 20 日の月曜に適用)。
順位 = 直近 36 か月(M−35〜M)の中で L(M) 以下の月の割合。高 = 0.8 以上 / 低 = 0.2 以下。見送りはペア単位。
系列 = deployed_book.mon_cell_h1(EA 実時刻 H1)。帳簿 = Mon4・Mon3・Mon2 instG。セル = 3 帳簿 × {高で見送り, 低で見送り}。判定 = q114.improved。
参照(判定に使わない)= 閾値 0.9 / 0.1・半分サイズ。
使い方: cd research && python3 -W ignore queue/q181_ffaj_long_ratio_gate.py <累積>   出力: results/q181_ffaj_long_ratio_gate.csv・_levels.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "forward")); os.chdir(ROOT)
from q_common import *
from q114_mon_index_intraday import stats, improved
import deployed_book as db
F = pd.read_csv("results/q180_ffaj_positions.csv", parse_dates=["month"])
def rank36(sym):
    s = F[F.pair == sym].set_index("month").long_ratio.sort_index()
    return s.rolling(36, min_periods=36).apply(lambda w: float((w <= w.iloc[-1]).mean()), raw=False)
RK = {p: rank36(p) for p in ("AUDJPY", "EURJPY", "GBPJPY", "USDJPY", "NZDJPY")}
def sig_month(d):
    """月曜 d に既知の最新の月末(21 日以降は前月末、20 日までは前々月末)"""
    first = d.replace(day=1); back = 1 if d.day >= 21 else 2
    return (first - pd.DateOffset(months=back)) + pd.offsets.MonthEnd(0)
def flag(sym, idx, kind, thr):
    r = np.array([RK[sym].get(sig_month(d), np.nan) for d in idx])
    return (r >= thr) if kind == "high" else (r <= thr)
def norm(v):
    v = v.dropna(); v.index = pd.DatetimeIndex(v.index).normalize(); return v.groupby(v.index).sum()
BOOKS = {"Mon4(4 通貨等分)": {"AUDJPY": .25, "EURJPY": .25, "GBPJPY": .25, "USDJPY": .25}, "Mon3(14074882 形)": {"EURJPY": .333, "USDJPY": .333, "NZDJPY": .334}, "Mon2 instG(11988011 形)": {"GBPJPY": .537, "AUDJPY": .463}}
LEG = {s: norm(db.mon_cell_h1(s)) for s in RK}
def book(w, kind=None, thr=None, mult=0.0):
    parts = []
    for s, wt in w.items():
        x = LEG[s].copy()
        if kind: x = x * np.where(flag(s, x.index, kind, thr), mult, 1.0)
        parts.append(x * wt)
    return pd.concat(parts, axis=1).dropna().sum(axis=1)
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q181", cum, 6, "results/q181_ffaj_long_ratio_gate.csv"); rows = []
    for nm, w in BOOKS.items():
        b = book(w); b = b[b.index >= PRE0]
        for kind in ("high", "low"):
            for thr, mult, is_cell in (((0.8 if kind == "high" else 0.2), 0.0, True), ((0.9 if kind == "high" else 0.1), 0.0, False), ((0.8 if kind == "high" else 0.2), 0.5, False)):
                v = book(w, kind, thr, mult); v = v[v.index >= PRE0]; im = improved(b, v)
                if is_cell: R.add("協会統計 買い比率フィルター", nm, f"買い比率の 36 か月順位 {'≥' if kind == 'high' else '≤'} {thr} の間はそのペアを見送り(翌月 21 日から既知)", v)
                bb = b[b.index >= IS0]; on = np.zeros(len(bb), bool); share = []
                for s in w:
                    fl = flag(s, bb.index, kind, thr); share.append(fl.mean()); on |= fl
                d = (b - v).reindex(bb.index)                     # 見送った分の損益(正 = 見送りで失った利益)
                rows.append(dict(book=nm, kind=kind, thr=thr, size=mult, cell="セル" if is_cell else "参照", n_mon=len(bb), mon_any_on=int(on.sum()), pair_on_share=round(float(np.mean(share)), 3),
                                 skipped_mean_bps=round(float(d[on].mean()) * 1e4, 1) if on.any() else None, **im))
    R.finish(); D = pd.DataFrame(rows); D.to_csv("results/q181_ffaj_long_ratio_gate_levels.csv", index=False); pd.set_option("display.width", 320); pd.set_option("display.max_columns", 30)
    print("\n== Q181 改良判定(base/var = (Sharpe, 最悪月%, 累積%)・skipped_mean_bps = 見送った月曜で失った平均損益(帳簿 bps・正なら見送りは損)) ==\n" + D.to_string(index=False))
    print("\n改良成立(セル):", int(D[D.cell == "セル"].ok.sum()), "/ 6")
