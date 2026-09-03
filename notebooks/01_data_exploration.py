import pandas as pd
import matplotlib.pyplot as plt
import time
import numpy as np
import statsmodels.api as sm

from statsmodels.tsa.stattools import adfuller, coint


# ============================================================
# CONFIGURATION
# ============================================================

OUTPUT_PATH_V = "../data/raw/V_2015-01-02_2025-12-31.csv"
OUTPUT_PATH_MA = "../data/raw/MA_2015-01-01_2026-01-01.csv"

OLS_WINDOW = 252
ZSCORE_WINDOW = 60

ENTRY_Z = 2
EXIT_Z = 0.5

GROSS_NOTIONAL = 10_000
INITIAL_CAPITAL = 10_000

COST_BPS = 5
COST_RATE = COST_BPS / 10_000


# ============================================================
# DATA LOADING AND PREPARATION
# ============================================================


def load_prices(output_path1, output_path2):
    V_loaded = pd.read_csv(
        output_path1,
        header=[0, 1],
        index_col=0,
        parse_dates=True
    )

    MA_loaded = pd.read_csv(
        output_path2,
        header=[0, 1],
        index_col=0,
        parse_dates=True
    )

    data = pd.DataFrame({
        "V_open": V_loaded["Open"]["V"],
        "V_close": V_loaded["Close"]["V"],
        "MA_open": MA_loaded["Open"]["MA"],
        "MA_close": MA_loaded["Close"]["MA"]
    }).dropna()

    return data


# ============================================================
# ROLLING OLS HEDGE RATIO AND SPREAD
# ============================================================


def calculate_rolling_spread(prices, window):
    alphas = []
    betas = []
    spreads = []

    for t in range(len(prices)):
        if t < window:
            alphas.append(np.nan)
            betas.append(np.nan)
            spreads.append(np.nan)
            continue

        X_window = prices["V"].iloc[t-window:t]
        Y_window = prices["MA"].iloc[t-window:t]

        X_window = sm.add_constant(X_window)

        model = sm.OLS(Y_window, X_window)
        results = model.fit()

        alpha_t = results.params["const"]
        beta_t = results.params["V"]

        spread_t = prices["MA"].iloc[t] - (
            alpha_t + beta_t * prices["V"].iloc[t]
        )

        alphas.append(alpha_t)
        betas.append(beta_t)
        spreads.append(spread_t)

    alpha_series = pd.Series(alphas, index=prices.index)
    beta_series = pd.Series(betas, index=prices.index)
    spread = pd.Series(spreads, index=prices.index)

    return alpha_series, beta_series, spread


# ============================================================
# STATISTICAL DIAGNOSTICS
# ============================================================


def run_statistical_diagnostics(prices, spread):
    # Run ADF test on the rolling spread.
    adf_result = adfuller(spread.dropna(), result_object=True)

    # Built-in Engle-Granger cointegration test.
    coint_result = coint(prices["MA"], prices["V"])

    return adf_result, coint_result


# ============================================================
# Z-SCORE
# ============================================================


def calculate_zscores(spread, window):
    # Rolling z-score used by the strategy.
    rolling_mean = spread.rolling(window=window).mean().shift(1)
    rolling_std = spread.rolling(window=window).std().shift(1)
    rolling_zscore = (spread - rolling_mean) / rolling_std

    return rolling_zscore


# ============================================================
# POSITION / SIGNAL GENERATION
# ============================================================


def generate_position_series(rolling_zscore):
    # +1 for z < -2, -1 for z > 2, and 0 for |z| < 0.5.
    position = 0
    positions = []

    for value in rolling_zscore:
        if pd.isna(value):
            position = 0
        elif position == 0:
            if value < -ENTRY_Z:
                position = 1
            elif value > ENTRY_Z:
                position = -1
        elif abs(value) < EXIT_Z:
            position = 0

        positions.append(position)

    position_series = pd.Series(
        positions,
        index=rolling_zscore.index
    )

    return position_series


# ============================================================
# BACKTEST
# ============================================================


def run_backtest(
    data,
    prices,
    beta_series,
    rolling_zscore,
    position_series,
    gross_notional,
    cost_rate
):
    position = 0
    ma_shares = 0.0
    v_shares = 0.0

    daily_pnl = []
    trade_log = []
    daily_costs = []

    for t in range(1, len(prices)):
        signal = position_series.iloc[t - 1]
        transaction_cost = 0.0

        # ====================================================
        # 1. OVERNIGHT PNL
        # Close[t-1] -> Open[t]
        # Uses the position held BEFORE today's execution
        # ====================================================

        ma_overnight_change = (
            data["MA_open"].iloc[t]
            - prices["MA"].iloc[t - 1]
        )

        v_overnight_change = (
            data["V_open"].iloc[t]
            - prices["V"].iloc[t - 1]
        )

        overnight_pnl = position * (
            ma_shares * ma_overnight_change
            - v_shares * v_overnight_change
        )

        # ====================================================
        # 2. EXECUTE YESTERDAY'S SIGNAL AT TODAY'S OPEN
        # ====================================================

        # ENTRY
        if position == 0:
            if signal != 0 and not pd.isna(beta_series.iloc[t - 1]):
                position = signal

                beta_t = beta_series.iloc[t - 1]

                ma_price = data["MA_open"].iloc[t]
                v_price = data["V_open"].iloc[t]

                ma_shares = gross_notional / (
                    ma_price + abs(beta_t) * v_price
                )

                v_shares = abs(beta_t) * ma_shares

                actual_gross = (
                    ma_shares * ma_price
                    + v_shares * v_price
                )

                transaction_cost += (
                    actual_gross * cost_rate
                )

                trade_log.append({
                    "event": "ENTRY",
                    "signal_date": prices.index[t - 1],
                    "date": prices.index[t],
                    "position": position,
                    "zscore": rolling_zscore.iloc[t - 1],
                    "beta": beta_t
                })

        # EXIT
        elif signal == 0:
            ma_exit_price = data["MA_open"].iloc[t]
            v_exit_price = data["V_open"].iloc[t]

            exit_gross = (
                ma_shares * ma_exit_price
                + v_shares * v_exit_price
            )

            transaction_cost += (
                exit_gross * cost_rate
            )

            trade_log.append({
                "event": "EXIT",
                "signal_date": prices.index[t - 1],
                "date": prices.index[t],
                "position": position,
                "zscore": rolling_zscore.iloc[t - 1],
                "beta": np.nan
            })

            position = 0
            ma_shares = 0.0
            v_shares = 0.0

        # ====================================================
        # 3. INTRADAY PNL
        # Open[t] -> Close[t]
        # Uses the position AFTER today's execution
        # ====================================================

        ma_intraday_change = (
            prices["MA"].iloc[t]
            - data["MA_open"].iloc[t]
        )

        v_intraday_change = (
            prices["V"].iloc[t]
            - data["V_open"].iloc[t]
        )

        intraday_pnl = position * (
            ma_shares * ma_intraday_change
            - v_shares * v_intraday_change
        )

        # ====================================================
        # 4. TOTAL DAILY PNL
        # ====================================================

        pnl_t = (
            overnight_pnl
            + intraday_pnl
            - transaction_cost
        )


        daily_pnl.append(pnl_t)
        daily_costs.append(transaction_cost)

    daily_pnl = pd.Series(
        daily_pnl,
        index=prices.index[1:]
    )

    trade_log = pd.DataFrame(trade_log)

    return daily_pnl, trade_log, daily_costs


# ============================================================
# PERFORMANCE METRICS
# ============================================================


def calculate_performance(daily_pnl, initial_capital):
    equity_curve = initial_capital + daily_pnl.cumsum()

    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1
    max_drawdown = drawdown.min()

    daily_strategy_returns = daily_pnl / initial_capital
    daily_mean = daily_strategy_returns.mean()
    daily_std = daily_strategy_returns.std()
    sharpe = (daily_mean / daily_std) * (252 ** 0.5)

    return equity_curve, drawdown, max_drawdown, sharpe

# ============================================================
# TRADE SUMMARY
# ============================================================

def build_trade_summary(trade_log, daily_pnl):
    """
                    trade_log.append({
                    "event": "ENTRY",
                    "signal_date": prices.index[t - 1],
                    "date": prices.index[t],
                    "position": position,
                    "zscore": rolling_zscore.iloc[t - 1],
                    "beta": beta_t
                })
    """
    trade_summary =  []
    for i in range(0, len(trade_log), 2):
        entry_date = trade_log["date"].iloc[i]
        exit_date = trade_log["date"].iloc[i + 1]

        trade_pnl = daily_pnl.loc[entry_date:exit_date].sum()

        trade_summary.append({
            "entry_date": entry_date,
            "exit_date": exit_date,
            "position": trade_log["position"].iloc[i],
            "days_held": (exit_date - entry_date).days,
            "pnl" : trade_pnl,
            "return" : trade_pnl / GROSS_NOTIONAL
        })

    trade_summary = pd.DataFrame(trade_summary)

    return trade_summary

def trade_summary_stats(trade_summary):
    wins = 0
    losses = 0
    win_amount = 0
    loss_amount = 0
    best_trade = 0
    worst_trade = 0

    total_win_period = 0
    total_loss_period = 0

    total_trades = len(trade_summary)
    for i in range(total_trades):
        temp = trade_summary["pnl"].iloc[i] # temp is more efficient than calling trade["pnl"] every time
        if temp > 0:
            wins += 1
            total_win_period += trade_summary["days_held"].iloc[i]
            if temp > best_trade:
                best_trade = temp
            win_amount += temp
        elif temp < 0:
            losses += 1
            total_loss_period += trade_summary["days_held"].iloc[i]
            if temp < worst_trade:
                worst_trade = temp
            loss_amount += temp

    print("Win rate: ", wins/total_trades)
    print("Average winner: ", win_amount / wins)
    print("Average loser: ", loss_amount / losses)
    print("Profit factor: ", win_amount / abs(loss_amount))
    print("Best trade: ", best_trade)
    print("Worst trade: ", worst_trade)
    print("Average win period: ", total_win_period / wins)
    print("Average loss period: ", total_loss_period / losses)

    winning_trades = trade_summary[trade_summary["pnl"] > 0]
    losing_trades = trade_summary[trade_summary["pnl"] < 0]

    print("Median win period:", winning_trades["days_held"].median())

    print("Median loss period:", losing_trades["days_held"].median())

    print("Longest winning trade:", winning_trades["days_held"].max())

    print("Longest losing trade:", losing_trades["days_held"].max())
    return None


# ============================================================
# MAIN SCRIPT
# ============================================================


def main():
    start_time = time.perf_counter()

    # Load and prepare data
    data = load_prices(OUTPUT_PATH_V, OUTPUT_PATH_MA)

    prices = data[["V_close", "MA_close"]].copy()
    prices.columns = ["V", "MA"]

    # Estimate rolling hedge ratio and spread
    alpha_series, beta_series, spread = calculate_rolling_spread(prices, OLS_WINDOW)

    spread.plot()
    #plt.show()
    plt.close()
    #print(spread.mean()) # gives average value of the spread, does not prove mean reversion

    # Statistical diagnostics
    adf_result, coint_result = run_statistical_diagnostics(prices, spread)

    #print(adf_result.stat)  # test statistic
    #print(adf_result.pvalue)  # p-value, if < 0.05 then we can say it's stationary.

    # Values won't be the same because manual version uses ADF test,
    # built-in relies on Engle-Granger framework.
    #print(coint_result[0])  # test statistic
    #print(coint_result[1])  # p-value

    # Z-scores
    rolling_zscore = calculate_zscores(spread, ZSCORE_WINDOW)

    rolling_zscore.plot()
    #plt.show()
    plt.close()

    """
    Now let's settle some things:
    Our spread is: St = MAt − (α + β Vt)

    So if our z-score is very positive, that means our spread is unusually high:
    MA is expensive relative to V according to the historical relationship
    The correct decision would be: short MA and long β units of V

    If our z-score is very negative, the opposite of the previous statement is true:
    Long MA and short β units of V

    Consider β = 1.77 for this example, this is the rough relationship:
    long spread = +1 MA, -1.7757 V
    short spread = -1 MA, +1.7757 V
    """

    # Generate position series
    position_series = generate_position_series(rolling_zscore)

    # Backtest
    daily_pnl, trade_log, daily_costs = run_backtest(
        data,
        prices,
        beta_series,
        rolling_zscore,
        position_series,
        GROSS_NOTIONAL,
        COST_RATE
    )

    print("Total transaction costs:", sum(daily_costs))
    print("Net PnL:", daily_pnl.sum())

    print(trade_log.head())


    # Performance
    equity_curve, drawdown, max_drawdown, sharpe = calculate_performance(daily_pnl, INITIAL_CAPITAL)

    equity_curve.plot()
    #plt.show()
    plt.close()

    """
    After updating the hedge ratio and removing the look-ahead bias, we can notice that the
    returns go from around 79% profit (with a peak around 100%) over the studied period to roughly 5%
    with the 2016-2020 period mostly represented by losses.
    We can say that this was a huge reality check and taught me to be more careful of these errors
    as they can falsify an entire research.
    """

    print(f"Max drawdown: {max_drawdown}")

    trade_summary = build_trade_summary(trade_log, daily_pnl)
    print(trade_summary.head())

    trade_summary_stats(trade_summary)

    drawdown.plot()
    #plt.show()
    plt.close()

    print(f"Sharpe: {sharpe}")

    end_time = time.perf_counter()
    print(f"Running time in seconds: {end_time - start_time}")


if __name__ == "__main__":
    main()
