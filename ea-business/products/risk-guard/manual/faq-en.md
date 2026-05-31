# RiskGuard — FAQ (English)

**Q. Does RiskGuard trade automatically?**
A. No. You make the entry decision. RiskGuard handles sizing, order placement and management (break-even, trailing).

**Q. Is this a "guaranteed win" tool?**
A. No. It does not predict markets and guarantees no profit. It mechanically applies your risk rules. Past performance does not guarantee future results.

**Q. I press BUY/SELL but nothing happens.**
A. Check: (1) Algo Trading is ON, (2) `InpStopLossPips` is not 0, (3) spread is within `InpMaxSpreadPts`, (4) license status is valid, (5) computed lot is not 0 (verify risk %, SL, free margin).

**Q. The lot looks too small/large.**
A. Lot = balance × risk% ÷ (SL distance × loss per 1 lot). A wider SL produces a smaller lot. Use `InpFixedLot` for a fixed size.

**Q. I get a WebRequest error (e.g. 4014). (self-hosted build)**
A. Add the license server URL to the whitelist in Tools > Options > Expert Advisors (see setup-en.md).

**Q. Can I run it on multiple charts?**
A. Yes. It works per symbol and identifies its own trades via `InpMagic`. CLOSE ALL only affects the same symbol and magic.

**Q. Supported accounts?**
A. MetaTrader 5, with 3- and 5-digit quote support. Test on a demo account first.

**Q. Refunds / support?**
A. Per the terms on the sales page. Report issues to the support channel where you purchased.
