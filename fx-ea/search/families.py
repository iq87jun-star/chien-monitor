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


# ------------------------------------------------------------ 出来高・断面系
def f_volspike(rows, cost, n=20, k=2.0, mode="follow", hold=3):
    """出来高が直近 n 日中央値の k 倍を超えた日の値動き方向に追随/逆行する。

    出来高は Yahoo では指数・商品でしか取れない(FXは常に0)。
    0 の日はデータ欠損として除外する。
    """
    o, h, l, c = _ohlc(rows)
    v = [r[5] if len(r) > 5 else 0 for r in rows]
    sig = []
    for i in range(n, len(rows)):
        w = [x for x in v[i - n:i] if x > 0]
        if v[i] <= 0 or len(w) < n // 2: continue
        med = st.median(w)
        if med <= 0 or v[i] < k * med: continue
        mv = c[i] - c[i - 1]
        if mv == 0: continue
        d = (1 if mv > 0 else -1) * (1 if mode == "follow" else -1)
        sig.append((i, d))
    return execute(rows, sig, hold, cost)


def f_breadth(rows_tgt, basket, cost, n=50, thr=0.5, above=True, direction=1, hold=5):
    """バスケットのうち n 日平均を上回っている銘柄の比率(市場の幅)で局面を判定し、
    その局面の日だけ tgt を direction 方向に建てる。

    basket: {name: rows}。個別銘柄の値ではなく「何割が上向きか」を条件にする点が
    volregime(自分自身のボラ)や xfilter(単一の外部指標)と異なる。
    """
    up_by_date = defaultdict(lambda: [0, 0])
    for nm, rows in basket.items():
        c = [r[4] for r in rows]
        m = I.sma(c, n)
        for i, r in enumerate(rows):
            if m[i] is None: continue
            cell = up_by_date[r[0]]
            cell[1] += 1
            if c[i] > m[i]: cell[0] += 1
    sig = []
    for i, r in enumerate(rows_tgt):
        cell = up_by_date.get(r[0])
        if not cell or cell[1] < max(2, len(basket) - 1): continue
        frac = cell[0] / cell[1]
        if (frac > thr) != above: continue
        sig.append((i, direction))
    return execute(rows_tgt, sig, hold, cost)


def f_ccystr(data, cost_of, look=20, hold=5):
    """通貨強弱の断面。各ペアの look 日騰落を「基軸通貨 +・決済通貨 −」に分解して
    通貨ごとの強さを出し、最強通貨を買い最弱通貨を売る組み合わせのペアを1本建てる。

    xsect が「ペアそのもの」を順位付けるのに対し、これは通貨単位で順位付ける。
    data: {PAIRNAME(6文字): rows}
    """
    idx = {nm: {r[0]: i for i, r in enumerate(rows)} for nm, rows in data.items()}
    chg_by_date = defaultdict(dict)
    for nm, rows in data.items():
        c = [r[4] for r in rows]
        for i in range(look, len(rows) - hold - 1):
            chg_by_date[rows[i][0]][nm] = c[i] / c[i - look] - 1
    pairs = set(data)
    out = []
    for d in sorted(chg_by_date):
        row = chg_by_date[d]
        if len(row) < len(data): continue
        acc = defaultdict(list)
        for nm, ch in row.items():
            acc[nm[:3]].append(ch)
            acc[nm[3:]].append(-ch)
        stren = {k: st.mean(v) for k, v in acc.items() if v}
        if len(stren) < 3: continue
        rank = sorted(stren.items(), key=lambda kv: -kv[1])
        best, worst = rank[0][0], rank[-1][0]
        nm, dr = (best + worst, 1) if best + worst in pairs else \
                 (worst + best, -1) if worst + best in pairs else (None, 0)
        if nm is None: continue
        rows = data[nm]; i = idx[nm][d]
        if i + 1 + hold >= len(rows): continue
        e, x = rows[i + 1][1], rows[i + 1 + hold][1]
        if e <= 0: continue
        out.append((d, ((x / e - 1) * 100) * dr - cost_of(nm, hold)))
    return out


SINGLE["volspike"] = f_volspike


# ------------------------------------------------------------ 指標トラック
# 売買の族が「翌日の方向」を当てにいくのに対し、こちらは
# 「翌日の変動幅」「いまの局面」を素朴な基準よりうまく言い当てられるかを測る。
# 返す形が違う: [(日付, 改善, 素朴基準の大きさ)]。
#   改善 = 素朴基準の誤差 − 予測の誤差  (プラス = 素朴基準より当たっている)

def i_rangefc(rows, n=14, kind="atr"):
    """翌日の値幅(終値比%)を予測できるか。

    素朴基準 = その銘柄のそれまでの全履歴の平均値幅(拡大平均)。
    予測      = ATR(n) / EWMA(n) / SMA(n) / 直前の値幅。
    予測対象は高安幅なので、予測子も高安幅で組む(kind="sma")のが定義として整合する。
    「想定変動幅の表示に中身があるか」を測る検定。
    """
    o, h, l, c = _ohlc(rows)
    rng = [(h[i] - l[i]) / c[i] * 100 if c[i] > 0 else None for i in range(len(rows))]
    a = I.atr(h, l, c, n)
    ew, prev = [None] * len(rows), None
    k = 2.0 / (n + 1)
    for i, x in enumerate(rng):
        if x is None: continue
        prev = x if prev is None else prev + k * (x - prev)
        ew[i] = prev
    out, run, cnt = [], 0.0, 0
    for i in range(len(rows) - 1):
        if rng[i] is None: continue
        run += rng[i]; cnt += 1              # ここまでの履歴のみ(先読みなし)
        if cnt < 60 or rng[i + 1] is None: continue
        base_pred = run / cnt
        if kind == "atr":
            # 注意: ATRは「真の値幅」でギャップを含む。予測対象の高安幅より
            # 系統的に大きく出るため、ギャップの大きい銘柄ほど当たらなくなる。
            pred = None if a[i] is None or c[i] <= 0 else a[i] / c[i] * 100
        elif kind == "ewma":
            pred = ew[i]
        elif kind == "sma":
            w = [x for x in rng[i - n + 1:i + 1] if x is not None]
            pred = sum(w) / len(w) if len(w) == n else None
        else:
            pred = rng[i]
        if pred is None: continue
        act = rng[i + 1]
        be, me = abs(act - base_pred), abs(act - pred)
        out.append((rows[i + 1][0], be - me, be))
    return out


def i_volpersist(rows, n=20, q=0.8):
    """「いま荒れている」の表示に中身があるか。

    直近 n 日の実現ボラがそれまでの履歴の上位 q 分位を超えた日について、
    翌日の値動きの大きさ |リターン| が無条件の平均をどれだけ上回るかを測る。
    素朴基準 = それまでの全履歴の平均 |リターン|(拡大平均)。
    """
    o, h, l, c = _ohlc(rows)
    ret = [None] + [c[i] / c[i - 1] - 1 for i in range(1, len(c))]
    sd = I.rolling_sd([0.0 if x is None else x for x in ret], n)
    hist, run, cnt, out = [], 0.0, 0, []
    for i in range(len(rows) - 1):
        if ret[i] is None: continue
        run += abs(ret[i]) * 100; cnt += 1
        if sd[i] is not None: hist.append(sd[i])
        if cnt < 250 or len(hist) < 250 or ret[i + 1] is None: continue
        past = sorted(hist[:-1])
        thr = past[min(len(past) - 1, int(len(past) * q))]
        if sd[i] is None or sd[i] < thr: continue
        base = run / cnt
        out.append((rows[i + 1][0], abs(ret[i + 1]) * 100 - base, base))
    return out


def i_dowrange(rows, dow=0):
    """「この曜日は動きやすい」の表示に中身があるか。

    その曜日の値幅が、それまでの全履歴の平均値幅をどれだけ上回るかを測る。
    """
    import datetime as _dt
    o, h, l, c = _ohlc(rows)
    run, cnt, out = 0.0, 0, []
    for i in range(len(rows)):
        if c[i] <= 0: continue
        r = (h[i] - l[i]) / c[i] * 100
        if cnt >= 250 and _dt.date.fromisoformat(rows[i][0]).weekday() == dow:
            base = run / cnt
            out.append((rows[i][0], r - base, base))
        run += r; cnt += 1                   # 当日を足すのは判定の後(先読みなし)
    return out


FORECAST = {"rangefc": i_rangefc, "volpersist": i_volpersist, "dowrange": i_dowrange}


def f_xspread(rows_tgt, rows_a, rows_b, cost, n=200, mode="ratio",
              above=True, direction=1, hold=5):
    """2つの参照系列の関係で局面を判定する。

    mode="ratio" なら a/b、"diff" なら a-b の系列を作り、
    それが自身の n 日平均より上(下)の日だけ tgt を direction 方向に建てる。
    金利カーブの傾き(10年 − 3ヶ月)や 銅/金 比のような、
    水準ではなく**系列間の関係**が意味を持つ指標のための族。
    """
    da = {r[0]: r[4] for r in rows_a}
    db = {r[0]: r[4] for r in rows_b}
    dates = sorted(set(da) & set(db))
    if len(dates) < n + 2: return []
    ser = []
    for d in dates:
        if mode == "ratio":
            if db[d] == 0: ser.append(None); continue
            ser.append(da[d] / db[d])
        else:
            ser.append(da[d] - db[d])
    m = I.sma([0.0 if x is None else x for x in ser], n)
    cond = {}
    for i, d in enumerate(dates):
        if ser[i] is None or m[i] is None: continue
        cond[d] = ser[i] > m[i]
    sig = []
    for i, r in enumerate(rows_tgt):
        c = cond.get(r[0])
        if c is None or c != above: continue
        sig.append((i, direction))
    return execute(rows_tgt, sig, hold, cost)


def i_effratio(rows, n=20):
    """「いまトレンドが出ているか」の表示に中身があるか。

    効率比 = |n本の正味の値動き| / |1本ごとの値動きの合計|。
    1 に近いほど一方向、0 に近いほど行ったり来たり。
    直近 n 本の効率比が、**次の n 本の効率比**を、その銘柄の平年並みの
    効率比より正確に言い当てられるかを測る。
    素朴基準 = それまでの全履歴の平均効率比(拡大平均)。
    """
    c = [r[4] for r in rows]
    absd = [0.0] + [abs(c[i] - c[i - 1]) for i in range(1, len(c))]
    pre = [0.0]
    for x in absd: pre.append(pre[-1] + x)

    def er(i, j):
        """バー i+1 〜 j の効率比。"""
        path = pre[j + 1] - pre[i + 1]
        return abs(c[j] - c[i]) / path if path > 0 else None

    # 素朴基準に入れてよいのは、目的変数の窓(i+1〜i+n)と重ならない実現値だけ。
    # i-1 時点の実現値の窓は i〜i+n-1 をカバーしていて重なるため、
    # n 本ぶん遅らせて積む。遅らせないと素朴基準だけが未来を覗くことになる。
    run, cnt, out, pend = 0.0, 0, [], []
    for i in range(n, len(rows) - n):
        cur = er(i - n, i)
        nxt = er(i, i + n)
        if cur is None or nxt is None: continue
        pend.append(nxt)
        if len(pend) > n:
            run += pend.pop(0); cnt += 1
        if cnt >= 250:
            base = run / cnt
            out.append((rows[i + n][0],
                        abs(nxt - base) - abs(nxt - cur), abs(nxt - base)))
    return out


def i_gapsize(rows, n=14, kind="sma"):
    """「明日の寄りはどれくらい飛ぶか」の表示に中身があるか。

    窓の大きさ = |始値 − 前日終値| / 前日終値 × 100。
    直近 n 本の平均窓幅が、翌日の窓幅を、その銘柄の平年並みより
    正確に言い当てられるかを測る。FXでは窓がほぼ出ないので指数・商品向け。
    """
    o = [r[1] for r in rows]; c = [r[4] for r in rows]
    gap = [None] + [abs(o[i] - c[i - 1]) / c[i - 1] * 100 if c[i - 1] > 0 else None
                    for i in range(1, len(rows))]
    run, cnt, out = 0.0, 0, []
    for i in range(len(rows) - 1):
        if gap[i] is None: continue
        run += gap[i]; cnt += 1
        if cnt < 250 or gap[i + 1] is None: continue
        w = [x for x in gap[max(1, i - n + 1):i + 1] if x is not None]
        if len(w) < n: continue
        pred = sum(w) / len(w) if kind == "sma" else gap[i]
        act, base = gap[i + 1], run / cnt
        out.append((rows[i + 1][0],
                    abs(act - base) - abs(act - pred), abs(act - base)))
    return out


FORECAST["effratio"] = i_effratio
FORECAST["gapsize"]  = i_gapsize


def f_combo(rows, cost, conds=None, direction=1, hold=3, need=None):
    """複数の条件が同じバーで**すべて**揃った翌日に建てる(合流)。

    need を指定すると「n個中k個」でも建てる。条件を緩めたときに
    優位性が消えるかどうかを測るための対照用。
    """
    import conditions as C
    met, allmet = C.build(rows, conds or [])
    k = len(conds or [])
    sig = []
    for i in range(len(rows)):
        n_ok = sum(1 for x in met[i] if x is True)
        hit = allmet[i] if need is None else (n_ok >= need)
        if hit: sig.append((i, direction))
    return execute(rows, sig, hold, cost)


SINGLE["combo"] = f_combo


def i_interval(rows, n=60, lo=0.1, hi=0.9):
    """値幅の「範囲」の示し方に中身があるか。

    点の予測(i_rangefc)ではなく、区間の予測を測る。
    直近 n 本の高安幅の分位で作った区間と、全履歴の分位で作った区間を、
    interval score(= 区間の幅 + 外したときの罰則)で比べる。
    狭くて、かつ外さない区間ほど良い。値幅計に「8割はこの範囲」と
    書けるかどうかの根拠になる。
    """
    o, h, l, c = _ohlc(rows)
    rng = [(h[i] - l[i]) / c[i] * 100 if c[i] > 0 else None for i in range(len(rows))]
    alpha = (1.0 - (hi - lo))
    hist, out = [], []

    def q(xs, p):
        s = sorted(xs)
        return s[min(len(s) - 1, int(len(s) * p))]

    def score(a, b, y):
        s = b - a
        if y < a: s += 2.0 / alpha * (a - y)
        elif y > b: s += 2.0 / alpha * (y - b)
        return s

    for i in range(len(rows) - 1):
        if rng[i] is None: continue
        hist.append(rng[i])
        if len(hist) < 250 or len(hist) < n or rng[i + 1] is None: continue
        act = rng[i + 1]
        w = hist[-n:]
        sm = score(q(w, lo), q(w, hi), act)          # 直近 n 本の分位
        sb = score(q(hist, lo), q(hist, hi), act)    # 全履歴の分位
        out.append((rows[i + 1][0], sb - sm, sb))
    return out


FORECAST["interval"] = i_interval


def i_quiethit(rows, n=14, base_bars=3000, thr=0.85, side="quiet"):
    """値幅計の「静か」「荒い」表示が当たっているか。

    静穏度 = 直近 n 本の平均値幅 ÷ 直近 base_bars 本の平均値幅。
      side="quiet": 静穏度 < thr のとき「静か」→ 翌バーが平年並みを下回るか
      side="busy" : 静穏度 > thr のとき「荒い」→ 翌バーが平年並みを上回るか
    素朴基準 = それまでの全履歴での無条件の割合(拡大平均)。

    出荷している表示そのものを測るので、既定値は MQL の input と揃えてある。
    """
    o, h, l, c = _ohlc(rows)
    rng = [(h[i] - l[i]) / c[i] * 100 if c[i] > 0 else None for i in range(len(rows))]
    pre, hist = [0.0], []
    for x in rng: pre.append(pre[-1] + (x if x is not None else 0.0))
    below = tot = 0
    out = []
    for i in range(len(rows) - 1):
        if rng[i] is None: continue
        hist.append(rng[i])
        b = min(base_bars, len(hist))
        if b < 250 or len(hist) <= n or rng[i + 1] is None: continue
        base = sum(hist[-b:]) / b
        fc = sum(hist[-n:]) / n
        if base <= 0: continue
        hit = (1.0 if rng[i + 1] < base else 0.0) if side == "quiet" \
              else (1.0 if rng[i + 1] > base else 0.0)
        fires = (fc / base < thr) if side == "quiet" else (fc / base > thr)
        if tot >= 250 and fires:
            p0 = below / tot                      # ここまでの無条件の割合
            out.append((rows[i + 1][0], hit - p0, p0))
        below += hit; tot += 1                    # 実現値を足すのは判定の後
    return out


FORECAST["quiethit"] = i_quiethit
