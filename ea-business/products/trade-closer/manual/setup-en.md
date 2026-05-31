# TradeCloser — Setup Guide (English)

## 1. Install
1. Put `TradeCloser.ex5` into `MQL5/Experts/` (or open `TradeCloser.mq5` in MetaEditor and **compile with F7**).
   - It references RiskGuard's `LicenseClient.mqh`. When building from source, keep
     `products/risk-guard/src/LicenseClient.mqh` at the relative path, or copy it next to the .mq5.
2. Restart MT5 or refresh the Navigator.
3. Drag it onto any chart.

## 2. Allow algo trading
- Toggle **Algo Trading** ON in the toolbar.
- Tick **Allow Algo Trading** in the attach dialog.

## 3. (Self-hosted build only) License setup
1. Tools > Options > Expert Advisors > tick **Allow WebRequest for listed URL**.
2. Add the license URL (e.g. `https://api.riskguard.app`).
3. Set `InpLicenseKey` and `InpLicenseServer`.

> Not required for the MQL5 Market build.

## 4. Verify
- The panel (CLOSE ALL / SYMBOL / WINNERS / LOSERS / CLOSE % / DEL PENDINGS / PANIC) is shown.
- The info label shows `scope` and `basket P/L`, status `Licensed` / `Market licensed`.
- Test buttons and basket auto-close on a **demo account** first.
