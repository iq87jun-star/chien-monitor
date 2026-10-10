# -*- coding: utf-8 -*-
"""docs/322 §5g Q119(診断・セル 0): NIY(円建て日経先物・CME)を先物口座の 4 本目(月曜 13 → 20 UTC・1 枚)に載せる前の流動性・コスト確認。
(1) Yahoo H1 の出来高: 13〜20 UTC(米国時間)と 00〜06 UTC(東京時間)の 1 本当たり出来高、13:00 と 20:00 UTC バーのゼロ出来高率、NKD との比較。
(2) コスト感応度: NIY 13→20 の週次系列をコスト 1.5 / 3 / 5 / 8 bps で再計算(2024-05〜2026-08)。CFD JP225 の同系列(4 bps)を併記。
使い方: cd research && SSL_CERT_FILE=/root/.ccr/ca-bundle.crt python3 queue/q119_niy_liquidity.py"""
import os, json, time, urllib.request
from q_common import *
from q114_mon_index_intraday import shot as cfd_shot, stats
CACHE = "data_yahoo_fut"; os.makedirs(CACHE, exist_ok=True)
def h1v(sym):
    f = os.path.join(CACHE, f"{sym.replace('=','')}_1h_vol.csv")
    if os.path.exists(f): return pd.read_csv(f, index_col=0, parse_dates=True)
    u = f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(sym, safe='=')}?interval=1h&range=730d"
    for i in range(6):
        try: d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=40))["chart"]["result"][0]; break
        except Exception as e: err = e; time.sleep(2 * (i + 1))
    else: raise RuntimeError(f"yahoo {sym}: {err}")
    q = d["indicators"]["quote"][0]; df = pd.DataFrame(dict(open=q["open"], high=q["high"], low=q["low"], close=q["close"], volume=q["volume"]), index=pd.to_datetime(d["timestamp"], unit="s"))
    df = df[~df.index.duplicated(keep="last")].sort_index(); df = df[df.open.notna()]; df.to_csv(f); time.sleep(0.6); return df
rows = []
for sym in ("NIY=F", "NKD=F"):
    d = h1v(sym); d = d[d.index >= "2025-01-01"]; v = d.volume.fillna(0); h = d.index.hour; wd = d.index.dayofweek
    us = v[(h >= 13) & (h < 20)]; tk = v[(h >= 0) & (h < 6)]; mon13 = v[(wd == 0) & (h == 13)]; mon20 = v[(wd == 0) & (h == 20)]
    rows.append(dict(sym=sym, bars=len(d), us_vol_per_bar=round(us.mean(), 1), tokyo_vol_per_bar=round(tk.mean(), 1), us_zero_share=round(float((us == 0).mean()), 3),
                     mon13_vol=round(mon13.mean(), 1), mon13_zero=round(float((mon13 == 0).mean()), 3), mon20_vol=round(mon20.mean(), 1), mon20_zero=round(float((mon20 == 0).mean()), 3),
                     us_range_bps=round(float(((d.high - d.low) / d.open)[(h >= 13) & (h < 20)].mean() * 1e4), 1)))
V = pd.DataFrame(rows); pd.set_option("display.width", 250); print("== 出来高(2025-01〜・Yahoo H1・枚)==\n" + V.to_string(index=False)); V.to_csv("results/q119_niy_liquidity_volume.csv", index=False)
# コスト感応度
o = h1v("NIY=F")["open"]; t = o.index[(o.index.dayofweek == 0) & (o.index.hour == 13)]; t_out = pd.DatetimeIndex([x.normalize() + pd.Timedelta(hours=20) for x in t])
pi, po = o.reindex(t).values, o.reindex(t_out).values; ok = ~np.isnan(pi) & ~np.isnan(po); raw = pd.Series(po[ok] / pi[ok] - 1, index=t[ok]); raw.index = raw.index.normalize()
H0, H1 = raw.index.min(), pd.Timestamp("2026-08-31"); rows = []
for c in (1.5, 3, 5, 8):
    s = raw - c * 1e-4; st_ = stats(s, H0, H1); rows.append(dict(leg="NIY 13→20", cost_bps=c, n=len(s[(s.index >= H0) & (s.index <= H1)]), sharpe=st_[0], worst_m=st_[1], cum=st_[2], mean_bps=round(float(s.mean() * 1e4), 1)))
cfd = cfd_shot("JP225", 13, 20); cfd = cfd[(cfd.index >= H0) & (cfd.index <= H1)]; st_ = stats(cfd, H0, H1)
rows.append(dict(leg="CFD JP225 13→20(4 bps)", cost_bps=4, n=len(cfd), sharpe=st_[0], worst_m=st_[1], cum=st_[2], mean_bps=round(float(cfd.mean() * 1e4), 1)))
C = pd.DataFrame(rows); print(f"\n== コスト感応度({H0.date()}〜{H1.date()})==\n" + C.to_string(index=False)); C.to_csv("results/q119_niy_liquidity_cost.csv", index=False)
