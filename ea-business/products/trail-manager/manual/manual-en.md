# TrailManager — User Manual (English)

**Version:** 1.00 · **Platform:** MetaTrader 5 · **Type:** EA (position-management utility)

---

## ⚠️ Risk Disclosure / Disclaimer
Trading leveraged products carries a high level of risk and can result in losses exceeding your deposit. TrailManager is a **utility that manages stop-loss orders (break-even and trailing) on existing positions**. It does not open trades, generate signals, or predict markets. It provides **no guarantee of profit. Past performance does not guarantee future results.** Use at your own risk.

---

## 1. What TrailManager is
Attach it to a chart and it applies break-even and a trailing stop to positions **you (or any other tool / EA / manual order) already opened**. It never opens new trades — stop management only.

### Three trailing modes
| Mode | Behaviour |
|---|---|
| **FIXED** | Trail at a fixed pip distance once in profit |
| **ATR** | Trail at ATR × multiplier (volatility-adaptive) |
| **STEP** | Move the SL only in discrete steps (reduces broker modify spam) |

### Also
- **Break-even**: move SL to entry (+lock) after a profit threshold
- **Initial SL** (optional): set an SL on positions that have none
- **Scope filters**: current symbol only, and/or match a magic number
- **Pause/Resume** toggle on the panel

---

## 2. Inputs

### Scope
| Input | Description |
|---|---|
| `InpCurrentSymbolOnly` | Manage the current chart symbol only |
| `InpFilterByMagic` | Only manage positions with the given magic |
| `InpMagic` | Magic to match (when filtering) |

### Break-even
| Input | Description |
|---|---|
| `InpUseBreakEven` | Enable break-even |
| `InpBreakEvenPips` | Profit (pips) to trigger break-even |
| `InpBreakEvenLock` | Profit (pips) locked at break-even |

### Trailing
| Input | Description |
|---|---|
| `InpTrailMode` | FIXED / ATR / STEP |
| `InpTrailStartPips` | Profit (pips) before trailing starts |
| `InpTrailDistancePips` | FIXED/STEP trailing distance (pips) |
| `InpTrailStepPips` | STEP: minimum SL advance per move (pips) |
| `InpATRPeriod` | ATR period |
| `InpATRMultiplier` | ATR distance multiplier |
| `InpATRTF` | ATR timeframe |

### Optional initial protection
| Input | Description |
|---|---|
| `InpSetSLIfMissing` | Set an initial SL on positions that have none |
| `InpInitialSLPips` | Initial SL distance (pips) |

### Execution / Licensing
| Input | Description |
|---|---|
| `InpSlippagePts` | Max deviation (points) |
| `InpLicenseKey` / `InpLicenseServer` | Self-hosted build only |

> Not required for the MQL5 Market build.

---

## 3. How to use
1. Set scope and mode (FIXED/ATR/STEP).
2. Drag onto a chart — existing positions are managed automatically.
3. Trailing starts at `InpTrailStartPips`; break-even fires at `InpBreakEvenPips`.
4. Use **PAUSE/RESUME** on the panel to stop/start management.

---

## 4. Notes
- The SL only moves in the **favourable** direction (never against you).
- In ATR mode, if the ATR handle fails the distance is 0 (no trailing) — check period/timeframe.
- If another EA also manages the same position's SL, they may conflict; use scope filters to separate.
- Test on a demo account first.

See `setup-en.md` and `faq-en.md`.
