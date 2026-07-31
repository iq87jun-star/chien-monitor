# -*- coding: utf-8 -*-
"""
recentfit_mc.py — 直近フィット・ポートフォリオのチャレンジ通過モンテカルロ
==========================================================================
recentfit_sweep.json の採用5スリーブについて、直近12.8ヶ月(FIT+HOLDOUT:
2025-07-01..2026-07-24)のトレードを日次バケットに集約し、カレンダー・
ブートストラップ(営業日を復元抽出)で FundedNext Stellar 2-Step を模擬する。

規則(docs/01): P1 +8% / P2 +5% / 日次5%(当日開始equity) / 最大10%静的 /
最低5取引日 / 時間無制限。EAガード: 日次は −4% で全決済+当日停止(これが
日次分布を−4%近傍で打ち切る)、最大は −8% で恒久停止。

重要な正直系限界:
  - サンプルは「直近だけ伸びている」選定済み期間そのもの=楽観バイアス込み。
    ここで出る通過率は上限の目安であり、レジーム転換時は保証されない。
  - 日次打ち切りは−4%で近似(バケット合計が−4%を下回る日は−4%に丸め)。
出力: research/results/recentfit_mc.json
"""
import os, json, math, datetime as dt
import numpy as np
import recentfit_sweep as rs

HERE = os.path.dirname(os.path.abspath(__file__))
OUTP = os.path.join(HERE, "results", "recentfit_mc.json")
SWEEP = os.path.join(HERE, "results", "recentfit_sweep.json")

USE_A, USE_B = "2025-07-01", "2026-07-24"   # FIT+HOLDOUT 全体
P1_TARGET, P2_TARGET = 8.0, 5.0
DAILY_GUARD = 4.0      # EA日次ガード(%)
MAX_GUARD   = 8.0      # EA恒久停止(%) — 規則10%の手前
RULE_DAILY  = 5.0
RULE_MAX    = 10.0
MAX_DAYS    = 260      # 1年で未達なら「時間切れ」扱い(規則上は無期限)
N_PATH      = 20000
SEED        = 20260730

def build_daily_R():
    """採用スリーブごとの日次R系列(dict date->R)を実データから再構築。"""
    with open(SWEEP) as f: sweep=json.load(f)
    specs=[p["spec"] for p in sweep["picked"]]
    per_sleeve={}
    for pair in sorted({s["pair"] for s in specs}):
        atr_map, atr_dates = rs.atr_pct_daily(pair)
        fams = rs.family_A(pair, atr_map, atr_dates) + \
               rs.family_B(pair, atr_map, atr_dates) + \
               rs.family_C(pair, atr_map, atr_dates)
        for spec, trades in fams:
            if spec in specs:
                m={}
                for d,p,a in trades:
                    if USE_A <= d <= USE_B:
                        m[d]=m.get(d,0.0)+max(p/(rs.SL_ATR_MULT*a),-1.0)
                per_sleeve[json.dumps(spec,sort_keys=True)]=m
    assert len(per_sleeve)==len(specs), f"{len(per_sleeve)} != {len(specs)}"
    return specs, per_sleeve

def daily_buckets(per_sleeve, risk_pct):
    """全営業日(いずれかのスリーブが取引した日+無取引日)の口座%リターン配列。
       無取引日も0%として含める=時間経過を正しく模擬。"""
    all_days=set()
    for m in per_sleeve.values(): all_days.update(m.keys())
    d0=dt.date.fromisoformat(USE_A); d1=dt.date.fromisoformat(USE_B)
    cal=[]
    d=d0
    while d<=d1:
        if d.weekday()<5: cal.append(d.isoformat())
        d+=dt.timedelta(days=1)
    rets=[]
    for day in cal:
        r=sum(m.get(day,0.0) for m in per_sleeve.values())*risk_pct
        rets.append(max(r, -DAILY_GUARD))   # 日次ガードで打ち切り
    return np.array(rets)

def run_phase(rng, rets, target, start_bal=100.0):
    """1フェーズ模擬。返り値: (result, days) result in pass/fail_daily/fail_max/timeout"""
    eq=start_bal; peak_floor=start_bal*(1-RULE_MAX/100); traded=0
    for day in range(1, MAX_DAYS+1):
        r=rets[rng.integers(0,len(rets))]
        day_start=eq
        eq*=(1+r/100)
        if r!=0.0: traded+=1
        # 規則判定(ガード後の日次リターンでも規則線超えを確認)
        if day_start-eq >= day_start*RULE_DAILY/100: return ("fail_daily", day)
        if eq <= peak_floor: return ("fail_max", day)
        if eq <= start_bal*(1-MAX_GUARD/100): return ("guard_stop", day)
        if eq >= start_bal*(1+target/100) and traded>=5: return ("pass", day)
    return ("timeout", MAX_DAYS)

def simulate(rets, n=N_PATH, seed=SEED):
    rng=np.random.default_rng(seed)
    out={"p1":{"pass":0,"fail_daily":0,"fail_max":0,"guard_stop":0,"timeout":0},
         "both":0, "days_p1":[], "days_total":[]}
    for _ in range(n):
        r1,d1=run_phase(rng, rets, P1_TARGET)
        out["p1"][r1]+=1
        if r1=="pass":
            out["days_p1"].append(d1)
            r2,d2=run_phase(rng, rets, P2_TARGET)
            if r2=="pass":
                out["both"]+=1; out["days_total"].append(d1+d2)
    res={"p1_pass%":round(out["p1"]["pass"]/n*100,1),
         "both_pass%":round(out["both"]/n*100,1),
         "fail_daily%":round(out["p1"]["fail_daily"]/n*100,2),
         "fail_max%":round(out["p1"]["fail_max"]/n*100,2),
         "guard_stop%":round(out["p1"]["guard_stop"]/n*100,2),
         "timeout%":round(out["p1"]["timeout"]/n*100,2)}
    if out["days_p1"]:
        res["p1_days_median"]=int(np.median(out["days_p1"]))
    if out["days_total"]:
        res["both_days_median"]=int(np.median(out["days_total"]))
    return res

def main():
    specs, per_sleeve = build_daily_R()
    print("sleeves:", len(specs))
    sumR={k:round(sum(m.values()),2) for k,m in per_sleeve.items()}
    for k,v in sumR.items(): print(" ", v, "R ", k)

    grid={}
    for risk in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0):
        rets=daily_buckets(per_sleeve, risk)
        ann=(np.prod(1+rets/100)**(252/len(rets))-1)*100
        # 実現最大DD(履歴そのまま1回)
        eq=np.cumprod(1+rets/100); dd=(eq/np.maximum.accumulate(eq)-1).min()*100
        r=simulate(rets)
        r["hist_ann%"]=round(float(ann),1); r["hist_maxDD%"]=round(float(dd),1)
        grid[str(risk)]=r
        print(f"risk={risk}: {r}")

    # ストレス: エッジ半減/消滅(取引日の平均リターン分を差し引く)。
    # 問い=「レジームが終わった時、失格で口座を飛ばすか、時間切れ・小損で済むか」。
    stress={}
    for risk in (1.25, 2.0):
        base=daily_buckets(per_sleeve, risk)
        traded=base!=0.0
        mu=base[traded].mean() if traded.any() else 0.0
        for decay,name in ((0.5,"half_edge"),(1.0,"no_edge")):
            r2=base.copy(); r2[traded]-=decay*mu
            r2=np.maximum(r2, -DAILY_GUARD)
            s=simulate(r2)
            eqs=np.cumprod(1+r2/100)
            s["hist_ann%"]=round(float((eqs[-1]**(252/len(r2))-1)*100),1)
            s["hist_maxDD%"]=round(float((eqs/np.maximum.accumulate(eqs)-1).min()*100),1)
            stress[f"risk{risk}_{name}"]=s
            print(f"stress risk={risk} {name}: {s}")

    out={"meta":{"window":[USE_A,USE_B],"n_path":N_PATH,"seed":SEED,
                 "rules":{"p1":P1_TARGET,"p2":P2_TARGET,"daily":RULE_DAILY,"max":RULE_MAX},
                 "guards":{"daily":DAILY_GUARD,"max":MAX_GUARD},
                 "caveat":"選定期間そのものをリサンプルしており楽観バイアス込み。上限の目安。"},
         "sleeve_sumR_window":sumR, "grid":grid, "stress":stress}
    with open(OUTP,"w") as f: json.dump(out,f,ensure_ascii=False,indent=1)
    print("->", OUTP)

if __name__ == "__main__":
    main()
