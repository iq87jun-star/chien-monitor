# -*- coding: utf-8 -*-
"""docs/244 Q145(週次アイデア束 #1・4 セル): 仲値(9:55 JST)前後の USDJPY。
H1 近似: 仲値前 = 00→01 UTC LONG、仲値後 = 01→02 UTC SHORT。日集合 {全営業日, ゴトー日(5/10/15/20/25/月末・週末は前営業日繰上)}。
コスト往復 3 pip・判定は docs/244 §1(Runner)。ゴトー日の定義は Q14 と同一(複製)。
Q14(docs/258)は同じ家族の 00→01 L / 01→03 S / 01→05 S を 36 セルで棄却済み。本件は 01→02 S(仲値直後 1 時間)を足す登録。
使い方: cd research && python3 queue/q145_tokyo_fix_usdjpy.py <累積セル数>"""
import sys, os
from q_common import *
def gotobi_dates(a, b):
    """Q14(q14_tokyo_fix_early.py)と同一定義(import するとモジュール本体が走るため複製)。"""
    out = set()
    for m in pd.period_range(a, b, freq="M"):
        for dd in (5, 10, 15, 20, 25):
            d = pd.Timestamp(m.year, m.month, dd)
            while d.dayofweek >= 5: d -= pd.Timedelta(days=1)
            out.add(d)
        d = m.to_timestamp(how="end").normalize()
        while d.dayofweek >= 5: d -= pd.Timedelta(days=1)
        out.add(d)
    return out
SYM = "USDJPY"

def cell(df, G, dayset, h_in, h_out, dir_):
    o = df["open"]; t = o.index[(o.index.hour == h_in) & (o.index.dayofweek <= 4)]
    if dayset == "ゴトー日": t = t[pd.DatetimeIndex(t.normalize()).isin(G)]
    r = trades(SYM, t, o.reindex(t).values, dir_ * np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=h_out - h_in)).values); return r

if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q145", cum, 4, "results/q145_tokyo_fix_usdjpy.csv")
    df = load(SYM); selfcheck(SYM, df); G = pd.DatetimeIndex(gotobi_dates(df.index[0], df.index[-1]))
    for dayset in ("全営業日", "ゴトー日"):
        R.add("仲値 USDJPY", SYM, f"{dayset} 00→01 UTC LONG(仲値前)", cell(df, G, dayset, 0, 1, +1))
        R.add("仲値 USDJPY", SYM, f"{dayset} 01→02 UTC SHORT(仲値後)", cell(df, G, dayset, 1, 2, -1))
    R.finish()
