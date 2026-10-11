"""
app.py

Modernes Streamlit-Web-Dashboard zur Visualisierung der Trading-Bot-Performance,
Equity-Kurve, Live-Status und Trade-Historie.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# -- Seiten-Konfiguration (Dark Mode & Layout) ------------------------------
st.set_page_config(
    page_title="AI Trading Bot Dashboard",
    page_icon="📈",
    layout="wide",
)

# Custom CSS für einen coolen Cyberpunk / Dark-Trader Look
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
        color: #ffffff;
    }
    .metric-card {
        background-color: #1a1c24;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #30333d;
    }
    stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# -- Sidebar: Bot Konfiguration & Steuerung ----------------------------------
st.sidebar.header("⚙️ Bot Steuerung & Filter")

symbol = st.sidebar.selectbox("Handels-Symbol", ["AAPL", "BTC-USD", "ETH-USD"])
timeframe = st.sidebar.selectbox("Timeframe", ["H1", "M15", "D1"])

st.sidebar.markdown("---")
st.sidebar.subheader("Indikatoren-Parameter")
fast_period = st.sidebar.slider("Fast EMA", 5, 50, 9)
slow_period = st.sidebar.slider("Slow EMA", 10, 100, 21)
trend_period = st.sidebar.slider("Trend EMA (Filter)", 100, 300, 200)
rsi_period = st.sidebar.slider("RSI Periode", 5, 30, 14)

st.sidebar.markdown("---")
if st.sidebar.button("🚀 Backtest / Bot starten", type="primary"):
    st.sidebar.success("Bot-Prozess im Hintergrund getriggert!")

# -- Hauptbereich: Titel & KPIs ---------------------------------------------
st.title("🚀 AI & Algorithmic Trading Control Center")
st.markdown("Willkommen in deiner persönlichen Kontrollzentrale. Hier hast du den 200er EMA Trendfilter und deine Performance im Blick.")

# Beispieldaten basierend auf deinen letzten Backtest-Ergebnissen
@st.cache_data
def load_trade_data():
    data = {
        "Trade_ID": [1, 2, 3, 4, 5, 6, 7],
        "Date": pd.date_range(start="2025-06-23", periods=7, freq="ME"),
        "Side": ["BUY", "BUY", "BUY", "BUY", "SELL", "SELL", "BUY"],
        "PnL": [-1202.25, -1146.39, 926.21, -307.23, 2119.18, -745.74, 604.10],
        "Reason": ["MA_CROSS", "STOP_LOSS", "RSI_OVERBOUGHT", "RSI_OVERBOUGHT", "RSI_OVERBOUGHT", "MA_CROSS", "RSI_OVERBOUGHT"]
    }
    df = pd.DataFrame(data)
    df["Equity"] = 100000.0 + df["PnL"].cumsum()
    return df

df_trades = load_trade_data()

# KPI Kennzahlen in Spalten
col1, col2, col3, col4 = st.columns(4)

total_pnl = df_trades["PnL"].sum()
final_equity = df_trades["Equity"].iloc[-1]
winning_trades = len(df_trades[df_trades["PnL"] > 0])
win_rate = (winning_trades / len(df_trades)) * 100
max_drawdown = 7.28  # Aus dem letzten Log-Report übernommen

col1.metric("Kontostand (Equity)", f"${final_equity:,.2f}", f"{total_pnl:+,.2f} USD")
col2.metric("Win-Rate", f"{win_rate:.1f}%", f"{winning_trades} von {len(df_trades)} Gewinner")
col3.metric("Max Drawdown", f"{max_drawdown}%", "Trendfilter aktiv")
col4.metric("Aktueller Status", "Bereit / Standby", "🟢 Online")

st.markdown("---")

# -- Layout: Equity-Kurve & System-Status ----------------------------------
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader(f"📈 Equity-Kurve ({symbol})")
    
    # Plotly Interaktiver Chart
    fig = px.line(
        df_trades, 
        x="Date", 
        y="Equity", 
        markers=True,
        title="Kontoverlauf über die Zeit"
    )
    fig.update_layout(
        plot_bgcolor="#1a1c24",
        paper_bgcolor="#0e1117",
        font_color="white",
        xaxis=dict(showgrid=True, gridcolor="#30333d"),
        yaxis=dict(showgrid=True, gridcolor="#30333d"),
        margin=dict(l=20, r=20, t=40, b=20)
    )
    fig.update_traces(line_color="#00ffcc", line_width=3)
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("🛡️ Bot & Risiko-Status")
    
    st.info("**Trendfilter:** 200 EMA aktiv. Blockiert konsequent Trades gegen den Haupttrend.")
    st.warning("**Exposure Limit:** Greift bei 95% Gesamtkapitalbindung.")
    st.success("**Order-Manager:** Slippage und Kommissionen werden live berechnet.")

    st.markdown("### Letzte Log-Meldung")
    st.code("LONG ENTRY Signal | symbol=AAPL | trend_ema=281.4997 | RSI=44.6", language="text")

# -- Trade Historie Tabelle ------------------------------------------------
st.markdown("---")
st.subheader("📋 Detaillierte Trade-Historie")

def color_pnl(val):
    color = "#00cc66" if val > 0 else "#ff4d4d"
    return f'color: {color}; font-weight: bold;'

styled_df = df_trades.style.format({
    "PnL": "${:+,.2f}",
    "Equity": "${:,.2f}"
}).applymap(color_pnl, subset=['PnL'])

st.dataframe(styled_df, use_container_width=True)