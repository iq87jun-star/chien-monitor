# -*- coding: utf-8 -*-
"""docs/244 Q283(2026-11-24 登録「登録実行」・セル 12): 週末の BTC の騰落(Q282 と同じ z)を、月曜の指数と夜の指数に当てる。
(A) 月曜の指数(セル 8): トパーズの本口座後の構成(Q280 と同じ: 円クロス 3.0 倍 + 指数 + ロール 4.5 倍)。指数のレグだけ: z ≤ −1 / −2 を見送る・z ≥ +1 / +2 を見送る・z ≤ −1 / −2 を 1.5 倍・z ≥ +1 / +2 を 1.5 倍。
(B) 夜の指数(セル 4): FTMO 50k の本口座後 + いまの夜の指数(VIX 25〜30 = 5 本 各 0.05・30 超 = 各 0.10・Q263b / Q269b と同じ作り)が基準。夜のレグだけ: z ≥ +1 を見送る・z ≥ 0 を見送る・z ≤ −1 を 2 倍・z ≤ 0 を 2 倍。
判定は Q278〜Q282 と同じ(①② の両方で win_ok)。照合: (A) の基準 = Q280 の現行(s10 98.25・p10 +108.47)。
データ: data_live/BTCUSD_rf.csv(Yahoo 日足・git 管理外)。
使い方: cd research && python3 -W ignore queue/q283_btc_weekend_vs_mon_index_and_night_index.py <累積セル数>   出力: results/q283_btc_weekend_index.csv・results/q283_btc_weekend_index_weeks.csv"""
import os, sys
_ARGV = list(sys.argv)
HERE = os.path.dirname(os.path.abspath(__file__)); _s = open(os.path.join(HERE, "q263b_monday_night_index_account_model.py"), encoding="utf-8").read()
n = {"__name__": "q263b_head", "__file__": os.path.join(HERE, "q263b_monday_night_index_account_model.py")}; exec(compile(_s.split("\nrows = []\n")[0], "q263b_head", "exec"), n)
np, pd = n["np"], n["pd"]; n3 = n["n3"]; norm_items, make_fac, build_full, roll_week, sim_funded, PM, table_x, paths_fac, K = (n[k] for k in ("norm_items", "make_fac", "build_full", "roll_week", "sim_funded", "PM", "table_x", "paths_fac", "K")); P0, P1 = n3["P0"], n3["P1"]
VIX = n3["VIX"]; _hot0 = n["hot"]; _C = {}
def _v(d): x = VIX.reindex([pd.Timestamp(d) - pd.Timedelta(days=3)], method="ffill").values[0]; return x if x == x else 0.0
HOTF = {"N": lambda d: _v(d) > 25, "L": lambda d: 25 < _v(d) <= 30, "H": lambda d: _v(d) > 30}
def band_table(sym, band):                                                  # Q269b と同じ
    k = (sym, band)
    if k not in _C: n["hot"] = HOTF[band]; n["_N"].pop(sym, None); _C[k] = n["night_table"](sym); n["_N"].pop(sym, None); n["hot"] = _hot0
    return _C[k]
paths_fac.__globals__["table"] = lambda sym, idx: band_table(sym[:-2], sym[-1]) if sym[-2:] in ("@N", "@L", "@H") else table_x(sym, idx)
IDX = ("NAS100", "US500", "US30", "JP225", "UK100"); NIGHT = [(s + "@L", True, 0.05) for s in IDX] + [(s + "@H", True, 0.10) for s in IDX]
def sig_btc():                                                              # Q282 と同じ
    b = pd.read_csv("data_live/BTCUSD_rf.csv"); b["d"] = pd.to_datetime(b["timestamp"]).dt.normalize(); c = b.drop_duplicates("d", keep="last").set_index("d")["close"].astype(float)
    M = pd.date_range("2016-01-04", P1, freq="7D"); wr = pd.Series({d: (c.get(d - pd.Timedelta(days=1), np.nan) / c.get(d - pd.Timedelta(days=3), np.nan) - 1) for d in M}).dropna()
    return (wr / wr.rolling(52).std().shift(1)).dropna()
def evaluate(items, g, fac, mult, pad, add=None, npaths=20000):             # Q278 の evaluate と同じ式
    T, dates = build_full(items, None, g, fac, mult); call = np.arange(len(dates)); c1 = call[np.array([d >= PM for d in dates])]; c2 = call[np.array([d < PM for d in dates])]; ad = np.zeros(len(dates)) if add is None else add(dates); r = {}
    for tag in ("lo", "cl"):
        m = sim_funded(T[tag], ad, call, 0.10, pad, False, 520, npaths); a = sim_funded(T[tag], ad, c1, 0.10, pad, False, 260, 10000); b = sim_funded(T[tag], ad, c2, 0.10, pad, False, 260, 10000)
        r[tag] = dict(s10=m[520][0], p10=m[520][1], s5=m[260][0], p5=m[260][1], s5a=a[260][0], p5a=a[260][1], s5b=b[260][0], p5b=b[260][1], wk_mean=float(T[tag][0][-1].mean()) * 100, guard=float((T[tag][1][-1] > 0).mean()) * 100)
    out = {k: round(min(r["lo"][k], r["cl"][k]), 2) for k in ("s10", "p10", "s5", "p5", "s5a", "p5a", "s5b", "p5b")}; out.update(wk_mean=round(r["cl"]["wk_mean"], 3), guard=round(max(r["lo"]["guard"], r["cl"]["guard"]), 2)); return out
def win_ok(v, b, sfx): return bool((v["p5" + sfx] >= b["p5" + sfx] + 3.0 and v["s5" + sfx] >= b["s5" + sfx] - 1.0) or (v["s5" + sfx] >= b["s5" + sfx] + 3.0 and v["p5" + sfx] >= b["p5" + sfx]))
def with_flag(fac, keys, flag, mult):
    fc = {k: dict(v) for k, v in fac.items()}
    for k in keys:
        d0 = fc.setdefault(k, {})
        for d in flag: d0[d] = d0.get(d, 1.0) * mult
    return fc
RA = [("z ≤ −1 を見送る", lambda z: z <= -1, 0.0), ("z ≤ −2 を見送る", lambda z: z <= -2, 0.0), ("z ≥ +1 を見送る", lambda z: z >= 1, 0.0), ("z ≥ +2 を見送る", lambda z: z >= 2, 0.0),
      ("z ≤ −1 を 1.5 倍", lambda z: z <= -1, 1.5), ("z ≤ −2 を 1.5 倍", lambda z: z <= -2, 1.5), ("z ≥ +1 を 1.5 倍", lambda z: z >= 1, 1.5), ("z ≥ +2 を 1.5 倍", lambda z: z >= 2, 1.5)]
RB = [("z ≥ +1 を見送る", lambda z: z >= 1, 0.0), ("z ≥ 0 を見送る(下げた週だけ建てる)", lambda z: z >= 0, 0.0), ("z ≤ −1 を 2 倍", lambda z: z <= -1, 2.0), ("z ≤ 0 を 2 倍", lambda z: z <= 0, 2.0)]
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 12; Z = sig_btc(); Z = Z[(Z.index >= P0) & (Z.index <= P1)]; rows = []
    # ---- 参照: 帯ごとの平均(1 本あたり・費用後・bps) ----
    def leg_r(tab): M, res = tab; return pd.Series(res[K]["r"], index=pd.DatetimeIndex(M.date.values))
    mi = pd.concat([leg_r(table_x(s, True)) for s in ("NAS100", "US500")], axis=1).mean(axis=1); ni = pd.concat([leg_r(band_table(s, "N")) for s in IDX], axis=1).mean(axis=1)
    WK = pd.DataFrame({"btc_z": Z}); WK["mon_idx_bps"] = (mi * 1e4).reindex(WK.index); WK["night_idx_bps"] = (ni * 1e4).reindex(WK.index); WK["vix_fri"] = [_v(d) for d in WK.index]; WK["w1"] = WK.index >= PM; WK.to_csv("results/q283_btc_weekend_index_weeks.csv")
    WK["band"] = pd.cut(WK.btc_z, [-99, -2, -1, 0, 1, 2, 99]); tstat = lambda v: float(v.mean() / (v.std() / np.sqrt(len(v)))) if len(v) > 2 and v.std() > 0 else np.nan
    for col in ("mon_idx_bps", "night_idx_bps"):
        x = WK.dropna(subset=[col]); print(f"\n{col} の帯ごと(週の数 {len(x)}・相関 {x.btc_z.corr(x[col]):+.2f}):"); print(x.groupby("band", observed=True)[col].agg(n="size", mean="mean", t=tstat, neg=lambda v: float((v < 0).mean())).round(2).to_string())
    x = WK.dropna(subset=["night_idx_bps"]); print("\n夜の指数: z < 0 / z ≥ 0:"); print(x.groupby(x.btc_z >= 0)["night_idx_bps"].agg(n="size", mean="mean", t=tstat, neg=lambda v: float((v < 0).mean())).round(2).to_string(), flush=True)
    # ---- (A) 月曜の指数・トパーズ 本口座後 ----
    items, cap, g = norm_items("6104739"); fac = make_fac(items, True, 0.5); addf = lambda dates: roll_week(dates, 4.5, g); ikeys = [(s, i) for s, i, w in items if i]; print("\n(A) 指数のレグ:", ikeys, flush=True)
    bA = evaluate(items, g, fac, 3.0, 0.01, add=addf); print("(A) 基準:", bA, flush=True); assert abs(bA["s10"] - 98.25) < 0.01 and abs(bA["p10"] - 108.47) < 0.01, "Q280 の現行と一致しない"
    rows.append(dict(part="A 月曜の指数(トパーズ 本口座後)", rule="現行", n_flag=0, n_w1=0, n_w2=0, mean_flag_bps=np.nan, cells=0, verdict="基準", **bA))
    for nm, fn, mult in RA:
        flag = [d for d, v in Z.items() if fn(v)]; r = evaluate(items, g, with_flag(fac, ikeys, flag, mult), 3.0, 0.01, add=addf); fl = WK[WK.index.isin(flag)].dropna(subset=["mon_idx_bps"]); ok = win_ok(r, bA, "a") and win_ok(r, bA, "b")
        rows.append(dict(part="A 月曜の指数(トパーズ 本口座後)", rule=nm, n_flag=len(fl), n_w1=int(fl.w1.sum()), n_w2=int((~fl.w1).sum()), mean_flag_bps=round(float(fl.mon_idx_bps.mean()), 1), cells=1, verdict="変更候補" if ok else "現行どおり", ok_w1=win_ok(r, bA, "a"), ok_w2=win_ok(r, bA, "b"), **r)); print("done A", nm, r, flush=True)
    # ---- (B) 夜の指数・FTMO 50k 本口座後 ----
    items, cap, g = norm_items("521100397"); fac = make_fac(items, False, 0.5); nkeys = [(s, i) for s, i, w in NIGHT]
    b0 = evaluate(items, g, fac, 3.75, 0.01); print("\n(B) 夜なし(参照):", b0, flush=True); bB = evaluate(list(items) + NIGHT, g, fac, 3.75, 0.01); print("(B) 基準(いまの夜の指数つき):", bB, flush=True)
    rows.append(dict(part="B 夜の指数(FTMO 50k 本口座後)", rule="参照: 夜の指数なし", n_flag=0, n_w1=0, n_w2=0, mean_flag_bps=np.nan, cells=0, verdict="参照", **b0)); rows.append(dict(part="B 夜の指数(FTMO 50k 本口座後)", rule="現行(いまの夜の指数つき)", n_flag=0, n_w1=0, n_w2=0, mean_flag_bps=np.nan, cells=0, verdict="基準", **bB))
    for nm, fn, mult in RB:
        flag = [d for d, v in Z.items() if fn(v)]; r = evaluate(list(items) + NIGHT, g, with_flag(fac, nkeys, flag, mult), 3.75, 0.01); fl = WK[WK.index.isin(flag)].dropna(subset=["night_idx_bps"]); ok = win_ok(r, bB, "a") and win_ok(r, bB, "b")
        rows.append(dict(part="B 夜の指数(FTMO 50k 本口座後)", rule=nm, n_flag=len(fl), n_w1=int(fl.w1.sum()), n_w2=int((~fl.w1).sum()), mean_flag_bps=round(float(fl.night_idx_bps.mean()), 1) if len(fl) else np.nan, cells=1, verdict="変更候補" if ok else "現行どおり", ok_w1=win_ok(r, bB, "a"), ok_w2=win_ok(r, bB, "b"), **r)); print("done B", nm, r, flush=True)
    D = pd.DataFrame(rows); D.to_csv("results/q283_btc_weekend_index.csv", index=False); assert int(D.cells.sum()) == N
    pd.set_option("display.width", 330); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 44)
    print(f"\n== Q283(累積セル {cum} + {N} = {cum + N}・n_flag = 該当してレグが建つ週の数・mean_flag_bps = その週の 1 本あたりの平均) =="); print(D[["part", "rule", "n_flag", "n_w1", "n_w2", "mean_flag_bps", "s10", "p10", "s5a", "p5a", "s5b", "p5b", "guard", "ok_w1", "ok_w2", "verdict"]].to_string(index=False))
    print(f"\n判定: 変更候補 {int((D.verdict == '変更候補').sum())} / {N} 件")
