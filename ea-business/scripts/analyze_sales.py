#!/usr/bin/env python3
"""Summarize sales across channels from exported CSVs.

Reads Gumroad/Stripe/MQL5 sales exports (CSV) and prints a per-channel summary:
units, gross, estimated net after platform fees, and refund count. Fee models
are the verified 2026 rates (see docs/phase0-design.md) and can be overridden.

This is an internal analysis tool. It does NOT forecast or guarantee anything.

Usage:
    python analyze_sales.py sales.csv [sales2.csv ...] [--rate USDJPY]

CSV is auto-sniffed for common column names:
    amount/price/total, channel/source, refunded/status, currency

Stdlib only.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Verified 2026 fee models. net = gross*(1-pct) - flat (per sale).
FEES = {
    "mql5":    (0.20, 0.00),
    "gumroad": (0.10, 0.50),   # + payment processing handled separately by Gumroad
    "stripe":  (0.029, 0.30),  # self-hosted: only processor fee
    "booth":   (0.056, 0.29),  # 5.6% + 45 JPY (~0.29 USD @155) -> flat in USD approx
    "other":   (0.0, 0.0),
}

AMOUNT_COLS  = ["amount", "price", "total", "gross", "sale price", "subtotal"]
CHANNEL_COLS = ["channel", "source", "platform", "store"]
REFUND_COLS  = ["refunded", "status", "state"]


def pick(row: dict, names: list[str]) -> str | None:
    low = {k.lower().strip(): v for k, v in row.items()}
    for n in names:
        if n in low and low[n] not in (None, ""):
            return low[n]
    return None


def to_float(s: str | None) -> float:
    if not s:
        return 0.0
    cleaned = "".join(c for c in str(s) if c.isdigit() or c in ".-")
    try:
        return float(cleaned or 0)
    except ValueError:
        return 0.0


def is_refund(row: dict) -> bool:
    v = (pick(row, REFUND_COLS) or "").lower()
    return "refund" in v or "dispute" in v or v == "true"


def channel_of(row: dict, default: str) -> str:
    c = (pick(row, CHANNEL_COLS) or default).lower()
    for key in FEES:
        if key in c:
            return key
    return "other"


def net_of(gross: float, channel: str) -> float:
    pct, flat = FEES.get(channel, FEES["other"])
    return max(0.0, gross * (1 - pct) - flat)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="+", help="sales CSV exports")
    ap.add_argument("--default-channel", default="other")
    args = ap.parse_args(argv)

    agg: dict[str, dict[str, float]] = {}
    for fp in args.files:
        path = Path(fp)
        if not path.exists():
            print(f"warn: skip missing {fp}", file=sys.stderr)
            continue
        with path.open(newline="", encoding="utf-8", errors="ignore") as fh:
            for row in csv.DictReader(fh):
                ch = channel_of(row, args.default_channel)
                gross = to_float(pick(row, AMOUNT_COLS))
                a = agg.setdefault(ch, {"units": 0, "gross": 0.0, "net": 0.0, "refunds": 0})
                if is_refund(row):
                    a["refunds"] += 1
                    continue
                a["units"] += 1
                a["gross"] += gross
                a["net"] += net_of(gross, ch)

    if not agg:
        print("No sales rows parsed.")
        return 0

    print(f"{'channel':10} {'units':>6} {'gross':>12} {'est.net':>12} {'refunds':>8}")
    print("-" * 52)
    tot = {"units": 0, "gross": 0.0, "net": 0.0, "refunds": 0}
    for ch, a in sorted(agg.items()):
        print(f"{ch:10} {int(a['units']):>6} {a['gross']:>12.2f} {a['net']:>12.2f} {int(a['refunds']):>8}")
        for k in tot:
            tot[k] += a[k]
    print("-" * 52)
    print(f"{'TOTAL':10} {int(tot['units']):>6} {tot['gross']:>12.2f} {tot['net']:>12.2f} {int(tot['refunds']):>8}")
    print("\nNote: internal estimate after platform fees. Not a forecast.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
