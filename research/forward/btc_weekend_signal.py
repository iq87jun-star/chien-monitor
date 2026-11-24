# -*- coding: utf-8 -*-
"""docs/519 §8(2026-11-24 登録): 週末の BTC の騰落を月曜の建ての前に記録する(紙の上の記録・EA は変えない)。
定義は Q282(docs/524)と同じ: 金曜の終値 → 日曜の終値(Yahoo 日足)の騰落を、直前 52 週の週末の騰落の標準偏差で割った z。
帯: z ≥ +2 =「見送り相当(BTC)」/ +1 ≤ z < +2 =「注意」/ z ≤ −2 =「下げた週」/ それ以外 =「通常」。
使い方: cd research && python3 -W ignore forward/btc_weekend_signal.py [--dry] [YYYY-MM-DD(月曜)]   既定 = 直近の月曜。--dry は表示だけで、CSV に足さない。
出力: forward/btc_weekend_log.csv に 1 行足す(同じ週の行が既にあれば足さない)。"""
import os, sys, csv, time, datetime as dt
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); os.chdir(ROOT)
import recentfit_screen as base
LOG = os.path.join(HERE, "btc_weekend_log.csv"); COLS = ["week_monday", "checked_at_utc", "fri_close", "sun_close", "weekend_ret_pct", "z", "band", "note"]
def series():
    base.DATA = os.path.join(ROOT, "data_live"); os.makedirs(base.DATA, exist_ok=True); p = os.path.join(base.DATA, "BTCUSD_rf.csv")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) > 3600: os.remove(p)
    base.P1_EPOCH = 1451606400; base.P2_EPOCH = int(time.time()); b = pd.read_csv(base.fetch("BTCUSD")); b["d"] = pd.to_datetime(b["timestamp"]).dt.normalize()
    return b.drop_duplicates("d", keep="last").set_index("d")["close"].astype(float)
def signal(c, monday):
    M = pd.date_range("2016-01-04", monday, freq="7D"); wr = pd.Series({d: (c.get(d - pd.Timedelta(days=1), float("nan")) / c.get(d - pd.Timedelta(days=3), float("nan")) - 1) for d in M}).dropna()
    z = wr / wr.rolling(52).std().shift(1); return wr, z
def band(z): return "見送り相当(BTC)" if z >= 2 else ("注意" if z >= 1 else ("下げた週" if z <= -2 else "通常"))
if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--dry"]; dry = "--dry" in sys.argv; now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    monday = pd.Timestamp(args[0]) if args else pd.Timestamp(now.date()) - pd.Timedelta(days=now.weekday()) + (pd.Timedelta(days=7) if now.weekday() == 6 else pd.Timedelta(0))
    c = series(); wr, z = signal(c, monday)
    if monday not in z.index or z[monday] != z[monday]: print(f"BTC の週末の値が取れない(月曜 {monday.date()}・データの最終日 {c.index[-1].date()})"); sys.exit(1)
    fri = float(c[monday - pd.Timedelta(days=3)]); sun = float(c[monday - pd.Timedelta(days=1)]); zz = float(z[monday]); row = [str(monday.date()), now.strftime("%Y-%m-%d %H:%M:%S"), round(fri, 1), round(sun, 1), round(float(wr[monday]) * 100, 2), round(zz, 2), band(zz), "日曜の終値は確認時点の値" if now < monday.to_pydatetime() else ""]
    print(f"週末の BTC: 金曜 {fri:,.0f} → 日曜 {sun:,.0f}({wr[monday] * 100:+.2f}%)・z {zz:+.2f}・{band(zz)}(月曜 {monday.date()} の週)")
    print("直近 6 週:", [(str(d.date()), round(float(v), 2)) for d, v in z.dropna().tail(6).items()])
    if dry: sys.exit(0)
    have = set()
    if os.path.exists(LOG):
        with open(LOG, encoding="utf-8") as f: have = {r["week_monday"] for r in csv.DictReader(f)}
    else:
        with open(LOG, "w", encoding="utf-8", newline="") as f: csv.writer(f).writerow(COLS)
    if str(monday.date()) in have: print("この週の行は記録済み(足さない)")
    else:
        with open(LOG, "a", encoding="utf-8", newline="") as f: csv.writer(f).writerow(row)
        print("記録した:", LOG)
