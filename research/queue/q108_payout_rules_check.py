# -*- coding: utf-8 -*-
"""docs/396 Q108: 資金化後の出金・残高扱い — 各社の現行規約(2026-11-04 取得)と MC(portfolio_sim)の前提の差を数値で見る参考計算(セル 0・診断)。
(a) FTMO 1-Step 資金化後: MC の静的床 vs 規約の EOD トレーリング床(最高残高 −10%、出金で新口座 = 額面・床 −10% に全リセット、分配 90%、ロール不可)。
(b) FTMO 2-Step 資金化後: MC の「超過分の半分を出金・残りは緩衝」vs 規約の「Reward 請求で全利益を分配(80%)・次口座へロールオーバー」。
    ロール後の床が (E2) 元の額面 −10% のまま か (E3) 新残高 −10% か は FTMO 未公表 → 両方を置く。
使い方: cd research && python3 -W ignore queue/q108_payout_rules_check.py → results/q108_payout_rules_check.csv"""
import os, sys, json
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, "forward"))
import portfolio_sim as ps
N, DAYS, BLOCK, SEED = 6000, 250, 5, 44
def paths(spec):
    r = ps.R(ps.book(spec)); rng = np.random.default_rng(SEED); nb = len(r) - BLOCK + 1
    stt = rng.integers(0, nb, size=(N, DAYS // BLOCK + 1)); idx = (stt[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(N, -1)[:, :DAYS]; return r[idx]
def sim(cf, mdd, dll, k, keep, pf, share, floor="static", claim="partial", every=21, roll_floor="orig", scale=1.0):
    """floor: static(額面 −mdd 固定) / trail(max(EOD 最高残高, 額面) − mdd)。claim: partial(超過分 × pf を出金・残りは口座に) / all(全利益を分配・口座は額面に戻る)
    / rollall(全利益を分配し、MC と同じ残高になるよう取り分からロール。roll_floor=orig: 床は元額面 −mdd、new: 床は新額面 −mdd)。"""
    e = np.ones(N); basel = np.ones(N); hwm = np.ones(N); failed = np.zeros(N, bool); paid = np.zeros(N); orig = np.ones(N); ro = np.zeros(N)   # ro = ロール済み(分配後・次回は 100%)
    for t in range(DAYS):
        act = ~failed
        fl = (np.maximum(hwm, basel) - mdd * orig) if floor == "trail" else (basel - mdd * orig)
        f = np.clip(1 + k * ((e - fl) / orig - mdd) / mdd, 1.0, 1 + k)
        ret = np.clip(cf[:, t] * f * scale, -dll, None); e = np.where(act, e * (1 + ret), e); hwm = np.maximum(hwm, e); failed |= act & (e <= fl)
        if (t + 1) % every == 0:
            ok = act & ~failed
            if claim == "partial":
                w = np.where(ok, np.maximum(e - basel * (1 + keep), 0.0) * pf, 0.0); paid += w * share; e -= w
            elif claim == "all":          # FTMO 1-Step: Reward で全利益 → 新口座(額面)・床リセット
                w = np.where(ok, np.maximum(e - basel, 0.0), 0.0); paid += w * share; e = np.where(ok & (w > 0), basel, e); hwm = np.where(ok & (w > 0), basel, hwm)
            else:                          # rollall: 全利益を分配。MC と同じ残高(basel×(1+keep) + 超過×(1−pf))になるまで取り分をロール
                prof = np.maximum(e - basel, 0.0); newp = np.maximum(prof - ro, 0.0); mine = ro + newp * share   # ロール済み分は 100%・新規利益は分配
                tgt = np.minimum(basel * (1 + keep) + np.maximum(e - basel * (1 + keep), 0) * (1 - pf), e); want = np.maximum(tgt - basel, 0.0)
                r = np.minimum(want, mine); trig = ok & (e > basel * (1 + keep))
                paid += np.where(trig, mine - r, 0.0); e = np.where(trig, basel + r, e); hwm = np.where(trig, e, hwm); ro = np.where(trig, r, ro)
                if roll_floor == "new": orig = np.where(trig, e, orig); basel = np.where(trig, e, basel); ro = np.where(trig, 0.0, ro)   # 新額面 = ロール後残高
    return dict(fail=failed.mean() * 100, paid_mean=paid.mean() * 100, paid_med=np.median(paid) * 100, paid_p16=np.quantile(paid, .16) * 100, zero=(paid <= 0).mean() * 100)
def main():
    cfg = json.load(open(os.path.join(ROOT, "config", "portfolio_current.json"), encoding="utf-8")); A = {a["name"]: a for a in cfg["accounts"]}
    rows = []
    a = A["1-Step 531466484"]; cf = paths(a["funded"])
    for lab, kw in [("A: MC 現行(静的床・保持20%・半分・分配80%)", dict(floor="static", claim="partial", share=0.8)),
                    ("A': MC 現行の分配のみ 90%", dict(floor="static", claim="partial", share=0.9)),
                    ("B: 規約床(EOD トレーリング)・保持20%・半分・90%", dict(floor="trail", claim="partial", share=0.9)),
                    ("C: 規約床・21営業日ごと全額 Reward(新口座リセット)・90%", dict(floor="trail", claim="all", every=21, share=0.9)),
                    ("D: 規約床・10営業日ごと全額 Reward・90%", dict(floor="trail", claim="all", every=10, share=0.9)),
                    ("E: 規約床・63営業日ごと全額 Reward・90%", dict(floor="trail", claim="all", every=63, share=0.9)),
                    ("C×0.5: 規約床・倍率半分(×1.56/1.0)・21営業日ごと全額・90%", dict(floor="trail", claim="all", every=21, share=0.9, scale=0.5)),
                    ("C×0.33: 規約床・倍率 1/3(×1.04/0.68)・21営業日ごと全額・90%", dict(floor="trail", claim="all", every=21, share=0.9, scale=1/3)),
                    ("C×0.25: 規約床・倍率 1/4(×0.78/0.51)・21営業日ごと全額・90%", dict(floor="trail", claim="all", every=21, share=0.9, scale=0.25))]:
        rows.append(dict(account="FTMO 1-Step 531466484(資金化後 ×3.125/2.03・k=2)", variant=lab, **sim(cf, a["mdd"], a["dll"], a["k"], 0.2, 0.5, **kw)))
    a = A["FTMO 50k 521100397"]; cf = paths(a["funded"])
    for lab, kw in [("E1: MC 現行(超過分の半分を出金・残りは口座)", dict(claim="partial")),
                    ("E2: FTMO 規約(全利益分配 → 取り分をロール)・床は元額面 −10% のまま", dict(claim="rollall", roll_floor="orig")),
                    ("E3: 同上・床は新額面(ロール後残高)−10%", dict(claim="rollall", roll_floor="new")),
                    ("E4: 全額出金(ロール無し)・毎月", dict(claim="all", every=21))]:
        rows.append(dict(account="FTMO 50k 2-Step(資金化済・Mon4 ×6・k=1.5)", variant=lab, **sim(cf, a["mdd"], a["dll"], a["k"], 0.2, 0.5, 0.8, floor="static", **kw)))
    df = pd.DataFrame(rows); out = os.path.join(ROOT, "results", "q108_payout_rules_check.csv"); df.to_csv(out, index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 70); print(df.round(2).to_string(index=False)); print("→", out)
if __name__ == "__main__": main()
