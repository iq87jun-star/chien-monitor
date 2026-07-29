# -*- coding: utf-8 -*-
"""
ftmo_compliant_portfolio.py — FTMO規約準拠の最適ポートフォリオ設計＋定量比較。

FTMO禁止事項の核(本構成に効くもの):
  ・同一/高相関銘柄での反対ポジション同時保有(ヘッジ)禁止。
  → P★(v7+v4+E5+E-Mon)の衝突点: (1)v7 LONG円 × v4 SHORT同じ円クロス, (2)E-Mon LONG指数 × E5 SHORT同じ指数。
  対策=「同一銘柄で反対側を持たない」よう銘柄を分離した準拠レッグに作り替える:
    v7   : 円3クロス 月曜LONG(不変・LONGのみ=衝突なし)
    v4c  : v4(k≥4合議)を【円を除く6メジャー】に限定 → v7と同一銘柄衝突なし
    E-Mon: 指数3つ 月曜LONG(不変・LONGのみ)
    E5c  : 多資産TSMOMを【金/銀/WTI/JP225/UK100】に限定(E-Monの米独指数を除外) → E-Monと同一銘柄衝突なし
各レッグを再構築し、相関・準拠ポートのSharpe/Calmar、P★との差を出す。
規律: 数字は盛らない。Yahoo近似=Drive+デモで確定。ニュース2分制限はEA側フィルタ/Swing口座で対応(別途)。"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parallel_vs_existing_compare import (load_daily, v7_monthly, emon_monthly, to_monthly,
                                          metrics, z, pip_size as pip, rsi_wilder, atr_daily)

HERE = os.path.dirname(os.path.abspath(__file__))


def v4_subset(pairs):
    """v4(D1 k≥4合議・逆張り)を指定ペア集合で。月次合算。"""
    monthly = {}
    for p in pairs:
        path = os.path.join(HERE, "data", f"{p}_d.csv")
        if not os.path.exists(path):
            continue
        df = load_daily(p)
        o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
        idx = df.index; n = len(c); rsi = rsi_wilder(c, 14); atr = atr_daily(h, l, c, 14)
        bb = 20; cost = 2 * pip(p); i = bb + 2
        while i < n - 1:
            win = c[i - bb:i]; mean = win.mean(); sd = win.std(ddof=1); zz = (c[i] - mean) / sd if sd > 0 else 0.0
            down = 0
            for k in range(12):
                if i - k - 1 >= 0 and c[i - k] < c[i - k - 1]: down += 1
                else: break
            up = 0
            for k in range(12):
                if i - k - 1 >= 0 and c[i - k] > c[i - k - 1]: up += 1
                else: break
            ret = (c[i] - c[i - 1]) / c[i - 1] if c[i - 1] else 0.0; mv = 0.005
            buy = int(rsi[i] < 35) + int(zz < -1.5) + int(down >= 3) + int(ret < -mv)
            sell = int(rsi[i] > 65) + int(zz > 1.5) + int(up >= 3) + int(ret > mv)
            sig = 1 if (buy >= 4 and buy > sell) else (-1 if (sell >= 4 and sell > buy) else 0)
            if sig == 0: i += 1; continue
            entry = o[i + 1]; sld = 1.5 * atr[i]; tpd = 1.2 * sld
            if sld <= 0: i += 1; continue
            sl = entry - sig * sld; tp = entry + sig * tpd; ex = None; j = i + 1; held = 0
            while j < n and held < 8:
                if sig > 0:
                    if l[j] <= sl: ex = sl; break
                    if h[j] >= tp: ex = tp; break
                else:
                    if h[j] >= sl: ex = sl; break
                    if l[j] <= tp: ex = tp; break
                j += 1; held += 1
            if ex is None: ex = c[min(j, n - 1)]
            r = sig * (ex / entry - 1.0) - cost / entry
            mk = pd.Period(idx[min(j, n - 1)], freq="M"); monthly[mk] = monthly.get(mk, 0.0) + r
            i = max(i + 1, j)
    return pd.Series(monthly).sort_index()


def e5_custom(names, cost_bps=6.0):
    """多資産TSMOM(月次・多ルックバック多数決)を指定銘柄で。"""
    closes = {}
    for nm in names:
        df = load_daily(nm); s = df["close"]; s.index = pd.to_datetime(df.index)
        closes[nm] = s.resample("ME").last()
    px = pd.DataFrame(closes).dropna(); ret = px.pct_change()
    sig = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for lb in (1, 3, 6, 12): sig = sig.add(np.sign(px.pct_change(lb)), fill_value=0)
    out = ((np.sign(sig).shift(1) * ret).mean(axis=1) - cost_bps / 1e4).dropna()
    out.index = out.index.to_period("M"); return out


def main():
    NONYEN = ["EURUSD", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD"]
    E5C = ["XAUUSD", "XAGUSD", "WTI", "JP225", "UK100"]      # E-Monの米独指数を除外

    comp = {"v7": v7_monthly(), "v4c": v4_subset(NONYEN), "E-Mon": emon_monthly(), "E5c": e5_custom(E5C)}
    M = pd.DataFrame(comp).dropna()
    print("=" * 80)
    print("FTMO準拠レッグ 単体(10年・Yahoo近似):")
    for k, v in comp.items():
        m = metrics(v, 12 if k in ("v4c", "E5c") else 52 if False else 12)
        print(f"   {k:6s} Sharpe{m['sharpe']:>5} maxDD{m['maxDD']:>6}% Calmar{m['calmar']:>5} n={m['n']}")
    # 参考: 制限前(P★レッグ)
    from parallel_vs_existing_compare import v4_monthly, e5_monthly
    print("   --- 参考(非準拠P★レッグ) ---")
    for k, v in {"v4(full9)": v4_monthly(), "E5(full)": e5_monthly()}.items():
        m = metrics(v, 12); print(f"   {k:10s} Sharpe{m['sharpe']:>5} maxDD{m['maxDD']:>6}% Calmar{m['calmar']:>5}")

    print("\n相関行列(準拠レッグ):"); print(M.corr().round(2).to_string())

    # 準拠ポート: E5cはほぼ死亡(Calmar0.01)ゆえ核は v7+v4c+E-Mon。比率を振る。
    def port(w):
        s = sum(z(M[k]) * w[k] for k in w)
        return metrics(s.dropna(), 12)
    cands = {
        "★準拠最適 v4c:35 v7:30 EMon:35(E5c無)": {"v4c": .35, "v7": .30, "E-Mon": .35},
        "準拠 等加重3 v7:v4c:EMon 33:33:34":     {"v7": .33, "v4c": .33, "E-Mon": .34},
        "準拠 v4c厚め 45:30:25":                  {"v4c": .45, "v7": .30, "E-Mon": .25},
        "(参考)E5c入り 35:25:25:15":              {"v4c": .35, "v7": .25, "E-Mon": .25, "E5c": .15},
        "2口座: FX口座 v7+v4c(50:50)":            {"v7": .50, "v4c": .50},
        "2口座: 指数口座 E-Mon単独":              {"E-Mon": 1.0},
    }
    print("\n準拠ポートフォリオ候補(リスク加重・共通目標DD−6%で年率):")
    print(f"{'構成':40s}{'Sharpe':>8}{'Calmar':>8}{'年率@-6%':>9}")
    out = {}
    for nm, w in cands.items():
        m = port(w); out[nm] = m
        print(f"{nm:40s}{m['sharpe']:>8}{m['calmar']:>8}{m['ann6']:>8}%")

    # ===== Option 2: v7を捨て『フルv4(円含む両建て)+E-Mon』(衝突ゼロでv4本来の強さ温存) =====
    from parallel_vs_existing_compare import v4_monthly as v4f
    M2 = pd.DataFrame({"v4full": v4f(), "E-Mon": comp["E-Mon"], "v7": comp["v7"]}).dropna()
    def port2(w):
        s = sum(z(M2[k]) * w[k] for k in w); return metrics(s.dropna(), 12)
    print("\n【Option 2】v7を外し フルv4(ADOPT・円含む両建て)+E-Mon（FTMO衝突ゼロ・v4の強さ温存）:")
    cands2 = {
        "★Opt2 v4full:E-Mon 60:40": {"v4full": .60, "E-Mon": .40},
        "  Opt2 v4full:E-Mon 55:45": {"v4full": .55, "E-Mon": .45},
        "  Opt2 v4full:E-Mon 70:30": {"v4full": .70, "E-Mon": .30},
    }
    for nm, w in cands2.items():
        m = port2(w); out[nm] = m
        print(f"{nm:40s}{m['sharpe']:>8}{m['calmar']:>8}{m['ann6']:>8}%")
    print(f"  v4⇄E-Mon 相関 = {round(float(M2['v4full'].corr(M2['E-Mon'])),3)}")

    # P★(非準拠)基準
    from parallel_vs_existing_compare import v4_monthly as v4ff, e5_monthly as e5f
    v4f = v4ff
    MP = pd.DataFrame({"v7": comp["v7"], "v4": v4f(), "E5": e5f(), "E-Mon": comp["E-Mon"]}).dropna()
    sp = 0.35 * z(MP["v4"]) + 0.25 * z(MP["v7"]) + 0.25 * z(MP["E-Mon"]) + 0.15 * z(MP["E5"])
    mp = metrics(sp.dropna(), 12)
    print(f"\n(参考)非準拠 P★ v4:35/v7:25/E-Mon:25/E5:15 : Sharpe{mp['sharpe']} Calmar{mp['calmar']} 年率@-6%{mp['ann6']}%")
    out["_pstar_noncompliant"] = mp

    with open(os.path.join(HERE, "results", "ftmo_compliant_portfolio.json"), "w") as fp:
        json.dump(dict(legs={k: metrics(v, 12) for k, v in comp.items()}, corr=M.corr().round(3).to_dict(),
                       ports=out), fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/ftmo_compliant_portfolio.json")


if __name__ == "__main__":
    main()
