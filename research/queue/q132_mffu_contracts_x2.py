# -*- coding: utf-8 -*-
"""docs/322 §5m Q132(診断・セル 0): MFFU の枚数 ×1.0 / ×1.5 / ×2.0 を、日中ソフト停止($2,500・時間足で近似)を入れた経路 MC で比較する。
docs/336 §18・docs/349 §8a の MC は「週次損益を −$2,500 で打ち切る」近似で、枚数を増やすほど日中の停止に当たりやすい効果を無視していた。
ここでは月曜 13→20 UTC の時間足で、累積損失が −$2,500 に達した時点で当日終了(= その損失で確定)とする。使い方: cd research && python3 queue/q132_mffu_contracts_x2.py"""
import sys, os, datetime as dt
from q_common import *
PX = {"US500": 7860 * 5, "NAS100": 31110 * 2, "US30": 51930 * 0.5}; Q = {"US500": 5, "NAS100": 2, "US30": 5}
N = sum(PX[k] * Q[k] for k in PX); COST = 2.5e-4; STOP = 2500.0
H = {k: load(k)["open"] for k in PX}
days = sorted(set.intersection(*[set(H[k].index[(H[k].index.dayofweek == 0) & (H[k].index.hour == 13)].normalize()) for k in PX]))
days = [d for d in days if d >= pd.Timestamp("2018-01-01")]
def weekly(s):
    out = []
    for d in days:
        path = None
        for h in range(13, 21):
            t = d + pd.Timedelta(hours=h); v = 0.0; ok = True
            for k in PX:
                o13 = H[k].get(d + pd.Timedelta(hours=13)); oh = H[k].get(t)
                if o13 is None or oh is None or not np.isfinite(o13) or not np.isfinite(oh): ok = False; break
                v += PX[k] * Q[k] * s * (oh / o13 - 1.0)
            if not ok: path = None; break
            path = v
            if h > 13 and v <= -STOP: path = -STOP; break
        if path is None: continue
        out.append((d, path / (N * s) - COST))   # 名目(N×s)比の損益
    return pd.Series([x for _, x in out], index=pd.DatetimeIndex([d for d, _ in out]))
rng = np.random.default_rng(7)
def run(s, r, n=8000, mll=4500, dll=2500, buf=4600, pmin=4500, pcap=4500, npay=5, target=9000, start=dt.date(2026, 10, 19)):
    cut = (dt.date(2027, 5, 31) - start).days // 7; res = []
    for _ in range(n):
        b = hi = 0.0; floor = -mll; wk = 0; ok = None
        while wk < 104:
            wk += 1; b += max(rng.choice(r) * N * s, -dll)
            if b <= floor: ok = False; break
            hi = max(hi, b); floor = max(floor, min(hi - mll, 100.0))
            if b >= target: ok = True; break
        if not ok: res.append(("eval_fail", wk, None, 0.0)); continue
        ew = wk; b = hi = 0.0; floor = -mll; k = 0; wk = 0; locked = False; first = None; paid = 0.0
        while wk < 156 and k < npay:
            wk += 1; b += max(rng.choice(r) * N * s, -dll)
            if b <= floor: res.append(("sim_fail", ew + wk, first, paid)); break
            hi = max(hi, b)
            if not locked:
                floor = max(floor, hi - mll)
                if hi >= buf: locked = True; floor = 100.0
            if locked and b - buf >= pmin: p = min(b - buf, pcap); paid += p; b -= p; k += 1; first = first or ew + wk
        else: res.append(("live", ew + wk, first, paid))
    o = pd.DataFrame(res, columns=["res", "wk", "first", "paid"])
    # Live 1 年(残高 $12k 維持・超過分出金)
    lb = []; lp = []
    for _ in range(n // 2):
        b = hi = 0.0; floor = -mll; paid2 = 0.0; br = False
        for wk in range(52):
            b += max(rng.choice(r) * N * s, -dll)
            if b <= floor: br = True; break
            hi = max(hi, b); floor = min(max(floor, hi - mll), 0.0)
            if b > 12000: paid2 += b - 12000; b = 12000
        lb.append(br); lp.append(paid2)
    return dict(eval_pass=float((o.res != "eval_fail").mean()), live=float((o.res == "live").mean()), fail=float(o.res.str.endswith("fail").mean()),
                first_by_may=float((o["first"].fillna(10**6) <= cut).mean()), live_by_may=float(((o.res == "live") & (o.wk <= cut)).mean()),
                sim_net=float(o.paid.mean() * 0.8), live_breach_1y=float(np.mean(lb)), live_net_1y=float(np.mean(lp) * 0.8))
rows = []
for s in (1.0, 1.5, 2.0):
    r = weekly(s); stops = float((r * N * s <= -STOP + 1).mean())
    d = run(s, r.values)
    rows.append(dict(scale=s, contracts=f"{int(5*s)}/{int(2*s)}/{int(5*s)}", weeks=len(r), stop_rate=round(stops * 100, 1), wk_mean=round(float(r.mean() * N * s)), wk_sd=round(float(r.std() * N * s)), **{k: round(v, 3) for k, v in d.items()}))
    print(f"×{s}: 週 {len(r)} 停止率 {stops*100:.1f}% 週平均 ${r.mean()*N*s:,.0f} σ ${r.std()*N*s:,.0f} | 評価通過 {d['eval_pass']*100:.0f}% Live {d['live']*100:.0f}% 失格 {d['fail']*100:.0f}% | 5月末まで 初回出金 {d['first_by_may']*100:.0f}% Live {d['live_by_may']*100:.0f}% | sim 手取り ${d['sim_net']:,.0f} | Live 1 年 失格 {d['live_breach_1y']*100:.0f}% 手取り ${d['live_net_1y']:,.0f}")
pd.DataFrame(rows).to_csv("results/q132_mffu_contracts_x2.csv", index=False)
