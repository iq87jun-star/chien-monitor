# -*- coding: utf-8 -*-
"""Q180(docs/244 2026-11-12 登録・診断・セル 0): ポジション系データの棚卸し。
 金融先物取引業協会(FFAJ)「店頭 FX 月次速報」trading_vol_and_position.xls を取得し、通貨ペア別の月末 売建 / 買建(百万円換算)を
 results/q180_ffaj_positions.csv に整形する。損益との関係は計算しない(検定は別項目で事前登録してから)。
 東京金融取引所(くりっく365)の日次相場表 CSV は建玉の合計のみ(売買別なし)であることを 1 日分で確認する。
使い方: cd research && python3 -W ignore queue/q180_positioning_inventory.py [FFAJ の xls の URL]"""
import os, sys, io, subprocess
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT)
URL = sys.argv[1] if len(sys.argv) > 1 else "https://www.ffaj.or.jp/wp-content/uploads/2026/10/trading_vol_and_position.xls"
os.makedirs("data_ext", exist_ok=True); p = "data_ext/ffaj_trading_vol_and_position.xls"
raw = subprocess.run(["curl", "-s", "--max-time", "60", URL], capture_output=True).stdout
if len(raw) > 10000: open(p, "wb").write(raw)
x = pd.ExcelFile(p, engine="xlrd"); out = []
for sn in x.sheet_names:
    if sn in ("note",): continue
    d = x.parse(sn, header=None)
    r = d[pd.to_numeric(d[0], errors="coerce").between(1, 12) & pd.to_numeric(d[1], errors="coerce").between(2000, 2100)]
    if not len(r): continue
    o = pd.DataFrame({"pair": sn, "month": pd.to_datetime(dict(year=r[1].astype(int), month=r[0].astype(int), day=1)) + pd.offsets.MonthEnd(0),
                      "vol_mjpy": pd.to_numeric(r[2], errors="coerce"), "short_mjpy": pd.to_numeric(r[3], errors="coerce"), "long_mjpy": pd.to_numeric(r[4], errors="coerce")})
    o["long_ratio"] = o.long_mjpy / (o.long_mjpy + o.short_mjpy); out.append(o)
f = pd.concat(out).sort_values(["pair", "month"]); f.to_csv("results/q180_ffaj_positions.csv", index=False)
g = f.groupby("pair").agg(months=("month", "count"), first=("month", "min"), last=("month", "max"), long_ratio_last=("long_ratio", "last"), long_ratio_med=("long_ratio", "median"),
                          long_ratio_p10=("long_ratio", lambda s: s.quantile(.1)), long_ratio_p90=("long_ratio", lambda s: s.quantile(.9)))
g["first"] = g["first"].dt.strftime("%Y-%m"); g["last"] = g["last"].dt.strftime("%Y-%m")
pd.set_option("display.width", 220); print(g.round(3).to_string()); print("sheets:", len(x.sheet_names), "/ rows:", len(f))
# くりっく365 日次相場表(1 日分)
t = subprocess.run(["curl", "-s", "--max-time", "30", "https://www.tfx.co.jp/kawase/document/PRT-010-CSV-003-20261111.CSV"], capture_output=True).stdout.decode("cp932", "replace").splitlines()
rows = [l.split(",") for l in t if l.startswith("D01")]
print("TFX 日次 CSV: 行", len(rows), "列", len(rows[0]) if rows else 0, "例", rows[0][3], "取引数量", rows[0][-2], "建玉数量(合計のみ)", rows[0][-1])
