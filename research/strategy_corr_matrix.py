# -*- coding: utf-8 -*-
"""
strategy_corr_matrix.py — 【計測】手法(戦略)同士の相関マトリクス。

ユーザー質問(2026-08-04)「手法毎の相関性を測る事も可能でしょうか」への実装。
docs/184の主発見(効くのは銘柄相関でなく構成レベル相関)を全手法に一般化し、
配備中の手法・その構成セル・トラックE候補の全ペア相関を計測する。

対象:
  A. 口座レベル: v7/EMon/E5(FN Instant PD_noV4の3部)・A案近似(S1+S2+S3。S4/S5の
     RSI2スリーブは日足近似不能のため除外を明記)・B(Fintokei)・C/D(FTMO 50k)・
     E候補(docs/184 TH1.0構成)
  B. セルレベル: 配備中の個別レッグ(Mon GBPJPY/AUDJPY/USDJPY/GBPUSD・v4 USDJPY/NZDUSD/
     AUDUSD・Hold JP225)+E候補セル(Mon NZDJPY・Hold UK100・TSMOM ADA/LTC)

尺度(スパース系列対応):
  - 日次: 営業日ユニオンに0埋めしたデイリーP&L相関(同日共倒れ=DD連鎖のリスク尺度)
  - 月次: 月次複利リターン相関(低頻度手法同士の本来の分散尺度)
  窓: 全期間(2016..2026-07-29)と直近12ヶ月を併記。重複が薄いペアはNA。
出力: results/strategy_corr_matrix.json → docs/185
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_lowcorr_screen as lc
import recentfit_screen as base

W12_0, W_ALL1 = base.W12_0, base.W_ALL1


def thu_short_cell(nm):
    """A案S3近似: 木曜o2oショート(16UTC 6h保有の日足近似・コストはMonと同一)"""
    df = base.load_daily(nm)
    c = 2 * base.pip_size(nm) / df["open"]
    return base.clip((-df[df["weekday"] == 3]["o2o"] - c).dropna())


def mix(parts):
    idx = sorted(set().union(*[set(s.index) for s, _ in parts]))
    c = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for s, w in parts:
        c = c.add(s.reindex(c.index).fillna(0.0) * w, fill_value=0.0)
    return c


def build_strategies():
    mon = {nm: base.mon_cell(nm) for nm in
           ["GBPJPY", "AUDJPY", "USDJPY", "GBPUSD", "NZDJPY"]}
    v4 = {nm: base.v4_cell(nm) for nm in ["USDJPY", "NZDUSD", "AUDUSD"]}
    holdJP = base.hold_cell("JP225")
    holdUK = base.hold_cell("UK100")
    tsA = lc.crypto_cell("TSMOM", "ADAUSD")
    tsL = lc.crypto_cell("TSMOM", "LTCUSD")

    acct = {
        "v7_FNIn": sum(base.mon_cell(n) for n in ["EURJPY", "GBPJPY", "USDJPY"]) / 3,
        "EMon_FNIn": sum(base.mon_cell(n) for n in ["NAS100", "US500", "GER40"]) / 3,
        "E5_FNIn": base.e5_composite(),
        "A_RF5近似": mix([(mon["GBPUSD"], 1 / 3), (mon["GBPJPY"], 1 / 3),
                          (thu_short_cell("USDCHF"), 1 / 3)]),
        "B_Fintokei": mix([(mon["GBPJPY"], .374), (mon["AUDJPY"], .322), (v4["USDJPY"], .304)]),
        "C_FTMO6m": mix([(mon["GBPJPY"], .323), (mon["AUDJPY"], .269),
                         (v4["NZDUSD"], .207), (v4["AUDUSD"], .201)]),
        "D_FTMO3m": mix([(mon["USDJPY"], .374), (v4["NZDUSD"], .287),
                         (mon["GBPJPY"], .139), (v4["AUDUSD"], .200)]),
        "E_TH1.0候補": mix([(mon["NZDJPY"], .463), (holdUK, .38), (tsA, .067), (tsL, .09)]),
    }
    celllv = {
        "Mon_GBPJPY": mon["GBPJPY"], "Mon_AUDJPY": mon["AUDJPY"], "Mon_USDJPY": mon["USDJPY"],
        "Mon_GBPUSD": mon["GBPUSD"], "Mon_NZDJPY": mon["NZDJPY"],
        "v4_USDJPY": v4["USDJPY"], "v4_NZDUSD": v4["NZDUSD"], "v4_AUDUSD": v4["AUDUSD"],
        "Hold_JP225": holdJP, "Hold_UK100": holdUK,
        "TSMOM_ADA": tsA, "TSMOM_LTC": tsL,
    }
    return acct, celllv


def monthly(s):
    mk = pd.PeriodIndex(s.index, freq="M")
    return pd.Series({k: float((1 + s[mk == k]).prod() - 1) for k in mk.unique()}).sort_index()


def corr_table(series, mode, t0=None, min_n_daily=100, min_n_monthly=24):
    names = list(series)
    if mode == "daily":
        packed = {}
        for n in names:
            s = series[n]
            if t0 is not None:
                s = s[s.index >= t0]
            packed[n] = s[s.index <= W_ALL1]
        idx = sorted(set().union(*[set(s.index) for s in packed.values()]))
        df = pd.DataFrame({n: packed[n].reindex(idx).fillna(0.0) for n in names},
                          index=pd.DatetimeIndex(idx))
        min_n = min_n_daily if t0 is None else 40
    else:
        df = pd.DataFrame({n: monthly(series[n]) for n in names}).fillna(0.0)
        if t0 is not None:
            df = df[df.index >= pd.Period(t0, freq="M")]
        min_n = min_n_monthly if t0 is None else 10
    out = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            j = pd.concat([df[a], df[b]], axis=1).dropna()
            j = j[(j != 0).any(axis=1)]        # 両方ゼロの行(共に無活動)は除外
            if len(j) < min_n or j[a].std() == 0 or j[b].std() == 0:
                out[f"{a}|{b}"] = None
            else:
                out[f"{a}|{b}"] = round(float(j.corr().iloc[0, 1]), 3)
    return out


def worst_joint_days(series, k=5):
    """配備中口座レベル手法の等ウェイト合算の最悪日と、各手法の同日寄与"""
    idx = sorted(set().union(*[set(s.index) for s in series.values()]))
    df = pd.DataFrame({n: s.reindex(idx).fillna(0.0) for n, s in series.items()},
                      index=pd.DatetimeIndex(idx))
    df = df[df.index >= pd.Timestamp("2020-01-01")]
    tot = df.mean(axis=1)
    worst = tot.nsmallest(k)
    return [dict(date=str(d.date()), total=round(float(v) * 100, 2),
                 parts={n: round(float(df.loc[d, n]) * 100, 2) for n in df.columns
                        if abs(df.loc[d, n]) > 1e-6})
            for d, v in worst.items()]


def main():
    for nm in base.YAHOO:
        try:
            base.fetch(nm)
        except Exception as e:
            print(f"  {nm} ERR {e}")
    print("[1/3] 手法系列の構築")
    acct, celllv = build_strategies()

    print("[2/3] 相関マトリクス(日次0埋め/月次・全期間/12m)")
    out = dict(meta=dict(
        purpose="手法同士の相関計測(口座レベル+セルレベル)",
        note="日次=営業日ユニオン0埋めP&L相関(同日共倒れ尺度)・月次=月次複利相関(分散尺度)。"
             "両方ゼロの期間は除外。A案はS1+S2+S3の日足近似(S4/S5 RSI2は除外)。"
             "季節RG3はリポジトリ外のため未収録。",
        inputs=base.sha256s()))
    for tag, series in dict(account=acct, cell=celllv).items():
        out[tag] = dict(
            daily_full=corr_table(series, "daily"),
            daily_12m=corr_table(series, "daily", W12_0),
            monthly_full=corr_table(series, "monthly"),
            monthly_12m=corr_table(series, "monthly", "2025-08"))

    print("[3/3] 配備中手法の同日共倒れ(等ウェイト合算の最悪日Top5・2020以降)")
    deployed = {k: v for k, v in acct.items() if k != "E_TH1.0候補"}
    out["worst_joint_days_deployed"] = worst_joint_days(deployed)
    for r in out["worst_joint_days_deployed"]:
        print(" ", r["date"], r["total"], r["parts"])

    path = os.path.join(HERE, "results", "strategy_corr_matrix.json")
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)

    # 表示用マトリクス(docs転記用)
    for tag, series in dict(account=acct, cell=celllv).items():
        names = list(series)
        for mode in ["monthly_full", "daily_12m"]:
            print(f"\n== {tag} {mode} ==")
            print("      " + " ".join(f"{n[:9]:>10s}" for n in names))
            tab = out[tag][mode]
            for a in names:
                row = []
                for b in names:
                    if a == b:
                        row.append("     —")
                    else:
                        key = f"{a}|{b}" if f"{a}|{b}" in tab else f"{b}|{a}"
                        v = tab.get(key)
                        row.append(f"{v:10.2f}" if v is not None else "        NA")
                print(f"{a[:9]:9s} " + " ".join(row))


if __name__ == "__main__":
    main()
