# -*- coding: utf-8 -*-
"""Q141(診断・セル 0): MFFU に 6J(USDJPY 月曜セッション LONG = 6J 売り・日曜 22 UTC → 月曜 20 UTC)を足すと評価・出金が改善するか。
指数(13→20 UTC)と 6J を同じ日の時間足経路に重ね、q139 の経路 MC(日中の含み損で判定)に通す。6J の名目は指数と同リスク(週次 σ 一致)を基準に配分。"""
import json, sys
sys.argv = ["q139"]
import q139_futures_prop_firms as M
from q_common import load, pd, np
o = load("USDJPY")["open"]
hrs = list(range(22, 24)) + list(range(0, 21))     # 日曜 22 UTC 〜 月曜 20 UTC
J = {}
for t in o.index[(o.index.dayofweek == 6) & (o.index.hour == 22)]:
    base = o[t]; row = []
    for k in range(1, 23):
        x = o.get(t + pd.Timedelta(hours=k)); row.append(np.nan if x is None else x / base - 1)
    J[(t + pd.Timedelta(hours=2)).normalize()] = row
idx_days = list(M.PD)
Pidx = M.P.copy()                                   # (週, 7) = 月曜 14..20 UTC
rows = []
for i, d in enumerate(idx_days):
    j = J.get(d)
    if j is None or any(np.isnan(j)): rows.append(None); continue
    rows.append(j)
ok = [r is not None for r in rows]
JP = np.array([r for r in rows if r is not None]); IP = Pidx[np.array(ok)]
sj = JP[:, -1].std(); si = IP[:, -1].std(); k = si / sj
print(f"週 {len(JP)}・相関 {np.corrcoef(JP[:, -1], IP[:, -1])[0, 1]:+.2f}・σ 指数 {si:.4f} 6J {sj:.4f}")
def build(w_idx, w_j):
    # 22 時点: 日曜 22 UTC の 1h 後(23)〜月曜 20 UTC。指数は 13 UTC まで 0、14..20 で IP
    out = np.zeros((len(JP), 22))
    out += w_j * k * JP - np.r_[np.zeros(21), 1e-4 * w_j * k]      # 6J コスト 1 bps
    out[:, 15:] += w_idx * IP                                       # 月曜 14..20 UTC は列 15..21
    return out
F = json.load(open("queue/q139_firms.json", encoding="utf-8"))[0]
res = []
for lab, wi, wj in [("指数のみ ×1.0(現行)", 1.0, 0.0), ("指数 ×0.7 + 6J ×0.7", 0.7, 0.7), ("指数 ×1.0 + 6J ×0.5", 1.0, 0.5), ("指数 ×1.0 + 6J ×1.0", 1.0, 1.0), ("6J のみ ×1.0", 0.0, 1.0)]:
    M.P = build(wi, wj); d = M.sim(dict(F, name=lab), n=8000)
    res.append(dict(構成=lab, 週平均=round(M.P[:, -1].mean() * M.N150), 週σ=round(M.P[:, -1].std() * M.N150), 評価通過=round(d["eval_pass"], 3), 出金あり=round(d["pay_any"], 3),
                    Live=round(d["live"], 3), 期待手取り=round(d["net"]), 上位16=round(d["net_p84"])))
R = pd.DataFrame(res); print(R.to_string(index=False)); R.to_csv("results/q141_mffu_add_6j.csv", index=False)
