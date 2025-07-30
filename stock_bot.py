import yfinance as yf
import pandas as pd
import time
import os
from datetime import datetime
import warnings
from playsound import playsound
from colorama import Fore, Style, init
init(autoreset=True)

warnings.filterwarnings("ignore")

def load_tickers(file_path):
    with open(file_path, "r") as f:
        tickers = [line.strip() for line in f if line.strip()]
    return tickers

def analyze_stock(ticker):
    df = yf.download(ticker, interval="5m", period="2d", progress=False)
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


    # Ultimele valori
    ma20 = float(df["MA20"].iloc[-1])
    macd = float(df["MACD"].iloc[-1])
    signal = float(df["Signal"].iloc[-1])
    rsi = float(df["RSI"].iloc[-1])
    price = float(df["Close"].iloc[-1])

    # Decizie simplificată
    if trend == "UP" and macd > signal and rsi < 70 and price > ma20:
        decision = "BUY"
    elif trend == "DOWN" and macd < signal and rsi > 30 and price < ma20:
        decision = "SELL"
    else:
        decision = "HOLD"

        
    play_sound(decision)

    return {
        "Ticker": ticker,
        "Trend": trend,
        "Price": round(price, 2),
        "MA20": round(ma20, 2),
        "MACD": round(macd, 3),
        "Signal": round(signal, 3),
        "RSI": round(rsi, 1),
        "Decision": decision
    }
    
def play_sound(decision):
    if decision == "BUY":
        playsound("buy.wav", block=False)
    elif decision == "SELL":
        playsound("sell.wav", block=False)

def main_loop(file_path, interval_sec=120):
    while True:
        tickers = load_tickers(file_path)
        results = []

        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting analysis...\n")
        
        for ticker in tickers:
            result = analyze_stock(ticker)
            results.append(result)

        df_results = pd.DataFrame(results)
        # Antet tabel colorat
        header = f"{'Ticker':>6} {'Trend':>8} {'Price($)':>9} {'MA20($)':>9} {'MACD':>7} {'Signal':>8} {'RSI':>5} {'Decision':>9}"
        print("-" * len(header))
        print(header)
        print("-" * len(header))

        # Afișare colorată pe rânduri
        for _, row in df_results.iterrows():
            color = ""
            if row["Decision"] == "BUY":
                color = Fore.GREEN
            elif row["Decision"] == "SELL":
                color = Fore.RED
            else:
                color = Style.RESET_ALL
        
            line = f"{row['Ticker']:>6} {row['Trend']:>8} {row['Price']:>9.2f} {row['MA20']:>9.2f} {row['MACD']:>7.3f} {row['Signal']:>8.3f} {row['RSI']:>5.1f} {row['Decision']:>9}"
            print(color + line)


        print(f"\nNext update in {interval_sec} seconds...\n")
        time.sleep(interval_sec)

if __name__ == "__main__":
    ticker_file = "tickers.txt"  # Pune aici fișierul cu tickere
    if os.path.exists(ticker_file):
        main_loop(ticker_file)
    else:
        print("Fisierul 'tickers.txt' nu a fost găsit.")
