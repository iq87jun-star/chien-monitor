# -*- coding: utf-8 -*-
"""docs/244 Q183(診断・セル 0・2026-11-12 登録「3は検証を」): 月曜レグの損切り合計に上限を入れた場合の影響(全口座)。
EA の月曜レグを H1 で再現: 円クロス = 月曜 4/6/8/10 UTC 建て、指数 = 米国現物寄り後の最初の正時(夏 14・冬 15 UTC)、24h 保有、
災害 SL = 3.0 × 直前 24 本の H1 レンジ平均(為替は最小 10 pips)。SL は H1 安値で判定し SL 価格で約定。コスト = q_common.cost。
ショットの SL リスク = 重み ÷ ショット数 × SL 幅 ÷ 建値。上限 C を超える新規は収まる大きさに縮小、残り枠がリスクの 1 割未満なら見送り。
方式 A = 建玉中のショットだけを数える(登録どおり・Instant v1.19 と同じ)。方式 B = その月曜に損切り済みのショットも数え続ける(実行後に追加: A では損切り後に枠が空いて建て直すため 1 日の損失が上限を超える)。
使い方: cd research && python3 -W ignore queue/q183_sl_sum_cap.py   出力: results/q183_sl_sum_cap.csv・_dist.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
import q_common as q
src = open(os.path.join(HERE, "q162_weekday_diversification.py"), encoding="utf-8").read().split('scen = {"B 現状"')[0]
ns = {"__name__": "q162_head", "__file__": os.path.join(HERE, "q162_weekday_diversification.py")}; exec(compile(src, "q162_head", "exec"), ns)
cfg, EA_LEGS = ns["cfg"], ns["EA_LEGS"]; acc_id = ns["ns"]["acc_id"]
P0, P1 = pd.Timestamp("2021-08-01"), pd.Timestamp("2026-07-31")
LIMIT = {"ftmo1step": 0.03, "fn_instant": 0.03}          # それ以外は 5%
IDXMAP = {"nas": "NAS100", "spx": "US500"}
def us_dst(d):
    y = d.year; mar = pd.Timestamp(y, 3, 8); mar += pd.Timedelta(days=(6 - mar.dayofweek) % 7); nov = pd.Timestamp(y, 11, 1); nov += pd.Timedelta(days=(6 - nov.dayofweek) % 7)
    return mar <= d < nov
_SH = {}
def shots(sym, idx):
    """月曜ごとのショット表: date, t_in, risk_per_unit(SL 幅 ÷ 建値), ret_sl(SL あり), ret_nosl, t_stop"""
    if (sym, idx) in _SH: return _SH[(sym, idx)]
    df = q.load(sym); o, lo = df["open"], df["low"]; atr = q.atr24(df); pip = q.base.pip_size(sym) if not idx else 0.0; rows = []
    mondays = pd.DatetimeIndex(sorted(set(o.index[(o.index.dayofweek == 0)].normalize())))
    for d in mondays:
        if not (P0 <= d <= P1): continue
        hours = [(14 if us_dst(d) else 15)] if idx else [4, 6, 8, 10]
        for h in hours:
            t = d + pd.Timedelta(hours=h); t2 = t + pd.Timedelta(hours=24)
            if t not in o.index or t2 not in o.index or np.isnan(atr.get(t, np.nan)): continue
            e = float(o[t]); sd = max(3.0 * float(atr[t]), 10 * pip); c = float(q.cost(sym, [e])[0]); seg = lo[(lo.index >= t) & (lo.index < t2)]
            hit = seg[seg <= e - sd]
            r_no = float(o[t2]) / e - 1 - c; r_sl = (-sd / e - c) if len(hit) else r_no
            rows.append((d, t, sd / e + c, r_sl, r_no, hit.index[0] if len(hit) else pd.NaT, len(hours)))
    _SH[(sym, idx)] = pd.DataFrame(rows, columns=["date", "t", "risk", "r_sl", "r_no", "t_stop", "nshots"]); return _SH[(sym, idx)]
CAPS = [None, 0.06, 0.05, 0.045, 0.04, 0.035, 0.03, 0.025, 0.02]
out, dist = [], []
for a in cfg["accounts"]:
    aid = acc_id(a["name"]); key = "funded" if (a.get("funded_now") and aid != "14074882") else "eval"; legs = EA_LEGS[aid][key]
    parts = []
    for k, w in legs.items():
        if k.startswith("mon:"): s = shots(k[4:], False).copy()
        elif k in IDXMAP: s = shots(IDXMAP[k], True).copy()
        else: continue
        s["w"] = w / s.nshots; s["leg"] = k; parts.append(s)
    if not parts: continue
    S = pd.concat(parts).sort_values(["date", "t"]).reset_index(drop=True); S["risk_w"] = S.w * S.risk
    L = LIMIT.get(a.get("rule"), 0.05); full = S.groupby("date").risk_w.sum()
    dist.append(dict(acct=a["name"][:20], legs_key=key, mon_weight=round(sum(w for k, w in legs.items() if k.startswith("mon:") or k in IDXMAP), 2), firm_daily_limit=L, mondays=len(full), sl_sum_med=round(full.median() * 100, 2),
                     sl_sum_p95=round(full.quantile(.95) * 100, 2), sl_sum_max=round(full.max() * 100, 2), sl_sum_max_date=str(full.idxmax().date()), share_over_limit=round(float((full > L).mean()), 3)))
    base_mean = None
    for C, VAR in [(c, v) for v in ("A 建玉中のみ数える(v1.19 と同じ)", "B 当日の損切り済みも数える") for c in CAPS if not (c is None and v.startswith("B"))]:
        f = np.ones(len(S))
        if C is not None:
            for d, g in S.groupby("date"):
                used = []                      # (t_stop, risk) of open shots
                for i in g.index:
                    t = S.t[i]; open_risk = sum(r for ts, r in used if VAR.startswith("B") or pd.isna(ts) or ts > t); room = C - open_risk; r = S.risk_w[i]
                    fi = 1.0 if r <= room else (room / r if room >= 0.1 * r else 0.0); f[i] = fi; used.append((S.t_stop[i], r * fi))
        pnl = (S.w * f * S.r_sl).groupby(S.date).sum(); pnl_no = (S.w * f * S.r_no).groupby(S.date).sum(); rk = (S.risk_w * f).groupby(S.date).sum()
        m = pnl.groupby(pnl.index.to_period("M")).sum(); sh = float(m.mean() / m.std() * np.sqrt(12)) if m.std() > 0 else np.nan
        if C is None: base_mean = pnl.mean()
        out.append(dict(acct=a["name"][:20], variant=("—" if C is None else VAR[:1]), cap=("なし" if C is None else f"{C*100:.1f}%"), firm_limit=f"{L*100:.0f}%", worst_monday_pct=round(pnl.min() * 100, 2), mondays_loss_over_limit=int((pnl < -L).sum()),
                        sl_sum_max_pct=round(rk.max() * 100, 2), mean_monday_bps=round(pnl.mean() * 1e4, 1), mean_change_pct=round((pnl.mean() / base_mean - 1) * 100, 1) if base_mean else 0.0,
                        sharpe_m=round(sh, 2), worst_month_pct=round(m.min() * 100, 2), cap_binds_share=round(float(pd.Series(f < 1, index=S.index).groupby(S.date).any().mean()), 3), notional_kept=round(float((S.w * f).sum() / S.w.sum()), 3),
                        mean_no_sl_bps=round(pnl_no.mean() * 1e4, 1), recommended=bool(C is not None and abs(C - (L - 0.005)) < 1e-9)))
D = pd.DataFrame(out); Z = pd.DataFrame(dist); D.to_csv("results/q183_sl_sum_cap.csv", index=False); Z.to_csv("results/q183_sl_sum_cap_dist.csv", index=False)
pd.set_option("display.width", 280); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 200)
print(Z.to_string(index=False)); print()
print(D[D.cap.isin(["なし"]) | D.recommended].drop(columns=["recommended"]).to_string(index=False)); print()
print(D[D.acct.str.contains("トパーズ") & (D.variant != "A")].drop(columns=["recommended", "mean_no_sl_bps"]).to_string(index=False))
