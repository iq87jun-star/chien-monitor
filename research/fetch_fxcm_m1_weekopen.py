# -*- coding: utf-8 -*-
"""FXCM 公開ローソク足(m1・BID/ASK・週次ファイル)から、各週の開場後 5 時間分だけを保存する(docs/244 Q193)。
既定のクライアント名で取得し、1 件ごとに間隔を空ける。保存先 data_fxcm/<SYM>_m1_weekopen.csv.gz は git 管理外。
使い方: cd research && python3 fetch_fxcm_m1_weekopen.py GBPJPY 2016 2026"""
import os, sys, io, gzip, time, subprocess
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "data_fxcm")
def get(sym, year, week):
    raw = subprocess.run(["curl", "-s", "--max-time", "40", f"https://candledata.fxcorporate.com/m1/{sym}/{year}/{week}.csv.gz"], capture_output=True).stdout
    try: d = pd.read_csv(io.BytesIO(gzip.decompress(raw)))
    except Exception: return None
    d["timestamp"] = pd.to_datetime(d["DateTime"], format="%m/%d/%Y %H:%M:%S.%f"); return d
if __name__ == "__main__":
    sym = sys.argv[1]; y0, y1 = int(sys.argv[2]), int(sys.argv[3]); os.makedirs(OUT, exist_ok=True); p = os.path.join(OUT, f"{sym}_m1_weekopen.csv.gz"); parts = []; miss = []
    for y in range(y0, y1 + 1):
        for w in range(1, 54):
            d = get(sym, y, w)
            if d is None or not len(d): miss.append((y, w)); time.sleep(0.15); continue
            t0 = d.timestamp.min(); parts.append(d[d.timestamp < t0 + pd.Timedelta(hours=5)].drop(columns=["DateTime"])); time.sleep(0.15)
        print(y, len(parts), flush=True)
    D = pd.concat(parts).drop_duplicates("timestamp").sort_values("timestamp"); D.to_csv(p, index=False, compression="gzip"); print("rows", len(D), "weeks", len(parts), "missing", miss)
