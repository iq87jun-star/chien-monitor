"""
edge15_month_seasonality.py — 月次季節性【事前登録 docs/88】。
確認的(N=3, α=0.0167): S1=9月株SHORT / S2=9月金LONG / S3=9/15以降USDJPY SHORT。
ゲート: G_dir(net>0) / G_perm(年次順列p<=0.0167) / G_split(pre2016と2016+両方+) /
G_month_rank(月シフト・プラセボ: 12ヶ月中1-2位)。
探索(参考のみ): 7資産×12ヶ月×L/S=168セル, Bonferroni α=0.0003。
"""
import os, json, importlib.util
import numpy as np, pandas as pd

spec = importlib.util.spec_from_file_location("e13", "research/edge13_longhistory_confirm.py")
e13 = importlib.util.module_from_spec(spec); spec.loader.exec_module(e13)

EQ = ["US500", "NAS100", "GER40"]
ALL7 = EQ + ["XAUUSD", "USDJPY", "EURJPY", "GBPJPY"]
ALPHA = 0.05/3

def perm_p(r, n=3000, seed=13):
    r = np.asarray(r, float)
    if len(r) == 0: return 1.0
    rng = np.random.default_rng(seed); real = r.sum(); a = np.abs(r)
    return float((np.array([(a*rng.choice([-1,1], size=len(a))).sum() for _ in range(n)]) >= real).mean())

def month_returns(asset, month, dir_, half_from_day=None):
    """各年の月リターン(dir適用・コスト控除)を年次系列で返す。"""
    s = e13.daily(asset)
    fx = asset.endswith("JPY")
    out = {}
    for y in sorted(set(s.index.year)):
        m = s[(s.index.year == y) & (s.index.month == month)]
        if len(m) < 10: continue
        prev = s[s.index < m.index[0]]
        if len(prev) == 0: continue
        if half_from_day:
            half = m[m.index.day >= half_from_day]
            if len(half) < 5: continue
            p0 = m[m.index < half.index[0]].iloc[-1] if len(m[m.index < half.index[0]]) else prev.iloc[-1]
        else:
            p0 = prev.iloc[-1]
        p1 = m.iloc[-1]
        cost = (2*0.01/p0) if fx else 5e-4
        out[y] = dir_*(p1/p0 - 1.0) - cost
    return pd.Series(out)

def stats(v):
    v = v.dropna()
    net = (np.prod(1+v.values)-1)*100
    return dict(net_pct=round(float(net), 1), mean_pct=round(float(v.mean())*100, 2),
                win=f"{int((v>0).sum())}/{len(v)}", n=int(len(v)), perm_p=round(perm_p(v.values), 4))

def basket(assets, month, dir_, half=None):
    df = pd.DataFrame({a: month_returns(a, month, dir_, half) for a in assets})
    return df.mean(axis=1).dropna()

def judge(name, assets, month, dir_, half=None):
    v = basket(assets, month, dir_, half)
    st = stats(v)
    pre, post = v[v.index < 2016], v[v.index >= 2016]
    ranks = []
    for m in range(1, 13):
        vm = basket(assets, m, dir_, half)
        ranks.append((m, float(vm.mean())))
    ranks.sort(key=lambda x: -x[1])
    sep_rank = [i+1 for i, (m, _) in enumerate(ranks) if m == month][0]
    g_dir = st["net_pct"] > 0
    g_perm = st["perm_p"] <= ALPHA
    g_split = (len(pre) > 3 and len(post) > 3 and pre.mean() > 0 and post.mean() > 0)
    g_rank = sep_rank <= 2
    passed = sum([g_dir, g_perm, g_split, g_rank])
    verdict = "SEP-LEAD" if passed == 4 else ("参考(G_perm未達)" if (g_dir and g_split and g_rank) else "REJECT")
    res = dict(**st, pre2016_mean=round(float(pre.mean())*100, 2) if len(pre) else None,
               post2016_mean=round(float(post.mean())*100, 2) if len(post) else None,
               month_rank=f"{sep_rank}/12",
               gates=dict(dir=g_dir, perm=g_perm, split=g_split, rank=g_rank), verdict=verdict,
               yearly_2016plus={int(y): round(float(r)*100, 1) for y, r in post.items()})
    print(f"\n### {name} → {verdict} ({passed}/4)")
    print(f"  全履歴: net{st['net_pct']}% 平均{st['mean_pct']}%/年 勝率{st['win']} p={st['perm_p']}(α{round(ALPHA,4)})")
    print(f"  pre2016平均 {res['pre2016_mean']}% / 2016+平均 {res['post2016_mean']}% | 月ランク {res['month_rank']}")
    print(f"  2016+年別: {res['yearly_2016plus']}")
    return res

out = {"confirmatory": {}, "exploratory_survivors": []}
out["confirmatory"]["S1_SEP_EQ_SHORT"]  = judge("S1 9月株SHORT", EQ, 9, -1)
out["confirmatory"]["S2_SEP_GOLD_LONG"] = judge("S2 9月金LONG", ["XAUUSD"], 9, +1)
out["confirmatory"]["S3_SEP_JPY"]       = judge("S3 9/15以降USDJPY SHORT", ["USDJPY"], 9, -1, half=15)

# 探索スキャン(参考のみ)
print("\n== 探索スキャン(168セル・Bonferroni α=0.0003・参考のみ) ==")
cells = []
for a in ALL7:
    for m in range(1, 13):
        for d in (1, -1):
            v = month_returns(a, m, d)
            if len(v) < 15: continue
            p = perm_p(v.values)
            cells.append((a, m, d, round(float(v.mean())*100, 2), round(p, 4), len(v)))
cells.sort(key=lambda c: c[4])
bonf = 0.05/168
for a, m, d, mu, p, n in cells[:10]:
    surv = "★Bonferroni生存" if p <= bonf else ""
    print(f"  {a} {m}月 {'L' if d>0 else 'S'}: 平均{mu:+.2f}%/年 p={p} n={n} {surv}")
    if p <= bonf: out["exploratory_survivors"].append(dict(asset=a, month=m, dir=d, mean=mu, p=p, n=n))

os.makedirs("research/results", exist_ok=True)
with open("research/results/edge15_month_seasonality.json", "w") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("\n保存: research/results/edge15_month_seasonality.json")
