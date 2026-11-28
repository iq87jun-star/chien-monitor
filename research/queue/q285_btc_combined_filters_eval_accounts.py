# -*- coding: utf-8 -*-
"""docs/244 Q285(2026-11-25 登録「登録実行」・セル 39): 週末の BTC を併用する 3 つの形(Q284 の変更候補)を、評価中の口座の到達・失格で確かめる。
型: G = z ≥ +1 を 0.5 倍 かつ z ≥ +2 を見送る / V = z ≥ +2 かつ 前金曜の VIX ≤ 25 を見送る / J = z ≥ +1 かつ 週明けの飛び ≥ +1 を見送る。月曜の円クロスのレグだけ。
場面(13): Q233・Q263b の評価中の場面から FN 14074882 の 2 場面を除く。「いま」の開始残高は 2026-11-25 06:22 JST の記録。それ以外の設定は Q263b のまま。
判定: 各セル = Q233 の ev_ok。型ごと = 13 場面のどれも悪化せず かつ 1 場面以上で ev_ok なら「評価中の口座でも使える」。
使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q285_btc_combined_filters_eval_accounts.py <累積セル数>   出力: results/q285_btc_combined_eval.csv"""
import os, sys
_ARGV = list(sys.argv)
HERE = os.path.dirname(os.path.abspath(__file__)); _s = open(os.path.join(HERE, "q263b_monday_night_index_account_model.py"), encoding="utf-8").read()
n = {"__name__": "q263b_head", "__file__": os.path.join(HERE, "q263b_monday_night_index_account_model.py")}; exec(compile(_s.split("\nrows = []\n")[0], "q263b_head", "exec"), n)
np, pd = n["np"], n["pd"]; n3 = n["n3"]; norm_items, account_items, acct, make_fac, build_full, sim_eval, MODE, PM, ev_ok = (n[k] for k in ("norm_items", "account_items", "acct", "make_fac", "build_full", "sim_eval", "MODE", "PM", "ev_ok")); P0, P1 = n3["P0"], n3["P1"]; VIX = n3["VIX"]
import q279_weekend_gap_skip_funded as q279
import q282_outside_info_btc_weekend_epu_gpr as q282
# 場面: (口座, key, 段階, 月曜の倍率, skew, tilt, smin, trail, 開始, 目標, pad, cap, 決済の型)。Q263b の B から FN 14074882 を除き、「いま」の開始だけ 11/25 の残高に置き換え
B = [("FTMO 0397", "521100397", "いま", 6.0, False, False, None, False, 53854 / 5e4 - 1, 0.10, 0.01, None, None), ("FTMO 7058", "531407058", "いま", 6.0, False, False, None, False, 51513 / 5e4 - 1, 0.10, 0.01, None, None),
     ("FTMO 50k", "521100397", "次", 6.0, False, True, 0.5, False, 0.0, 0.05, 0.01, None, None),
     ("宝くじ", "531343523", "いま", 8.0, True, False, None, False, 92749 / 1e5 - 1, 0.10, 0.005, None, "E1"), ("宝くじ", "531343523", "次", 8.0, True, True, 0.5, False, 0.0, 0.05, 0.005, None, "E1"),
     ("1-Step", "531466484", "いま", None, True, False, None, True, 95432 / 1e5 - 1, 0.10, 0.01, "acct", None),
     ("トパーズ", "6104739", "いま", 8.0, False, False, None, False, 35344369 / 35e6 - 1, 0.08, 0.01, None, "E1"), ("トパーズ", "6104739", "次(6 倍)", 6.0, True, True, 0.5, False, 0.0, 0.06, 0.01, None, "E1"),
     ("ルビー", "6104736", "いま", 8.35, False, True, 0.5, False, 10047790 / 1e7 - 1, 0.08, 0.01, None, "E1"), ("ルビー", "6104736", "次(8.35 倍)", 8.35, False, True, 0.5, False, 0.0, 0.06, 0.01, None, "E1"), ("ルビー", "6104736", "次(6.3 倍)", 6.3, False, True, 0.5, False, 0.0, 0.06, 0.01, None, "E1"),
     ("パール", "6071612", "いま", 5.57, False, False, None, False, 5061556 / 5e6 - 1, 0.08, 0.01, None, "E1"), ("パール", "6071612", "次", 5.57, False, True, 0.5, False, 0.0, 0.06, 0.01, None, "E1")]
def worse(b, v): return bool(any(v[f"reach_{w}"] < b[f"reach_{w}"] - 1.0 or v[f"fail_{w}"] > b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")))
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 39
    it0, _, _ = q279.m.norm_items("521100397"); GP, _ = q279.gaps(it0); Z = q282.sig_btc()[0]; Z = Z[(Z.index >= P0) & (Z.index <= P1)]
    vx = pd.Series(VIX.reindex(Z.index - pd.Timedelta(days=3), method="ffill").values, index=Z.index); gp = GP.reindex(Z.index)
    up1, up2 = Z >= 1, Z >= 2
    FORMS = {"G: 上げた週は 0.5 倍・大きく上げた週は見送り": {**{d: 0.5 for d in Z.index[up1]}, **{d: 0.0 for d in Z.index[up2]}}, "V: 大きく上げ かつ VIX ≤ 25 を見送り": {d: 0.0 for d in Z.index[up2 & (vx <= 25)]}, "J: 上げ かつ 飛び ≥ +1 を見送り": {d: 0.0 for d in Z.index[up1 & (gp >= 1)]}}
    print("該当する週:", {k: len(v) for k, v in FORMS.items()}, flush=True); rows = []
    def run(items, cap, g, fac, mm, mode, start, target, pad0, smin, trail):
        MODE["k"] = mode; T, dates = build_full(items, cap, g, fac, mm); MODE["k"] = None; r = {}
        for wn, sel in (("W1", np.array([d >= PM for d in dates])), ("W2", np.array([d < PM for d in dates]))):
            cols = np.arange(len(dates))[sel]; rr = [sim_eval(T[tag], cols, start, target, 0.10, pad0, smin, trail) for tag in ("lo", "cl")]; r[f"reach_{wn}"] = round(min(x[0] for x in rr), 1); r[f"fail_{wn}"] = round(max(x[1] for x in rr), 1); r[f"weeks_{wn}"] = max((x[2] or 0) for x in rr)
        return r
    for nm, key, stage, mm, skew, tilt, smin, trail, start, target, pad0, capm, mode in B:
        items, cap, g = norm_items(key); cap = cap if capm == "acct" else None
        if mm is None: _, i0, _, _ = account_items(acct(key)); mm = sum(w for s_, i, w in i0 if not i)
        fac = make_fac(items, skew, 0.5 if tilt else None); fxk = [(s_, i) for s_, i, w in items if not i]
        b = run(items, cap, g, fac, mm, mode, start, target, pad0, smin, trail); rows.append(dict(acct=nm, stage=stage, form="現行", fx_legs=len(fxk), cells=0, verdict="基準", **b))
        for fn, mp in FORMS.items():
            fc = {k: dict(v) for k, v in fac.items()}
            for k in fxk:
                d0 = fc.setdefault(k, {})
                for d, x in mp.items(): d0[d] = d0.get(d, 1.0) * x
            v = run(items, cap, g, fc, mm, mode, start, target, pad0, smin, trail); w = worse(b, v); ok = ev_ok(b, v)
            rows.append(dict(acct=nm, stage=stage, form=fn, fx_legs=len(fxk), cells=1, verdict="変更候補" if ok else ("悪化" if w else "現行どおり"), **v))
        print("done", nm, stage, b, flush=True)
    D = pd.DataFrame(rows); D.to_csv("results/q285_btc_combined_eval.csv", index=False); assert int(D.cells.sum()) == N
    pd.set_option("display.width", 330); pd.set_option("display.max_rows", 200); pd.set_option("display.max_colwidth", 46)
    print(f"\n== Q285(累積セル {cum} + {N} = {cum + N}・到達 % / 失格 % / 中央の週数。W1 = 2021-08〜・W2 = 2016-11〜2021-07) =="); print(D[["acct", "stage", "form", "reach_W1", "fail_W1", "weeks_W1", "reach_W2", "fail_W2", "weeks_W2", "verdict"]].to_string(index=False))
    for fn in FORMS:
        x = D[D.form == fn]; nb = int((x.verdict == "悪化").sum()); nk = int((x.verdict == "変更候補").sum()); print(f"{fn}: 変更候補 {nk} / 13・悪化 {nb} / 13 → {'評価中の口座でも使える' if (nb == 0 and nk >= 1) else '本口座後だけの候補'}")
    print(f"\nセルの判定: 変更候補 {int((D.verdict == '変更候補').sum())} / {N}・悪化 {int((D.verdict == '悪化').sum())} / {N}")
