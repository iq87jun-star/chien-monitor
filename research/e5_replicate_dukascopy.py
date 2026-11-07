# -*- coding: utf-8 -*-
"""
e5_replicate_dukascopy.py — E5 の別ソース(Dukascopy日足)同窓再現(docs/209の実装)。
生成式は recentfit_screen.e5_composite を無変更で使い、入力データだけ Dukascopy に差し替える。
R1 相関(vs Yahoo E5) / R2 順列検定(月次符号反転) / R3 年次ジャックナイフ / R4 5年ブロック。
出力: results/e5_replicate_dukascopy.json → docs/209 §4
"""
import os, sys, json, math
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import recentfit_screen as base
SEED = 7; N_PERM = 10000; ALPHA = 0.05 / 6; JK_ALPHA = 0.10
DUKA = os.path.join(HERE, "data_dukascopy"); RF = os.path.join(HERE, "data_duka_rf"); os.makedirs(RF, exist_ok=True)
E5B = ["XAUUSD", "US500", "NAS100", "GER40"]


def prepare():
    """Dukascopy 日足 → base.load_daily が読む `<name>_rf.csv` 形式(週末行を除去)。"""
    starts = {}
    for nm in E5B:
        d = pd.read_csv(os.path.join(DUKA, f"{nm}_day.csv"), parse_dates=["timestamp"])
        d = d[d.timestamp.dt.dayofweek <= 4]
        d = d[~((d.open == d.high) & (d.high == d.low) & (d.low == d.close) & (d.volume == 0))]   # 祝日のフラット行
        d[["timestamp", "open", "high", "low", "close"]].assign(timestamp=d.timestamp.dt.strftime("%Y-%m-%d %H:%M:%S")) \
            .to_csv(os.path.join(RF, f"{nm}_rf.csv"), index=False)
        starts[nm] = d.timestamp.min(); print(f"  {nm}: {d.timestamp.min().date()}..{d.timestamp.max().date()} ({len(d)}本)")
    return max(starts.values())


def monthly(s):
    mk = pd.PeriodIndex(s.index, freq="M")
    return pd.Series({k: float((1 + s[mk == k]).prod() - 1) for k in mk.unique()}).sort_index()


def perm_p(m, rng, n=N_PERM):
    a = np.asarray(m, float); obs = a.mean()
    flips = rng.choice([-1, 1], size=(n, len(a))); return float(((flips * a).mean(axis=1) >= obs).mean())


def e5_on(data_dir, w0, w1):
    base.DATA = data_dir; base.W_ALL0, base.W_ALL1 = w0, w1
    s = base.e5_composite(); return s[(s.index >= w0) & (s.index <= w1)]


def stats(s):
    eq = (1 + s).cumprod(); yrs = (s.index[-1] - s.index[0]).days / 365.25; m = monthly(s)
    return dict(net_pct=round(float(eq.iloc[-1] - 1) * 100, 1), cagr=round(float(eq.iloc[-1] ** (1 / yrs) - 1) * 100, 2),
                maxdd=round(float(((eq - eq.cummax()) / eq.cummax()).min()) * 100, 1),
                sharpe=round(float(m.mean() / m.std() * math.sqrt(12)), 2), n_months=int(len(m)))


def main():
    rng = np.random.default_rng(SEED)
    print("[1/4] Dukascopy → rf形式"); duka_start = prepare()
    duka_end = pd.Timestamp("2026-08-31")
    print("[2/4] E5 生成(同一式)")
    y0, y1 = pd.Timestamp("2016-01-01"), duka_end
    e5_yahoo10 = e5_on(os.path.join(HERE, "data_202609"), y0, y1)
    e5_duka10 = e5_on(RF, y0, y1)
    long0 = pd.Timestamp(duka_start.year + 1, 1, 1)             # 12ヶ月モメンタムの助走後から
    e5_duka_long = e5_on(RF, long0, y1)
    out = {"meta": dict(purpose="E5 Dukascopy 同窓再現 docs/209", seed=SEED, duka_start=str(duka_start.date()),
                        window10=[str(y0.date()), str(y1.date())], window_long=[str(long0.date()), str(y1.date())], alpha=ALPHA)}
    print("[3/4] R1 相関 / 統計")
    my, md = monthly(e5_yahoo10), monthly(e5_duka10)
    j = pd.concat([my.rename("y"), md.rename("d")], axis=1).dropna(); r1 = float(j.y.corr(j.d))
    out["R1_corr_monthly_10y"] = round(r1, 3)
    out["yahoo10"] = stats(e5_yahoo10); out["duka10"] = stats(e5_duka10); out["duka_long"] = stats(e5_duka_long)
    print(f"  R1 月次相関(2016-26)= {r1:.3f}\n  Yahoo10: {out['yahoo10']}\n  Duka10 : {out['duka10']}\n  DukaLong: {out['duka_long']}")
    print("[4/4] R2 順列 / R3 ジャックナイフ / R4 5年ブロック(最長窓)")
    ml = monthly(e5_duka_long); p2 = perm_p(ml, rng); out["R2_perm_p"] = round(p2, 5)
    jk = {}
    for y in sorted(set(ml.index.year)):
        sub = ml[ml.index.year != y]; jk[int(y)] = round(perm_p(sub, np.random.default_rng(SEED), n=2000), 4)
    out["R3_jackknife"] = jk; out["R3_max_p"] = max(jk.values())
    blocks = {}
    for b0 in range(long0.year, y1.year + 1, 5):
        sub = ml[(ml.index.year >= b0) & (ml.index.year < b0 + 5)]
        if len(sub) >= 12: blocks[f"{b0}-{min(b0+4, y1.year)}"] = round(float((1 + sub).prod() - 1) * 100, 1)
    out["R4_blocks"] = blocks
    out["duka10_perm_p"] = round(perm_p(md, np.random.default_rng(SEED)), 5)
    v = dict(R1=bool(r1 >= 0.90), R2=bool(p2 < ALPHA), R3=bool(out["R3_max_p"] <= JK_ALPHA), R4=bool(all(x > 0 for x in blocks.values())))
    v["ADOPT"] = all(v.values()); out["verdict"] = v
    print(f"  R2 perm_p={p2:.5f} (α={ALPHA:.4f})  R3 JK max_p={out['R3_max_p']}  R4 blocks={blocks}\n  10年窓 perm_p={out['duka10_perm_p']}\n  判定: {v}")
    json.dump(out, open(os.path.join(HERE, "results", "e5_replicate_dukascopy.json"), "w"), ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
