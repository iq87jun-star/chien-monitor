# -*- coding: utf-8 -*-
"""
calendar_event_edge_10y.py — 「曜日(DOW)・月末(TOM)以外」の未トライ・カレンダー系エッジ一括探索(10年)。

背景(これまでの土俵):
  - docs/14 : FX の 曜日 / ターン・オブ・マンス を全数検定 → 円月曜(v7)だけ生存。
  - docs/50 : 指数/暗号/コモディティの 曜日 / 指数TOM / 相対価値 を N=130 で検定 → 指数月曜(E-Mon)だけ生存。
  → どちらも検定したのは「曜日」と「月末(TOM)」のみ。本書はこれまで一度も検定していない
     "別系統のカレンダー/イベント・アノマリー" を、v1-v6/E-Mon を裁いたのと同一ハーネスで一括検定する:

  H  プレ祝日効果(pre-holiday): 市場休場の直前営業日。Ariel(1990)/Lakonishok-Smidt(1988)の古典。
       休場日は各資産の自前カレンダーの「平日ギャップ」から自動検出(ハードコード無し=再現性)。
  Y  年末年始(turn-of-year / Santa Claus rally): 12月最終 dec_n 営業日 + 1月最初 jan_n 営業日。
  M  月別シーズナリティ(month-of-year): 各暦月を丸ごと保有(Sell-in-May / 11-4月=Best Six Months 等)。

トレード定義(リポジトリ統一): trade_date の open でエントリ、翌 trade_date の open で決済(o2o, 1営業日保有)。
  プレ祝日は休場をまたいで翌寄付で決済(=プレ祝日+休場明けギャップを取る)。往復コストは bps 控除。

全候補は事前登録 → 合計 N で Bonferroni 補正。各候補に v1-v6/E-Mon を葬った同じ二次ハーネス:
  順列検定(符号シャッフル) / IS-OOS(70:30は無くプール半割) / 全年ジャックナイフ / Bonferroni / コスト感応 /
  ★既存エッジとの月次相関 = v7(円月曜) と E-Mon(指数月曜) の両方(候補が指数系→E-Mon冗長性チェックが肝)。

データ: research/data/<NAME>_d.csv(Yahoo日足10年, research/fetch_calendar.py)。
規律: 数字を盛らない。出なければ「出ない」と書く。Yahoo日足は配当除く指数・OHLC概算・bps単純化。
      採用候補は必ず Drive(配当込/CFD近似)+デモ前進検証で実測。「必ず通る手法」は存在しない。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# 往復コスト(bps)。指数/金は数bps。
COST_BPS = {"US500": 3.0, "NAS100": 3.0, "GER40": 3.0, "UK100": 4.0, "JP225": 4.0, "XAUUSD": 4.0}
DEFAULT_COST_BPS = 4.0
INDICES = ["US500", "NAS100", "GER40", "UK100", "JP225"]
UNIVERSE = INDICES + ["XAUUSD"]


def load_daily(name):
    df = pd.read_csv(os.path.join(DATA, f"{name}_d.csv"))
    df["t"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t")
    df["trade_date"] = (df["t"] + pd.Timedelta(hours=2)).dt.floor("D")
    df = df.groupby("trade_date", as_index=True).last()
    df["weekday"] = df.index.dayofweek
    df = df[df["weekday"] <= 4]                          # 平日のみ(休場ギャップ検出の前提)
    df["o2o"] = df["open"].shift(-1) / df["open"] - 1.0  # 当日open→翌営業日open
    return df


# ---------------- 統計ユーティリティ(既存ハーネスと同一) ----------------
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
    s = r.copy(); s.index = pd.to_datetime(s.index).to_period("M")
    return s.groupby(level=0).sum()


# ---------------- 既存エッジ 月次プロキシ(無相関判定の基準) ----------------
def v7_monthly_ref():
    """v7 = 円3クロス 月曜LONG(open→翌open)。"""
    acc = None
    for p in ["EURJPY", "GBPJPY", "USDJPY"]:
        df = load_daily(p)
        m = to_monthly(df[df["weekday"] == 0]["o2o"].dropna())
        acc = m if acc is None else acc.add(m, fill_value=0.0)
    return (acc / 3.0).rename("v7")


def emon_monthly_ref():
    """E-Mon = 指数3つ(US500/NAS100/GER40) 月曜LONG(open→翌open) 等加重。"""
    acc = None
    for nm in ["US500", "NAS100", "GER40"]:
        df = load_daily(nm)
        c = COST_BPS.get(nm, DEFAULT_COST_BPS) / 1e4
        m = to_monthly((df[df["weekday"] == 0]["o2o"] - c).dropna())
        acc = m if acc is None else acc.add(m, fill_value=0.0)
    return (acc / 3.0).rename("emon")


# ---------------- 候補シリーズ生成 ----------------
def _cost(name, cost_bps):
    return (COST_BPS.get(name, DEFAULT_COST_BPS) if cost_bps is None else cost_bps) / 1e4


def preholiday_series(name, direction, cost_bps=None):
    """市場休場の直前営業日(=次営業日が想定より先=ギャップ)で建て、休場明け翌寄付で決済。"""
    df = load_daily(name).copy()
    gap = df.index.to_series().diff().shift(-1).dt.days.values   # 当日→次の取引日までの暦日数
    expected = np.where(df["weekday"].values <= 3, 1, 3)         # Mon-Thu=翌日, Fri=月曜
    pre = (gap > expected) & ~np.isnan(gap)                       # 想定超 = 間に休場
    sub = df[pre]
    return (direction * sub["o2o"] - _cost(name, cost_bps)).dropna()


def turnofyear_series(name, direction, dec_n=5, jan_n=2, cost_bps=None):
    """年末年始: 各年の12月 最終 dec_n 営業日 + 1月 最初 jan_n 営業日(o2o)。"""
    df = load_daily(name).copy()
    yr = df.index.year; mo = df.index.month
    df["yr"], df["mo"] = yr, mo
    # 12月: 月内 末尾から dec_n 日
    dec = df[df["mo"] == 12].copy()
    dec["from_end"] = dec.groupby("yr").cumcount(ascending=False) + 1
    dec_sel = dec[dec["from_end"] <= dec_n]
    # 1月: 月初から jan_n 日
    jan = df[df["mo"] == 1].copy()
    jan["from_start"] = jan.groupby("yr").cumcount() + 1
    jan_sel = jan[jan["from_start"] <= jan_n]
    sub = pd.concat([dec_sel, jan_sel]).sort_index()
    return (direction * sub["o2o"] - _cost(name, cost_bps)).dropna()


def month_series(name, month, direction, cost_bps=None):
    """月別: 暦月 month を丸ごと保有(各営業日 o2o)。"""
    df = load_daily(name)
    sub = df[df.index.month == month]
    return (direction * sub["o2o"] - _cost(name, cost_bps)).dropna()


def bestsix_series(name, direction, cost_bps=None):
    """Best Six Months(Sell-in-May): 11,12,1,2,3,4月を保有。"""
    df = load_daily(name)
    sub = df[df.index.month.isin([11, 12, 1, 2, 3, 4])]
    return (direction * sub["o2o"] - _cost(name, cost_bps)).dropna()


# ---------------- 年次ブロック評価(単月シーズナリティの"正直な"サンプル数=年数) ----------------
def yearly_returns(r):
    """日次o2oリターンSeriesを年ごとに複利合算 → 1年=1観測。単月戦略の実サンプル数は年数。"""
    s = pd.Series(r).dropna()
    if len(s) == 0:
        return pd.Series(dtype=float)
    g = (1 + s).groupby(pd.to_datetime(s.index).year).prod() - 1.0
    return g


def yearly_block_p(r, n_iter=20000, seed=11):
    """年次合算リターンに対する符号反転順列検定(=年を独立ブロックとした片側p)。"""
    y = yearly_returns(r).values
    if len(y) < 3:
        return 1.0, len(y)
    rng = np.random.default_rng(seed); real = y.sum(); a = np.abs(y)
    null = np.array([(a * rng.choice([-1, 1], size=len(a))).sum() for _ in range(n_iter)])
    return float((null >= real).mean()), len(y)


def index_basket(month_or_fn, indices, cost_bps=None):
    """指数バスケット(等加重)の日次リターン。month_or_fn=int(月) または callable(name)->Series。"""
    acc = None
    for nm in indices:
        if callable(month_or_fn):
            r = month_or_fn(nm)
        else:
            r = month_series(nm, month_or_fn, +1, cost_bps)
        acc = r if acc is None else acc.add(r, fill_value=0.0)
    return (acc / len(indices)).dropna()


# ---------------- 候補レジストリ(事前登録) ----------------
def build_candidates():
    cands = []
    for nm in UNIVERSE:
        for d in (+1, -1):
            tag = "L" if d > 0 else "S"
            cands.append((f"{nm}_PreHol_{tag}", "H_preHoliday",
                          (lambda n=nm, dd=d: (lambda c=None: preholiday_series(n, dd, c)))()))
            cands.append((f"{nm}_TurnYear_{tag}", "Y_turnOfYear",
                          (lambda n=nm, dd=d: (lambda c=None: turnofyear_series(n, dd, cost_bps=c)))()))
            cands.append((f"{nm}_BestSix_{tag}", "M_bestSix",
                          (lambda n=nm, dd=d: (lambda c=None: bestsix_series(n, dd, c)))()))
            for mo in range(1, 13):
                cands.append((f"{nm}_{MONTHS[mo-1]}_{tag}", "M_monthOfYear",
                              (lambda n=nm, m=mo, dd=d: (lambda c=None: month_series(n, m, dd, c)))()))
    return cands


def run():
    refs = {"v7": v7_monthly_ref(), "emon": emon_monthly_ref()}
    cands = [(l, f, g) for (l, f, g) in build_candidates() if len(g()) >= 80]
    n_tests = len(cands)
    alpha = 0.05 / n_tests

    rows = []; GEN = {}
    for lbl, fam, gen in cands:
        GEN[lbl] = gen
        r = gen()
        p = perm_p(r.values); st = stats(r.values); cm = to_monthly(r)
        cc = {}
        for k, ref in refs.items():
            j = pd.concat([cm.rename("c"), ref.rename("r")], axis=1).dropna()
            cc[f"corr_{k}"] = round(float(j["c"].corr(j["r"])), 2) if len(j) > 30 else None
        rows.append(dict(label=lbl, family=fam, **st, perm_p=round(p, 4), **cc))
    df = pd.DataFrame(rows).sort_values("perm_p").reset_index(drop=True)

    sig = df[df.perm_p <= 0.05].copy()
    surv = sig[sig.perm_p <= alpha].copy()

    # 二次ハーネス: Bonferroni生存 + (p<=0.05 かつ 両既存エッジと |相関|<=0.3 の無相関候補)
    #   相関が None/NaN(=活動月が少なく重なりが無い→構造的に分散)も「無相関」として追検対象に含める。
    def _ok(v):
        return v is None or (isinstance(v, float) and np.isnan(v)) or abs(v) <= 0.3
    def uncorr(row):
        return _ok(row.get("corr_v7")) and _ok(row.get("corr_emon"))
    targets = pd.concat([surv, sig[sig.apply(uncorr, axis=1)]]).drop_duplicates("label")
    detail = {}
    for _, row in targets.iterrows():
        lbl = row["label"]; r = GEN[lbl]()
        half = r.index[len(r) // 2]
        is_ = stats(r[r.index < half].values); oos = stats(r[r.index >= half].values)
        oos_p = perm_p(r[r.index >= half].values)
        yrs = sorted(set(pd.to_datetime(r.index).year))
        jk = {int(y): round(perm_p(r[pd.to_datetime(r.index).year != y].values), 3) for y in yrs}
        base_c = COST_BPS.get(lbl.split("_")[0], DEFAULT_COST_BPS)
        cost = {f"{m}x": stats(GEN[lbl](base_c * m).values)["net_pct"] for m in (1, 2, 3)}
        yb_p, yb_n = yearly_block_p(r)                  # ★年次ブロック=正直なサンプル数の片側p
        yr = yearly_returns(r)
        detail[lbl] = dict(
            full=dict(net_pct=row["net_pct"], win_pct=row["win_pct"], maxDD_pct=row["maxDD_pct"],
                      n=int(row["n"]), perm_p=row["perm_p"], corr_v7=row.get("corr_v7"), corr_emon=row.get("corr_emon")),
            bonferroni_survivor=bool(row["perm_p"] <= alpha),
            yearly_block_p=round(yb_p, 4), yearly_n=int(yb_n),
            yearly_pos_pct=round(float((yr > 0).mean()) * 100, 0) if len(yr) else None,
            IS=is_, oos=dict(**oos, perm_p=round(oos_p, 4)),
            jackknife_max_p=round(max(jk.values()), 3), jackknife=jk, cost_net=cost)

    # ---------------- バスケット採点(E-Mon流 "1現象を多指数でサンプル") ----------------
    # S-Nov = US500/NAS100/GER40 の11月ロング等加重 / S-Jul = US500/NAS100 の7月ロング等加重。
    baskets = {
        "S-Nov(US500+NAS100+GER40 Nov L)": index_basket(11, ["US500", "NAS100", "GER40"]),
        "S-Jul(US500+NAS100 Jul L)":       index_basket(7, ["US500", "NAS100"]),
    }
    basket_out = {}
    for bname, br in baskets.items():
        yb_p, yb_n = yearly_block_p(br)
        yr = yearly_returns(br)
        bm = to_monthly(br)
        cc = {}
        for k, ref in refs.items():
            j = pd.concat([bm.rename("c"), ref.rename("r")], axis=1).dropna()
            cc[f"corr_{k}"] = round(float(j["c"].corr(j["r"])), 2) if len(j) > 8 else None
        basket_out[bname] = dict(
            **stats(br.values), daily_perm_p=round(perm_p(br.values), 4),
            yearly_block_p=round(yb_p, 4), yearly_n=int(yb_n),
            yearly_pos_pct=round(float((yr > 0).mean()) * 100, 0),
            yearly_mean_pct=round(float(yr.mean()) * 100, 2), yearly_min_pct=round(float(yr.min()) * 100, 2),
            cost2x_net=stats(index_basket(11 if "Nov" in bname else 7,
                             ["US500", "NAS100", "GER40"] if "Nov" in bname else ["US500", "NAS100"],
                             cost_bps=8.0).values)["net_pct"],
            **cc)

    out = dict(n_tests=n_tests, alpha_bonf=round(alpha, 6),
               sig_count=int(len(sig)), bonferroni_survivors=int(len(surv)),
               span=[str(refs["v7"].index.min()), str(refs["v7"].index.max())],
               all_significant=sig.to_dict("records"), detail=detail, baskets=basket_out)
    return df, sig, surv, out


if __name__ == "__main__":
    pd.set_option("display.width", 240); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 300)
    df, sig, surv, out = run()

    bal = load_daily("US500")["weekday"].value_counts().sort_index()
    print("[sanity] US500 曜日件数(各~500/週末0なら正規化OK):", dict(zip(range(5), bal.values)))
    ph = preholiday_series("US500", +1)
    print(f"[sanity] US500 検出プレ祝日数(10年): {len(ph)} (米株の年間休場~9 → 10年で~90が目安)")

    print(f"\n全候補数(多重検定試行数) N = {out['n_tests']}   Bonferroni α = {out['alpha_bonf']}")
    print(f"\n===== 順列 p<=0.05 の候補 ({len(sig)}/{out['n_tests']}) =====")
    print(sig.to_string() if len(sig) else "  なし")
    print(f"\n===== ★Bonferroni 生存 (p<=α={out['alpha_bonf']}): {len(surv)}件 =====")
    print(surv.to_string() if len(surv) else "  なし")

    print("\n===== 追検対象(Bonferroni生存 + 既存2エッジと無相関|corr|<=0.3)の二次ハーネス =====")
    print("(★年次ブロックp = 年を独立サンプルとした正直な片側p。日次pは過大評価しうる)")
    for k, d in out["detail"].items():
        f, o, i = d["full"], d["oos"], d["IS"]
        flag = "★BONF生存" if d["bonferroni_survivor"] else ""
        print(f"\n[{k}] {flag} 全:純益{f['net_pct']}% 勝率{f['win_pct']}% DD{f['maxDD_pct']}% n={f['n']} 日次p={f['perm_p']} "
              f"v7相関={f['corr_v7']} Emon相関={f['corr_emon']}")
        print(f"   ★年次ブロックp={d['yearly_block_p']} (年数={d['yearly_n']}, 陽性年{d['yearly_pos_pct']}%) | "
              f"IS純益{i['net_pct']}% / OOS純益{o['net_pct']}% p={o['perm_p']} | JKmax_p={d['jackknife_max_p']} | コスト{d['cost_net']}")

    print("\n===== バスケット採点(E-Mon流: 1シーズナル現象を多指数でサンプル) =====")
    for bname, b in out["baskets"].items():
        print(f"\n[{bname}] 純益{b['net_pct']}% 勝率{b['win_pct']}% DD{b['maxDD_pct']}% n={b['n']}")
        print(f"   日次p={b['daily_perm_p']} | ★年次ブロックp={b['yearly_block_p']}(年数{b['yearly_n']}, 陽性年{b['yearly_pos_pct']}%, "
              f"年平均{b['yearly_mean_pct']}%, 最悪年{b['yearly_min_pct']}%)")
        print(f"   コスト2x純益={b['cost2x_net']}% | v7相関={b['corr_v7']} E-Mon相関={b['corr_emon']}")

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "calendar_event_edge_10y.json"), "w") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/calendar_event_edge_10y.json")
