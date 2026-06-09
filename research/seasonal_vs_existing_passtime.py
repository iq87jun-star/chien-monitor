#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seasonal_vs_existing_passtime.py
=================================================================
第3並走ポートフォリオ(季節性核口座) を、既存主軸ポートの【中央値4ヶ月版】と
"同じ FundedNext Phase1 +8% / 月次解像度" で正面比較する。

★既存の枠組み(docs/56,64 / p1_july_start_sjul.py):
  既存主軸ポート(v7+v4+E5)は mult=1.47 で Phase1 を【中央4ヶ月】通過するよう
  サイズ較正されている = "median4" 版。一次値(p1_july_start_sjul.json):
    median4: 通過93.9% / 失格6.1% / ≤3ヶ月38.0% / ≤4ヶ月53.7% / 中央4ヶ月。

★本スクリプトの問い(ユーザー): 「第3口座も中央値4ヶ月版にして既存と比較」。
  → 季節口座は年1-2窓(7月/12月)しか発火しない。∴ ★中央4ヶ月は"構造的に不可能"
    (7月待ちの期待だけで中央~6ヶ月)。サイズを上げても -10%枠で頭打ち。
    本スクリプトは「季節口座の"最速で実現可能な"月次中央値」を-10%枠内で測り、
    既存median4と"正直に"並べる。盛らない: 4ヶ月に届かないことを数値で示す。

  併せて、季節性が"中央4ヶ月の土俵で役立つ"唯一の正しい使い方=
    【既存median4口座への7月オーバーレイ】の一次効果(p1_julyより)も並記する。

数値出所:
  - 既存median4: research/results/p1_july_start_sjul.json (一次・そのまま引用)
  - 季節口座: research/results/calendar_event_edge_10y.json の確定窓を月次MC
出力: research/results/seasonal_vs_existing_passtime.json
"""
import json, os, random

random.seed(20260609)
HERE = os.path.dirname(os.path.abspath(__file__))
RESDIR = os.path.join(HERE, "results")

# ---------------------------------------------------------------
# 季節窓の一次値(calendar_event_edge_10y.json / docs/64)
# ---------------------------------------------------------------
def load_legs():
    legs = {
        "S-Jul": {"month": 7, "yearly_mean_pct": 3.04, "yearly_min_pct": -0.4,
                  "pos_pct": 80.0, "maxDD_pct": -5.7, "corr_emon": -0.31, "corr_v7": 0.64},
        "XAU-Dec": {"month": 12, "yearly_mean_pct": 1.9, "yearly_min_pct": -1.5,
                    "pos_pct": 80.0, "maxDD_pct": -5.8, "oos_perm_p": 0.2592, "jk_max_p": 0.123},
    }
    try:
        j = json.load(open(os.path.join(RESDIR, "calendar_event_edge_10y.json")))
        bj = j.get("baskets", {}).get("S-Jul(US500+NAS100 Jul L)")
        if bj:
            legs["S-Jul"].update(yearly_mean_pct=bj["yearly_mean_pct"],
                                 yearly_min_pct=bj["yearly_min_pct"],
                                 pos_pct=bj["yearly_pos_pct"], maxDD_pct=bj["maxDD_pct"],
                                 corr_emon=bj["corr_emon"], corr_v7=bj["corr_v7"])
        dj = j.get("detail", {}).get("XAUUSD_Dec_L")
        if dj:
            legs["XAU-Dec"].update(maxDD_pct=dj["full"]["maxDD_pct"],
                                   oos_perm_p=dj.get("oos", {}).get("perm_p"),
                                   jk_max_p=dj.get("jackknife_max_p"))
    except FileNotFoundError:
        pass
    return legs


def load_existing_median4():
    """既存主軸ポートの median4 版(=mult1.47)を一次JSONから引用。"""
    try:
        j = json.load(open(os.path.join(RESDIR, "p1_july_start_sjul.json")))
        sc = j["scenarios"]
        return {
            "base":     sc["FundedNext +8%|median4|S-Jul無"],
            "overlay_1pt": sc["FundedNext +8%|median4|ｻﾃﾗｲﾄ+1pt"],
            "overlay_mid": sc["FundedNext +8%|median4|中ｻｲｽﾞ"],
            "overlay_full": sc["FundedNext +8%|median4|ﾌﾙ脚相当"],
        }
    except FileNotFoundError:
        return None


def synth_yearly(mean, ymin, pos_pct, n=10):
    npos = round(pos_pct / 100.0 * n); nneg = n - npos
    neg = [ymin] * max(nneg, 0)
    needed = mean * n - sum(neg)
    pos = [needed / max(npos, 1)] * npos
    s = neg + pos
    adj = mean - sum(s) / n
    return [x + adj for x in s]


# ---------------------------------------------------------------
# 季節口座: 月次解像度の Phase1 +8% 通過MC(ランダム開始月)
#  各月: 7月なら核S-Jul発火 / 12月なら金(任意・半分) / 他月はP&L=0(休眠)。
#  -5%日次/-10%最大ガード。窓内トラフ= maxDD×U(0.4,1.0) で確率化(盛らない)。
# ---------------------------------------------------------------
def mc_phase1_months(legs, mult, include_dec, n_sims=60000, cap_months=60,
                     target=8.0, max_loss=10.0):
    sj = legs["S-Jul"]; dc = legs["XAU-Dec"]
    sj_s = synth_yearly(sj["yearly_mean_pct"], sj["yearly_min_pct"], sj["pos_pct"])
    dc_s = synth_yearly(dc["yearly_mean_pct"], dc["yearly_min_pct"], dc["pos_pct"])
    sj_dd = abs(sj["maxDD_pct"]); dc_dd = abs(dc["maxDD_pct"])
    months_pass = []; breaches = 0; timeouts = 0
    for _ in range(n_sims):
        eq = 0.0; m0 = random.randint(1, 12); broke = passed = False
        for k in range(cap_months):
            mon = (m0 - 1 + k) % 12 + 1
            if mon == 7:
                r = random.choice(sj_s) * mult
                trough = eq + min(r, 0.0) - sj_dd * mult * random.uniform(0.4, 1.0)
                if trough <= -max_loss: broke = True; break
                eq += r
                if eq >= target: passed = True; months_pass.append(k + 1); break
            elif mon == 12 and include_dec:
                r = random.choice(dc_s) * mult * 0.5
                trough = eq + min(r, 0.0) - dc_dd * mult * 0.5 * random.uniform(0.4, 1.0)
                if trough <= -max_loss: broke = True; break
                eq += r
                if eq >= target: passed = True; months_pass.append(k + 1); break
            # 休眠月: 何もしない(DDも積まない)
        if not passed:
            if broke: breaches += 1     # -10%枠抵触=真の失格
            else:     timeouts += 1     # 5年内に+8%未達=遅いだけ(時間制限なしなら失格でない)
    months_pass.sort(); n = len(months_pass)
    out = {"mult": mult, "include_dec": include_dec,
           "pass_pct": round(100.0 * n / n_sims, 1),
           "breach_fail_pct": round(100.0 * breaches / n_sims, 2),
           "timeout_pct(5y, not a real DQ)": round(100.0 * timeouts / n_sims, 1)}
    if n:
        out["median_month"] = months_pass[n // 2]
        out["mean_month"] = round(sum(months_pass) / n, 1)
        out["le4_pct"] = round(100.0 * sum(1 for x in months_pass if x <= 4) / n_sims, 1)
        out["le6_pct"] = round(100.0 * sum(1 for x in months_pass if x <= 6) / n_sims, 1)
        out["p90_month"] = months_pass[min(n - 1, int(0.9 * n))]
    return out


# ---------------------------------------------------------------
# 並走(口座1=既存median4 ∥ 口座3=季節)の"全損回避"を粗く評価。
#  既存median4の失格6.1%(独立) と 季節の失格 を、相関≈0(季節は11ヶ月休眠)
#  と仮定して「両方とも失格(=完全全損)」確率を出す。盛らない: 近似と明記。
# ---------------------------------------------------------------
def parallel_survival(exist_fail_pct, seasonal_fail_pct):
    pe = exist_fail_pct / 100.0; ps = seasonal_fail_pct / 100.0
    return {
        "exist_fail_pct": exist_fail_pct,
        "seasonal_fail_pct": seasonal_fail_pct,
        "both_fail_pct(approx, indep)": round(100.0 * pe * ps, 3),
        "at_least_one_pass_pct(approx)": round(100.0 * (1 - pe * ps), 3),
        "note": "季節は年11ヶ月休眠ゆえ口座レベル相関≈0と仮定した独立近似。実相関はデモで確認。",
    }


def main():
    legs = load_legs()
    exist = load_existing_median4()

    seasonal = {}
    for label, mult, inc in [
        ("season_x1.0(素)", 1.0, False),
        ("season_x1.3(守り)", 1.3, False),
        ("season_x1.5(-10%枠上限寄り)", 1.5, False),
        ("season_x1.5+dec(金12月併用)", 1.5, True),
    ]:
        seasonal[label] = mc_phase1_months(legs, mult, inc)

    result = {
        "title": "第3季節口座 vs 既存median4ポート — Phase1 +8% 月次通過の正面比較",
        "discipline": "数字を盛らない。既存側は一次p1_july引用。季節側は確定窓の月次MC。",
        "existing_median4_primary(p1_july_start_sjul.json)": exist,
        "seasonal_account_monthly_mc": seasonal,
        "structural_note":
            "季節口座は年1-2窓(7月/12月)のみ発火。ランダム開始だと7月到達の期待だけで"
            "中央~6ヶ月。∴ ★中央4ヶ月は構造的に不可能(サイズを上げても-10%枠で頭打ち)。"
            "本口座は『速さ』でなく『口座2(E-Mon)と負相関=同時DD回避・生存』が価値。",
        "correlation": {
            "S-Jul_vs_E-Mon(account2)": legs["S-Jul"]["corr_emon"],
            "S-Jul_vs_v7(account1)": legs["S-Jul"]["corr_v7"],
        },
    }
    if exist:
        ef = exist["base"]["fail_pct"]
        sf = seasonal["season_x1.5(-10%枠上限寄り)"]["breach_fail_pct"]
        result["parallel_survival(account1_median4 ∥ account3_seasonal)"] = parallel_survival(ef, sf)
        result["overlay_path_on_median4(季節を主軸口座に重畳した時の一次効果)"] = {
            "base(median4, S-Jul無)": {k: exist["base"][k] for k in ("pass_pct", "le3", "le4", "med")},
            "+S-Jul中サイズ": {k: exist["overlay_mid"][k] for k in ("pass_pct", "le3", "le4", "med")},
            "+S-Julフル脚相当": {k: exist["overlay_full"][k] for k in ("pass_pct", "le3", "le4", "med")},
            "note": "既存median4口座に7月だけ重畳=通過93.9%→94.4-94.8%・≤3ヶ月38.0%→40.6-43.4%(速度寄り小改善)。",
        }

    os.makedirs(RESDIR, exist_ok=True)
    outp = os.path.join(RESDIR, "seasonal_vs_existing_passtime.json")
    json.dump(result, open(outp, "w"), indent=2, ensure_ascii=False)

    # コンソール
    print("== 第3季節口座 vs 既存median4ポート (Phase1 +8% 月次) ==")
    if exist:
        b = exist["base"]
        print(f"  [既存median4 (mult1.47)] 通過{b['pass_pct']}% 失格{b['fail_pct']}% "
              f"中央{b['med']}ヶ月 ≤3ヶ月{b['le3']}% ≤4ヶ月{b['le4']}%  ← 4ヶ月の土俵")
    print("  [第3季節口座(月次MC)]")
    for k, v in seasonal.items():
        print(f"   {k}: 通過{v['pass_pct']}% 枠抵触{v['breach_fail_pct']}% "
              f"遅延{v['timeout_pct(5y, not a real DQ)']}% "
              f"中央{v.get('median_month','-')}ヶ月 ≤4ヶ月{v.get('le4_pct','-')}% ≤6ヶ月{v.get('le6_pct','-')}% "
              f"p90 {v.get('p90_month','-')}ヶ月")
    print("  ★中央4ヶ月は季節口座単独では不可能(7月待ち=中央~6ヶ月以上・-10%枠で頭打ち)。")
    if exist:
        ps = result["parallel_survival(account1_median4 ∥ account3_seasonal)"]
        print(f"  [並走 口座1∥口座3] 両方失格≈{ps['both_fail_pct(approx, indep)']}% "
              f"(=少なくとも片方通過≈{ps['at_least_one_pass_pct(approx)']}%・独立近似)")
    print(f"  -> {outp}")


if __name__ == "__main__":
    main()
