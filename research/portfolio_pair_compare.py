# -*- coding: utf-8 -*-
"""
portfolio_pair_compare.py — 【比較】次の1枚: 「C/D系クラスタをもう1枚」vs「E候補(第2の軸)」。

ユーザー質問(2026-08-04)「比較できますか」への実装。docs/185で判明した手法相関
(C↔D .79 / E候補↔全手法 ≈0)を**保ったまま**の同時モンテカルロで、
2口座ペアの共同成績(両方資金化/共倒れ/合計EV)を比較する。

方法: 2手法の日次系列を共通カレンダーに0埋めで並べ、**同じ日付ブロック**(5日)を
両方に適用するブートストラップ(=クロス相関を保存)。各口座は自分の業者ルールで判定:
  FTMO 10/5(静的-10%・-4%クリップ)/ FN Stellar 8/5(同)
ペア:
  P1「クラスタ2枚」= C(6.0x FTMO) + D(5.52x FTMO)   ← 現行C/D購入の再現=対照群
  P2「クラスタ+軸」= C(6.0x FTMO) + E候補(0.8x FN)
サンプル: 直近12ヶ月(楽観)/全期間(悲観)。シード7・1万パス。
EV: FTMO=-402+資金化で+2,002 / FN=-300+資金化で+2,875(docs/181 §3.4・docs/184の前提)。
出力: results/portfolio_pair_compare.json → docs/186
⚠ 同時スタート・同一カレンダー前提(相関効果が最大に出るストレス設定)。
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_lowcorr_screen as lc
import recentfit_screen as base
import strategy_corr_matrix as scm

SEED, N_MC, BLOCK, MAX_DAYS = 7, 10000, 5, 250
MAX_DD, DAY_GUARD = 0.10, 0.04
W12_0 = base.W12_0

FIRM = dict(FTMO=dict(p1=0.10, p2=0.05, cost=401.99, payoff=2002.0),
            FN=dict(p1=0.08, p2=0.05, cost=299.99, payoff=2875.0))


def to_bdays(s):
    """週末(暗号)のリターンを翌営業日へ複利圧縮 — 全口座のホライズンを営業日換算で統一。
    和集合カレンダーだとFX側に無取引日が混入し250日ホライズンが実質短縮される歪みの補正。"""
    idx = pd.DatetimeIndex(s.index)
    shift = np.where(idx.dayofweek == 5, 2, np.where(idx.dayofweek == 6, 1, 0))
    bd = idx + pd.to_timedelta(shift, unit="D")
    return (1 + pd.Series(s.values, index=bd)).groupby(level=0).prod() - 1


def outcome_path(e, p1, p2):
    """1パスの片口座判定: 1=資金化 0=期限切れ -1=失格"""
    hit = np.where(e - 1 >= p1)[0]
    dq = np.where(e - 1 <= -MAX_DD)[0]
    if len(dq) and (not len(hit) or dq[0] < hit[0]):
        return -1
    if not len(hit) or hit[0] >= MAX_DAYS:
        return 0
    b2 = e[hit[0]]
    e2 = e[hit[0] + 1:] / b2
    hit2 = np.where(e2 - 1 >= p2)[0]
    dq2 = np.where(e2 - 1 <= -MAX_DD)[0]
    if len(dq2) and (not len(hit2) or dq2[0] < hit2[0]):
        return -1
    if len(hit2) and hit2[0] + hit[0] + 1 < MAX_DAYS * 2:
        return 1
    return 0


def joint_mc(sA, sB, multA, multB, firmA, firmB, t0=None):
    """同一日付ブロックを両系列に適用する共同ブートストラップ"""
    sA, sB = to_bdays(sA), to_bdays(sB)
    if t0 is not None:
        sA = sA[sA.index >= t0]; sB = sB[sB.index >= t0]
    idx = sorted(set(sA.index) | set(sB.index))
    A = np.clip(sA.reindex(idx).fillna(0.0).values * multA, -DAY_GUARD, None)
    B = np.clip(sB.reindex(idx).fillna(0.0).values * multB, -DAY_GUARD, None)
    rng = np.random.default_rng(SEED)
    nb = len(A) - BLOCK + 1
    starts = rng.integers(0, nb, size=(N_MC, MAX_DAYS // BLOCK + 2))
    sel = (starts[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(N_MC, -1)[:, :MAX_DAYS * 2]
    eqA = np.cumprod(1 + A[sel], axis=1)
    eqB = np.cumprod(1 + B[sel], axis=1)
    fa, fb = FIRM[firmA], FIRM[firmB]
    oA = np.array([outcome_path(eqA[i], fa["p1"], fa["p2"]) for i in range(N_MC)])
    oB = np.array([outcome_path(eqB[i], fb["p1"], fb["p2"]) for i in range(N_MC)])
    ev = (-fa["cost"] + (oA == 1) * fa["payoff"]) + (-fb["cost"] + (oB == 1) * fb["payoff"])
    both_dq = (oA == -1) & (oB == -1)
    return dict(
        fundedA=round(float((oA == 1).mean()) * 100, 1),
        fundedB=round(float((oB == 1).mean()) * 100, 1),
        both_funded=round(float(((oA == 1) & (oB == 1)).mean()) * 100, 1),
        at_least_one=round(float(((oA == 1) | (oB == 1)).mean()) * 100, 1),
        none_funded=round(float(((oA != 1) & (oB != 1)).mean()) * 100, 1),
        dqA=round(float((oA == -1).mean()) * 100, 1),
        dqB=round(float((oB == -1).mean()) * 100, 1),
        both_dq=round(float(both_dq.mean()) * 100, 1),
        ev_mean=round(float(ev.mean()), 0),
        ev_p10=round(float(np.percentile(ev, 10)), 0),
        ev_p50=round(float(np.percentile(ev, 50)), 0),
        p_total_loss=round(float((ev <= -(fa["cost"] + fb["cost"]) + 1e-9).mean()) * 100, 1))


def joint_day_stats(sA, sB, multA, multB, t0):
    sA, sB = to_bdays(sA), to_bdays(sB)
    a = sA[sA.index >= t0] * multA
    b = sB[sB.index >= t0] * multB
    idx = sorted(set(a.index) | set(b.index))
    tot = (a.reindex(idx).fillna(0.0) + b.reindex(idx).fillna(0.0)) / 2
    wd, wdd = base.worst_stats(tot)
    return dict(worst_joint_day=round(wd * 100, 2), worst_joint_mdd=round(wdd * 100, 2))


def main():
    for nm in base.YAHOO:
        try:
            base.fetch(nm)
        except Exception:
            pass
    acct, _ = scm.build_strategies()
    C, D, E = acct["C_FTMO6m"], acct["D_FTMO3m"], acct["E_TH1.0候補"]
    MULT = dict(C=6.0, D=5.52, E=0.8)

    pairs = {
        "P1_クラスタ2枚(C+D)": (C, D, MULT["C"], MULT["D"], "FTMO", "FTMO"),
        "P2_クラスタ+軸(C+E)": (C, E, MULT["C"], MULT["E"], "FTMO", "FN"),
    }
    out = dict(meta=dict(purpose="次の1枚の比較: クラスタ増し vs 第2の軸(相関保存の同時MC)",
                         seed=SEED, n_mc=N_MC,
                         firms=FIRM, mults=MULT,
                         note="同一日付ブロックを両口座に適用=クロス相関を保存。"
                              "同時スタート前提(相関効果最大のストレス設定)。",
                         inputs=base.sha256s()), pairs={})
    for tag, (sA, sB, mA, mB, fA, fB) in pairs.items():
        r = dict(
            sample_12m=joint_mc(sA, sB, mA, mB, fA, fB, t0=W12_0),
            sample_full=joint_mc(sA, sB, mA, mB, fA, fB),
            joint_day_12m=joint_day_stats(sA, sB, mA, mB, W12_0))
        out["pairs"][tag] = r
        print(f"== {tag}")
        for k, v in r.items():
            print("  ", k, v)

    path = os.path.join(HERE, "results", "portfolio_pair_compare.json")
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
