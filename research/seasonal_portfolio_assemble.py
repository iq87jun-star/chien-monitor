#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seasonal_portfolio_assemble.py
=================================================================
第3並走ポートフォリオ(=季節性核オーバーレイ口座)の "組み立て + 採点"。

★方針(ユーザー選択): 既存口座1(v7系) / 口座2(E-Mon系) と並走する第3口座を、
  「季節性(month-of-year)を核」に・FundedNext Stellar 2-Step 向けに構築する。

★規律(docs/14,18,50,64 の系譜): 数字は盛らない。新規データ探索はしない。
  一次値は既に確定済みの探索結果 research/results/calendar_event_edge_10y.json
  (Yahoo日足10年・N=164・順列/IS-OOS/年次JK/Bonferroni/コスト/相関) を"そのまま"使う。
  本スクリプトは「既存の検定済み季節窓を、第3口座として組み立て・採点」するだけ。
  ∴ 新しい有意性主張はしない。確証はデモ前進検証(docs/29)で埋める。

入力(一次・calendar_event_edge_10y.json より):
  - S-Jul(US500+NAS100 7月L): 年平均+3.04% / 最悪年-0.4% / 陽性年80% /
    年次ブロックp=0.0045 / maxDD-5.7% / corr_emon=-0.31 / corr_v7=+0.64
       → クリーンな SEASONAL-LEAD。第3口座の【核】。
  - XAU_Dec(金 12月L): net+21%/10y(≒年平均+1.9%) / 陽性年80% / 年次p=0.0252 /
    ただし ★OOS perm_p=0.26(非有意) / ★年次JK_max=0.123(>0.10不合格) /
    コスト3xで+2.4%(脆) → 弱い。【小サイズの第2窓(別資産・別月)】に限定。
  - S-Nov(指数11月): corr_emon=+0.55(冗長) → 不採用(口座2と重複)。

出力: results/seasonal_portfolio_assemble.json
"""
import json, os, math, random

random.seed(20260609)
HERE = os.path.dirname(os.path.abspath(__file__))
RESDIR = os.path.join(HERE, "results")
SRC = os.path.join(RESDIR, "calendar_event_edge_10y.json")

# ---------------------------------------------------------------
# 1) 一次値の取り込み(既存JSON)。無ければ docs/64 記載値にフォールバック。
# ---------------------------------------------------------------
def load_primary():
    prim = {
        "S-Jul": {  # docs/64 / baskets["S-Jul(US500+NAS100 Jul L)"]
            "month": 7, "assets": ["US500", "NAS100"],
            "yearly_mean_pct": 3.04, "yearly_min_pct": -0.4, "pos_pct": 80.0,
            "yearly_block_p": 0.0045, "maxDD_pct": -5.7,
            "corr_v7": 0.64, "corr_emon": -0.31, "grade": "SEASONAL-LEAD(core)",
        },
        "XAU-Dec": {  # detail["XAUUSD_Dec_L"]
            "month": 12, "assets": ["XAUUSD"],
            "yearly_mean_pct": 1.9, "yearly_min_pct": -1.5, "pos_pct": 80.0,
            "yearly_block_p": 0.0252, "maxDD_pct": -5.8,
            "oos_perm_p": 0.2592, "jk_max_p": 0.123, "cost3x_net_pct": 2.4,
            "grade": "WEAK(OOS-fail/jk-fail) -> small satellite only",
        },
    }
    try:
        with open(SRC) as f:
            j = json.load(f)
        bj = j.get("baskets", {}).get("S-Jul(US500+NAS100 Jul L)")
        if bj:
            prim["S-Jul"].update({
                "yearly_mean_pct": bj["yearly_mean_pct"],
                "yearly_min_pct": bj["yearly_min_pct"],
                "pos_pct": bj["yearly_pos_pct"],
                "yearly_block_p": bj["yearly_block_p"],
                "maxDD_pct": bj["maxDD_pct"],
                "corr_emon": bj["corr_emon"],
                "corr_v7": bj["corr_v7"],
            })
        dj = j.get("detail", {}).get("XAUUSD_Dec_L")
        if dj:
            prim["XAU-Dec"].update({
                "yearly_block_p": dj.get("yearly_block_p"),
                "maxDD_pct": dj["full"]["maxDD_pct"],
                "oos_perm_p": dj.get("oos", {}).get("perm_p"),
                "jk_max_p": dj.get("jackknife_max_p"),
                "cost3x_net_pct": dj.get("cost_net", {}).get("3x"),
            })
        prim["_source"] = "calendar_event_edge_10y.json (primary)"
    except FileNotFoundError:
        prim["_source"] = "docs/64 fallback (json not found)"
    return prim


# ---------------------------------------------------------------
# 2) 季節窓ごとの年次リターン標本を近似(10標本)。
#    実年次系列は未保存ゆえ、確定済みの (mean, min, pos%) に整合する
#    10点の代表標本をモーメント整合で構成する(過大評価しないため
#    最悪年=min をアンカー・上振れは控えめ)。これは "盛らない" 近似で
#    あって新規主張ではない。最終はDriveで実年次系列に置換すること。
# ---------------------------------------------------------------
def synth_yearly(mean, ymin, pos_pct, n=10):
    """meanとminと陽性年率に整合する保守的な10標本(対称に盛らない)。"""
    npos = round(pos_pct / 100.0 * n)
    nneg = n - npos
    neg = [ymin] * max(nneg, 0)
    # 陽性年は mean を僅かに上回る程度に控えめ(派手な上振れを作らない)
    needed_sum = mean * n - sum(neg)
    pos_val = needed_sum / max(npos, 1)
    pos = [pos_val] * npos
    s = neg + pos
    # 平均を厳密に合わせる微調整
    adj = mean - (sum(s) / n)
    s = [x + adj for x in s]
    return s


# ---------------------------------------------------------------
# 3) No-time-limit FundedNext 2-Step の通過モンテカルロ。
#    季節口座は1年に Jul(核)+Dec(任意の弱窓) が発火。時間制限なしゆえ
#    "+8%(P1)到達まで何年積むか" を測る。各窓は equity に加算、
#    日次-5%/最大-10% ガードは季節窓の小DD(最悪 Jul-0.4% / Dec-5.8%)では
#    ほぼ拘束しないが、保守的に窓内DDを引いた上で判定する。
# ---------------------------------------------------------------
def mc_pass_years(legs, risk_mult, include_dec, n_sims=50000, max_years=12,
                  p1_target=8.0, p2_target=5.0, max_loss=10.0):
    sj = legs["S-Jul"]
    dc = legs["XAU-Dec"]
    sj_samp = synth_yearly(sj["yearly_mean_pct"], sj["yearly_min_pct"], sj["pos_pct"])
    dc_samp = synth_yearly(dc["yearly_mean_pct"], dc["yearly_min_pct"], dc["pos_pct"])
    sj_dd = abs(sj["maxDD_pct"]); dc_dd = abs(dc["maxDD_pct"])

    pass_years = []
    fails = 0
    for _ in range(n_sims):
        # Phase1: +8% を積むまで(時間制限なし) / Phase2: 残高リセットして +5%
        for phase, target in (("P1", p1_target), ("P2", p2_target)):
            equity = 0.0          # 基準(=0)からの累積%。max-lossは -max_loss でブレーチ
            yr = 0
            passed = False
            broke = False
            while yr < max_years:
                yr += 1
                # July 核(必ず発火)
                r_jul = random.choice(sj_samp) * risk_mult
                # 窓内DD(含み損の谷)。毎年"最悪"を引くのは過度に悲観ゆえ、
                # 窓内トラフを maxDD の一様割合(0.4-1.0倍)で確率化する(盛らない近似)。
                dd_jul = sj_dd * risk_mult * random.uniform(0.4, 1.0)
                trough = equity + min(r_jul, 0.0) - dd_jul
                if trough <= -max_loss:
                    broke = True; break
                equity += r_jul
                if equity >= target:
                    passed = True; break
                # December 金(任意・弱窓・小サイズ=半分)
                if include_dec:
                    r_dec = random.choice(dc_samp) * risk_mult * 0.5
                    dd_dec = dc_dd * risk_mult * 0.5 * random.uniform(0.4, 1.0)
                    trough = equity + min(r_dec, 0.0) - dd_dec
                    if trough <= -max_loss:
                        broke = True; break
                    equity += r_dec
                    if equity >= target:
                        passed = True; break
            if broke or not passed:
                fails += 1
                phase_fail = True
                break
            phase_fail = False
            if phase == "P1":
                p1_years = yr
            else:
                p2_years = yr
        if not phase_fail:
            pass_years.append(p1_years + p2_years)

    pass_years.sort()
    n_pass = len(pass_years)
    out = {
        "risk_mult": risk_mult, "include_dec": include_dec, "n_sims": n_sims,
        "pass_pct": round(100.0 * n_pass / n_sims, 1),
        "fail_pct": round(100.0 * fails / n_sims, 1),
    }
    if n_pass:
        out["median_years_P1P2"] = pass_years[n_pass // 2]
        out["mean_years_P1P2"] = round(sum(pass_years) / n_pass, 2)
        out["p90_years_P1P2"] = pass_years[min(n_pass - 1, int(0.9 * n_pass))]
    return out


def main():
    prim = load_primary()
    legs = {"S-Jul": prim["S-Jul"], "XAU-Dec": prim["XAU-Dec"]}

    result = {
        "title": "第3並走ポートフォリオ(季節性核オーバーレイ口座) 組み立て・採点",
        "discipline": "数字を盛らない。新規データ探索なし。一次=calendar_event_edge_10y.json。確証はデモ前進検証。",
        "source": prim.get("_source"),
        "legs": legs,
        "excluded": {
            "S-Nov(index Nov L)": "corr_emon=+0.55(口座2 E-Monと冗長)ゆえ不採用",
        },
        # 口座レベルの相関の正直な解釈:
        # ・S-Jul の共活性相関は corr_emon=-0.31(口座2と負=分散源), corr_v7=+0.64(口座1と高い)。
        # ・ただし第3口座は年11ヶ月フラット(7月と12月のみ発火)ゆえ、年率/月次の
        #   "口座レベル"の共変動は機械的に希薄化する(大半の月でP&L=0)。
        # ・∴ 口座2との並走価値は高い(負相関×低稼働=同時DD回避)。口座1とは7月に
        #   共にロングになり得る(corr_v7=+0.64)が、稼働月が年1-2ヶ月ゆえ
        #   同時大DDの実害は限定的。盛らずに両方を明記する。
        "correlation_note": {
            "S-Jul_vs_E-Mon(account2)": legs["S-Jul"]["corr_emon"],
            "S-Jul_vs_v7(account1)": legs["S-Jul"]["corr_v7"],
            "interpretation": "co-active corr。口座は年1-2ヶ月のみ稼働ゆえ口座レベルは希薄化。"
                              "口座2(E-Mon)とは負相関=真の分散。口座1(v7)とは7月共ロングに注意(小稼働で実害限定)。",
        },
        "monte_carlo_no_time_limit": {},
    }

    # 季節口座のサイズ(=核S-Julの実効リスク倍率)を数段で試算。
    # mult=1 は月次1%素サイズ相当(年平均~3%)。プロップは-10%枠内でサイズを上げる。
    # 季節口座は-10%枠ゆえ小サイズ限定(核S-Julの素maxDD-5.7%が既に枠の過半)。
    # 現実的なプロップ・サイズ帯=1.0-1.5x のみを試算する(1.7x超は単一窓で枠割れ)。
    for label, rm, inc in [
        ("core_only_x1.0(素・月1%相当)", 1.0, False),
        ("core_only_x1.3(守り中サイズ)", 1.3, False),
        ("core+dec_x1.3(7月核+12月金衛星)", 1.3, True),
        ("core+dec_x1.5(上限寄り・-10%枠内)", 1.5, True),
    ]:
        result["monte_carlo_no_time_limit"][label] = mc_pass_years(legs, rm, inc)

    os.makedirs(RESDIR, exist_ok=True)
    outp = os.path.join(RESDIR, "seasonal_portfolio_assemble.json")
    with open(outp, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # コンソール要約
    print("== 第3並走ポートフォリオ(季節性核) 組み立て ==")
    print(f"  source: {result['source']}")
    print(f"  核 S-Jul: 年平均{legs['S-Jul']['yearly_mean_pct']}% / 最悪{legs['S-Jul']['yearly_min_pct']}%"
          f" / corr_emon={legs['S-Jul']['corr_emon']} / corr_v7={legs['S-Jul']['corr_v7']}")
    print(f"  弱窓 XAU-Dec: 年平均{legs['XAU-Dec']['yearly_mean_pct']}% / OOS_p={legs['XAU-Dec'].get('oos_perm_p')}"
          f" / jk_max={legs['XAU-Dec'].get('jk_max_p')} (=弱い・小サイズ)")
    print("  -- No-time-limit 2-Step 通過MC --")
    for k, v in result["monte_carlo_no_time_limit"].items():
        print(f"   {k}: 通過{v['pass_pct']}% / 失格{v['fail_pct']}% / "
              f"中央{v.get('median_years_P1P2','-')}年(P1+P2) / p90 {v.get('p90_years_P1P2','-')}年")
    print(f"  -> {outp}")
    print("\n  ⚠ 年次標本=モーメント整合の保守近似(実年次系列はDrive実行で置換)。")
    print("  ⚠ 季節性=実サンプル年数のみ=薄い。SEASONAL-LEADでありADOPTでない。本資金前デモ必須。")


if __name__ == "__main__":
    main()
