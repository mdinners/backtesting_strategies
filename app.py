
from flask import Flask, render_template, request, session
from flask_bootstrap import Bootstrap
from flask_table import Table, Col
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
matplotlib.use('Agg')
from io import BytesIO
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import yfinance as yf
import numpy as np
import datetime as dt
import copy
from tabulate import tabulate
import matplotlib.ticker as mtick
import io
from flask import make_response
import base64
import os



import warnings
warnings.filterwarnings("ignore")


# Import the Hedge v5 trading strategy script
from hedge_functions import CAGR, total_return_multiple, volatility, sharpe, max_dd

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

    # Calculating SMA/EMA signal
    ohlc_dict = copy.deepcopy(ohlc_data)  # copy original data
    cl_price = pd.DataFrame()

    print('Calculating SMA and EMA for ', ticker_signal)
    ohlc_dict[ticker_signal]['Short SMA'] = ohlc_dict[ticker_signal]['Adj Close'].rolling(window=short).mean()
    ohlc_dict[ticker_signal]['Long SMA'] = ohlc_dict[ticker_signal]['Adj Close'].rolling(window=long).mean()
    ohlc_dict[ticker_signal]['Short EMA'] = ohlc_dict[ticker_signal]['Adj Close'].ewm(span=short, adjust=False).mean()
    ohlc_dict[ticker_signal]['Long EMA'] = ohlc_dict[ticker_signal]['Adj Close'].ewm(span=long, adjust=False).mean()
    cl_price[ticker_signal] = ohlc_dict[ticker_signal]['Adj Close']

    print('Calculating Buy/Sell signal for ', ticker_signal)
    ohlc_dict[ticker_signal]['Signal'] = 0.0
    ohlc_dict[ticker_signal]['Signal'] = np.where(
        ohlc_dict[ticker_signal]['Short {}'.format(ind)] > ohlc_dict[ticker_signal]['Long {}'.format(ind)], 1.0, 0.0)
    ohlc_dict[ticker_signal]['Signal'] = ohlc_dict[ticker_signal]['Signal'].shift(1)
    ohlc_dict[ticker_signal]['Position'] = ohlc_dict[ticker_signal]['Signal'].diff()

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

    # Charts
    fig, ax = plt.subplots(nrows=2, ncols=1, figsize=(10, 10))
    #ax[0].set_title('Long-only strategy: {a}'.format(a=ticker_strat))
    ax[0].set_title('Crossover signal: {a} {b}/{c} {d} '.format(a=ticker_signal, b=short, c=long, d=ind))
    ax[1].set_title('Cumulative return')

    ax[0].grid()
    ax[1].grid()
    #ax[2].grid()

    # Chart 1
    #ax[0].plot(strat_returns[ticker_strat], color='black')

    # Chart 2
    ax[0].plot(ohlc_dict[ticker_signal]['Adj Close'], color='black', label='Adj Close')
    ax[0].plot(ohlc_dict[ticker_signal]['Short {}'.format(ind)], color='black', label='Short {}'.format(ind))
    ax[0].plot(ohlc_dict[ticker_signal]['Long {}'.format(ind)], color='g', label='Long {}'.format(ind))

    buys = ohlc_dict[ticker_signal][ohlc_dict[ticker_signal]['Position'] == 1].index
    sells = ohlc_dict[ticker_signal][ohlc_dict[ticker_signal]['Position'] == -1].index
    ax[0].plot_date(buys, ohlc_dict[ticker_signal]['Short {}'.format(ind)][ohlc_dict[ticker_signal]['Position'] == 1], \
                    '^', markersize=5, color='g', label='buy')
    ax[0].plot_date(sells, ohlc_dict[ticker_signal]['Short {}'.format(ind)][ohlc_dict[ticker_signal]['Position'] == -1], \
                    'v', markersize=5, color='r', label='sell')
    ax[0].legend()

    # Chart 3
    strategy_df_2["cum_return"] = (1 + strategy_df_2["Returns"]).cumprod()
    strategy_df_2['Position'] = strat_returns['Position']
    ax[1].plot(strategy_df_2["cum_return"])
    ax[1].yaxis.set_major_formatter(mtick.PercentFormatter(1.0))

    # Chart 4
    strategy_df["cum_return"] = (1 + strategy_df["Returns"]).cumprod()
    strategy_df['Position'] = strat_returns['Position']
    ax[1].plot(strategy_df["cum_return"],color='green')
    ax[1].yaxis.set_major_formatter(mtick.PercentFormatter(1.0))

    #table calcs
    class KPIs(Table):
        kpi = Col('KPI')
        long_only = Col('Long-only strat w/ signal')
        long_only_no_signal = Col('Long-only strat w/o signal')

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

    img_buffer = io.BytesIO()
    fig.savefig(img_buffer, format='png',bbox_inches='tight')
    img_buffer.seek(0)

    # Create a base64 encoded image string
    img_str = base64.b64encode(img_buffer.getvalue()).decode('utf-8')

    session['symbol'] = symbol
    session['short'] = short
    session['long'] = long
    session['ind'] = ind
    session['start_years_ago'] = start_years_ago
    session['end_years_ago'] = end_years_ago

    session['symbol'] = symbol
    session['short'] = short
    session['long'] = long
    session['ind'] = ind
    session['start_years_ago'] = start_years_ago
    session['end_years_ago'] = end_years_ago

    return render_template('index.html', table_html=table_html, img_str=img_str, symbol=symbol, short=short, long=long, ind=ind, start_years_ago=start_years_ago, end_years_ago=end_years_ago)


if __name__ == '__main__':
    app.run(port=port, debug=True)
