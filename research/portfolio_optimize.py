# -*- coding: utf-8 -*-
"""
portfolio_optimize.py — 既存P0(v7:v4:E5=40:40:20)より良い構成を最適化探索＋過剰最適化検証。

5エッジ(v7/v4/E5/E-Mon/CRYPTO)の月次リターンを再構築し、リスク加重(等ボラ標準化×比率)で合成。
ランダム探索(Dirichlet)で max-Sharpe / max-Calmar の重みを求め、リスクパリティ(等加重)と比較。
★過剰最適化の検証: IS(前半70%)で重みを決め、OOS(後半30%)で固定適用して P0 を上回るか確認。
規律: 数字は盛らない。in-sample最適は楽観。採否はOOSロバスト性で判断。絶対値はDrive+デモで確定。"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parallel_vs_existing_compare import (v7_monthly, v4_monthly, e5_monthly, emon_monthly, metrics)
from portfolio_patterns import crypto_monthly

HERE = os.path.dirname(os.path.abspath(__file__))
RNG = np.random.default_rng(20260608)


def aligned(names):
    comp = {"v7": v7_monthly(), "v4": v4_monthly(), "E5": e5_monthly(),
            "E-Mon": emon_monthly(), "CRYPTO": crypto_monthly()}
    M = pd.DataFrame({k: comp[k] for k in names}).dropna()
    return M


def znorm(M, target=0.01):
    """各列を月次ボラ=target に標準化(リスク加重の土台)。"""
    return M / M.std() * target


def port_metrics(Z, w):
    s = (Z * w).sum(axis=1)
    eq = (1 + s).cumprod(); dd = float(((eq - eq.cummax()) / eq.cummax()).min()) * 100
    mu = s.mean() * 12; vol = s.std() * np.sqrt(12); shp = mu / vol if vol > 0 else 0
    cagr = (eq.iloc[-1] ** (12 / len(s)) - 1) * 100 if eq.iloc[-1] > 0 else -100
    cal = cagr / abs(dd) if dd else 0
    return dict(sharpe=round(float(shp), 3), maxDD=round(dd, 1), calmar=round(float(cal), 2),
                ann6=round(6.0 * float(cal), 1))


def search(Z, n=60000, cap=None):
    """Dirichletで重みをサンプリングし max-Sharpe/max-Calmar を探す。cap=各重み上限(分散強制)。"""
    k = Z.shape[1]; best_s = (-9, None); best_c = (-9, None)
    for _ in range(n):
        w = RNG.dirichlet(np.ones(k))
        if cap is not None and w.max() > cap:
            continue
        m = port_metrics(Z, w)
        if m["sharpe"] > best_s[0]: best_s = (m["sharpe"], w)
        if m["calmar"] > best_c[0]: best_c = (m["calmar"], w)
    return best_s, best_c


def wdict(names, w):
    return {n: round(float(x), 2) for n, x in zip(names, w)}


def main():
    out = {}
    # P0 既存(v7:v4:E5=40:40:20) を基準系列で
    base_names = ["v7", "v4", "E5"]
    Mb = aligned(base_names); Zb = znorm(Mb)
    p0 = port_metrics(Zb, np.array([.40, .40, .20]))
    print("基準 P0 (v7:v4:E5=40:40:20):", p0)

    for tag, names in [("no_crypto", ["v7", "v4", "E5", "E-Mon"]),
                       ("with_crypto", ["v7", "v4", "E5", "E-Mon", "CRYPTO"])]:
        M = aligned(names); Z = znorm(M)
        # P0を同じ共通期間で再評価(公平比較のため)
        Mb2 = M[base_names]; Zb2 = znorm(Mb2); p0c = port_metrics(Zb2, np.array([.40, .40, .20]))
        # 全期間 最適
        bs, bc = search(Z, cap=0.45)
        # リスクパリティ(等加重)
        rp = port_metrics(Z, np.ones(len(names)) / len(names))
        # ★IS/OOS: IS(前半70%)で重み決定→OOS(後半30%)固定適用
        cut = int(len(M) * 0.7)
        Zis, Zoos = Z.iloc[:cut], Z.iloc[cut:]
        bs_is, bc_is = search(Zis, n=40000, cap=0.45)
        oos_opt_sharpe = port_metrics(Zoos, bs_is[1])      # ISで選んだmaxSharpe重みをOOSで
        oos_opt_calmar = port_metrics(Zoos, bc_is[1])
        # OOSでのP0 と 等加重
        Zb_oos = znorm(M[base_names]).iloc[cut:]
        oos_p0 = port_metrics(Zb_oos, np.array([.40, .40, .20]))
        oos_rp = port_metrics(Zoos, np.ones(len(names)) / len(names))

        print("\n" + "=" * 78)
        print(f"[{tag}] ユニバース={names}  共通月数={len(M)}")
        print(f"  P0(同期間)        : {p0c}")
        print(f"  max-Sharpe(全期間) : {bs[0]}  w={wdict(names,bs[1])} -> {port_metrics(Z,bs[1])}")
        print(f"  max-Calmar(全期間) : w={wdict(names,bc[1])} -> {port_metrics(Z,bc[1])}")
        print(f"  リスクパリティ等加重: {rp}  w={wdict(names,np.ones(len(names))/len(names))}")
        print(f"  --- 過剰最適化チェック(IS→OOS固定適用) ---")
        print(f"  ISで選んだmaxSharpe重み w={wdict(names,bs_is[1])}")
        print(f"    OOS適用: {oos_opt_sharpe}  (OOSのP0={oos_p0} / OOS等加重={oos_rp})")
        print(f"  ISで選んだmaxCalmar重み w={wdict(names,bc_is[1])}")
        print(f"    OOS適用: {oos_opt_calmar}")
        out[tag] = dict(names=names, months=len(M), P0=p0c,
                        max_sharpe=dict(w=wdict(names, bs[1]), m=port_metrics(Z, bs[1])),
                        max_calmar=dict(w=wdict(names, bc[1]), m=port_metrics(Z, bc[1])),
                        risk_parity=dict(w=wdict(names, np.ones(len(names)) / len(names)), m=rp),
                        oos=dict(p0=oos_p0, rp=oos_rp,
                                 opt_sharpe_w=wdict(names, bs_is[1]), opt_sharpe_oos=oos_opt_sharpe,
                                 opt_calmar_w=wdict(names, bc_is[1]), opt_calmar_oos=oos_opt_calmar))

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "portfolio_optimize.json"), "w") as fp:
        json.dump(dict(P0=p0, universes=out), fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/portfolio_optimize.json")


if __name__ == "__main__":
    main()
