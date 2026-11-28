# -*- coding: utf-8 -*-
"""[Q292 は下の説明を参照。以下は Q286 と同じ前半]
docs/244 Q286(2026-11-25 登録・ユーザー「各口座最適ガードを考案してください」・セル 63): 口座ごとのガードの最適な組み合わせ(Fintokei 3 口座・FTMO 50k 2 口座)。
組み合わせ(8): SKEW の見送り × 200 日線の上 0.5 倍 × 損失枠の縮小(下限 0.5)。場面(9): 5 口座のいまの段階と次の段階。「いま」の開始残高は 2026-11-25 06:22 JST。
倍率・決済の型・日次ガードは Q263b の場面のまま。夜の指数は配備・予定どおり(FTMO 7058 いま・パール いま・FTMO 50k 次・トパーズ 次・パール 次)。
判定: 各セル = Q233 の ev_ok(その場面のいまの組み合わせに対して)。その場面の最適 = ev_ok の中で(① 到達 − 失格)+(② 到達 − 失格)が最大。無ければ「いまの組み合わせが最適」。
使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q286_guard_combo_per_account_eval.py <累積セル数>   出力: results/q286_guard_combo_eval.csv"""
import os, sys, itertools
_ARGV = list(sys.argv)
HERE = os.path.dirname(os.path.abspath(__file__)); _s = open(os.path.join(HERE, "q263b_monday_night_index_account_model.py"), encoding="utf-8").read()
n = {"__name__": "q263b_head", "__file__": os.path.join(HERE, "q263b_monday_night_index_account_model.py")}; exec(compile(_s.split("\nrows = []\n")[0], "q263b_head", "exec"), n)
np, pd = n["np"], n["pd"]; n3 = n["n3"]; norm_items, make_fac, build_full, sim_eval, MODE, PM, table_x, paths_fac, ev_ok = (n[k] for k in ("norm_items", "make_fac", "build_full", "sim_eval", "MODE", "PM", "table_x", "paths_fac", "ev_ok")); VIX = n3["VIX"]; _hot0 = n["hot"]; _C = {}
def _v(d): x = VIX.reindex([pd.Timestamp(d) - pd.Timedelta(days=3)], method="ffill").values[0]; return x if x == x else 0.0
HOTF = {"L": lambda d: 25 < _v(d) <= 30, "H": lambda d: _v(d) > 30}
def band_table(sym, band):                                                  # Q269b と同じ
    k = (sym, band)
    if k not in _C: n["hot"] = HOTF[band]; n["_N"].pop(sym, None); _C[k] = n["night_table"](sym); n["_N"].pop(sym, None); n["hot"] = _hot0
    return _C[k]
paths_fac.__globals__["table"] = lambda sym, idx: band_table(sym[:-2], sym[-1]) if sym[-2:] in ("@L", "@H") else table_x(sym, idx)
IDX = ("NAS100", "US500", "US30", "JP225", "UK100"); NIGHT = [(s + "@L", True, 0.05) for s in IDX] + [(s + "@H", True, 0.10) for s in IDX]
# ---------------- Q292 ----------------
# docs/244 Q292(2026-11-26 登録「登録して実行」・診断・セル 0): パールと同じ作りを自己資金(基準 1000 万円・固定)で動かす場合の「負けに耐える分」。
# 作り = パールのいまの配備(月曜 GBPJPY・AUDJPY 5.57 倍・E1・SKEW + 200 日線・ガード 2.4%・月 2 回発動で月末まで月曜を休む)。失格線なし・出金なし・数量は基準残高に固定。
# 形: {月曜のみ / + ロール 4.5 倍 / + ロール + 夜の指数} × {縮小なし / 縮小あり(数量 × clamp(1 + 累計 ÷ 10%, 0.5, 1))}。
# (1) 実際の順番での最大の落ち込み。(2) 週を並べ替えた 10 年(520 週・20,000 本・乱数 187)の最大の落ち込みの分布。全期間と前半(〜2021-07)。安値判定と終値判定の悪い方。
# 使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q292_pearl_form_own_capital_reserve.py   出力: results/q292_own_capital_reserve.csv
roll_week = n["roll_week"]; LV = n3["LV"]; BASE = 1000.0; MDD = 0.10; G = 0.024; MM = 5.57; RW = 4.5; TH = (0.10, 0.15, 0.20, 0.30)
def lvl(c, shrink): return np.abs(LV[None, :] - (np.clip(1.0 + c / MDD, 0.5, 1.0) if shrink else np.ones_like(c))[:, None]).argmin(axis=1)
def hist(T, add, dates, shrink):
    pnl, fired = T[0], T[1]; c = 0.0; hwm = 0.0; mdd = 0.0; fires = 0; mk = None; ws = []; uw = 0; uwmax = 0; trough = None
    for i, d in enumerate(dates):
        if (d.year, d.month) != mk: mk = (d.year, d.month); fires = 0
        gi = int(lvl(np.array([c]), shrink)[0]); act = fires < 2; x = (float(pnl[gi, i]) if act else 0.0) + float(add[i]); fires += int(fired[gi, i]) if act else 0; c += x; ws.append(x); hwm = max(hwm, c); uw = uw + 1 if c < hwm - 1e-12 else 0; uwmax = max(uwmax, uw)
        if hwm - c > mdd: mdd = hwm - c; trough = d
    w = pd.Series(ws); return dict(h_maxdd=mdd, h_trough=str(trough.date()) if trough is not None else "", h_worst_week=float(w.min()), h_worst_4w=float(w.rolling(4).sum().min()), h_worst_52w=float(w.rolling(52).sum().min()), h_underwater_weeks=uwmax, h_total=c, h_years=len(dates) / 52.0)
def boot(T, add, cols, shrink, weeks=520, n_paths=20000, seed=187):
    pnl, fired = T[0][:, cols], T[1][:, cols]; ad = add[cols]; nn = pnl.shape[1]; rng = np.random.default_rng(seed); c = np.zeros(n_paths); hwm = np.zeros(n_paths); mdd = np.zeros(n_paths); fires = np.zeros(n_paths, int); out = {}; c52 = None
    for w in range(weeks):
        if w % 4 == 0: fires[:] = 0
        idx = rng.integers(0, nn, n_paths); gi = lvl(c, shrink); act = fires < 2; c = c + np.where(act, pnl[gi, idx], 0.0) + ad[idx]; fires += np.where(act, fired[gi, idx], 0); hwm = np.maximum(hwm, c); mdd = np.maximum(mdd, hwm - c)
        if w + 1 == 52: c52 = c.copy()
        if w + 1 in (52, 260, 520):
            y = (w + 1) // 52; out[f"dd95_{y}y"] = float(np.quantile(mdd, 0.95)); out[f"dd50_{y}y"] = float(np.median(mdd)); out[f"dd99_{y}y"] = float(np.quantile(mdd, 0.99))
            for th in TH: out[f"p_dd{int(th * 1000)}_{y}y"] = float((mdd >= th).mean()) * 100
    out["mean_year"] = float(c.mean()) / (weeks / 52.0); out["p_neg_year"] = float((c52 < 0).mean()) * 100; return out
if __name__ == "__main__":
    items, _, _ = norm_items("6071612"); fac = make_fac(items, True, 0.5); rows = []
    for fn, its, rw in (("月曜のみ", list(items), 0.0), ("月曜 + ロール", list(items), RW), ("月曜 + ロール + 夜の指数", list(items) + NIGHT, RW)):
        MODE["k"] = "E1"; T, dates = build_full(its, None, G, fac, MM); MODE["k"] = None; dates = [pd.Timestamp(d) for d in dates]; assert all(dates[i] < dates[i + 1] for i in range(len(dates) - 1)); add = roll_week(dates, rw, G) if rw else np.zeros(len(dates)); call = np.arange(len(dates)); c2 = call[np.array([d < PM for d in dates])]
        for shrink in (False, True):
            H = {tag: hist(T[tag], add, dates, shrink) for tag in ("lo", "cl")}; r = dict(form=fn, shrink="あり" if shrink else "なし", weeks=len(dates), guard_rate=round(float(max((T[t][1][-1] > 0).mean() for t in ("lo", "cl"))) * 100, 1))
            for k in ("h_maxdd", "h_underwater_weeks"): r[k] = max(H[t][k] for t in H)
            for k in ("h_worst_week", "h_worst_4w", "h_worst_52w", "h_total"): r[k] = min(H[t][k] for t in H)
            r["h_trough"] = max(H.values(), key=lambda x: x["h_maxdd"])["h_trough"]; r["h_years"] = H["lo"]["h_years"]
            for sn, cols in (("all", call), ("w2", c2)):
                Bt = {tag: boot(T[tag], add, cols, shrink) for tag in ("lo", "cl")}
                for k in Bt["lo"]: r[f"{sn}_{k}"] = (min if k == "mean_year" else max)(Bt[t][k] for t in Bt)
            rows.append(r); print("done", fn, shrink, flush=True)
    D = pd.DataFrame(rows); pc = [c for c in D.columns if c.startswith(("h_maxdd", "h_worst", "h_total")) or "_dd95" in c or "_dd50" in c or "_dd99" in c or c.endswith("mean_year")]
    for c in pc: D[c] = (D[c] * BASE).round(1)          # 基準 1000 万円に対する万円
    D = D.round(2); D.to_csv("results/q292_own_capital_reserve.csv", index=False); pd.set_option("display.width", 330); pd.set_option("display.max_columns", 80)
    print("\n== Q292 (1) 実際の順番(金額は万円・基準 1000 万円)=="); print(D[["form", "shrink", "weeks", "guard_rate", "h_maxdd", "h_trough", "h_underwater_weeks", "h_worst_week", "h_worst_4w", "h_worst_52w", "h_total", "h_years"]].to_string(index=False))
    for sn, lab in (("all", "全期間の抽選"), ("w2", "前半(2016-11〜2021-07)だけの抽選")):
        print(f"\n== Q292 (2) 並べ替え 10 年・{lab}(最大の落ち込み 万円: 中央 / 95% / 99%・超える確率 %)=="); print(D[["form", "shrink"] + [f"{sn}_{k}" for k in ("dd50_10y", "dd95_10y", "dd99_10y", "dd95_1y", "dd95_5y", "p_dd100_1y", "p_dd100_5y", "p_dd100_10y", "p_dd150_10y", "p_dd200_10y", "p_dd300_10y", "mean_year", "p_neg_year")]].to_string(index=False))
    x = D[(D.form == "月曜 + ロール") & (D.shrink == "あり")].iloc[0]; res = float(np.ceil(max(x.h_maxdd, x.all_dd95_10y) / 10.0) * 10); print(f"\n先に決めた決め方: 「月曜 + ロール・縮小あり」— 実際の最大 {x.h_maxdd} 万・並べ替え 10 年の 95% 点 {x.all_dd95_10y} 万 → 負けに耐える分 = {res:.0f} 万円。元手 = 証拠金 223 万 + {res:.0f} 万 = {223 + res:.0f} 万円。より保守的: 99% 点 {x.all_dd99_10y} 万・前半だけの 95% 点 {x.w2_dd95_10y} 万・99% 点 {x.w2_dd99_10y} 万")
