import pandas as pd
import yfinance as yf

def download_ticker_data(tickers, start_years_ago, end_years_ago):
    # Download historical data for tickers
    start = pd.Timestamp.today() - pd.DateOffset(years=start_years_ago)
    end = pd.Timestamp.today() - pd.DateOffset(years=end_years_ago)
    ohlc_data = {}

    for ticker in tickers:
        try:
            ohlc_data[ticker] = yf.download(ticker, start, end)
        except Exception as e:
            print("Failed to download data for ticker {}: {}".format(ticker, str(e)))

    return ohlc_data

