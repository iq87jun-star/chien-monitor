# -*- coding: utf-8 -*-
"""
median3_rg3_target.py — 中央3ヶ月(median-3)の最良ポートフォリオを E-Mon raw vs RG3 で確定する。

背景: docs/68 で「E-Mon は RG3(非対称リスクオフ・ゲート)版を採用」と結論したが、その確定数値は
  中央4ヶ月(median-4)のみで、median3_target.json(単一口座 median-3)は raw E-Mon のままだった。
  本スクリプトは median3_target.py と**同一の手法・中央値定義(=通過パスのみの med_month)**で
  raw vs RG3 を直接比較し、median-3 の最良構成を確定する。

データ解決(Drive優先):
  1) Google Drive がマウントされ {DRIVE_BASE}/multiasset_daily/{指数}_d.csv があれば research/data へ取込
     (=docs/68 の確定値と同じ入力 → E-Mon net≈67% 水準)。
  2) 無ければ固定窓(2016-2025) Yahoo にフォールバック(E-Mon net≈57% 水準=相対比較用)。
     ⚠ Yahoo時は絶対値が median3_target.json(Drive系)と一致しない。**raw vs RG3 の差分を読む**こと。

審査条件: FundedNext Stellar P1 (+8% / −10%静的)。参考で median-4 も併記。
規律: 数字は盛らない。月次解像度=失格は楽観。最終はデモで確定。
出力: results/median3_rg3_target.json (+ 実行環境・入力ハッシュは notebooks 版の save_result で)
"""
import os, sys, json, shutil, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
os.environ.setdefault("RG_ALLOW_YAHOO", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parallel_vs_existing_compare import v7_monthly, v4_monthly, e5_monthly, z
from pstar_challenge_mc import find_scale, simulate, p95_annual_maxdd
import edge_regime_gate_10y as RG

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
INDEXES = ["NAS100", "US500", "GER40"]


def resolve_drive_first():
    """Drive の指数日足があれば research/data に取込(docs/68 と同一入力)。"""
    src_dir = os.path.join(DRIVE_BASE, "multiasset_daily")
    got = []
    if os.path.isdir(src_dir):
        os.makedirs(DATA, exist_ok=True)
        for nm in INDEXES:
            s = os.path.join(src_dir, f"{nm}_d.csv")
            if os.path.exists(s):
                shutil.copy(s, os.path.join(DATA, f"{nm}_d.csv")); got.append(nm)
    print(f"[データ] Drive取込={got or 'なし(固定窓Yahooへフォールバック)'}")
    return got


def to_m(w):
    s = w.copy(); s.index = pd.to_datetime(s.index).to_period("M"); return s.groupby(level=0).sum()


def median_month(s, scale, t):
    return simulate(s, scale, t, n_paths=12000)["med_month"]   # median3_target.py と同一定義(通過パスのみ)


def scale_for_median(s, ref, want, t, lo=0.2, hi=6.0):
    for _ in range(30):
        mid = (lo + hi) / 2
        if median_month(s, mid * ref, t) <= want: hi = mid
        else: lo = mid
    return hi * ref


def main():
    drive_got = resolve_drive_first()
    V4 = v4_monthly()
    EMON = {"raw": to_m(RG.emon_weekly_raw()), "RG3": to_m(RG.emon_weekly_gated("riskoff"))}

    print("E-Mon スリーブ(共通期間):")
    sleeve = {}
    for k, s in EMON.items():
        eq = (1 + s).cumprod(); dd = ((eq - eq.cummax()) / eq.cummax()).min() * 100
        sleeve[k] = dict(net_pct=round((eq.iloc[-1] - 1) * 100, 1), maxDD_pct=round(dd, 1), n=len(s))
        print(f"  {k:3s}: net{(eq.iloc[-1]-1)*100:7.1f}%  maxDD{dd:6.1f}%  n={len(s)}")
    # サニティ指標: Drive入力なら raw net ≈ +67%(docs/68)。Yahoo時は ≈ +57%(相対比較モード)。

    def series_for(wv4, wem, emk):
        M = pd.DataFrame({"v4": V4, "E-Mon": EMON[emk]}).dropna()
        return (z(M["v4"]) * wv4 + z(M["E-Mon"]) * wem).dropna()

    base55 = series_for(.55, .45, "raw")
    S10ref = find_scale(base55, -10.0)            # 55:45(raw) の −10%枠=1.0x 基準(表示用)

    V7 = v7_monthly(); E5 = e5_monthly()

    def series_w(weights, emk):
        cols = {}
        for k, wv in weights.items():
            if wv <= 0: continue
            cols[k] = EMON[emk] if k == "E-Mon" else {"v7": V7, "v4": V4, "E5": E5}[k]
        M = pd.DataFrame(cols).dropna()
        return sum(z(M[k]) * weights[k] for k in cols).dropna()

    # v7/E5 込み(現状運用=docs/70 整合)。E-Mon有り構成は raw/RG3 両方を採点。
    CANDS = [
        ("v4:E-Mon 55:45 (旧2成分)",        {"v4": .55, "E-Mon": .45}, True),
        ("v7:v4:E5 40:40:20 (P0)",          {"v7": .40, "v4": .40, "E5": .20}, False),
        ("PA v7:v4:E5:E-Mon 30:30:20:20",   {"v7": .30, "v4": .30, "E5": .20, "E-Mon": .20}, True),
        ("D v4:v7:E-Mon:E5 30:25:25:20",    {"v4": .30, "v7": .25, "E-Mon": .25, "E5": .20}, True),
        ("v7:v4:E-Mon 35:35:30 (E5無)",     {"v7": .35, "v4": .35, "E-Mon": .30}, True),
        ("均等 25:25:25:25",                 {"v7": .25, "v4": .25, "E5": .25, "E-Mon": .25}, True),
    ]
    out = {"data_source": ("Drive" if drive_got else "Yahoo(fixed-window)"), "sleeve": sleeve, "grids": {}}

    for tag, t, want in [("FundedNext +8% / median-3", 0.08, 3),
                         ("FundedNext +8% / median-4", 0.08, 4)]:
        print("\n" + "=" * 94); print(tag); print("=" * 94)
        print(f"{'構成':22s}{'E-Mon':>6}{'倍率*':>8}{'p95年DD':>9}{'通過%':>8}{'失格%':>8}{'中央月':>7}")
        grid = {}
        for nm, w, has_emon in CANDS:
            for emk in (["raw", "RG3"] if has_emon else ["raw"]):
                s = series_w(w, emk)
                S = scale_for_median(s, S10ref, want, t)
                r = simulate(s, S, t, n_paths=20000); dd = p95_annual_maxdd(s, S)
                grid[f"{nm}|{emk}"] = dict(mult=round(S / S10ref, 2), p95DD=round(dd, 0),
                                           pass_pct=r["pass_pct"], fail_pct=r["fail_pct"], med=r["med_month"])
                print(f"{nm:22s}{emk:>6}{('×'+format(S/S10ref,'.2f')):>8}{dd:>9.0f}{r['pass_pct']:>8}{r['fail_pct']:>8}{r['med_month']:>7}")
        best = min(grid.items(), key=lambda kv: kv[1]["fail_pct"])
        print(f"→ 最小失格 = 【{best[0]}】 失格{best[1]['fail_pct']}% / 通過{best[1]['pass_pct']}%")
        out["grids"][tag] = grid

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    path = os.path.join(HERE, "results", "median3_rg3_target.json")
    json.dump(out, open(path, "w"), ensure_ascii=False, indent=2, default=str)
    print(f"\n保存: {path}")
    print("* 倍率=55:45(raw)の−10%枠=1.0x基準(表示用)。中央値=通過パスのみ(median3_target.pyと同一定義)。")
    print("⚠ データ源が Yahoo の場合、絶対値は median3_target.json(Drive系)より悪く出る。raw vs RG3 の差分を読む。")
    return out


if __name__ == "__main__":
    main()
