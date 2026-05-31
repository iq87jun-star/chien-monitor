# TradeCloser — User Manual (English)

**Version:** 1.00 · **Platform:** MetaTrader 5 · **Type:** EA (closing & position-management utility)

---

## ⚠️ Risk Disclosure / Disclaimer
Trading leveraged products carries a high level of risk and can result in losses exceeding your deposit. TradeCloser is a **utility for closing and managing existing positions and orders**. It does not open trades, generate signals, or predict markets. It provides **no guarantee of profit. Past performance does not guarantee future results.** Use at your own risk.

---

## 1. What TradeCloser is
A one-panel utility to **close and manage your open positions and pending orders quickly and reliably**. It never opens new trades — it is closing/management only.

### Features
- **CLOSE ALL** — close every position in scope
- **CLOSE SYMBOL** — close only the current chart symbol
- **CLOSE WINNERS / LOSERS** — close only profitable / only losing positions
- **CLOSE %** — partial-close each position by a set percentage
- **DEL PENDINGS** — delete all pending orders
- **PANIC** — close all positions and delete all pendings in one click
- **Basket auto-close** — automatically close everything when total floating P/L reaches a profit target or a loss stop

---

## 2. Inputs

### Scope
| Input | Description |
|---|---|
| `InpCurrentSymbolOnly` | Act on the current chart symbol only |
| `InpFilterByMagic` | Only touch positions with the given magic |
| `InpMagic` | Magic to match (when filtering) |

### Partial close
| Input | Description |
|---|---|
| `InpPartialPercent` | % of volume to close on "CLOSE %" |

### Basket auto-close (0 = off)
| Input | Description |
|---|---|
| `InpTargetProfitMoney` | Close all when total P/L ≥ this (account ccy) |
| `InpTargetProfitPct` | ...or ≥ this % of balance |
| `InpStopLossMoney` | Close all when total P/L ≤ −this (account ccy) |
| `InpStopLossPct` | ...or ≤ −this % of balance |
| `InpBasketIncludesSwap` | Include swap in basket P/L |

> If both money and % are set, the **nearer (stricter)** trigger fires.

### Execution
| Input | Description |
|---|---|
| `InpSlippagePts` | Max deviation (points) |

### Licensing (self-hosted build only)
| Input | Description |
|---|---|
| `InpLicenseKey` | License key issued at purchase |
| `InpLicenseServer` | License verification API URL |

> Not required for the MQL5 Market build.

---

## 3. How to use
1. Set the scope (all / current symbol / magic).
2. Use the panel buttons to close or delete instantly.
3. For basket auto-close, set a profit target and/or loss stop; everything closes automatically when hit.
4. In emergencies, **PANIC** clears all positions and pendings at once.

---

## 4. Notes
- Positions whose partial-close volume rounds below the broker minimum are skipped.
- Basket P/L is the sum over positions in scope — mind your scope settings.
- Execution depends on server conditions; confirm results in the Experts log on critical actions.

See `setup-en.md` and `faq-en.md`.
