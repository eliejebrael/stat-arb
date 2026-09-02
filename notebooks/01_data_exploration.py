import pandas as pd
import matplotlib.pyplot as plt
import time


start_time = time.perf_counter()
output_path1 = f"../data/raw/V_2015-01-02_2025-12-31.csv"
output_path2 = f"../data/raw/MA_2015-01-01_2026-01-01.csv"

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


V_close = V_loaded["Close"]["V"]
MA_close = MA_loaded["Close"]["MA"]

prices = pd.concat([V_close, MA_close], axis=1)
prices.columns = ["V", "MA"]

returns = prices / prices.shift(1) - 1

import numpy as np
import statsmodels.api as sm

window = 252

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


    spread_t = prices["MA"].iloc[t] - (alpha_t + beta_t * prices["V"].iloc[t])

    alphas.append(alpha_t)
    betas.append(beta_t)
    spreads.append(spread_t)

alpha_series = pd.Series(alphas, index=prices.index)
beta_series = pd.Series(betas, index=prices.index)
spread = pd.Series(spreads, index=prices.index)
"""
Here is the old faulty code I had in place, then I realised that this has look-ahead bias by
taking the same hedge ratio which is calculated using 2015-2026 data instead of historic data

Y = prices["MA"]
X = prices["V"]

X = sm.add_constant(X) # adds columns of 1 so OLS can estimate the intercept (alpha)
#print(X.head())

model = sm.OLS(Y, X) # creates the OLS regression problem
results = model.fit() # solves for given coefficients

#print(results.params) # prints intercept (alpha) and hedge ratio (beta)
predicted_MA = results.predict(X) # predicts MA for every V using coefficients found
spread = Y - predicted_MA # calculates spread using actual MA - predicted MA
"""

spread.plot()
#plt.show()
plt.close()
#print(spread.mean()) # gives average value of the spread, does not prove mean reversion

# Run ADF test
from statsmodels.tsa.stattools import adfuller
adf_result = adfuller(spread.dropna()) # runs ADF test on spread, to determine whether stationary or non-stationary
#print(adf_result[0])  # test statistic
#print(adf_result[1])  # p-value, if < 0.05 then we can say it's stationary.

# let's test for cointegration using built-in function now (we already did manual version)
# Values won't be the same because manual version uses ADF test, built-in relies on Engle-Granger framework
from statsmodels.tsa.stattools import coint
coint_result = coint(prices["MA"], prices["V"])
#print(coint_result[0])  # test statistic
#print(coint_result[1])  # p-value

# Since we can't determine whether a spread value is abnormal or not, we can standardize it.
# This will help us determine how many std deviations away our value is from the mean.
spread_mean = spread.mean()
spread_std = spread.std()

zscore = (spread - spread_mean) / spread_std
zscore.plot()
#plt.show()
plt.close()
# A potential trading strategy: z > 2 short the spread, z < -2 long the spread, z ≈ 0 exit

# We use rolling windows to avoid issues like the "look-ahead bias"
# We also need to shift by 1 to make sure that the day of interest is not included.
rolling_mean = spread.rolling(window=60).mean().shift(1)
rolling_std = spread.rolling(window=60).std().shift(1)
rolling_zscore = (spread - rolling_mean) / rolling_std

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

# Now let's build a positions system to determine what our action should be for the current day
position = 0 # +1 for z < -2, -1 for z > 2, and 0 for |z| < 0.5, else do nothing.
positions = []
for value in rolling_zscore:
    if pd.isna(value):
        position = 0
    elif position == 0:
        if value < -2:
            position = 1
        elif value > 2:
            position = -1
    elif abs(value) < 0.5:
        position = 0
    positions.append(position)

position_series = pd.Series( # turn it into panda
    positions,
    index=rolling_zscore.index
)

gross_notional = 10_000

position = 0
ma_shares = 0.0
v_shares = 0.0
cost_bps = 5
cost_rate = cost_bps / 10_000

daily_pnl = []

trade_log = []
daily_costs = []
entry_date = None

for t in range(len(prices) - 1):
    signal = position_series.iloc[t]
    transaction_cost = 0.0

    if position == 0:
        if signal != 0 and not pd.isna(beta_series.iloc[t]):
            position = signal

            entry_date = prices.index[t]

            beta_t = beta_series.iloc[t]

            trade_log.append({
                "event": "ENTRY",
                "date": entry_date,
                "position": position,
                "zscore": rolling_zscore.iloc[t],
                "beta": beta_t
            })

            ma_price = prices["MA"].iloc[t]
            v_price = prices["V"].iloc[t]

            ma_shares = gross_notional / (
                    ma_price + abs(beta_t) * v_price
            )

            v_shares = abs(beta_t) * ma_shares

            actual_gross = (
                    ma_shares * ma_price
                    + v_shares * v_price
            )

            transaction_cost += actual_gross * cost_rate


    elif signal == 0:

        exit_gross = (
                ma_shares * prices["MA"].iloc[t]
                + v_shares * prices["V"].iloc[t]
        )

        transaction_cost += exit_gross * cost_rate

        trade_log.append({
            "event": "EXIT",
            "date": prices.index[t],
            "position": position,
            "zscore": rolling_zscore.iloc[t],
            "beta": np.nan
        })

        position = 0
        ma_shares = 0.0
        v_shares = 0.0

    ma_change = prices["MA"].iloc[t + 1] - prices["MA"].iloc[t]
    v_change = prices["V"].iloc[t + 1] - prices["V"].iloc[t]

    trading_pnl = position * (ma_shares * ma_change - v_shares * v_change)

    pnl_t = trading_pnl - transaction_cost
    daily_costs.append(transaction_cost)

    daily_pnl.append(pnl_t)

daily_pnl = pd.Series(
    daily_pnl,
    index=prices.index[1:]
)

print("Total transaction costs:", sum(daily_costs))
print("Net PnL:", daily_pnl.sum())

trade_log = pd.DataFrame(trade_log)

print(trade_log.head(4))

print(daily_pnl.sum())


"""
End of section
"""

#print(strategy_returns[strategy_returns != 0].head())
initial_capital = 10_000
equity_curve = initial_capital + daily_pnl.cumsum()
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

running_max = equity_curve.cummax()
drawdown = equity_curve / running_max - 1
max_drawdown = drawdown.min()
print(max_drawdown)
drawdown.plot()
#plt.show()
plt.close()

daily_strategy_returns = daily_pnl / initial_capital
daily_mean = daily_strategy_returns.mean()
daily_std = daily_strategy_returns.std()
sharpe = (daily_mean / daily_std) * (252 ** 0.5) # 252 trading days pear year on average
print(sharpe)

end_time = time.perf_counter()
print(f"Running time in seconds: {end_time - start_time}")
