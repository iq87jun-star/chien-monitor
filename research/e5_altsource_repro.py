# -*- coding: utf-8 -*-
"""
e5_altsource_repro.py — docs/127 §2 の実行(R1: E5の別ソース再現・docs/86 §4の残存昇格手段)。
Dukascopy BID日足(XAUUSD/USA500IDXUSD/USATECHIDXUSD/DEUIDXEUR)の月末終値でE5逐語ロジックを再実行し、
同一窓のYahoo実行と比較する。PASS = ①Duka窓 net>0 ②月次戦略リターン相関 ρ≥0.6(docs/127固定)。
出力: results/e5_altsource_repro.json(入力SHA-256付き) → docs/128 へ転記。
"""
import os, sys, json, glob, lzma, struct, hashlib, datetime as dt
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DUKA = os.path.join(DATA, "duka")
sys.path.insert(0, HERE)

COST_M = 5e-4
CORR_MIN = 0.6
INSTR = {"XAUUSD": ("XAUUSD", 0.001), "US500": ("USA500IDXUSD", 0.001),
         "NAS100": ("USATECHIDXUSD", 0.001), "GER40": ("DEUIDXEUR", 0.001)}


def read_day_year(instr, year, point):
    p = os.path.join(DUKA, f"{instr}_{year}_day.bi5")
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        return []
    d = lzma.decompress(open(p, "rb").read())
    out = []
    base = dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc)
    for i in range(0, len(d) - 23, 24):
        off, o, c, l, h, v = struct.unpack(">IIIIIf", d[i:i + 24])
        ts = base + dt.timedelta(seconds=off)
        if v <= 0 or o == 0:
            continue
        out.append((ts.replace(tzinfo=None), o * point, h * point, l * point, c * point))
    return out


def duka_daily(name):
    instr, point = INSTR[name]
    rows = []
    for y in range(2010, 2027):
        rows += read_day_year(instr, y, point)
    df = pd.DataFrame(rows, columns=["t", "open", "high", "low", "close"]).sort_values("t")
    df = df.set_index("t")
    df = df[df.index.dayofweek <= 4]
    return df


def yahoo_daily(name):
    df = pd.read_csv(os.path.join(DATA, f"{name}_d.csv"))
    df["t"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t")
    df["trade_date"] = (df["t"] + pd.Timedelta(hours=2)).dt.floor("D")
    df = df.groupby("trade_date", as_index=True).last()
    return df[df.index.dayofweek <= 4]


def e5_monthly_from_closes(closes: dict):
    """E5逐語(parallel_vs_existing_compare.e5_monthly と同一): 1/3/6/12符号合議・等WT・5bp/月。"""
    px = pd.DataFrame({n: s.resample("ME").last() for n, s in closes.items()}).dropna()
    ret = px.pct_change()
    sig = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for lb in (1, 3, 6, 12):
        sig = sig.add(np.sign(px.pct_change(lb)), fill_value=0)
    pos = np.sign(sig).shift(1)
    out = ((pos * ret).mean(axis=1) - COST_M).dropna()
    out.index = out.index.to_period("M")
    return out, px


def main():
    R = {"meta": dict(started=dt.datetime.now(dt.timezone.utc).isoformat(),
                      spec="docs/127 §2", pass_rule=f"duka net>0 AND corr>={CORR_MIN}")}
    # Dukascopy側
    dk_closes, sanity = {}, {}
    for name in INSTR:
        df = duka_daily(name)
        dk_closes[name] = df["close"]
        sanity[name] = dict(rows=int(len(df)),
                            start=str(df.index.min().date()) if len(df) else None,
                            end=str(df.index.max().date()) if len(df) else None)
    # 共通窓の確定(4資産揃う最初の月〜)
    e5_dk, px_dk = e5_monthly_from_closes(dk_closes)
    # Yahoo側を同一窓で
    yh_closes = {n: yahoo_daily(n)["close"] for n in INSTR}
    e5_yh_full, px_yh = e5_monthly_from_closes(yh_closes)
    common = e5_dk.index.intersection(e5_yh_full.index)
    # TSMOMは12ヶ月ルックバック確定後から有効 → 共通有効月のみ
    e5_dk_c = e5_dk.reindex(common).dropna()
    e5_yh_c = e5_yh_full.reindex(e5_dk_c.index).dropna()
    e5_dk_c = e5_dk_c.reindex(e5_yh_c.index)

    # 価格レベルのサニティ(月次リターン相関・資産別)
    px_corr = {}
    for n in INSTR:
        a = px_dk[n].pct_change().rename("d")
        b = px_yh[n].resample("ME").last().pct_change().rename("y")
        a.index = a.index.to_period("M"); b.index = b.index.to_period("M")
        j = pd.concat([a, b], axis=1).dropna()
        px_corr[n] = round(float(j["d"].corr(j["y"])), 4) if len(j) > 12 else None

    net_dk = round(float(e5_dk_c.sum()) * 100, 2)
    net_yh = round(float(e5_yh_c.sum()) * 100, 2)
    corr = round(float(e5_dk_c.corr(e5_yh_c)), 4)
    sign_agree = round(float((np.sign(e5_dk_c) == np.sign(e5_yh_c)).mean()) * 100, 1)

    gates = dict(G1_net_pos=net_dk > 0, G2_corr=corr >= CORR_MIN)
    R.update(sanity=sanity, price_monthly_corr=px_corr,
             window=[str(e5_dk_c.index.min()), str(e5_dk_c.index.max())],
             n_months=int(len(e5_dk_c)),
             e5_duka_net=net_dk, e5_yahoo_net_samewindow=net_yh,
             strategy_monthly_corr=corr, monthly_sign_agree_pct=sign_agree,
             gates=gates,
             verdict="PASS(別ソース再現✔)" if all(gates.values()) else "FAIL(docs/128で級降格を提起)")

    hashes = {}
    for f in sorted(glob.glob(os.path.join(DUKA, "*_day.bi5"))):
        hashes[os.path.basename(f)] = hashlib.sha256(open(f, "rb").read()).hexdigest()[:16]
    R["input_sha256"] = hashes

    out = os.path.join(HERE, "results", "e5_altsource_repro.json")
    json.dump(R, open(out, "w"), indent=1, ensure_ascii=False, default=str)
    print(json.dumps({k: R[k] for k in ("sanity", "price_monthly_corr", "window", "n_months",
                                        "e5_duka_net", "e5_yahoo_net_samewindow",
                                        "strategy_monthly_corr", "monthly_sign_agree_pct",
                                        "verdict")}, indent=1, ensure_ascii=False))
    print("saved:", out)


if __name__ == "__main__":
    main()
