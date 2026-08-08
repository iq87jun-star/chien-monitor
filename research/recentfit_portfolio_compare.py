# -*- coding: utf-8 -*-
"""
recentfit_portfolio_compare.py — 現行配備ポートフォリオ vs 非FX新案の同一物差し比較
(2026-08-06 ユーザー依頼。recentfit_nonfx_screen.py の続き)

現行4口座(docs/178/181)を配備倍率で再構築し、非FX案(recentfit_nonfx_screen.json)と
リターン・リスク・相関・分散効果を比較する。

近似の注意:
- S1/S2/Mon系は月曜o2o(24h)近似(実EAは12h保有=保守側に乖離し得る)
- S3は木曜o2o SHORT近似(実EAは16UTC+6h保有)
- S4/S5はRSI(2)逆張りをD1で再現(翌始値建て・N日後始値決済・単玉)
- A案は各スリーブ等リスク(1.25%/回)を等ウェイト×校正倍率で近似
- Fintokei資金は¥500万≈$32k(155円)と仮定
- Yahoo日足・配当除く。数字は全て近似であり実口座成績ではない
出力: results/recentfit_portfolio_compare.json
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_screen as base
import recentfit_nonfx_screen as nfx   # ユニバース拡張(WTI/NATGAS)とv4_cell_nonfxを再利用

# ---------------- A案 RecentFit5 の追加セル ----------------
def mon_cell_dow(nm, dow, short=False):
    """曜日o2oセル(dow: 0=月..4=金)。S3=木曜SHORT用"""
    df = base.load_daily(nm)
    c = 2 * base.pip_size(nm) / df["open"]
    s = (df[df["weekday"] == dow]["o2o"] - c).dropna()
    return base.clip(-s if short else s)


def rsi2_cell(nm, lo, hi, hold_days):
    """RSI(2)逆張り: 当日終値RSI<lo→翌始値LONG / >hi→翌始値SHORT、N本後始値決済・単玉"""
    df = base.load_daily(nm)
    o = df["open"].values; c = df["close"].values; idx = df.index
    rsi = base.rsi_w(c, n=2)
    cost = 2 * base.pip_size(nm)
    acc = {}; n = len(c); i = 5; busy_until = -1
    while i < n - 1:
        if i <= busy_until:
            i += 1; continue
        sig = 1 if rsi[i] < lo else (-1 if rsi[i] > hi else 0)
        if sig == 0:
            i += 1; continue
        j_ent = i + 1
        j_ex = min(j_ent + hold_days, n - 1)
        entry = o[j_ent]
        if entry <= 0:
            i += 1; continue
        prev = entry
        for t in range(j_ent, j_ex + 1):
            px = o[j_ex] if t == j_ex else c[t]
            r = sig * (px - prev) / entry
            if t == j_ent: r -= cost / entry
            acc[idx[t]] = acc.get(idx[t], 0.0) + r
            prev = px
        busy_until = j_ex
        i += 1
    return base.clip(pd.Series(acc).sort_index())


def aligned_sum(parts, weights=None):
    idx = sorted(set().union(*[set(s.index) for s in parts]))
    out = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for k, s in enumerate(parts):
        w = 1.0 if weights is None else weights[k]
        out = out.add(s.reindex(out.index).fillna(0.0) * w, fill_value=0.0)
    return out


def metrics(s, label):
    s12 = base.win(s, base.W12_0); s6 = base.win(s, base.W6_0)
    act = s[s != 0.0]; act12 = s12[s12 != 0.0]
    years = max((s.index[-1] - s.index[0]).days / 365.25, 1e-9)
    cagr = (1 + act).prod() ** (1 / years) - 1
    wd12, wdd12 = base.worst_stats(s12)
    wd_full, wdd_full = base.worst_stats(s)
    eq = (1 + s).cumprod(); maxdd_full = float(((eq - eq.cummax()) / eq.cummax()).min())
    eq12 = (1 + s12).cumprod(); maxdd12 = float(((eq12 - eq12.cummax()) / eq12.cummax()).min())
    sharpe12 = float(act12.mean() / act12.std() * np.sqrt(252)) if len(act12) > 5 and act12.std() > 0 else None
    return dict(
        label=label,
        cum_12m=round(float((1 + s12).prod() - 1) * 100, 2),
        cum_6m=round(float((1 + s6).prod() - 1) * 100, 2),
        cagr_full=round(float(cagr) * 100, 2),
        sharpe_12m=round(sharpe12, 2) if sharpe12 else None,
        vol_12m_ann=round(float(act12.std() * np.sqrt(252)) * 100, 2) if len(act12) > 5 else None,
        worst_day_12m=round(wd12 * 100, 2), worst_intramonth_dd_12m=round(wdd12 * 100, 2),
        max_dd_12m=round(maxdd12 * 100, 2),
        worst_day_full=round(wd_full * 100, 2), max_dd_full=round(maxdd_full * 100, 2))


def main():
    print("[1/4] 現行4口座の合成を配備構成で再構築")
    # A案 FTMO100k(等ウェイト近似・倍率は同一規則で校正)
    a_parts = [base.mon_cell("GBPUSD"),                     # S1(月曜o2o近似)
               base.mon_cell("GBPJPY"),                     # S2
               mon_cell_dow("USDCHF", 3, short=True),       # S3 木曜SHORT近似
               rsi2_cell("GBPUSD", 30, 70, 5),              # S4
               rsi2_cell("GBPJPY", 20, 80, 3)]              # S5
    a_raw = aligned_sum(a_parts, [0.2] * 5)
    a_mult = base.calibrate(base.win(a_raw, base.W12_0))
    comp_A = a_raw * a_mult

    comp_B = aligned_sum([base.mon_cell("GBPJPY"), base.mon_cell("AUDJPY"), base.v4_cell("USDJPY")],
                         [0.374, 0.322, 0.304]) * 4.0
    comp_C = aligned_sum([base.mon_cell("GBPJPY"), base.mon_cell("AUDJPY"),
                          base.v4_cell("NZDUSD"), base.v4_cell("AUDUSD")],
                         [0.323, 0.269, 0.207, 0.201]) * 6.0
    comp_D = aligned_sum([base.mon_cell("USDJPY"), base.mon_cell("GBPJPY"),
                          base.v4_cell("NZDUSD"), base.v4_cell("AUDUSD")],
                         [0.374, 0.139, 0.287, 0.2]) * 5.52

    print(f"  A案校正倍率(近似)={a_mult}")

    print("[2/4] 非FX新案の合成(recentfit_nonfx_screenの選抜・標準倍率1.56x)")
    with open(os.path.join(HERE, "results", "recentfit_nonfx_screen.json")) as f:
        nfx_res = json.load(f)
    sel = nfx_res["selected"]; nfx_mult = nfx_res["variants"]["standard"]["mult"]
    cell_fn = {"Mon": base.mon_cell, "Hold": base.hold_cell,
               "TSMOM": base.tsmom_cell, "v4": nfx.v4_cell_nonfx}
    parts, ws = [], []
    for key, w in sel.items():
        fam, sym = key.split("_", 1)
        parts.append(cell_fn[fam](sym)); ws.append(w)
    comp_N = aligned_sum(parts, ws) * nfx_mult

    print("[3/4] 口座資金加重の現行合算と、非FX追加後の合算")
    CAP = {"A_FTMO100k": 100.0, "B_Fintokei": 32.0, "C_FTMO50k": 50.0, "D_FTMO50k": 50.0}
    comps = {"A_FTMO100k": comp_A, "B_Fintokei": comp_B, "C_FTMO50k": comp_C, "D_FTMO50k": comp_D}
    tot = sum(CAP.values())
    cur = aligned_sum([comps[k] for k in CAP], [CAP[k] / tot for k in CAP])
    # 非FXを新規100k Swing口座に配備した想定(docs/182 §3の実配備に一致。
    # 2026-08-08修正: 旧実装は50k想定でdocs/182 §1の引用値と配備規模が不整合だった)
    NEW_CAP = 100.0
    tot2 = tot + NEW_CAP
    caps2 = {**{k: CAP[k] / tot2 for k in CAP}, "NonFX_100k": NEW_CAP / tot2}
    combined = aligned_sum([comps[k] for k in CAP] + [comp_N], list(caps2.values()))

    print("[4/4] 指標と相関")
    rows = [metrics(comp_A, "A案 RecentFit5(FTMO100k)"),
            metrics(comp_B, "B案 2026H2(Fintokei 4.0x)"),
            metrics(comp_C, "C案 6ヶ月(FTMO50k 6.0x)"),
            metrics(comp_D, "D案 3ヶ月(FTMO50k 5.52x)"),
            metrics(comp_N, f"非FX新案(標準{nfx_mult}x)"),
            metrics(cur, "現行合算(資金加重)"),
            metrics(combined, "現行+非FX100k合算")]
    for r in rows:
        print(f"  {r['label']:26s} 12m={r['cum_12m']:>7}% 6m={r['cum_6m']:>7}% "
              f"Sh12m={r['sharpe_12m']} 最悪日12m={r['worst_day_12m']}% 月中DD12m={r['worst_intramonth_dd_12m']}%")

    named = {"A案": comp_A, "B案": comp_B, "C案": comp_C, "D案": comp_D, "非FX": comp_N}
    al = nfx.daily_aligned(list(named.values()))
    mat = pd.DataFrame({k: v for k, v in zip(named, al)})
    corr12 = mat[mat.index >= base.W12_0].corr().round(2)
    corr_full = mat.corr().round(2)
    print("  12ヶ月相関:\n", corr12.to_string())

    res = dict(
        meta=dict(purpose="現行4口座ポートフォリオ vs 非FX新案の同一物差し比較",
                  approx=["S1/S2/Mon=月曜o2o(実EAは12h)", "S3=木曜o2o SHORT(実EAは6h)",
                          "S4/S5=RSI2逆張りD1再現", f"A案倍率={a_mult}(等ウェイト近似を同一規則で校正)",
                          "Fintokei=¥500万≈$32k", "Yahoo日足近似・実口座成績ではない"],
                  deployed_mults=dict(A=a_mult, B=4.0, C=6.0, D=5.52, NonFX=nfx_mult),
                  capital_weights=caps2),
        portfolios={r["label"]: r for r in rows},
        corr_12m=corr12.to_dict(), corr_full=corr_full.to_dict())
    path = os.path.join(HERE, "results", "recentfit_portfolio_compare.json")
    with open(path, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
