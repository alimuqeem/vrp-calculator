#!/usr/bin/env python3
"""Validate recorded VRP snapshots once their selected option expiry has passed."""
import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf


def forward_realized_vol(symbol, observation_date, expiry, spot):
    """Annualised close-to-close volatility from the recorded spot through expiry."""
    observation_date = pd.to_datetime(observation_date).date()
    expiry = pd.to_datetime(expiry).date()
    history = yf.Ticker(symbol).history(
        start=observation_date.isoformat(),
        end=(expiry + timedelta(days=1)).isoformat(),
    )
    if history.empty:
        return None, 0

    closes = history["Close"].dropna()
    closes = closes[[index.date() > observation_date for index in closes.index]]
    prices = pd.Series([float(spot), *closes.astype(float).tolist()])
    log_returns = np.log(prices / prices.shift(1)).dropna()
    if len(log_returns) < 2:
        return None, len(log_returns)
    return float(log_returns.std() * np.sqrt(252) * 100), len(log_returns)


def completed_observations(history):
    today = date.today()
    completed = []
    for row in history.to_dict("records"):
        if pd.to_datetime(row["expiry"]).date() > today:
            continue
        forward_rv, trading_days = forward_realized_vol(
            row["symbol"], row["observation_date"], row["expiry"], row["spot"]
        )
        if forward_rv is None:
            continue
        row["forward_rv_pct"] = forward_rv
        row["trading_days"] = trading_days
        row["realized_vrp_pct"] = float(row["iv_pct"]) - forward_rv
        completed.append(row)
    return pd.DataFrame(completed)


def markdown_report(results, history_path):
    if results.empty:
        return (
            "# VRP Validation Report\n\n"
            f"No completed observations in `{history_path}` yet. "
            "Run `vrp_scan.py --spy --record` regularly and re-run this report after an expiry.\n"
        )

    positive = (results["realized_vrp_pct"] > 0).mean() * 100
    correlation = results["vrp_pct"].corr(results["realized_vrp_pct"])
    lines = [
        "# VRP Validation Report",
        "",
        f"Source: `{history_path}`",
        "",
        "## Overall",
        "",
        "| Completed observations | Mean IV − forward RV | Median IV − forward RV | Positive observations | Correlation: forecast VRP vs realised gap |",
        "|---:|---:|---:|---:|---:|",
        f"| {len(results)} | {results['realized_vrp_pct'].mean():+.2f} pp | {results['realized_vrp_pct'].median():+.2f} pp | {positive:.1f}% | {correlation:.2f} |",
        "",
        "A positive realised gap means the snapshot IV exceeded volatility actually realised before expiry. The correlation tests whether a larger forecast VRP coincided with a larger realised gap.",
        "",
        "## By signal",
        "",
        "| Signal | Samples | Mean IV − forward RV | Positive observations |",
        "|---|---:|---:|---:|",
    ]
    for signal, group in results.groupby("signal", sort=False):
        lines.append(
            f"| {signal} | {len(group)} | {group['realized_vrp_pct'].mean():+.2f} pp | "
            f"{(group['realized_vrp_pct'] > 0).mean() * 100:.1f}% |"
        )

    front = results.loc[results.groupby("captured_at")["tenor_days"].idxmin()]
    if len(front) > 1:
        lines.extend([
            "",
            "## Front-tenor outcome by curve shape",
            "",
            "| Curve shape | Samples | Mean forward RV |",
            "|---|---:|---:|",
        ])
        for shape, group in front.groupby("curve_shape", sort=False):
            lines.append(f"| {shape} | {len(group)} | {group['forward_rv_pct'].mean():.2f}% |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Validate recorded SPY VRP observations at expiry.")
    parser.add_argument("--history", default="vrp_history.csv", help="Snapshot CSV from vrp_scan.py --record")
    parser.add_argument("--output", default="vrp_validation_report.md", help="Markdown report path")
    args = parser.parse_args()

    history_path = Path(args.history)
    if not history_path.exists():
        parser.error(f"history file not found: {history_path}")
    history = pd.read_csv(history_path)
    required = {"observation_date", "symbol", "expiry", "spot", "iv_pct", "vrp_pct", "signal", "curve_shape", "captured_at", "tenor_days"}
    missing = required - set(history.columns)
    if missing:
        parser.error(f"history file is missing columns: {', '.join(sorted(missing))}")

    report = markdown_report(completed_observations(history), history_path)
    Path(args.output).write_text(report, encoding="utf-8")
    print(report, end="")
    print(f"Saved report to {args.output}")


if __name__ == "__main__":
    main()
