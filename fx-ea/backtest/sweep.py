#!/usr/bin/env python3
"""Variant sweep for ChienTrendRider logic with IS (2016-2021) / OOS (2022-2025) split."""
import csv, os
from datetime import datetime

UP = '/root/.claude/uploads/a60920ff-b5f1-54fc-b986-4629d305c95d'
FILES = {'USDJPY': '4fc0bf86-USDJPY_h1.csv',
         'EURJPY': '0fb4ac0c-EURJPY_h1.csv',
         'GBPJPY': 'ad848be3-GBPJPY_h1.csv'}
SPREADS = {'USDJPY': 0.004, 'EURJPY': 0.006, 'GBPJPY': 0.012}
RISK_PCT = 1.0

def load(path):
    rows = []
    with open(path) as f:
        r = csv.reader(f); next(r)
        for line in r:
            rows.append((datetime.strptime(line[0], '%Y-%m-%d %H:%M:%S'),
                         float(line[1]), float(line[2]), float(line[3]), float(line[4])))
    return rows

def resample(rows, hours):
    if hours == 1: return rows
    out = []; cur = None
    for t, o, h, l, c in rows:
        # bucket by epoch-hour block
        block = (t.toordinal() * 24 + t.hour) // hours
        if cur is None or cur[0] != block:
            if cur: out.append(cur[1])
            cur = (block, [t, o, h, l, c])
        else:
            b = cur[1]
            b[2] = max(b[2], h); b[3] = min(b[3], l); b[4] = c
    if cur: out.append(cur[1])
    return [tuple(b) for b in out]

def ema_series(closes, period):
    out = [None]*len(closes); k = 2.0/(period+1)
    if len(closes) < period: return out
    out[period-1] = sum(closes[:period])/period
    for i in range(period, len(closes)):
        out[i] = closes[i]*k + out[i-1]*(1-k)
    return out

def rsi_series(closes, period):
    out = [None]*len(closes)
    if len(closes) <= period: return out
    g = l = 0.0
    for i in range(1, period+1):
        d = closes[i]-closes[i-1]; g += max(d,0); l += max(-d,0)
    ag, al = g/period, l/period
    out[period] = 100.0 if al == 0 else 100-100/(1+ag/al)
    for i in range(period+1, len(closes)):
        d = closes[i]-closes[i-1]
        ag = (ag*(period-1)+max(d,0))/period
        al = (al*(period-1)+max(-d,0))/period
        out[i] = 100.0 if al == 0 else 100-100/(1+ag/al)
    return out

def atr_series(rows, period):
    n = len(rows); out = [None]*n; trs = [None]*n
    for i in range(1, n):
        h, l, pc = rows[i][2], rows[i][3], rows[i-1][4]
        trs[i] = max(h-l, abs(h-pc), abs(l-pc))
    if n <= period: return out
    out[period] = sum(trs[1:period+1])/period
    for i in range(period+1, n):
        out[i] = (out[i-1]*(period-1)+trs[i])/period
    return out

def donchian(rows, period):
    """highest high / lowest low of previous `period` bars (excluding current)."""
    n = len(rows); hh = [None]*n; ll = [None]*n
    for i in range(period, n):
        hs = [rows[j][2] for j in range(i-period, i)]
        ls = [rows[j][3] for j in range(i-period, i)]
        hh[i] = max(hs); ll[i] = min(ls)
    return hh, ll

def run(rows, spread, cfg):
    closes = [r[4] for r in rows]
    ef = ema_series(closes, cfg['fast']); es = ema_series(closes, cfg['slow'])
    rsi = rsi_series(closes, 14); atr = atr_series(rows, 14)
    entry_type = cfg['entry']
    if entry_type == 'donchian':
        hh, ll = donchian(rows, cfg.get('don', 20))
    sl_m, tp_m = cfg['sl'], cfg['tp']
    use_be, use_trail, trail_m = cfg['be'], cfg['trail'] > 0, cfg['trail']
    be_trig, be_lock = 1.0, 0.1

    pos = None; trades = []
    start = cfg['slow'] + 5
    for i in range(start, len(rows)):
        t, o, h, l, c = rows[i]
        if pos is not None:
            d = pos['dir']; ex = None
            if d > 0:
                if l <= pos['sl']: ex = pos['sl']
                elif pos['tp'] and h >= pos['tp']: ex = pos['tp']
            else:
                if h + spread >= pos['sl']: ex = pos['sl']
                elif pos['tp'] and l + spread <= pos['tp']: ex = pos['tp']
            if ex is not None:
                r_mult = d*(ex-pos['entry'])/pos['sl0']
                trades.append((t, r_mult)); pos = None
            else:
                a = atr[i]
                if a and (use_be or use_trail):
                    if d > 0:
                        ns = pos['sl']
                        if use_be and c-pos['entry'] >= a*be_trig:
                            ns = max(ns, pos['entry']+a*be_lock)
                        if use_trail:
                            tr = c-a*trail_m
                            if tr > ns and tr > pos['entry']: ns = tr
                        if ns > pos['sl'] and ns < c: pos['sl'] = ns
                    else:
                        ns = pos['sl']
                        if use_be and pos['entry']-(c+spread) >= a*be_trig:
                            ns = min(ns, pos['entry']-a*be_lock)
                        if use_trail:
                            tr = c+spread+a*trail_m
                            if tr < ns and tr < pos['entry']: ns = tr
                        if ns < pos['sl'] and ns > c+spread: pos['sl'] = ns
        if pos is None:
            if t.weekday() >= 5: continue
            e_f, e_s, a = ef[i-1], es[i-1], atr[i-1]
            if None in (e_f, e_s, a) or a <= 0: continue
            up_ok = e_f > e_s; dn_ok = e_f < e_s
            go = 0
            if entry_type == 'rsi':
                r1, r2 = rsi[i-1], rsi[i-2]
                if r1 is None or r2 is None: continue
                lb, ls_ = cfg['rsi_buy'], cfg['rsi_sell']
                if up_ok and r2 < lb and r1 >= lb: go = 1
                elif dn_ok and r2 > ls_ and r1 <= ls_: go = -1
            elif entry_type == 'donchian':
                H, L = hh[i-1], ll[i-1]
                if H is None: continue
                pc = rows[i-1][4]
                if up_ok and pc > H: go = 1
                elif dn_ok and pc < L: go = -1
            if go == 1:
                e = o + spread
                pos = {'dir': 1, 'entry': e, 'sl': e-a*sl_m,
                       'tp': e+a*tp_m if tp_m > 0 else None, 'sl0': a*sl_m}
            elif go == -1:
                e = o
                pos = {'dir': -1, 'entry': e, 'sl': e+a*sl_m,
                       'tp': e-a*tp_m if tp_m > 0 else None, 'sl0': a*sl_m}
    return trades

def stats(trades, y0, y1):
    tr = [(t, r) for t, r in trades if y0 <= t.year <= y1]
    n = len(tr)
    if n == 0: return dict(n=0, pf=0, net=0, dd=0, wr=0)
    bal = 100.0; peak = 100.0; dd = 0.0
    gp = gl = 0.0; w = 0
    for _, r in tr:
        p = RISK_PCT * r
        if p > 0: gp += p; w += 1
        else: gl += -p
        bal *= (1 + p/100)
        peak = max(peak, bal); dd = max(dd, (peak-bal)/peak*100)
    pf = gp/gl if gl > 0 else 99.0
    return dict(n=n, pf=pf, net=bal-100, dd=dd, wr=w/n*100)

if __name__ == '__main__':
    data = {s: load(os.path.join(UP, f)) for s, f in FILES.items()}
    tf_cache = {}
    for s, rows in data.items():
        for tfh in (1, 4):
            tf_cache[(s, tfh)] = resample(rows, tfh)

    configs = []
    for tfh in (1, 4):
        for entry in ('rsi', 'donchian'):
            if entry == 'rsi':
                levels = [(40, 60), (45, 55), (50, 50)]
            else:
                levels = [(0, 0)]
            for lb, ls_ in levels:
                for exit_name, tp, be, trail in (
                        ('tp3_be_tr2', 3.0, True, 2.0),
                        ('tr3_only',   0.0, False, 3.0),
                        ('tp4_be',     4.0, True, 0.0)):
                    configs.append(dict(tf=tfh, entry=entry, rsi_buy=lb, rsi_sell=ls_,
                                        fast=50, slow=200, sl=2.0, tp=tp, be=be,
                                        trail=trail, name=f"{'H1' if tfh==1 else 'H4'}"
                                        f"|{entry}{lb if entry=='rsi' else 20}|{exit_name}"))

    print(f"{'config':<28}{'pair':<8}{'IS n/PF/net%':<24}{'OOS n/PF/net%':<24}")
    summary = []
    for cfg in configs:
        agg_is_pf = []; agg_oos_pf = []; lines = []
        for s in FILES:
            tr = run(tf_cache[(s, cfg['tf'])], SPREADS[s], cfg)
            si = stats(tr, 2016, 2021); so = stats(tr, 2022, 2025)
            lines.append((s, si, so))
            agg_is_pf.append(si['pf']); agg_oos_pf.append(so['pf'])
        ok = all(p > 1.0 for p in agg_is_pf + agg_oos_pf)
        mark = ' <<<' if ok else ''
        for s, si, so in lines:
            print(f"{cfg['name']:<28}{s:<8}"
                  f"{si['n']:>4}/{si['pf']:.2f}/{si['net']:+7.1f}%      "
                  f"{so['n']:>4}/{so['pf']:.2f}/{so['net']:+7.1f}%{mark}")
        summary.append((cfg['name'], min(agg_is_pf+agg_oos_pf), ok))
    print("\n--- configs profitable in IS and OOS on all pairs ---")
    for name, mn, ok in summary:
        if ok: print(f"{name}  worstPF={mn:.2f}")
