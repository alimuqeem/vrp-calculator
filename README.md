# VRP Calculator

A small script that scans tickers for **Volatility Risk Premium (VRP)** —
the gap between what the options market is pricing in (implied volatility)
and what the stock has actually been doing (realized volatility).

```
VRP = ATM Implied Volatility − 30-day Realized Volatility
```

A positive VRP means options are priced richer than recent realized moves
justify — the setup premium sellers (covered calls, cash-secured puts,
credit spreads) look for. A negative VRP means the opposite: options are
cheap relative to how much the stock is actually moving.

No broker account, API key, or login required — everything comes from
[yfinance](https://github.com/ranaroussi/yfinance).

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Scan the built-in 40-ticker universe (indices, mega-caps, high-vol growth, etc.)
python3 vrp_scan.py

# Scan specific tickers
python3 vrp_scan.py AAPL MSFT NVDA

# Only show the top 5 by VRP
python3 vrp_scan.py --top 5

# Multi-tenor VRP term structure for SPY (single command, no ticker list needed)
python3 vrp_scan.py --spy
```

## Output

For each ticker: spot price, implied volatility (%), realized volatility
(%), VRP (percentage points), and a signal:

| Signal | VRP |
|---|---|
| STRONG SELL | > 10 |
| SELL | 5 – 10 |
| NEUTRAL | 0 – 5 |
| AVOID | < 0 |

```
Rank  Ticker    Spot     IV%    RV%     VRP  Signal
------------------------------------------------------
   1  XYZ      123.45   45.2   28.1    +17.1  STRONG SELL
   2  ABC       67.89   30.0   24.5     +5.5  SELL
```

## SPY mode (`--spy`)

Instead of scanning many tickers at one point in the term structure, `--spy`
scans one ticker (SPY) at four points in the term structure — **tenors**:

| Tenor | Target DTE |
|---|---|
| 7d | ~1 week |
| 15d | ~2 weeks |
| 30d | ~1 month |
| 45d | ~6 weeks |

For each tenor, IV is read from the options expiry closest to that DTE, and
realized volatility is computed over a **matching lookback window** (e.g.
7-day IV is compared against 7-day RV, not the usual 30-day RV). This gives
a like-for-like VRP reading at each horizon and a view of the term
structure's shape:

- **Contango** (IV rises from 7d → 45d): normal regime, no acute near-term
  event priced in.
- **Backwardation** (IV falls from 7d → 45d): front-tenor stress — the
  market is pricing a near-term event or elevated risk.

This is meant as a quick read on the broad market's volatility regime
without having to scan individual names.

```
--- SPY MULTI-TENOR VRP — 2026-08-07 ---
Spot: 645.32

Tenor  Expiry        DTE    IV%    RV%     VRP  Signal
--------------------------------------------------------
  7d   2026-08-14      7   11.2%   9.8%    +1.4  NEUTRAL
 15d   2026-08-21     14   12.0%  10.5%    +1.5  NEUTRAL
 30d   2026-09-05     29   13.1%  11.0%    +2.1  NEUTRAL
 45d   2026-09-19     43   13.8%  11.5%    +2.3  NEUTRAL

Term structure: contango (IV rising from front to back tenor) — normal regime, no acute near-term event priced in.
```

## Notes

- Implied volatility is taken from the nearest options expiry that's at
  least 25 days out, at the strike closest to the current spot price.
- Realized volatility is annualized from 30 days of daily log returns.
- yfinance occasionally rate-limits — if a scan comes back empty, wait a
  bit and try again.
- This is a research/screening tool, not trading advice.
