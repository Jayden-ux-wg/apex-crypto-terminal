from datetime import datetime, timedelta
import json
import os
import plotly.graph_objects as go
import pandas as pd
import streamlit as st
import yfinance as yf

# 1. SEITEN-EINSTELLUNGEN
st.set_page_config(
    page_title="Apex Crypto Terminal", page_icon="⚡", layout="wide"
)

st.title("Apex Krypto & ETF-Terminal")
st.caption(
    "Echtzeit-Analyse, Interaktive Kerzen-Charts (TradingView-Style),"
    " Automatisches Logbuch & Adaptive Mini-KI mit P&L-Tracker"
)

# Speicherpfade direkt im Skript-Ordner
basis_pfad = os.path.dirname(os.path.abspath(__file__))
desktop_pfad = os.path.join(basis_pfad, "bot_trades.csv")
config_pfad = os.path.join(basis_pfad, "rsi_config.json")

# Liste der Assets und deren Langnamen
coins = ["BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD", "IBIT"]
coin_namen = {
    "BTC-USD": "BTC-USD (Bitcoin)",
    "ETH-USD": "ETH-USD (Ethereum)",
    "SOL-USD": "SOL-USD (Solana)",
    "AVAX-USD": "AVAX-USD (Avalanche)",
    "IBIT": "IBIT (iShares Bitcoin Trust)",
}

# Standard-Zielwerte als Fallback
standard_ziele = {
    "BTC-USD": 60,
    "ETH-USD": 69,
    "SOL-USD": 70,
    "AVAX-USD": 60,
    "IBIT": 60,
}


def lade_config():
  if os.path.exists(config_pfad):
    try:
      with open(config_pfad, "r") as f:
        return json.load(f)
    except Exception:
      pass
  return standard_ziele.copy()


def speichere_config(ziele):
  try:
    with open(config_pfad, "w") as f:
      json.dump(ziele, f, indent=4)
  except Exception:
    pass


@st.cache_data(ttl=1800)
def hole_historische_daten(ticker):
  try:
    df = yf.Ticker(ticker).history(period="1mo", interval="1h")
    if df.empty or len(df) < 5:
      df = yf.Ticker(ticker).history(period="5d", interval="1h")
    return df
  except Exception:
    return pd.DataFrame()


@st.cache_data(ttl=12)
def hole_chart_daten(ticker):
  try:
    df = yf.Ticker(ticker).history(period="1d", interval="5m")
    if not df.empty and all(
        col in df.columns for col in ["Open", "High", "Low", "Close"]
    ):
      return df
  except Exception:
    pass
  return pd.DataFrame()


def berechne_rsi(data, window=14):
  delta = data["Close"].diff()
  gain = delta.where(delta > 0, 0).rolling(window=window).mean()
  loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
  rs = gain / loss
  return 100 - (100 / (1 + rs))


def mini_ki_optimiere_wert(data, ticker):
  kandidaten = [55, 60, 65, 70, 75]
  best_rsi = standard_ziele.get(ticker, 70)
  beste_trefferquote = -1

  if len(data) < 20:
    return best_rsi

  for rsi_limit in kandidaten:
    gewinne = 0
    gesamte_signale = 0

    for i in range(15, len(data) - 2):
      preis = data["Close"].iloc[i]
      sma = data["SMA20"].iloc[i]
      rsi = data["RSI"].iloc[i]

      if pd.isna(sma) or pd.isna(rsi):
        continue

      if preis > sma and rsi < rsi_limit:
        gesamte_signale += 1
        if data["Close"].iloc[i + 2] > preis:
          gewinne += 1

    if gesamte_signale > 0:
      trefferquote = gewinne / gesamte_signale
      if trefferquote > beste_trefferquote:
        beste_trefferquote = trefferquote
        best_rsi = rsi_limit

  return best_rsi


def log_trade_wenn_neu(coin, preis, rsi):
  jetzt = datetime.now()
  zeit_str = jetzt.strftime("%Y-%m-%d %H:%M:%S")
  anzeige_name = coin_namen.get(coin, coin)

  if os.path.exists(desktop_pfad):
    try:
      df = pd.read_csv(desktop_pfad)
      if (
          not df.empty
          and "Coin" in df.columns
          and "Zeitstempel" in df.columns
      ):
        coin_trades = df[df["Coin"] == anzeige_name]
        if not coin_trades.empty:
          letzte_zeit = datetime.strptime(
              coin_trades["Zeitstempel"].iloc[-1], "%Y-%m-%d %H:%M:%S"
          )
          if jetzt - letzte_zeit < timedelta(hours=1):
            return
    except Exception:
      pass

  neuer_eintrag = pd.DataFrame([{
      "Zeitstempel": zeit_str,
      "Coin": anzeige_name,
      "Einstiegspreis": round(preis, 2),
      "RSI": round(rsi, 1),
      "Aktueller Preis": round(preis, 2),
      "P&L (%)": 0.0,
      "Status": "Offen",
  }])

  if not os.path.exists(desktop_pfad):
    neuer_eintrag.to_csv(desktop_pfad, index=False)
  else:
    neuer_eintrag.to_csv(desktop_pfad, mode="a", header=False, index=False)


def aktualisiere_pnl_tracker():
  if os.path.exists(desktop_pfad):
    try:
      df = pd.read_csv(desktop_pfad)
      if df.empty:
        return

      if "Aktueller Preis" not in df.columns:
        df["Aktueller Preis"] = df["Einstiegspreis"]
      if "P&L (%)" not in df.columns:
        df["P&L (%)"] = 0.0

      rev_coin_namen = {v: k for k, v in coin_namen.items()}

      geaendert = False
      for idx, row in df.iterrows():
        if row["Status"] == "Offen":
          coin_anzeige = row["Coin"]
          coin = rev_coin_namen.get(coin_anzeige, coin_anzeige)
          entry = row["Einstiegspreis"]
          try:
            curr_df = yf.Ticker(coin).history(period="1d", interval="1m")
            if not curr_df.empty:
              curr_price = curr_df["Close"].iloc[-1]
              pnl = ((curr_price - entry) / entry) * 100

              df.at[idx, "Aktueller Preis"] = round(curr_price, 2)
              df.at[idx, "P&L (%)"] = round(pnl, 2)
              geaendert = True

              if pnl >= 1.5:
                df.at[idx, "Status"] = "Gewinn (TP +1.5%)"
              elif pnl <= -1.0:
                df.at[idx, "Status"] = "Verlust (SL -1%)"
          except Exception:
            pass

      if geaendert:
        df.to_csv(desktop_pfad, index=False)
    except Exception:
      pass


@st.fragment(run_every=12)
def lade_live_dashboard():
  st.subheader("Markt-Lage & Adaptive Mini-KI (12-Sekunden Takt)")

  aktualisiere_pnl_tracker()

  aktuelle_ziele = lade_config()
  results = []
  charts_data = {}
  config_hat_sich_geändert = False
  fehler_ticker = []

  for ticker in coins:
    data_logik = hole_historische_daten(ticker)

    if data_logik.empty or "Close" not in data_logik.columns:
      fehler_ticker.append(ticker)
      continue

    data_logik["SMA20"] = data_logik["Close"].rolling(window=20).mean()
    data_logik["RSI"] = berechne_rsi(data_logik)

    gelernter_rsi = mini_ki_optimiere_wert(data_logik, ticker)

    if aktuelle_ziele.get(ticker) != gelernter_rsi:
      aktuelle_ziele[ticker] = gelernter_rsi
      config_hat_sich_geändert = True

    optimaler_rsi = aktuelle_ziele[ticker]

    letzter_preis = data_logik["Close"].iloc[-1]
    letzter_sma = (
        data_logik["SMA20"].iloc[-1]
        if not pd.isna(data_logik["SMA20"].iloc[-1])
        else letzter_preis
    )
    letzter_rsi = (
        data_logik["RSI"].iloc[-1]
        if not pd.isna(data_logik["RSI"].iloc[-1])
        else 50.0
    )

    if letzter_preis > letzter_sma and letzter_rsi < optimaler_rsi:
      status = "Kaufsignal (KI-Optimiert)"
      log_trade_wenn_neu(ticker, letzter_preis, letzter_rsi)
    elif letzter_preis > letzter_sma and letzter_rsi >= optimaler_rsi:
      status = f"Überkauft (RSI >= {optimaler_rsi})"
    else:
      status = "Abwärtstrend"

    results.append({
        "Coin": coin_namen.get(ticker, ticker),
        "Preis ($)": f"${letzter_preis:.2f}",
        "SMA20 ($)": f"${letzter_sma:.2f}",
        "RSI": f"{letzter_rsi:.1f}",
        "KI-Zielwert": f"RSI < {optimaler_rsi}",
        "Status": status,
    })

    charts_data[ticker] = hole_chart_daten(ticker)

  if config_hat_sich_geändert:
    speichere_config(aktuelle_ziele)

  if fehler_ticker:
    st.warning(
        "Hinweis: Für folgende Assets konnten aktuell keine Yahoo-Daten"
        f" geladen werden: {', '.join(fehler_ticker)}"
    )

  if results:
    cols = st.columns(min(len(results), 5))
    for i, item in enumerate(results):
      if i < len(cols):
        cols[i].metric(
            label=item["Coin"],
            value=item["Preis ($)"],
            delta=item["KI-Zielwert"],
        )

    st.dataframe(pd.DataFrame(results), use_container_width=True)
  else:
    st.error("Keine Marktdaten verfügbar.")

  st.divider()

  st.subheader("Interaktive Live-Charts (Kerzen-Ansicht im 12-Sekunden-Takt)")
  st.caption("Echtzeit-Kerzencharts im Stil von professionellen Krypto-Terminals.")

  tab_namen = [coin_namen.get(t, t) for t in coins]
  tabs = st.tabs(tab_namen)

  for i, tab in enumerate(tabs):
    with tab:
      ticker = coins[i]
      df_chart = charts_data.get(ticker, pd.DataFrame())

      if not df_chart.empty:
        fig = go.Figure(
            data=[
                go.Candlestick(
                    x=df_chart.index,
                    open=df_chart["Open"],
                    high=df_chart["High"],
                    low=df_chart["Low"],
                    close=df_chart["Close"],
                    increasing_line_color="#26a69a",
                    decreasing_line_color="#ef5350",
                )
            ]
        )

        fig.update_layout(
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, t=10, b=10),
            height=450,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )

        st.plotly_chart(fig, use_container_width=True)
      else:
        st.warning(f"Keine Chart-Daten für {ticker} verfügbar.")

  st.divider()

  st.subheader("Automatisches Trade-Logbuch & P&L Tracker")
  if os.path.exists(desktop_pfad):
    df_trades = pd.read_csv(desktop_pfad)
    st.dataframe(df_trades, use_container_width=True)
  else:
    st.info("Noch keine Trades in 'bot_trades.csv' gefunden.")

  st.divider()

  st.subheader("Mini-KI Gedächtnis Direkt im Dashboard Anzeigen")
  aktuelle_config = lade_config()
  st.json(aktuelle_config)


lade_live_dashboard()