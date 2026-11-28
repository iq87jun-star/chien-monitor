# -*- coding: utf-8 -*-
"""docs/244 Q199(診断・セル 0・2026-11-13 登録「登録して実行」): 自己資金口座で月曜枠(Mon4)を動かした場合の成績。
経路 = Q188 の H1 モデル(SL 3.0×ATR・往復 3 pip)。入金 = 1、月曜の建玉 = L × 有効証拠金(週次複利)、証拠金 = 建玉 ÷ 25、強制ロスカット = 安値ベースで有効証拠金 < 必要証拠金。
構成 C0 Mon4 / C1 200 日線の上にいる通貨 0.5 倍。ガード G0 なし / G1 当日 −0.667% × L で全決済(×1.1)。窓 W1・W2・10 年。MC 20,000 本 × 52 / 260 週。
使い方: cd research && python3 -W ignore queue/q199_self_funded_monday_book.py   出力: results/q199_self_funded_monday_book.csv・_weekly.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
src = open(os.path.join(HERE, "q188_skew_gate_guard_model.py"), encoding="utf-8").read().split('if __name__ == "__main__":')[0]
ns = {"__name__": "q188_head", "__file__": os.path.join(HERE, "q188_skew_gate_guard_model.py")}; exec(compile(src, "q188_head", "exec"), ns)
table, us_dst, G, K = (ns[k] for k in ("table", "us_dst", "G", "K"))
from q196_weak_state_only_near_miss import weak_flags, states_h1, RULES
WFN = RULES[0][1]; PAIRS = ("GBPJPY", "EURJPY", "AUDJPY", "USDJPY"); LEVS = (3, 5, 8, 10, 15, 20); N = 20000; TAX = 0.20315; MARGIN = 1 / 25.0
WINS = (("W1 2021-08〜2026-07", pd.Timestamp("2021-08-01"), pd.Timestamp("2026-07-31")), ("W2 2016-11〜2021-07", pd.Timestamp("2016-11-01"), pd.Timestamp("2021-07-31")), ("10 年(W1 + W2)", pd.Timestamp("2016-11-01"), pd.Timestamp("2026-07-31")))
def unit_paths(tilt):
    """建玉合計 1.0(Mon4 各 0.25)あたりの月曜の経路。戻り値: DataFrame(date, fin, lo_min, 経路 lo / cl)。tilt=True は 200 日線の上の通貨 0.5 倍。"""
    rows = {}
    for s in PAIRS:
        Mt, res = table(s, False); Rk = res[K]; dts = [pd.Timestamp(d) for d in Mt.date.values]; hit, valid = weak_flags(s, states_h1, dts, WFN)
        for i, (d, off, n, stp) in enumerate(zip(dts, Mt.off.values, Mt.nshots.values, np.asarray(Rk["stop"]))):
            f = 1.0 if (not tilt or (hit[i] and valid[i])) else 0.5; w = 0.25 / n * f
            p = rows.setdefault(d, dict(lo=np.zeros(G), cl=np.zeros(G))); p["lo"] += Rk["worst"][i] * w; p["cl"] += Rk["mark"][i] * w
    ds = sorted(rows); return ds, np.array([rows[d]["lo"] for d in ds]), np.array([rows[d]["cl"] for d in ds])
def weekly(lo, cl, L, guard):
    """レバレッジ L の週次損益(有効証拠金比)と、強制ロスカット・ガード発動のフラグ。"""
    lo_min = lo.min(axis=1) * L; fin = cl[:, -1] * L; so_level = -(1.0 - L * MARGIN); pnl = fin.copy(); so = np.zeros(len(fin), bool); gd = np.zeros(len(fin), bool)
    if guard:
        g = 0.00667 * L; gd = lo_min <= -g; pnl = np.where(gd, -g * 1.1, pnl)
    so = (~gd) & (lo_min <= so_level); pnl = np.where(so, so_level, pnl)
    if guard: so = so | (gd & (-0.00667 * L * 1.1 <= so_level))
    return pnl, so, gd
def mc(pnl, so, weeks, seed=199):
    rng = np.random.default_rng(seed); idx = rng.integers(0, len(pnl), (N, weeks)); x = pnl[idx]; eq = np.cumprod(1.0 + x, axis=1); peak = np.maximum.accumulate(np.maximum(eq, 1.0), axis=1); dd = (eq / peak - 1.0).min(axis=1)
    yrs = weeks / 52.0; tot = eq[:, -1] - 1.0; ann = (eq[:, -1]) ** (1 / yrs) - 1.0; hit_so = so[idx].any(axis=1)
    if weeks == 52: after = np.where(tot > 0, tot * (1 - TAX), tot)
    else:
        e2 = eq.reshape(N, -1, 52)[:, :, -1]; prev = np.concatenate([np.ones((N, 1)), e2[:, :-1]], axis=1); yr = e2 / prev - 1.0; after_eq = np.prod(1.0 + np.where(yr > 0, yr * (1 - TAX), yr), axis=1); after = after_eq ** (1 / yrs) - 1.0
    q = lambda a, p: float(np.quantile(a, p)) * 100
    return dict(ret_mean=round(float(ann.mean()) * 100, 1), ret_med=q(ann, .5), ret_p05=q(ann, .05), ret_p95=q(ann, .95), after_tax_med=q(after, .5), p_loss=round(float((tot < 0).mean()) * 100, 1),
                dd_med=q(dd, .5), dd_p95=q(dd, .05), p_dd30=round(float((dd <= -0.30).mean()) * 100, 1), p_dd50=round(float((dd <= -0.50).mean()) * 100, 1), p_stopout=round(float(hit_so.mean()) * 100, 1))
rows = []; wk = []
for cn, tilt in (("C0 Mon4 そのまま", False), ("C1 200 日線の上は 0.5 倍", True)):
    ds, LO, CL = unit_paths(tilt); ds = pd.DatetimeIndex(ds)
    for wn, a, b in WINS:
        m = (ds >= a) & (ds <= b); lo, cl = LO[m], CL[m]; u = cl[:, -1]
        wk.append(dict(config=cn, window=wn, mondays=int(m.sum()), unit_mean_bps=round(float(u.mean()) * 1e4, 2), unit_std_bps=round(float(u.std()) * 1e4, 1), unit_worst_pct=round(float(u.min()) * 100, 2), unit_worst_intraday_pct=round(float(lo.min()) * 100, 2), win_rate=round(float((u > 0).mean()) * 100, 1)))
        for L in LEVS:
            for gn, guard in (("G0 ガードなし", False), ("G1 ガードあり", True)):
                pnl, so, gd = weekly(lo, cl, L, guard); base = dict(config=cn, window=wn, L=L, guard=gn, week_mean_pct=round(float(pnl.mean()) * 100, 3), week_worst_pct=round(float(pnl.min()) * 100, 2), guard_hits=int(gd.sum()), stopouts_hist=int(so.sum()))
                for yrs_, weeks in (("1y", 52), ("5y", 260)):
                    r = mc(pnl, so, weeks); rows.append(dict(base, horizon=yrs_, **{k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items()}))
D = pd.DataFrame(rows); D.to_csv("results/q199_self_funded_monday_book.csv", index=False); W = pd.DataFrame(wk); W.to_csv("results/q199_self_funded_monday_book_weekly.csv", index=False)
pd.set_option("display.width", 330); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 500)
print(W.to_string(index=False)); print()
for hz in ("1y", "5y"):
    print(f"== {hz} =="); print(D[D.horizon == hz][["config", "window", "L", "guard", "week_mean_pct", "week_worst_pct", "guard_hits", "stopouts_hist", "ret_mean", "ret_med", "ret_p05", "ret_p95", "after_tax_med", "p_loss", "dd_med", "dd_p95", "p_dd30", "p_dd50", "p_stopout"]].to_string(index=False)); print()
