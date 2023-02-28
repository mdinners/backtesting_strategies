
from flask import Flask, render_template, request, session
from flask_bootstrap import Bootstrap
from flask_table import Table, Col
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import yfinance as yf
import numpy as np
import copy
import os

import warnings
warnings.filterwarnings("ignore")

# Import the Hedge v5 trading strategy script
from hedge_functions import CAGR, total_return_multiple, volatility, sharpe, max_dd
from charts import generate_charts
from sma_ema import add_sma_ema_signals


app = Flask(__name__, template_folder='templates',static_folder='templates')

# generate a secret key
secret_key = os.urandom(24)

# set the secret key in the Flask app
app.secret_key = secret_key

#call boostrap table for bootstrap table
bootstrap = Bootstrap(app)


# default values
default_symbol = 'QQQ'
default_short = 1
default_long = 200
default_ind = 'SMA'
default_start_years_ago = 20
default_end_years_ago = 0

@app.route('/')
def index():
    return render_template('index.html',
        symbol=session.get('symbol', default_symbol),
        short=session.get('short', default_short),
        long=session.get('long', default_long),
        ind=session.get('ind', default_ind),
        start_years_ago=session.get('start_years_ago', default_start_years_ago),
        end_years_ago=session.get('end_years_ago', default_end_years_ago),
        img_str = '',
        table_str = '')


@app.route('/generate_chart', methods=['POST'])
def generate_chart():
    # Get user input
    symbol = request.form.get('symbol', default_symbol)
    short = int(request.form.get('short', default_short))
    long = int(request.form.get('long', default_long))
    ind = request.form.get('ind', default_ind)
    start_years_ago = int(request.form.get('start_years_ago', default_start_years_ago))
    end_years_ago = int(request.form.get('end_years_ago', default_end_years_ago))


    # Download historical data for ticker
    start = pd.Timestamp.today() - pd.DateOffset(years=start_years_ago)
    end = pd.Timestamp.today() - pd.DateOffset(years=end_years_ago)
    df = pd.DataFrame()

    ticker_signal = symbol
    ticker_strat = symbol

    tickers = [symbol]
    ohlc_data = {}

    # Other ticker: '^IXIC','ARKK','GOOG','QQQ',

    for ticker in tickers:
        try:
            ohlc_data[ticker] = yf.download(ticker, start, end)
        except Exception as e:
            print("Failed to download data for ticker {}: {}".format(ticker, str(e)))

    # Add SMA/EMA signals and buy/sell signals
    ohlc_dict = add_sma_ema_signals(ohlc_data, symbol, short, long, ind)

    print('Dictionary after SMA and EMA calc and buy/sell signal',ohlc_dict)


    # Calculate returns with long strategy and ticker signal
    df_temp = pd.concat(ohlc_dict, axis=1)
    strat_returns = df_temp.xs('Adj Close', axis=1, level=1)
    strat_returns['Position'] = df_temp.xs('Position', axis=1, level=1)
    strat_returns = strat_returns.copy()
    strat_returns['Signal'] = df_temp.xs('Signal', axis=1, level=1)
    strat_returns['Returns'] = 0

    for i in range(1, len(strat_returns)):
        if strat_returns['Signal'].iloc[i] == 1:
            strat_returns['Returns'].iloc[i] = (
                    (strat_returns[ticker_strat].iloc[i] / strat_returns[ticker_strat].iloc[i - 1]) - 1)
        else:
            strat_returns['Returns'].iloc[i] = 0

    strat_returns['All Returns'] = (strat_returns[ticker_strat].pct_change())

    # Calculating long-only strategy KPIs without signal
    strategy_df_2 = pd.DataFrame()
    strategy_df_2["Returns"] = strat_returns["All Returns"]
    strategy_df_2["Returns"] = strategy_df_2.mean(axis=1)
    strategy_df_2["cum_return"] = (1 + strategy_df_2["Returns"]).cumprod()

    # Calculating long-only strategy KPIs with signal
    strategy_df = pd.DataFrame()
    strategy_df["Returns"] = strat_returns["Returns"]
    strategy_df["Returns"] = strategy_df.mean(axis=1)

    #table calcs
    class KPIs(Table):
        kpi = Col('KPI')
        long_only = Col('Long-only strat w/ signal', column_html_attrs={'class': 'text-center'})
        long_only_no_signal = Col('Long-only strat w/o signal', column_html_attrs={'class': 'text-center'})

    data = [
        {'kpi': 'CAGR', 'long_only': '{:.2%}'.format(CAGR(strategy_df)),
         'long_only_no_signal': '{:.2%}'.format(CAGR(strategy_df_2))},
        {'kpi': 'Sharpe ratio', 'long_only': '{:.2f}'.format(sharpe(strategy_df, 0.025)),
         'long_only_no_signal': '{:.2f}'.format(sharpe(strategy_df_2, 0.025))},
        {'kpi': 'Max Drawdown', 'long_only': '{:.2%}'.format(max_dd(strategy_df)),
         'long_only_no_signal': '{:.2%}'.format(max_dd(strategy_df_2))},
        {'kpi': 'Total return multiple', 'long_only': '{:.2%}'.format(total_return_multiple(strategy_df)),
         'long_only_no_signal': '{:.2%}'.format(total_return_multiple(strategy_df_2))}
    ]

    table_html = KPIs(data, classes=['table', 'table-striped']).__html__()

    buys = ohlc_dict[ticker_signal][ohlc_dict[ticker_signal]['Position'] == 1].index
    sells = ohlc_dict[ticker_signal][ohlc_dict[ticker_signal]['Position'] == -1].index

    img_str = generate_charts(ohlc_dict, ticker_signal, short, long, ind, ticker_strat, strat_returns, buys, sells)


    session['symbol'] = symbol
    session['short'] = short
    session['long'] = long
    session['ind'] = ind
    session['start_years_ago'] = start_years_ago
    session['end_years_ago'] = end_years_ago


    return render_template('index.html', table_html=table_html, img_str=img_str, symbol=symbol, short=short, long=long, ind=ind, start_years_ago=start_years_ago, end_years_ago=end_years_ago)


if __name__ == '__main__':
    app.run(port=port, debug=True)
