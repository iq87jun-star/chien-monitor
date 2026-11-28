# -*- coding: utf-8 -*-
"""docs/398 Q109(診断・セル 0): Hold(UK100 / WTI / XAUUSD / GER40)の実口座の建て直しと、研究系列 hold_cell(終値→終値・月初 5 bps・スワップなし)の前提を突き合わせる。
入力: research/ops_inbox/<口座>/positions.csv・open_positions.csv(コメント RFHold_・git 管理外)、参照価格 results/q109_ref_daily_yahoo.csv(Yahoo 日足 2026-08〜11・hold_cell と同じ出所)。
出力: results/q109_hold_reentry_cost.csv(取引ごと)・標準出力に (a) 建て直しの直接コスト、(b) フラット期間の価格変化(モデルとの乖離)、(c) スワップ・手数料の月率、(d) 保有期間の実 vs モデル。
使い方: cd research && python3 -W ignore queue/q109_hold_reentry_cost.py"""
import os, sys, glob
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SYM = {"UK100": "UK100", "UK100p": "UK100", "USOUSD": "WTI", "USOILp": "WTI", "GER40.cash": "GER40", "XAUUSD": "XAUUSD"}
CCY = {"UK100": 1.35, "UK100p": 1.35, "GER40.cash": 1.17}; FXJ = 158.0; JPY_ACCTS = {"6104739", "6104736", "6071612"}
SNAP = pd.Timestamp("2026-11-03 22:00:00")   # 建玉中の評価時刻(status.json 生成時刻・サーバ時刻 ≈ UTC+2)
def rd(p):
    try: return pd.read_csv(p, encoding="utf-8-sig")
    except Exception: return pd.DataFrame()
def trades():
    rows = []
    for d in sorted(glob.glob(os.path.join(ROOT, "ops_inbox", "*"))):
        a = os.path.basename(d)
        if not a.isdigit(): continue
        p = rd(os.path.join(d, "positions.csv")); p = p[p.comment.astype(str).str.startswith("RFHold")] if len(p) else p
        for _, r in p.iterrows(): rows.append(dict(acct=a, sym=r.symbol, ot=r.open_time, ct=r.close_time, vol=r.volume, op=r.open_price, cp=r.close_price, comm=r.commission, swap=r.swap, pl=r.profit, open=False))
        o = rd(os.path.join(d, "open_positions.csv")); o = o[o.comment.astype(str).str.startswith("RFHold")] if len(o) else o
        for _, r in o.iterrows(): rows.append(dict(acct=a, sym=r.symbol, ot=r.open_time, ct=SNAP.strftime("%Y.%m.%d %H:%M:%S"), vol=r.volume, op=r.open_price, cp=r.price_current, comm=0.0, swap=r.swap, pl=r.profit, open=True))
    H = pd.DataFrame(rows); H["ot"] = pd.to_datetime(H.ot, format="%Y.%m.%d %H:%M:%S"); H["ct"] = pd.to_datetime(H.ct, format="%Y.%m.%d %H:%M:%S")
    H["days"] = (H.ct - H.ot).dt.total_seconds() / 86400
    # 契約サイズは損益から逆算(建玉中は profit が未確定なので同銘柄の決済済みから引く・無ければ標準値)
    std = {"XAUUSD": 100, "UK100": 10, "USOUSD": 100, "GER40.cash": 1, "UK100p": 1, "USOILp": 1000}
    H["cs"] = [std[s] for s in H.sym]
    H["notional"] = H.apply(lambda r: r.vol * r.cs * r.op * CCY.get(r.sym, 1.0) * (FXJ if r.acct in JPY_ACCTS else 1.0), axis=1)
    H["ref"] = [SYM[s] for s in H.sym]
    H["px_bps"] = (H.cp / H.op - 1) * 1e4; H["pl_bps"] = H.pl / H.notional * 1e4
    H["swap_bps_m"] = H.swap / H.notional * 1e4 / H.days.clip(lower=0.5) * 30.4; H["comm_bps"] = H.comm / H.notional * 1e4
    return H.sort_values(["acct", "sym", "ot"]).reset_index(drop=True)
def ref_daily():
    d = pd.read_csv(os.path.join(ROOT, "results", "q109_ref_daily_yahoo.csv"), parse_dates=["t"]); d["date"] = (d.t + pd.Timedelta(hours=2)).dt.floor("D"); return d
def model_ret(ref, sym, t0, t1):
    """hold_cell と同じ終値→終値(t0 の日の終値から t1 の日の終値)。サーバ時刻(UTC+2/+3)→ 日付。月初 5 bps を含む。"""
    d = ref[ref.sym == sym].set_index("date").close; d0 = t0.floor("D"); d1 = t1.floor("D")
    s = d[(d.index > d0) & (d.index <= d1)]; prev = d[d.index <= d0]
    if len(s) == 0 or len(prev) == 0: return np.nan
    r = s.iloc[-1] / prev.iloc[-1] - 1; firsts = pd.Series(s.index, index=s.index).groupby(pd.PeriodIndex(s.index, freq="M")).min()
    return (r - 5e-4 * len(firsts)) * 1e4
def main():
    H = trades(); ref = ref_daily()
    H["model_bps"] = [model_ret(ref, r.ref, r.ot, r.ct) for r in H.itertuples()]; H["gap_bps"] = H.px_bps - H.model_bps
    pd.set_option("display.width", 260); pd.set_option("display.max_columns", 30)
    print("## (d) 取引ごと: 実(建値→決済値)と hold_cell(終値→終値・月初 5 bps)の差(bps・符号は実−モデル)")
    print(H[["acct", "sym", "ot", "ct", "vol", "op", "cp", "days", "px_bps", "model_bps", "gap_bps", "swap_bps_m", "comm_bps", "open"]].round(1).to_string(index=False))
    # (a) 建て直しの直接コスト: 同一口座・同一銘柄で決済 → 次の建てまでの間隔と価格差
    print("\n## (a)(b) 建て直し: 決済 → 次の建て(同口座・同銘柄)。gap_min = 空白時間(分)、px_gap_bps = (次の建値 / 決済値 − 1)。空白が短いものは純粋な執行コスト、長いものは露出の欠落(モデルは保有継続)")
    rows = []
    for (a, s), g in H.groupby(["acct", "sym"]):
        g = g.sort_values("ot").reset_index(drop=True)
        for i in range(len(g) - 1):
            c = g.loc[i]; n = g.loc[i + 1]; mins = (n.ot - c.ct).total_seconds() / 60
            mdl = model_ret(ref, c.ref, c.ct, n.ot) if mins > 24 * 60 else np.nan
            rows.append(dict(acct=a, sym=s, close_t=c.ct, reopen_t=n.ot, gap_min=round(mins, 1), close_px=c.cp, reopen_px=n.op, px_gap_bps=round((n.op / c.cp - 1) * 1e4, 1), model_gap_bps=(round(mdl, 1) if mdl == mdl else None), kind=("執行" if mins <= 60 else "露出欠落")))
    G = pd.DataFrame(rows); print(G.to_string(index=False))
    print("\n## (c) スワップ・手数料(bps / 月・想定元本比)")
    C = H.groupby(["acct", "ref"]).apply(lambda g: pd.Series(dict(days=g.days.sum(), swap_bps_m=(g.swap.sum() / (g.notional * g.days).sum() * 30.4 * 1e4) if (g.notional * g.days).sum() > 0 else 0, comm_bps_per_trade=g.comm_bps[~g.open].mean() if (~g.open).any() else 0, n=len(g)))).reset_index()
    print(C.round(1).to_string(index=False))
    H.to_csv(os.path.join(ROOT, "results", "q109_hold_reentry_cost.csv"), index=False); G.to_csv(os.path.join(ROOT, "results", "q109_hold_rebuilds.csv"), index=False); C.to_csv(os.path.join(ROOT, "results", "q109_hold_swap_comm.csv"), index=False)
    print("saved results/q109_hold_reentry_cost.csv / q109_hold_rebuilds.csv / q109_hold_swap_comm.csv")
if __name__ == "__main__": main()
