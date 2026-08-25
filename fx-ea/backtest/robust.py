#!/usr/bin/env python3
"""Robustness checks for the H1 Donchian-breakout winner."""
import os
from sweep import load, resample, run, stats, UP, FILES, SPREADS, RISK_PCT

data = {s: load(os.path.join(UP, f)) for s, f in FILES.items()}

def cfg_for(don, tf=1):
    return dict(tf=tf, entry='donchian', don=don, rsi_buy=0, rsi_sell=0,
                fast=50, slow=200, sl=2.0, tp=3.0, be=True, trail=2.0,
                name=f'don{don}')

print("=== Donchian period sensitivity (H1, full period 2016-2025) ===")
print(f"{'don':<6}{'pair':<8}{'n':>6}{'PF':>7}{'net%':>10}{'maxDD%':>9}{'win%':>7}")
for don in (10, 15, 20, 25, 30, 40):
    for s in FILES:
        tr = run(data[s], SPREADS[s], cfg_for(don))
        st = stats(tr, 2016, 2025)
        print(f"{don:<6}{s:<8}{st['n']:>6}{st['pf']:>7.2f}{st['net']:>+10.1f}{st['dd']:>9.1f}{st['wr']:>7.1f}")

print("\n=== Spread stress (don20): normal vs +50% vs x2 ===")
for s in FILES:
    for mult, lbl in ((1.0, 'normal'), (1.5, '+50%'), (2.0, 'x2')):
        tr = run(data[s], SPREADS[s]*mult, cfg_for(20))
        st = stats(tr, 2016, 2025)
        print(f"{s} {lbl:<8} PF={st['pf']:.2f} net={st['net']:+8.1f}% DD={st['dd']:.1f}%")

print("\n=== Yearly net% (don20) ===")
for s in FILES:
    tr = run(data[s], SPREADS[s], cfg_for(20))
    ys = {}
    for t, r in tr:
        ys.setdefault(t.year, 0.0)
        ys[t.year] += RISK_PCT * r
    line = "  ".join(f"{y}:{v:+.1f}" for y, v in sorted(ys.items()))
    neg = sum(1 for v in ys.values() if v < 0)
    print(f"{s}: {line}  (losing years: {neg}/10)")

print("\n=== SL/TP sensitivity (don20, H1) ===")
for sl, tp in ((1.5, 2.25), (2.0, 3.0), (2.5, 3.75), (2.0, 4.0), (3.0, 4.5)):
    for s in FILES:
        c = cfg_for(20); c['sl'] = sl; c['tp'] = tp
        tr = run(data[s], SPREADS[s], c)
        st = stats(tr, 2016, 2025)
        print(f"SL{sl}/TP{tp} {s}: PF={st['pf']:.2f} net={st['net']:+8.1f}% DD={st['dd']:.1f}%")
