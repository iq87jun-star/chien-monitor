# -*- coding: utf-8 -*-
"""
regime_monitor.py — B-6(docs/99): 「現行レジーム終了」の早期警報モニタ(月次実行)。

背景(docs/84,86): v4/v7/E-Mon は全て「2016年以降の現行レジーム現象」と確定済み。
  検証級を上げる手段は消尽し、残る生命線は ①フォワード採点 ②年次生存確認 ③本モニタ。
  docs/86 §2 の推奨「直近24ヶ月ローリングnetの符号監視」を運用スクリプト化する。

★警報条件(事前定義・変更は事前登録扱いでdocs更新が必要):
  - GREEN : 24Mローリングnet > 0
  - YELLOW: 24Mローリングnet ≤ 0 が当月末に発生(初回)
      → 行動: 該当スリーブの新規サイズを50%に落とす(EA入力の該当リスク%を半分)。翌月再判定。
  - RED   : 24Mローリングnet ≤ 0 が2ヶ月末連続
      → 行動: 該当スリーブを新規停止(建玉は自然決済)。復帰は「24M netが正へ回復」まで。
  - 補助指標(警報には使わない・参考のみ): 12Mローリングnet、直近36M相関ドリフト(docs/101)。

⚠ データはYahoo日足近似(実行日までのローリング窓)。絶対値でなく【符号】だけを使う設計
  なので近似の影響は小さいが、YELLOW/RED発火時は必ずDrive(Dukascopy)で再確認してから行動する。
使い方: 毎月初に `python3 research/regime_monitor.py` → 表とresults/regime_monitor.jsonを確認。
"""
import os, sys, json, csv, time, urllib.request, urllib.parse, datetime as dt
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")

P1 = 1451606400   # 2016-01-01(系列構築に十分な履歴)
SYMBOLS = {
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X", "AUDUSD": "AUDUSD=X",
    "USDCHF": "USDCHF=X", "USDCAD": "USDCAD=X", "NZDUSD": "NZDUSD=X",
    "EURJPY": "EURJPY=X", "GBPJPY": "GBPJPY=X",
    "XAUUSD": "GC=F", "US500": "^GSPC", "NAS100": "^IXIC", "GER40": "^GDAXI",
}
ROLL = 24
CONSEC_RED = 2


def fetch_all(p2=None):
    p2 = p2 or int(time.time())
    os.makedirs(DATA, exist_ok=True)
    for name, sym in SYMBOLS.items():
        u = (f"https://query2.finance.yahoo.com/v8/finance/chart/"
             f"{urllib.parse.quote(sym)}?interval=1d&period1={P1}&period2={p2}")
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        d = json.loads(urllib.request.urlopen(req, timeout=25).read())
        r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
        rows = []
        for i, t in enumerate(ts):
            o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
            if None in (o, h, l, c):
                continue
            rows.append((dt.datetime.fromtimestamp(t, dt.timezone.utc).replace(tzinfo=None)
                         .strftime("%Y-%m-%d %H:%M:%S"), o, h, l, c))
        p = os.path.join(DATA, f"{name}_d.csv")
        with open(p, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["timestamp", "open", "high", "low", "close"]); w.writerows(rows)
        time.sleep(0.6)


def build_series():
    from parallel_vs_existing_compare import v7_monthly, v4_monthly, e5_monthly
    import edge_regime_gate_10y as RG
    def to_m(w):
        s = w.copy(); s.index = pd.to_datetime(s.index).to_period("M"); return s.groupby(level=0).sum()
    out = {
        "v4": v4_monthly(),
        "v7": v7_monthly(),
        "E-Mon[RG3]": to_m(RG.emon_weekly_gated("riskoff")).rename("E-Mon[RG3]"),
        "E5(参考)": e5_monthly(),
    }
    # 間引き版(docs/135/133・配備予定の定義)も監視対象に追加(docs/150)
    try:
        from portfolio_daily_compare import mon_daily
        from policy_prune_symbols import e5_basket
        def d_to_m(d):
            mk = pd.PeriodIndex(d.index, freq="M")
            return pd.Series({k: float((1 + d[mk == k]).prod() - 1) for k in mk.unique()}).sort_index()
        out["v7p(2クロス・配備予定)"] = d_to_m(mon_daily(["EURJPY", "GBPJPY"]))
        out["E5p(2資産・配備予定)"] = d_to_m(e5_basket(["XAUUSD", "NAS100"]))
    except Exception as e:
        print(f"⚠ 間引き版系列の構築に失敗(監視は現行4系列のみ): {e}")
    return out


def judge(roll_net_by_month):
    """月末ごとの24M netから状態を判定。RED=直近CONSEC_RED回連続で<=0。"""
    s = roll_net_by_month.dropna()
    if len(s) == 0:
        return "NO_DATA", 0
    neg_streak = 0
    for v in s.values[::-1]:
        if v <= 0:
            neg_streak += 1
        else:
            break
    if neg_streak >= CONSEC_RED:
        return "RED", neg_streak
    if neg_streak == 1:
        return "YELLOW", neg_streak
    return "GREEN", neg_streak


def main():
    print("[1/2] データ取得(2016-01〜実行日)")
    fetch_all()
    print("[2/2] 24ヶ月ローリングnetの符号判定")
    series = build_series()
    asof = None
    out = dict(rule=dict(roll_months=ROLL, red_consecutive=CONSEC_RED,
                         yellow_action="該当スリーブの新規サイズ50%へ(翌月再判定)",
                         red_action="該当スリーブ新規停止(24M net回復まで)",
                         note="発火時はDrive/Dukascopyで再確認してから行動(Yahoo近似)"),
               sleeves={})
    rows = []
    for name, s in series.items():
        s = s.dropna()
        # 進行中の当月は月末未確定=判定から除外
        cur = pd.Period(dt.date.today(), freq="M")
        s_closed = s[s.index < cur]
        roll = s_closed.rolling(ROLL).sum()
        state, streak = judge(roll)
        last = roll.dropna()
        asof = str(last.index[-1]) if len(last) else "n/a"
        hist_neg = int((last <= 0).sum())
        rows.append(dict(sleeve=name, state=state, neg_streak=streak,
                         roll24_net_pct=round(float(last.iloc[-1] * 100), 2) if len(last) else None,
                         roll12_net_pct=round(float(s_closed.rolling(12).sum().dropna().iloc[-1] * 100), 2),
                         months_neg_in_history=hist_neg, months_total=int(len(last))))
        out["sleeves"][name] = rows[-1]
    out["asof_month"] = asof
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    warn = [r for r in rows if r["state"] != "GREEN" and "参考" not in r["sleeve"]]
    if warn:
        print("\n⚠⚠ 警報あり → Drive再確認の上、事前定義の行動(YELLOW=半減/RED=停止)を実施 ⚠⚠")
    else:
        print("\n全スリーブGREEN(現行レジーム継続)。次回実行=翌月初。")
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    path = os.path.join(HERE, "results", "regime_monitor.json")
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
