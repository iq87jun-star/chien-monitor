# RiskGuard — User Manual (English)

**Version:** 1.00 · **Platform:** MetaTrader 5 · **Type:** EA (manual-trading assistant)

---

## ⚠️ Risk Disclosure / Disclaimer
Trading leveraged products carries a high level of risk and can result in losses exceeding your deposit. RiskGuard is a **position-sizing and order-management assistant**. It does not generate trading signals and does not predict the market. It provides **no guarantee of profit. Past performance does not guarantee future results.** Use at your own risk.

---

## 1. What RiskGuard is
RiskGuard is a manual-trading assistant EA. You press Buy or Sell; RiskGuard **computes the lot size from a fixed account-risk %**, attaches a Stop Loss (SL) and Take Profit (TP), then manages the open position (break-even, trailing stop).

It is **not** an automated strategy. **You make the entry decision.**

### Features
- Risk-% based lot sizing (or fixed lot)
- SL in pips + TP as an R multiple
- Break-even (move SL to entry + lock)
- Trailing stop
- Spread filter (blocks entries when spread is too wide)
- On-chart panel (BUY / SELL / CLOSE ALL)

---

## 2. Inputs

### Risk & sizing
| Input | Description |
|---|---|
| `InpRiskPercent` | Risk per trade (% of balance). e.g. 1.0 = 1% |
| `InpFixedLot` | Fixed lot. If > 0 it overrides risk % |
| `InpStopLossPips` | Stop Loss in pips. **0 blocks orders** (no risk calc possible) |
| `InpRiskReward` | TP as a multiple of SL (R). 0 = no TP |

### Position management
| Input | Description |
|---|---|
| `InpUseBreakEven` | Enable break-even |
| `InpBreakEvenPips` | Profit (pips) to trigger break-even |
| `InpBreakEvenLock` | Profit (pips) locked at break-even |
| `InpUseTrailing` | Enable trailing stop |
| `InpTrailStartPips` | Profit (pips) before trailing starts |
| `InpTrailStepPips` | Trailing distance (pips) |

### Filters & execution
| Input | Description |
|---|---|
| `InpMaxSpreadPts` | Max allowed spread (points) |
| `InpSlippagePts` | Max deviation (points) |
| `InpMagic` | Magic number |

### Licensing (self-hosted build only)
| Input | Description |
|---|---|
| `InpLicenseKey` | License key issued at purchase |
| `InpLicenseServer` | License verification API URL (set by seller) |

> The MQL5 Market build needs no license input (handled by the platform).

---

## 3. How to use
1. Set your SL (`InpStopLossPips`) and risk (`InpRiskPercent`).
2. Read the computed lot from the panel label (top-left of the chart).
3. Press **BUY / SELL** — the order is sent with that lot and SL/TP.
4. Break-even and trailing then manage the position automatically.
5. **CLOSE ALL** closes all positions for this symbol and magic number.

> Pip conversion supports 3- and 5-digit quotes (1 pip = 10 points).

---

## 4. Notes
- SL = 0 disables entries (risk cannot be computed). This is by design.
- Entries are skipped when the spread exceeds `InpMaxSpreadPts`.
- If the computed lot is below the broker minimum, it is rounded up to the minimum — verify your margin and risk tolerance.

See `setup-en.md` for installation and `faq-en.md` for common questions.
