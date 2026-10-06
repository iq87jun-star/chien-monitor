# -*- coding: utf-8 -*-
"""docs/322 Q84: 実口座で劣化が大きい Mon ショットの除外(改良系・4 セル)。
問い: Q83(docs/323)の実口座記録で執行成分(建て滑り + 手仕舞い滑り + 実コスト − モデルコスト)が最も薄いショットを外した
「Mon3」が、研究系列で配備中の「Mon4(4/6/8/10 UTC 均等・24h)」を改良系基準(IS・OOS 両方で Sharpe 改善 かつ 最悪月が悪化しない)で上回るか。
セル = 除外ショット {4, 6, 8, 10} の 4 本(事前指定の主セルは Q83 で特定した 1 本、残り 3 本は参照)。
対象 = 配備中の Mon 銘柄(円クロス 7 本 + ETHUSD)。等ウェイト合成(ショット平均 → 銘柄平均 = 総エクスポージャ一定)。
H1 Dukascopy(data_dukascopy + forward/*_data の 2026-09 月次)・始値→24h 後の始値・コスト FX 往復 2pip / ETHUSD 15 bps(docs/244 §1・Q7 と同じ)。
窓: 前窓 2016-01〜2021-09 / IS 2021-10〜2024-12 / OOS 2025-01〜末尾(Q7 と同じ)。
自己検証: 同一セルの LONG + SHORT = −2×コスト(docs/249)。research/ で実行。"""
import os, glob, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT)
FX = ["GBPJPY", "EURJPY", "AUDJPY", "USDJPY", "CADJPY", "CHFJPY", "NZDJPY"]; SYMS = FX + ["ETHUSD"]; SHOTS = (4, 6, 8, 10); HOLD = 24
COST = {s: None for s in FX}; COST["ETHUSD"] = 15e-4
PRE0, IS0, IS1, OOS0 = pd.Timestamp("2016-01-01"), pd.Timestamp("2021-10-01"), pd.Timestamp("2024-12-31 23:00"), pd.Timestamp("2025-01-01")
END = pd.Timestamp("2026-12-31")

def load(sym):
    df = pd.read_csv(f"data_dukascopy/{sym}_hour.csv.gz"); df["t"] = pd.to_datetime(df["timestamp"]); df = df.set_index("t").sort_index()
    extra = sorted(glob.glob(f"forward/q20_monitor_data/{sym}_*_bid.csv") + glob.glob(f"forward/exec_gap_data/{sym}_*_bid.csv"))
    for f in extra:
        e = pd.read_csv(f); e["t"] = pd.to_datetime(e["t"]); e = e.set_index("t").sort_index(); e = e[e.index > df.index.max()]
        if len(e): df = pd.concat([df, e[["open", "high", "low", "close", "volume"]]])
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df[((df.high > df.low) | (df.volume > 0)) & (df.index >= PRE0)]

def cell(df, h0, cost, short=False):
    o = df["open"]; d = df[(df.index.dayofweek == 0) & (df.index.hour == h0)]
    oe = o.reindex(d.index + pd.Timedelta(hours=HOLD)); ok = ~oe.isna().values
    r = oe.values[ok] / d["open"].values[ok] - 1.0; c = (2 * 0.01 / d["open"].values[ok]) if cost is None else cost
    return pd.Series((-r if short else r) - c, index=d.index[ok].normalize())   # 週(月曜日付)で揃える

def monthly(x): return x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
def st(r, a, b):
    x = r[(r.index >= a) & (r.index <= b)].dropna()
    if len(x) < 5: return dict(n=0)
    m = monthly(x)
    return dict(n=len(m), plus=int((m > 0).sum()), mean_bps=round(float(x.mean()) * 1e4, 2), sharpe=round(float(x.mean() / x.std() * np.sqrt(52)), 3) if x.std() > 0 else np.nan,
                worst_m=round(float(m.min()) * 1e4, 1), worst_m_date=str(m.idxmin()))

# ---- 1. 実口座の特定(docs/323・exec_gap_trades.csv・Mon の記録は 14166201 ETHUSD のみ) ----
tr = pd.read_csv("results/exec_gap_trades.csv"); tr = tr[tr.fam == "Mon"].copy()
tr["exec_bps"] = tr.slip_in_bps + tr.slip_out_bps + tr.cost_diff_bps
ident = tr.groupby("shot").agg(n=("exec_bps", "size"), exec_bps=("exec_bps", "mean"), slip_in=("slip_in_bps", "mean"), slip_out=("slip_out_bps", "mean"),
                               cost_diff=("cost_diff_bps", "mean"), real_net=("real_net_bps", "mean"), paper_model=("paper_model_bps", "mean"), gap=("gap_bps", "mean")).round(2)
ident.index = ident.index.astype(int); ident["exec_se"] = (tr.groupby("shot").exec_bps.std() / np.sqrt(tr.groupby("shot").exec_bps.size())).round(2).values
PRIMARY = int(ident.exec_bps.idxmin())
print("== 実口座(14166201 Mon ETHUSD・2026-08/09)ショット別の執行成分 bps/取引"); print(ident.to_string()); print(f"主セル(執行成分が最小のショット)= {PRIMARY} UTC\n")

# ---- 2. 研究系列 ----
shots = {}   # (sym, h0) -> weekly series
for sym in SYMS:
    df = load(sym); c = COST[sym]
    l, s = cell(df, 4, c), cell(df, 4, c, True); z = (l + s).dropna(); assert float(z.max()) <= 1e-12, f"[COST SIGN] {sym}"   # docs/249 自己検証
    for h0 in SHOTS: shots[(sym, h0)] = cell(df, h0, c)
    print(f"{sym}: {df.index.min().date()}〜{df.index.max().date()}  週数 {len(shots[(sym, 4)])}")

def composite(syms, use_shots):
    per_sym = [pd.concat([shots[(s, h)] for h in use_shots], axis=1).mean(axis=1) for s in syms]
    return pd.concat(per_sym, axis=1).mean(axis=1).dropna()

rows = []
for grp, syms in [("Mon8(JPY7+ETH)", SYMS), ("JPY7", FX), ("ETHUSD", ["ETHUSD"])] + [(s, [s]) for s in FX]:
    base = composite(syms, SHOTS); bi, bo, bp = st(base, IS0, IS1), st(base, OOS0, END), st(base, PRE0, IS0 - pd.Timedelta(hours=1))
    rows.append(dict(group=grp, cell="Mon4(base)", excl=None, pre_mean=bp.get("mean_bps"), is_n=bi.get("n"), is_plus=bi.get("plus"), is_mean=bi.get("mean_bps"), is_sharpe=bi.get("sharpe"), is_worst=bi.get("worst_m"),
                     oos_n=bo.get("n"), oos_plus=bo.get("plus"), oos_mean=bo.get("mean_bps"), oos_sharpe=bo.get("sharpe"), oos_worst=bo.get("worst_m"), d_is_sharpe=0.0, d_oos_sharpe=0.0, improve=False, primary=False))
    for ex in SHOTS:
        use = tuple(h for h in SHOTS if h != ex); r = composite(syms, use); ri, ro, rp = st(r, IS0, IS1), st(r, OOS0, END), st(r, PRE0, IS0 - pd.Timedelta(hours=1))
        imp = (ri["sharpe"] > bi["sharpe"]) and (ro["sharpe"] > bo["sharpe"]) and (ri["worst_m"] >= bi["worst_m"]) and (ro["worst_m"] >= bo["worst_m"])
        rows.append(dict(group=grp, cell=f"Mon3 ex{ex}", excl=ex, pre_mean=rp.get("mean_bps"), is_n=ri.get("n"), is_plus=ri.get("plus"), is_mean=ri.get("mean_bps"), is_sharpe=ri.get("sharpe"), is_worst=ri.get("worst_m"),
                         oos_n=ro.get("n"), oos_plus=ro.get("plus"), oos_mean=ro.get("mean_bps"), oos_sharpe=ro.get("sharpe"), oos_worst=ro.get("worst_m"),
                         d_is_sharpe=round(ri["sharpe"] - bi["sharpe"], 3), d_oos_sharpe=round(ro["sharpe"] - bo["sharpe"], 3), improve=bool(imp), primary=(ex == PRIMARY and grp == "Mon8(JPY7+ETH)")))
R = pd.DataFrame(rows); R.to_csv("results/q84_mon_shot_exclude_real.csv", index=False); pd.set_option("display.width", 250)
print("\n== 合成(配備 Mon 銘柄・等ウェイト・総エクスポージャ一定)"); print(R[R.group == "Mon8(JPY7+ETH)"].to_string(index=False))
print("\n== JPY7 / ETHUSD"); print(R[R.group.isin(["JPY7", "ETHUSD"])].to_string(index=False))
print("\n== 銘柄別(改良系を満たすセル)"); print(R[(R.improve) & (~R.group.isin(["Mon8(JPY7+ETH)", "JPY7", "ETHUSD"]))].to_string(index=False))
# 参考: ショット単体(ETHUSD)— 実口座特定の裏付け
e = pd.DataFrame([dict(shot=h, **{f"is_{k}": v for k, v in st(shots[("ETHUSD", h)], IS0, IS1).items()}, **{f"oos_{k}": v for k, v in st(shots[("ETHUSD", h)], OOS0, END).items()}) for h in SHOTS])
print("\n== 参考: ETHUSD ショット単体"); print(e[["shot", "is_n", "is_plus", "is_mean_bps", "is_sharpe", "is_worst_m", "oos_n", "oos_plus", "oos_mean_bps", "oos_sharpe", "oos_worst_m"]].to_string(index=False))
ident.to_csv("results/q84_real_shot_ident.csv")
