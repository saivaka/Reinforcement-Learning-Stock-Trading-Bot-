import yfinance as yf
import pandas as pd

# script to install data

tickers = [
    'MMM', 'AXP', 'AAPL', 'BA', 'CAT', 'CVX', 'CSCO', 'KO', 'DIS', 'DOW',
    'GS', 'HD', 'IBM', 'INTC', 'JNJ', 'JPM', 'MCD', 'MRK', 'MSFT', 'NKE',
    'PFE', 'PG', 'TRV', 'UNH', 'RTX', 'VZ', 'V', 'WBA', 'WMT', 'XOM'
]

def get_data(tickers):
    """
    Make a dictionary where the key is a ticker and the value 
    is the daily prices in a datframe
    """
    stock_data = {}
    for ticker in tickers:
        df = yf.download(ticker, start="2009-01-01", end="2023-05-08")
        df = df[['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']]
        df.index = df.index.date
        # Name the index
        df.index.name = 'Date'
        stock_data[ticker] = df
    return stock_data

stock_data = get_data(tickers)

# Explicit column names to avoid confusion
column_names = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']

# Save to CSV with explicit headers
for ticker, df in stock_data.items():
    # Reset the column names just in case
    df.columns = column_names
    # Ensure the 'Date' is used as the index in the CSV
    df.to_csv(f'{ticker}.csv', index=True)