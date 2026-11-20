# -*- coding: utf-8 -*-
"""docs/244 Q266(2026-11-17 登録「登録実行」・診断 + 改良系 2 セル): 荒れた週の「週明けの開場から月曜の夜まで」の指数。
ユーザー 2026-11-17「何か新案はありそうですか」→ 案を提示 →「登録実行」。判定の 2 本は内訳を見る前に docs/244 で固定した。
診断(セル 0): 指数 5 本を荒れた週(前金曜の VIX > 25)と静かな週に分け、
    金曜 20 UTC → 日曜 23 UTC(週末の窓)・日曜 23 → 月曜 07・月曜 07 → 13・月曜 13 → 20・月曜 20 → 火曜 13 UTC の平均と t(費用なし)。
A1 = 荒れた週だけ、日曜 23:00 UTC の足の始値で 5 本を買い、火曜 13:00 UTC に決済(1 往復)。
A3 = 荒れた週だけ、日曜 23:00 UTC → 月曜 13:00 UTC と 月曜 20:00 UTC → 火曜 13:00 UTC(2 往復・費用も 2 回分)。
判定 = 「配備形 + いまの夜の指数 5 本(合計 0.25)」に対する 3 窓(Sharpe が 3 窓とも上・最悪月が悪化しない)。
共通: 5 本の等分・合計 0.25。費用 q_common.cost(1 往復ごと)。損切りなし。日曜 23 UTC の足が無い週・銘柄は、その銘柄だけいまの形(月曜 20 → 火曜 13)に戻す。
参照(判定しない): 配備形だけに対する 3 窓・月曜 13 UTC 建て → 火曜 13 UTC・日曜の夜の往復の費用を 2 倍にした場合。
使い方: cd research && PYTHONPATH=queue:. python3 -W ignore queue/q266_hot_week_open_to_monday_night_index.py <累積セル数>   出力: results/q266_hot_week_open.csv・_anatomy.csv"""
import sys
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
from q240_weekend_premium_predictions import frame, series
from q265_weekend_btc_signal_and_night_index_anatomy import night_all, hotflag, bundle_night, IDX5, WIN, H
WEEKS = pd.date_range("2016-01-04", "2026-12-28", freq="7D"); HOT = hotflag(WEEKS)
def leg(sym, h0, h1, cmult=1.0):
    """月曜 00:00 UTC から数えて h0 時 → h1 時の買い(費用後)。index = 月曜。足が無い週は NaN。"""
    o = load(sym)["open"]; p0 = o.reindex(WEEKS + h0 * H).values; p1 = o.reindex(WEEKS + h1 * H).values
    return pd.Series(p1 / p0 - 1 - cmult * cost(sym, p0), index=WEEKS)
def bundle(kind, total=0.25, cmult=1.0):
    """荒れた週の 5 本の束。kind: A1 / A3 / A2(参照)。早い足が無い週・銘柄はいまの形に戻す。"""
    out = None; n = None; early = 0; fb = 0
    for s in IDX5:
        b = night_all(s).reindex(WEEKS)                                  # いまの形(月曜 20 → 火曜 13・費用後)
        if kind == "A1": v = leg(s, -1, 37, cmult)
        elif kind == "A3": v = leg(s, -1, 13, cmult) + b
        else: v = leg(s, 13, 37)
        x = v.where(v.notna() & b.notna(), b)                            # 早い足が無い(または決済の足が無い)週はいまの形
        x = x[HOT.values].dropna(); early += int((v.notna() & b.notna())[HOT.values].sum()); fb += int((v.isna() & b.notna())[HOT.values].sum())
        out = x if out is None else out.add(x, fill_value=0.0); c = pd.Series(1.0, index=x.index); n = c if n is None else n.add(c, fill_value=0.0)
    return (out / n) * total, early, fb
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 2; rows = []; ref = []; P = frame(); B = series(P, "base")
    NB = bundle_night(IDX5, HOT, 0.25); REF = B.add(NB, fill_value=0.0); rs = {w: stats(REF, a, b) for w, a, b in WIN}; bs = {w: stats(B, a, b) for w, a, b in WIN}
    def judge(v, base): vs = {w: stats(v, a, b) for w, a, b in WIN}; return vs, all(vs[w][0] > base[w][0] and vs[w][1] >= base[w][1] for w, _, _ in WIN)
    def row(part, nm, x, extra=""):
        vs, ok = judge(B.add(x, fill_value=0.0), rs); _, okb = judge(B.add(x, fill_value=0.0), bs); t = float(x.mean() / x.std() * np.sqrt(len(x))) if len(x) > 2 else 0.0
        seg = " / ".join(f"{x[(x.index >= a) & (x.index <= b)].mean() / 0.25 * 1e4:+.0f}({int(((x.index >= a) & (x.index <= b)).sum())})" for w, a, b in WIN)
        rows.append(dict(part=part, cell=nm, 前窓=str(vs["前窓"][:3]), IS=str(vs["IS"][:3]), OOS=str(vs["OOS"][:3]), verdict=("成立" if ok else "不成立") if part == "判定" else f"(参照)夜の指数つきを 3 窓で上回る = {ok}", 配備形だけに対して=okb, 束の平均bps_前窓_IS_OOS=seg, 全期間bps=round(float(x.mean()) / 0.25 * 1e4, 1), t=round(t, 2), note=extra))
    rows.append(dict(part="基準", cell="配備形 Mon4", 前窓=str(bs["前窓"][:3]), IS=str(bs["IS"][:3]), OOS=str(bs["OOS"][:3]), verdict="", note=""))
    row("基準", "配備形 + いまの夜の指数 5 本(月曜 20 → 火曜 13)", NB, f"荒れた週 {len(NB)}")
    rows[-1]["verdict"] = "(判定の基準)"
    for k, nm in (("A1", "A1 日曜 23 UTC → 火曜 13 UTC(持ち通し)"), ("A3", "A3 日曜 23 → 月曜 13 と 月曜 20 → 火曜 13(2 回)")):
        x, e, f = bundle(k); row("判定", nm, x, f"早い足で建てた銘柄・週 {e}・いまの形に戻した {f}")
    x, e, f = bundle("A2"); row("参照", "月曜 13 UTC → 火曜 13 UTC(24 時間)", x, f"銘柄・週 {e}")
    for k in ("A1", "A3"):
        x, e, f = bundle(k, cmult=2.0); row("参照", f"{k} で日曜の夜の往復の費用を 2 倍", x, "")
    # 診断: 時間帯の内訳(費用なし)。銘柄ごと + 5 本の週平均(t は週の数で数える)
    SEG = (("金20→日23(週末の窓)", -52, -1), ("日23→月07", -1, 7), ("月07→13", 7, 13), ("月13→20", 13, 20), ("月20→火13(いまの形)", 20, 37), ("日23→月13(A3 の前半)", -1, 13))
    raw = {}
    for s in IDX5:
        o = load(s)["open"]
        for nm, h0, h1 in SEG: raw[(s, nm)] = pd.Series(o.reindex(WEEKS + h1 * H).values / o.reindex(WEEKS + h0 * H).values - 1, index=WEEKS)
    def cellf(x): x = x.dropna(); return f"{x.mean() * 1e4:+.1f}(t {x.mean() / x.std() * np.sqrt(len(x)):.1f}・{len(x)})" if len(x) > 2 and x.std() > 0 else "—"
    for grp, m in (("荒れた週", HOT.values), ("静かな週", ~HOT.values)):
        for s in IDX5 + ["5 本の週平均"]:
            r_ = dict(group=f"{s}・{grp}")
            for nm, _, _ in SEG:
                x = raw[(s, nm)] if s in IDX5 else pd.concat([raw[(q, nm)] for q in IDX5], axis=1).mean(axis=1, skipna=True)
                r_[nm] = cellf(x[m])
            ref.append(r_)
    # 荒れた週の 5 本の週平均を窓ごとに(符号の安定)
    for nm, _, _ in SEG:
        x = pd.concat([raw[(q, nm)] for q in IDX5], axis=1).mean(axis=1, skipna=True)[HOT.values].dropna(); r_ = dict(group=f"荒れた週・5 本の週平均・{nm}")
        for w, a, b in WIN: y = x[(x.index >= a) & (x.index <= b)]; r_[w] = f"{y.mean() * 1e4:+.1f}({len(y)})" if len(y) else "—"
        r_["プラスの週の割合"] = f"{(x > 0).mean() * 100:.0f}%"; ref.append(r_)
    D = pd.DataFrame(rows); RF = pd.DataFrame(ref); D.to_csv("results/q266_hot_week_open.csv", index=False); RF.to_csv("results/q266_hot_week_open_anatomy.csv", index=False)
    pd.set_option("display.width", 360); pd.set_option("display.max_colwidth", 70); pd.set_option("display.max_rows", 100)
    print(f"\n== Q266(累積セル {cum} + {N} = {cum + N}) =="); print(D.fillna("").to_string(index=False)); print("\n== 診断: 時間帯の内訳(費用なし・bps) =="); print(RF.fillna("").to_string(index=False))
