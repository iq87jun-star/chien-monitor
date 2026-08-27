#!/usr/bin/env python3
"""戦略族の実装.

各族は「確定足で条件成立 → 翌日の寄りで建て → hold 営業日後の寄りで決済」に統一。
時間依存の決済(トレーリング等)を入れないのは、日足データでは経路依存を
正しく評価できないため(本検証で確認済み)。
"""
import statistics as st
from collections import defaultdict
import indicators as I


def _ohlc(rows):
    return ([r[1] for r in rows], [r[2] for r in rows],
            [r[3] for r in rows], [r[4] for r in rows])


def execute(rows, signals, hold, cost):
    """signals: [(bar_index, direction)] → [(date, return_pct)]"""
    op = [r[1] for r in rows]
    out = []
    for i, d in signals:
        if i + 1 + hold >= len(rows): continue
        e, x = op[i + 1], op[i + 1 + hold]
        if e <= 0: continue
        out.append((rows[i][0], ((x / e - 1) * 100) * d - cost))
    return out


# ------------------------------------------------------------ 指標系
def f_rsi(rows, cost, n=14, low=30, high=70, mode="fade", hold=3):
    """mode=fade: 売られすぎで買い / mode=follow: 買われすぎで買い"""
    o, h, l, c = _ohlc(rows)
    r = I.rsi(c, n); sig = []
    for i in range(1, len(c)):
        if r[i] is None or r[i - 1] is None: continue
        if mode == "fade":
            if r[i - 1] >= low and r[i] < low: sig.append((i, 1))
            elif r[i - 1] <= high and r[i] > high: sig.append((i, -1))
        else:
            if r[i - 1] <= high and r[i] > high: sig.append((i, 1))
            elif r[i - 1] >= low and r[i] < low: sig.append((i, -1))
    return execute(rows, sig, hold, cost)


def f_bb(rows, cost, n=20, k=2.0, mode="fade", hold=3):
    """ボリンジャーバンド。fade=バンドタッチで逆張り / break=バンド抜けで順張り"""
    o, h, l, c = _ohlc(rows)
    m = I.sma(c, n); s = I.rolling_sd(c, n); sig = []
    for i in range(len(c)):
        if m[i] is None or s[i] is None or s[i] <= 0: continue
        up, lo = m[i] + k * s[i], m[i] - k * s[i]
        if mode == "fade":
            if c[i] <= lo: sig.append((i, 1))
            elif c[i] >= up: sig.append((i, -1))
        else:
            if c[i] >= up: sig.append((i, 1))
            elif c[i] <= lo: sig.append((i, -1))
    return execute(rows, sig, hold, cost)


def f_macd(rows, cost, fast=12, slow=26, signal=9, hold=5):
    """MACD がシグナルを上抜けで買い / 下抜けで売り"""
    o, h, l, c = _ohlc(rows)
    ml, sl, _ = I.macd(c, fast, slow, signal); sig = []
    for i in range(1, len(c)):
        if None in (ml[i], sl[i], ml[i - 1], sl[i - 1]): continue
        if ml[i - 1] <= sl[i - 1] and ml[i] > sl[i]: sig.append((i, 1))
        elif ml[i - 1] >= sl[i - 1] and ml[i] < sl[i]: sig.append((i, -1))
    return execute(rows, sig, hold, cost)


def f_stoch(rows, cost, n=14, smooth=3, low=20, high=80, hold=3):
    """ストキャス %K が %D を売られすぎ圏で上抜け → 買い"""
    o, h, l, c = _ohlc(rows)
    k, d = I.stochastic(h, l, c, n, smooth); sig = []
    for i in range(1, len(c)):
        if None in (k[i], d[i], k[i - 1], d[i - 1]): continue
        if k[i - 1] <= d[i - 1] and k[i] > d[i] and k[i] < low: sig.append((i, 1))
        elif k[i - 1] >= d[i - 1] and k[i] < d[i] and k[i] > high: sig.append((i, -1))
    return execute(rows, sig, hold, cost)


def f_cci(rows, cost, n=20, thr=100, mode="fade", hold=3):
    o, h, l, c = _ohlc(rows)
    v = I.cci(h, l, c, n); sig = []
    for i in range(1, len(c)):
        if v[i] is None or v[i - 1] is None: continue
        if mode == "fade":
            if v[i - 1] >= -thr and v[i] < -thr: sig.append((i, 1))
            elif v[i - 1] <= thr and v[i] > thr: sig.append((i, -1))
        else:
            if v[i - 1] <= thr and v[i] > thr: sig.append((i, 1))
            elif v[i - 1] >= -thr and v[i] < -thr: sig.append((i, -1))
    return execute(rows, sig, hold, cost)


def f_adx(rows, cost, n=14, thr=25, hold=5):
    """ADX がしきい値超え(トレンド有り)で +DI/-DI の優勢方向に順張り"""
    o, h, l, c = _ohlc(rows)
    a, p, m = I.adx(h, l, c, n); sig = []
    for i in range(1, len(c)):
        if None in (a[i], p[i], m[i]) or a[i] < thr: continue
        if p[i - 1] is None or m[i - 1] is None: continue
        if p[i - 1] <= m[i - 1] and p[i] > m[i]: sig.append((i, 1))
        elif p[i - 1] >= m[i - 1] and p[i] < m[i]: sig.append((i, -1))
    return execute(rows, sig, hold, cost)


def f_ichimoku(rows, cost, tenkan=9, kijun=26, senkou=52, hold=10):
    """終値が雲を上抜け → 買い / 下抜け → 売り"""
    o, h, l, c = _ohlc(rows)
    tk, kj, sa, sb = I.ichimoku(h, l, c, tenkan, kijun, senkou); sig = []
    for i in range(1, len(c)):
        if None in (sa[i], sb[i], sa[i - 1], sb[i - 1]): continue
        top, bot = max(sa[i], sb[i]), min(sa[i], sb[i])
        ptop, pbot = max(sa[i - 1], sb[i - 1]), min(sa[i - 1], sb[i - 1])
        if c[i - 1] <= ptop and c[i] > top: sig.append((i, 1))
        elif c[i - 1] >= pbot and c[i] < bot: sig.append((i, -1))
    return execute(rows, sig, hold, cost)


def f_donchian(rows, cost, n=20, mode="break", hold=5):
    o, h, l, c = _ohlc(rows)
    up, lo = I.donchian(h, l, n); sig = []
    for i in range(len(c)):
        if up[i] is None or lo[i] is None: continue
        if mode == "break":
            if c[i] > up[i]: sig.append((i, 1))
            elif c[i] < lo[i]: sig.append((i, -1))
        else:
            if c[i] > up[i]: sig.append((i, -1))
            elif c[i] < lo[i]: sig.append((i, 1))
    return execute(rows, sig, hold, cost)


def f_macross(rows, cost, fast=20, slow=50, kind="sma", hold=10):
    o, h, l, c = _ohlc(rows)
    fn = I.sma if kind == "sma" else I.ema
    f, s = fn(c, fast), fn(c, slow); sig = []
    for i in range(1, len(c)):
        if None in (f[i], s[i], f[i - 1], s[i - 1]): continue
        if f[i - 1] <= s[i - 1] and f[i] > s[i]: sig.append((i, 1))
        elif f[i - 1] >= s[i - 1] and f[i] < s[i]: sig.append((i, -1))
    return execute(rows, sig, hold, cost)


def f_atrbreak(rows, cost, n=14, k=1.5, mode="follow", hold=3):
    """1日の値動きが ATR の k 倍を超えたら追随(follow)か逆張り(fade)"""
    o, h, l, c = _ohlc(rows)
    a = I.atr(h, l, c, n); sig = []
    for i in range(1, len(c)):
        if a[i] is None or a[i] <= 0: continue
        mv = c[i] - c[i - 1]
        if abs(mv) < k * a[i]: continue
        d = (1 if mv > 0 else -1) * (1 if mode == "follow" else -1)
        sig.append((i, d))
    return execute(rows, sig, hold, cost)


# ------------------------------------------------------------ 構造系
def f_gap(rows, cost, k=0.5, n=14, mode="fade", hold=1):
    """前日終値に対する寄りのギャップが ATR の k 倍超で、埋め(fade)か追随(follow)"""
    o, h, l, c = _ohlc(rows)
    a = I.atr(h, l, c, n); sig = []
    for i in range(1, len(c) - 1):
        if a[i] is None or a[i] <= 0: continue
        gap = o[i + 1] - c[i]
        if abs(gap) < k * a[i]: continue
        d = (1 if gap > 0 else -1) * (1 if mode == "follow" else -1)
        sig.append((i, d))
    return execute(rows, sig, hold, cost)


def f_rangebreak(rows, cost, mode="break", hold=2):
    """終値が前日の高値上抜け/安値下抜け"""
    o, h, l, c = _ohlc(rows)
    sig = []
    for i in range(1, len(c)):
        s = 1 if mode == "break" else -1
        if c[i] > h[i - 1]: sig.append((i, s))
        elif c[i] < l[i - 1]: sig.append((i, -s))
    return execute(rows, sig, hold, cost)


def f_dom(rows, cost, day=1, direction=1, hold=1):
    """月内の第 day 営業日の寄りで建てる"""
    idx = defaultdict(list)
    for i, r in enumerate(rows): idx[r[0][:7]].append(i)
    sig = []
    for k in sorted(idx):
        v = idx[k]
        if len(v) >= day: sig.append((v[day - 1] - 1, direction))
    return execute(rows, [(i, d) for i, d in sig if i >= 0], hold, cost)


def f_streak(rows, cost, run=4, mode="fade", hold=2):
    """run 日連続の陽線/陰線のあと、逆張り(fade)か追随(follow)"""
    o, h, l, c = _ohlc(rows)
    sig = []
    for i in range(run, len(c)):
        up = all(c[i - j] > c[i - j - 1] for j in range(run))
        dn = all(c[i - j] < c[i - j - 1] for j in range(run))
        if not (up or dn): continue
        base = 1 if up else -1
        sig.append((i, base * (1 if mode == "follow" else -1)))
    return execute(rows, sig, hold, cost)


def f_inout(rows, cost, kind="inside", direction=1, hold=2):
    """インサイドバー(はらみ)/ アウトサイドバー(包み)の翌日"""
    o, h, l, c = _ohlc(rows)
    sig = []
    for i in range(1, len(c)):
        ins = h[i] <= h[i - 1] and l[i] >= l[i - 1]
        out = h[i] > h[i - 1] and l[i] < l[i - 1]
        hit = ins if kind == "inside" else out
        if hit: sig.append((i, direction))
    return execute(rows, sig, hold, cost)


def f_volregime(rows, cost, n=20, ref=100, high_vol=True, direction=1, hold=5):
    """ボラティリティが長期平均より高い(低い)局面でのみ direction 方向に建てる"""
    o, h, l, c = _ohlc(rows)
    rets = [0.0] + [c[i] / c[i - 1] - 1 for i in range(1, len(c))]
    short = I.rolling_sd(rets, n); long_ = I.rolling_sd(rets, ref)
    sig = []
    for i in range(len(c)):
        if short[i] is None or long_[i] is None or long_[i] <= 0: continue
        hv = short[i] > long_[i]
        if hv == high_vol: sig.append((i, direction))
    return execute(rows, sig, hold, cost)


# ------------------------------------------------------------ 複数銘柄系
def f_xsect(data, cost_of, look=20, hold=5, n_side=2):
    """断面ランク: 直近 look 日の騰落で上位 n_side を買い、下位 n_side を売る。
    data: {name: rows}"""
    by_date = defaultdict(dict)
    for nm, rows in data.items():
        c = [r[4] for r in rows]; o = [r[1] for r in rows]
        for i in range(look, len(rows) - hold - 1):
            by_date[rows[i][0]][nm] = (c[i] / c[i - look] - 1, o[i + 1], o[i + 1 + hold])
    out = []
    for d in sorted(by_date):
        row = by_date[d]
        if len(row) < 2 * n_side + 1: continue
        rank = sorted(row.items(), key=lambda kv: -kv[1][0])
        for nm, (_, e, x) in rank[:n_side]:
            out.append((d, (x / e - 1) * 100 - cost_of(nm, hold)))
        for nm, (_, e, x) in rank[-n_side:]:
            out.append((d, -(x / e - 1) * 100 - cost_of(nm, hold)))
    return out


def f_pairs(rows_a, rows_b, cost_a, cost_b, win=30, thr=2.0, hold=5):
    """2銘柄の対数価格比の z-score が閾値を超えたら平均回帰を狙う。
    a を買い b を売る(またはその逆)の合成リターン。
    cost_a / cost_b は各脚の往復コスト(保有日数分のキャリーを含む)。"""
    import math
    da = {r[0]: r for r in rows_a}; db = {r[0]: r for r in rows_b}
    # 2020年4月のWTIのように限月価格がマイナスになる銘柄があるため、
    # 対数比が定義できない日は除外する(log(負) で落ちる)。
    dates = sorted(d for d in (set(da) & set(db))
                   if da[d][4] > 0 and db[d][4] > 0 and da[d][1] > 0 and db[d][1] > 0)
    if len(dates) < win + hold + 2: return []
    spread = [math.log(da[d][4]) - math.log(db[d][4]) for d in dates]
    out = []
    for i in range(win, len(dates) - hold - 1):
        w = spread[i - win:i]
        m = st.mean(w); s = st.pstdev(w)
        if s <= 0: continue
        z = (spread[i] - m) / s
        if abs(z) < thr: continue
        d = -1 if z > 0 else 1          # 広がったら縮小に賭ける
        ea, xa = da[dates[i + 1]][1], da[dates[i + 1 + hold]][1]
        eb, xb = db[dates[i + 1]][1], db[dates[i + 1 + hold]][1]
        r = ((xa / ea - 1) - (xb / eb - 1)) * 100 * d - (cost_a + cost_b)
        out.append((dates[i], r))
    return out


SINGLE = {
    "rsi": f_rsi, "bb": f_bb, "macd": f_macd, "stoch": f_stoch, "cci": f_cci,
    "adx": f_adx, "ichimoku": f_ichimoku, "donchian": f_donchian,
    "macross": f_macross, "atrbreak": f_atrbreak,
    "gap": f_gap, "rangebreak": f_rangebreak, "dom": f_dom,
    "streak": f_streak, "inout": f_inout, "volregime": f_volregime,
}


# ------------------------------------------------------------ 銘柄間・外部条件系
def f_lead(rows_src, rows_tgt, cost, thr=0.0, mode="follow", hold=1, ref_win=100):
    """銘柄間リードラグ: src の当日終値変化を条件に、tgt を翌日の寄りで建てる。

    thr は src 日次リターンの直近 ref_win 日標準偏差に対する倍率。
    src の確定終値が tgt の建玉時刻(翌営業日の寄り)より前に来る組み合わせでのみ
    使うこと(例: 米指数の引け → 翌日のアジア指数/FXの寄り)。
    """
    cs = [r[4] for r in rows_src]
    rets = [None] + [cs[i] / cs[i - 1] - 1 for i in range(1, len(cs))]
    sd = I.rolling_sd([0.0 if x is None else x for x in rets], ref_win)
    src_by_date = {}
    for i, r in enumerate(rows_src):
        if rets[i] is None or sd[i] is None or sd[i] <= 0: continue
        src_by_date[r[0]] = rets[i] / sd[i]
    sig = []
    for i, r in enumerate(rows_tgt):
        z = src_by_date.get(r[0])
        if z is None or abs(z) < thr: continue
        d = (1 if z > 0 else -1) * (1 if mode == "follow" else -1)
        sig.append((i, d))
    return execute(rows_tgt, sig, hold, cost)


def f_nr(rows, cost, n=7, look=10, mode="follow", hold=3):
    """ボラ収縮(直近 n 日で最小レンジの足)の翌日に、直近 look 日の
    方向へ追随(follow)/逆行(fade)する。"""
    o, h, l, c = _ohlc(rows)
    rng = [h[i] - l[i] for i in range(len(rows))]
    sig = []
    for i in range(max(n, look), len(rows)):
        if rng[i] <= 0: continue
        if rng[i] > min(rng[i - n + 1:i + 1]): continue
        chg = c[i] - c[i - look]
        if chg == 0: continue
        d = (1 if chg > 0 else -1) * (1 if mode == "follow" else -1)
        sig.append((i, d))
    return execute(rows, sig, hold, cost)


def f_xfilter(rows_tgt, rows_ref, cost, n=50, above=True, direction=1, hold=5):
    """外部指標の局面フィルタ: ref の終値が自身の n 日平均より上(下)の日だけ、
    tgt を direction 方向に建てる。volregime と違い、条件は別銘柄から取る。"""
    cr = [r[4] for r in rows_ref]
    m = I.sma(cr, n)
    cond_by_date = {}
    for i, r in enumerate(rows_ref):
        if m[i] is None: continue
        cond_by_date[r[0]] = cr[i] > m[i]
    sig = []
    for i, r in enumerate(rows_tgt):
        cond = cond_by_date.get(r[0])
        if cond is None or cond != above: continue
        sig.append((i, direction))
    return execute(rows_tgt, sig, hold, cost)


SINGLE["nr"] = f_nr
