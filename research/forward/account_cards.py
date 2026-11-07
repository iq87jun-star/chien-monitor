# -*- coding: utf-8 -*-
"""口座カード(ダッシュボード)のデータ生成。① 現状数値(ops digest + config/portfolio_current.json)と、
② 採用 EA のリスク倍率で均した月利の過去 5 年推移(forward/portfolio_sim の帳簿・評価中/資金化後の両倍率)、
③ 初回出金の時期・金額の見込み(portfolio_sim と同じ経路・規則の MC・N=6000・種 44・30 か月)を 2 つの JSON(行配列)に書く。
使い方: cd research && python3 -W ignore forward/account_cards.py
出力: results/account_cards_accounts.json(口座 1 行)・results/account_cards_monthly.json(口座 × 年月 1 行)。
更新: 本 script を再実行 → 2 ファイルをダッシュボードの添付ファイルとして再アップロードし、各データセットの url/updated を書き換える。"""
import os, sys, json, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); os.chdir(ROOT)
import numpy as np, pandas as pd
from forward.portfolio_sim import legs, book, R
cfg = json.load(open("config/portfolio_current.json", encoding="utf-8"))
DIG = "results/ops_digest_latest.json"; digest = json.load(open(DIG, encoding="utf-8")) if os.path.exists(DIG) else {"accounts": []}
dig = {a["account"]: a for a in digest.get("accounts", [])}
FX = 158.0; N = 6000; SEED = 44; MONTHS = 30; BLOCK = 5; YEARS = 5
META = {  # 口座番号 → 会社・表示名・採用 EA(docs/241 §1ak 時点)
    "531466484": ("FTMO", "100k 1-Step", "EA9 A案 HoldXAU+MonGBPJPY+MonNAS100+Mon3 3.0倍 v1.06"),
    "531343523": ("FTMO", "100k 2-Step 宝くじ", "EA10L Mon4 10.0倍+GER40ブレイク 6.0倍+HoldXAU0.9 v1.07"),
    "14166201": ("FundedNext", "100k Stellar 2-Step", "RecentFit Hold UK100/WTI 2.22倍+Roll5 4.5倍 v1.39"),
    "6104736": ("Fintokei", "スイング ルビー 1,000万", "RecentFit B案 12.0倍 v1.07"),
    "6104739": ("Fintokei", "スイング トパーズ 3,500万", "EA11 Mon4×8.0+IdxMon1.0 dyn1 v1.20"),
    "521100397": ("FTMO", "50k 2-Step 資金化済", "EA8 Mon4 6.0倍+GER40ブレイク 2.0倍 dyn1 v1.39"),
    "531407058": ("FTMO", "50k 2-Step 資金化済", "EA3 Mon4 6.0倍 dyn1 v1.21"),
    "6071612": ("Fintokei", "スイング パール 500万 資金化済", "RecentFit B案 8.0倍 v1.13"),
    "14074882": ("FundedNext", "100k 資金化済", "RecentFit Mon3×4+HoldXAU0.4 v1.13"),
    "11988011": ("FundedNext", "Instant 20k", "RecentFit G Mon2×4+MonNAS100/US500×1 v1.17"),
}
RULE_JA = {"static": "静的床・月次出金", "ftmo2step": "FTMO 2-Step(全利益分配・ロール)", "ftmo1step": "FTMO 1-Step(トレーリング床・毎月全額)", "fn_instant": "FN Instant(建値ロック・+5% で 2%)"}
def acc_id(name): return name.split()[-1]
def spec_txt(spec): return " + ".join(f"{k} ×{w:g}" for k, w in spec.items())
def monthly(spec, sw):
    s = book(spec, sw); m = (1 + s).resample("ME").prod() - 1
    end = m.index[-1]; start = pd.Timestamp(year=end.year - YEARS, month=end.month, day=1) + pd.offsets.MonthEnd(0) + pd.offsets.MonthBegin(1)
    return m[m.index >= start]
def mstats(m):
    if len(m) == 0: return {}
    eq = (1 + m).cumprod(); dd = (eq / eq.cummax() - 1).min()
    return dict(mean=float(m.mean()), med=float(m.median()), win=float((m > 0).mean()), best=float(m.max()), worst=float(m.min()), mdd=float(dd),
                cagr=float(eq.iloc[-1] ** (12 / len(m)) - 1), last12=float((1 + m.iloc[-12:]).prod() - 1), sharpe=float(m.mean() / m.std() * np.sqrt(12)) if m.std() > 0 else 0.0)
# ---- MC(forward/portfolio_sim.run_portfolio と同じ規則。初回出金の月と金額を記録) ----
g = cfg["global"]; k, keep, pf = g["k"], g["keep"], g.get("pay_frac", 1.0); start = pd.Timestamp(g["start"])
DAYS = 21 * MONTHS; rng = np.random.default_rng(SEED)
T = len(R(legs()["mon4"])); nb = T - BLOCK + 1; stt = rng.integers(0, nb, size=(N, DAYS // BLOCK + 1)); IDX = (stt[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(N, -1)[:, :DAYS]
def mc(a):
    sw = a.get("swap_xau_bps_m", 0.0)
    ce = R(book(a["eval"], sw))[IDX]; cf = R(book(a["funded"], sw))[IDX]; e0 = a["e0"]; tg = a["targets"]; mdd = a["mdd"]; dll = a["dll"]; bal = a["balance_jpy"]
    kk = a.get("k", k); kp = a.get("keep", keep); fn = a.get("funded_now", False); trail = a.get("trail", False)
    rule = a.get("rule", "static"); share = a.get("share", {"ftmo1step": 0.9, "fn_instant": 0.7}.get(rule, 0.8)); pfx = a.get("pay_fixed") if rule == "fn_instant" else None
    e = np.full(N, e0); basel = np.ones(N); stage = np.zeros(N, int); funded = np.full(N, fn); failed = np.zeros(N, bool); hwm = np.full(N, e0); paid = np.zeros((N, MONTHS)); ro = np.zeros(N); fund_day = np.full(N, -1); fund_day[funded] = 0
    for t in range(DAYS):
        act = ~failed
        if rule == "ftmo1step": fl = np.where(funded, np.maximum(hwm, basel) - mdd, np.minimum(hwm - mdd, 1.0))
        elif rule == "fn_instant": fl = np.minimum(hwm - mdd, basel)
        else:
            fl = basel * (1 - mdd)
            if trail: fl = np.where(funded, basel * (1 - mdd), np.minimum(hwm - mdd, 1.0))
        f = np.where(funded, np.clip(1 + kk * ((e - fl) / basel - mdd) / mdd, 1.0, 1 + kk), 1.0)
        ret = np.clip(np.where(funded, cf[:, t] * f, ce[:, t]), -dll, None); e = np.where(act, e * (1 + ret), e); hwm = np.maximum(hwm, e); failed |= act & (e <= fl)
        if not fn:
            for s in range(len(tg)):
                hit = act & ~failed & ~funded & (stage == s) & (e >= basel * (1 + tg[s]))
                if s == len(tg) - 1: funded |= hit; e[hit] = 1.0; basel[hit] = 1.0; hwm[hit] = 1.0; fund_day[hit] = t
                else: stage[hit] = s + 1; basel[hit] = e[hit]
        if (t + 1) % 21 == 0:
            m = (t + 1) // 21 - 1; ok = funded & ~failed
            if pfx is not None: w = np.where(ok & (e >= basel * (1 + pfx[0])), pfx[1], 0.0); paid[:, m] = w * bal * share; e -= w
            elif rule == "ftmo1step": w = np.where(ok, np.maximum(e - basel, 0.0), 0.0); paid[:, m] = w * bal * share; e = np.where(ok & (w > 0), basel, e); hwm = np.where(ok & (w > 0), basel, hwm)
            elif rule == "ftmo2step":
                prof = np.maximum(e - basel, 0.0); newp = np.maximum(prof - ro, 0.0); mine = ro + newp * share
                tgt = np.minimum(basel * (1 + kp) + np.maximum(e - basel * (1 + kp), 0) * (1 - pf), e); want = np.maximum(tgt - basel, 0.0)
                r = np.minimum(want, mine); trig = ok & (e > basel * (1 + kp))
                paid[:, m] = np.where(trig, mine - r, 0.0) * bal; e = np.where(trig, basel + r, e); hwm = np.where(trig, e, hwm); ro = np.where(trig, r, ro)
            else: w = np.where(ok, np.maximum(e - basel * (1 + kp), 0.0) * pf, 0.0); paid[:, m] = w * bal * share; e -= w
    has = (paid > 0).any(axis=1); first = np.where(has, np.argmax(paid > 0, axis=1), -1); fm = first[has]; fa = paid[has, fm]
    cum12 = np.array([paid[i, first[i]:first[i] + 12].sum() for i in np.where(has)[0]]); fits = fm <= MONTHS - 12
    q = lambda x, p: float(np.quantile(x, p)) if len(x) else float("nan")
    def ym(m): return (start + pd.Timedelta(days=int(round((m + 1) * 21 * 365 / 250)))).strftime("%Y-%m")
    fd = fund_day[funded & (fund_day >= 0)]
    return dict(p_pay=float(has.mean()), p_fail=float(failed.mean()), p_reach=float(funded.mean()), reach_med=(ym(q(fd, .5) / 21 - 1) if (not fn and len(fd)) else ""),
                t_med_m=q(fm, .5) + 1, t_lo_m=q(fm, .023) + 1, t_hi_m=q(fm, .977) + 1, t_med=ym(q(fm, .5)), t_lo=ym(q(fm, .023)), t_hi=ym(q(fm, .977)),
                a_med=q(fa, .5), a_lo=q(fa, .023), a_hi=q(fa, .977), c12_med=q(cum12[fits], .5), c12_lo=q(cum12[fits], .023), c12_hi=q(cum12[fits], .977),
                c30_mean=float(paid.sum(axis=1).mean()), c30_p0=float((paid.sum(axis=1) <= 0).mean()), horizon_m=MONTHS)
gen = dict(generated_utc=dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), digest_utc=digest.get("ingested_utc", ""), sim_start=str(start.date()), N=N, seed=SEED, horizon_m=MONTHS)
def actual_monthly(aid, latest_balance):
    """実口座の実績月利: ops_inbox/<口座>/positions.csv(決済済み・損益+手数料+スワップ)を決済月で集計し、最新残高から月末残高を逆算(入出金なしの前提)。"""
    p = os.path.join("ops_inbox", aid, "positions.csv")
    if not os.path.exists(p) or latest_balance is None: return []
    x = pd.read_csv(p, encoding="utf-8-sig"); x["ct"] = pd.to_datetime(x.close_time, format="%Y.%m.%d %H:%M:%S", errors="coerce"); x = x[x.ct.notna()]
    x["net"] = x.profit.fillna(0) + x.commission.fillna(0) + x.swap.fillna(0); grp = x.groupby(x.ct.dt.to_period("M"))
    months = sorted(grp.groups.keys()); out = []; bal_end = float(latest_balance)
    cur = pd.Timestamp.utcnow().to_period("M")
    for per in reversed(months):
        g = grp.get_group(per); net = float(g.net.sum()); n = int(len(g)); bal_start = bal_end - net
        out.append(dict(ym=str(per), year=per.year, month=per.month, net=round(net, 2), n=n, bal_start=round(bal_start, 2), bal_end=round(bal_end, 2), pct=(net / bal_start) if bal_start else None, mtd=bool(per == cur)))
        bal_end = bal_start
    return list(reversed(out))
rows_a, rows_m = [], []
for a in cfg["accounts"]:
    if not a.get("active", True): continue
    aid = acc_id(a["name"]); firm, label, ea = META.get(aid, ("", "", "")); d = dig.get(aid, {}); fn = a.get("funded_now", False)
    cur = d.get("currency", "JPY" if firm == "Fintokei" else "USD"); init = a["balance_jpy"] if cur == "JPY" else a["balance_jpy"] / FX
    sw = a.get("swap_xau_bps_m", 0.0); me = monthly(a["eval"], sw); mf = monthly(a["funded"], sw); stage = "funded" if fn else "eval"
    for ym_, ve, vf in zip(me.index, me.values, mf.values):
        rows_m.append(dict(account=aid, name=a["name"], kind="ledger", ym=ym_.strftime("%Y-%m"), year=int(ym_.year), month=int(ym_.month), ret_eval=round(float(ve), 5), ret_funded=round(float(vf), 5), ret_cur=round(float(vf if fn else ve), 5), ret_actual=None, net_actual=None, n_actual=None, mtd=False))
    eq = d.get("equity"); bl = d.get("balance")
    act = actual_monthly(aid, bl)
    for r_ in act:
        rows_m.append(dict(account=aid, name=a["name"], kind="actual", ym=r_["ym"], year=r_["year"], month=r_["month"], ret_eval=None, ret_funded=None, ret_cur=None, ret_actual=round(r_["pct"], 5) if r_["pct"] is not None else None, net_actual=r_["net"], n_actual=r_["n"], mtd=r_["mtd"]))
    act_cum = float(np.prod([1 + r_["pct"] for r_ in act if r_["pct"] is not None]) - 1) if act else None
    st_e, st_f = mstats(me), mstats(mf); st_c = st_f if fn else st_e; s = mc(a)
    rows_a.append(dict(account=aid, name=a["name"], firm=firm, label=label, ea=ea, rule=a.get("rule", "static"), rule_ja=RULE_JA[a.get("rule", "static")], stage=stage, stage_ja="資金化済" if fn else "評価中",
                       targets=" / ".join(f"{t*100:g}%" for t in a["targets"]) if a["targets"] else "", e0=a["e0"], spec_eval=spec_txt(a["eval"]), spec_funded=spec_txt(a["funded"]), spec_cur=spec_txt(a["funded"] if fn else a["eval"]),
                       k=a.get("k", k), keep=a.get("keep", keep), pay_frac=pf, mdd=a["mdd"], dll=a["dll"], swap_xau_bps_m=sw, balance_jpy=a["balance_jpy"], currency=cur, initial=round(init, 2),
                       balance=bl, equity=eq, pnl_pct=(eq / init - 1) if eq is not None else None, open_positions=d.get("open_positions"), snapshot_utc=d.get("snapshot_utc", ""), net_7d=d.get("net_7d"), net_30d=d.get("net_30d"),
                       net_30d_pct=(d.get("net_30d") / init) if d.get("net_30d") is not None else None, sl_hit_rate_30d=d.get("sl_hit_rate_30d"), closed_total=d.get("closed_total"),
                       **{f"h_{k_}": v for k_, v in st_c.items()}, **{f"he_{k_}": v for k_, v in st_e.items()}, **{f"hf_{k_}": v for k_, v in st_f.items()},
                       hist_from=me.index[0].strftime("%Y-%m"), hist_to=me.index[-1].strftime("%Y-%m"), generated_utc=gen["generated_utc"], digest_utc=gen["digest_utc"],
                       actual_from=act[0]["ym"] if act else "", actual_to=act[-1]["ym"] if act else "", actual_months=len(act), actual_cum=act_cum, actual_n=int(sum(r_["n"] for r_ in act)), **s))
os.makedirs("results", exist_ok=True)
json.dump(dict(rows=rows_a, **gen), open("results/account_cards_accounts.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
json.dump(dict(rows=rows_m, **gen), open("results/account_cards_monthly.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
df = pd.DataFrame(rows_a); pd.set_option("display.width", 250)
print(df[["name", "stage_ja", "currency", "equity", "pnl_pct", "net_30d_pct", "h_mean", "h_win", "h_worst", "h_mdd", "p_pay", "t_med", "a_med", "c12_med"]].round(3).to_string(index=False))
print(f"月次行 {len(rows_m)}・期間 {rows_m[0]['ym']}〜{rows_m[-1]['ym']}・生成 {gen['generated_utc']}")
