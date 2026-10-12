# Statistical Arbitrage / Pairs Trading

A Python research project for building and evaluating a statistical arbitrage strategy using pairs trading.

The current implementation studies **Visa (V)** and **Mastercard (MA)** using a rolling hedge ratio, mean-reverting spread, z-score trading signals, realistic next-open execution, transaction costs, and trade-level performance analysis.

The project is intentionally built from simple, interpretable statistical methods before moving to more advanced models.

---

## Project Goals

This project aims to develop a rigorous statistical arbitrage research pipeline while focusing on:

- understanding the difference between correlation and cointegration
- estimating a dynamic hedge ratio with rolling OLS
- constructing and analyzing a mean-reverting spread
- generating z-score based entry and exit signals
- avoiding look-ahead bias and data leakage
- modeling execution timing realistically
- accounting for transaction costs
- evaluating both portfolio-level and trade-level performance
- testing whether observed performance is robust rather than overfit

The longer-term goal is to extend the framework from a single pair to a multi-pair statistical arbitrage portfolio.

---

## Current Strategy

### Pair

- Visa (`V`)
- Mastercard (`MA`)

### Data Frequency

Daily market data covering approximately 2015–2025.

The strategy currently uses:

- daily **Close** prices for statistical modeling and signal generation
- next trading day's **Open** prices for trade execution

### Hedge Ratio

A rolling Ordinary Least Squares regression is estimated using a 252-trading-day lookback:

```text
MA_t = alpha_t + beta_t * V_t + epsilon_t
```

For each day `t`, the regression only uses observations available before that day's signal calculation.

The estimated `beta_t` is used as the hedge ratio.

### Spread

The spread is defined as:

```text
Spread_t = MA_t - (alpha_t + beta_t * V_t)
```

The spread represents the deviation of Mastercard's observed price from the value implied by the rolling statistical relationship with Visa.

### Z-Score

The spread is standardized using a 60-day rolling mean and standard deviation:

```text
z_t = (Spread_t - rolling_mean_t) / rolling_std_t
```

The rolling mean and standard deviation are shifted by one day so that the current observation does not contribute to its own historical benchmark.

### Trading Rules

Current baseline rules:

```text
Enter long spread:   z < -2
Enter short spread:  z > +2
Exit:                |z| < 0.5
```

Where:

- **Long spread** = long MA, short V
- **Short spread** = short MA, long V

Positions remain open until the exit condition is reached.

---

## Position Sizing

The strategy uses a fixed gross notional of:

```text
$10,000 per trade
```

The hedge ratio determines relative share quantities.

For a positive hedge ratio:

```text
q_V = |beta| * q_MA
```

with:

```text
q_MA = Gross Notional / (P_MA + |beta| * P_V)
```

Shares are fixed at entry and remain unchanged until the position is closed.

The strategy does **not** rebalance every day as the rolling hedge ratio changes.

---

## Execution Model

A major focus of the project is avoiding unrealistic same-bar execution.

The current timeline is:

```text
Close of day t
    ↓
Update spread and z-score
    ↓
Generate trading signal
    ↓
Open of day t+1
    ↓
Execute entry or exit
```

This prevents the backtest from observing a closing price and then unrealistically assuming a trade could have been executed at that same closing price.

Daily P&L is decomposed into:

```text
previous close → current open
+
current open → current close
```

This ensures that overnight and intraday exposure are correctly attributed to the position actually held during each interval.

The accounting implementation was manually validated by reconciling daily P&L for a complete trade against direct entry-to-exit P&L, matching to floating-point precision.

---

## Transaction Costs

The baseline transaction-cost model assumes:

```text
5 basis points per transaction
```

Costs are applied to the actual gross dollar value traded at both entry and exit.

Current limitations include:

- no explicit bid-ask spread model
- no slippage model
- no short borrow fees
- no market-impact model

These will be addressed in later stages.

---

## Current Backtest Results

Current baseline results for the V / MA pair:

| Metric | Result |
|---|---:|
| Net P&L | **$742.28** |
| Initial capital | **$10,000** |
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

These results are **research results, not evidence of a production-ready trading strategy**.

The current Sharpe ratio and long testing horizon indicate that significant validation and refinement are still required.

---

## Trade Duration Analysis

Trade-level analysis revealed a notable difference between winning and losing positions:

| Metric | Winning Trades | Losing Trades |
|---|---:|---:|
| Average holding period | **21.4 days** | **49.6 days** |
| Median holding period | **15.5 days** | **52 days** |
| Longest holding period | **69 days** | **82 days** |

This suggests that successful mean reversion tends to happen considerably faster than unsuccessful trades.

This observation may justify future research into:

- time-based exits
- relationship-breakdown detection
- adaptive exit rules

However, these rules will not be added solely because they improve the current in-sample backtest. They must be tested for robustness and out-of-sample performance.

---

## Research Lessons So Far

Several changes materially reduced apparent performance but made the backtest more trustworthy.

### Rolling rather than full-sample regression

Using a single regression over the full dataset creates look-ahead bias because future prices influence historical hedge ratios.

The current implementation estimates the relationship using only information available at each point in time.

### Next-open execution

Earlier versions effectively generated a signal from the day's close and executed at that same close.

The corrected model executes at the next trading day's open.

This reduced performance, as expected from removing an optimistic execution assumption.

### High win rate does not imply low risk

Although the current strategy wins roughly 68% of completed trades, losing trades are substantially larger and tend to remain open much longer.

This illustrates why win rate alone is not a useful measure of strategy quality.

---

## Statistical Diagnostics

The project currently includes:

- Augmented Dickey-Fuller testing
- Engle-Granger cointegration testing
- rolling OLS regression
- rolling spread analysis

These diagnostics are treated as research tools rather than as proof that a trading relationship will remain stable in the future.

Further work will focus on stability through time and structural relationship changes.

---

## Project Structure

```text
stat-arb/
│
├── data/
│   └── raw/
│
├── notebooks/
│   └── 01_data_exploration.py
│
├── src/
│
├── tests/
│
├── .gitignore
└── README.md
```

The current strategy is still concentrated in the research script while the methodology is being finalized. Code will be moved into reusable modules as the project matures.

---

## Roadmap

### Completed / Current Baseline

- [x] Download and align price data
- [x] Explore price relationships
- [x] Study correlation vs cointegration
- [x] Implement rolling OLS hedge ratio
- [x] Construct rolling spread
- [x] Implement rolling z-score
- [x] Generate state-based entry and exit signals
- [x] Implement hedge-ratio-based share sizing
- [x] Keep shares fixed during each trade
- [x] Add transaction costs
- [x] Remove full-sample regression look-ahead bias
- [x] Add next-open execution
- [x] Correct overnight and intraday P&L accounting
- [x] Calculate equity, Sharpe ratio, and drawdown
- [x] Build trade-level summaries
- [x] Analyze win/loss holding periods

### Next Steps

- [ ] Analyze performance by holding-period bucket
- [ ] Test the unchanged framework on additional pairs
- [ ] Create research / validation / test splits
- [ ] Study parameter robustness
- [ ] Estimate mean-reversion half-life
- [ ] Test time-based exits only if statistically justified
- [ ] Add richer performance and risk metrics
- [ ] Model slippage, spread, and borrowing costs
- [ ] Build systematic pair-selection pipeline
- [ ] Backtest multiple pairs simultaneously
- [ ] Construct a portfolio-level stat-arb strategy
- [ ] Add automated tests
- [ ] Refactor research code into reusable modules
- [ ] Explore an intraday adaptation after the daily framework is validated

---

## Future Intraday Extension

The current strategy operates on daily bars.

A future version may adapt the same statistical framework to intraday data, where models and signals would be updated throughout the trading session.

Moving to a higher frequency would require a complete revalidation of:

- OLS lookback length
- z-score window
- entry and exit thresholds
- execution assumptions
- transaction costs
- bid-ask spread
- slippage
- latency
- market microstructure effects

Intraday trading should therefore be treated as a separate research stage rather than simply compressing the daily strategy into shorter time intervals.

---

## Technologies

- Python
- pandas
- NumPy
- statsmodels
- matplotlib
- yfinance

---

## Running the Project

Install the required Python packages:

```bash
pip install pandas numpy matplotlib statsmodels yfinance
```

Run the current research script:

```bash
python notebooks/01_data_exploration.py
```

> Paths and data-download workflow may be refactored as the project moves from research into a reusable package structure.

---

## Disclaimer

This project is for **educational and research purposes only**.

The backtest does not represent guaranteed future performance and currently omits several real-world trading costs and execution constraints. Nothing in this repository constitutes financial advice or a recommendation to trade securities.

---

## Author

Built as a personal quantitative finance and statistical arbitrage research project.
