# -*- coding: utf-8 -*-
"""docs/244 Q219(改良系・3 セル・2026-11-15 登録): 月曜の円クロス(配備形 Mon4)に火曜の建て(同じ時刻・24 時間)を混ぜる。合計の数量は 1.0。
V1: 月 0.75 + 火 0.25。V2: 月 0.5 + 火 0.5。V3: 火曜だけ 1.0。週単位で集計(火曜は同じ週の月曜の日付に寄せる)。コストは別々に引く。
判定 = 縮小なしの Mon4 に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない(事後の着想なので 3 窓)。
使い方: cd research && python3 -W ignore queue/q219_mon4_plus_tuesday.py <累積セル数>   出力: results/q219_mon4_plus_tuesday.csv・_diag.csv"""
import sys, os
from q_common import *
from q147_roll_rate_diff_gate import stats
from q194_mon_own_technical_state_gate import PAIRS, states
from q218_mon4_what_changed_2020 import shots
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END))
def legs(tilt=False):
    """週(月曜の日付)ごとの Mon4・Tue4 の束(各通貨 0.25)。tilt = 200 日線の下 1.0・上 0.5(建ての前の最後の確定日足)。"""
    out = {}
    for d in (0, 1):
        tot = None
        for s in PAIRS:
            x = shots(s, d)
            if tilt: st = states(s).sma200.shift(1).reindex(x.index, method="ffill"); x = x * np.where(st.isna(), 1.0, np.where(st < 0, 1.0, 0.5))
            x = x.copy(); x.index = x.index - pd.Timedelta(days=d); tot = (x * 0.25) if tot is None else tot.add(x * 0.25, fill_value=0.0)
        out[d] = tot
    idx = out[0].index.union(out[1].index); return out[0].reindex(idx).fillna(0.0), out[1].reindex(idx).fillna(0.0)
def mon_tue(w_tue=0.5, tilt=False):
    """紙上候補用: 月 (1 − w) + 火 w の週次系列。"""
    m, t = legs(tilt); return m * (1 - w_tue) + t * w_tue
if __name__ == "__main__":
    cum = int(sys.argv[1]); N = 3; m, t = legs(False); rows = []; bs = {k: stats(m, a, b) for k, a, b in WIN}
    for lab, w in (("V1 月 0.75 + 火 0.25", 0.25), ("V2 月 0.5 + 火 0.5", 0.5), ("V3 火曜だけ", 1.0)):
        v = m * (1 - w) + t * w; vs = {k: stats(v, a, b) for k, a, b in WIN}
        rows.append(dict(cell=lab, base_PRE=bs["前窓"], var_PRE=vs["前窓"], base_IS=bs["IS"], var_IS=vs["IS"], base_OOS=bs["OOS"], var_OOS=vs["OOS"], sharpe_up_3win=bool(all(vs[k][0] > bs[k][0] for k, _, _ in WIN)), improved=bool(all(vs[k][0] > bs[k][0] and vs[k][1] >= bs[k][1] for k, _, _ in WIN))))
    D = pd.DataFrame(rows); D.to_csv("results/q219_mon4_plus_tuesday.csv", index=False); pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 300)
    print(f"Q219: cells={N} cum_before={cum} cum_after={cum + N} improved={int(D.improved.sum())}/{N}  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)"); print(D.to_string(index=False))
    diag = []
    for k, a, b in WIN:
        mm, tt = m[(m.index >= a) & (m.index <= b)], t[(t.index >= a) & (t.index <= b)]
        diag.append(dict(window=k, weeks=len(mm), mon_bps=round(float(mm.mean()) * 1e4, 2), tue_bps=round(float(tt.mean()) * 1e4, 2), mon_win=round(float((mm > 0).mean()) * 100, 1), tue_win=round(float((tt > 0).mean()) * 100, 1), tue_t=round(float(tt.mean() / tt.std() * np.sqrt(len(tt))), 2), corr_mon_tue=round(float(mm.corr(tt)), 3), mon_sd_bps=round(float(mm.std()) * 1e4, 1), tue_sd_bps=round(float(tt.std()) * 1e4, 1)))
    G = pd.DataFrame(diag); G.to_csv("results/q219_mon4_plus_tuesday_diag.csv", index=False); print("\n== 診断: 月曜 / 火曜の束(週あたり・コスト後) =="); print(G.to_string(index=False))
    mt, tt_ = legs(True); print("\n== 参考: 200 日線の縮小(下 1.0・上 0.5)を両方に掛けた場合 ==")
    for lab, w in (("月だけ(配備形)", 0.0), ("月 0.75 + 火 0.25", 0.25), ("月 0.5 + 火 0.5", 0.5), ("火だけ", 1.0)): v = mt * (1 - w) + tt_ * w; print(f"  {lab}: ", {k: stats(v, a, b)[:3] for k, a, b in WIN})
    print("\n年ごとの火曜の束 %:", (t.groupby(t.index.year).sum() * 100).round(2).to_dict())
