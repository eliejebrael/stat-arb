import yfinance as yf
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent

def download_data(ticker, start_date, end_date, interval="1d", auto_adjust=True):
    data = yf.download(
        ticker,
        start=start_date,
        end=end_date,
        interval=interval,
        auto_adjust=auto_adjust
    )

    output_path = project_root / "data" / "raw" / f"{ticker}_{start_date}_{end_date}.csv"
    data.to_csv(output_path)

    return data

if __name__ == "__main__":
    download_data("MA", "2015-01-01", "2026-01-01", "1d", True)
