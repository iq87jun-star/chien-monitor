#!/usr/bin/env python3
"""非FXポートフォリオ RecentFit流スクリーニング (2026-08 クラウド検証).

背景: chien-monitor リポジトリには研究資産(recentfit_screen.py/docs/174/175)が
無いため、EA(mql/Fintokei_6078225_RecentFit_C6m_v1.03.mq5)のコメントから
方法論を再構成したもの。オリジナルの再現ではない点に注意。

方針(事前固定・docs/174流のEVベット):
  - セル族: DOW(曜日o2o L/S) / v4(日足4条件合議・EAパリティ) / SEASON(月次L/S)
  - 選抜窓: DOW/v4=直近12ヶ月(直近特化)。SEASONは1年に1観測しかないため
    全期間(≈10年)のヒット率で選抜(族が別物であることを明記)。
  - 多重検定の誠実な記録: 全セル数を報告(選抜セルはノイズで入れ替わる前提)。
  - 相関フィルタ: 現行C6mレッグ(Mon GBPJPY/AUDJPY, v4 NZDUSD/AUDUSD)の
    プロキシとの|ρ|>0.4で除外、採用セル同士は|ρ|>0.5で後着除外。
  - 重み: 銘柄の年率ボラ逆数で正規化(Σw=1.0)。倍率は口座側で別途。

データ: Yahoo Finance chart API 日足(通常のHTTPS GET)。
実行: python3 research/nonfx_screen.py  (キャッシュ: research/.cache/*.json)
"""
import json, math, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone

UA = "Mozilla/5.0 (X11; Linux x86_64)"
CACHE = os.path.join(os.path.dirname(__file__), ".cache")


def fetch_daily(ysym, rng="10y"):
    os.makedirs(CACHE, exist_ok=True)
    fn = os.path.join(CACHE, re.sub(r"[^A-Za-z0-9]", "_", ysym) + ".json")
    if os.path.exists(fn) and time.time() - os.path.getmtime(fn) < 86400:
        return json.load(open(fn))
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(ysym)}?range={rng}&interval=1d")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.loads(r.read().decode())
    r = d["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    rows = []
    for i, ts in enumerate(r["timestamp"]):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c) or o <= 0:
            continue
        day = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        rows.append([day, o, h, l, c])
    json.dump(rows, open(fn, "w"))
    return rows

# ------------------------------------------------------------------ universe
# (Yahooシンボル, 表示名, CFD相当) — 非FX: 指数/貴金属/エネルギー/銅
UNIVERSE = [
    ("^N225", "JP225"), ("^GSPC", "US500"), ("^DJI", "US30"), ("^NDX", "NAS100"),
    ("^GDAXI", "GER40"), ("^FTSE", "UK100"), ("^STOXX50E", "EUSTX50"),
    ("^HSI", "HK50"), ("^AXJO", "AUS200"),
    ("GC=F", "XAUUSD"), ("SI=F", "XAGUSD"), ("PL=F", "XPTUSD"), ("HG=F", "COPPER"),
    ("CL=F", "USOIL"), ("BZ=F", "UKOIL"), ("NG=F", "NATGAS"),
]
# 現行全ブックのプロキシ(相関除外用)。2026-08-15改訂:
# claude/ea-code-review-integration-p8p06z の焼き込みEA群から全口座のレッグを抽出。
#   Instant20k/パール500万: Mon GBPJPY/AUDJPY + v4 USDJPY
#   C6m系(FTMO50k/速攻プロ2000万): Mon GBPJPY/AUDJPY + v4 NZDUSD/AUDUSD
#   D3m(FTMO50k): Mon USDJPY/GBPJPY + v4 NZDUSD/AUDUSD
#   fn100k非FX(FN#14166201): Mon ETHUSD + v4 BTCUSD + Hold UK100/WTI
CURRENT_LEGS = [
    ("GBPJPY=X", "cur_Mon_GBPJPY", "DOW", ("Mon", +1)),
    ("AUDJPY=X", "cur_Mon_AUDJPY", "DOW", ("Mon", +1)),
    ("USDJPY=X", "cur_Mon_USDJPY", "DOW", ("Mon", +1)),
    ("ETH-USD", "cur_Mon_ETHUSD", "DOW", ("Mon", +1)),
    ("USDJPY=X", "cur_v4_USDJPY", "V4", None),
    ("NZDUSD=X", "cur_v4_NZDUSD", "V4", None),
    ("AUDUSD=X", "cur_v4_AUDUSD", "V4", None),
    ("BTC-USD", "cur_v4_BTCUSD", "V4", None),
    ("^FTSE", "cur_Hold_UK100", "HOLD", None),
    ("CL=F", "cur_Hold_WTI", "HOLD", None),
]
# 銘柄除外(2026-08-15 rev4: RG3「置き換え」ユーザー決定):
#   UK100/USOIL: FN#14166201(非FXトラック)使用中 — FN口座間の同一取引禁止
#   (rev3のJP225/XAUUSD除外はRG3並走前提だった。置き換え=RG3停止により解除。
#    ただしRG3停止前に本EAを起動しないこと=移行手順で順序を保証する)
EXCLUDE_SYMBOLS = {"UK100", "USOIL"}
DOWS = ["Mon", "Tue", "Wed", "Thu", "Fri"]

# ------------------------------------------------------------ cell simulators
def dow_daily_returns(rows, dow_idx, direction):
    """曜日o2o: 対象曜日の寄りで建て翌営業日の寄りで手仕舞い。日次リターン系列。"""
    out = {}
    for i in range(len(rows) - 1):
        d = datetime.strptime(rows[i][0], "%Y-%m-%d")
        if d.weekday() == dow_idx:
            r = (rows[i + 1][1] - rows[i][1]) / rows[i][1]
            out[rows[i + 1][0]] = direction * r
    return out


def rsi14(closes):
    """EAのiRSI(14)パリティ(Wilder平滑)。closes全系列→各indexのRSI。"""
    n = 14
    rsis = [None] * len(closes)
    if len(closes) < n + 1:
        return rsis
    gains = losses = 0.0
    for i in range(1, n + 1):
        ch = closes[i] - closes[i - 1]
        gains += max(ch, 0); losses += max(-ch, 0)
    ag, al = gains / n, losses / n
    rsis[n] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    for i in range(n + 1, len(closes)):
        ch = closes[i] - closes[i - 1]
        ag = (ag * (n - 1) + max(ch, 0)) / n
        al = (al * (n - 1) + max(-ch, 0)) / n
        rsis[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return rsis


def atr14(rows):
    n = 14
    atrs = [None] * len(rows)
    trs = []
    for i in range(len(rows)):
        _, o, h, l, c = rows[i]
        if i == 0:
            trs.append(h - l)
        else:
            pc = rows[i - 1][4]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        if i == n - 1:
            atrs[i] = sum(trs[:n]) / n
        elif i >= n:
            atrs[i] = (atrs[i - 1] * (n - 1) + trs[i]) / n
    return atrs


def v4_trades(rows, allow_short=True):
    """EAのV4Signalパリティ: RSI14<35 / z(BB20)<-1.5 / 3日連続 / 日中0.5%超 の
    4条件全成立で翌寄り成行。SL=1.5*ATR14 / TP=1.2*SL / 最大8日で翌寄り手仕舞い。
    SL/TP同日ヒットはSL優先(保守側)。戻り値: [(entry日, exit日, リターン, 方向)]"""
    closes = [r[4] for r in rows]
    rs = rsi14(closes)
    at = atr14(rows)
    trades = []
    i = 21
    while i < len(rows) - 1:
        # シグナルはi日の終値時点(EAは新D1バーでshift1評価)
        c0, c1 = closes[i], closes[i - 1]
        win = closes[i - 19:i + 1]
        if len(win) < 20 or rs[i] is None or at[i] is None or at[i] <= 0:
            i += 1; continue
        mean = sum(win) / 20
        var = sum((x - mean) ** 2 for x in win) / 19
        sd = math.sqrt(var)
        z = (c0 - mean) / sd if sd > 0 else 0.0
        down = up = 0
        for k in range(12):
            if i - k - 1 < 0: break
            if closes[i - k] < closes[i - k - 1]: down += 1
            else: break
        for k in range(12):
            if i - k - 1 < 0: break
            if closes[i - k] > closes[i - k - 1]: up += 1
            else: break
        ret = (c0 - c1) / c1 if c1 else 0.0
        buy = (rs[i] < 35) + (z < -1.5) + (down >= 3) + (ret < -0.005)
        sell = (rs[i] > 65) + (z > 1.5) + (up >= 3) + (ret > 0.005)
        sig = 0
        if buy >= 4 and buy > sell: sig = 1
        elif sell >= 4 and sell > buy and allow_short: sig = -1
        if sig == 0:
            i += 1; continue
        e = rows[i + 1][1]  # 翌寄り
        sd_px = 1.5 * at[i]; tp_px = 1.2 * sd_px
        sl = e - sig * sd_px; tp = e + sig * tp_px
        exit_px, exit_i = None, min(i + 1 + 8, len(rows) - 1)
        for j in range(i + 1, min(i + 1 + 8, len(rows))):
            _, o, h, l, c = rows[j]
            if sig > 0:
                if l <= sl: exit_px, exit_i = sl, j; break
                if h >= tp: exit_px, exit_i = tp, j; break
            else:
                if h >= sl: exit_px, exit_i = sl, j; break
                if l <= tp: exit_px, exit_i = tp, j; break
        if exit_px is None:
            exit_px = rows[exit_i][1]
        trades.append((rows[i + 1][0], rows[exit_i][0], sig * (exit_px - e) / e, sig))
        i = exit_i + 1
    return trades


def v4_daily_returns(rows, allow_short=True):
    out = {}
    idx = {r[0]: k for k, r in enumerate(rows)}
    for ent, ex, _, sig in v4_trades(rows, allow_short):
        i0, i1 = idx[ent], idx[ex]
        for j in range(i0, i1 + 1):
            base = rows[j - 1][4] if j > i0 else rows[j][1]
            px = rows[j][4]
            out[rows[j][0]] = out.get(rows[j][0], 0.0) + sig * (px - base) / base
    return out


def season_yearly(rows, month, direction):
    """月次シーズナル: 当月初営業日寄り→翌月初営業日寄り。年毎リターン。"""
    firsts = {}
    for i, r in enumerate(rows):
        d = datetime.strptime(r[0], "%Y-%m-%d")
        key = (d.year, d.month)
        if key not in firsts:
            firsts[key] = i
    out = []
    for (y, m), i0 in sorted(firsts.items()):
        if m != month: continue
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        i1 = firsts.get((ny, nm))
        if i1 is None: continue
        out.append((y, direction * (rows[i1][1] - rows[i0][1]) / rows[i0][1]))
    return out


def hold_daily_returns(rows):
    """Hold(連続LONG)プロキシ: 終値ベース日次リターン。"""
    return {rows[i][0]: (rows[i][4] - rows[i - 1][4]) / rows[i - 1][4]
            for i in range(1, len(rows))}


def season_daily_returns(rows, month, direction):
    out = {}
    for i in range(1, len(rows)):
        d = datetime.strptime(rows[i][0], "%Y-%m-%d")
        if d.month == month:
            out[rows[i][0]] = direction * (rows[i][4] - rows[i - 1][4]) / rows[i - 1][4]
    return out

# ------------------------------------------------------------------ metrics
def window_stats(daily, start, end):
    vals = [v for d, v in daily.items() if start <= d <= end]
    n = len([v for v in vals if v != 0.0])
    tot = sum(vals)
    if n < 2:
        return dict(n=n, tot=tot, t=0.0)
    act = [v for v in vals if v != 0.0]
    mu = sum(act) / len(act)
    sd = math.sqrt(sum((v - mu) ** 2 for v in act) / (len(act) - 1))
    t = mu / sd * math.sqrt(len(act)) if sd > 0 else 0.0
    return dict(n=n, tot=tot, t=t)


def ann_vol(rows, lookback=250):
    cs = [r[4] for r in rows[-lookback - 1:]]
    rets = [(cs[i] - cs[i - 1]) / cs[i - 1] for i in range(1, len(cs))]
    mu = sum(rets) / len(rets)
    sd = math.sqrt(sum((r - mu) ** 2 for r in rets) / (len(rets) - 1))
    return sd * math.sqrt(252)


def corr(a, b):
    days = sorted(set(a) | set(b))
    if len(days) < 30:
        return 0.0
    xs = [a.get(d, 0.0) for d in days]
    ys = [b.get(d, 0.0) for d in days]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)

# --------------------------------------------------------------------- main
def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yr_ago = (datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year - 1)).strftime("%Y-%m-%d")
    data = {}
    for ysym, name in UNIVERSE:
        try:
            data[name] = fetch_daily(ysym)
            print(f"[data] {name:8s} {len(data[name])} bars {data[name][0][0]}..{data[name][-1][0]}", file=sys.stderr)
        except Exception as e:
            print(f"[data] {name}: FAILED {e}", file=sys.stderr)

    cur = {}
    for ysym, name, fam, arg in CURRENT_LEGS:
        try:
            rows = fetch_daily(ysym)
            if fam == "DOW":
                cur[name] = dow_daily_returns(rows, DOWS.index(arg[0]), arg[1])
            elif fam == "HOLD":
                cur[name] = hold_daily_returns(rows)
            else:
                cur[name] = v4_daily_returns(rows)
            print(f"[cur ] {name} ok", file=sys.stderr)
        except Exception as e:
            print(f"[cur ] {name}: FAILED {e}", file=sys.stderr)

    cells = []  # (id, family, symbol, daily, stat12, statall, extra)
    for name, rows in data.items():
        # DOW族
        for di, dow in enumerate(DOWS):
            for dirn, dl in [(+1, "L"), (-1, "S")]:
                daily = dow_daily_returns(rows, di, dirn)
                s12 = window_stats(daily, yr_ago, today)
                sall = window_stats(daily, "0000", today)
                cells.append((f"DOW_{name}_{dow}_{dl}", "DOW", name, daily, s12, sall, None))
        # v4族(方向はシグナル任せ=1セル)
        daily = v4_daily_returns(rows)
        trades = v4_trades(rows)
        t12 = [t for t in trades if t[0] >= yr_ago]
        s12 = dict(n=len(t12), tot=sum(t[2] for t in t12),
                   t=(lambda a: (sum(a)/len(a))/ (math.sqrt(sum((x-sum(a)/len(a))**2 for x in a)/(len(a)-1))) * math.sqrt(len(a)) if len(a) > 2 and math.sqrt(sum((x-sum(a)/len(a))**2 for x in a)/(len(a)-1))>0 else 0.0)([t[2] for t in t12]) if len(t12) > 2 else 0.0)
        sall = dict(n=len(trades), tot=sum(t[2] for t in trades), t=0.0)
        cells.append((f"V4_{name}", "V4", name, daily, s12, sall, trades))
        # SEASON族(全期間ヒット率選抜)
        for month in range(1, 13):
            for dirn, dl in [(+1, "L"), (-1, "S")]:
                yearly = season_yearly(rows, month, dirn)
                if len(yearly) < 6: continue
                wins = sum(1 for _, r in yearly if r > 0)
                mu = sum(r for _, r in yearly) / len(yearly)
                daily = season_daily_returns(rows, month, dirn)
                s12 = window_stats(daily, yr_ago, today)
                cells.append((f"SEA_{name}_{month:02d}_{dl}", "SEASON", name, daily,
                              s12, dict(n=len(yearly), tot=sum(r for _, r in yearly), t=0.0),
                              dict(hit=wins / len(yearly), mu=mu, years=len(yearly))))

    print(f"\n=== セル総数(多重検定の規模): {len(cells)} "
          f"(DOW {sum(1 for c in cells if c[1]=='DOW')} / V4 {sum(1 for c in cells if c[1]=='V4')} / "
          f"SEASON {sum(1 for c in cells if c[1]=='SEASON')}) ===")

    # --- 選抜: DOW/v4=直近12M tスタット, SEASON=全期間ヒット率×平均
    def rank_key(c):
        if c[1] == "SEASON":
            return (c[6]["hit"], c[6]["mu"])
        return (c[4]["t"], c[4]["tot"])

    MIN_N = {"DOW": 30, "V4": 5, "SEASON": 8}
    pool = []
    for c in cells:
        if c[2] in EXCLUDE_SYMBOLS:
            continue
        fam = c[1]
        n = c[6]["years"] if fam == "SEASON" else c[4]["n"]
        if n < MIN_N[fam]: continue
        if fam == "SEASON" and (c[6]["hit"] < 0.7 or c[6]["mu"] <= 0 or c[4]["tot"] <= 0):
            continue  # 全期間7割ヒット+直近12Mも正
        if fam != "SEASON" and (c[4]["t"] < 1.0 or c[4]["tot"] <= 0):
            continue
        pool.append(c)
    pool.sort(key=rank_key, reverse=True)

    print(f"=== 一次候補 {len(pool)}セル(上位20) ===")
    for c in pool[:20]:
        ex = f" hit={c[6]['hit']:.2f} mu={c[6]['mu']*100:+.2f}%/月 yrs={c[6]['years']}" if c[1] == "SEASON" else ""
        print(f"  {c[0]:24s} 12M: n={c[4]['n']:3d} tot={c[4]['tot']*100:+7.2f}% t={c[4]['t']:5.2f} | "
              f"全期間: n={c[5]['n']:4d} tot={c[5]['tot']*100:+8.2f}%{ex}")

    # --- 相関フィルタ(現行レッグ|ρ|>0.4除外 → 相互|ρ|>0.5後着除外, 同一銘柄は1族まで)
    CUR_RHO, X_RHO, MAX_CELLS = 0.4, 0.5, 6
    picked, sym_used = [], {}
    for c in pool:
        if len(picked) >= MAX_CELLS: break
        rhos_cur = {k: corr(c[3], v) for k, v in cur.items()}
        if any(abs(r) > CUR_RHO for r in rhos_cur.values()):
            print(f"  [除外] {c[0]}: 現行レッグ相関 " +
                  ", ".join(f"{k}={v:+.2f}" for k, v in rhos_cur.items() if abs(v) > CUR_RHO))
            continue
        if any(abs(corr(c[3], p[3])) > X_RHO for p in picked):
            print(f"  [除外] {c[0]}: 採用済みセルと相関>|{X_RHO}|")
            continue
        if sym_used.get(c[2], 0) >= 2:
            print(f"  [除外] {c[0]}: 同一銘柄2セル上限")
            continue
        picked.append(c)
        sym_used[c[2]] = sym_used.get(c[2], 0) + 1

    # --- 重み: 年率ボラ逆数正規化
    invvols = {c[0]: 1.0 / max(ann_vol(data[c[2]]), 1e-6) for c in picked}
    tot_iv = sum(invvols.values())
    print(f"\n=== 採用 {len(picked)}セル(重み=年率ボラ逆数正規化 Σw=1.0) ===")
    for c in picked:
        w = invvols[c[0]] / tot_iv
        rhos = " ".join(f"{k.split('_',1)[1]}={corr(c[3],v):+.2f}" for k, v in cur.items())
        ex = f" hit={c[6]['hit']:.2f} mu={c[6]['mu']*100:+.2f}%/月({c[6]['years']}y)" if c[1] == "SEASON" else ""
        print(f"  {c[0]:24s} w={w:.3f} vol={ann_vol(data[c[2]])*100:5.1f}% "
              f"12Mtot={c[4]['tot']*100:+6.2f}%{ex} | 現行相関: {rhos}")

    # ポートフォリオ合成(全期間+直近12M)
    port = {}
    for c in picked:
        w = invvols[c[0]] / tot_iv
        for d, v in c[3].items():
            port[d] = port.get(d, 0.0) + w * v
    ps = window_stats(port, yr_ago, today)
    days = sorted(port)
    eqty, peak, mdd12 = 0.0, 0.0, 0.0
    for d in days:
        if d < yr_ago: continue
        eqty += port[d]; peak = max(peak, eqty); mdd12 = min(mdd12, eqty - peak)
    print(f"\n=== 合成(直近12M・Σw=1.0倍率1.0): tot={ps['tot']*100:+.2f}% 稼働日={ps['n']} maxDD={mdd12*100:.2f}% ===")

    # 倍率校正(recentfit_screen.py:calibrate 移植): 最悪日≥-day_cap かつ
    # 最悪DD≥-floor_cap(8%) を満たす最大倍率×0.8。
    # オリジナル規則は直近12M系列に対して校正(=直近特化の明示ベット)。
    # 全期間系列での校正値は悲観バウンドとして併記。
    def calibrate(series, day_cap):
        if not series: return 0.0
        wd = min(series.values())
        eqty = peak = mdd = 0.0
        for d in sorted(series):
            eqty += series[d]; peak = max(peak, eqty); mdd = min(mdd, eqty - peak)
        m = 0.05; best = 0.05
        while m <= 6.0:
            if wd * m >= -day_cap and mdd * m >= -0.08:
                best = m
            else:
                break
            m = round(m + 0.05, 2)
        return round(0.8 * best, 2), wd, mdd

    port12 = {d: v for d, v in port.items() if d >= yr_ago}
    for tag, series, day_cap in (
            ("オリジナル規則パリティ(12M窓・EA日次-4%)", port12, 0.04),
            ("RG3並走保守(12M窓・日次予算-3%)", port12, 0.03),
            ("悲観バウンド(全期間窓・-4%)", port, 0.04)):
        mult, wd, mdd = calibrate(series, day_cap)
        print(f"[校正 {tag}] 窓内最悪日={wd*100:.2f}% maxDD={mdd*100:.2f}% → mult={mult} "
              f"(倍率後: 最悪日{wd*mult*100:.2f}%/DD{mdd*mult*100:.2f}%/12M合成{ps['tot']*mult*100:+.1f}%)")
    print("(注: 校正はコスト未計上の近似。正式配備はp8p06zのrecentfit_nonfx_screen.py系で再校正+MC必須)")


if __name__ == "__main__":
    main()
