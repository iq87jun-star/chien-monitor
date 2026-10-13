# -*- coding: utf-8 -*-
"""Q139(診断・セル 0): 先物プロップ他社比較。MFFU と同じボット(月曜 13→20 UTC・MES/MNQ/MYM 5/2/5 相当・名目比で口座サイズに比例)を、
各社の評価 → 資金化(sim)→ 出金規約に通した経路 MC。時間足(13〜20 UTC)の含み損益で 日中トレーリング・日次上限(即失格 / 当日停止)を判定する。
規約値は firms.json(Web 調査・docs/360)。使い方: cd research && python3 queue/q139_futures_prop_firms.py [firms.json]"""
import sys, os, json, datetime as dt
from q_common import *
PX = {"US500": 7860 * 5, "NAS100": 31110 * 2, "US30": 51930 * 0.5}; Q = {"US500": 5, "NAS100": 2, "US30": 5}
N150 = sum(PX[k] * Q[k] for k in PX); COST = 2.5e-4
H = {k: load(k)["open"] for k in PX}
days = sorted(set.intersection(*[set(H[k].index[(H[k].index.dayofweek == 0) & (H[k].index.hour == 13)].normalize()) for k in PX]))
days = [d for d in days if d >= pd.Timestamp("2018-01-01")]
P = []          # 週ごとの時間足 累積損益(名目比): [h14..h20]
for d in days:
    row = []; ok = True
    for h in range(14, 21):
        v = 0.0
        for k in PX:
            o13 = H[k].get(d + pd.Timedelta(hours=13)); oh = H[k].get(d + pd.Timedelta(hours=h))
            if o13 is None or oh is None or not np.isfinite(o13) or not np.isfinite(oh): ok = False; break
            v += PX[k] * Q[k] * (oh / o13 - 1.0)
        if not ok: break
        row.append(v / N150)
    if ok: row[-1] -= COST; P.append(row)
P = np.array(P)                      # (週, 7)
rng = np.random.default_rng(139)

def week(notional, dd, st):
    """1 週(月曜 1 日)を進める。dd: dict(type, amt, lock, daily, daily_hard)。st: dict(b, hi, floor, locked)。戻り: (日次損益, 失格?)"""
    path = P[rng.integers(len(P))] * notional
    b0 = st["b"]; dl = None if (dd.get("dll_until_lock") and st["locked"]) else dd.get("daily"); pnl = path[-1]
    for v in path:
        eq = b0 + v
        if dd["type"] == "intraday" and not st["locked"]:
            st["floor"] = max(st["floor"], eq - dd["amt"])
            if dd.get("lock") is not None and st["floor"] >= dd["lock"]: st["floor"] = dd["lock"]; st["locked"] = True
        if eq <= st["floor"]: return v, True
        if dl and v <= -dl:
            if dd.get("daily_hard"): return v, True
            pnl = -dl; break
    st["b"] = b0 + pnl
    if dd["type"] == "eod" and not st["locked"]:
        st["hi"] = max(st["hi"], st["b"]); st["floor"] = max(st["floor"], st["hi"] - dd["amt"])
        if dd.get("lock") is not None and st["floor"] >= dd["lock"]: st["floor"] = dd["lock"]; st["locked"] = True
    return pnl, st["b"] <= st["floor"]

def new_state(dd): return dict(b=0.0, hi=0.0, floor=-dd["amt"], locked=dd["type"] == "static")

def path(f, weeks=78):
    """1 口座の一生(最大 weeks 週)。戻り: dict(passed, failed_eval, failed_funded, live, paid_gross, fees, first_pay_wk, n_pay)"""
    notional = N150 * f["size"] / 150000 * f.get("scale", 1.0)
    fees = f["eval_price"]; wk = 0; months = 1
    # ---- 評価 ----
    E = f["eval"]; st = new_state(E); best = 0.0; days_traded = 0
    while True:
        wk += 1
        if wk > weeks: return dict(passed=False, failed=False, ffail=False, live=False, paid=0.0, fees=fees, first=None, npay=0)
        if E.get("max_weeks") and days_traded >= E["max_weeks"]:          # 期限切れ(Bulenox 30 日 ≈ 月曜 4 回)
            return dict(passed=False, failed=True, ffail=False, live=False, paid=0.0, fees=fees, first=None, npay=0)
        if f.get("eval_monthly") and wk > months * 4.33: months += 1; fees += f["eval_price"]
        pnl, br = week(notional, E, st); days_traded += 1; best = max(best, pnl)
        if br:
            if f.get("reset_on_fail"):                       # 失格 → リセット購入で再挑戦(月額型は月額に含む)
                fees += f.get("reset_price", 0.0); st = new_state(E); best = 0.0; days_traded = 0; continue
            return dict(passed=False, failed=True, ffail=False, live=False, paid=0.0, fees=fees, first=None, npay=0)
        prof = st["b"]
        if prof >= E["target"] and days_traded >= E.get("min_days", 1) and (not E.get("consistency") or best <= E["consistency"] * prof): break
    fees += f.get("activation", 0.0)
    # ---- 資金化(sim)----
    F = f["funded"]; st = new_state(F); paid = 0.0; npay = 0; first = None; cyc_best = 0.0; cyc_prof = 0.0; cyc_days = 0; win_days = 0; base = 0.0
    while wk < weeks:
        wk += 1
        pnl, br = week(notional, F, st); cyc_days += 1; cyc_prof += pnl; cyc_best = max(cyc_best, pnl)
        if pnl >= F.get("win_day", 0.0) and pnl > 0: win_days += 1
        if br: return dict(passed=True, failed=False, ffail=True, live=False, paid=paid, fees=fees, first=first, npay=npay)
        avail = st["b"] - F["buffer"]
        ok = (avail >= F["pmin"] and cyc_days >= F.get("cycle_days", 1) and win_days >= F.get("win_days", 0)
              and (not F.get("consistency") or (cyc_prof > 0 and cyc_best <= F["consistency"] * cyc_prof)))
        if ok:
            pmax = F["pmax_first"][npay] if F.get("pmax_first") and npay < len(F["pmax_first"]) else F.get("pmax", 1e9); p = min(avail * F.get("pfrac", 1.0), pmax)
            if p < F["pmin"]: continue
            paid += p; st["b"] -= p; npay += 1; first = first or wk
            cyc_best = cyc_prof = 0.0; cyc_days = 0; win_days = 0
            if F.get("lock_after_pay") is not None and not st["locked"]: st["floor"] = F["lock_after_pay"]; st["locked"] = True
            if F.get("npay_live") and npay >= F["npay_live"]: return dict(passed=True, failed=False, ffail=False, live=True, paid=paid, fees=fees, first=first, npay=npay)
    return dict(passed=True, failed=False, ffail=False, live=False, paid=paid, fees=fees, first=first, npay=npay)

def sim(f, n=6000, weeks=78):
    R = pd.DataFrame([path(f, weeks) for _ in range(n)])
    net = R.paid * f["split"] - R.fees
    return dict(firm=f["name"], price=f["eval_price"], eval_pass=R.passed.mean(), funded_fail=(R.ffail).mean(), live=R.live.mean(),
                pay_any=(R.npay > 0).mean(), first_med_wk=float(R["first"].dropna().median()) if R["first"].notna().any() else np.nan,
                fees=R.fees.mean(), payout_net=(R.paid * f["split"]).mean(), net=net.mean(), net_p16=net.quantile(.16), net_med=net.median(), net_p84=net.quantile(.84),
                roi=net.mean() / R.fees.mean())

if __name__ == "__main__":
    firms = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "queue/q139_firms.json", encoding="utf-8"))
    print(f"週 {len(P)}(2018〜)・名目 150K あたり ${N150:,.0f}・週平均 ${P[:, -1].mean() * N150:,.0f} σ ${P[:, -1].std() * N150:,.0f}")
    rows = [sim(f) for f in firms if f.get("enabled", True)]
    R = pd.DataFrame(rows); pd.set_option("display.width", 250)
    print(R.round(3).to_string(index=False)); R.to_csv("results/q139_futures_prop_firms.csv", index=False)
