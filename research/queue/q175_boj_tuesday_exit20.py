# -*- coding: utf-8 -*-
"""docs/244 Q175(改良系・新規 1 セル・2026-11-09 登録「登録」→「今行って」): 日銀決定日(火曜)の前日 20 UTC 手仕舞い。
基準 = Q176 の EA 実時刻 Mon4(AUDJPY/EURJPY/GBPJPY/USDJPY 等ウェイト・月曜 4/6/8/10 UTC 建て → +24h・往復 3pip・docs/411)。
変種 = data_ext/events_boj.csv の決定日が火曜である週の月曜ショットだけ 同日 20 UTC 決済(q114.shot(sym,h,20))に置換、他の週は基準と同一。
判定 = docs/244 §1 改良系(IS 2021-10〜2024-12・OOS 2025〜 の両方で Sharpe が基準を上回り最悪月が悪化しない)。参照(判定に使わない): 前窓、決定日が水〜金の週、Mon3/instG への同じ置換、決定日当日の夜間 bps。
⚠ docs/409 §8c で登録前に見た値: 前窓 0.28→0.31・IS 1.37→1.67・OOS 1.10→1.19(最悪週 2022-12-19 を見た後の設計)。
使い方: cd research && python3 -W ignore queue/q175_boj_tuesday_exit20.py <累積>   出力: results/q175_boj_tuesday_exit20.csv・_days.csv"""
import sys
from q_common import *
from q114_mon_index_intraday import shot, stats, improved
HOURS = (4, 6, 8, 10); EXIT = 20
BOJ = pd.to_datetime(pd.read_csv("data_ext/events_boj.csv")["date"])
BOJ_MON = pd.DatetimeIndex(sorted({(d - pd.Timedelta(days=1)).normalize() for d in BOJ if d.dayofweek == 1}))          # 火曜決定 → その月曜
BOJ_MON_OTHER = pd.DatetimeIndex(sorted({(d - pd.Timedelta(days=d.dayofweek)).normalize() for d in BOJ if d.dayofweek >= 2}))   # 水〜金決定 → その週の月曜(参照)
_C = {}
def leg(sym, h, exit_h):
    k = (sym, h, exit_h)
    if k not in _C: _C[k] = shot(sym, h, exit_h)
    return _C[k]
def family(weights, days):
    """days の月曜だけ 同日 20 UTC 決済、他は 24h。days=None で基準。"""
    out = None
    for sym, w in weights.items():
        for h in HOURS:
            b = leg(sym, h, None); v = leg(sym, h, EXIT)
            s = b.copy()
            if days is not None:
                hit = s.index.isin(days); s[hit] = v.reindex(s.index[hit]).values
            s = s * (w / len(HOURS)); out = s if out is None else out.add(s, fill_value=0.0)
    return out.dropna()
W4 = {"AUDJPY": .25, "EURJPY": .25, "GBPJPY": .25, "USDJPY": .25}
W3 = {"EURJPY": .333, "USDJPY": .333, "NZDJPY": .334}
W2 = {"GBPJPY": .537, "AUDJPY": .463}
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q175", cum, 1, "results/q175_boj_tuesday_exit20.csv")
    base, var = family(W4, None), family(W4, BOJ_MON)
    R.add("Mon4 日銀火曜 20 UTC 手仕舞い(改良系)", "Mon4", "火曜決定の週の月曜ショットを同日 20 UTC 決済(他週は 24h・H1 実時刻)", var); R.finish()
    J = improved(base, var); pre_b, pre_v = stats(base, PRE0, IS0), stats(var, PRE0, IS0)
    print(f"\n== Q175 改良判定(Sharpe 週次, 最悪月 %, 累積 %) == 前窓 base {pre_b} var {pre_v} | IS base {J['base_IS']} var {J['var_IS']} | OOS base {J['base_OOS']} var {J['var_OOS']} | 改良系 {'通過' if J['ok'] else '不通過'}")
    print(f"事前値(docs/409 §8c・登録前に閲覧): 前窓 0.28→0.31・IS 1.37→1.67・OOS 1.10→1.19")
    # 参照 1: 対象週の内訳(夜間 = 24h − 同日 20 UTC の差分)
    rows = []
    for d in BOJ_MON:
        if d not in base.index: continue
        rows.append(dict(monday=d.date(), decision=(d + pd.Timedelta(days=1)).date(), r24_bps=round(base[d] * 1e4, 1), r20_bps=round(var[d] * 1e4, 1), night_bps=round((base[d] - var[d]) * 1e4, 1), window="前窓" if d < IS0 else ("IS" if d <= IS1 else "OOS")))
    T = pd.DataFrame(rows); T.to_csv("results/q175_boj_tuesday_exit20_days.csv", index=False)
    print(f"\n== 対象週(火曜決定)n={len(T)}: 24h 平均 {T.r24_bps.mean():.1f} / 20 UTC 平均 {T.r20_bps.mean():.1f} / 夜間平均 {T.night_bps.mean():.1f} bps・夜間が負 {int((T.night_bps<0).sum())}/{len(T)}・2022-12-19 抜き 夜間平均 {T[T.monday.astype(str)!='2022-12-19'].night_bps.mean():.1f} ==")
    print(T.to_string(index=False))
    # 参照 2: 水〜金決定の週と、全週の夜間平均
    allm = base.index; nite = (base - family(W4, allm)) * 1e4
    print(f"\n== 夜間(20 UTC → 翌日建て時刻)平均 bps: 全週 {nite.mean():.1f}(n={len(nite)}) / 火曜決定週 {nite.reindex(BOJ_MON).dropna().mean():.1f}(n={nite.reindex(BOJ_MON).dropna().shape[0]}) / 水〜金決定週 {nite.reindex(BOJ_MON_OTHER).dropna().mean():.1f}(n={nite.reindex(BOJ_MON_OTHER).dropna().shape[0]}) / 日銀なし週 {nite.drop(nite.index.intersection(BOJ_MON.union(BOJ_MON_OTHER))).mean():.1f} ==")
    # 参照 3: Mon3(14074882)・instG Mon2(11988011)への同じ置換
    for nm, w in (("Mon3(14074882)", W3), ("Mon2 instG(11988011)", W2)):
        b2, v2 = family(w, None), family(w, BOJ_MON); j = improved(b2, v2)
        print(f"{nm}: 前窓 {stats(b2, PRE0, IS0)}→{stats(v2, PRE0, IS0)} | IS {j['base_IS']}→{j['var_IS']} | OOS {j['base_OOS']}→{j['var_OOS']} | 形式 {'改善' if j['ok'] else '非改善'}")
    # 参照 4: 水〜金決定の週にも同じ手仕舞いを広げた場合(対象外・参考)
    v3 = family(W4, BOJ_MON.union(BOJ_MON_OTHER)); j3 = improved(base, v3)
    print(f"参考・全日銀週で 20 UTC 手仕舞い: IS {j3['base_IS']}→{j3['var_IS']} | OOS {j3['base_OOS']}→{j3['var_OOS']} | 形式 {'改善' if j3['ok'] else '非改善'}")
