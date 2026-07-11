# -*- coding: utf-8 -*-
"""
g3_h1_extension.py — docs/127 §3 の実行(R2: G3 FOMCドリフトの2011-2015延長・docs/86 §3の宿題)。
Dukascopy USA500IDXUSD H1(BID)で、定例FOMC 40回(2011-2015・Fed公式カレンダー確認済み)の
「前営業日H時台ET終値→当日H時台ET終値 LONG」を edge12 逐語ルール+声明時刻適合で検定。
H=13(声明14:00/14:15 ET) / H=11(声明12:30 ET)。コスト=edge12と同一(RT1.0bps+2.5bps/晩)。
PASS = ①net>0 ②順列p<0.10(片側) ③プラセボ(非FOMC火水・年同数)中央値を上回る(docs/127固定)。
出力: results/g3_h1_extension.json → docs/128 へ転記。
"""
import os, json, glob, lzma, struct, hashlib, datetime as dt
import numpy as np, pandas as pd, warnings
from zoneinfo import ZoneInfo
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DUKA = os.path.join(HERE, "data", "duka")
ET = ZoneInfo("America/New_York")

POINT = 0.001
COST_RT_BPS = 1.0
FIN_BPS_NIGHT = 2.5

# (声明日, 声明ET時刻, 使用バーH) — docs/127 §3 固定(Fed公式カレンダーで確認済み)
FOMC = [
    ("2011-01-26", "14:15", 13), ("2011-03-15", "14:15", 13), ("2011-04-27", "12:30", 11),
    ("2011-06-22", "12:30", 11), ("2011-08-09", "14:15", 13), ("2011-09-21", "14:15", 13),
    ("2011-11-02", "12:30", 11), ("2011-12-13", "14:15", 13),
    ("2012-01-25", "12:30", 11), ("2012-03-13", "14:15", 13), ("2012-04-25", "12:30", 11),
    ("2012-06-20", "12:30", 11), ("2012-08-01", "14:15", 13), ("2012-09-13", "12:30", 11),
    ("2012-10-24", "14:15", 13), ("2012-12-12", "12:30", 11),
    ("2013-01-30", "14:00", 13), ("2013-03-20", "14:00", 13), ("2013-05-01", "14:00", 13),
    ("2013-06-19", "14:00", 13), ("2013-07-31", "14:00", 13), ("2013-09-18", "14:00", 13),
    ("2013-10-30", "14:00", 13), ("2013-12-18", "14:00", 13),
    ("2014-01-29", "14:00", 13), ("2014-03-19", "14:00", 13), ("2014-04-30", "14:00", 13),
    ("2014-06-18", "14:00", 13), ("2014-07-30", "14:00", 13), ("2014-09-17", "14:00", 13),
    ("2014-10-29", "14:00", 13), ("2014-12-17", "14:00", 13),
    ("2015-01-28", "14:00", 13), ("2015-03-18", "14:00", 13), ("2015-04-29", "14:00", 13),
    ("2015-06-17", "14:00", 13), ("2015-07-29", "14:00", 13), ("2015-09-17", "14:00", 13),
    ("2015-10-28", "14:00", 13), ("2015-12-16", "14:00", 13),
]


def read_hour_month(instr, year, month):
    p = os.path.join(DUKA, f"{instr}_{year}_{month:02d}_hour.bi5")
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        return []
    d = lzma.decompress(open(p, "rb").read())
    base = dt.datetime(year, month, 1, tzinfo=dt.timezone.utc)
    out = []
    for i in range(0, len(d) - 23, 24):
        off, o, c, l, h, v = struct.unpack(">IIIIIf", d[i:i + 24])
        ts = base + dt.timedelta(seconds=off)
        if o == 0:
            continue
        out.append((ts, o * POINT, h * POINT, l * POINT, c * POINT, v))
    return out


def load_h1():
    rows = []
    for y in range(2010, 2017):
        for m in range(1, 13):
            rows += read_hour_month("USA500IDXUSD", y, m)
    df = pd.DataFrame(rows, columns=["t", "open", "high", "low", "close", "vol"]).sort_values("t")
    df = df.drop_duplicates(subset="t").set_index("t")
    # ET変換(DST自動)
    idx_et = df.index.tz_convert(ET)
    df["et_date"] = [d.date() for d in idx_et]
    df["et_hour"] = [d.hour for d in idx_et]
    return df


def bar_close(df, day, hour):
    """当日ET hour時台バーの終値(そのバーが存在する場合)。"""
    m = df[(df["et_date"] == day) & (df["et_hour"] == hour)]
    return float(m["close"].iloc[-1]) if len(m) else None


def prev_bday_close(df, day, hour, max_back=5):
    for k in range(1, max_back + 1):
        d0 = day - dt.timedelta(days=k)
        if d0.weekday() >= 5:
            continue
        c = bar_close(df, d0, hour)
        if c is not None:
            return d0, c
    return None, None


def event_returns(df, events):
    legs, skipped = [], []
    for ds, ts, H in events:
        day = pd.Timestamp(ds).date()
        c1 = bar_close(df, day, H)
        if c1 is None:
            skipped.append((ds, "no exit bar"))
            continue
        d0, c0 = prev_bday_close(df, day, H)
        if c0 is None:
            skipped.append((ds, "no entry bar"))
            continue
        nights = max(1, (day - d0).days)
        r = c1 / c0 - 1.0 - COST_RT_BPS / 1e4 - nights * FIN_BPS_NIGHT / 1e4
        legs.append(dict(date=ds, entry_day=str(d0), H=H, ret_bps=round(r * 1e4, 1), r=r))
    return legs, skipped


def perm_p_sign(rets, n=4000, seed=7):
    rng = np.random.default_rng(seed)
    actual = float(np.sum(rets))
    a = np.asarray(rets)
    cnt = 0
    for _ in range(n):
        if (a * rng.choice([-1, 1], size=len(a))).sum() >= actual:
            cnt += 1
    return round((cnt + 1) / (n + 1), 5)


def placebo_nonfomc(df, events, reps=500, seed=11):
    """非FOMC火水・年同数のランダム日で同ルール(H=13)。"""
    rng = np.random.default_rng(seed)
    fomc_days = set(pd.Timestamp(ds).date() for ds, _, _ in events)
    all_days = sorted(set(df["et_date"]))
    cands = [d for d in all_days
             if d.weekday() in (1, 2) and d not in fomc_days
             and dt.date(2011, 1, 1) <= d <= dt.date(2015, 12, 31)]
    per_yr = {}
    for ds, _, _ in events:
        y = pd.Timestamp(ds).year
        per_yr[y] = per_yr.get(y, 0) + 1
    nets = []
    for _ in range(reps):
        picks = []
        for y, k in per_yr.items():
            pool = [d for d in cands if d.year == y]
            sel = rng.choice(len(pool), size=min(k, len(pool)), replace=False)
            picks += [pool[i] for i in sel]
        evs = [(str(d), "14:00", 13) for d in sorted(picks)]
        legs, _ = event_returns(df, evs)
        nets.append(sum(l["r"] for l in legs))
    nets = np.asarray(nets)
    return dict(median=round(float(np.median(nets)) * 100, 2),
                p95=round(float(np.quantile(nets, 0.95)) * 100, 2),
                p_ge_actual=None, n_reps=reps), nets


def main():
    R = {"meta": dict(started=dt.datetime.now(dt.timezone.utc).isoformat(), spec="docs/127 §3",
                      cost=f"RT{COST_RT_BPS}bps+{FIN_BPS_NIGHT}bps/night", n_events_target=len(FOMC))}
    df = load_h1()
    R["data"] = dict(bars=int(len(df)), start=str(df.index.min()), end=str(df.index.max()))
    print("H1 bars:", R["data"])

    legs, skipped = event_returns(df, FOMC)
    rets = [l["r"] for l in legs]
    net = round(float(np.sum(rets)) * 100, 2)
    mean_bps = round(float(np.mean(rets)) * 1e4, 1)
    win = round(float(np.mean([r > 0 for r in rets])) * 100, 1)
    p = perm_p_sign(rets)
    plc, nets = placebo_nonfomc(df, FOMC)
    plc["p_ge_actual"] = round(float((nets >= float(np.sum(rets))).mean()), 4)

    # 年別内訳(誠実な記録)
    yearly = {}
    for l in legs:
        y = l["date"][:4]
        yearly[y] = round(yearly.get(y, 0.0) + l["r"] * 100, 2)

    gates = dict(G1_net_pos=net > 0, G2_perm=p < 0.10,
                 G3_placebo=float(np.sum(rets)) * 100 > plc["median"])
    R.update(n_events=len(legs), skipped=skipped, net_pct=net, mean_bps_per_event=mean_bps,
             winrate=win, perm_p=p, placebo=plc, yearly=yearly, legs=legs, gates=gates,
             verdict=("PASS → G3耐久級を『2011年以降の構造』へ更新" if all(gates.values())
                      else "FAIL → G3は現行レジーム級と確定(docs/86 §3保留の解消)"))

    hashes = {}
    for f in sorted(glob.glob(os.path.join(DUKA, "USA500IDXUSD_*_hour.bi5"))):
        hashes[os.path.basename(f)] = hashlib.sha256(open(f, "rb").read()).hexdigest()[:16]
    R["input_sha256"] = hashes

    out = os.path.join(HERE, "results", "g3_h1_extension.json")
    json.dump(R, open(out, "w"), indent=1, ensure_ascii=False, default=str)
    show = {k: R[k] for k in ("n_events", "net_pct", "mean_bps_per_event", "winrate",
                              "perm_p", "placebo", "yearly", "gates", "verdict")}
    print(json.dumps(show, indent=1, ensure_ascii=False))
    print("saved:", out)


if __name__ == "__main__":
    main()
