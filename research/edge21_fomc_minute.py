"""
edge21_fomc_minute.py — FOMC発表後ドリフトの分足検定【事前登録 docs/106】。
Dukascopy USA500IDXUSD 分足BID(発表日82日, docs/81 §5のリストを逐語流用)。
H21a: 初動15分(14:00-14:15 ET)の符号に順張り、14:14建て→15:44決済(90分)。片道1.5bp。
ゲート: dir / 符号反転p≤0.05 / 11:00 ETタイミングプラセボ / split(2016-20 vs 2021-26) / 2×コスト / DD。
"""
import os, json, time, lzma, struct, hashlib, importlib.util, urllib.request
import numpy as np, pandas as pd

spec = importlib.util.spec_from_file_location("e12", "research/edge12_indices_gold_h1.py")
e12 = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(e12)
except Exception:
    pass  # データ取得部が走っても FOMC リストだけ使う
FOMC = e12.FOMC  # docs/81 §5 固定(定例82回)

LOCAL, OUT = "./research/data", "./research/results/edge21_fomc_minute.json"
COST1, PERM_N, SEED = 0.00015, 2000, 21

def _dst(d):
    """米国夏時間: 3月第2日曜〜11月第1日曜"""
    y = d.year
    mar = pd.Timestamp(y, 3, 1) + pd.Timedelta(days=(6 - pd.Timestamp(y, 3, 1).dayofweek) % 7 + 7)
    nov = pd.Timestamp(y, 11, 1) + pd.Timedelta(days=(6 - pd.Timestamp(y, 11, 1).dayofweek) % 7)
    return mar <= d < nov

def minute_closes(d):
    """発表日dの分足終値(秒offset→close)。取得失敗はNone。"""
    path = f"{LOCAL}/us500m_{d.strftime('%Y%m%d')}.bi5"
    url = (f"https://datafeed.dukascopy.com/datafeed/USA500IDXUSD/{d.year}/"
           f"{d.month-1:02d}/{d.day:02d}/BID_candles_min_1.bi5")
    if not os.path.exists(path):
        for k in range(5):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                raw = urllib.request.urlopen(req, timeout=60).read()
                open(path, "wb").write(raw); break
            except Exception:
                if k == 4: return None
                time.sleep(2 ** k)
        time.sleep(0.2)
    raw = open(path, "rb").read()
    if len(raw) == 0: return None
    b = lzma.decompress(raw)
    out = {}
    for i in range(0, len(b), 24):
        t, o, c, lo, hi, v = struct.unpack(">5If", b[i:i+24])
        out[t] = c / 1000.0
    return out

def leg(closes, et_hour, d):
    """et_hour:00 ETの初動15分符号→+14分建て→+104分決済。(r0, r_trade)"""
    utc_h = et_hour + (4 if _dst(d) else 5)
    base = utc_h * 3600
    def c(off):
        return closes.get(base + off)
    p0, p1, p2 = c(-60), c(14 * 60), c(104 * 60)
    if p0 is None or p1 is None or p2 is None or p0 <= 0: return None
    r0 = p1 / p0 - 1
    if r0 == 0: return None
    s = 1.0 if r0 > 0 else -1.0
    return s * (p2 / p1 - 1)

def perm_p(r, rng):
    r = np.asarray(r, float); real = r.sum(); a = np.abs(r)
    sims = np.array([(a * rng.choice([-1, 1], size=len(a))).sum() for _ in range(PERM_N)])
    return float((sims >= real).mean())

def main():
    os.makedirs(LOCAL, exist_ok=True); os.makedirs("./research/results", exist_ok=True)
    rng = np.random.default_rng(SEED)
    ev, ev_pl, dates, skipped = [], [], [], []
    for ds in FOMC:
        d = pd.Timestamp(ds)
        closes = minute_closes(d)
        if closes is None:
            skipped.append(ds); continue
        r = leg(closes, 14, d)
        if r is None:
            skipped.append(ds); continue
        ev.append(r); dates.append(ds)
        rp = leg(closes, 11, d)
        if rp is not None: ev_pl.append(rp)
    ev = np.array(ev)
    net_ev = ev - 2 * COST1
    net, net2x = float(net_ev.sum()), float((ev - 4 * COST1).sum())
    pval = perm_p(ev, rng)
    pl_sum, pl_p = float(np.sum(ev_pl)), perm_p(ev_pl, rng)
    yrs = np.array([int(s[:4]) for s in dates])
    net_a = float(net_ev[yrs <= 2020].sum()); net_b = float(net_ev[yrs >= 2021].sum())
    eq = np.cumprod(1 + net_ev)
    maxdd = float((eq / np.maximum.accumulate(eq) - 1).min())
    gates = {"G_dir": net > 0, "G_p": pval <= 0.05,
             "G_placebo_time": (pl_p > 0.05) and (pl_sum < 0.5 * float(ev.sum())),
             "G_split": (net_a > 0) and (net_b > 0), "G_cost": net2x > 0,
             "G_dd": maxdd >= -0.20}
    if all(gates.values()): verdict = "STRONG-LEAD" if pval <= 0.01 else "LEAD"
    elif net > 0 and pval <= 0.10: verdict = "参考"
    else: verdict = "REJECT"
    h = hashlib.sha256()
    for f in sorted(os.listdir(LOCAL)):
        if f.startswith("us500m_"): h.update(open(f"{LOCAL}/{f}", "rb").read())
    out = {"doc": "docs/106", "n_events": int(len(ev)), "n_skipped": len(skipped),
           "skipped": skipped, "gross_sum": round(float(ev.sum()), 4),
           "net_sum": round(net, 4), "net_2xcost": round(net2x, 4),
           "perm_p": round(pval, 4), "hit_rate": round(float((ev > 0).mean()), 3),
           "placebo_11et": {"sum": round(pl_sum, 4), "perm_p": round(pl_p, 4), "n": len(ev_pl)},
           "net_2016_2020": round(net_a, 4), "net_2021_2026": round(net_b, 4),
           "maxdd_lev1": round(maxdd, 4), "gates": {k: bool(v) for k, v in gates.items()},
           "verdict": verdict, "input_sha256": h.hexdigest()}
    json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
    print(json.dumps(out, indent=1, ensure_ascii=False))

if __name__ == "__main__":
    main()
