# -*- coding: utf-8 -*-
"""docs/244 Q161(新規 1 セル・2026-11-06 登録・ai-council 11/6 ①): XAUUSD の金曜の窓 LONG。
セル = 木曜 18 UTC 足の始値で LONG(COMEX 清算後)→ 金曜 17 UTC 足の始値で決済(COMEX 清算前)。コスト XAUUSD 5 bps 往復(q_common.trades)。
判定 = docs/244 §1 標準(Runner: IS 2021-10〜2024-12 二項 p < 0.05/累積・IS 月数 ≥ 24・OOS 平均 > 0・前窓 +月率 ≥ 50%。XAU H1 は 2021-01 開始のため前窓は 2021-01〜09 の 9 か月 = Q123/Q128 と同じ扱い)。
参照(判定に使わない): ±1 時間(17/19 UTC 建て・16/18 UTC 決済)、雇用統計の金曜(第 1 金曜・近似)除外、区間分解(木 18→24 UTC / 金 00→17 UTC)、Hold XAU(日次)・Thu XAUUSD(木曜 o2o・紙上候補)との日次相関。
データ: data_dukascopy/XAUUSD_hour.csv.gz(2021-01〜2025-12・週末埋め足は high==low で除外)。2026 年分は Dukascopy 不通(429)のため無し。
使い方: cd research && python3 queue/q161_xau_friday_window_long.py <累積>   出力: results/q161_xau_friday_window_long.csv・_levels.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
from q_common import *
from q114_mon_index_intraday import stats
SYM = "XAUUSD"
DF = load(SYM); O = DF["open"]; REAL = (DF["high"] > DF["low"])   # 埋め足(週末・休場)は high==low
def window(h_in, h_out, dow_in=3, dow_out=4, exclude=None):
    t_in = O.index[(O.index.dayofweek == dow_in) & (O.index.hour == h_in)]
    t_out = pd.DatetimeIndex([x.normalize() + pd.Timedelta(days=(dow_out - dow_in)) + pd.Timedelta(hours=h_out) for x in t_in])
    ok = t_out.isin(O.index) & REAL.reindex(t_in).fillna(False).values & REAL.reindex(t_out).fillna(False).values
    t_in, t_out = t_in[ok], t_out[ok]
    if exclude is not None: keep = ~pd.DatetimeIndex(t_out.normalize()).isin(exclude); t_in, t_out = t_in[keep], t_out[keep]
    r = trades(SYM, t_in, O.reindex(t_in).values, np.ones(len(t_in)), O.reindex(t_out).values); r.index = r.index.normalize(); return r
def first_fridays():
    d = pd.date_range("2021-01-01", "2026-12-31", freq="D"); f = d[d.dayofweek == 4]
    return pd.DatetimeIndex([x for x in f if x.day <= 7])   # 雇用統計 = 第 1 金曜の近似(BLS の例外・祝日ずれは未反映)
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q161", cum, 1, "results/q161_xau_friday_window_long.csv"); rows = []
    base_s = window(18, 17)
    R.add("XAU 金曜の窓", SYM, "木曜 18 UTC LONG → 金曜 17 UTC 決済(COMEX 清算後 → 清算前)", base_s); R.finish()
    variants = [("セル 木18→金17", base_s), ("参照 木17→金17", window(17, 17)), ("参照 木19→金17", window(19, 17)), ("参照 木18→金16", window(18, 16)), ("参照 木18→金18", window(18, 18)),
                ("参照 雇用統計金曜除外", window(18, 17, exclude=first_fridays())), ("区間 木18→金00", window(18, 0, 3, 4)), ("区間 金00→金17", window(0, 17, 4, 4))]
    for nm, s in variants:
        for w, lo, hi in (("前窓 2021-01〜09", PRE0, IS0), ("IS", IS0, IS1), ("OOS 2025", OOS0, END)):
            q = st(s, lo, hi); sh, worst, cumr = stats(s, lo, hi)
            rows.append(dict(系列=nm, 窓=w, 月数=q["n"], プラス月=q["plus"], 勝率=q["rate"], 取引=q["trades"], 平均bps=q["mean"], Sharpe=sh, 最悪月pct=worst, 累積pct=cumr, p=q["p"]))
    T = pd.DataFrame(rows); pd.set_option("display.width", 260); print("\n" + T.to_string(index=False)); T.to_csv("results/q161_xau_friday_window_long_levels.csv", index=False)
    # 相関(日次・2021-10〜)
    import forward.paper_forward as pf
    hold = base.hold_cell("XAUUSD"); thu = pf.candidate_series("Thu", "XAUUSD", 3, False)
    def dcorr(a, b):
        j = a.index.intersection(b.index); j = j[j >= IS0]; return (round(float(np.corrcoef(a[j], b[j])[0, 1]), 3), len(j)) if len(j) > 10 else (float("nan"), len(j))
    hold_fri = hold[hold.index.dayofweek == 4]; thu_d = thu.copy(); thu_d.index = pd.DatetimeIndex(thu_d.index).normalize()
    bf = base_s.copy(); bf.index = bf.index + pd.Timedelta(days=1)   # 決済日(金曜)に揃える
    print("\n金曜の窓 vs Hold XAU の同じ金曜(日次 close→close):", dcorr(bf, hold_fri))
    print("金曜の窓(木曜日付)vs Thu XAUUSD(木曜 o2o 24h・日足):", dcorr(base_s, thu_d))
    wk = lambda s_: s_.groupby(pd.PeriodIndex(s_.index, freq="W")).sum().pipe(lambda x: x.set_axis(x.index.to_timestamp()))
    print("週次: 金曜の窓 vs Hold XAU(週合計):", dcorr(wk(base_s), wk(hold)))
