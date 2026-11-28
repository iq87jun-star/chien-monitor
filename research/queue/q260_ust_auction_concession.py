# -*- coding: utf-8 -*-
"""docs/244 Q260(新規・6 セル・2026-11-17 登録「登録して実行」): 米国債の入札日の前後の債券(USTBOND・1 時間足)。
ユーザー 2026-11-17「特定の時点にだけある事情を他に探してください」→ 検証済みの一覧と残りの候補 4 つを提示(おすすめ A = 米国債の入札日)→「登録して実行」。
仕組み(仮説): 入札の前は引き受ける業者が売って備えるので債券が下がり、入札のあとに戻る(入札の値引き)。
入札日程 = 米財務省の公開データ(fiscaldata の auctions_query)から取得した 10 年・20 年・30 年の利付債(物価連動・変動利付を除く・リオープンを含む)→ data_ext/ust_auctions_10y_20y_30y.csv。
T = 入札の締め切り(通常 13:00 米東部時間 = 夏 17 UTC・冬 18 UTC)。建値・決済値は 1 時間足の始値、コストは q.cost(往復 2 bps)。
セル: U1 30 年・入札後の買い [T+1h → T+25h] / U2 30 年・入札前の売り [T−24h → T] / U3 10 年・入札後の買い / U4 10 年・入札前の売り / U5 10・20・30 年まとめ・入札後の買い / U6 同・入札前の売り。
判定(事前固定・新規の標準)= 探索窓のプラス月の二項 p < 0.05 /(累積 + 6)・探索の月数 ≥ 24・OOS の平均 > 0・前窓のプラス月 ≥ 50%。
参照(セル外): T−48h 〜 T+48h の平均の道筋(コストなし)、締め切り直後 1 時間、年限ごとの前 / 後の平均と t。
注意: USTBOND の 1 時間足は 2018-01 から(2018-07〜12 は欠け・2019-02 までは薄い)。10 年の入札の翌日が 30 年の入札になる週が多く、「10 年の入札後」と「30 年の入札前」は同じ時間帯に重なる。
使い方: cd research && PYTHONPATH=queue:. python3 -W ignore queue/q260_ust_auction_concession.py <累積セル数>   出力: results/q260_ust_auction.csv・_ref.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
SYM = "USTBOND"; A = pd.read_csv("data_ext/ust_auctions_10y_20y_30y.csv"); H = pd.Timedelta(hours=1)
A["tc"] = pd.to_datetime(A.auction_date + " " + A.closing_time_comp, format="%Y-%m-%d %I:%M %p").dt.tz_localize("America/New_York").dt.tz_convert("UTC").dt.tz_localize(None); A["term"] = A.original_security_term.str.replace("-Year", " 年")
O = load(SYM)["open"]; PRE1 = IS0 - H; WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); ALLW = WIN + (("全期間", PRE0, END),)
def leg(terms, kind):
    """kind = 'post'(T+1h で買い → T+25h)/ 'pre'(T−24h で売り → T)。戻り値 = コスト後の損益(index = 建てた時刻)。"""
    T = pd.DatetimeIndex(A[A.term.isin(terms)].tc.values); t_in, t_out, d = (T + H, T + 25 * H, 1.0) if kind == "post" else (T - 24 * H, T, -1.0)
    return trades(SYM, t_in, O.reindex(t_in).values, np.full(len(T), d), O.reindex(t_out).values)
def raw(terms, a, b, t0=None, t1=None):
    """コストなしの買いの値動き [T+a h → T+b h]。"""
    T = pd.DatetimeIndex(A[A.term.isin(terms)].tc.values); T = T[(T >= (t0 or PRE0)) & (T <= (t1 or END))]; x = O.reindex(T + b * H).values / O.reindex(T + a * H).values - 1; return pd.Series(x, index=T).dropna()
if __name__ == "__main__":
    cum = int(_ARGV[1]); R = Runner("Q260", cum, 6, "results/q260_ust_auction.csv"); ref = []; S = {}
    CELLS = [("U1 30 年・入札後の買い [T+1h → T+25h]", ["30 年"], "post"), ("U2 30 年・入札前の売り [T−24h → T]", ["30 年"], "pre"), ("U3 10 年・入札後の買い", ["10 年"], "post"), ("U4 10 年・入札前の売り", ["10 年"], "pre"), ("U5 10・20・30 年まとめ・入札後の買い", ["10 年", "20 年", "30 年"], "post"), ("U6 10・20・30 年まとめ・入札前の売り", ["10 年", "20 年", "30 年"], "pre")]
    for nm, terms, kind in CELLS: x = leg(terms, kind); S[nm] = x; R.add("UstAuction", SYM, nm, x)
    D = R.finish()
    print("\n== 窓ごと(回数・1 回の平均 bps・勝率・t。コスト後) ==")
    for nm, x in S.items(): print("  " + nm + ": " + " | ".join(f"{w} n={len(y)} {y.mean() * 1e4:+.1f}bps {100 * (y > 0).mean():.0f}% t={y.mean() / y.std() * np.sqrt(len(y)):.2f}" for w, a, b in ALLW for y in [x[(x.index >= a) & (x.index <= b)]] if len(y) > 2))
    for terms, lab in ((["30 年"], "30 年"), (["10 年"], "10 年"), (["20 年"], "20 年")):
        for w, a, b in ALLW:
            for seg, (h0, h1) in (("T−48h → T−24h", (-48, -24)), ("T−24h → T(入札前)", (-24, 0)), ("T → T+1h(結果の直後)", (0, 1)), ("T+1h → T+25h(入札後)", (1, 25)), ("T+25h → T+49h", (25, 49))):
                y = raw(terms, h0, h1, a, b); ref.append(dict(term=lab, window=w, segment=seg, n=len(y), mean_bps=round(float(y.mean()) * 1e4, 1) if len(y) else None, up_pct=round(float((y > 0).mean()) * 100, 0) if len(y) else None, t=round(float(y.mean() / y.std() * np.sqrt(len(y))), 2) if len(y) > 2 else None))
    RF = pd.DataFrame(ref); RF.to_csv("results/q260_ust_auction_ref.csv", index=False); pd.set_option("display.width", 300); pd.set_option("display.max_rows", 200)
    print("\n== 参照: 買いの値動き(コストなし・bps)と t =="); print(RF.pivot_table(index=["term", "segment"], columns="window", values=["mean_bps", "t", "n"], aggfunc="first", sort=False).to_string())
    # 対照: 入札の無い同じ曜日・同じ時刻(水・木の 17/18 UTC)の 24 時間
    allT = set(pd.DatetimeIndex(A.tc.values)); cand = O.index[(O.index.dayofweek.isin([1, 2, 3])) & (O.index.hour.isin([17, 18]))]; cand = pd.DatetimeIndex([t for t in cand if (t.hour == (17 if 3 < t.month < 11 else 18)) and t not in allT and (t - 24 * H) not in allT and (t + 24 * H) not in allT])
    y = (O.reindex(cand + 25 * H).values / O.reindex(cand + H).values - 1); y = pd.Series(y, index=cand).dropna(); print(f"\n対照(入札の前後 1 日に当たらない火〜木の同じ時刻・T+1h → T+25h・コストなし): n={len(y)} 平均 {y.mean() * 1e4:+.1f} bps・t {y.mean() / y.std() * np.sqrt(len(y)):.2f}")
