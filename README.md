# Statistical Arbitrage / Pairs Trading

This repo is my implementation of a statistical arbitrage / pairs trading strategy in Python.

The current version focuses on **Visa (`V`) and Mastercard (`MA`)**. The goal is not just to make a backtest that looks profitable, but to build the strategy carefully enough that the results are not driven by obvious look-ahead bias or unrealistic execution assumptions.

At the moment, the project includes rolling hedge-ratio estimation, spread construction, z-score signals, next-open execution, transaction costs, P&L accounting, risk metrics, and trade-level analysis.

> **Status:** work in progress. The current V/MA backtest is a research baseline, not a finished or validated trading strategy.

---

## Strategy Overview

The strategy looks for temporary deviations in the historical relationship between Visa and Mastercard and trades the spread under the assumption that it may mean-revert.

The current baseline uses:

| Parameter | Value |
|---|---:|
| Pair | V / MA |
| Data frequency | Daily |
| OLS lookback | 252 trading days |
| Z-score lookback | 60 trading days |
| Entry threshold | ±2.0 |
| Exit threshold | ±0.5 |
| Gross notional per trade | $10,000 |
| Transaction cost | 5 bps per transaction |
| Execution | Next trading day open |

---

## Methodology

### 1. Rolling hedge ratio

For each day, I estimate the relationship between MA and V using rolling OLS:

```text
MA_t = alpha_t + beta_t * V_t + epsilon_t
```

The regression uses only observations before the current signal date. This avoids estimating historical hedge ratios with future data.

`beta_t` is then used as the share hedge ratio for the pair.

### 2. Spread

The spread is calculated as:

```text
Spread_t = MA_t - (alpha_t + beta_t * V_t)
```

Rather than trading the two stocks independently, the strategy trades deviations in this estimated relationship.

### 3. Z-score

The spread is standardized using a rolling mean and standard deviation:

```text
z_t = (Spread_t - rolling_mean_t) / rolling_std_t
```

The rolling statistics are shifted by one day, so the current spread does not contribute to the historical mean and standard deviation used to evaluate itself.

### 4. Trading rules

The current rules are:

```text
z < -2.0   -> long spread
z > +2.0   -> short spread
|z| < 0.5  -> exit
```

For the current positive hedge ratio:

```text
Long spread  = long MA, short V
Short spread = short MA, long V
```

There is no stop-loss or time-based exit in the baseline yet.

---

## Position Sizing

The strategy allocates a fixed **$10,000 gross notional** to each trade.

For a positive hedge ratio:

```text
q_V = |beta| * q_MA
```

and:

```text
q_MA = Gross Notional / (P_MA + |beta| * P_V)
```

The share quantities are calculated at entry using the hedge ratio associated with the signal.

Once a trade is opened, the shares are kept fixed until exit. The strategy does not rebalance every day as the rolling beta changes.

---

## Execution and P&L

One of the main changes made during development was removing same-close execution.

A signal that depends on the close of day `t` cannot realistically be executed at that same closing price. The current backtest therefore uses:

```text
Close of day t
    -> calculate spread / z-score
    -> generate signal

Open of day t+1
    -> execute entry or exit
```

P&L is split into two parts:

```text
previous close -> current open
current open   -> current close
```

This lets the backtest correctly handle entry days, holding days, and exit days without earning P&L before a position exists or after it has been closed.

I also checked the accounting manually on a complete trade. The sum of daily P&L matched direct entry-to-exit P&L to floating-point precision.

---

## Transaction Costs

The current model charges **5 basis points** on the gross dollar value traded at both entry and exit.

It does not yet model:

- bid-ask spread
- slippage
- short borrow fees
- market impact
- execution latency

Those are later realism checks rather than assumptions hidden inside the current results.

---

## Current Results

Current V/MA development-backtest results:

| Metric | Result |
|---|---:|
| Initial capital / reference capital | $10,000 |
| Net P&L | **$742.28** |
| Transaction costs | **$537.15** |
| Sharpe ratio | **0.173** |
| Maximum drawdown | **-6.46%** |
| Completed trades | **53** |
| Win rate | **67.9%** |
| Average winner | **$77.01** |
| Average loser | **-$119.42** |
| Profit factor | **1.366** |
| Best trade | **$225.11** |
| Worst trade | **-$370.03** |

The Sharpe ratio currently uses daily P&L divided by the fixed initial capital and is annualized with `sqrt(252)`.

These numbers should be treated as **development results**, not out-of-sample evidence of a durable trading edge. Parameter robustness and held-out testing are still to be done.

---

## Trade-Level Analysis

The trade summary exposed an interesting pattern: losing trades tend to remain open much longer than winning trades.

| Holding period | Winners | Losers |
|---|---:|---:|
| Average | **21.4 calendar days** | **49.6 calendar days** |
| Median | **15.5 calendar days** | **52 calendar days** |
| Longest | **69 calendar days** | **82 calendar days** |

This gives a useful hypothesis for later research: if mean reversion does not happen relatively quickly, the probability of a successful trade may deteriorate.

I am not adding a time stop based on this result alone, since doing that directly on the same sample would risk tuning the strategy to historical outcomes.

---

## Statistical Diagnostics

The research script currently includes:

- Augmented Dickey-Fuller testing
- Engle-Granger cointegration testing
- rolling OLS
- rolling spread analysis

The ADF and cointegration tests are currently used as diagnostics rather than as live trading filters.

A later stage of the project will look more carefully at relationship stability, structural breaks, and pair selection.

---

## What Changed During Development

A few early versions of the backtest produced much better-looking performance, but for the wrong reasons.

The most important corrections so far were:

**Full-sample OLS -> rolling OLS**  
The original regression used the entire dataset to estimate the relationship, which allowed future observations to influence historical hedge ratios.

**Same-close execution -> next-open execution**  
Signals are generated using closing data and are now executed at the following trading day's open.

**Close-to-close P&L -> interval-aware P&L**  
P&L now distinguishes overnight and intraday exposure around entries and exits.

These changes reduced the reported performance, but made the backtest more realistic and much more useful as a research baseline.

---

## Repository Structure

```text
stat-arb/
|
|-- notebooks/
|   |-- 01_v_ma_backtest.py
|   `-- data_download_check.py
|
|-- src/
|   `-- data_download.py
|
|-- .gitignore
|-- README.md
`-- requirements.txt
```

Raw market data is stored locally under:

```text
data/raw/
```

The `data/` directory is intentionally excluded from Git.

---

## Setup

Clone the repository:

```bash
git clone https://github.com/eliejebrael/stat-arb.git
cd stat-arb
```

Create and activate a virtual environment, then install the dependencies:

```bash
pip install -r requirements.txt
```

The main dependencies are:

```text
pandas
numpy
matplotlib
statsmodels
yfinance
```

---

## Downloading the Data

`src/data_download.py` contains the yfinance download helper used by the project.

The current backtest expects these two files under `data/raw/`:

```text
V_2015-01-02_2025-12-31.csv
MA_2015-01-01_2026-01-01.csv
```

They can be created from the project root with:

```bash
python -c "from src.data_download import download_data; download_data('V', '2015-01-02', '2025-12-31'); download_data('MA', '2015-01-01', '2026-01-01')"
```

The download helper creates `data/raw/` automatically if it does not already exist.

---

## Running the Backtest

The current script uses paths relative to the `notebooks/` directory, so run it from there:

```bash
cd notebooks
python 01_v_ma_backtest.py
```

The script currently prints the main backtest metrics, the first rows of the trade log, and the trade-level statistics.

---

## Roadmap

### Completed

- [x] Historical data download and alignment
- [x] Correlation / cointegration exploration
- [x] Rolling OLS hedge ratio
- [x] Spread construction
- [x] Rolling z-score
- [x] Stateful entry and exit logic
- [x] Hedge-ratio-based position sizing
- [x] Fixed shares during each trade
- [x] Transaction costs
- [x] Removal of full-sample look-ahead bias
- [x] Next-open execution
- [x] Overnight / intraday P&L accounting
- [x] Equity curve, drawdown, and Sharpe ratio
- [x] Trade summary
- [x] Win/loss and holding-period analysis

### Next

- [ ] Analyze trade performance by holding-period bucket
- [ ] Test the unchanged framework on additional pairs
- [ ] Add research / validation / test splits
- [ ] Study parameter robustness
- [ ] Estimate mean-reversion half-life
- [ ] Investigate time-based exits without overfitting
- [ ] Add more performance and risk metrics
- [ ] Add slippage, spread, and borrow-cost assumptions
- [ ] Build a systematic pair-selection process
- [ ] Backtest multiple pairs
- [ ] Build a portfolio-level stat-arb framework
- [ ] Add automated tests
- [ ] Refactor research code into reusable modules
- [ ] Explore intraday data after the daily framework is validated

---

## Longer-Term Direction

The daily V/MA strategy is mainly the first research case.

The longer-term goal is to build a framework that can evaluate multiple candidate pairs and eventually combine them into a portfolio. After the daily version is properly validated, I also want to explore whether the same ideas can be adapted to intraday data.

An intraday version would need to be treated as a separate strategy: different estimation windows, different signal behavior, and much more detailed execution-cost modeling.

---

## Disclaimer

This repository is an educational and research project.

The backtest does not represent guaranteed future performance, and several real-world trading frictions are not yet modeled. Nothing in this repository should be interpreted as financial advice.

## Author

Built as a personal quantitative finance and statistical arbitrage research project.
