# -*- coding: utf-8 -*-
"""Dukascopy の日次 M1 ローソク(BID/ASK_candles_min_1.bi5)を取得し、14:00〜17:30 UTC だけを残して data_dukascopy_m1/<SYM>_<side>_m1_1400_1730.csv.gz に保存(docs/284 家族 2: フィックス前後)。
使い方: python3 tools/dukascopy_m1_fetch.py bid EURUSD,GBPUSD,USDJPY,AUDUSD 2024-01-01 2026-08-31 <予算分>
raw キャッシュ data_dukascopy_m1/raw/<SYM>/<YYYY-MM-DD>_<side>.bi5、manifest.json に日単位の完了を記録。週末はスキップ。404 は空日として完了扱い。"""
import os, sys, time, lzma, struct, json, datetime as dt, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import dukascopy_fetch as dk
D = "data_dukascopy_m1"; os.makedirs(D + "/raw", exist_ok=True); MF = D + "/manifest.json"
def load_mf(): return json.load(open(MF)) if os.path.exists(MF) else {}
def decode_day(data, sym, day):
    raw = lzma.decompress(data); sc = dk.scale(sym); rows = []
    for i in range(0, len(raw) - 23, 24):
        t, o, c, l, h, v = struct.unpack(">5if", raw[i:i + 24]); rows.append((day + pd.Timedelta(seconds=t), o / sc, h / sc, l / sc, c / sc, v))   # Dukascopy 順: time, open, close, low, high
    return rows
def main():
    side = sys.argv[1]; syms = sys.argv[2].split(","); d0 = pd.Timestamp(sys.argv[3]); d1 = pd.Timestamp(sys.argv[4]); budget = float(sys.argv[5]) * 60 if len(sys.argv) > 5 else 1e12; t0 = time.time()
    mf = load_mf(); n_new = 0
    for sym in syms:
        key = f"{sym}|{side}"; done = set(mf.get(key, {}).get("days", [])); os.makedirs(f"{D}/raw/{sym}", exist_ok=True)
        for day in pd.bdate_range(d0, d1):
            ds = day.strftime("%Y-%m-%d")
            if ds in done: continue
            if time.time() - t0 > budget: print(f"[予算] {sys.argv[5]} 分に到達 → 終了", flush=True); save(mf, side, syms); return
            f = f"{D}/raw/{sym}/{ds}_{side}.bi5"
            if not os.path.exists(f):
                st, data = dk.fetch(f"https://datafeed.dukascopy.com/datafeed/{sym}/{day.year}/{day.month - 1:02d}/{day.day:02d}/{side.upper()}_candles_min_1.bi5"); time.sleep(dk.GAP)
                if st == 404: open(f, "wb").write(b"")
                elif st == 200 and data: open(f, "wb").write(data)
                else: print(f"  [{sym}] {ds} 取得失敗(st={st})", flush=True); continue
            done.add(ds); n_new += 1; mf.setdefault(key, {})["days"] = sorted(done)
            if n_new % 20 == 0: json.dump(mf, open(MF, "w"), indent=1); print(f"  [{sym}] {ds} 済 (+{n_new})", flush=True)
    save(mf, side, syms)
def save(mf, side, syms):
    json.dump(mf, open(MF, "w"), indent=1)
    for sym in syms:
        rows = []
        for f in sorted(os.listdir(f"{D}/raw/{sym}")):
            if not f.endswith(f"_{side}.bi5") or os.path.getsize(f"{D}/raw/{sym}/{f}") == 0: continue
            day = pd.Timestamp(f[:10]); rows += [r for r in decode_day(open(f"{D}/raw/{sym}/{f}", "rb").read(), sym, day) if 14 <= r[0].hour < 17 or (r[0].hour == 17 and r[0].minute < 30)]
        if rows:
            df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"]); df.to_csv(f"{D}/{sym}_{side}_m1_1400_1730.csv.gz", index=False)
            print(f"[{sym}] {side} M1 rows={len(df)} days={len(mf.get(f'{sym}|{side}', {}).get('days', []))} → {D}/{sym}_{side}_m1_1400_1730.csv.gz", flush=True)
if __name__ == "__main__": main()
