# -*- coding: utf-8 -*-
"""docs/225: 全セルの「紙上フォワード」— 日足を当日まで再取得し、選抜凍結(2026-07-29)以後の月次リターンをセル別に出す。
実口座の記録ではなく生成式の延長(執行コスト=モデル定数)。フォワード記録(docs/218/224)との差 = 執行の実態。
使い方: python3 forward/paper_forward.py [YYYY-MM ...]   既定 = 2026-08 と当月"""
import os, sys, time, glob, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
import recentfit_screen as base, deployed_book as db
FREEZE = pd.Timestamp("2026-07-29")


def refresh_live():
    base.DATA = os.path.join(ROOT, "data_live"); os.makedirs(base.DATA, exist_ok=True)
    for f in glob.glob(os.path.join(base.DATA, "*_rf.csv")):           # 当日より古いキャッシュは捨てて再取得
        if time.time() - os.path.getmtime(f) > 6 * 3600: os.remove(f)
    base.P2_EPOCH = int(time.time()); base.W_ALL0, base.W_ALL1 = pd.Timestamp("2016-01-01"), pd.Timestamp.today().normalize()


def universe():
    cells = [("Mon", s) for s in base.MON_FX + base.MON_IDX] + [("Hold", s) for s in base.HOLD_SYMS] \
          + [("TSMOM", s) for s in base.TSMOM_SYMS] + [("v4", s) for s in base.V4_PAIRS]
    for acc in db.BOOK.values():
        for f, s, _ in acc["legs"]:
            if (f, s) not in cells: cells.append((f, s))
    return cells


# docs/229 §4 事前登録の候補セル(2026-10〜2027-03 の 6 ヶ月判定)。universe() には含めない(既知セル集合を変えないため)
CANDIDATES = [("Thu", "XAUUSD", 3, False)] + [("MonExHol", s, 0, False) for s in ("EURJPY", "GBPJPY", "USDJPY", "NZDJPY", "CHFJPY")] \
    + [("MonExAUNZ", s, 0, False) for s in ("AUDJPY", "NZDJPY")] + [("MonExJpTue", s, 0, False) for s in ("USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY")] + [("MonExGotobi", "Mon7", 0, False)] + [("HoldSL10", "BTCUSD", 0, False)] + [("MonIdxIntra", s, 0, False) for s in ("US30", "JP225")] + [("MonJpyIntra6J", "USDJPY", 0, False)] + [("MonIdxSession0", s, 0, False) for s in ("US500", "NAS100", "US30")] + [("MonJpySession6J", "USDJPY", 0, False)] + [("RollGateB2", "Roll5", 0, False)] + [("MonSkewGate", "Mon4", 0, False), ("MonSkewGate3", "Mon3", 0, False)] + [("MonBojExit20", "Mon4", 0, False)] + [("MonWeakSMA200A", "Mon4", 0, False), ("MonWeakSMA200B", "Mon4", 0, False)] + [("MonWeakOnlySMA200", "NZDJPY", 0, False), ("MonWeakOnlySMA200", "US30", 0, False)] + [("RollSma200B", "Roll5", 0, False)] + [("MonAboveExit20", "Mon4", 0, False)] + [("MonIdxStateF", s, 0, False) for s in ("US30", "JP225")] + [("MonVixJumpExit", "Mon4", 0, False)] + [("MonGapLowExit", "Mon4", 0, False), ("MonVixOrGapExit", "Mon4", 0, False)] + [("MonSkewGateHotOff", "Mon4", 0, False), ("MonSkewGateHotOffE1", "Mon4", 0, False)] + [("MonIdxExNyse", x, 0, False) for x in ("US500", "US30", "JP225", "US3")] + [("MonAudCad" + k, "AUDJPY+CADJPY", 0, False) for k in ("E1", "G1", "G3")] + [("MonNightIdxHot", "IDX5", 0, False)]   # 2026-11-09 docs/412 Q175: 日銀火曜の週だけ月曜ショットを同日 20 UTC 手仕舞い(H1 実時刻 Mon4・改良系通過・改善は 2022-12-19 の 1 事象が大半・紙上のみ)   # 2026-11-08 docs/410 Q174: Mon3 の SKEW 門(改良系通過・紙上のみ)   # 2026-11-08 docs/409 Q173: Mon4 の SKEW 門(改良系通過・紙上のみ)   # 2026-10-26 docs/378 Q147: Roll 5 本等分に通貨別政策金利差 ≥ 2.0% のゲート(改良系通過・現在は非拘束・紙上のみ)   # 2026-10-11 docs/344・347: セッション版(月曜 0 UTC / 日曜 22 UTC 建て → 20 UTC・標準未通過・紙上のみ)   # 2026-10-11 docs/338 Q119: Mon USDJPY 4 ショット(4/6/8/10 UTC)→ 同日 20 UTC(6J 日中版・前窓 48% で紙上のみ)   # 2026-10-09 docs/333 Q114: Mon 指数の日中版(13→20 UTC・改良系通過・紙上のみ)   # 2026-10-09 docs/330 Q90: Hold BTCUSD の災害 SL 10%(改良系通過・差は僅少・紙上のみ)   # 2026-09-26 docs/304 Q56   # 2026-09-26 docs/303 Q53: 祝日月曜スキップ(改良系通過・紙上のみ)   # 2026-09-18 docs/249: 曜日 SHORT 候補 4 本(MonS EURGBP / FriS NZDUSD / WedS CADCHF / TueS CADCHF)はコスト符号バグの産物のため削除


def candidate_series(fam, sym, dow, short):
    if fam == "MonExHol":   # docs/303 Q53: 月曜 o2o LONG から日本の祝日月曜を除く
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q_jp import is_jp_holiday
        m = base.mon_cell(sym); return m[[not is_jp_holiday(t) for t in m.index]]
    if fam == "MonSun22":   # docs/365 Q139(10/21 docs/367 §5 で候補から除外・bid アーティファクト): 日曜 22 UTC(東京オープン)建て → 月曜 20 UTC 決済(H1・週明けショット)
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q139_mon_sun22 import shot_sun22
        return shot_sun22(sym)
    if fam == "RollGateB2":   # docs/378 Q147: Roll 5 本等分 + 通貨別政策金利差 ≥ 2.0% ゲート(2026-10-26)
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q147_roll_rate_diff_gate import leg, family, PAIRS, rate_series
        legs = {x: leg(x) for x in PAIRS}; days = pd.DatetimeIndex(sorted(set().union(*[set(legs[x].index) for x in PAIRS]))); jp = rate_series("JPY", days)
        return family(legs, {x: (rate_series(x[:3], days) - jp >= 2.0) for x in PAIRS})
    if fam == "RollSma200B":   # docs/444 Q205(2026-11-14): Roll5(門 2.0pp)で 200 日線の上の通貨 1.0 倍・下の通貨 0.5 倍(改良系 形式通過・Sharpe は微増だが累積は減る・紙上のみ・配備の提案なし)
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q205_roll5_sma200_state import roll5_sma200
        return roll5_sma200("B")
    if fam == "MonVixJumpExit":   # docs/478 Q239(2026-11-16): 配備形 Mon4 で、金曜の VIX が前日比 +2pt 以上の週だけ 24h・それ以外は同日 20 UTC 決済(改良系 3 窓通過。採用済みの E1 = VIX の水準で切り替える形は上回らない・紙上のみ)
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q239_cross_asset_state_for_mon4 import mon4_cross_asset
        return mon4_cross_asset("C2")
    if fam in ("MonGapLowExit", "MonVixOrGapExit"):   # docs/479 Q240(2026-11-16): 配備形 Mon4 で、週末の窓(金曜の最終足 → 月曜 04 UTC)が自分の過去の下位 20% の通貨だけ 24h(G1)/ VIX > 25 または G1 のとき 24h(G3)。それ以外は同日 20 UTC 決済(改良系 3 窓通過。採用済みの E1 は 3 窓では上回らない・紙上のみ)
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q240_weekend_premium_predictions import weekend_premium
        return weekend_premium("G1" if fam == "MonGapLowExit" else "G3")
    if fam in ("MonSkewGateHotOff", "MonSkewGateHotOffE1", "MonIdxExNyse"):   # docs/481 Q242(2026-11-16): SKEW 門を前金曜の VIX > 25 の週には掛けない(決済 24h / E1)・月曜の指数(13 UTC 24h)から NYSE 月曜休場の日を除く(改良系 3 窓通過・SKEW 門の 2 本は探索と OOS で各 1 週しか違わない・紙上のみ)
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q242_untested_observations_from_q240_q241 import observation
        return observation({"MonSkewGateHotOff": "B1", "MonSkewGateHotOffE1": "B2"}.get(fam, "C_" + sym))
    if fam == "MonNightIdxHot":   # docs/503〜505 Q263・Q264・Q265(2026-11-17 ユーザー「登録」): 前金曜の VIX > 25 の週だけ、月曜 20 UTC に指数 5 本(NAS100・US500・US30・JP225・UK100 等分)を買い、火曜 13 UTC に決済。レグ単体の規則では僅差の不成立(前窓の最悪月)・口座モデルは本口座後 7/7・評価中 9/15 が変更候補。年 6 週ほど・紙上のみ
        sys.path.insert(0, os.path.join(ROOT, "queue")); import q_common as _qc, q265_weekend_btc_signal_and_night_index_anatomy as _q265; _q265.load = _qc.load          # 月次 H1 の継ぎ足し(candidate_interim の差し替え)を効かせる
        _idx = pd.date_range("2016-01-04", pd.Timestamp.today().normalize() + pd.Timedelta(days=7), freq="7D"); return _q265.bundle_night(_q265.IDX5, _q265.hotflag(_idx), 1.0).sort_index()
    if fam in ("MonAudCadE1", "MonAudCadG1", "MonAudCadG3"):   # docs/482 Q243(2026-11-16): AUDJPY・CADJPY 等分の月曜の買いに決済の切り替え(E1 / G1 / G3)。改良系 3 窓通過だが、通貨別の結果を見た後で選んだ束(事後選択)・採用 4 本の E1 より Sharpe は低い・紙上のみ
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q243_audjpy_cadjpy_bundle_exit_switch import aud_cad
        return aud_cad(fam[-2:])
    if fam == "MonIdxStateF":   # docs/470 Q231(2026-11-15): 月曜の指数(13 UTC 建て)を 200 日線の下 1.0 倍・24h / 上 0.5 倍・同日 20 UTC 決済(US30・JP225 が改良系 3 窓通過・紙上のみ)
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q231_near_miss_rotation_and_state_exit import f_series
        return f_series(sym, "F")
    if fam == "MonAboveExit20":   # docs/468 Q229(2026-11-15): 配備形 Mon4(線の下 1.0・上 0.5)で、200 日線の上の通貨だけ同日 20 UTC 決済(改良系 3 窓通過・前後の時刻では前窓が不成立・紙上のみ)
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q229_state_dependent_exit import state_exit
        return state_exit("M3")
    if fam == "MonBojExit20":   # docs/412 Q175(2026-11-09): EA 実時刻 Mon4(4/6/8/10 UTC → 24h)で、日銀決定が翌火曜の月曜だけ同日 20 UTC 決済(改良系通過・紙上のみ・切替待ち)
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q175_boj_tuesday_exit20 import family, W4, BOJ_MON
        return family(W4, BOJ_MON)
    if fam == "MonWeakOnlySMA200":   # docs/435 Q196(2026-11-13): 金曜終値が 200 日線の下のときだけ月曜を建てる(NZDJPY = 4/6/8/10 UTC 24h・US30 = 13 UTC 24h。改良系 3 窓通過・口座モデルでは改善なし・紙上のみ)
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q196_weak_state_only_near_miss import weak_only_series
        return weak_only_series(sym)
    if fam in ("MonWeakSMA200A", "MonWeakSMA200B"):   # docs/434 Q195(2026-11-13): 配備形 Mon4 で金曜終値が 200 日線の下の通貨を 1.5 倍・それ以外を 0.75 倍(A)/ 0.5 倍(B)(改良系 3 窓通過・口座モデルでは改善なし・紙上のみ)
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q195_mon_weak_state_tilt import mon4_weak_tilt
        return mon4_weak_tilt("終値 < SMA200", 1.5, 0.75 if fam.endswith("A") else 0.5)
    if fam == "MonSkewGate3":   # docs/410 Q174 (a1)(2026-11-08): Mon3 円クロス(14074882 形・EURJPY .333 + USDJPY .333 + NZDJPY .334)から前金曜の SKEW 252 日 80 分位超の月曜を除く(改良系通過・紙上のみ)
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q173_skew_vvix_gate import PR, norm
        m = (norm(base.mon_cell("EURJPY")) * 0.333 + norm(base.mon_cell("USDJPY")) * 0.333 + norm(base.mon_cell("NZDJPY")) * 0.334).dropna()
        hi = PR["SKEW"].reindex(m.index - pd.Timedelta(days=3), method="ffill").values > 0.8; return m[~hi]
    if fam == "MonSkewGate":   # docs/409 Q173(2026-11-08): 配備形 Mon4(等ウェイト)から前金曜の CBOE SKEW が 252 日 80 分位超の月曜を除く(改良系通過・紙上のみ・EA は SKEW を参照できないため運用側で週次設定が必要)
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q173_skew_vvix_gate import mon4_skew_gated
        return mon4_skew_gated(0.8)
    if fam == "MonIdxIntra":   # docs/333 Q114: 月曜 13 UTC 建て → 同日 20 UTC 決済(H1)
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q114_mon_index_intraday import shot
        return shot(sym, 13, 20)
    if fam == "MonJpyIntra6J":   # docs/332 §2 / docs/338: 月曜 4/6/8/10 UTC 建て → 同日 20 UTC 決済の等ウェイト(6J 日中版)
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q114_mon_index_intraday import shot
        return pd.concat([shot(sym, h, 20) for h in (4, 6, 8, 10)], axis=1).mean(axis=1).dropna()
    if fam in ("MonIdxSession0", "MonJpySession6J"):   # docs/344・347: 先物プロップの取引日内に収まる最長形
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q_session import session
        return session(sym, 0, 0 if fam == "MonIdxSession0" else "open")
    if fam == "HoldSL10":   # docs/330 Q90: 連続 LONG + 建値固定 SL 10%(窓初日に建て直し・翌日始値で再建て)
        sys.path.insert(0, os.path.join(ROOT, "queue")); live = base.DATA; from q90_hold_disaster_sl import hold_sl; base.DATA = live   # Q107(docs/395 §2): q90 の import が base.DATA を凍結フォルダに固定するのを戻す
        return hold_sl(sym, 10.0)[0]
    if fam in ("MonExAUNZ", "MonExJpTue", "MonExGotobi"):   # docs/304 Q56: 参加者フィルター(改良系通過・紙上のみ)
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q_jp import is_jp_holiday; from q_cal import CAL, gotobi, mon7
        m = mon7() if sym == "Mon7" else base.mon_cell(sym)
        if fam == "MonExAUNZ": keep = [not ((t in CAL["AU"]) or (t in CAL["NZ"])) for t in m.index]
        elif fam == "MonExJpTue": keep = [not is_jp_holiday(t + pd.Timedelta(days=1)) for t in m.index]
        else: keep = [not gotobi(t) for t in m.index]
        return m[keep]
    df = base.load_daily(sym); c = base.IDX_COST.get(sym) or (2 * base.pip_size(sym) / df["open"])
    s = df[df["weekday"] == dow]["o2o"]; s = ((-s if short else s) - c).dropna(); return base.clip(s)   # 2026-09-18 修正(docs/249)


def main():
    months = sys.argv[1:] or ["2026-08", pd.Timestamp.today().strftime("%Y-%m")]
    refresh_live(); today = pd.Timestamp.today().normalize(); rows = []
    base.YAHOO.setdefault("EURGBP", "EURGBP=X"); base.YAHOO.setdefault("CADCHF", "CADCHF=X")
    for fam, sym, *cand in list(universe()) + [(f, s, d, sh) for f, s, d, sh in CANDIDATES]:
        try: s = candidate_series(fam, sym, *cand) if cand else db.leg_series(fam, sym)
        except Exception as e: rows.append(dict(family=fam, symbol=sym, error=str(e)[:80])); continue
        s = s[s.index < today]
        r = dict(family=fam + ("(候補)" if cand else ""), symbol=sym, data_end=str(s.index.max().date()), n_post_freeze=int((s.index > FREEZE).sum()))
        for m in months:
            q = s[s.index.to_period("M") == pd.Period(m)]
            r[f"{m}_pct"] = round(float((1 + q).prod() - 1) * 100, 3) if len(q) else np.nan; r[f"{m}_n"] = len(q)
        y = s[s.index > today - pd.DateOffset(months=12)]
        r["12m_pct"] = round(float((1 + y).prod() - 1) * 100, 2); r["12m_mean_bps"] = round(float(y.mean()) * 1e4, 2)
        rows.append(r)
    df = pd.DataFrame(rows); out = os.path.join(ROOT, "results", f"paper_forward_{months[0]}.csv"); df.to_csv(out, index=False)
    pd.set_option("display.width", 200); print(df.to_string(index=False)); print("->", out)
    try:   # Q107(docs/395): 候補セルの中間判定(docs/229 §4 の 6 か月判定)を同じ定例で集計。時間足系は月次 H1 を継ぎ足して再計算
        sys.path.insert(0, HERE); import candidate_interim as ci; ci.main(fetch=True)
    except Exception as e: print(f"(候補の中間判定に失敗: {e})")


if __name__ == "__main__": main()
