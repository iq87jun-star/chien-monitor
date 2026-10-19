# -*- coding: utf-8 -*-
"""
parallel_edge_hunt_10y.py — 「並行ポートフォリオ」用の "無相関の新エッジ" 一括事前登録探索(10年)。

背景: docs/14 は FX のみで 曜日/ターン・オブ・マンス を全数検定し全滅(円月曜=v7だけ生存)。
      edge5(docs/23) は多資産で TSMOM を検定し ADOPT ゼロ(MA2=E5 が STRONG-LEAD 止まり)。
      → ユーザー要望「新しい無相関エッジを探索」に対し、これまで未トライの "土俵" を厳格ハーネスで一括検定する:

  F1  株価指数ターン・オブ・マンス  : TOMは本来"株式"のアノマリー(月末リバランス・401k資金流入)。
                                       docs/14 はFXのみ→指数(US500/NAS100/GER40/UK100/JP225)+金で未検定。
  F2  株価指数 曜日効果             : 週末効果/月曜効果は株式の古典。指数で未検定。
  F3  暗号資産 曜日/週末            : BTC/ETH は7日取引→週末固有のフロー。FXと別クラス=分散先候補。
  F4  コモディティ 曜日            : 金/銀/WTI の曜日。
  F5  相対価値ペア(z-score平均回帰): US500-NAS100 / 金-銀 / EURUSD-GBPUSD / AUDUSD-NZDUSD / BTC-ETH。
                                       方向予測でもカレンダーでもない第3の系統(docs/14の選択肢3)。

全候補は事前登録し、合計試行数 N で Bonferroni 補正。各候補に v1-v6 を葬った同じハーネス:
  順列検定(符号シャッフル) / IS-OOS(70:30) / 全年ジャックナイフ / Bonferroni / コスト感応 /
  ★v7(円月曜)月次相関(並行ポートフォリオの肝=無相関でなければ"並行"の意味が無い)。

データ: research/data/<NAME>_d.csv (Yahoo日足10年, research/fetch_*.py で取得)。
規律: 数字を盛らない。出なければ「出ない」と書く。最終判定はユーザーのDukascopy/足内エンジン+デモ前進検証。
注意: Yahoo日足はOHLC概算・配当除く指数・先物近月。コストはbps控除の単純化。採用候補は必ず足内+デモで実測。
"""
import os, json, itertools, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# 往復コスト(bps)。指数/金は概ね数bps、暗号は約定/スプレッドが過酷→2倍で計上。
COST_BPS = {"US500": 3.0, "NAS100": 3.0, "GER40": 3.0, "UK100": 4.0, "JP225": 4.0,
            "XAUUSD": 4.0, "XAGUSD": 6.0, "WTI": 6.0, "BTCUSD": 12.0, "ETHUSD": 14.0}
DEFAULT_COST_BPS = 4.0


def load_daily(name, crypto=False):
    """日足を取引日へ正規化。crypto=Trueなら週末も残す(7日取引)。"""
    df = pd.read_csv(os.path.join(DATA, f"{name}_d.csv"))
    df["t"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t")
    df["trade_date"] = (df["t"] + pd.Timedelta(hours=2)).dt.floor("D")
    df = df.groupby("trade_date", as_index=True).last()
    df["weekday"] = df.index.dayofweek
    if not crypto:
        df = df[df["weekday"] <= 4]
    df["o2o"] = df["open"].shift(-1) / df["open"] - 1.0   # 当日open→翌足open(1営業日保有)
    df["c2c"] = df["close"].pct_change()                  # 相対価値用の日次リターン
    return df


# ---------------- 統計ユーティリティ ----------------
def perm_p(rets, n_iter=4000, seed=7):
    rets = np.asarray(rets, float)
    if len(rets) == 0:
        return 1.0
    rng = np.random.default_rng(seed); real = rets.sum(); s = np.abs(rets)
    null = np.array([(s * rng.choice([-1, 1], size=len(s))).sum() for _ in range(n_iter)])
    return float((null >= real).mean())


def stats(x):
    x = pd.Series(x).dropna()
    if len(x) == 0:
        return dict(net_pct=0, win_pct=0, maxDD_pct=0, n=0)
    eq = (1 + x).cumprod(); dd = ((eq - eq.cummax()) / eq.cummax()).min() * 100
    return dict(net_pct=round((eq.iloc[-1] - 1) * 100, 1), win_pct=round((x > 0).mean() * 100, 0),
                maxDD_pct=round(dd, 1), n=int(len(x)))


def to_monthly(r):
    """日次リターンSeries(index=date)を月次合算(近似:和)に。相関測定用。"""
    s = r.copy(); s.index = pd.to_datetime(s.index).to_period("M")
    return s.groupby(level=0).sum()


# ---------------- v7(円月曜)月次プロキシ = 無相関判定の基準 ----------------
def v7_monthly_ref():
    """v7 = 円3クロス 月曜LONG(open→翌open)。3ペア等加重の月次合算リターン。"""
    acc = None
    for p in ["EURJPY", "GBPJPY", "USDJPY"]:
        df = load_daily(p)
        mon = df[df["weekday"] == 0]["o2o"].dropna()      # 月曜のみ
        m = to_monthly(mon)
        acc = m if acc is None else acc.add(m, fill_value=0.0)
    return (acc / 3.0).rename("v7")


# ---------------- 候補シリーズ生成 ----------------
def dow_series(name, wd, direction, cost_bps=None, crypto=False):
    df = load_daily(name, crypto=crypto)
    c = (COST_BPS.get(name, DEFAULT_COST_BPS) if cost_bps is None else cost_bps) / 1e4
    sub = df[df["weekday"] == wd]
    return (direction * sub["o2o"] - c).dropna()


def tom_series(name, direction, cost_bps=None, last_n=1, first_n=3):
    df = load_daily(name).copy()
    c = (COST_BPS.get(name, DEFAULT_COST_BPS) if cost_bps is None else cost_bps) / 1e4
    ym = df.index.to_period("M")
    df["from_start"] = df.groupby(ym).cumcount() + 1
    df["from_end"] = df.groupby(ym).cumcount(ascending=False) + 1
    mask = (df["from_end"] <= last_n) | (df["from_start"] <= first_n)
    sub = df[mask]
    return (direction * sub["o2o"] - c).dropna()


def rv_series(a, b, direction, cost_bps=8.0, win=60, z_thr=2.0):
    """相対価値: spread=log(A)-log(B) のzスコア。direction=+1:平均回帰(乖離に逆張り) / -1:モメンタム。
       毎日リバランス(1日保有)で path 依存を避け順列検定を素直に。シグナルはt-1の確定zで建て、t日のスプレッド変化で損益。"""
    da = load_daily(a); db = load_daily(b)
    j = pd.concat([np.log(da["close"]).rename("a"), np.log(db["close"]).rename("b")], axis=1).dropna()
    spread = j["a"] - j["b"]
    z = (spread - spread.rolling(win).mean()) / spread.rolling(win).std()
    dspread = spread.diff()                       # その日のスプレッド変化(=ロングAショートBの損益近似)
    sig = -np.sign(z.shift(1)) * (z.shift(1).abs() >= z_thr)   # 平均回帰: 乖離の反対側に建てる
    c = cost_bps / 1e4
    turn = sig.diff().abs().fillna(0)             # 建て替え時のみコスト
    r = direction * sig * dspread - c * turn
    return r.dropna()


# ---------------- 候補レジストリ(事前登録) ----------------
INDICES = ["US500", "NAS100", "GER40", "UK100", "JP225"]
COMMODS = ["XAUUSD", "XAGUSD", "WTI"]
CRYPTOS = ["BTCUSD", "ETHUSD"]
RV_PAIRS = [("US500", "NAS100"), ("XAUUSD", "XAGUSD"), ("EURUSD", "GBPUSD"),
            ("AUDUSD", "NZDUSD"), ("BTCUSD", "ETHUSD")]


def build_candidates():
    cands = []
    # F1 株価指数+金 ターン・オブ・マンス
    for nm in INDICES + ["XAUUSD"]:
        for d in (+1, -1):
            lbl = f"{nm}_TOM_{'L' if d > 0 else 'S'}"
            cands.append((lbl, "F1_idxTOM", (lambda n=nm, dd=d: (lambda c=None: tom_series(n, dd, c)))()))
    # F2 株価指数 曜日
    for nm in INDICES:
        for wd in range(5):
            for d in (+1, -1):
                lbl = f"{nm}_{WD[wd]}_{'L' if d > 0 else 'S'}"
                cands.append((lbl, "F2_idxDOW", (lambda n=nm, w=wd, dd=d: (lambda c=None: dow_series(n, w, dd, c)))()))
    # F3 暗号 曜日(7日)
    for nm in CRYPTOS:
        for wd in range(7):
            for d in (+1, -1):
                lbl = f"{nm}_{WD[wd]}_{'L' if d > 0 else 'S'}"
                cands.append((lbl, "F3_cryptoDOW", (lambda n=nm, w=wd, dd=d: (lambda c=None: dow_series(n, w, dd, c, crypto=True)))()))
    # F4 コモディティ 曜日
    for nm in COMMODS:
        for wd in range(5):
            for d in (+1, -1):
                lbl = f"{nm}_{WD[wd]}_{'L' if d > 0 else 'S'}"
                cands.append((lbl, "F4_commDOW", (lambda n=nm, w=wd, dd=d: (lambda c=None: dow_series(n, w, dd, c)))()))
    # F5 相対価値(平均回帰=+1 / モメンタム=-1)
    for a, b in RV_PAIRS:
        for d in (+1, -1):
            lbl = f"RV_{a}_{b}_{'MR' if d > 0 else 'MO'}"
            cands.append((lbl, "F5_relval", (lambda x=a, y=b, dd=d: (lambda c=None: rv_series(x, y, dd, 8.0 if c is None else c)))()))
    return cands


def run():
    ref = v7_monthly_ref()
    cands = [(l, f, g) for (l, f, g) in build_candidates() if len(g()) >= 80]
    n_tests = len(cands)
    alpha = 0.05 / n_tests

    rows = []; GEN = {}
    for lbl, fam, gen in cands:
        GEN[lbl] = gen
        r = gen()
        p = perm_p(r.values)
        st = stats(r.values)
        cm = to_monthly(r)
        j = pd.concat([cm.rename("c"), ref.rename("r")], axis=1).dropna()
        corr = float(j["c"].corr(j["r"])) if len(j) > 30 else np.nan
        rows.append(dict(label=lbl, family=fam, **st, perm_p=round(p, 4),
                         corr_v7=round(corr, 2) if corr == corr else None))
    df = pd.DataFrame(rows).sort_values("perm_p").reset_index(drop=True)

    sig = df[df.perm_p <= 0.05].copy()
    surv = sig[sig.perm_p <= alpha].copy()

    # 二次ハーネス: Bonferroni生存 + (p<=0.05 かつ |v7相関|<=0.3 の無相関候補) を追検
    targets = pd.concat([surv, sig[sig.corr_v7.abs() <= 0.3]]).drop_duplicates("label")
    detail = {}
    for _, row in targets.iterrows():
        lbl = row["label"]; r = GEN[lbl]()
        half = r.index[len(r) // 2]
        is_ = stats(r[r.index < half].values); oos = stats(r[r.index >= half].values)
        oos_p = perm_p(r[r.index >= half].values)
        yrs = sorted(set(pd.to_datetime(r.index).year))
        jk = {int(y): round(perm_p(r[pd.to_datetime(r.index).year != y].values), 3) for y in yrs}
        base_c = COST_BPS.get(lbl.split("_")[0], 8.0)
        cost = {f"{m}x": stats(GEN[lbl](base_c * m).values)["net_pct"] for m in (1, 2, 3)}
        detail[lbl] = dict(
            full=dict(net_pct=row["net_pct"], win_pct=row["win_pct"], maxDD_pct=row["maxDD_pct"],
                      n=int(row["n"]), perm_p=row["perm_p"], corr_v7=row["corr_v7"]),
            bonferroni_survivor=bool(row["perm_p"] <= alpha),
            IS=is_, oos=dict(**oos, perm_p=round(oos_p, 4)),
            jackknife_max_p=round(max(jk.values()), 3), jackknife=jk, cost_net=cost)

    out = dict(n_tests=n_tests, alpha_bonf=round(alpha, 6),
               sig_count=int(len(sig)), bonferroni_survivors=int(len(surv)),
               span=[str(ref.index.min()), str(ref.index.max())],
               all_significant=sig.to_dict("records"), detail=detail)
    return df, sig, surv, out


if __name__ == "__main__":
    pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 200)
    df, sig, surv, out = run()

    bal = load_daily("US500")["weekday"].value_counts().sort_index()
    print("[sanity] US500 曜日件数(各~500/週末0なら正規化OK):", dict(zip([WD[i] for i in bal.index], bal.values)))
    cbal = load_daily("BTCUSD", crypto=True)["weekday"].value_counts().sort_index()
    print("[sanity] BTC 曜日件数(7日とも~500なら週末取引OK):", dict(zip([WD[i] for i in cbal.index], cbal.values)))

    print(f"\n全候補数(多重検定試行数) N = {out['n_tests']}   Bonferroni α = {out['alpha_bonf']}")
    print(f"\n===== 順列 p<=0.05 の候補 ({len(sig)}/{out['n_tests']}) =====")
    print(sig.to_string() if len(sig) else "  なし")
    print(f"\n===== ★Bonferroni 生存 (p<=α={out['alpha_bonf']}): {len(surv)}件 =====")
    print(surv.to_string() if len(surv) else "  なし")

    print("\n===== 追検対象(Bonferroni生存 + 無相関|corr_v7|<=0.3)の二次ハーネス =====")
    for k, d in out["detail"].items():
        f, o, i = d["full"], d["oos"], d["IS"]
        flag = "★BONF生存" if d["bonferroni_survivor"] else ""
        print(f"\n[{k}] {flag} 全:純益{f['net_pct']}% 勝率{f['win_pct']}% DD{f['maxDD_pct']}% n={f['n']} p={f['perm_p']} v7相関={f['corr_v7']}")
        print(f"   IS:純益{i['net_pct']}% / OOS:純益{o['net_pct']}% DD{o['maxDD_pct']}% p={o['perm_p']} | JKmax_p={d['jackknife_max_p']} | コスト{d['cost_net']}")

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "parallel_edge_hunt_10y.json"), "w") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/parallel_edge_hunt_10y.json")
