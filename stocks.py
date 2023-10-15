import yfinance as yf
import bs4 as bs
import requests
import numpy as np
import pandas as pd

def save_sp500_tickers():
    resp = requests.get('http://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
    soup = bs.BeautifulSoup(resp.text, 'lxml')
    table = soup.find('table', {'class': 'wikitable sortable'})
    tickers = []
    for row in table.findAll('tr')[1:]:
        ticker = row.findAll('td')[0].text.strip()
        tickers.append(ticker)
    return tickers

def get_signals(stock):
    try:
        signals_list = []  # List to store all generated signals

        df = yf.download(stock, start="2018-01-01", end="2023-01-01", progress=False)
        df['VMA'] = df['Volume'].rolling(window=20).mean()

        # ADX Calculation
        high_minus_low = df['High'] - df['Low']
        high_minus_prev_close = abs(df['High'] - df['Close'].shift(1))
        low_minus_prev_close = abs(df['Low'] - df['Close'].shift(1))
        TR = pd.concat([high_minus_low, high_minus_prev_close, low_minus_prev_close], axis=1).max(axis=1)
        
        df['+DM'] = np.where(((df['High'] - df['High'].shift(1)) > (df['Low'].shift(1) - df['Low'])), df['High'] - df['High'].shift(1), 0)
        df['-DM'] = np.where(((df['High'] - df['High'].shift(1)) < (df['Low'].shift(1) - df['Low'])), df['Low'].shift(1) - df['Low'], 0)
        df['+DM_MA'] = df['+DM'].rolling(window=14).mean()
        df['-DM_MA'] = df['-DM'].rolling(window=14).mean()
        df['TR_MA'] = TR.rolling(window=14).mean()
        df['+DI'] = (df['+DM_MA'] / df['TR_MA']) * 100
        df['-DI'] = (df['-DM_MA'] / df['TR_MA']) * 100
        df['DX'] = abs((df['+DI'] - df['-DI']) / (df['+DI'] + df['-DI'])) * 100
        df['ADX'] = df['DX'].rolling(window=14).mean()

        # OBV Calculation
        df['OBV'] = np.where(df['Close'] > df['Close'].shift(1), df['Volume'], np.where(df['Close'] < df['Close'].shift(1), -df['Volume'], 0)).cumsum()

        # MACD Calculation
        df['12_EMA'] = df['Close'].ewm(span=12).mean()
        df['26_EMA'] = df['Close'].ewm(span=26).mean()
        df['MACD'] = df['12_EMA'] - df['26_EMA']
        df['Signal_Line'] = df['MACD'].ewm(span=9).mean()

        # Bollinger Bands
        df['20_MA'] = df['Close'].rolling(window=20).mean()
        df['Upper_Band'] = df['20_MA'] + (df['Close'].rolling(window=20).std() * 2)
        df['Lower_Band'] = df['20_MA'] - (df['Close'].rolling(window=20).std() * 2)

        df['50_MA'] = df['Close'].rolling(window=50).mean()
        df['200_MA'] = df['Close'].rolling(window=200).mean()

        # Stochastic Oscillator
        df['L14'] = df['Close'].rolling(window=14).min()
        df['H14'] = df['Close'].rolling(window=14).max()
        df['%K'] = 100 * ((df['Close'] - df['L14']) / (df['H14'] - df['L14']))
        df['%D'] = df['%K'].rolling(window=3).mean()

        latest_data = df.iloc[-1]

        if latest_data['Volume'] > df['VMA'].iloc[-1]:
            volume_pressure = "Increasing"
        else:
            volume_pressure = "Decreasing"

        # Integrate ADX and OBV into signals
        if latest_data['ADX'] > 25:
            trend_strength = "Strong"
        elif latest_data['ADX'] < 20:
            trend_strength = "Weak"
        else:
            trend_strength = "Moderate"

        if df['OBV'].diff().iloc[-1] > 0:
            obv_trend = "Upward"
        else:
            obv_trend = "Downward"

        if df.shape[0] < 5*252:
            first_available_date = df.index[0]
            five_years_ago = df.loc[first_available_date, 'Close']
        else:
            five_years_ago = df.iloc[-5*252]['Close']

        one_year_ago = df.iloc[-252]['Close'] if df.shape[0] >= 252 else df.iloc[0]['Close']

        # Calculate RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        RSI = 100 - (100 / (1 + rs))


        # Logic for generating signals
        if latest_data['Close'] > 2*five_years_ago and latest_data['Close'] > 1.2*one_year_ago:
            highest_three = df['Close'].tail(30).nlargest(3).iloc[-1]
            lowest_three = df['Close'].tail(30).nsmallest(3).iloc[-1]

            if latest_data['Close'] >= highest_three:
                signals_list.append("SELL")
            elif latest_data['Close'] <= lowest_three and latest_data['Close'] > df.iloc[-30]['Close']:
                signals_list.append("BUY")
                
        if latest_data['50_MA'] > latest_data['200_MA'] and df.iloc[-2]['50_MA'] <= df.iloc[-2]['200_MA']:
            signals_list.append("BUY based on Golden Cross")
        elif latest_data['50_MA'] < latest_data['200_MA'] and df.iloc[-2]['50_MA'] >= df.iloc[-2]['200_MA']:
            signals_list.append("SELL based on Death Cross")
        elif latest_data['MACD'] > latest_data['Signal_Line'] and df.iloc[-2]['MACD'] <= df.iloc[-2]['Signal_Line']:
            signals_list.append("BUY based on MACD Cross")
        elif latest_data['MACD'] < latest_data['Signal_Line'] and df.iloc[-2]['MACD'] >= df.iloc[-2]['Signal_Line']:
            signals_list.append("SELL based on MACD Cross")
        elif latest_data['%K'] > latest_data['%D'] and latest_data['%K'] < 20 and latest_data['%D'] < 20:
            signals_list.append("BUY based on Stochastic")
        elif latest_data['%K'] < latest_data['%D'] and latest_data['%K'] > 80 and latest_data['%D'] > 80:
            signals_list.append("SELL based on Stochastic")
        
        if latest_data['Close'] < latest_data['Lower_Band']:
            signals_list.append("BUY based on Bollinger Bands")
        elif latest_data['Close'] > latest_data['Upper_Band']:
            signals_list.append("SELL based on Bollinger Bands")

        latest_RSI = RSI.iloc[-1]

        if latest_RSI < 30:
            signals_list.append("BUY based on RSI")
        elif latest_RSI > 70:
            signals_list.append("SELL based on RSI")

        basic_buy_signals = [s for s in signals_list if s == "BUY"]
        basic_sell_signals = [s for s in signals_list if s == "SELL"]

        if basic_buy_signals and volume_pressure == "Increasing":
            signals_list.append("BUY (Strong with Volume Pressure)")
        elif basic_sell_signals and volume_pressure == "Decreasing":
            signals_list.append("SELL (Strong with Volume Pressure)")

        if basic_buy_signals and trend_strength == "Strong":
            signals_list.append("BUY (Strong Trend) ADX")
        elif basic_sell_signals and trend_strength == "Strong":
            signals_list.append("SELL (Strong Trend) ADX")

        if basic_buy_signals and obv_trend == "Upward":
            signals_list.append("BUY (Confirmed by OBV)")
        elif basic_sell_signals and obv_trend == "Downward":
            signals_list.append("SELL (Confirmed by OBV)")
        
        if not signals_list:
            signals_list.append("HOLD")

        return signals_list

    except Exception as e:
        return f"Error for {stock}: {e}"


# Get all S&P 500 stocks
sp500_tickers = save_sp500_tickers()

# Analyze each stock
# Analyze each stock
for ticker in sp500_tickers:
    signals = get_signals(ticker)
    # Only print if 'BUY' exists in the list
    if any('BUY' in signal for signal in signals):  
        print(f"Debugging {ticker}: {signals}")  # Debug line
        print(f"Signals for {ticker}: {', '.join(signals)}")

