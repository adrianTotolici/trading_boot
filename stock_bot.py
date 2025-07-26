import pandas as pd
import yfinance as yf
from rich.live import Live
from rich.table import Table
from rich.console import Console
from datetime import datetime, timezone
import time
import sys
import io
import winsound  # ✅ Sunete pe Windows
from plyer import notification  # ✅ Notificări desktop

# Setare output UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

console = Console()

# ✅ Funcții pentru sunet

def play_buy_sound():
    winsound.Beep(750, 300)  # Sunet mai lung și mai puternic

def play_sell_sound():
    winsound.Beep(450, 300)

# ✅ Funcție notificare

def notify(title, message):
    try:
        notification.notify(
            title=title,
            message=message,
            timeout=5
        )
    except Exception as e:
        console.log(f"[red]Eroare notificare:[/red] {e}")

def classify_candle(open_price, close_price, high, low):
    direction = "Bullish" if close_price > open_price else "Bearish"
    body = abs(close_price - open_price)
    upper_shadow = high - max(open_price, close_price)
    lower_shadow = min(open_price, close_price) - low
    total_range = high - low if high - low != 0 else 1
    body_pct = round((body / total_range) * 100, 2)
    upper_pct = round((upper_shadow / total_range) * 100, 2)
    lower_pct = round((lower_shadow / total_range) * 100, 2)

    is_doji = body_pct < 10 and upper_pct > 30 and lower_pct > 30
    is_hammer = body_pct < 25 and lower_pct > 50 and upper_pct < 25 and direction == "Bullish"
    is_inverted_hammer = body_pct < 25 and upper_pct > 50 and lower_pct < 25 and direction == "Bullish"
    is_shooting_star = body_pct < 25 and upper_pct > 50 and lower_pct < 25 and direction == "Bearish"
    is_inverted_hammer_bear = body_pct < 25 and lower_pct > 50 and upper_pct < 25 and direction == "Bearish"

    return {
        "direction": direction,
        "body_pct": body_pct,
        "upper_pct": upper_pct,
        "lower_pct": lower_pct,
        "is_doji": is_doji,
        "is_hammer": is_hammer,
        "is_inverted_hammer": is_inverted_hammer,
        "is_shooting_star": is_shooting_star,
        "is_inverted_hammer_bear": is_inverted_hammer_bear,
    }

def calculate_rsi(data, period=14):
    delta = data["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def safe_get_float(series):
    if series.empty:
        return None
    val = series.iloc[0]
    if isinstance(val, pd.Series):
        val = val.item()
    if pd.isna(val):
        return None
    return float(val)

def analyze_ticker(ticker):
    try:
        data = yf.download(ticker, interval="5m", period="1d", auto_adjust=False, progress=False)
    except Exception as e:
        return f"[red]{ticker}: Eroare la descărcare date ({e})[/red]"

    if data.empty:
        return f"[red]{ticker}: Nu există date[/red]"

    data["MA20"] = data["Close"].rolling(window=20).mean()
    data["RSI"] = calculate_rsi(data)

    last = data.iloc[-1:]

    open_price = safe_get_float(last["Open"])
    close_price = safe_get_float(last["Close"])
    high = safe_get_float(last["High"])
    low = safe_get_float(last["Low"])
    ma20 = safe_get_float(last["MA20"])
    rsi = safe_get_float(last["RSI"])

    if None in (open_price, close_price, high, low):
        return f"[yellow]{ticker}: Date incomplete[/yellow]"

    candle = classify_candle(open_price, close_price, high, low)
    suggestion = []
    signal = None

    # Sugestii bazate pe tipul lumânării
    if candle["is_doji"]:
        suggestion.append("⚖️ Doji - indecizie pe piață")
    elif candle["is_hammer"]:
        suggestion.append("🔨 Hammer bullish - posibilă inversare ascendentă")
    elif candle["is_inverted_hammer"]:
        suggestion.append("🔨 Inverted Hammer bullish - posibilă inversare ascendentă")
    elif candle["is_shooting_star"]:
        suggestion.append("🎯 Shooting Star - posibilă inversare descendentă")
    elif candle["is_inverted_hammer_bear"]:
        suggestion.append("🎯 Inverted Hammer bearish - posibilă inversare descendentă")
    else:
        if candle["direction"] == "Bullish" and candle["body_pct"] > 50:
            suggestion.append("📈 BUY - Posibil trend ascendent")
            play_buy_sound()
            signal = "BUY"
        elif candle["direction"] == "Bearish" and candle["body_pct"] > 50:
            suggestion.append("📉 SELL - Posibil trend descendent")
            play_sell_sound()
            signal = "SELL"
        else:
            suggestion.append("🔍 Posibilă consolidare")

    # Sugestii MA20
    previous = data.iloc[-2:-1]
    if not previous.empty and ma20 is not None:
        prev_close = safe_get_float(previous["Close"])
        prev_ma20 = safe_get_float(previous["MA20"])
        if prev_close is not None and prev_ma20 is not None:
            if prev_close < prev_ma20 and close_price > ma20:
                suggestion.append("🔄 Cruce bullish peste MA20")
            elif prev_close > prev_ma20 and close_price < ma20:
                suggestion.append("🔄 Cruce bearish sub MA20")
            else:
                suggestion.append("✅ Deasupra MA20" if close_price > ma20 else "⚠️ Sub MA20")
    else:
        if ma20 is not None:
            suggestion.append("✅ Deasupra MA20" if close_price > ma20 else "⚠️ Sub MA20")

    # RSI
    if rsi is not None:
        if rsi > 70:
            suggestion.append("💡 RSI supra-cumpărat (>70)")
        elif rsi < 30:
            suggestion.append("💡 RSI supra-vândut (<30)")
        elif 45 <= rsi <= 55:
            suggestion.append("⚖️ RSI neutru (45-55)")
        else:
            suggestion.append("RSI în zona normală")

    suggest_text = " | ".join(suggestion)
    timestamp = last.index[0]
    final_text = f"{timestamp} -> {candle['direction']}, Corp: {candle['body_pct']}%, Umbre: ↑{candle['upper_pct']}% ↓{candle['lower_pct']}% | {suggest_text}"

    if signal:
        notify(f"{signal} - {ticker}", final_text)

    return final_text
    
def load_tickers_from_file(filename="tickers.txt"):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        console.log(f"[red]Eroare la citirea fișierului {filename}: {e}[/red]")
        return []

def analyze_all():
    tickers = load_tickers_from_file()
    table = Table(title=f"Analiză Real-Time {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    table.add_column("Ticker", style="cyan", no_wrap=True)
    table.add_column("Analiză", style="white")

    for ticker in tickers:
        analysis = analyze_ticker(ticker)
        table.add_row(ticker, analysis)

    return table

with Live(analyze_all(), refresh_per_second=0.2, screen=False) as live:
    while True:
        time.sleep(60)
        live.update(analyze_all())
