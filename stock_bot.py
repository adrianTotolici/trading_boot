import yfinance as yf
import datetime
import pytz
import time
import os
from plyer import notification
from rich.console import Console
from rich.table import Table
from playsound import playsound

console = Console()

# Sunete pentru BUY și SELL
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BUY_SOUND = os.path.join(BASE_DIR, "buy.wav")
SELL_SOUND = os.path.join(BASE_DIR, "sell.wav")

# Configurație interval și lookback
INTERVAL = "5m"
LOOKBACK = 5  # minute

# Încarcă tickerele din fișier
TICKERS_FILE = "tickers.txt"
def load_tickers():
    try:
        with open(TICKERS_FILE, "r") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Eroare la citirea fisierului de tickere: {e}")
        return []

def play_buy_sound():
    try:
        playsound(BUY_SOUND)
    except Exception as e:
        print(f"Eroare sunet BUY: {e}")

def play_sell_sound():
    try:
        playsound(SELL_SOUND)
    except Exception as e:
        print(f"Eroare sunet SELL: {e}")

def compute_rsi(data, period=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def safe_float(val):
    # Dacă e un pd.Series cu un element, ia elementul
    if hasattr(val, "iloc"):
        val = val.iloc[0]
    # Dacă e un pd.Series cu un item, folosește .item()
    if hasattr(val, "item"):
        val = val.item()
    return float(val)

def analyze_ticker2(ticker):
    try:
        df = yf.download(ticker, period="2d", interval=INTERVAL, progress=False, auto_adjust=False)
        df.dropna(inplace=True)

        if df.empty or len(df) < 20:
            return ticker, "Date insuficiente"

        # RSI + validare
        df["RSI"] = compute_rsi(df["Close"])
        rsi = safe_float(df["RSI"].iloc[-1]) if not df["RSI"].isna().iloc[-1] else None

        # Trend din ultimele 4 închideri
        recent_closes = df.loc[:, "Close"].iloc[-4:].values.tolist()
        if len(recent_closes) < 4:
            trend_direction = "Trend necunoscut"
        elif all(x > y for x, y in zip(recent_closes, recent_closes[1:])):
            trend_direction = "Trend descendent"
        elif all(x < y for x, y in zip(recent_closes, recent_closes[1:])):
            trend_direction = "Trend ascendent"
        else:
            trend_direction = "Trend lateral"

        last = df.iloc[-1]
        open_price = safe_float(last["Open"])
        close_price = safe_float(last["Close"])
        high_price = safe_float(last["High"])
        low_price = safe_float(last["Low"])

        body = abs(close_price - open_price)
        upper_shadow = high_price - max(close_price, open_price)
        lower_shadow = min(close_price, open_price) - low_price
        total_range = high_price - low_price if high_price != low_price else 1

        body_pct = (body / total_range) * 100
        upper_pct = (upper_shadow / total_range) * 100
        lower_pct = (lower_shadow / total_range) * 100

        candle_direction = "Bullish" if close_price > open_price else "Bearish"

        # MA20
        ma20_series = df["Close"].rolling(window=20).mean()
        ma20 = safe_float(ma20_series.iloc[-1])
        below_ma20 = close_price < ma20

        # Variație pe intervalul de LOOKBACK
        current_time = df.index[-1]
        old_time = current_time - datetime.timedelta(minutes=LOOKBACK)
        df_recent = df[df.index >= old_time]
        if not df_recent.empty:
            old_close = safe_float(df_recent["Close"].iloc[0])
            price_change_pct = ((close_price - old_close) / old_close) * 100
        else:
            price_change_pct = 0

        # Generare sugestii
        suggestion = []

        if candle_direction == "Bullish" and body_pct > 50:
            if price_change_pct > 0.3 and trend_direction == "Trend ascendent":
                suggestion.append("📈 BUY - Confirmare trend ascendent")
                play_buy_sound()
            else:
                suggestion.append("🔍 Posibilă revenire")
        elif candle_direction == "Bearish" and body_pct > 50:
            if trend_direction == "Trend descendent":
                if price_change_pct >= 1:
                    suggestion.append(f"⚠️ Bearish, dar +{price_change_pct:.2f}% în {LOOKBACK}m - posibil fals SELL")
                elif price_change_pct > 0.3:
                    suggestion.append(f"📉 SELL (atenție: +{price_change_pct:.2f}% recent)")
                    play_sell_sound()
                else:
                    suggestion.append("📉 SELL - Trend descendent")
                    play_sell_sound()
            else:
                suggestion.append("🔍 Consolidare sau corecție")
        else:
            suggestion.append("🔍 Posibilă consolidare")

        # Alte semnale tehnice
        suggestion.append(f"{'⚠️' if below_ma20 else '✅'} {'Sub' if below_ma20 else 'Peste'} MA20")

        if rsi is None:
            suggestion.append("⚠️ RSI indisponibil")
        elif rsi < 30:
            suggestion.append("🟢 RSI scăzut (posibil BUY)")
        elif rsi > 70:
            suggestion.append("🔴 RSI ridicat (posibil SELL)")
        else:
            suggestion.append("RSI în zona normală")

        # Textul final
        text = (f"{current_time} -> {candle_direction}, Corp: {body_pct:.2f}%, Umbre: ↑{upper_pct:.2f}% ↓{lower_pct:.2f}% | "
                f"{trend_direction} | " + " | ".join(suggestion))

        return ticker.replace("-USD", ""), text

    except Exception as e:
        return ticker, f"Eroare: {e}"

def analyze_ticker(ticker):
    try:
        df = yf.download(ticker, period="2d", interval=INTERVAL, progress=False, auto_adjust=False)
        df.dropna(inplace=True)

        if df.empty or len(df) < 26:  # MACD necesită minim 26 puncte
            return ticker, "Date insuficiente"

        # RSI
        df["RSI"] = compute_rsi(df["Close"])
        rsi = safe_float(df["RSI"].iloc[-1]) if not df["RSI"].isna().iloc[-1] else None

        # MACD
        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

        macd = safe_float(df["MACD"].iloc[-1])
        macd_signal = safe_float(df["MACD_signal"].iloc[-1])
        prev_macd = safe_float(df["MACD"].iloc[-2])
        prev_macd_signal = safe_float(df["MACD_signal"].iloc[-2])

        # Trend pe ultimele 4 închideri
        recent_closes = list(df["Close"].iloc[-4:].values)
        if len(recent_closes) < 4:
            trend_direction = "Trend necunoscut"
        elif all(x > y for x, y in zip(recent_closes, recent_closes[1:])):
            trend_direction = "Trend descendent"
        elif all(x < y for x, y in zip(recent_closes, recent_closes[1:])):
            trend_direction = "Trend ascendent"
        else:
            trend_direction = "Trend lateral"

        last = df.iloc[-1]
        open_price = safe_float(last["Open"])
        close_price = safe_float(last["Close"])
        high_price = safe_float(last["High"])
        low_price = safe_float(last["Low"])

        body = abs(close_price - open_price)
        upper_shadow = high_price - max(close_price, open_price)
        lower_shadow = min(close_price, open_price) - low_price
        total_range = high_price - low_price if high_price != low_price else 1

        body_pct = (body / total_range) * 100
        upper_pct = (upper_shadow / total_range) * 100
        lower_pct = (lower_shadow / total_range) * 100

        candle_direction = "Bullish" if close_price > open_price else "Bearish"

        # MA20
        ma20_series = df["Close"].rolling(window=20).mean()
        ma20 = safe_float(ma20_series.iloc[-1])
        below_ma20 = close_price < ma20

        # Variație recentă
        current_time = df.index[-1]
        old_time = current_time - datetime.timedelta(minutes=LOOKBACK)
        df_recent = df[df.index >= old_time]
        if not df_recent.empty:
            old_close = safe_float(df_recent["Close"].iloc[0])
            price_change_pct = ((close_price - old_close) / old_close) * 100
        else:
            price_change_pct = 0

        suggestion = []

        # Candelă + trend
        if candle_direction == "Bullish" and body_pct > 50:
            if price_change_pct > 0.3 and trend_direction == "Trend ascendent":
                suggestion.append("📈 BUY - Confirmare trend ascendent")
                play_buy_sound()
            else:
                suggestion.append("🔍 Posibilă revenire")
        elif candle_direction == "Bearish" and body_pct > 50:
            if trend_direction == "Trend descendent":
                if price_change_pct >= 1:
                    suggestion.append(f"⚠️ Bearish, dar +{price_change_pct:.2f}% în {LOOKBACK}m - posibil fals SELL")
                elif price_change_pct > 0.3:
                    suggestion.append(f"📉 SELL (atenție: +{price_change_pct:.2f}% recent)")
                    play_sell_sound()
                else:
                    suggestion.append("📉 SELL - Trend descendent")
                    play_sell_sound()
            else:
                suggestion.append("🔍 Consolidare sau corecție")
        else:
            suggestion.append("🔍 Posibilă consolidare")

        # MA20
        suggestion.append(f"{'⚠️' if below_ma20 else '✅'} {'Sub' if below_ma20 else 'Peste'} MA20")

        # RSI
        if rsi is None:
            suggestion.append("⚠️ RSI indisponibil")
        elif rsi < 30:
            suggestion.append("🟢 RSI scăzut (posibil BUY)")
        elif rsi > 70:
            suggestion.append("🔴 RSI ridicat (posibil SELL)")
        else:
            suggestion.append("RSI în zona normală")

        # MACD
        if prev_macd < prev_macd_signal and macd > macd_signal:
            suggestion.append("🟢 MACD crossover UP - posibil BUY")
            play_buy_sound()
        elif prev_macd > prev_macd_signal and macd < macd_signal:
            suggestion.append("🔴 MACD crossover DOWN - posibil SELL")
            play_sell_sound()
        else:
            suggestion.append("MACD neutru")

        # Final
        text = (f"{current_time} -> {candle_direction}, Corp: {body_pct:.2f}%, Umbre: ↑{upper_pct:.2f}% ↓{lower_pct:.2f}% | "
                f"{trend_direction} | " + " | ".join(suggestion))

        return ticker.replace("-USD", ""), text

    except Exception as e:
        return ticker, f"Eroare: {e}"

def show_notification(title, message):
    try:
        notification.notify(
            title=title,
            message=message,
            app_name="StockBot",
            timeout=5
        )
    except Exception as e:
        print(f"Nu s-a putut trimite notificarea: {e}")

def main():
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        now = datetime.datetime.now(datetime.timezone.utc)
        table = Table(title=f"Analiză Real-Time {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        table.add_column("Ticker", style="cyan", no_wrap=True)
        table.add_column("Analiză", style="white")

        tickers = load_tickers()
        for ticker in tickers:
            short_ticker, result = analyze_ticker(ticker)
            table.add_row(short_ticker, result)

        console.print(table)
        time.sleep(60)

if __name__ == "__main__":
    main()
