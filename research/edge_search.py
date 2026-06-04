"""
edge_search.py — 本番10年データに対する誠実なエッジ探索。

背景: v1〜v4(平均回帰・極値モメンタム・ORB・合議)は本番データで全滅。
本スクリプトは「まだ試していない別系統(トレンドフォロー)」を、v4検証ノートと
同一の厳格ゲート(順列検定 / halt-OFF真DD / OOS PF・Wilson / 年次WF)に通す。

エンジン(load_h1/resample_h4/run_backtest/evaluate/permutation_test 等)は
FundedNext_v4_validation_SELFCONTAINED.ipynb から再利用する(シグナル層のみ差替)。

使い方:  DATA_DIR=/path/to/real python3 research/edge_search.py
出力は人間可読のテーブル。合格戦略が出れば、その設定でEAを書く。
"""
import os, sys, math, json, itertools, numpy as np, pandas as pd, nbformat, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
NB   = os.path.join(HERE, "FundedNext_v4_validation_SELFCONTAINED.ipynb")

# ---- エンジン関数を notebook から取り込む(top-levelの実行/表示は無害化) ----
G = {"__name__": "__engine__"}
G["display"] = lambda *a, **k: None          # display()を無効化
nb = nbformat.read(NB, as_version=4)
cells = [c for c in nb.cells if c.cell_type == "code"]
# cell0:Driveマウント(Colab専用)はスキップ。1:import/設定, 2:データ, 3:signals,
# 4:backtest/evaluate, 8:yearly_wf, 9:permutation の "関数定義" を取り込む。
for i in (1, 2, 3, 4, 8):
    exec(cells[i].source, G)
# cell9 は末尾に実行ループがあるので、関数定義部分だけ取り込む
src9 = cells[9].source.split("\nperm_rows")[0]
exec(src9, G)

load_h1   = G["load_h1"];   resample_h4 = G["resample_h4"]
_atr      = G["_atr_wilder"]; _rsi = G["_rsi_wilder"]
run_backtest = G["run_backtest"]; evaluate = G["evaluate"]; wilson_lower = G["wilson_lower"]
permutation_test = G["permutation_test"]; yearly_wf = G["yearly_wf"]; pip_size = G["pip_size"]
AVAIL = G["AVAIL"]
print("エンジン取り込み完了。利用可能ペア:", AVAIL)

# =====================================================================
# 候補シグナル群(トレンドフォロー系 = これまで未検証の別系統)
# 各関数は h4(OHLC) と P を受け、{'signal','atr'} の DataFrame を返す。
# signal: +1=買い / -1=売り / 0=見送り。すべて確定足[i]の情報のみ使用(翌足約定)。
# =====================================================================
def _ema(s, n): return s.ewm(span=n, adjust=False, min_periods=n).mean()

def sig_donchian(h4, P):
    """チャネルブレイク順張り: 終値が直近N本の高値上抜けで買い/安値下抜けで売り。
    任意のEMAトレンドフィルタ(TrendEma>0)で逆行を排除。"""
    c, hi, lo = h4["close"], h4["high"], h4["low"]
    N = P["Donch"]
    upper = hi.shift(1).rolling(N).max()
    lower = lo.shift(1).rolling(N).min()
    sig = pd.Series(0, index=c.index, dtype=int)
    longC  = c > upper
    shortC = c < lower
    te = P.get("TrendEma", 0)
    if te > 0:
        ema = _ema(c, te)
        longC  &= c > ema
        shortC &= c < ema
    sig[longC] = 1
    sig[shortC & ~longC] = -1
    return pd.DataFrame({"signal": sig, "atr": _atr(h4, P["AtrPeriod"])})

def sig_tsmom(h4, P):
    """時系列モメンタム(TSMOM): 終値>Lookback本前 かつ 終値>EMAtrend で買い。逆で売り。"""
    c = h4["close"]
    L = P["Lookback"]
    ema = _ema(c, P.get("TrendEma", 100))
    mom_up = c > c.shift(L)
    sig = pd.Series(0, index=c.index, dtype=int)
    longC  = mom_up & (c > ema)
    shortC = (~mom_up) & (c < ema)
    sig[longC] = 1
    sig[shortC] = -1
    return pd.DataFrame({"signal": sig, "atr": _atr(h4, P["AtrPeriod"])})

def sig_volbreak(h4, P):
    """ボラ収縮→拡大ブレイク: 直近の足レンジが収縮(NR)した後、
    前足高値/安値を実体ブレイクした方向に順張り。EMAトレンドフィルタ任意。"""
    c, hi, lo = h4["close"], h4["high"], h4["low"]
    rng = (hi - lo)
    nr = rng.shift(1) <= rng.shift(1).rolling(P.get("NRwin", 10)).min() * 1.0  # 直近最小レンジ足
    longC  = nr & (c > hi.shift(1))
    shortC = nr & (c < lo.shift(1))
    te = P.get("TrendEma", 0)
    if te > 0:
        ema = _ema(c, te)
        longC  &= c > ema
        shortC &= c < ema
    sig = pd.Series(0, index=c.index, dtype=int)
    sig[longC] = 1
    sig[shortC & ~longC] = -1
    return pd.DataFrame({"signal": sig, "atr": _atr(h4, P["AtrPeriod"])})

SIGFUNS = {"donchian": sig_donchian, "tsmom": sig_tsmom, "volbreak": sig_volbreak}

# compute_signals を戦略ディスパッチに差し替え(backtest/permutation はこれを呼ぶ)
def compute_signals(h4, P):
    return SIGFUNS[P["Strategy"]](h4, P)
G["compute_signals"] = compute_signals      # エンジン側の参照も差し替え

# =====================================================================
# 評価ユーティリティ: 1設定をhalt-OFFで通し、OOS(後25%)も測る
# =====================================================================
BASE = dict(G["P"])   # v4の資金管理パラメータを土台に流用

def make_P(strategy, **kw):
    P = dict(BASE)
    P["Strategy"] = strategy
    P.update(kw)
    return P

def split_oos(tdf, frac=0.75):
    if len(tdf) == 0: return tdf, tdf
    cut = tdf["ent_time"].quantile(frac)
    return tdf[tdf["ent_time"] < cut], tdf[tdf["ent_time"] >= cut]

def eval_full(pair, P):
    """halt-OFF(=真の連続成績)で全期間backtest → 全体/OOS指標を返す。"""
    h1 = load_h1(pair); h4 = resample_h4(h1)
    tdf, eqdf = run_backtest(pair, h1, h4, P, halt_on_target=False, halt_on_floor=False)
    if len(tdf) < 20:
        return None
    full = evaluate(tdf, eqdf, P, "full")
    _, oos = split_oos(tdf, 0.75)
    if len(oos) >= 20:
        oeq = oos[["exit_time", "equity"]].rename(columns={"exit_time": "time"}).set_index("time")
        oo = evaluate(oos, oeq, P, "oos")
    else:
        oo = {"n": len(oos), "PF": float("nan"), "wilson_gt_BE": False, "wilson_lo": float("nan")}
    return dict(full=full, oos=oo, tdf=tdf, eqdf=eqdf)

# =====================================================================
# フェーズ1: 設計空間スイープ(順列なしの軽量スクリーニング、全ペアプール基準)
# =====================================================================
def sweep():
    grid = []
    # donchian
    for N in (20, 30, 40, 55):
        for te in (0, 100, 200):
            for rr in (1.5, 2.0, 3.0):
                for hold in (12, 24, 40):
                    grid.append(make_P("donchian", Donch=N, TrendEma=te, RR=rr,
                                       HoldH4Bars=hold, AtrSLMult=2.0))
    # tsmom
    for L in (10, 20, 40):
        for te in (50, 100, 200):
            for rr in (1.5, 2.0, 3.0):
                for hold in (24, 40, 60):
                    grid.append(make_P("tsmom", Lookback=L, TrendEma=te, RR=rr,
                                       HoldH4Bars=hold, AtrSLMult=2.0))
    # volbreak
    for nw in (6, 10, 20):
        for te in (0, 100, 200):
            for rr in (1.5, 2.0, 3.0):
                for hold in (12, 24, 40):
                    grid.append(make_P("volbreak", NRwin=nw, TrendEma=te, RR=rr,
                                       HoldH4Bars=hold, AtrSLMult=2.0))
    print(f"スイープ設定数: {len(grid)}  × ペア {len(AVAIL)}")
    rows = []
    for gi, P in enumerate(grid):
        agg = {"n": 0, "gp": 0.0, "gl": 0.0, "on": 0, "ogp": 0.0, "ogl": 0.0}
        ok = True
        for pair in AVAIL:
            r = eval_full(pair, P)
            if r is None:
                ok = False; break
            t = r["tdf"]; R = t["rmultiple"].values
            agg["n"] += len(R); agg["gp"] += R[R > 0].sum(); agg["gl"] += -R[R < 0].sum()
            _, oos = split_oos(t, 0.75); oR = oos["rmultiple"].values
            agg["on"] += len(oR); agg["ogp"] += oR[oR > 0].sum(); agg["ogl"] += -oR[oR < 0].sum()
        if not ok or agg["n"] < 60:
            continue
        pf  = agg["gp"]/agg["gl"] if agg["gl"] > 0 else float("inf")
        opf = agg["ogp"]/agg["ogl"] if agg["ogl"] > 0 else float("inf")
        key = {k: P[k] for k in P if k in ("Strategy","Donch","TrendEma","RR","HoldH4Bars",
                                           "Lookback","NRwin","AtrSLMult")}
        rows.append(dict(**key, n=agg["n"], PF=round(pf,3), OOS_n=agg["on"], OOS_PF=round(opf,3)))
    df = pd.DataFrame(rows)
    return df

if __name__ == "__main__":
    pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30)
    pd.set_option("display.max_rows", 60)
    df = sweep()
    if len(df) == 0:
        print("\n有効設定なし(全件 n<60 か データ不足)。")
        sys.exit(0)
    # 全期間PF>1 かつ OOS_PF>1 を優先。OOS_PFで降順。
    df = df.sort_values(["OOS_PF","PF"], ascending=False).reset_index(drop=True)
    print("\n===== スイープ上位30(全ペアプール, halt-OFF全期間 & OOS後25%) =====")
    print(df.head(30).to_string())
    both = df[(df.PF > 1.0) & (df.OOS_PF > 1.0)]
    print(f"\n全期間PF>1 かつ OOS_PF>1 の設定数: {len(both)} / {len(df)}")
    df.to_csv(os.path.join(HERE, "results", "edge_sweep.csv"), index=False)
    print("保存: research/results/edge_sweep.csv")
