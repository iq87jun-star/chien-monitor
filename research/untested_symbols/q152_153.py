# -*- coding: utf-8 -*-
"""Q152〜Q153(結果前に固定)。窓 PRE 2016〜2021-09 / IS 2021-10〜2024 / OOS 2025〜。Dukascopy 1 時間足 BID/ASK。
Q152 Mon 指数 日中版 × M2K(ラッセル 2000 マイクロ)を先物ボットに足すか。
     セル(新規 1・標準基準): US2000 月曜 13→20 UTC LONG・中値 − 先物コスト 1.6 bps(M2K 1 tick × 2 + 手数料)・VIX 門 25(配備形と同じ)。
     ※ Q145 の参考行(CFD 実行値・門なし)で +4.7 / +4.8 / +3.9 bps・IS p 0.10 は既に見えている。標準基準は通らない見込みで、主題は下の帳簿比較。
     帳簿比較(改良系): 現行ボット(MES 5・MNQ 2・MYM 5 → 名目 167k / 98k / 115k ドル比、中値 − 1 bps、VIX 門 25)に M2K 5 枚(名目 62k ドル比)を足す。
     改良 = IS・OOS の両方で週次 Sharpe が上がり、最悪月(名目合計比)が悪化しない。
Q153 VIX 門を CFD の Mon 指数(月曜 13 UTC 建て → 24h LONG・実行値)へ転用(改良系 6 セル)。
     前の取引日の VIX 終値 > 20 / > 25 の月曜は見送る × US500・NAS100・GER40。見送り週は 0 として Sharpe を比べる。
     改良 = IS・OOS の両方で Sharpe が上がり、最悪月が悪化しない(Q121 と同じ基準)。
累積 9,848 → 9,855。"""
import pandas as pd, numpy as np, sys
from math import comb
S = sys.argv[1]
IS0, OOS0 = pd.Timestamp("2021-10-01"), pd.Timestamp("2025-01-01")
WIN = [("PRE", pd.Timestamp("2016-01-01"), IS0), ("IS", IS0, OOS0), ("OOS", OOS0, pd.Timestamp("2027-01-01"))]
NCUM = 9848 + 7
def load(p, d):
    b = pd.read_csv(f"{S}/{d}/{p}_h1.csv", index_col=0, parse_dates=True)["open"]; a = pd.read_csv(f"{S}/{d}/{p}_h1_ask.csv", index_col=0, parse_dates=True)["open"]
    j = b.index.intersection(a.index); b, a = b[j], a[j]; idx = pd.to_datetime(j, utc=True).tz_localize(None); b.index = idx; a.index = idx
    ok = a >= b; return b[ok], a[ok]
vix = pd.read_csv(f"{S}/vix.csv", index_col=0, parse_dates=True).iloc[:, 0].dropna()
def prev_vix(day): x = vix[vix.index < day]; return x.iloc[-1] if len(x) else np.nan
def mon(p, d, h0, dur, mode, cost=0.0):
    b, a = load(p, d); m = (b + a) / 2
    t = b.index[(b.index.dayofweek == 0) & (b.index.hour == h0)]; t2 = t + pd.Timedelta(hours=dur); ok = t2.isin(b.index); t, t2 = t[ok], t2[ok]
    r = (b.reindex(t2).values / a.reindex(t).values - 1) if mode == "exec" else (m.reindex(t2).values / m.reindex(t).values - 1 - cost)
    s = pd.Series(r, index=t.normalize()).dropna(); s = s[~s.index.duplicated()]
    return s
def gate(r, th):
    v = pd.Series([prev_vix(d) for d in r.index], index=r.index); return r.where(~(v > th), 0.0)
def wstats(r):
    out = {}
    for lab, lo, hi in WIN:
        x = r[(r.index >= lo) & (r.index < hi)]
        if len(x) < 8: out[lab] = None; continue
        m = x.groupby(x.index.to_period("M")).sum(); n = len(m); k = int((m > 0).sum())
        out[lab] = dict(bps=x.mean() * 1e4, sh=x.mean() / x.std() * np.sqrt(52), worst=m.min() * 100, n=n, k=k, rate=k / n, p=sum(comb(n, j) for j in range(k, n + 1)) / 2 ** n, nz=int((x != 0).sum()))
    return out
f = lambda s: "-" if s is None else f"{s['bps']:+.1f}bps / Sh {s['sh']:.2f} / 最悪月 {s['worst']:+.2f}% / {s['nz']}回"
rows = []
# ---------- Q152 ----------
FUT = {"US500": 167, "NAS100": 98, "US30": 115}
legs = {p: gate(mon(p, "idx", 13, 7, "mid", 1e-4), 25) for p in FUT}
m2k = gate(mon("US2000", "new", 13, 7, "mid", 1.6e-4), 25)
s = wstats(m2k)
rows.append(dict(Q="Q152", cell="M2K 月曜 13→20 UTC LONG(VIX 門 25)", PRE=f(s["PRE"]), IS=f(s["IS"]) + f" / p{s['IS']['p']:.3g}", OOS=f(s["OOS"]),
                 判定="標準 " + ("通過" if s["IS"]["p"] < 0.05 / NCUM and s["OOS"]["bps"] > 0 and s["PRE"]["rate"] >= 0.5 else "不通過")))
def book(extra):
    df = pd.concat({**legs, **({"US2000": m2k} if extra else {})}, axis=1).dropna()
    w = pd.Series({**FUT, **({"US2000": 62} if extra else {})}); return (df * w).sum(axis=1) / w.sum() * (w.sum() / sum(FUT.values()))  # 現行ボット名目比の損益率
b0, b1 = wstats(book(False)), wstats(book(True))
imp = all(b1[k]["sh"] > b0[k]["sh"] and b1[k]["worst"] >= b0[k]["worst"] for k in ("IS", "OOS"))
rows.append(dict(Q="Q152", cell="帳簿 現行ボット(MES・MNQ・MYM)", PRE=f(b0["PRE"]), IS=f(b0["IS"]), OOS=f(b0["OOS"]), 判定="基準"))
rows.append(dict(Q="Q152", cell="帳簿 + M2K 5 枚", PRE=f(b1["PRE"]), IS=f(b1["IS"]), OOS=f(b1["OOS"]), 判定="改良 " + ("成立" if imp else "不成立")))
jj = pd.concat([m2k, book(False)], axis=1).dropna(); corr = round(float(jj.corr().iloc[0, 1]), 2)
# ---------- Q153 ----------
for p in ["US500", "NAS100", "GER40"]:
    base = mon(p, "idx", 13, 24, "exec"); s0 = wstats(base)
    rows.append(dict(Q="Q153", cell=f"CFD Mon {p} 24h(門なし・配備形)", PRE=f(s0["PRE"]), IS=f(s0["IS"]), OOS=f(s0["OOS"]), 判定="基準"))
    for th in (20, 25):
        s1 = wstats(gate(base, th)); ok = all(s1[k]["sh"] > s0[k]["sh"] and s1[k]["worst"] >= s0[k]["worst"] for k in ("IS", "OOS"))
        rows.append(dict(Q="Q153", cell=f"CFD Mon {p} 24h + VIX 門 {th}", PRE=f(s1["PRE"]), IS=f(s1["IS"]), OOS=f(s1["OOS"]), 判定="改良 " + ("成立" if ok else "不成立")))
R = pd.DataFrame(rows); pd.set_option("display.width", 320); pd.set_option("display.max_colwidth", 80)
print(R.to_string(index=False)); print("M2K と現行ボット帳簿の週次相関:", corr)
R.to_csv(f"{S}/q152_153.csv", index=False)
