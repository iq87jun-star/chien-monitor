# -*- coding: utf-8 -*-
"""docs/322 §5d Q115(4 セル + 参照): 先物 vs 現物 CFD。Q114 の Mon 指数(13 UTC 建て → 同日 20 UTC / → 翌 13 UTC)を CME 先物連続限月(Yahoo ES=F / NQ=F / YM=F / NKD=F・H1 は 2024-05-17〜)で
再現し、同一期間の CFD(Dukascopy H1)と週次リターンの相関・Sharpe・最悪月を比べる。セル = 先物 4 銘柄の 13→20(標準基準で数える・IS は 2024-05〜12 の 8 か月しかなく判定不能=数えるだけ)。
参照: (a) 先物 13→翌13 vs CFD 24h、(b) 日足 2016〜 の「月曜セッション(Globex 日 18:00 ET → 月 17:00 ET)始値→終値」を先物と CFD(日 22/23 UTC 始値 → 月 21 UTC 始値)で全窓比較。
先物コスト(往復・bps 固定): ES 0.6 / NQ 0.3 / YM 0.5 / NKD 1.5(1 ティック + 手数料 $4 の概算・ミクロは手数料比率が上がる)。
使い方: cd research && SSL_CERT_FILE=/root/.ccr/ca-bundle.crt python3 queue/q115_futures_vs_cfd.py <累積セル数>"""
import sys, os, json, time, urllib.request, datetime as dt
from q_common import *
from q114_mon_index_intraday import shot as cfd_shot, stats
PAIR = {"US500": "ES=F", "NAS100": "NQ=F", "US30": "YM=F", "JP225": "NKD=F"}
FUT_COST = {"ES=F": 0.6e-4, "NQ=F": 0.3e-4, "YM=F": 0.5e-4, "NKD=F": 1.5e-4}
CACHE = "data_yahoo_fut"; os.makedirs(CACHE, exist_ok=True)
def yahoo(sym, iv, qs):
    f = os.path.join(CACHE, f"{sym.replace('=','')}_{iv}.csv")
    if os.path.exists(f): return pd.read_csv(f, index_col=0, parse_dates=True)
    u = f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(sym, safe='=')}?interval={iv}&{qs}"
    for i in range(6):
        try: d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=40))["chart"]["result"][0]; break
        except Exception as e: err = e; time.sleep(2 * (i + 1))
    else: raise RuntimeError(f"yahoo {sym} {iv}: {err}")
    q = d["indicators"]["quote"][0]; df = pd.DataFrame(dict(open=q["open"], high=q["high"], low=q["low"], close=q["close"]), index=pd.to_datetime(d["timestamp"], unit="s"))
    df = df.dropna(); df = df[~df.index.duplicated(keep="last")].sort_index(); df.to_csv(f); time.sleep(0.6); return df
def fut_h1(sym): return yahoo(sym, "1h", "range=730d")   # Yahoo の H1 は直近 730 日のみ(period 指定は 422)
def fut_d1(sym): return yahoo(sym, "1d", f"period1={int(dt.datetime(2016, 1, 1).timestamp())}&period2={int(time.time())}")
def fut_shot(sym, h_in, h_out_same_day):
    o = fut_h1(sym)["open"]; t = o.index[(o.index.dayofweek == 0) & (o.index.hour == h_in)]
    t_out = (t + pd.Timedelta(hours=24)) if h_out_same_day is None else pd.DatetimeIndex([x.normalize() + pd.Timedelta(hours=h_out_same_day) for x in t])
    pi, po = o.reindex(t).values, o.reindex(t_out).values; ok = ~np.isnan(pi) & ~np.isnan(po)
    r = pd.Series(po[ok] / pi[ok] - 1 - FUT_COST[sym], index=t[ok]); r.index = r.index.normalize(); return r
def fut_mon_session(sym):
    """日足: 月曜バー(Globex 日 18:00 ET → 月 17:00 ET)の始値→終値。index = 月曜。"""
    d = fut_d1(sym); d = d[d.index.dayofweek == 0]; return pd.Series(d["close"].values / d["open"].values - 1 - FUT_COST[sym], index=d.index.normalize())
def cfd_mon_session(sym):
    """CFD H1: 日曜 20 UTC 以降の最初のバー始値 → 月曜 21 UTC バー始値(なければ 20 UTC)。index = 月曜。"""
    o = load(sym)["open"]; mons = pd.DatetimeIndex(sorted(set(o.index[o.index.dayofweek == 0].normalize()))); rows = {}
    for m in mons:
        a = o[(o.index >= m - pd.Timedelta(hours=4)) & (o.index < m + pd.Timedelta(hours=21))]
        b = o.reindex([m + pd.Timedelta(hours=21)]).values[0]
        if np.isnan(b): b = o.reindex([m + pd.Timedelta(hours=20)]).values[0]
        if len(a) and not np.isnan(b): rows[m] = b / a.iloc[0] - 1
    r = pd.Series(rows); return r - cost(sym, np.ones(len(r)))
def compare(f, c, a, b):
    j = pd.concat([f, c], axis=1, keys=["fut", "cfd"]).dropna(); j = j[(j.index >= a) & (j.index <= b)]
    sf, sc = stats(j.fut, a, b), stats(j.cfd, a, b)
    return dict(n=len(j), corr=round(float(j.fut.corr(j.cfd)), 3), fut_sharpe=sf[0], cfd_sharpe=sc[0], fut_worst=sf[1], cfd_worst=sc[1], fut_cum=sf[2], cfd_cum=sc[2],
                diff_bps=round(float((j.fut - j.cfd).mean()) * 1e4, 2), same_sign=round(float((np.sign(j.fut) == np.sign(j.cfd)).mean()), 3))
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q115", cum, 4, "results/q115_futures_vs_cfd.csv"); rows = []
    H0 = max(fut_h1(s).index.min() for s in PAIR.values()).normalize(); H1 = pd.Timestamp("2026-08-31")
    for cfd, fut in PAIR.items():
        v = fut_shot(fut, 13, 20); R.add("Mon 指数 日中版(先物)", fut, "月曜 13 UTC 建て → 同日 20 UTC 決済(CME 連続限月・Yahoo H1)", v)
        rows.append(dict(symbol=cfd, fut=fut, form="13→20 UTC(セル)", window=f"{H0.date()}〜{H1.date()}", **compare(v, cfd_shot(cfd, 13, 20), H0, H1)))
        rows.append(dict(symbol=cfd, fut=fut, form="13→翌13 UTC(参照)", window=f"{H0.date()}〜{H1.date()}", **compare(fut_shot(fut, 13, None), cfd_shot(cfd, 13, None), H0, H1)))
        fm, cm = fut_mon_session(fut), cfd_mon_session(cfd)
        for w, (a, b) in dict(PRE=(PRE0, IS0), IS=(IS0, IS1), OOS=(OOS0, H1)).items():
            rows.append(dict(symbol=cfd, fut=fut, form=f"月曜セッション 日足(参照・{w})", window=f"{a.date()}〜{b.date()}", **compare(fm, cm, a, b)))
    R.finish(); pd.set_option("display.width", 300); D = pd.DataFrame(rows); D.to_csv("results/q115_futures_vs_cfd_compare.csv", index=False)
    print("\n== Q115 先物 vs CFD(週次リターン: 相関・Sharpe・最悪月 %・累積 %・平均差 bps・符号一致率)==\n" + D.to_string(index=False))
