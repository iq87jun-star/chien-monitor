#!/usr/bin/env python3
"""Generate a clean performance summary from an MT5 Strategy Tester HTML report.

The MT5 tester exports an HTML report ("Report" / "ReportTester...html"). This
script parses the key metrics and emits a tidy Markdown summary with a MANDATORY
risk disclaimer injected — so every performance asset we publish stays compliant
(no profit guarantees, past-performance disclaimer always present).

Usage:
    python gen_report.py <tester_report.html> [-o out.md] [--lang ja|en]

Requires only the standard library.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

DISCLAIMER = {
    "en": (
        "> **Risk disclosure:** These results are from a historical backtest on "
        "past data. Backtest results do not represent live trading and **do not "
        "guarantee future results.** Trading leveraged products carries a high "
        "level of risk. This material is not investment advice."
    ),
    "ja": (
        "> **リスク開示：** 本結果は過去データに基づくバックテストの結果です。"
        "バックテストはリアル取引の成果を表すものではなく、**将来の結果を保証しません。**"
        "レバレッジ取引には高いリスクが伴います。本資料は投資助言ではありません。"
    ),
}

# Metrics we surface. Keys are substrings as they appear in the MT5 report.
WANTED = [
    "Total Net Profit",
    "Profit Factor",
    "Expected Payoff",
    "Maximal drawdown",
    "Maximum drawdown",
    "Total Trades",
    "Sharpe Ratio",
    "Initial Deposit",
    "Recovery Factor",
]


def strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def parse_metrics(raw_html: str) -> dict[str, str]:
    """Extract label/value pairs from the report's table cells."""
    plain = strip_tags(raw_html)
    found: dict[str, str] = {}
    for label in WANTED:
        # value typically follows the label, possibly after a colon
        m = re.search(
            re.escape(label) + r"\s*:?\s*([-\d][\d\s.,%]*)", plain, re.IGNORECASE
        )
        if m:
            found[label] = m.group(1).strip()
    return found


def build_markdown(metrics: dict[str, str], src: str, lang: str) -> str:
    lines = [
        f"# Backtest Summary — {Path(src).stem}",
        "",
        DISCLAIMER.get(lang, DISCLAIMER["en"]),
        "",
        "| Metric | Value |",
        "| --- | --- |",
    ]
    if metrics:
        for k, v in metrics.items():
            lines.append(f"| {k} | {v} |")
    else:
        lines.append("| (no recognizable metrics found) | — |")
    lines += [
        "",
        f"_Source report: `{src}`_",
        "",
        DISCLAIMER.get(lang, DISCLAIMER["en"]),
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("report", help="MT5 Strategy Tester HTML report")
    ap.add_argument("-o", "--out", help="output markdown path (default: stdout)")
    ap.add_argument("--lang", choices=["ja", "en"], default="en")
    args = ap.parse_args(argv)

    path = Path(args.report)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 1

    raw = path.read_text(encoding="utf-8", errors="ignore")
    metrics = parse_metrics(raw)
    md = build_markdown(metrics, str(path), args.lang)

    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"wrote {args.out} ({len(metrics)} metrics)")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
