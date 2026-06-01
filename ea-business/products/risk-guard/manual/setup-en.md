# RiskGuard — Setup Guide (English)

## 1. Install
1. Put `RiskGuard.ex5` (compiled) into `MQL5/Experts/` of your MT5 data folder.
   - If you received source: place `RiskGuard.mq5` and `LicenseClient.mqh` in the same folder, open `RiskGuard.mq5` in MetaEditor and **compile with F7**.
2. Restart MT5 or refresh the Navigator.
3. Drag `RiskGuard` onto any chart.

## 2. Allow algo trading
- Toggle **Algo Trading** ON in the toolbar.
- In the EA attach dialog, tick **Allow Algo Trading**.

## 3. (Self-hosted build only) License setup
WebRequest needs the license host whitelisted:
1. Open **Tools > Options > Expert Advisors**.
2. Tick **Allow WebRequest for listed URL**.
3. Add the license server URL (e.g. `https://license.example.com`).
4. Set the EA inputs `InpLicenseKey` (your purchase key) and `InpLicenseServer` (the verify URL).

> Not required for the MQL5 Market build (platform handles licensing).

## 4. Verify
- The top-left label should read `RiskGuard | <symbol> | risk x.xx% | lot x.xx | <status>`.
- Status should be `Licensed` or `Market licensed`.
- On license failure, a message is shown and the trade buttons are disabled.

## 5. Suggested starting values (example)
- `InpRiskPercent = 1.0`, `InpStopLossPips = 200`, `InpRiskReward = 1.5`
- Test on a **demo account** first to confirm sizing, SL/TP and trailing behaviour.
