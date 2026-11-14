# -*- coding: utf-8 -*-
"""Q179(docs/244 2026-11-12 登録・診断・セル 0): 代替データ源の到達性と銘柄カバレッジ。
 (a) Yahoo(yfinance): Q164 の 25 銘柄 + WTI の日足開始年・行数、1 時間足(直近 730 日)の行数。
 (b) FXCM 公開ローソク足アーカイブ(candledata.fxcorporate.com・H1・BID/ASK・週次ファイル): 既存 Dukascopy H1 との照合(GBPJPY・AUDJPY・2024 年)。
     Yahoo 日足と Dukascopy H1 から作った日足(各 UTC 時刻締め)の日次リターン相関 → Yahoo 日足の締め時刻を推定。
 (c) Q164 の登録(H1・4/6/8/10 UTC 建て・実行値コスト = BID/ASK)を変えずに実行できる銘柄数。
 既定のクライアント名で応答する取得元だけを使う(ブラウザを装って制限を回避しない)。
使い方: cd research && python3 -W ignore queue/q179_alt_data_sources.py   出力: results/q179_alt_data_coverage.csv / q179_alt_data_quality.csv"""
import os, sys, io, gzip, time, subprocess
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT)
import yfinance as yf
YT = {"XPTUSD": "PL=F", "XPDUSD": "PA=F", "COPPER": "HG=F", "XRPUSD": "XRP-USD", "LTCUSD": "LTC-USD", "ADAUSD": "ADA-USD", "SGDJPY": "SGDJPY=X", "USDNOK": "NOK=X", "USDSEK": "SEK=X",
      "EURNOK": "EURNOK=X", "EURSEK": "EURSEK=X", "USDCNH": "CNH=X", "USDSGD": "SGD=X", "USDPLN": "PLN=X", "EURPLN": "EURPLN=X", "USDHUF": "HUF=X", "USDCZK": "CZK=X",
      "SUI20": "^SSMI", "ESP35": "^IBEX", "NLD25": "^AEX", "ITA40": "FTSEMIB.MI", "FRA40": "^FCHI", "CHI50": "XIN9.FGI", "IND50": "^NSEI", "US2000": "^RUT", "WTI(Q158)": "CL=F"}
KIND = {**{k: "先物(限月つなぎ・CFD スポットと別物)" for k in ("XPTUSD", "XPDUSD", "COPPER", "WTI(Q158)")}, **{k: "暗号資産(現物・24h)" for k in ("XRPUSD", "LTCUSD", "ADAUSD")},
        **{k: "現物指数(現地の取引時間のみ・24h の CFD ではない)" for k in ("SUI20", "ESP35", "NLD25", "ITA40", "FRA40", "CHI50", "IND50", "US2000")}}
rows = []
SKIP_A = os.path.exists('results/q179_alt_data_coverage.csv') and len(sys.argv) > 1 and sys.argv[1] == 'quality'
for sym, t in ({} if SKIP_A else YT).items():
    r = dict(symbol=sym, yahoo=t, kind=KIND.get(sym, "為替(気配の合成・BID/ASK なし)"))
    try:
        d = yf.download(t, start="2010-01-01", interval="1d", progress=False, auto_adjust=False)
        r.update(daily_rows=len(d), daily_from=str(d.index.min().date()) if len(d) else "", daily_to=str(d.index.max().date()) if len(d) else "")
    except Exception as e: r.update(daily_rows=0, daily_err=str(e)[:60])
    try:
        h = yf.download(t, period="730d", interval="1h", progress=False, auto_adjust=False)
        r.update(h1_rows=len(h), h1_from=str(h.index.min())[:10] if len(h) else "", h1_hours_per_day=round(len(h) / max(1, h.index.normalize().nunique()), 1) if len(h) else 0)
    except Exception as e: r.update(h1_rows=0, h1_err=str(e)[:60])
    rows.append(r); time.sleep(0.4)
if SKIP_A: cov = pd.read_csv("results/q179_alt_data_coverage.csv")
else:
    cov = pd.DataFrame(rows); cov["bid_ask"] = "なし"
    cov["q164_as_registered"] = "不可(H1 の BID/ASK が無い・5 年分の H1 が無い)"
    cov.to_csv("results/q179_alt_data_coverage.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
print(cov[["symbol", "yahoo", "daily_rows", "daily_from", "h1_rows", "h1_from", "h1_hours_per_day", "kind"]].to_string(index=False))

# (b) FXCM H1(BID/ASK)と Dukascopy H1 の照合
def fxcm(sym, year, weeks):
    out = []
    for w in weeks:
        try:
            raw = subprocess.run(["curl", "-s", "--max-time", "30", f"https://candledata.fxcorporate.com/H1/{sym}/{year}/{w}.csv.gz"], capture_output=True).stdout
            out.append(pd.read_csv(io.BytesIO(gzip.decompress(raw))))
        except Exception: pass
        time.sleep(0.15)
    d = pd.concat(out); d["t"] = pd.to_datetime(d["DateTime"], format="%m/%d/%Y %H:%M:%S.%f"); return d.drop_duplicates("t").set_index("t").sort_index()
def duka(sym, ask=False):
    d = pd.read_csv(f"data_dukascopy/{sym}_hour{'_ask' if ask else ''}.csv.gz", parse_dates=["timestamp"]).set_index("timestamp"); return d[d.volume > 0]
q = []
for sym in ("GBPJPY", "AUDJPY"):
    f = fxcm(sym, 2024, range(1, 53)); b = duka(sym); a = duka(sym, True)
    j = pd.DataFrame({"f_bid": f.BidClose, "f_ask": f.AskClose, "d_bid": b.close, "d_ask": a.close}).dropna()
    rf, rd = np.log(j.f_bid).diff(), np.log(j.d_bid).diff()
    lb = np.log(b.close).diff(); cand = []
    for k in (-2, -1, 0, 1, 2):
        x = np.log(f.BidClose).diff(); x.index = x.index + pd.Timedelta(hours=k); x, yv = x.align(lb, join="inner"); cand.append((k, float(x.corr(yv))))
    best = max(cand, key=lambda z: z[1])
    pip = 0.01
    q.append(dict(check=f"FXCM H1 vs Dukascopy H1 {sym} 2024", n=len(j), corr_h1_ret=round(float(rf.corr(rd)), 4), best_shift_h=best[0], corr_at_best=round(float(best[1]), 4),
                  med_abs_diff_pips=round(float((j.f_bid - j.d_bid).abs().median() / pip), 2), spread_fxcm_pips=round(float((j.f_ask - j.f_bid).median() / pip), 2), spread_duka_pips=round(float((j.d_ask - j.d_bid).median() / pip), 2),
                  spread_fxcm_4_10utc=round(float((j.f_ask - j.f_bid)[j.index.hour.isin([4, 6, 8, 10])].median() / pip), 2), spread_duka_4_10utc=round(float((j.d_ask - j.d_bid)[j.index.hour.isin([4, 6, 8, 10])].median() / pip), 2)))
# Yahoo 日足の締め時刻(Dukascopy H1 の各 UTC 時刻締めの日次リターンとの相関)
for sym, t in (("USDJPY", "JPY=X"), ("GBPJPY", "GBPJPY=X")):
    if not os.path.exists(f"data_dukascopy/{sym}_hour.csv.gz"): continue
    y = yf.download(t, start="2021-01-01", end="2026-08-31", interval="1d", progress=False, auto_adjust=False)["Close"].squeeze(); y.index = pd.to_datetime(y.index).tz_localize(None)
    b = duka(sym).close; res = []
    for hh in range(0, 24):
        dd = b[b.index.hour == hh]; dd.index = dd.index.normalize(); r1, r2 = np.log(y).diff().align(np.log(dd).diff(), join="inner")
        for lag in (0, 1):
            res.append((hh, lag, float(r1.corr(r2.shift(-lag) if lag else r2))))
    hh, lag, c = max(res, key=lambda x: x[2])
    q.append(dict(check=f"Yahoo 日足 vs Dukascopy H1 {sym}(日次リターン)", n=len(y), corr_h1_ret=np.nan, best_shift_h=hh, corr_at_best=round(c, 4), note=f"最良 = Dukascopy の {hh}:00 UTC 足の終値(翌日ずれ {lag})"))
qd = pd.DataFrame(q); qd.to_csv("results/q179_alt_data_quality.csv", index=False); print(); print(qd.to_string(index=False))
