---
title: "Automating Money Management in MT5: Risk-% Based Position Sizing"
lang: en
keywords: ["MT5 lot size calculator", "position sizing", "risk percent lot", "money management MT5"]
status: draft
canonical: ""
---

# Automating Money Management in MT5: Risk-% Based Position Sizing

Before any trade is won or lost, one thing is already decided: **how much you risk per trade**. This post explains how to size positions in MT5 from a fixed *percentage of account balance* — and how to automate it.

## Why fixed lots are risky
A fixed lot does not keep your risk constant as balance or stop distance change. With a wide stop your real risk balloons; with a tight stop you under- or over-size.

## The risk-% sizing formula
```
risk money   = balance × risk%
loss per lot = (SL distance / tick size) × tick value
lot          = risk money / loss per lot
```
From the stop distance, symbol specs (tick value/size) and balance, you get the lot that loses the **same %** every time.

## Implementation notes (MQL5)
- Use `SYMBOL_TRADE_TICK_VALUE` / `SYMBOL_TRADE_TICK_SIZE` (pip value differs across JPY crosses vs. USD pairs).
- 3- and 5-digit quotes: 1 pip = 10 points.
- Round to the broker's min/max lot and lot step.

## Takeaway
Fixing risk % is the starting point of risk management. Systematizing the lot calculation — manual or automated — removes a major source of inconsistency.

---
> This article is informational, not investment advice. Trading leveraged products is risky; past performance does not guarantee future results.

<!-- CTA: One-click sizing and trade management → RiskGuard ($49, buy-once). See the landing page. -->
