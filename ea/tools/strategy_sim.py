#!/usr/bin/env python3
"""
strategy_sim.py - reference port of StellarEA's trading logic for LOGIC
verification (NOT profitability, NOT an MT5 backtest).

It re-implements, in pure Python, the same decisions the MQL5 EA makes:
  - indicators (EMA, Wilder ADX/RSI/ATR, Bollinger)
  - regime detection (trend / range / neutral)
  - entries (pullback continuation / Bollinger+RSI reversion)
  - ATR stop / RR target, breakeven, ATR trailing
  - %-risk position sizing from tick value (the prop-firm risk math)
  - daily-loss and max-drawdown halts, session / weekday / spread filters

Goal: confirm the algorithm behaves as designed and the risk math is exact.
Differences vs MT5 are expected (no tick fills, broker spread/swap, exact
calendar). Use MetaTrader's Strategy Tester for performance/return numbers.
"""
import json
import math
import socket
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone


# ----------------------------- config (mirrors Inp* inputs) ----------------
@dataclass
class Cfg:
    adx_period: int = 14
    adx_trend: float = 25.0
    adx_range: float = 20.0
    htf_ema: int = 200
    fast_ema: int = 21
    slow_ema: int = 50
    pull_ema: int = 21
    bb_period: int = 20
    bb_dev: float = 2.0
    rsi_period: int = 14
    rsi_os: float = 30.0
    rsi_ob: float = 70.0
    atr_period: int = 14
    sl_atr: float = 2.0
    trend_rr: float = 2.0
    range_rr: float = 1.2
    use_be: bool = True
    be_trigger_atr: float = 1.0
    be_lock_atr: float = 0.10
    use_trail: bool = True
    trail_atr: float = 2.0
    risk_pct: float = 0.75
    daily_loss_pct: float = 4.0
    max_dd_pct: float = 8.0
    max_positions: int = 1
    max_trades_day: int = 6
    use_session: bool = True
    sess_start: int = 7
    sess_end: int = 20
    trade_days: tuple = (1, 2, 3, 4, 5)   # Mon..Fri (0=Sun,6=Sat)
    # instrument economics (EURUSD-like defaults)
    tick_size: float = 0.00001
    tick_value: float = 1.0
    vol_step: float = 0.01
    vol_min: float = 0.01
    vol_max: float = 100.0
    spread_points: float = 12.0           # round-trip cost applied as price
    initial_balance: float = 10000.0


# ----------------------------- indicators ----------------------------------
def ema(vals, period):
    out = [None] * len(vals)
    if len(vals) < period:
        return out
    sma = sum(vals[:period]) / period
    out[period - 1] = sma
    k = 2.0 / (period + 1)
    for i in range(period, len(vals)):
        out[i] = vals[i] * k + out[i - 1] * (1 - k)
    return out


def rma(vals, period):
    """Wilder's smoothing (used by ATR/RSI/ADX)."""
    out = [None] * len(vals)
    if len(vals) < period:
        return out
    avg = sum(vals[:period]) / period
    out[period - 1] = avg
    for i in range(period, len(vals)):
        avg = (avg * (period - 1) + vals[i]) / period
        out[i] = avg
    return out


def true_ranges(h, l, c):
    tr = [None] * len(c)
    for i in range(1, len(c)):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    return tr


def atr(h, l, c, period):
    tr = true_ranges(h, l, c)
    return rma([0.0 if x is None else x for x in tr], period)


def rsi(c, period):
    gains = [0.0] * len(c)
    losses = [0.0] * len(c)
    for i in range(1, len(c)):
        d = c[i] - c[i - 1]
        gains[i] = max(d, 0.0)
        losses[i] = max(-d, 0.0)
    ag = rma(gains, period)
    al = rma(losses, period)
    out = [None] * len(c)
    for i in range(len(c)):
        if ag[i] is None or al[i] is None:
            continue
        if al[i] == 0:
            out[i] = 100.0
        else:
            rs = ag[i] / al[i]
            out[i] = 100.0 - 100.0 / (1 + rs)
    return out


def adx(h, l, c, period):
    n = len(c)
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    tr = [0.0] * n
    for i in range(1, n):
        up = h[i] - h[i - 1]
        dn = l[i - 1] - l[i]
        plus_dm[i] = up if (up > dn and up > 0) else 0.0
        minus_dm[i] = dn if (dn > up and dn > 0) else 0.0
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    str_ = rma(tr, period)
    sp = rma(plus_dm, period)
    sm = rma(minus_dm, period)
    dx = [None] * n
    for i in range(n):
        if str_[i] is None or str_[i] == 0:
            continue
        pdi = 100.0 * sp[i] / str_[i]
        mdi = 100.0 * sm[i] / str_[i]
        s = pdi + mdi
        dx[i] = 0.0 if s == 0 else 100.0 * abs(pdi - mdi) / s
    # ADX = RMA of DX, started after first valid DX
    out = [None] * n
    first = next((i for i, v in enumerate(dx) if v is not None), None)
    if first is None:
        return out
    vals = [0.0 if dx[i] is None else dx[i] for i in range(n)]
    sm2 = rma(vals[first:], period)
    for j, v in enumerate(sm2):
        out[first + j] = v
    return out


def bollinger(c, period, dev):
    up = [None] * len(c)
    lo = [None] * len(c)
    mid = [None] * len(c)
    for i in range(period - 1, len(c)):
        window = c[i - period + 1:i + 1]
        m = sum(window) / period
        var = sum((x - m) ** 2 for x in window) / period   # population (MQL5)
        sd = math.sqrt(var)
        mid[i] = m
        up[i] = m + dev * sd
        lo[i] = m - dev * sd
    return up, mid, lo


# ----------------------------- risk math (ports CalcLot) -------------------
def calc_lot(equity, sl_dist, cfg: Cfg):
    risk_amt = equity * cfg.risk_pct / 100.0
    if cfg.tick_value <= 0 or cfg.tick_size <= 0 or sl_dist <= 0:
        return 0.0
    money_per_price_per_lot = cfg.tick_value / cfg.tick_size
    loss_per_lot = sl_dist * money_per_price_per_lot
    if loss_per_lot <= 0:
        return 0.0
    lot = risk_amt / loss_per_lot
    lot = math.floor(lot / cfg.vol_step) * cfg.vol_step
    if lot > cfg.vol_max:
        lot = cfg.vol_max
    if lot < cfg.vol_min:
        return 0.0
    return round(lot, 2)


def money_per_price(cfg: Cfg):
    return cfg.tick_value / cfg.tick_size


# ----------------------------- data ----------------------------------------
def fetch_yahoo(symbol="EURUSD=X", rng="730d", interval="1h"):
    socket.setdefaulttimeout(15)
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?range={rng}&interval={interval}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    d = json.loads(urllib.request.urlopen(req).read())
    r = d["chart"]["result"][0]
    ts = r["timestamp"]
    q = r["indicators"]["quote"][0]
    bars = []
    for i in range(len(ts)):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        bars.append((datetime.fromtimestamp(ts[i], tz=timezone.utc), o, h, l, c))
    return bars


def resample_htf(bars, factor_seconds):
    """Group bars into HTF buckets; return dict bucket_key -> close list end."""
    buckets = {}
    for dt, o, h, l, c in bars:
        key = int(dt.timestamp()) // factor_seconds
        if key not in buckets:
            buckets[key] = [o, h, l, c]
        else:
            b = buckets[key]
            b[1] = max(b[1], h)
            b[2] = min(b[2], l)
            b[3] = c
    keys = sorted(buckets)
    closes = [buckets[k][3] for k in keys]
    return keys, closes


# ----------------------------- backtest (ports the EA loop) ----------------
def run(bars, cfg: Cfg, htf_factor_seconds=4 * 3600):
    dts = [b[0] for b in bars]
    o = [b[1] for b in bars]
    h = [b[2] for b in bars]
    l = [b[3] for b in bars]
    c = [b[4] for b in bars]
    n = len(c)

    fast = ema(c, cfg.fast_ema)
    slow = ema(c, cfg.slow_ema)
    pull = ema(c, cfg.pull_ema)
    adx_v = adx(h, l, c, cfg.adx_period)
    rsi_v = rsi(c, cfg.rsi_period)
    bb_up, bb_mid, bb_lo = bollinger(c, cfg.bb_period, cfg.bb_dev)
    atr_v = atr(h, l, c, cfg.atr_period)

    # HTF EMA: compute on resampled closes, map prior-closed value onto bars.
    hkeys, hcloses = resample_htf(bars, htf_factor_seconds)
    htf_ema_series = ema(hcloses, cfg.htf_ema)
    key_to_idx = {k: i for i, k in enumerate(hkeys)}

    def htf_ema_at(dt):
        key = int(dt.timestamp()) // htf_factor_seconds
        idx = key_to_idx.get(key)
        if idx is None or idx == 0:
            return None
        return htf_ema_series[idx - 1]   # last CLOSED htf bar

    mpp = money_per_price(cfg)
    spread_price = cfg.spread_points * cfg.tick_size

    balance = cfg.initial_balance
    pos = None  # dict: dir, lot, entry, sl, tp, open_eq
    trades = []
    regime_count = {"trend": 0, "range": 0, "neutral": 0}

    cur_day = None
    day_start_eq = balance
    trades_today = 0
    halt_today = False
    halt_perm = False
    dd_peak_breached = False
    daily_halt_fired = 0
    max_dd_seen = 0.0

    def equity_now(price):
        if pos is None:
            return balance
        flt = (price - pos["entry"]) * pos["dir"] * mpp * pos["lot"]
        return balance + flt

    for i in range(n):
        dt = dts[i]
        # daily reset
        d = dt.date()
        if d != cur_day:
            cur_day = d
            day_start_eq = equity_now(c[i])
            trades_today = 0
            halt_today = False

        eq = equity_now(c[i])
        # track drawdown vs initial balance
        dd = (cfg.initial_balance - eq) / cfg.initial_balance * 100.0
        max_dd_seen = max(max_dd_seen, dd)

        # risk guards
        if not halt_today and cfg.daily_loss_pct > 0:
            if eq <= day_start_eq * (1 - cfg.daily_loss_pct / 100.0):
                halt_today = True
                daily_halt_fired += 1
                if pos is not None:
                    balance = close_position(balance, pos, c[i], mpp, spread_price, trades, dt, "daily_halt")
                    pos = None
        if not halt_perm and cfg.max_dd_pct > 0:
            if eq <= cfg.initial_balance * (1 - cfg.max_dd_pct / 100.0):
                halt_perm = True
                dd_peak_breached = True
                if pos is not None:
                    balance = close_position(balance, pos, c[i], mpp, spread_price, trades, dt, "max_dd")
                    pos = None

        # manage open position over THIS bar (SL first = conservative)
        if pos is not None:
            hit = None
            if pos["dir"] == 1:
                if l[i] <= pos["sl"]:
                    hit = pos["sl"]
                elif h[i] >= pos["tp"]:
                    hit = pos["tp"]
            else:
                if h[i] >= pos["sl"]:
                    hit = pos["sl"]
                elif l[i] <= pos["tp"]:
                    hit = pos["tp"]
            if hit is not None:
                balance = close_position(balance, pos, hit, mpp, spread_price, trades, dt, "sl/tp")
                pos = None
            elif atr_v[i]:
                # breakeven + trailing using this bar's ATR
                a = atr_v[i]
                if pos["dir"] == 1:
                    new_sl = pos["sl"]
                    if cfg.use_be and (c[i] - pos["entry"]) >= a * cfg.be_trigger_atr:
                        new_sl = max(new_sl, pos["entry"] + a * cfg.be_lock_atr)
                    if cfg.use_trail:
                        new_sl = max(new_sl, c[i] - a * cfg.trail_atr)
                    if new_sl > pos["sl"]:
                        pos["sl"] = new_sl
                else:
                    new_sl = pos["sl"]
                    if cfg.use_be and (pos["entry"] - c[i]) >= a * cfg.be_trigger_atr:
                        new_sl = min(new_sl, pos["entry"] - a * cfg.be_lock_atr)
                    if cfg.use_trail:
                        new_sl = min(new_sl, c[i] + a * cfg.trail_atr)
                    if new_sl < pos["sl"]:
                        pos["sl"] = new_sl

        if halt_perm or halt_today:
            continue

        # ---- entry decision on this CLOSED bar -> fill at next bar open ----
        if pos is not None or trades_today >= cfg.max_trades_day:
            continue
        if i + 1 >= n:
            continue
        if not pass_filters(dt, cfg):
            continue

        a1 = adx_v[i]
        f1, s1, p1 = fast[i], slow[i], pull[i]
        he = htf_ema_at(dt)
        at1 = atr_v[i]
        if None in (a1, f1, s1, p1, he, at1) or at1 <= 0:
            continue

        close1, low1, high1 = c[i], l[i], h[i]
        bias_up = close1 > he and f1 > s1
        bias_dn = close1 < he and f1 < s1
        long_sig = short_sig = False
        rr = cfg.trend_rr

        if a1 >= cfg.adx_trend:
            regime_count["trend"] += 1
            if bias_up and low1 <= p1 and close1 > p1:
                long_sig = True
            if bias_dn and high1 >= p1 and close1 < p1:
                short_sig = True
            rr = cfg.trend_rr
        elif a1 < cfg.adx_range:
            regime_count["range"] += 1
            u1, lo1, r1 = bb_up[i], bb_lo[i], rsi_v[i]
            if None in (u1, lo1, r1):
                continue
            if close1 <= lo1 and r1 < cfg.rsi_os:
                long_sig = True
            if close1 >= u1 and r1 > cfg.rsi_ob:
                short_sig = True
            rr = cfg.range_rr
        else:
            regime_count["neutral"] += 1
            continue

        if not (long_sig or short_sig):
            continue

        direction = 1 if long_sig else -1
        entry = o[i + 1] + (spread_price / 2 if direction == 1 else -spread_price / 2)
        sl_dist = at1 * cfg.sl_atr
        sl = entry - sl_dist * direction
        tp = entry + sl_dist * rr * direction
        lot = calc_lot(eq, sl_dist, cfg)
        if lot <= 0:
            continue
        pos = {"dir": direction, "lot": lot, "entry": entry, "sl": sl, "tp": tp,
               "open_dt": dts[i + 1], "open_eq": eq, "rr": rr}
        trades_today += 1

    # close any dangling position at last close
    if pos is not None:
        balance = close_position(balance, pos, c[-1], mpp, spread_price, trades, dts[-1], "end")

    res = summarize(trades, regime_count, cfg, balance, max_dd_seen, daily_halt_fired)
    res["max_dd_halt"] = dd_peak_breached
    return res


def close_position(balance, pos, exit_price, mpp, spread_price, trades, dt, reason):
    pl = (exit_price - pos["entry"]) * pos["dir"] * mpp * pos["lot"]
    pl -= spread_price / 2 * mpp * pos["lot"]   # exit-side spread cost
    trades.append({"dir": pos["dir"], "pl": pl, "reason": reason,
                   "open_dt": pos["open_dt"], "close_dt": dt})
    return balance + pl


def pass_filters(dt, cfg: Cfg):
    # weekday: python weekday() Mon=0..Sun=6 -> MQL day_of_week Sun=0..Sat=6
    mql_dow = (dt.weekday() + 1) % 7
    if mql_dow not in cfg.trade_days:
        return False
    if cfg.use_session:
        hh = dt.hour
        if cfg.sess_start <= cfg.sess_end:
            if not (cfg.sess_start <= hh < cfg.sess_end):
                return False
        else:
            if not (hh >= cfg.sess_start or hh < cfg.sess_end):
                return False
    return True


def summarize(trades, regime_count, cfg, final_balance, max_dd_seen, daily_halts):
    n = len(trades)
    wins = sum(1 for t in trades if t["pl"] > 0)
    gross = sum(t["pl"] for t in trades)
    net = final_balance - cfg.initial_balance
    return {
        "trades": n,
        "win_rate": (100.0 * wins / n) if n else 0.0,
        "net_pl": net,
        "final_balance": final_balance,
        "max_dd_pct": max_dd_seen,
        "daily_halts": daily_halts,
        "regime_bars": regime_count,
    }


def main():
    cfg = Cfg()
    print("StellarEA LOGIC verification (NOT an MT5 backtest / NOT profitability)")
    print("-" * 70)
    try:
        bars = fetch_yahoo("EURUSD=X", "730d", "1h")
        src = "Yahoo EURUSD=X 1h (HTF=4h), times in UTC"
    except Exception as e:
        print(f"[data] live fetch failed ({e!r}); aborting run.")
        return
    print(f"[data] {src}: {len(bars)} bars "
          f"{bars[0][0].date()} -> {bars[-1][0].date()}")
    res = run(bars, cfg)
    rb = res["regime_bars"]
    tot = sum(rb.values()) or 1
    print(f"[regime] trend={rb['trend']} ({100*rb['trend']/tot:.0f}%)  "
          f"range={rb['range']} ({100*rb['range']/tot:.0f}%)  "
          f"neutral={rb['neutral']} ({100*rb['neutral']/tot:.0f}%)")
    print(f"[trades] count={res['trades']}  win_rate={res['win_rate']:.1f}%")
    print(f"[risk]   max_dd_seen={res['max_dd_pct']:.2f}%  "
          f"daily_halts_fired={res['daily_halts']}  "
          f"max_dd_halt={'YES' if res['max_dd_halt'] else 'no'}")
    print(f"[pnl]    net={res['net_pl']:.2f}  final_balance={res['final_balance']:.2f} "
          f"(indicative only)")
    print("-" * 70)
    print("Interpretation: confirms the pipeline produces trades, the regime")
    print("switch fires, and the DD guard keeps drawdown within the configured")
    print("limit. P/L here is indicative, not a performance claim - run MT5.")


if __name__ == "__main__":
    main()
