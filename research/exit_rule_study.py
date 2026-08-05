# -*- coding: utf-8 -*-
"""
exit_rule_study.py — 【探索】決済ルールをテクニカル指標化すると成績は安定するか。

ユーザー質問(2026-08-05)「現状のEAの決済をテクニカル指標により判断する事で成績を
安定させる事は可能でしょうか」への計測。

現行の決済(配備中レッグ):
  Mon  : 月曜寄り買い→翌日寄り決済(時間決済)+災害SL 2.5×ATR(H1)のみ
  v4   : SL=1.5×ATR / TP=1.2×SL / 最大8日
  Hold : 連続保有(災害SLのみ)
検証する決済変種(日足近似・エントリーは全変種で現行と同一=決済だけを変える):
  Mon  : close(引け決済) / sl1.0(1.0×ATR日足ストップ) / tp1sl15(TP1.0×ATR+SL1.5×ATR)
  v4   : rsi50(RSI50回帰で手仕舞い・TPなし) / tp08(TP=0.8×SL) / time3(最大3日)
  Hold : sma200 / sma100(終値が移動平均割れで退出・回復で再エントリー)
判定尺度=「安定」の定義: 年率ボラ・最悪単日・月中DD・月次勝率(全期間)。リターンは従属。
⚠ 日足近似の限界: Mon実装の12h/H1系・スプレッド変動は再現不能。同日にTP/SL両接触時は
  SL先着と仮定(保守側)。事後に最良変種を選ぶ行為自体が選択バイアス — 採用時は要事前登録。
出力: results/exit_rule_study.json → docs/188
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_screen as base
import recentfit_lowcorr_screen as lc

SEED = 7
W12_0 = base.W12_0


# ---------- Mon 決済変種 ----------
def mon_variant(nm, mode):
    df = base.load_daily(nm)
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    atr = base.atr_d(h, l, c)
    cost_s = (base.IDX_COST[nm] * np.ones(len(df))) if nm in base.IDX_COST \
        else (2 * base.pip_size(nm) / o)
    o2o = df["o2o"].values
    wd = df["weekday"].values
    out = {}
    for i in range(1, len(df) - 1):
        if wd[i] != 0 or not np.isfinite(o2o[i]):
            continue
        a = atr[i - 1]
        entry = o[i]
        if mode == "o2o":
            r = o2o[i]
        elif mode == "close":
            r = (c[i] - entry) / entry
        elif mode == "sl1.0":
            s = entry - 1.0 * a
            r = (s - entry) / entry if l[i] <= s else o2o[i]
        elif mode == "tp1sl15":
            s = entry - 1.5 * a; t = entry + 1.0 * a
            if l[i] <= s:                      # SL先着仮定(保守)
                r = (s - entry) / entry
            elif h[i] >= t:
                r = (t - entry) / entry
            else:
                r = o2o[i]
        out[df.index[i]] = r - cost_s[i]
    return base.clip(pd.Series(out).sort_index())


# ---------- v4 決済変種 ----------
def v4_variant(p, mode):
    df = base.load_daily(p)
    o = df["open"].values; hh = df["high"].values; ll = df["low"].values; c = df["close"].values
    idx = df.index; n = len(c); rsi = base.rsi_w(c); atr = base.atr_d(hh, ll, c); bb = 20
    cost = 2 * base.pip_size(p); acc = {}; i = bb + 2
    max_hold = 3 if mode == "time3" else 8
    while i < n - 1:
        win = c[i - bb:i]; mean = win.mean(); sd = win.std(ddof=1)
        z = (c[i] - mean) / sd if sd > 0 else 0
        down = 0
        for k in range(12):
            if i - k - 1 >= 0 and c[i - k] < c[i - k - 1]: down += 1
            else: break
        up = 0
        for k in range(12):
            if i - k - 1 >= 0 and c[i - k] > c[i - k - 1]: up += 1
            else: break
        retd = (c[i] - c[i - 1]) / c[i - 1] if c[i - 1] else 0
        buy = int(rsi[i] < 35) + int(z < -1.5) + int(down >= 3) + int(retd < -.005)
        sell = int(rsi[i] > 65) + int(z > 1.5) + int(up >= 3) + int(retd > .005)
        sig = 1 if (buy >= 4 and buy > sell) else (-1 if (sell >= 4 and sell > buy) else 0)
        if sig == 0:
            i += 1; continue
        entry = o[i + 1]; sld = 1.5 * atr[i]
        tpd = {"current": 1.2, "tp08": 0.8, "time3": 1.2}.get(mode, None)
        if sld <= 0 or entry <= 0:
            i += 1; continue
        sl = entry - sig * sld
        tp = entry + sig * (tpd * sld) if tpd is not None else None
        ex = None; j = i + 1; held = 0
        while j < n and held < max_hold:
            if sig > 0:
                if ll[j] <= sl: ex = sl; break
                if tp is not None and hh[j] >= tp: ex = tp; break
            else:
                if hh[j] >= sl: ex = sl; break
                if tp is not None and ll[j] <= tp: ex = tp; break
            if mode == "rsi50" and ((sig > 0 and rsi[j] >= 50) or (sig < 0 and rsi[j] <= 50)):
                ex = c[j]; break                     # RSI回帰完了→引け手仕舞い
            j += 1; held += 1
        jx = min(j, n - 1)
        if ex is None: ex = c[jx]
        prev = entry
        for t in range(i + 1, jx + 1):
            px = ex if t == jx else c[t]
            r = sig * (px - prev) / entry
            if t == i + 1: r -= cost / entry
            acc[idx[t]] = acc.get(idx[t], 0.0) + r
            prev = px
        i = max(i + 1, j)
    return base.clip(pd.Series(acc).sort_index())


# ---------- Hold 決済変種 ----------
def hold_variant(nm, sma):
    df = base.load_daily(nm)
    cl = df["close"]
    pos = (cl > cl.rolling(sma).mean()).astype(float).shift(1).fillna(0.0)
    s = cl.pct_change() * pos
    s = base.clip(s.dropna())
    flips = pos.diff().abs().reindex(s.index).fillna(0.0)
    s = s - flips * 5e-4                                     # 出入りコスト
    return s


def stats(s, label):
    s12 = s[s.index >= W12_0]
    act = s[s != 0.0]
    mk = pd.PeriodIndex(act.index, freq="M")
    monthly = pd.Series({k: float((1 + act[mk == k]).prod() - 1) for k in mk.unique()})
    wd, wdd = base.worst_stats(s)
    return dict(label=label,
                cum_full=round(float((1 + act).prod() - 1) * 100, 1),
                cum_12m=round(float((1 + s12).prod() - 1) * 100, 2),
                vol_ann=round(float(act.std()) * np.sqrt(252) * 100, 1),
                worst_day=round(wd * 100, 2), mdd_full=round(wdd * 100, 2),
                mwin=round(float((monthly > 0).mean()) * 100, 0),
                score12=lc.stats_for(s)["score"])


def main():
    for nm in base.YAHOO:
        try:
            base.fetch(nm)
        except Exception:
            pass
    out = dict(meta=dict(purpose="決済ルールのテクニカル化の探索(docs/188)", seed=SEED,
                         caveat="日足近似・同日TP/SL両接触はSL先着仮定。事後選択バイアスあり"
                                "=採用時は要事前登録。", inputs=base.sha256s()), cells={})

    print("[1/3] Mon決済変種(配備3銘柄)")
    for nm in ["GBPJPY", "AUDJPY", "USDJPY"]:
        rows = {}
        for mode in ["o2o", "close", "sl1.0", "tp1sl15"]:
            rows[mode] = stats(mon_variant(nm, mode), mode)
            print(f"  Mon_{nm:7s} {mode:8s} {rows[mode]}")
        out["cells"][f"Mon_{nm}"] = rows

    print("[2/3] v4決済変種(配備3ペア)")
    for p in ["USDJPY", "NZDUSD", "AUDUSD"]:
        rows = {}
        for mode in ["current", "rsi50", "tp08", "time3"]:
            rows[mode] = stats(v4_variant(p, mode), mode)
            print(f"  v4_{p:8s} {mode:8s} {rows[mode]}")
        out["cells"][f"v4_{p}"] = rows

    print("[3/3] Hold決済変種(JP225)+B構成合成の現行vs変種")
    rows = {"current": stats(base.hold_cell("JP225"), "current"),
            "sma200": stats(hold_variant("JP225", 200), "sma200"),
            "sma100": stats(hold_variant("JP225", 100), "sma100")}
    for k, v in rows.items():
        print(f"  Hold_JP225 {k:8s} {v}")
    out["cells"]["Hold_JP225"] = rows

    # B構成(Fintokei 3レッグ)での合成比較: 現行 vs 「安定寄り」変種束
    def mix(parts):
        idx = sorted(set().union(*[set(s.index) for s, _ in parts]))
        cc = pd.Series(0.0, index=pd.DatetimeIndex(idx))
        for s, w in parts:
            cc = cc.add(s.reindex(cc.index).fillna(0.0) * w, fill_value=0.0)
        return cc
    combos = {
        "B現行": [(mon_variant("GBPJPY", "o2o"), .374), (mon_variant("AUDJPY", "o2o"), .322),
                  (v4_variant("USDJPY", "current"), .304)],
        "B変種_close": [(mon_variant("GBPJPY", "close"), .374), (mon_variant("AUDJPY", "close"), .322),
                        (v4_variant("USDJPY", "rsi50"), .304)],
        "B変種_slのみ": [(mon_variant("GBPJPY", "sl1.0"), .374), (mon_variant("AUDJPY", "sl1.0"), .322),
                         (v4_variant("USDJPY", "current"), .304)],
    }
    out["composites"] = {}
    for name, parts in combos.items():
        comp = mix(parts)
        st = stats(comp, name)
        m12 = lc.max_mult(comp[comp.index >= W12_0])
        mult = round(min(0.8 * m12, 6.0), 2)
        mc12 = lc.mc_challenge(comp[comp.index >= W12_0], mult, 0.08, 0.05, np.random.default_rng(SEED))
        mcf = lc.mc_challenge(comp, mult, 0.08, 0.05, np.random.default_rng(SEED))
        out["composites"][name] = dict(stats=st, mult=mult, mc_fn_12m=mc12, mc_fn_full=mcf)
        print(f"  {name}: {st}")
        print(f"    mult={mult} MC12m={mc12}")
        print(f"    MCfull={mcf}")

    path = os.path.join(HERE, "results", "exit_rule_study.json")
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
