# -*- coding: utf-8 -*-
"""
edge24_limit_entry.py — v7執行の指値化スタディ【事前登録 docs/149】。
入力: Chien_TickExport_Edge20 v1.30 の ChienRatesM1v2_{PAIR}.csv(M1・bid OHLC+spread_open)
使い方: python3 research/edge24_limit_entry.py <データディレクトリ>
出力: results/edge24_limit_entry.json + 印字(docs/150へ転記)
判定(docs/149 §4): L_mid_15がEURJPY/GBPJPY両方で 平均≥+0.3pip・B1/B2両正・全暦年非負 → 採用。
"""
import os, sys, json, hashlib
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PAIRS = ["EURJPY", "GBPJPY", "USDJPY"]   # USDJPYは参考(間引き済み・判定外)
SLOTS = [4, 6, 8, 10]                    # UTC・月曜
VARIANTS = {"L_mid_15": ("mid", 15), "L_mid_5": ("mid", 5),
            "L_bid_15": ("bid", 15), "L_bid_5": ("bid", 5)}
PRIMARY = "L_mid_15"


def eu_dst_on(ts):
    y = ts.year
    mar = pd.Timestamp(y, 3, 31); mar -= pd.Timedelta(days=(mar.weekday() + 1) % 7)
    oct_ = pd.Timestamp(y, 10, 31); oct_ -= pd.Timedelta(days=(oct_.weekday() + 1) % 7)
    return mar <= ts.normalize() < oct_


def load(path, pip):
    df = pd.read_csv(path)
    df["t"] = pd.to_datetime(df["time_server"], format="%Y.%m.%d %H:%M")
    off = df["t"].apply(lambda x: 3 if eu_dst_on(x) else 2)
    df["t_utc"] = df["t"] - pd.to_timedelta(off, unit="h")
    df["spread"] = df["spread_pips_open"] * pip
    return df.sort_values("t_utc").reset_index(drop=True)


def simulate(df, pip):
    """各月曜スロット: ベースライン成行 vs 指値変種。戻り: 変種→ショット別節約pipsのSeries"""
    mon = df[df["t_utc"].dt.weekday == 0]
    out = {v: [] for v in VARIANTS}
    fills = {v: 0 for v in VARIANTS}; total = 0
    idx_by_t = df.set_index("t_utc")
    for (d, h), g in mon.groupby([mon["t_utc"].dt.date, mon["t_utc"].dt.hour]):
        if h not in SLOTS: continue
        g = g.sort_values("t_utc")
        b0 = g.iloc[0]
        t0 = b0["t_utc"]
        base_ask = b0["open_bid"] + b0["spread"]
        # スロット後W分のバー(同日同時間帯のみ)
        win = df[(df["t_utc"] > t0) & (df["t_utc"] <= t0 + pd.Timedelta(minutes=16))]
        total += 1
        for v, (kind, W) in VARIANTS.items():
            limit = b0["open_bid"] + (b0["spread"] / 2 if kind == "mid" else 0.0)
            w = win[win["t_utc"] <= t0 + pd.Timedelta(minutes=W)]
            filled = False
            # 当該バー自身のlowでも判定(バー内で置いた直後に触れる場合・保守的にspread_open使用)
            if b0["low_bid"] + b0["spread"] <= limit:
                filled = True
            else:
                for _, r in w.iterrows():
                    if r["low_bid"] + r["spread"] <= limit:
                        filled = True; break
            if filled:
                entry = limit; fills[v] += 1
            else:
                nxt = df[df["t_utc"] > t0 + pd.Timedelta(minutes=W)]
                if len(nxt) == 0: continue
                r = nxt.iloc[0]
                if r["t_utc"] - t0 > pd.Timedelta(minutes=W + 30): continue  # データ欠落はスキップ
                entry = r["open_bid"] + r["spread"]
            out[v].append((t0, (base_ask - entry) / pip))
    res = {}
    for v in VARIANTS:
        s = pd.Series({t: x for t, x in out[v]}).sort_index()
        res[v] = dict(series=s, fill_rate=round(fills[v] / max(total, 1) * 100, 1))
    return res, total


def main():
    ddir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "data", "tick_edge24")
    out = {"meta": dict(prereg="docs/149", slots=SLOTS, variants=list(VARIANTS), primary=PRIMARY,
                        inputs={})}
    verdict_parts = []
    for p in PAIRS:
        path = os.path.join(ddir, f"ChienRatesM1v2_{p}.csv")
        if not os.path.exists(path):
            print(f"⚠ {p}: {path} なし→スキップ"); continue
        out["meta"]["inputs"][p] = hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
        pip = 0.01
        df = load(path, pip)
        res, total = simulate(df, pip)
        rec = {"n_shots": total, "span": [str(df['t_utc'].min())[:10], str(df['t_utc'].max())[:10]]}
        for v, r in res.items():
            s = r["series"]
            half = len(s) // 2
            years = {int(y): round(float(s[s.index.year == y].mean()), 3)
                     for y in sorted(set(s.index.year))}
            rec[v] = dict(mean_pips=round(float(s.mean()), 3), fill_pct=r["fill_rate"],
                          B1=round(float(s.iloc[:half].mean()), 3),
                          B2=round(float(s.iloc[half:].mean()), 3), yearly=years)
        out[p] = rec
        pr = rec[PRIMARY]
        ok = (pr["mean_pips"] >= 0.3 and pr["B1"] > 0 and pr["B2"] > 0
              and all(v >= 0 for v in pr["yearly"].values()))
        if p in ("EURJPY", "GBPJPY"):
            verdict_parts.append(ok)
        print(f"### {p} ({total}ショット {rec['span']})")
        for v in VARIANTS:
            r = rec[v]
            print(f"  {v}: 平均{r['mean_pips']:+.3f}pip 約定率{r['fill_pct']}% "
                  f"B1 {r['B1']:+.3f}/B2 {r['B2']:+.3f} 年別{r['yearly']}")
    adopt = len(verdict_parts) == 2 and all(verdict_parts)
    out["verdict"] = ("採用(EA v1.32 指値W分→成行・デモへ)" if adopt
                      else "REJECT/LEAD(docs/149 §4の下位判定を適用・現行成行維持)")
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "edge24_limit_entry.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("\n判定:", out["verdict"])
    print("保存: research/results/edge24_limit_entry.json")


if __name__ == "__main__":
    main()
