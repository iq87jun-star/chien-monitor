#!/usr/bin/env python3
"""テクニカル指標の実装(すべて確定足のみを参照、先読みなし)."""
import math, statistics as st


def sma(xs, n):
    out = [None] * len(xs); s = 0.0
    for i, v in enumerate(xs):
        s += v
        if i >= n: s -= xs[i - n]
        if i >= n - 1: out[i] = s / n
    return out


def ema(xs, n):
    out = [None] * len(xs)
    if len(xs) < n: return out
    k = 2.0 / (n + 1)
    out[n - 1] = sum(xs[:n]) / n
    for i in range(n, len(xs)):
        out[i] = xs[i] * k + out[i - 1] * (1 - k)
    return out


def rolling_sd(xs, n):
    out = [None] * len(xs)
    for i in range(n - 1, len(xs)):
        out[i] = st.pstdev(xs[i - n + 1:i + 1])
    return out


def rsi(cl, n=14):
    """Wilder RSI."""
    out = [None] * len(cl)
    if len(cl) < n + 1: return out
    g = l = 0.0
    for i in range(1, n + 1):
        ch = cl[i] - cl[i - 1]; g += max(ch, 0.0); l += max(-ch, 0.0)
    au, ad = g / n, l / n
    out[n] = 100.0 if ad == 0 else 100 - 100 / (1 + au / ad)
    for i in range(n + 1, len(cl)):
        ch = cl[i] - cl[i - 1]
        au = (au * (n - 1) + max(ch, 0.0)) / n
        ad = (ad * (n - 1) + max(-ch, 0.0)) / n
        out[i] = 100.0 if ad == 0 else 100 - 100 / (1 + au / ad)
    return out


def true_range(h, l, c):
    tr = [h[0] - l[0]]
    for i in range(1, len(c)):
        tr.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
    return tr


def atr(h, l, c, n=14):
    """Wilder ATR."""
    tr = true_range(h, l, c)
    out = [None] * len(c)
    if len(c) < n: return out
    out[n - 1] = sum(tr[:n]) / n
    for i in range(n, len(c)):
        out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out


def macd(cl, fast=12, slow=26, sig=9):
    """returns (macd_line, signal_line, histogram)."""
    ef, es = ema(cl, fast), ema(cl, slow)
    line = [None if (ef[i] is None or es[i] is None) else ef[i] - es[i]
            for i in range(len(cl))]
    vals = [v for v in line if v is not None]
    start = len(line) - len(vals)
    sg_vals = ema(vals, sig)
    sg = [None] * start + sg_vals
    hist = [None if (line[i] is None or sg[i] is None) else line[i] - sg[i]
            for i in range(len(cl))]
    return line, sg, hist


def stochastic(h, l, c, n=14, smooth=3):
    """returns (%K smoothed, %D)."""
    raw = [None] * len(c)
    for i in range(n - 1, len(c)):
        hh = max(h[i - n + 1:i + 1]); ll = min(l[i - n + 1:i + 1])
        raw[i] = 50.0 if hh == ll else 100 * (c[i] - ll) / (hh - ll)
    vals = [v for v in raw if v is not None]
    start = len(raw) - len(vals)
    k = [None] * start + sma(vals, smooth)
    kv = [v for v in k if v is not None]
    d = [None] * (len(k) - len(kv)) + sma(kv, smooth)
    return k, d


def cci(h, l, c, n=20):
    tp = [(h[i] + l[i] + c[i]) / 3.0 for i in range(len(c))]
    m = sma(tp, n)
    out = [None] * len(c)
    for i in range(n - 1, len(c)):
        w = tp[i - n + 1:i + 1]
        md = sum(abs(x - m[i]) for x in w) / n
        out[i] = 0.0 if md == 0 else (tp[i] - m[i]) / (0.015 * md)
    return out


def adx(h, l, c, n=14):
    """returns (adx, plus_di, minus_di) — Wilder."""
    size = len(c)
    pdm = [0.0] * size; ndm = [0.0] * size
    for i in range(1, size):
        up, dn = h[i] - h[i - 1], l[i - 1] - l[i]
        pdm[i] = up if (up > dn and up > 0) else 0.0
        ndm[i] = dn if (dn > up and dn > 0) else 0.0
    tr = true_range(h, l, c)
    out = [None] * size; pdi = [None] * size; ndi = [None] * size
    if size < 2 * n: return out, pdi, ndi
    atr_s = sum(tr[1:n + 1]); p_s = sum(pdm[1:n + 1]); n_s = sum(ndm[1:n + 1])
    dxs = []
    for i in range(n + 1, size):
        atr_s = atr_s - atr_s / n + tr[i]
        p_s = p_s - p_s / n + pdm[i]
        n_s = n_s - n_s / n + ndm[i]
        if atr_s <= 0: continue
        p = 100 * p_s / atr_s; m = 100 * n_s / atr_s
        pdi[i], ndi[i] = p, m
        dx = 0.0 if (p + m) == 0 else 100 * abs(p - m) / (p + m)
        dxs.append((i, dx))
        if len(dxs) == n:
            out[i] = sum(d for _, d in dxs) / n
        elif len(dxs) > n:
            out[i] = (out[i - 1] * (n - 1) + dx) / n
    return out, pdi, ndi


def donchian(h, l, n=20):
    """returns (upper, lower) excluding the current bar."""
    up = [None] * len(h); lo = [None] * len(h)
    for i in range(n, len(h)):
        up[i] = max(h[i - n:i]); lo[i] = min(l[i - n:i])
    return up, lo


def ichimoku(h, l, c, tenkan=9, kijun=26, senkou=52):
    """一目均衡表。returns (tenkan, kijun, spanA, spanB) — 雲は kijun 分先行させず
    「現在バーに対応する雲」として返す(先読みを避けるため kijun 本前の値を使用)."""
    size = len(c)
    def mid(period, i):
        if i < period - 1: return None
        return (max(h[i - period + 1:i + 1]) + min(l[i - period + 1:i + 1])) / 2.0
    tk = [mid(tenkan, i) for i in range(size)]
    kj = [mid(kijun, i) for i in range(size)]
    sa = [None] * size; sb = [None] * size
    for i in range(size):
        j = i - kijun          # kijun 本前に計算された値が現在の雲
        if j < 0: continue
        if tk[j] is not None and kj[j] is not None: sa[i] = (tk[j] + kj[j]) / 2.0
        sb[i] = mid(senkou, j)
    return tk, kj, sa, sb
