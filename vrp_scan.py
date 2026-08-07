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
    python3 vrp_scan.py --spy                   # SPY multi-tenor VRP term structure

SPY mode (--spy):
    Computes VRP separately at four tenors (7d/15d/30d/45d) for SPY, with
    each tenor's realized volatility measured over a matching lookback
    window (e.g. 7-day IV vs 7-day RV). This gives a quick, single-name
    read on the broad market's vol term structure without scanning
    individual names.

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


def atm_iv_for_expiry(ticker: yf.Ticker, expiry: str, spot: float):
    """ATM implied vol at a specific expiry, from the strike closest to spot."""
    chain = ticker.option_chain(expiry).puts
    if chain.empty:
        return None

    chain = chain.assign(dist=(chain["strike"] - spot).abs())
    atm_row = chain.sort_values("dist").iloc[0]
    iv = atm_row.get("impliedVolatility")
    return float(iv) if pd.notna(iv) else None


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

    return atm_iv_for_expiry(ticker, target_exp, spot)


def nearest_expiry(expiries, target_days: int, today):
    """Expiry whose DTE is closest to target_days (ties go to the earlier expiry)."""
    best = None
    for exp in expiries:
        dte = (pd.to_datetime(exp).date() - today).days
        if dte <= 0:
            continue
        if best is None or abs(dte - target_days) < abs(best[1] - target_days):
            best = (exp, dte)
    return best


TENORS = [7, 15, 30, 45]


def scan_spy_term_structure(symbol: str = "SPY"):
    """Multi-tenor VRP for a single symbol: IV and RV both measured at each tenor."""
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="90d")
        if hist.empty:
            return None, []
        spot = float(hist["Close"].dropna().iloc[-1])

        expiries = t.options
        if not expiries:
            return spot, []

        today = datetime.now(timezone.utc).date()
        rows = []
        for tenor in TENORS:
            match = nearest_expiry(expiries, tenor, today)
            if match is None:
                continue
            expiry, dte = match
            iv = atm_iv_for_expiry(t, expiry, spot)
            rv = get_realized_vol(hist, window=tenor)
            if iv is None or rv is None:
                continue
            vrp_pts = round((iv - rv) * 100, 2)
            rows.append({
                "tenor": tenor,
                "expiry": expiry,
                "dte": dte,
                "iv_pct": round(iv * 100, 1),
                "rv_pct": round(rv * 100, 1),
                "vrp": vrp_pts,
                "signal": signal(vrp_pts),
            })
        return spot, rows
    except Exception:
        return None, []


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


def print_spy_term_structure(symbol: str = "SPY"):
    print(f"--- {symbol} MULTI-TENOR VRP — {datetime.now().date()} ---")
    spot, rows = scan_spy_term_structure(symbol)
    if spot is None:
        print("No data returned — check ticker or network connection.")
        sys.exit(1)
    print(f"Spot: {spot:.2f}")

    if not rows:
        print("No tenor data returned — check options chain availability.")
        sys.exit(1)

    hdr = f"\n{'Tenor':>5}  {'Expiry':<10}  {'DTE':>4}  {'IV%':>6}  {'RV%':>6}  {'VRP':>6}  {'Signal'}"
    print(hdr)
    print("-" * (len(hdr) - 1))
    for row in rows:
        print(f"{row['tenor']:>4}d  {row['expiry']:<10}  {row['dte']:>4}  "
              f"{row['iv_pct']:>5.1f}%  {row['rv_pct']:>5.1f}%  "
              f"{row['vrp']:>+6.1f}  {row['signal']}")

    if len(rows) >= 2:
        front, back = rows[0], rows[-1]
        if back["iv_pct"] > front["iv_pct"]:
            shape = "contango (IV rising from front to back tenor) — normal regime, no acute near-term event priced in"
        elif back["iv_pct"] < front["iv_pct"]:
            shape = "backwardation (IV falling from front to back tenor) — front-tenor stress, market pricing a near-term event or elevated risk"
        else:
            shape = "flat — front and back tenor IV roughly equal"
        print(f"\nTerm structure: {shape}.")


def main():
    parser = argparse.ArgumentParser(description="Volatility Risk Premium scanner")
    parser.add_argument("tickers", nargs="*", help="Tickers to scan (default: built-in 40-name universe)")
    parser.add_argument("--top", type=int, default=None, help="Only show the top N results by VRP")
    parser.add_argument("--spy", action="store_true", help="Multi-tenor (7d/15d/30d/45d) VRP term structure for SPY")
    args = parser.parse_args()

    if args.spy:
        print_spy_term_structure()
        return

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
