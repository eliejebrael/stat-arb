import pandas as pd
import matplotlib.pyplot as plt


output_path = "../data/raw/V_2015-01-02_2025-12-31.csv"

loaded = pd.read_csv(
    output_path,
    header=[0, 1],
    index_col=0,
    parse_dates=True
)

print(loaded.head())
print('----------')
print(loaded.columns)
print('----------')
print(loaded.index.dtype)
print('----------')
print(loaded.shape)
print('----------')
print(loaded.isna().sum())
print('----------')

close = loaded["Close"]["V"]

close.plot()
plt.show()