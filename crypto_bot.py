import yfinance as yf
import pandas as pd
import time
import os
from datetime import datetime
import warnings
from playsound import playsound
from colorama import Fore, Style, init
init(autoreset=True)
from binance.client import Client

warnings.filterwarnings("ignore")

client = Client()  # no key needed for public data

def fetch_binance_klines(symbol, interval, limit):
    # symbol example: 'BTCUSDT'
    klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    # klines fields: [Open time, Open, High, Low, Close, Volume, Close time, ...]
    df = pd.DataFrame(klines, columns=[
        'Open_time', 'Open', 'High', 'Low', 'Close', 'Volume',
        'Close_time', 'Quote_asset_volume', 'Number_of_trades',
        'Taker_buy_base_asset_volume', 'Taker_buy_quote_asset_volume', 'Ignore'
    ])

    # Convert to numeric
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        df[col] = pd.to_numeric(df[col])

    # Set index by time (optional)
    df['Open_time'] = pd.to_datetime(df['Open_time'], unit='ms')
    df.set_index('Open_time', inplace=True)

    return df

def load_tickers(file_path):
    with open(file_path, "r") as f:
        tickers = [line.strip() for line in f if line.strip()]
    return tickers

def analyze_stock(ticker):
    #binance_symbol = ticker.replace("-", "").replace("/", "")
    #if "USDT" not in binance_symbol:
    #    binance_symbol += "USDT"  # assume USDT pair
    df = fetch_binance_klines(ticker, interval='5m', limit=60)
    if df.empty or len(df) < 25:
        return {"Ticker": ticker, "Status": "Not enough data"}
    
    df["MA20"] = df["Close"].rolling(window=20).mean()

    # MACD
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

    # RSI
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # Trend pe ultimele 5 lumânări
    recent_closes = df.iloc[-5:]["Close"].values.tolist()
    if all(x < y for x, y in zip(recent_closes, recent_closes[1:])):
        trend = "UP"
    elif all(x > y for x, y in zip(recent_closes, recent_closes[1:])):
        trend = "DOWN"
    else:
        trend = "SIDEWAYS"
        
    # Calculeaza Stoch
    low14 = df["Low"].rolling(window=14).min()
    high14 = df["High"].rolling(window=14).max()
    df["%K"] = 100 * (df["Close"] - low14) / (high14 - low14)
    df["%D"] = df["%K"].rolling(window=3).mean()

    # Ultimele valori
    ma20 = float(df["MA20"].iloc[-1])
    macd = float(df["MACD"].iloc[-1])
    signal = float(df["Signal"].iloc[-1])
    rsi = float(df["RSI"].iloc[-1])
    price = float(df["Close"].iloc[-1])
    stoch_k = float(df["%K"].iloc[-1])
    stoch_d = float(df["%D"].iloc[-1])

    # Decizie simplificată
    if (
        trend == "UP" and
        macd > signal and
        rsi < 70 and
        #stoch_k > stoch_d and     # %K e peste %D → semnal pozitiv
        #stoch_k < 80 and
        price > ma20
    ):
        decision = "BUY"
    elif (
        trend == "DOWN" and
        macd < signal and
        rsi > 30 and
        #stoch_k < stoch_d and     # %K e sub %D → semnal negativ
        #stoch_k > 20 and
        price < ma20
    ):
        decision = "SELL"
    else:
        decision = "HOLD"

        
    #play_sound(decision)

    return {
    "Ticker": ticker,
    "Trend": trend,
    "Price": round(price, 2),
    "MA20": round(ma20, 2),
    "MACD": round(macd, 3),
    "Signal": round(signal, 3),
    "RSI": round(rsi, 1),
    "STOCH_K": round(stoch_k, 1),
    "STOCH_D": round(stoch_d, 1),
    "Decision": decision
}

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')
    
def play_sound(decision):
    if decision == "BUY":
        playsound("buy.wav", block=False)
    elif decision == "SELL":
        playsound("sell.wav", block=False)

def main_loop(file_path, interval_sec=60):
    history = []

    while True:
        tickers = load_tickers(file_path)
        results = []

        for ticker in tickers:
            result = analyze_stock(ticker)
            results.append(result)

        df_results = pd.DataFrame(results)

        output = []
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        output.append(f"\n[{timestamp}] Market Analysis\n")

        header = (
            f"{'Ticker':<8} | {'Trend':<9} | {'Price($)':>9} | {'MA20($)':>8} | "
            f"{'MACD':>7} | {'Signal':>7} | {'RSI':>5} | {'%K':>5} | {'%D':>5} | {'Decision':<8}"
        )
        separator = "-" * len(header)
        output.append(separator)
        output.append(header)
        output.append(separator)

        # Helper functions for coloring
        def green_if(cond, val):
            return Fore.GREEN + val + Style.RESET_ALL if cond else val

        def red_if(cond, val):
            return Fore.RED + val + Style.RESET_ALL if cond else val

        for _, row in df_results.iterrows():
            # Conditions for coloring indicators:
            trend_green = row["Trend"] == "UP"
            trend_red = row["Trend"] == "DOWN"

            macd_buy = row["MACD"] > row["Signal"]
            macd_sell = row["MACD"] < row["Signal"]

            rsi_buy = row["RSI"] < 70
            rsi_sell = row["RSI"] > 30

            price_buy = row["Price"] > row["MA20"]
            price_sell = row["Price"] < row["MA20"]

            stoch_buy = row["STOCH_K"] > row["STOCH_D"]
            stoch_sell = row["STOCH_K"] < row["STOCH_D"]

            # Color each indicator value accordingly
            trend_colored = (
                Fore.GREEN + row["Trend"] + Style.RESET_ALL if trend_green else
                Fore.RED + row["Trend"] + Style.RESET_ALL if trend_red else
                row["Trend"]
            )

            price_colored = green_if(price_buy, f"{row['Price']:.2f}")
            ma20_colored = green_if(price_buy, f"{row['MA20']:.2f}")

            macd_colored = green_if(macd_buy, f"{row['MACD']:.3f}")
            signal_colored = green_if(macd_buy, f"{row['Signal']:.3f}")

            rsi_colored = green_if(rsi_buy, f"{row['RSI']:.1f}")

            stoch_k_colored = green_if(stoch_buy, f"{row['STOCH_K']:.1f}")
            stoch_d_colored = green_if(stoch_buy, f"{row['STOCH_D']:.1f}")

            # For sell signals, color red if indicator favors sell and not buy:
            if not macd_buy and macd_sell:
                macd_colored = red_if(True, macd_colored)
                signal_colored = red_if(True, signal_colored)

            if not price_buy and price_sell:
                price_colored = red_if(True, price_colored)
                ma20_colored = red_if(True, ma20_colored)

            if not rsi_buy and rsi_sell:
                rsi_colored = red_if(True, rsi_colored)

            if not stoch_buy and stoch_sell:
                stoch_k_colored = red_if(True, stoch_k_colored)
                stoch_d_colored = red_if(True, stoch_d_colored)

            # Whole row color by decision
            decision_color = (
                Fore.GREEN if row["Decision"] == "BUY" else
                Fore.RED if row["Decision"] == "SELL" else
                Style.RESET_ALL
            )

            line = (
                f"{row.get('Ticker',''):<9} | "
                f"{trend_colored:<9} | "
                f"{price_colored:>9} | "
                f"{ma20_colored:<9} | "
                f"{macd_colored:>9} | "
                f"{signal_colored:<9} | "
                f"{rsi_colored:>9} | "
                f"{stoch_k_colored:<9} | "
                f"{stoch_d_colored:>9} | "
                f"{row.get('Decision',''):<9}"
            )
            output.append(decision_color + line)

        output_text = "\n".join(output)

        # Keep last 3 outputs
        history.append(output_text)
        history = history[-3:]

        clear_screen()
        print("\n\n".join(history))

        print(f"\nNext update in {interval_sec} seconds...\n")
        time.sleep(interval_sec)




if __name__ == "__main__":
    ticker_file = "tickers_crypto.txt"
    if os.path.exists(ticker_file):
        main_loop(ticker_file)
    else:
        print("Fisierul 'tickers.txt' nu a fost găsit.")
