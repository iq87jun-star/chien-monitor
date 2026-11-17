# -*- coding: utf-8 -*-
"""docs/244 Q259(新規・6 セル・2026-11-17 登録「登録して実行」): 「下げた通貨の戻り」を月曜以外(火〜木)で取れるか。主体の時間軸を週 1 回から毎日に替える検証。
ユーザー 2026-11-17「主体の時間軸を変えた場合にトレード機会を創出する事につながりませんか」→ 未検証の主軸として提示 →「登録して実行」。
形は月曜の配備形と同じ: 円クロス 4 本(GBPJPY・EURJPY・AUDJPY・USDJPY 各 0.25)・その日の 4 / 6 / 8 / 10 UTC の始値で買い → 24 時間後の始値で決済・往復 3 pip。金曜は 24 時間後の足が無いので対象外。
条件(その日より前の最後の日足): B = 終値 < 200 日線。C = B かつ 5 日前より安い(まだ下げている)。C20 = B かつ 終値 < 20 日線。条件に当たる通貨だけ建てる(当たらない通貨は 0)。
セル: N1 火〜木まとめ × C / N2 火〜木まとめ × C20 / N3 火〜木まとめ × B / N4 火曜 × C / N5 水曜 × C / N6 木曜 × C。
判定(事前固定・新規の標準)= 探索窓のプラス月の二項 p < 0.05 /(累積 + 6)・探索の月数 ≥ 24・OOS の平均 > 0・前窓のプラス月 ≥ 50%。
参照(セル外): 同じ条件の月曜・条件なしの各曜日・条件ごと × 曜日ごとの 1 建てあたりの平均、3 窓の Sharpe、月曜(配備形)との週次の相関。
使い方: cd research && PYTHONPATH=queue:. python3 -W ignore queue/q259_jpy_cross_dip_rebound_tue_thu.py <累積セル数>   出力: results/q259_dip_rebound_tue_thu.csv・_ref.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q194_mon_own_technical_state_gate import states
MON4 = ["GBPJPY", "EURJPY", "AUDJPY", "USDJPY"]; HOURS = (4, 6, 8, 10); H24 = pd.Timedelta(hours=24); DOW = {0: "月曜", 1: "火曜", 2: "水曜", 3: "木曜"}
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); ALLW = WIN + (("全期間", PRE0, END),)
def frame():
    rows = []
    for s in MON4:
        o = load(s)["open"]; acc = None; cnt = None
        for hh in HOURS:
            t = o.index[(o.index.dayofweek <= 3) & (o.index.hour == hh)]; t = t[(t + H24).isin(o.index)]; p0 = o.reindex(t).values; r = pd.Series(o.reindex(t + H24).values / p0 - 1 - cost(s, p0), index=t.normalize())
            acc = r if acc is None else acc.add(r, fill_value=0.0); c1 = pd.Series(1.0, index=r.index); cnt = c1 if cnt is None else cnt.add(c1, fill_value=0.0)
        m = pd.DataFrame({"r": acc / len(HOURS), "shots": cnt}).sort_index(); m = m[m.index >= PRE0]; S = states(s).shift(1).reindex(m.index, method="ffill")
        m["sym"] = s; m["dow"] = m.index.dayofweek; m["B"] = (S.sma200 < 0).fillna(False).values; m["C"] = m.B & (S.wk < 0).fillna(False).values; m["C20"] = m.B & (S.sma20 < 0).fillna(False).values; rows.append(m)
    return pd.concat(rows).sort_index(kind="stable")
def bundle(P, cond, dows):
    """条件に当たる通貨だけ 0.25 ずつ建てた束の日次損益(index = 建てた日)。条件 None = 全通貨。"""
    z = P[P.dow.isin(dows)]; z = z if cond is None else z[z[cond]]; return (z.r * 0.25).groupby(level=0).sum()
def wk(x): return x.groupby(x.index - pd.to_timedelta(x.index.dayofweek, unit="D")).sum()
def sh(x, a, b):
    y = wk(x); y = y[(y.index >= a) & (y.index <= b)]; m = y.groupby(pd.PeriodIndex(y.index, freq="M")).sum()
    return f"{y.mean() / y.std() * np.sqrt(52):.2f} / {m.min() * 100:.2f} / {y.sum() * 100:+.1f}" if len(y) > 5 and y.std() > 0 else "—"
if __name__ == "__main__":
    cum = int(_ARGV[1]); P = frame(); R = Runner("Q259", cum, 6, "results/q259_dip_rebound_tue_thu.csv"); ref = []
    CELLS = [("N1 火〜木 × 線の下 かつ 5 日前より安い", "C", [1, 2, 3]), ("N2 火〜木 × 線の下 かつ 20 日線より下", "C20", [1, 2, 3]), ("N3 火〜木 × 線の下", "B", [1, 2, 3]), ("N4 火曜 × 線の下 かつ 5 日前より安い", "C", [1]), ("N5 水曜 × 線の下 かつ 5 日前より安い", "C", [2]), ("N6 木曜 × 線の下 かつ 5 日前より安い", "C", [3])]
    S = {}
    for nm, cond, dows in CELLS: x = bundle(P, cond, dows); S[nm] = x; R.add("DipReboundTueThu", "JPY4", nm, x)
    D = R.finish(); MONB = bundle(P.assign(w=np.where(P.B, 1.0, 0.5)).assign(r=lambda z: z.r * z.w), None, [0]); mw = wk(MONB)
    print("\n== 3 窓(週でまとめた Sharpe / 最悪月 % / 累積 %)と、月曜の配備形との週次の相関 ==")
    for nm, x in list(S.items()) + [("参照: 月曜の配備形(200 日線の下 1.0・上 0.5)", MONB), ("参照: 月曜 × 線の下 かつ 5 日前より安い", bundle(P, "C", [0])), ("参照: 火〜木 × 条件なし", bundle(P, None, [1, 2, 3]))]:
        c = wk(x).reindex(mw.index).fillna(0.0).corr(mw); print(f"  {nm}: " + " | ".join(f"{w} {sh(x, a, b)}" for w, a, b in WIN) + f" | 月曜との相関 {c:+.2f} | 建てた日数 {int((x != 0).sum())}")
    for w, a, b in ALLW:
        z = P[(P.index >= a) & (P.index <= b)]
        for d, dn in DOW.items():
            for g, m in (("条件なし", z.dow == d), ("線の下", (z.dow == d) & z.B), ("線の下 × 5 日前より安い", (z.dow == d) & z.C), ("線の下 × 5 日前より高い", (z.dow == d) & z.B & ~z.C), ("線の上", (z.dow == d) & ~z.B)):
                y = z.r[m]; dm = y.groupby(level=0).mean(); ref.append(dict(window=w, dow=dn, group=g, n=len(y), mean_bps=round(float(y.mean()) * 1e4, 1) if len(y) else None, win=round(float((y > 0).mean()) * 100, 0) if len(y) else None, t_day=round(float(dm.mean() / dm.std() * np.sqrt(len(dm))), 2) if len(dm) > 2 and dm.std() > 0 else None))
    RF = pd.DataFrame(ref); RF.to_csv("results/q259_dip_rebound_tue_thu_ref.csv", index=False); pd.set_option("display.width", 300); pd.set_option("display.max_rows", 200)
    print("\n== 参照: 1 建て(通貨 × 日・1 倍・24h)の平均 bps と、日でまとめた t =="); print(RF.pivot_table(index=["group", "dow"], columns="window", values=["mean_bps", "t_day"], aggfunc="first", sort=False).to_string())
