#!/usr/bin/env python3
"""
vrp_scan.py — Volatility Risk Premium (VRP) scanner.

Standalone, no broker account or API key required. Uses yfinance for both
the options chain (implied volatility) and price history (realized
volatility), so it runs anywhere with a plain internet connection.

VRP = ATM Implied Volatility (nearest expiry, ~25+ DTE) minus 30-day
Realized Volatility, expressed in percentage points. A positive VRP means
the options market is pricing in more movement than the stock has actually
been making — the classic setup for selling premium (covered calls,
cash-secured puts, credit spreads).

Setup:
    pip install yfinance pandas numpy

Usage:
    python3 vrp_scan.py                        # scan the built-in 40-ticker universe
    python3 vrp_scan.py AAPL MSFT NVDA          # scan just these tickers
    python3 vrp_scan.py --top 5                 # show only the top N by VRP

Signals:
    STRONG SELL   VRP > 10
    SELL          VRP  5-10
    NEUTRAL       VRP  0-5
    AVOID         VRP < 0
"""
import argparse
import math
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yfinance as yf

DEFAULT_UNIVERSE = [
    # Indices & ETFs
    "SPY", "QQQ", "IWM", "GLD", "TLT", "XLE", "XLK", "XLF",
    # Mega-cap tech
    "AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "TSLA",
    # High-vol growth
    "NFLX", "AMD", "PYPL", "PLTR", "SOFI", "HIMS",
    "COIN", "HOOD", "UBER", "SHOP", "SQ", "SNAP", "ROKU",
    # Cybersecurity / cloud
    "CRWD", "PANW", "SNOW", "NET",
    # Crypto proxies / high-beta
    "MSTR", "MARA", "RIOT",
    # International / sector
    "BABA", "NIO", "RKLB", "SMCI",
    "ABNB", "DKNG",
]


def get_realized_vol(hist: pd.DataFrame, window: int = 30):
    """Annualized realized volatility from daily log returns."""
    if hist is None or len(hist) < window:
        return None
    log_returns = np.log(hist["Close"] / hist["Close"].shift(1)).dropna()
    std_dev = log_returns.tail(window).std()
    return float(std_dev) * math.sqrt(252)


def get_atm_iv(ticker: yf.Ticker, spot: float):
    """ATM implied vol from the nearest expiry that is at least 25 days out."""
    expiries = ticker.options
    if not expiries:
        return None

    today = datetime.now(timezone.utc).date()
    target_exp = expiries[0]
    for exp in expiries:
        dte = (pd.to_datetime(exp).date() - today).days
        if dte >= 25:
            target_exp = exp
            break

    chain = ticker.option_chain(target_exp).puts
    if chain.empty:
        return None

    chain = chain.assign(dist=(chain["strike"] - spot).abs())
    atm_row = chain.sort_values("dist").iloc[0]
    iv = atm_row.get("impliedVolatility")
    return float(iv) if pd.notna(iv) else None


def signal(vrp: float) -> str:
    if vrp > 10:
        return "STRONG SELL"
    if vrp > 5:
        return "SELL"
    if vrp >= 0:
        return "NEUTRAL"
    return "AVOID"


def scan_ticker(symbol: str):
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="60d")
        if hist.empty:
            return None
        spot = float(hist["Close"].dropna().iloc[-1])

        rv = get_realized_vol(hist, window=30)
        iv = get_atm_iv(t, spot)
        if rv is None or iv is None:
            return None

        vrp_pts = round((iv - rv) * 100, 2)
        return {
            "ticker": symbol,
            "spot": round(spot, 2),
            "iv_pct": round(iv * 100, 1),
            "rv_pct": round(rv * 100, 1),
            "vrp": vrp_pts,
            "signal": signal(vrp_pts),
        }
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Volatility Risk Premium scanner")
    parser.add_argument("tickers", nargs="*", help="Tickers to scan (default: built-in 40-name universe)")
    parser.add_argument("--top", type=int, default=None, help="Only show the top N results by VRP")
    args = parser.parse_args()

    universe = [t.upper() for t in args.tickers] if args.tickers else DEFAULT_UNIVERSE

    print(f"--- VRP SCAN — {datetime.now().date()} ---")
    print(f"Universe: {len(universe)} tickers\nScanning ", end="", flush=True)

    results, errors = [], []
    for symbol in universe:
        print(".", end="", flush=True)
        row = scan_ticker(symbol)
        (results if row else errors).append(row or symbol)
    print()

    if errors:
        print(f"Skipped (no data): {', '.join(errors)}")
    if not results:
        print("No results returned — check tickers or network connection.")
        sys.exit(1)

    results.sort(key=lambda x: x["vrp"], reverse=True)
    if args.top:
        results = results[: args.top]

    hdr = f"\n{'Rank':>4}  {'Ticker':<7}  {'Spot':>8}  {'IV%':>6}  {'RV%':>6}  {'VRP':>6}  {'Signal'}"
    print(hdr)
    print("-" * (len(hdr) - 1))
    for i, row in enumerate(results, 1):
        print(f"{i:>4}  {row['ticker']:<7}  {row['spot']:>8.2f}  "
              f"{row['iv_pct']:>5.1f}%  {row['rv_pct']:>5.1f}%  "
              f"{row['vrp']:>+6.1f}  {row['signal']}")

    strong = sum(1 for r in results if r["vrp"] > 10)
    sell = sum(1 for r in results if 5 < r["vrp"] <= 10)
    neutral = sum(1 for r in results if 0 <= r["vrp"] <= 5)
    avoid = sum(1 for r in results if r["vrp"] < 0)
    print(f"\nSummary: STRONG SELL {strong}  SELL {sell}  NEUTRAL {neutral}  AVOID {avoid}")


if __name__ == "__main__":
    main()
