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

## Why VRP is a real edge, not a market-timing bet

VRP isn't just a screening heuristic — it's the tradeable expression of a
well-documented market anomaly: **implied volatility systematically
overstates subsequently realized volatility.** Options, on average, are
priced richer than the moves that actually follow, and that gap is a
structural premium collected by whoever is short the option (covered calls,
cash-secured puts, credit spreads).

The landmark empirical study is:

> Bakshi, G., & Kapadia, N. (2003). *Delta-Hedged Gains and the Negative
> Market Volatility Risk Premium.* The Review of Financial Studies, 16(2),
> 527–566.

Using delta-hedged option portfolios on the S&P 500, Bakshi and Kapadia
showed the market volatility risk premium is negative and statistically
significant — option sellers earned consistent gains that can only be
explained by implied volatility running ahead of realized volatility, not by
directional market risk. Carr, P., & Wu, L. (2009), *Variance Risk
Premiums*, The Review of Financial Studies, 22(3), 1311–1341, corroborated
this across the S&P 500 and individual equities using variance swap
replication.

The economic explanation is crash/tail-risk aversion: option buyers pay for
downside insurance, which structurally inflates implied volatility above
what subsequently realized. That's why the premium persists rather than
arbitraging away — it's compensation for underwriting a risk most
participants prefer to pay to avoid, not a pricing inefficiency. This is the
premise this tool operationalizes: rank tickers (or SPY's term structure) by
how wide that IV-over-RV gap currently is, and surface where the premium on
offer is richest.

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

# Append a dated SPY snapshot for later validation
python3 vrp_scan.py --spy --record

# After one or more selected expiries have passed, calculate forward realised volatility
python3 validate_vrp.py
```

## Output

For each ticker: spot price, implied volatility (%), realized volatility
 (%), VRP (percentage points), and a practical screening signal. The signal is
based only on the measured IV-minus-RV gap; it is not an academic VRP
classification or a complete trade recommendation.

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

## Validate SPY term-structure forecasts

`--record` appends one row per tenor to `vrp_history.csv`, including the exact
expiry, ATM put IV, trailing realised volatility, and curve shape observed at
the time of the scan. Use it once per trading day or once per week, at a
consistent time:

```bash
python3 vrp_scan.py --spy --record
```

Once an expiry has passed, generate the report:

```bash
python3 validate_vrp.py --history vrp_history.csv --output vrp_validation_report.md
```

The report compares snapshot IV against **forward realised volatility** from
the captured spot through the selected expiry. It shows the average realised
gap, how often IV exceeded subsequent realised volatility, whether bigger
forecast VRPs corresponded to bigger realised gaps, and the front-tenor
outcome for contango versus backwardation snapshots. This validates the
forecasting signal; it does not model option bid/ask spreads, skew, fees, or
tail losses, so it is not a trading-performance backtest.
