# -*- coding: utf-8 -*-
"""docs/401 Q159(診断・セル 0): FTMO 2-Step 本口座(50k ×2・Mon4 ×6・k=1.5・日次 4%・静的床 −10%)の Reward 請求方針を、FTMO 回答(docs/396 §7・E2:
請求 = 全利益を分配(80%)・一部不可・ロール可(ロール分は次回 100%)・床は元の額面基準・請求時に全建玉決済 → 新口座)の下で同じ MC で比較する。
方針: 請求せず / 月次ロール(現行 MC = 保持 20%・超過の半分)/ 月次ロール(超過全部)/ 四半期・半年・年 1 回の全額請求(ロール無し)/ 年 1 回 全額 + 低倍率。
感度: 請求後の空白日数(新口座発行まで Mon4 が止まる)0/2/5 営業日、ロール分の分配 100%(FAQ)/80%。
使い方: cd research && python3 -W ignore queue/q159_ftmo_2step_reward_policy.py → results/q159_ftmo_2step_reward_policy.csv"""
import os, sys, json
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, "forward"))
import portfolio_sim as ps
N, BLOCK, SEED = 6000, 5, 44
def paths(spec, days):
    r = ps.R(ps.book(spec)); rng = np.random.default_rng(SEED); nb = len(r) - BLOCK + 1
    stt = rng.integers(0, nb, size=(N, days // BLOCK + 1)); idx = (stt[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(N, -1)[:, :days]; return r[idx]
def sim(cf, mdd, dll, k, keep, pf, share, claim, every, days, gap=0, roll_share=1.0, scale=1.0):
    """claim: none(請求せず)/ rollall(全利益分配・MC と同じ残高まで取り分をロール・床は元額面)/ all(全額請求・ロール無し・額面に戻る)。
    gap: 請求後に新口座が発行されるまでの空白営業日(リターン 0)。roll_share: ロール済み分を次回受け取るときの分配(FAQ 1.0・保守 0.8)。"""
    e = np.ones(N); basel = np.ones(N); failed = np.zeros(N, bool); paid = np.zeros(N); ro = np.zeros(N); idle = np.zeros(N, int); nclaim = np.zeros(N)
    for t in range(days):
        act = ~failed; fl = basel - mdd
        f = np.clip(1 + k * ((e - fl) - mdd) / mdd, 1.0, 1 + k)
        ret = np.clip(cf[:, t] * f * scale, -dll, None); ret = np.where(idle > 0, 0.0, ret); idle = np.maximum(idle - 1, 0)
        e = np.where(act, e * (1 + ret), e); failed |= act & (e <= fl)
        if claim != "none" and (t + 1) % every == 0 and t + 1 < days + 1:
            ok = act & ~failed
            if claim == "all":
                w = np.where(ok, np.maximum(e - basel, 0.0), 0.0); trig = ok & (w > 0)
                paid += w * share; e = np.where(trig, basel, e); idle = np.where(trig, gap, idle); nclaim += trig
            else:
                prof = np.maximum(e - basel, 0.0); newp = np.maximum(prof - ro, 0.0); mine = ro * roll_share + newp * share
                tgt = np.minimum(basel * (1 + keep) + np.maximum(e - basel * (1 + keep), 0) * (1 - pf), e); want = np.maximum(tgt - basel, 0.0)
                r = np.minimum(want, mine); trig = ok & (e > basel * (1 + keep))
                paid += np.where(trig, mine - r, 0.0); e = np.where(trig, basel + r, e); ro = np.where(trig, r, ro); idle = np.where(trig, gap, idle); nclaim += trig
    alive = ~failed; resid = np.where(alive, np.maximum(e - basel, 0.0), 0.0); resid_mine = np.where(alive, np.maximum(resid - ro, 0) * share + np.minimum(resid, ro) * roll_share, 0.0)
    yrs = days / 250
    return dict(fail=failed.mean() * 100, paid_mean=paid.mean() * 100 / yrs, paid_med=np.median(paid) * 100 / yrs, paid_p16=np.quantile(paid, .16) * 100 / yrs, zero=(paid <= 0).mean() * 100,
                resid_mine=resid_mine.mean() * 100, total_mean=(paid + resid_mine).mean() * 100 / yrs, claims=nclaim.mean(), buf_end=np.where(alive, e - basel, np.nan))
def main():
    cfg = json.load(open(os.path.join(ROOT, "config", "portfolio_current.json"), encoding="utf-8")); A = {a["name"]: a for a in cfg["accounts"]}
    a = A["FTMO 50k 521100397"]; g = cfg["global"]; keep, pf = g["keep"], g["pay_frac"]; rows = []
    POL = [("P0 請求せず(緩衝を積む)", dict(claim="none", every=21)),
           ("P1 月次ロール・保持20%・超過の半分(現行 MC・E2)", dict(claim="rollall", every=21)),
           ("P2 月次ロール・保持20%・超過全部(pf 1.0)", dict(claim="rollall", every=21, pf=1.0)),
           ("P3 月次 全額請求(ロール無し・E4)", dict(claim="all", every=21)),
           ("P4 四半期 全額請求(63 営業日)", dict(claim="all", every=63)),
           ("P5 半年 全額請求(125 営業日)", dict(claim="all", every=125)),
           ("P6 年 1 回 全額請求(250 営業日)", dict(claim="all", every=250)),
           ("P7 年 1 回 全額 + 低倍率 ×0.55(Mon4 ×3.3 相当)", dict(claim="all", every=250, scale=0.55)),
           ("P8 半年 全額 + 低倍率 ×0.55", dict(claim="all", every=125, scale=0.55))]
    for days in (250, 500):
        cf = paths(a["funded"], days)
        for lab, kw in POL:
            kw = dict(kw); p = kw.pop("pf", pf)
            for gap in (0, 2, 5):
                if gap and kw["claim"] == "none": continue
                for rs in ((1.0, 0.8) if kw["claim"] == "rollall" and gap == 0 else (1.0,)):
                    r = sim(cf, a["mdd"], a["dll"], a["k"], keep, p, 0.8, days=days, gap=gap, roll_share=rs, **kw); be = r.pop("buf_end")
                    rows.append(dict(horizon_years=days / 250, policy=lab, gap_bd=gap, roll_share=rs, **{k2: round(float(v), 2) for k2, v in r.items()},
                                     buf_end_med=round(float(np.nanmedian(be)) * 100, 1), buf_end_p16=round(float(np.nanquantile(be, .16)) * 100, 1)))
    df = pd.DataFrame(rows); out = os.path.join(ROOT, "results", "q159_ftmo_2step_reward_policy.csv"); df.to_csv(out, index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 48); pd.set_option("display.max_rows", 200); print(df.to_string(index=False)); print("→", out)
if __name__ == "__main__": main()
