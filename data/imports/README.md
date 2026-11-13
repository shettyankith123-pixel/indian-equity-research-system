# Data imports

## 2026-11-13 INDmoney holdings snapshot
Seven live equity positions were read from the user's connected INDmoney account. These are opening-position snapshots containing quantity, average cost, invested value, current value and unrealised P&L. They are **not** reconstructed transaction history. Purchase dates, individual buy/sell fills, fees and taxes were not exposed by the connected holdings endpoint and are deliberately not fabricated.

Snapshot totals: invested ₹19,975.38; market value ₹20,165.00; unrealised P&L ₹189.62.

## 2026-11-13 NSE watchlist quotes
All 64 watchlist symbols were retrieved through the connected NSE historical data service, including price and volume, dated 2026-11-13. This connector snapshot is stored separately from the official raw NSE UDiFF EOD archive that the scheduled GitHub Action downloads. Do not label this file as the raw bhavcopy or as the official exchange close without checking the source timestamp and reconciliation.
\n## INDmoney market snapshot — 2026-11-13\n\nA 64-symbol market snapshot from the connected INDmoney details service. Includes latest price timestamps, market cap, traded volume, 52-week range and sell-side consensus where available. Analyst targets and consensus are context only; they are not used as intrinsic fair value or as a BUY trigger.\n