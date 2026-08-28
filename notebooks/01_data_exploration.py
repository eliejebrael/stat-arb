import pandas as pd
import matplotlib.pyplot as plt

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
print(returns.head())
print(returns.corr())
