# -*- coding: utf-8 -*-
"""docs/334 §5 Q116(1 セル + 参照): 円建て日経先物 NIY=F(CME・Yahoo)で Mon JP225 の 13→20 UTC を再現し、CFD JP225 および米ドル建て NKD=F と比較する。
セル = NIY 13→20(標準基準で数える・IS 8 か月で判定不能)。参照 = 13→翌13、日足 2016〜の月曜清算→火曜清算(PRE/IS/OOS・NIY の Yahoo 日足は清算値のみのバーが多く始値→終値は使えない)、NIY vs NKD。コスト: NIY 1.5 bps(1 ティック 5 円 + 手数料)。
使い方: cd research && SSL_CERT_FILE=/root/.ccr/ca-bundle.crt python3 queue/q116_niy_vs_jp225.py <累積セル数>"""
import sys
from q_common import *
from q114_mon_index_intraday import shot as cfd_shot
import q115_futures_vs_cfd as q115
from q115_futures_vs_cfd import fut_shot, compare, fut_h1, fut_d1
q115.FUT_COST["NIY=F"] = 1.5e-4
def fut_mon_cc(sym):
    """日足参照: 月曜清算値 → 火曜清算値(NIY の Yahoo 日足は 63% が清算値のみの 4 本値同一バーで始値→終値が使えないため、清算値同士で比較)。index = 月曜。"""
    d = fut_d1(sym)["close"]; d.index = d.index.normalize(); m = d.index[d.index.dayofweek == 0]; nxt = d.reindex(m + pd.Timedelta(days=1)).values
    r = pd.Series(nxt / d.reindex(m).values - 1 - q115.FUT_COST[sym], index=m); return r.dropna()
def cfd_mon_cc(sym):
    """CFD 側の対応: 月曜 20 UTC バー始値 → 火曜 20 UTC バー始値(21 UTC は冬時間に欠けるため・清算 16:00 ET に近い共通時刻)。"""
    o = load(sym)["open"]; m = pd.DatetimeIndex(sorted(set(o.index[o.index.dayofweek == 0].normalize()))); t0 = m + pd.Timedelta(hours=20); t1 = t0 + pd.Timedelta(days=1)
    r = pd.Series(o.reindex(t1).values / o.reindex(t0).values - 1, index=m).dropna(); return r - cost(sym, np.ones(len(r)))
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q116", cum, 1, "results/q116_niy_vs_jp225.csv"); rows = []
    H0 = max(fut_h1(s).index.min() for s in ("NIY=F", "NKD=F")).normalize(); H1 = pd.Timestamp("2026-08-31")
    v = fut_shot("NIY=F", 13, 20); R.add("Mon 指数 日中版(先物・円建て)", "NIY=F", "月曜 13 UTC 建て → 同日 20 UTC 決済(CME 円建て日経・Yahoo H1)", v)
    rows.append(dict(pair="NIY vs JP225(CFD)", form="13→20 UTC(セル)", window=f"{H0.date()}〜{H1.date()}", **compare(v, cfd_shot("JP225", 13, 20), H0, H1)))
    rows.append(dict(pair="NIY vs JP225(CFD)", form="13→翌13 UTC(参照)", window=f"{H0.date()}〜{H1.date()}", **compare(fut_shot("NIY=F", 13, None), cfd_shot("JP225", 13, None), H0, H1)))
    rows.append(dict(pair="NIY vs NKD(先物同士)", form="13→20 UTC(参照)", window=f"{H0.date()}〜{H1.date()}", **compare(v, fut_shot("NKD=F", 13, 20), H0, H1)))
    fm, cm, nk = fut_mon_cc("NIY=F"), cfd_mon_cc("JP225"), fut_mon_cc("NKD=F")
    for w, (a, b) in dict(PRE=(PRE0, IS0), IS=(IS0, IS1), OOS=(OOS0, H1)).items():
        rows.append(dict(pair="NIY vs JP225(CFD)", form=f"月曜清算→火曜清算 日足(参照・{w})", window=f"{a.date()}〜{b.date()}", **compare(fm, cm, a, b)))
        rows.append(dict(pair="NIY vs NKD(先物同士)", form=f"月曜清算→火曜清算 日足(参照・{w})", window=f"{a.date()}〜{b.date()}", **compare(fm, nk, a, b)))
    R.finish(); pd.set_option("display.width", 300); D = pd.DataFrame(rows); D.to_csv("results/q116_niy_vs_jp225_compare.csv", index=False)
    print("\n== Q116 NIY(円建て)vs JP225 CFD / NKD(週次: 相関・Sharpe・最悪月 %・累積 %・平均差 bps・符号一致率)==\n" + D.to_string(index=False))
