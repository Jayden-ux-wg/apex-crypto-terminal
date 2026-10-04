import os
import time
import pandas as pd
import alpaca_trade_api as tradeapi

# ==========================================
# 1. KONFIGURATION & API-ZUGANG
# ==========================================
# Trage hier deine echten Alpaca Paper-Keys ein (oder nutze Umgebungsvariablen)
API_KEY = os.getenv("APACA_API_KEY", "DEIN_PAPER_API_KEY")
SECRET_KEY = os.getenv("APACA_SECRET_KEY", "DEIN_PAPER_SECRET_KEY")
BASE_URL = "https://paper-api.alpaca.markets"  # Wichtig: Paper-Trading Umgebung zum Testen

# Verbindung zu Alpaca herstellen
api = tradeapi.REST(API_KEY, SECRET_KEY, BASE_URL, api_version='v2')

# Pfad zur gemeinsamen Signal-Datei (aus deinem Dashboard)
SIGNAL_FILE = "bot_trades.csv"

def check_for_signals():
    """Überprüft die CSV-Datei des Dashboards auf neue Handelssignale."""
    if not os.path.exists(SIGNAL_FILE):
        return None
    
    try:
        df = pd.read_csv(SIGNAL_FILE)
        if df.empty:
            return None
        
        # Das allerletzte Signal auslesen
        latest_signal = df.iloc[-1]
        return latest_signal
    except Exception as e:
        print(f"Fehler beim Auslesen der Signal-Datei: {e}")
        return None

def execute_leveraged_trade(symbol="SPY", target_position_value_usd=10000.0):
    """
    Führt den Trade aus: Berechnet die Stückzahl für die 10.000 $ Position 
    und setzt eine Bracket-Order mit -0,8% Stop-Loss und +2,0% Take-Profit.
    """
    try:
        # Aktuellen Marktpreis abrufen
        latest_trade = api.get_latest_trade(symbol)
        current_price = latest_trade.price
        
        # Menge für die gewünschte Positionsgröße berechnen
        qty = int(target_position_value_usd / current_price)
        
        if qty <= 0:
            print("Achtung: Berechnete Stückzahl ist 0. Betrag ist zu gering für den aktuellen Kurs.")
            return

        # Risikomanagement: Exakt -0,8% Stop-Loss und +2,0% Take-Profit
        stop_loss_price = current_price * 0.992   # -0,8% Absicherung
        take_profit_price = current_price * 1.02  # +2,0% Gewinnziel
        
        print(f"--- TRADE WIRD VORBEREITET ---")
        print(f"Asset: {symbol} | Aktueller Kurs: {current_price} $")
        print(f"Berechnete Menge: {qty} Stück (Positionsgröße: {target_position_value_usd} $)")
        print(f"Server-Stop-Loss (-0,8%): {stop_loss_price:.2f} $")
        print(f"Take-Profit (+2,0%): {take_profit_price:.2f} $")

        # Bracket-Order an Alpaca senden (sichert den Stop-Loss direkt auf dem Broker-Server ab)
        order = api.submit_order(
            symbol=symbol,
            qty=qty,
            side='buy',
            type='market',
            time_in_force='gtc',
            order_class='bracket',
            stop_loss={'stop_price': round(stop_loss_price, 2)},
            take_profit={'limit_price': round(take_profit_price, 2)}
        )
        
        print(f"Erfolgreich an Alpaca übermittelt! Order-ID: {order.id}")
        return order.id

    except Exception as e:
        print(f"Fehler bei der Ausführung des Alpaca-Trades: {e}")
        return None

if __name__ == "__main__":
    print("🤖 Trading-Bot-Dauerschleife gestartet. Warte auf Signale in der CSV...")
    
    # Speichert bereits verarbeitete Zeitstempel, damit Trades nicht doppelt ausgeführt werden
    processed_timestamps = set()
    
    while True:
        signal = check_for_signals()
        if signal is not None:
            # Werte aus der CSV auslesen (unterstützt die Spaltennamen timestamp, symbol, signal)
            try:
                timestamp = str(signal.get("timestamp", ""))
                symbol = str(signal.get("symbol", "SPY"))
                sig_type = str(signal.get("signal", "BUY"))
            except Exception:
                timestamp = str(signal)
                symbol = "SPY"
                sig_type = "BUY"

            # Prüfen, ob dieses spezifische Signal bereits verarbeitet wurde
            if timestamp and timestamp not in processed_timestamps:
                print(f"\n📥 Neues Signal empfangen ({timestamp}): {symbol} -> {sig_type}")
                
                if sig_type == "BUY":
                    execute_leveraged_trade(symbol=symbol, target_position_value_usd=10000.0)
                
                # Timestamp als "erledigt" markieren
                processed_timestamps.add(timestamp)
        
        # Alle 5 Sekunden das nächste Update abwarten
        time.sleep(5)
