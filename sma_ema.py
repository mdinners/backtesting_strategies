import pandas as pd
import numpy as np
import copy

def add_sma_ema_signals(ohlc_data, symbol, short, long, ind):
    """
    Calculate SMA/EMA signals and buy/sell signals for a given OHLC dataset.

    Parameters:
    ohlc_data (pd.DataFrame): OHLC dataset
    symbol (str): Ticker symbol
    short (int): Short window for SMA/EMA calculation
    long (int): Long window for SMA/EMA calculation
    ind (str): Indicator type ('SMA' or 'EMA')

    Returns:
    pd.DataFrame: OHLC dataset with SMA/EMA signals and buy/sell signals added
    """
    # Copy original data
    ohlc_dict = copy.deepcopy(ohlc_data)

    # Calculate SMA/EMA signal
    cl_price = pd.DataFrame()
    ohlc_dict[symbol]['Short {}'.format(ind)] = ohlc_dict[symbol]['Adj Close'].rolling(window=short).mean()
    ohlc_dict[symbol]['Long {}'.format(ind)] = ohlc_dict[symbol]['Adj Close'].rolling(window=long).mean()
    ohlc_dict[symbol]['Short EMA'] = ohlc_dict[symbol]['Adj Close'].ewm(span=short, adjust=False).mean()
    ohlc_dict[symbol]['Long EMA'] = ohlc_dict[symbol]['Adj Close'].ewm(span=long, adjust=False).mean()
    cl_price[symbol] = ohlc_dict[symbol]['Adj Close']

    # Calculate buy/sell signal
    ohlc_dict[symbol]['Signal'] = 0.0
    ohlc_dict[symbol]['Signal'] = np.where(ohlc_dict[symbol]['Short {}'.format(ind)] > ohlc_dict[symbol]['Long {}'.format(ind)], 1.0, 0.0)
    ohlc_dict[symbol]['Signal'] = ohlc_dict[symbol]['Signal'].shift(1)
    ohlc_dict[symbol]['Position'] = ohlc_dict[symbol]['Signal'].diff()

    return ohlc_dict

