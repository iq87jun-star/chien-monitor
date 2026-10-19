# -*- coding: utf-8 -*-
"""
edge25_range_meanrev.py — レンジ相場定義→平均回帰の条件付き起動(docs/156事前登録の実行)。

候補(N=6固定): レンジ定義 {R1:ADX14<20, R2:BB幅20分位以下, R3:実現ボラ20分位以下}
             × 戦略 {S1:RSI(2)≤10/≥90反転, S2:BB(20,2σ)バンド外反転}
FX9ペア等加重・シグナル=当日close・翌open建て・3営業日後open決済・重複許容・往復2pip基準。
ゲート: perm(月次符号シャッフル)<0.0083 / 円環シフトプラセボ500draw 95分位超 / 素版超 /
       LOYO全年除外正 / IS-OOS(70:30)両正 / 4pip耐性 / close系はpre-2016(lh)参考。
出力: results/edge25_range_meanrev.json → docs/157(転記のみ)
"""
import os, json, hashlib
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF",
         "EURJPY", "GBPJPY", "USDJPY"]
YEN_LH = ["EURJPY", "GBPJPY", "USDJPY"]
COST_PIP, HOLD = 2.0, 3
N_PLACEBO, N_PERM, SEED = 500, 5000, 7
BONF = 0.05 / 6


def pip(p): return 0.01 if p.endswith("JPY") else 0.0001


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()[:16]


def load(pair, lh=False):
    fn = os.path.join(DATA, f"{pair}_lh_d.csv" if lh else f"{pair}_d.csv")
    if not os.path.exists(fn):
        return None
    df = pd.read_csv(fn)
    df.columns = [c.strip().lower() for c in df.columns]
    tcol = "timestamp" if "timestamp" in df.columns else "date"
    df["t"] = pd.to_datetime(df[tcol], errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t").set_index("t")
    return df


def wilder(s, n):
    return s.ewm(alpha=1.0 / n, adjust=False).mean()


def adx14(df, n=14):
    h, l, c = df["high"], df["low"], df["close"]
    up, dn = h.diff(), -l.diff()
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = wilder(tr, n)
    pdi = 100 * wilder(pd.Series(plus, index=df.index), n) / atr
    mdi = 100 * wilder(pd.Series(minus, index=df.index), n) / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi)
    return wilder(dx, n)


def rsi(c, n=2):
    d = c.diff()
    g = wilder(d.clip(lower=0), n)
    ls = wilder((-d).clip(lower=0), n)
    return 100 - 100 / (1 + g / ls)


def pct_rank_low(s, w=252, q=0.20):
    """過去w日内の分位q以下ならTrue(当日値含む・前日までの情報+当日close=シグナル日close確定)"""
    r = s.rolling(w, min_periods=w).apply(lambda a: (a <= a[-1]).mean(), raw=True)
    return r <= q


def build_pair(df):
    """ペアごとの (trade_ret S1/S2, レンジマスク R1/R2/R3)。tはシグナル日。"""
    c, o = df["close"], df["open"]
    mid = c.rolling(20).mean()
    sd = c.rolling(20).std()
    up, lo = mid + 2 * sd, mid - 2 * sd
    ret = {}
    # 翌open→(HOLD+1)日後open。dirはシグナルで決定
    entry = o.shift(-1)
    exit_ = o.shift(-(1 + HOLD))
    gross = exit_ / entry - 1.0
    cost = COST_PIP * (0.01 if c.iloc[-1] > 20 else 0.0001) / entry  # JPY系はclose水準で判別
    r2v = rsi(c, 2)
    sig1 = np.where(r2v <= 10, 1, np.where(r2v >= 90, -1, 0))
    sig2 = np.where(c < lo, 1, np.where(c > up, -1, 0))
    ret["S1"] = pd.Series(sig1 * gross - (np.abs(sig1) * cost), index=c.index)
    ret["S2"] = pd.Series(sig2 * gross - (np.abs(sig2) * cost), index=c.index)
    ret["S1_n"] = pd.Series(np.abs(sig1), index=c.index)
    ret["S2_n"] = pd.Series(np.abs(sig2), index=c.index)
    masks = {}
    if "high" in df.columns:
        masks["R1"] = (adx14(df) < 20)
    masks["R2"] = pct_rank_low((up - lo) / mid)
    masks["R3"] = pct_rank_low(c.pct_change().rolling(20).std())
    return ret, masks


def monthly(s):
    mk = pd.PeriodIndex(s.index, freq="M")
    return s.groupby(mk).sum()


def perm_p(m, rng, n=N_PERM):
    obs = m.mean()
    v = m.values
    cnt = 0
    for _ in range(n):
        if (v * rng.choice([-1, 1], size=len(v))).mean() >= obs:
            cnt += 1
    return (cnt + 1) / (n + 1)


def stats_for(trades_by_pair, masks_by_pair, R, S, rng):
    """全ペア合算のゲート版成績+全ゲート判定"""
    rows, rows_base = [], []
    for p in trades_by_pair:
        tr = trades_by_pair[p][S]
        if R is not None:
            m = masks_by_pair[p].get(R)
            if m is None:
                continue
            g = tr.where(m.fillna(False), 0.0)
        else:
            g = tr
        rows.append(g)
        rows_base.append(tr)
    g = pd.concat(rows, axis=1).mean(axis=1).dropna()
    total = float(g.sum())
    m = monthly(g)
    n_tr = int(sum((trades_by_pair[p][S + "_n"].where(
        masks_by_pair[p].get(R, pd.Series(True, index=trades_by_pair[p][S].index)).fillna(False), 0)
        if R else trades_by_pair[p][S + "_n"]).sum() for p in trades_by_pair))
    yrs = sorted(set(m.index.year))
    loyo = {str(y): float(m[m.index.year != y].mean()) for y in yrs}
    k = int(len(m) * 0.7)
    return g, dict(total_ret_pct=round(total * 100, 2), n_trades=n_tr,
                   mean_month_bp=round(float(m.mean()) * 1e4, 2),
                   perm_p=round(perm_p(m, rng), 4),
                   loyo_all_positive=bool(all(v > 0 for v in loyo.values())),
                   loyo_min=round(min(loyo.values()) * 1e4, 2),
                   is_mean_bp=round(float(m.iloc[:k].mean()) * 1e4, 2),
                   oos_mean_bp=round(float(m.iloc[k:].mean()) * 1e4, 2))


def placebo_pct(trades_by_pair, masks_by_pair, R, S, gated_total, rng):
    """ONマスクを円環シフト(全ペア同一オフセット)500draw → ゲート版totalの分位"""
    vals = []
    pairs = [p for p in trades_by_pair if R in masks_by_pair[p]]
    trs = {p: trades_by_pair[p][S].fillna(0.0).values for p in pairs}
    mks = {p: masks_by_pair[p][R].fillna(False).values for p in pairs}
    n = min(len(v) for v in trs.values())
    for _ in range(N_PLACEBO):
        k = int(rng.integers(30, n - 30))
        tot = 0.0
        for p in pairs:
            tot += float((trs[p] * np.roll(mks[p], k)).sum()) / len(pairs)
        vals.append(tot)
    return round(100.0 * float((np.asarray(vals) < gated_total).mean()), 1)


def main():
    rng = np.random.default_rng(SEED)
    print("[1/4] データ読込+指標構築")
    trades, masks, shas = {}, {}, {}
    for p in PAIRS:
        df = load(p)
        if df is None:
            continue
        trades[p], masks[p] = build_pair(df)
        shas[p] = sha256(os.path.join(DATA, f"{p}_d.csv"))
    print(f"  {len(trades)}ペア読込")

    out = {}
    print("[2/4] 素版(ゲートなし)ベースライン")
    base = {}
    for S in ("S1", "S2"):
        _, st = stats_for(trades, masks, None, S, rng)
        base[S] = st
        print(f"  素版{S}: {st}")

    print("[3/4] 候補6本(ゲート版)+プラセボ+コスト感応")
    for R in ("R1", "R2", "R3"):
        for S in ("S1", "S2"):
            key = f"{R}x{S}"
            g, st = stats_for(trades, masks, R, S, rng)
            st["placebo_pct"] = placebo_pct(trades, masks, R, S, float(g.sum()), rng)
            st["beats_base"] = bool(st["total_ret_pct"] > base[S]["total_ret_pct"])
            # コスト感応(1/4pip): 取引数×差分pipで近似せず再計算
            global COST_PIP
            keep = COST_PIP
            sens = {}
            for cp in (1.0, 4.0):
                COST_PIP = cp
                tb = {p: build_pair(load(p))[0] for p in trades}
                _, s2 = stats_for(tb, masks, R, S, np.random.default_rng(SEED))
                sens[f"{cp}pip"] = s2["total_ret_pct"]
            COST_PIP = keep
            st["cost_sens_total_pct"] = sens
            gates = dict(G_perm=st["perm_p"] < BONF,
                         G_plac=st["placebo_pct"] > 95.0,
                         G_base=st["beats_base"],
                         G_loyo=st["loyo_all_positive"],
                         G_oos=(st["is_mean_bp"] > 0 and st["oos_mean_bp"] > 0),
                         G_cost=sens["4.0pip"] > 0)
            st["gates"] = gates
            st["verdict"] = "ADOPT候補" if all(gates.values()) else (
                "LEAD" if (gates["G_perm"] and gates["G_plac"]) else "REJECT")
            out[key] = st
            print(f"  {key}: total={st['total_ret_pct']}% perm_p={st['perm_p']} "
                  f"plac={st['placebo_pct']} base超={st['beats_base']} "
                  f"loyo={st['loyo_all_positive']} IS/OOS={st['is_mean_bp']}/{st['oos_mean_bp']}bp "
                  f"→ {st['verdict']}")

    print("[4/4] pre-2016参考(close系: R2/R3×S1/S2・円3クロスlh 2003-2015)")
    pre = {}
    tr_lh, mk_lh = {}, {}
    for p in YEN_LH:
        df = load(p, lh=True)
        if df is None:
            continue
        df = df[df.index < "2016-01-01"]
        df["open"] = df["close"].shift(1)  # close-only: openをclose(t-1)で近似(参考扱いの根拠)
        tr_lh[p], mk_lh[p] = build_pair(df)
    for R in ("R2", "R3"):
        for S in ("S1", "S2"):
            _, st = stats_for(tr_lh, mk_lh, R, S, np.random.default_rng(SEED))
            pre[f"{R}x{S}"] = dict(total_ret_pct=st["total_ret_pct"],
                                   mean_month_bp=st["mean_month_bp"])
            print(f"  pre2016 {R}x{S}: {pre[f'{R}x{S}']}")

    res = dict(meta=dict(prereg="docs/156", n_candidates=6, bonferroni=round(BONF, 4),
                         pairs=list(trades.keys()), cost_pip=2.0, hold_days=HOLD,
                         n_placebo=N_PLACEBO, n_perm=N_PERM, seed=SEED, inputs=shas,
                         caveat="Yahoo日足・重複許容・固定3日保有。pre-2016はclose-only近似(参考)。"),
               baseline_ungated=base, candidates=out, pre2016_reference=pre)
    path = os.path.join(HERE, "results", "edge25_range_meanrev.json")
    with open(path, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
