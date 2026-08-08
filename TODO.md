# VRP Calculator roadmap

This is a research and screening tool. A positive measured VRP is not, by
itself, evidence that a short-option strategy will be profitable: skew, jump
risk, bid/ask spreads, fees, hedging, sizing, and tail losses all matter.

## 1. Establish a reliable research baseline

- [ ] **Finish and use the SPY forecast-validation workflow.**
  Record `python3 vrp_scan.py --spy --record` on a consistent schedule, then
  run `validate_vrp.py` after the relevant expiries. Collect enough completed
  observations before drawing conclusions; report the number of samples next
  to every metric.

- [ ] **Make validation statistically more robust.**
  Add command-line options for a start/end date, tenor, and a
  non-overlapping-observations mode. Include confidence intervals or bootstrap
  intervals for mean realised VRP, a benchmark comparison (for example,
  forecast IV versus trailing-RV forecast), and breakdowns by tenor and
  signal. Do not interpret correlations from very small samples.

- [ ] **Validate by market regime.**
  Persist simple context at snapshot time—SPY return, trailing SPY volatility,
  and optionally VIX when available—and report results for quiet versus
  stressed regimes. This tests whether the signal works only in a particular
  volatility environment.

- [ ] **Avoid treating overlapping measurements as independent.**
  Snapshots taken daily for 30- or 45-day expiries share most of the same
  forward returns. Default the research report to either non-overlapping
  observations or clearly label overlapping rows and calculate both views.

## 2. Improve option-chain data quality

- [ ] **Estimate ATM IV from both calls and puts.**
  Replace the put-only `atm_iv_for_expiry` path with a helper that identifies
  ATM call and put contracts, reads each IV, and returns a liquidity-weighted
  average when both are usable. Fall back to one side only when the other is
  unavailable, recording which side was used.

- [ ] **Add option-liquidity and quote-quality filters.**
  For each candidate contract, capture bid, ask, last price, volume, open
  interest, and quote timestamp where yfinance provides them. Reject or flag
  zero/invalid IV, missing bid/ask, very wide relative spreads, and contracts
  below configurable minimum volume/open-interest thresholds. Return a clear
  skip reason instead of silently dropping the ticker.

- [ ] **Check price/option timestamp consistency.**
  The history close and the option chain may represent different points in
  time. Capture the available timestamps and mark delayed or stale data. Use
  the option-chain underlying price when trustworthy; otherwise report that
  spot and IV may not be synchronized.

- [ ] **Make expiry selection explicit and configurable.**
  Add `--target-dte`, `--min-dte`, and `--max-dte` for the regular scan, and
  `--tenors 7,15,30,45` for term structure. Print the selected expiry and DTE
  in normal scan output so results can be reproduced and audited.

- [ ] **Use consistent trading-day conventions.**
  Calendar DTE and the number of daily close-to-close returns are currently
  different units. Convert the selected expiry's calendar DTE to an expected
  number of trading days (or make the convention an explicit option), and use
  that same horizon when computing realised-volatility comparators.

## 3. Build a better VRP signal

- [ ] **Offer multiple realised-volatility estimates.**
  Preserve the current rolling standard deviation as the baseline, then add
  EWMA volatility with a configurable decay factor. Present trailing 30-day,
  tenor-matched, and EWMA results side by side. Keep more complex forecasting
  methods optional until they are validated against the baseline.

- [ ] **Add optional forward-volatility forecasts.**
  Implement a simple forecast interface (for example, EWMA first, then an
  optional GARCH implementation). Compare IV with forecast volatility rather
  than only trailing volatility, and save the forecast method and parameters
  in every output/history row for reproducibility.

- [ ] **Normalize comparisons across tickers.**
  In addition to raw `IV - RV` percentage points, calculate `IV / RV`, the
  variance premium `IV^2 - RV^2`, and each ticker's historical VRP percentile
  or z-score. Build a documented composite rank only after backtesting each
  component; retain raw metrics in output so ranking decisions are visible.

- [ ] **Replace fixed trading labels with evidence-based labels.**
  `STRONG SELL`, `SELL`, and `AVOID` imply a strategy recommendation. Rename
  them to neutral research labels (for example, `HIGH_VRP`, `MID_VRP`,
  `LOW_VRP`) or make thresholds configurable. Calibrate any thresholds from
  the validation dataset and show their sample support in the report.

## 4. Account for known event risk and tradability

- [ ] **Flag earnings risk.**
  Retrieve the next earnings date where available, determine whether it falls
  before the selected expiry, and include an `earnings_before_expiry` field.
  Add `--exclude-earnings` to omit those contracts and a default visible
  warning when an expiry spans earnings. Treat unavailable earnings data as
  unknown, not safe.

- [ ] **Add a tradability score.**
  Combine relative bid/ask spread, volume, open interest, and option price
  into a transparent pass/flag score. Keep this distinct from the VRP rank:
  a high theoretical premium with poor liquidity should be visible but not
  presented as equally actionable.

- [ ] **Represent skew rather than a single ATM point.**
  Capture a small set of delta- or moneyness-based strikes (for example,
  25-delta put, ATM, and 25-delta call) when data permits. Report put/call
  skew and use it to identify whether an apparent premium is concentrated in
  downside crash insurance.

- [ ] **Separate research signal from strategy economics.**
  If the project later models covered calls, cash-secured puts, or spreads,
  make each a separate module with assumptions for entry price, bid/ask,
  commissions, assignment, delta, position size, and tail scenarios. Do not
  infer strategy P&L directly from a positive VRP reading.

## 5. Make the scanner usable as a repeatable tool

- [ ] **Add structured output.**
  Support `--format table|csv|json` and `--output FILE`. Include all source
  fields: scan timestamp, ticker, selected expiry/DTE, spot, IV source,
  liquidity metrics, RV method, normalized metrics, event flags, and errors.
  Keep human-readable table output as the default.

- [ ] **Persist normal-scan history.**
  Extend recording beyond SPY to the ordinary ticker universe. Use a stable
  schema with a schema-version column; append one observation per ticker and
  expiry so historical percentiles and later validation are possible.

- [ ] **Improve failure reporting and retries.**
  Replace broad `except Exception` blocks with logged, per-ticker error
  categories such as no price history, no expiries, invalid chain, rate limit,
  and liquidity rejection. Add bounded retries with exponential backoff for
  transient yfinance failures, but never retry indefinitely.

- [ ] **Speed up safely.**
  Fetch independent ticker data with a small configurable worker pool after
  the sequential implementation is fully tested. Preserve deterministic
  output ordering, rate-limit retries, and a conservative default concurrency
  so the data provider is not overloaded.

- [ ] **Add configuration instead of hard-coded assumptions.**
  Support a checked-in example YAML/TOML configuration for universe, DTE
  targets, liquidity thresholds, RV windows, signal cutoffs, output format,
  and retry settings. CLI options should override config values, and the
  effective configuration should be recorded in structured output.

## 6. Test, document, and publish responsibly

- [ ] **Increase deterministic test coverage.**
  Add fixtures for option chains, missing/stale quotes, call/put fallback,
  expiry selection, trading-day conversion, event flags, output serialization,
  and validation edge cases. Unit tests must not require live Yahoo Finance
  data; keep any live smoke test opt-in.

- [ ] **Document data limitations and assumptions.**
  Explain Yahoo Finance delays/coverage gaps, how ATM is chosen, annualization
  assumptions, calendar-versus-trading-day choices, event data limitations,
  and how skips are handled. Include a concise explanation of why a forecast
  gap is not a guaranteed option-selling return.

- [ ] **Add reproducible research artifacts.**
  Provide a sample configuration, anonymized/synthetic fixture data, a command
  sequence for collecting snapshots and producing a report, and a short
  methodology document. Version the data schema and report methodology when
  either changes.

## Suggested delivery order

1. Finish validation, sample collection, and robust reporting.
2. Implement call/put ATM IV, quote-quality guards, expiry visibility, and
   precise skip reasons.
3. Add trading-day consistency, earnings flags, structured output, and normal
   scan history.
4. Add normalized metrics and evaluate them using collected data.
5. Introduce forward-volatility forecasts, skew, and strategy-economics
   modules only once the simpler signal has a sufficient validation record.

## Why these improvements matter

| Improvement | Why | Expected benefit |
|---|---|---|
| Finish SPY validation and collect observations | A hypothesis cannot be trusted from a single live snapshot or a handful of expiries. | Creates the evidence base for deciding which signals deserve further work. |
| Robust validation statistics | Small and overlapping samples can make random outcomes look meaningful. | Produces more honest, reproducible conclusions and prevents false confidence. |
| Regime-based validation | The relationship between implied and realised volatility can change materially in quiet and stressed markets. | Identifies where the signal is reliable and where it should be treated cautiously. |
| Non-overlapping observation handling | Daily snapshots of the same future period reuse many of the same returns. | Prevents inflated sample sizes and misleading statistical significance. |
| Call-and-put ATM IV | A single put can be stale or affected by downside skew. | Gives a more representative and resilient estimate of the market's ATM implied volatility. |
| Liquidity and quote-quality filters | A theoretical IV is not actionable when quotes are missing, stale, or prohibitively wide. | Removes misleading candidates and makes results closer to what could actually be traded. |
| Price/option timestamp checks | Spot and option data captured at different moments can create a false ATM selection or VRP. | Improves data integrity and makes stale inputs visible to the user. |
| Configurable, visible expiry selection | A hard-coded expiry rule hides an important modelling choice. | Makes scans reproducible and lets users evaluate the horizon that matches their research question. |
| Consistent trading-day conventions | Calendar DTE and daily return windows do not describe the same length of time. | Ensures IV and RV are compared on like-for-like horizons. |
| Multiple RV estimates | Recent historical volatility is only one imperfect forecast of future volatility. | Shows whether a reading is robust to reasonable volatility-estimation choices. |
| Forward-volatility forecasts | Option prices reflect expected future risk, while trailing RV only describes the past. | Makes the core comparison more economically relevant and potentially more predictive. |
| Cross-ticker normalization | Raw IV-minus-RV points are not directly comparable between low- and high-volatility stocks. | Produces fairer rankings and highlights unusually rich premiums relative to a ticker's own history. |
| Neutral, evidence-based labels | `SELL` labels can be mistaken for a complete trading recommendation. | Keeps the tool aligned with research use and ties classifications to validated evidence. |
| Earnings-risk flags | A large premium before earnings often compensates for a known, discontinuous price move. | Separates ordinary VRP from event risk and avoids misleading rankings. |
| Tradability score | A high signal and practical ability to enter/exit the position are separate questions. | Helps users distinguish attractive research observations from candidates with usable market depth. |
| Skew measurements | Downside insurance can dominate a put-based IV reading. | Explains the composition of the premium and improves tail-risk awareness. |
| Separate strategy-economics modules | VRP is not strategy P&L; different positions have different payoffs and frictions. | Prevents overclaiming and enables later backtests with explicit, testable assumptions. |
| CSV/JSON output | Terminal tables are difficult to store, compare, chart, or consume in other tools. | Enables automation, analysis notebooks, dashboards, and auditability. |
| Normal-scan history | Historical percentiles and future validation require dated observations. | Turns one-off scans into a growing research dataset. |
| Specific errors and bounded retries | Silent broad failures make missing results impossible to diagnose. | Improves reliability, user trust, and troubleshooting without hammering the data source. |
| Safe concurrency | Sequential remote calls make broader scans slow, but unbounded concurrency causes rate limits. | Reduces scan time while preserving provider-friendly behaviour and deterministic output. |
| Configuration support | Research assumptions should not require editing source code. | Makes experiments repeatable, reviewable, and easier to share. |
| Deterministic tests | Live market-data tests are intermittent and cannot cover important failure states consistently. | Allows safe refactoring and catches regressions before release. |
| Documentation and reproducible artifacts | Users need to know both the model assumptions and its data limitations. | Makes outputs interpretable, facilitates independent reproduction, and sets appropriate expectations. |
