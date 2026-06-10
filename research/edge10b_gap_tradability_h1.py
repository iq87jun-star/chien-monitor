# -*- coding: utf-8 -*-
"""
edge10b_gap_tradability_h1.py — edge10 で Bonferroni 生存した GapFollow(US500/JP225) の
「実取引可能性」追検。

懸念(これを潰さないと採用判定できない):
  現物指数の寄付値(Yahoo ^GSPC/^N225 の open)は、構成銘柄の寄付遅れ(stale open)で
  真のギャップを過小表示する。すると open→close リターンには「印字寄付値→真の価格水準への
  機械的な収束」がギャップ方向に混入し、**取引不可能な見かけの利益**で GapFollow が盛れる。
  CFD/先物のトレーダーは既に全ギャップ織込み済みの価格でしか建てられない。

検定(H1・固定窓):
  T0 寄付バー始値エントリー(=edge10 と同じ・stale汚染あり) → 引け決済
  T1 寄付1時間後エントリー(=stale収束の外側・実際に建てられる) → 引け決済
  T2 寄付バー始値→寄付1時間後 決済(=最初の1時間だけ。stale汚染が集中するはずの区間)
  判定: T1 が T0 と同符号で有意に正なら「実取引可能な日中継続」。利益の大半が T2 に
  集中し T1 が死ぬなら stale-open アーティファクト → GapFollow は採用不可。

副診断(日足・10年, edge10 のデータ再利用):
  ギャップ方向別の分解(gap-up LONG のみ / gap-down SHORT のみ)。
  SHORT 側も独立に正なら「単なる上昇相場ベータ」では説明できない。

データ: Yahoo 60m(^GSPC/^N225)。60m は Yahoo 制約で直近~730日しか取れないため、
  固定窓は 2024-06-15..2025-12-31(凍結)。サンプルは日足10年より薄い=「方向の確認」用であり
  これ単体で有意性を主張しない。規律: 数字を盛らない。
"""
import os, json, time, datetime as dt
import urllib.request
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

from edge10_session_structure_10y import (load_daily, GAP_SIGMA, COST_BPS, DEFAULT_COST_BPS,
                                          perm_p, stats, ensure_data)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data"); RESULTS = os.path.join(HERE, "results")

# H1 固定窓(60m は Yahoo 制約 ~730日 → 2024-06-15..2025-12-31 に凍結)
H1_P1, H1_P2 = 1718409600, 1767225599
H1_SYM = {"US500": "^GSPC", "JP225": "^N225"}


def fetch_h1(name):
    p = os.path.join(DATA, f"{name}_h1.csv")
    if os.path.exists(p):
        return pd.read_csv(p)
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{H1_SYM[name]}"
         f"?period1={H1_P1}&period2={H1_P2}&interval=60m")
    last = None
    for k in range(6):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            d = json.loads(urllib.request.urlopen(req, timeout=25).read())
            r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
            rows = []
            for i, t in enumerate(ts):
                o, c = q["open"][i], q["close"][i]
                if None in (o, c):
                    continue
                d_ = dt.datetime.fromtimestamp(t, dt.timezone.utc).replace(tzinfo=None)
                rows.append((d_.strftime("%Y-%m-%d %H:%M:%S"), o, c))
            df = pd.DataFrame(rows, columns=["timestamp", "open", "close"])
            df.to_csv(p, index=False)
            return df
        except Exception as e:
            last = e; time.sleep(2 ** k)
    raise last


def h1_daily_legs(name):
    """H1 から日ごとの (寄付バー始値, 寄付1h後始値, 引けバー終値, 前日引け) を組む。"""
    df = fetch_h1(name)
    df["t"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("t")
    df["d"] = df["t"].dt.floor("D")
    out = []
    prev_close = None
    for d, g in df.groupby("d"):
        g = g.sort_values("t")
        if len(g) < 3:
            prev_close = g["close"].iloc[-1]; continue
        out.append(dict(d=d, o0=g["open"].iloc[0], o1=g["open"].iloc[1],
                        close=g["close"].iloc[-1], prev_close=prev_close))
        prev_close = g["close"].iloc[-1]
    z = pd.DataFrame(out).dropna()
    z["c2c"] = z["close"] / z["prev_close"] - 1.0
    z["sigma20"] = z["c2c"].rolling(20).std().shift(1)
    z["gap"] = z["o0"] / z["prev_close"] - 1.0
    return z.dropna()


def tradability(name):
    z = h1_daily_legs(name)
    sel = z[z["gap"].abs() > GAP_SIGMA * z["sigma20"]].copy()
    sgn = np.sign(sel["gap"])
    c = COST_BPS.get(name, DEFAULT_COST_BPS) / 1e4
    legs = {
        "T0_open_to_close":   sgn * (sel["close"] / sel["o0"] - 1.0) - c,
        "T1_open1h_to_close": sgn * (sel["close"] / sel["o1"] - 1.0) - c,
        "T2_open_to_open1h":  sgn * (sel["o1"] / sel["o0"] - 1.0) - c,
    }
    res = {}
    for k, r in legs.items():
        r = r.dropna()
        res[k] = dict(**stats(r.values), perm_p=round(perm_p(r.values), 4),
                      mean_bps=round(float(r.mean()) * 1e4, 1))
    res["n_events"] = int(len(sel))
    return res


def daily_side_split(name):
    """日足10年: gap-up LONG / gap-down SHORT を別々に採点(ベータ説明の排除)。"""
    df = load_daily(name)
    sel = df[(df["gap"].abs() > GAP_SIGMA * df["sigma20"]) & df["sigma20"].notna()]
    c = COST_BPS.get(name, DEFAULT_COST_BPS) / 1e4
    up = (sel[sel["gap"] > 0]["o2c"] - c).dropna()
    dn = (-sel[sel["gap"] < 0]["o2c"] - c).dropna()
    return {
        "gapup_LONG":  dict(**stats(up.values), perm_p=round(perm_p(up.values), 4)),
        "gapdn_SHORT": dict(**stats(dn.values), perm_p=round(perm_p(dn.values), 4)),
    }


if __name__ == "__main__":
    ensure_data()
    out = {}
    for nm in ["US500", "JP225"]:
        out[nm] = dict(daily_10y_side_split=daily_side_split(nm), h1_tradability=tradability(nm))

    for nm, d in out.items():
        s = d["daily_10y_side_split"]
        print(f"\n===== {nm} =====")
        print(f"[日足10年 方向分解] gap-up LONG: 純益{s['gapup_LONG']['net_pct']}% p={s['gapup_LONG']['perm_p']} n={s['gapup_LONG']['n']}"
              f" | gap-down SHORT: 純益{s['gapdn_SHORT']['net_pct']}% p={s['gapdn_SHORT']['perm_p']} n={s['gapdn_SHORT']['n']}")
        t = d["h1_tradability"]
        print(f"[H1 実取引可能性 2024-06..2025-12, events={t['n_events']}]")
        for k in ("T0_open_to_close", "T1_open1h_to_close", "T2_open_to_open1h"):
            v = t[k]
            print(f"  {k:20s} 純益{v['net_pct']:7.1f}% 平均{v['mean_bps']:6.1f}bps/回 p={v['perm_p']} n={v['n']}")
        print("  判定基準: T1>0 が残れば実取引可能 / 利益がT2集中・T1死亡なら stale-open アーティファクト")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "edge10b_gap_tradability_h1.json"), "w") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/edge10b_gap_tradability_h1.json")
