# -*- coding: utf-8 -*-
"""docs/244 Q172(新規 5 セル・2026-11-08 ユーザー「登録実行お願いします」): ペア回帰(統計的裁定)。
ペア: (GBPJPY, EURJPY)(AUDJPY, NZDJPY)(US500, NAS100)(GER40, EUSTX50)(XAUUSD, XAGUSD)。日次(FX は 21 UTC・米指数と金属は 20 UTC・欧州指数は 19 UTC の足始値 = 各市場の最終足)の対数比 r = ln(A/B)、
z = (r − 60 日移動平均)/60 日移動標準偏差。|z| > 2 で割高側 SHORT・割安側 LONG(各 0.5 名目)、z が 0 を横切るか 10 営業日で決済。重複建てなし(決済まで次の建てを待つ)。
コスト: 各レグ q_common.cost(FX 往復 3pip・指数/金属 IDX_COST / NONFX_COST)。損益は建て日に置く。データ: data_dukascopy H1(2018-01〜・前窓 2018-01〜2021-09)。判定: docs/244 §1 標準。
使い方: cd research && python3 queue/q172_pairs_reversion.py <累積>   出力: results/q172_pairs_reversion.csv"""
import sys
from q_common import *
WIN = 60; Z = 2.0; MAXD = 10
PAIRS = [("GBPJPY", "EURJPY", 21), ("AUDJPY", "NZDJPY", 21), ("US500", "NAS100", 20), ("GER40", "EUSTX50", 19), ("XAUUSD", "XAGUSD", 20)]
def daily_open(sym, h):
    o = load(sym)["open"]; o = o[o.index.hour == h]; o.index = o.index.normalize(); return o[~o.index.duplicated(keep="last")]
def pair(a, b, H):
    oa, ob = daily_open(a, H), daily_open(b, H); j = oa.index.intersection(ob.index); oa, ob = oa[j], ob[j]
    r = np.log(oa / ob); z = (r - r.rolling(WIN).mean()) / r.rolling(WIN).std()
    t_in, out = [], []; i = WIN
    days = j
    while i < len(days) - 1:
        zi = z.iloc[i]
        if np.isnan(zi) or abs(zi) < Z: i += 1; continue
        d = -np.sign(zi)   # z>0 = A 割高 → A SHORT・B LONG
        k = i + 1
        while k < len(days) and k - i < MAXD and np.sign(z.iloc[k]) == np.sign(zi): k += 1
        if k >= len(days): break
        ra = d * (oa.iloc[k] / oa.iloc[i] - 1) - cost(a, oa.iloc[i]); rb = -d * (ob.iloc[k] / ob.iloc[i] - 1) - cost(b, ob.iloc[i])
        t_in.append(days[i]); out.append(0.5 * (float(ra) + float(rb))); i = k
    s = pd.Series(out, index=pd.DatetimeIndex(t_in) + pd.Timedelta(hours=H)); return s[s.index >= PRE0], z
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q172", cum, len(PAIRS), "results/q172_pairs_reversion.csv"); info = []
    for a, b, H in PAIRS:
        s, z = pair(a, b, H); R.add("ペア回帰", f"{a}/{b}", f"ln({a}/{b}) z60>2 逆張り・0 横切り or 10 日・各 0.5", s)
        hold = []  # 参考: 建て数・|z| 分布
        info.append(dict(pair=f"{a}/{b}", trades=len(s), per_year=round(len(s) / max((s.index[-1] - s.index[0]).days / 365, 1e-9), 1), mean_bps=round(float(s.mean()) * 1e4, 2), win=round(float((s > 0).mean()), 3), z_abs_gt2_share=round(float((z.abs() > Z).mean()), 3), z_ac1=round(float(z.dropna().autocorr(1)), 3)))
    R.finish(); print("\n参考:"); print(pd.DataFrame(info).to_string(index=False))
