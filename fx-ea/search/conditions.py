#!/usr/bin/env python3
"""バー単位の条件(述語)。合流(conjunction)を組むための部品。

各条件は「バー i の時点で成立しているか」を返す。i より後のデータは使わない。
定石弐のように「複数の条件がすべて揃った場面だけ」を検定するために用意した。
単一の仕組みでは 49 仮説すべてが棄却されており、合流は未検定の領域。
"""
import statistics as st
import indicators as I

OPS = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b,
       ">": lambda a, b: a > b, ">=": lambda a, b: a >= b}


def _ohlc(rows):
    return ([r[1] for r in rows], [r[2] for r in rows],
            [r[3] for r in rows], [r[4] for r in rows])


def c_rsi(rows, n=14, op="<", thr=35.0):
    c = _ohlc(rows)[3]
    v = I.rsi(c, n)
    f = OPS[op]
    return [None if v[i] is None else f(v[i], thr) for i in range(len(rows))]


def c_z(rows, win=20, op="<", thr=-1.5):
    """終値が直前 win 本(判定バー自身は含めない)の平均から何標本SD離れているか。"""
    c = _ohlc(rows)[3]
    f = OPS[op]
    out = [None] * len(rows)
    for i in range(win + 1, len(rows)):
        w = c[i - win:i]
        sd = st.stdev(w)
        if sd <= 0: continue
        out[i] = f((c[i] - st.mean(w)) / sd, thr)
    return out


def c_streak(rows, run=3, dirn=-1):
    """終値が run 本以上続けて前日を下回った(dirn=-1)/上回った(dirn=1)。

    引数名が run なのは、条件の種別キー "k" と衝突させないため。
    """
    c = _ohlc(rows)[3]
    out = [None] * len(rows)
    for i in range(run, len(rows)):
        out[i] = all((c[i - j] < c[i - j - 1]) if dirn < 0 else (c[i - j] > c[i - j - 1])
                     for j in range(run))
    return out


def c_ret(rows, op="<", pct=-0.5):
    """前日終値比の当日変動(%)。"""
    c = _ohlc(rows)[3]
    f = OPS[op]
    out = [None] * len(rows)
    for i in range(1, len(rows)):
        if c[i - 1] <= 0: continue
        out[i] = f((c[i] / c[i - 1] - 1) * 100, pct)
    return out


def c_vol(rows, n=20, ref=100, op=">"):
    """直近 n 本の実現ボラが、長期 ref 本のボラより大きい/小さい。"""
    c = _ohlc(rows)[3]
    rets = [0.0] + [c[i] / c[i - 1] - 1 for i in range(1, len(c))]
    s, l = I.rolling_sd(rets, n), I.rolling_sd(rets, ref)
    f = OPS[op]
    return [None if (s[i] is None or l[i] is None or l[i] <= 0) else f(s[i], l[i])
            for i in range(len(rows))]


def c_range(rows, n=20, mult=1.5, op=">"):
    """当日の高安幅が、直近 n 本の平均高安幅の mult 倍より大きい/小さい。"""
    o, h, l, c = _ohlc(rows)
    rng = [h[i] - l[i] for i in range(len(rows))]
    f = OPS[op]
    out = [None] * len(rows)
    for i in range(n, len(rows)):
        m = sum(rng[i - n:i]) / n
        if m <= 0: continue
        out[i] = f(rng[i], mult * m)
    return out


KINDS = {"rsi": c_rsi, "z": c_z, "streak": c_streak, "ret": c_ret,
         "vol": c_vol, "range": c_range}


_MEMO = {}


def build(rows, specs):
    """specs: [{"k": "rsi", ...パラメータ}] → 各バーの成立本数と全成立フラグ。

    戻り値: (met[i] = [各条件の成否], allmet[i] = 全条件成立か)
    """
    cols = []
    for sp in specs:
        # 同じ銘柄・同じ条件は使い回す(合流の検定は同じ列を何度も引くため)
        key = (id(rows), len(rows), repr(sorted(sp.items())))
        if key not in _MEMO:
            p = dict(sp); kind = p.pop("k")
            if kind not in KINDS:
                raise KeyError(f"未知の条件 {kind!r}。使えるのは {sorted(KINDS)}")
            _MEMO[key] = KINDS[kind](rows, **p)
        cols.append(_MEMO[key])
    met, allmet = [], []
    for i in range(len(rows)):
        row = [col[i] for col in cols]
        met.append(row)
        allmet.append(all(x is True for x in row))
    return met, allmet
