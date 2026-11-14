# -*- coding: utf-8 -*-
"""docs/322 Q87: 帳簿リスク寄与の自動計算(docs/318 §3・§8a の手作業を置き換える)。毎月 1 日に運用ダイジェストから実行。
入力: research/config/portfolio_current.json(口座ごとの額面・レグ・倍率 = docs/349 の現行設定)と research/ops_inbox/<口座>/open_positions.csv(建玉)。
出力: 族別(Mon / その他 / Roll / Hold)のリスク寄与 2 法 —
  (R) 共分散法: 全口座合計の日次損益(円)に対する族の限界寄与 cov(F_f, total)/var(total)(合計 100%)。
  (V) 単位 vol 法(docs/318 §8a): σ_f × 額面 × 重み × 倍率 の按分。
目標(docs/322 Q87): Mon 40–50 / その他 15–20 / Hold ≤15、Roll は名目上限(swap-free 口座 ×3)で見る。乖離 ±10pt 超を「改正案」行に。
使い方: cd research && python3 forward/book_mix.py [--phase eval|funded|both] [--csv results/book_mix_YYYY-MM-DD.csv]
制限: GER40 ブレイク(EA8 / EA10L)はレグ DB に無いので含まない(その他が実際より小さい)。"""
import os, sys, json, argparse, datetime as dt, glob
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE); os.chdir(ROOT)
import portfolio_sim as ps
FAMS = ["Mon", "その他", "Roll", "Hold"]; TARGET = {"Mon": (40, 50), "その他": (15, 20), "Hold": (0, 15)}
def fam_legs():
    """spec キー → [(族, 系列)]。portfolio_sim.legs() と同じ定義を族に分解。"""
    L = ps.L; base = ps.base
    mon4 = ps.legs()["mon4"]; nas = ps.on_cal(base.mon_cell("NAS100")); spx = ps.on_cal(base.mon_cell("US500")); holdxau = ps.legs()["holdxau"]; roll = ps.legs()["roll"]
    return dict(mon4=[("Mon", mon4)], bplan=[("Mon", L("Mon", "GBPJPY") * 0.374 + L("Mon", "AUDJPY") * 0.322), ("その他", L("v4", "USDJPY") * 0.304)], idx=[("その他", nas + spx)],
                holdxau=[("Hold", holdxau)], roll=[("Roll", roll)], hold_uw=[("Hold", ps.legs()["hold_uw"])], btc=[("その他", ps.legs()["btc"])], mon3=[("Mon", ps.legs()["mon3"])],
                a9=[("Hold", holdxau / 3), ("Mon", L("Mon", "GBPJPY") / 3), ("その他", nas / 3)],
                instG=[("Mon", L("Mon", "GBPJPY") * 0.537 * 4 + L("Mon", "AUDJPY") * 0.463 * 4), ("その他", (nas + spx) * 0.125 * 4)])
def risk_mix(cfg, phase):
    FL = fam_legs(); rows = []; F = {f: 0.0 for f in FAMS}; V = {f: 0.0 for f in FAMS}; per = []
    for a in cfg["accounts"]:
        if not a.get("active", True): continue
        spec = a["funded"] if (phase == "funded" or a.get("funded_now")) else a["eval"]; bal = a["balance_jpy"]; acc = {f: 0.0 for f in FAMS}
        for k, w in spec.items():
            for fam, s in FL[k]:
                r = ps.R(s) * w * bal; acc[fam] = acc[fam] + r
        for f in FAMS:
            if np.ndim(acc[f]): F[f] = F[f] + acc[f]; V[f] += float(np.std(acc[f])); per.append(dict(account=a["name"], family=f, vol_jpy=float(np.std(acc[f]))))
        rows.append(dict(account=a["name"], roll_mult=spec.get("roll", 0.0), **{f: (float(np.std(acc[f])) if np.ndim(acc[f]) else 0.0) for f in FAMS}))
    total = sum(F[f] for f in FAMS if np.ndim(F[f])); var = float(np.var(total))
    rc = {f: (float(np.cov(F[f], total)[0, 1]) / var * 100 if np.ndim(F[f]) else 0.0) for f in FAMS}; vs = sum(V.values()); vm = {f: V[f] / vs * 100 for f in FAMS}
    return rc, vm, pd.DataFrame(rows), float(np.std(total))
def live_mix(inbox="ops_inbox"):
    out = []
    for p in sorted(glob.glob(os.path.join(inbox, "*", "open_positions.csv"))):
        acc = os.path.basename(os.path.dirname(p))
        try: d = pd.read_csv(p, encoding="utf-8-sig")
        except Exception: continue
        for _, r in d.iterrows():
            c = str(r.get("comment", "")); fam = "Mon" if c.startswith("RFMon") else "Roll" if c.startswith("RFRoll") else "Hold" if c.startswith("RFHold") else "その他"
            out.append(dict(account=acc, family=fam, symbol=r.get("symbol"), volume=r.get("volume"), profit=r.get("profit")))
    return pd.DataFrame(out)
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--phase", default="both"); ap.add_argument("--csv", default=None); ap.add_argument("--config", default="config/portfolio_current.json"); a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8")); today = dt.date.today().isoformat(); allrows = []; proposals = []
    for phase in (["eval", "funded"] if a.phase == "both" else [a.phase]):
        rc, vm, per, sd = risk_mix(cfg, phase); lab = "評価段階(現行)" if phase == "eval" else "資金化後"
        print(f"== {lab}: 族別リスク寄与 %(R 共分散法 / V 単位 vol 法)・全口座合計の日次 σ {sd/1e4:,.0f} 万円")
        for f in FAMS:
            tg = TARGET.get(f); flag = ""
            if tg: flag = "↑ 目標超" if rc[f] > tg[1] + 10 else "↓ 目標未満" if rc[f] < tg[0] - 10 else ("(目標内)" if tg[0] <= rc[f] <= tg[1] else "(±10pt 内)")
            print(f"  {f:4s} R {rc[f]:5.1f}  V {vm[f]:5.1f}  目標 {tg if tg else '名目上限 ×3'} {flag}")
            if tg and (rc[f] > tg[1] + 10 or rc[f] < tg[0] - 10): proposals.append(f"{lab}: {f} {rc[f]:.0f}%(目標 {tg[0]}–{tg[1]})")
            allrows.append(dict(date=today, phase=phase, family=f, rc_cov=round(rc[f], 1), rc_vol=round(vm[f], 1)))
        hi = per[per.roll_mult > 3.0]
        if len(hi): print("  Roll 名目 ×3 超: " + ", ".join(f"{r.account} ×{r.roll_mult}" for _, r in hi.iterrows()))
        print("  口座別 日次 σ(万円): " + "; ".join(f"{r.account}: " + "/".join(f"{r[f]/1e4:.0f}" for f in FAMS) for _, r in per.iterrows()))
    lv = live_mix()
    if len(lv):
        g = lv.groupby("family").agg(n=("symbol", "size"), pl=("profit", "sum")); print("== 建玉(ops_inbox・最終取り込み時点): " + "; ".join(f"{f}: {int(g.loc[f,'n'])} 本 P/L {g.loc[f,'pl']:,.0f}" for f in g.index))
    print("改正案: " + ("; ".join(proposals) if proposals else "なし(乖離 ±10pt 以内)"))
    if a.csv: pd.DataFrame(allrows).to_csv(a.csv, index=False); print("saved", a.csv)
if __name__ == "__main__": main()
