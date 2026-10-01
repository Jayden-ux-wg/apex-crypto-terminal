import json
import os
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# ==========================================
# 1. SEITEN-EINSTELLUNGEN & DESIGN
# ==========================================
st.set_page_config(
    page_title="Apex Crypto Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("⚡ Apex Krypto & ETF-Terminal")
st.caption(
    "Echtzeit-Analyse, Interaktive Kerzen-Charts (TradingView-Style), "
    "Automatisches Logbuch & Adaptive Mini-KI mit P&L-Tracker"
)

# ==========================================
# 2. HILFSFUNKTIONEN (FORMATE & DATEIEN)
# ==========================================


def format_de_number(val, is_currency=True, currency_symbol="€"):
    """Formatiert Zahlen ins deutsche Format (z.B. 1.234,56 €)"""
    if pd.isna(val) or val is None:
        return "N/A"
    formatted = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} {currency_symbol}" if is_currency else formatted


def load_config():
    if os.path.exists("rsi_config.json"):
        try:
            with open("rsi_config.json", "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "rsi_period": 14,
        "overbought": 70,
        "oversold": 30,
        "krypto_hebel": 1.0,
    }


def save_config(config):
    with open("rsi_config.json", "w") as f:
        json.dump(config, f, indent=4)


def load_trades():
    if os.path.exists("bot_trades.csv"):
        try:
            return pd.read_csv("bot_trades.csv")
        except Exception:
            pass
    return pd.DataFrame(
        columns=[
            "Datum",
            "Asset",
            "Typ",
            "Kaufpreis",
            "Verkaufspreis",
            "Menge",
            "Gewinn_Verlust",
        ]
    )


def save_trades(df):
    df.to_csv("bot_trades.csv", index=False)


# ==========================================
# 3. SIDEBAR / STEUERUNG
# ==========================================
st.sidebar.header("⚙️ Einstellungen")

# Asset-Auswahl mit deutscher Beschriftung
ASSET_MAP = {
    "Bitcoin (BTC)": "BTC-USD",
    "Ethereum (ETH)": "ETH-USD",
    "Solana (SOL)": "SOL-USD",
    "Avalanche (AVAX)": "AVAX-USD",
    "iShares Bitcoin ETF (IBIT)": "IBIT",
}

selected_asset_label = st.sidebar.selectbox(
    "Wähle ein Asset aus:", list(ASSET_MAP.keys())
)
ticker_symbol = ASSET_MAP[selected_asset_label]

# Währungsauswahl (€ oder $)
currency_choice = st.sidebar.radio(
    "Anzeigewährung:", ["EUR (€)", "USD ($)"], index=0
)
currency_symbol = "€" if "EUR" in currency_choice else "$"

# Zeiträume auf Deutsch
ZEITRAUM_MAP = {
    "1 Tag": ("1d", "5m"),
    "5 Tage": ("5d", "15m"),
    "1 Monat": ("1mo", "1h"),
    "6 Monate": ("6mo", "1d"),
    "1 Jahr": ("1y", "1d"),
    "Maximal": ("max", "1wk"),
}

selected_zeitraum_label = st.sidebar.select_slider(
    "Zeitraum wählen:", options=list(ZEITRAUM_MAP.keys()), value="1 Monat"
)
period, interval = ZEITRAUM_MAP[selected_zeitraum_label]

# ==========================================
# 4. DATEN HOLEN & UMRECHNEN
# ==========================================


@st.cache_data(ttl=60)
def fetch_data(symbol, p, i):
    data = yf.download(symbol, period=p, interval=i, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data


@st.cache_data(ttl=300)
def get_usd_eur_rate():
    try:
        eur_data = yf.Ticker("EURUSD=X").history(period="1d")
        return eur_data["Close"].iloc[-1]
    except Exception:
        return 0.92  # Fallback Wechselkurs USD zu EUR


df = fetch_data(ticker_symbol, period, interval)

if df.empty:
    st.error("❌ Keine Daten gefunden. Bitte versuche es später erneut.")
    st.stop()

# Falls EUR gewählt ist, rechnen wir die USD-Kurse live um
usd_eur_rate = get_usd_eur_rate()
if currency_symbol == "€":
    for col in ["Open", "High", "Low", "Close"]:
        if col in df.columns:
            df[col] = df[col] * usd_eur_rate

# Deutsche Zeitstempel erzwingen (Europe/Berlin)
df.index = pd.to_datetime(df.index)
if df.index.tz is None:
    df.index = df.index.tz_localize("UTC").tz_convert("Europe/Berlin")
else:
    df.index = df.index.tz_convert("Europe/Berlin")

# ==========================================
# 5. KENNZAHLEN / METRIKEN
# ==========================================
aktueller_kurs = df["Close"].iloc[-1]
erster_kurs = df["Close"].iloc[0]
kurs_aenderung = aktueller_kurs - erster_kurs
prozent_aenderung = (kurs_aenderung / erster_kurs) * 100

hoch_kurs = df["High"].max()
tief_kurs = df["Low"].min()
letzte_aktualisierung = df.index[-1].strftime("%d.%m.%Y um %H:%M Uhr")

st.markdown(f"**Letztes Update:** {letzte_aktualisierung} (Deutsche Zeit)")

m1, m2, m3, m4 = st.columns(4)
m1.metric(
    label=f"Aktueller Kurs ({selected_asset_label.split(' ')[0]})",
    value=format_de_number(aktueller_kurs, True, currency_symbol),
    delta=f"{prozent_aenderung:+.2f}%",
)
m2.metric(
    label="Höchstkurs (Periode)",
    value=format_de_number(hoch_kurs, True, currency_symbol),
)
m3.metric(
    label="Tiefstkurs (Periode)",
    value=format_de_number(tief_kurs, True, currency_symbol),
)
m4.metric(
    label="Gesamtveränderung",
    value=format_de_number(kurs_aenderung, True, currency_symbol),
)

st.divider()

# ==========================================
# 6. INTERAKTIVES CHART (TRADINGVIEW-STYLE DEUTSCH)
# ==========================================
st.subheader(
    f"📈 Kerzen-Chart: {selected_asset_label} ({selected_zeitraum_label})"
)

fig = go.Figure()

fig.add_trace(
    go.Candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name="Kursverlauf",
        increasing_line_color="#00c853",
        decreasing_line_color="#ff3d00",
        text=[
            f"Datum: {d.strftime('%d.%m.%Y %H:%M')}<br>"
            f"Eröffnung: {o:,.2f} {currency_symbol}<br>"
            f"Hoch: {h:,.2f} {currency_symbol}<br>"
            f"Tief: {l:,.2f} {currency_symbol}<br>"
            f"Schluss: {c:,.2f} {currency_symbol}"
            for d, o, h, l, c in zip(
                df.index, df["Open"], df["High"], df["Low"], df["Close"]
            )
        ],
        hoverinfo="text",
    )
)

fig.update_layout(
    template="plotly_dark",
    xaxis_title="Datum / Uhrzeit",
    yaxis_title=f"Preis ({currency_symbol})",
    xaxis_rangeslider_visible=False,
    height=550,
    margin=dict(l=20, r=20, t=30, b=20),
)

fig.update_xaxes(
    tickformat="%d.%m.%Y\n%H:%M",
    gridcolor="#2a2e39",
)
fig.update_yaxes(gridcolor="#2a2e39")

st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 7. TRADING BOT / P&L TRACKER & CONFIG
# ==========================================
st.divider()
tab1, tab2 = st.tabs(
    ["📊 Bot-Logbuch & P&L Tracker", "⚙️ RSI-Indikator & KI-Einstellungen"]
)

with tab1:
    st.subheader("📋 Getätigte Trades & Performance")
    trades_df = load_trades()

    if not trades_df.empty:
        st.dataframe(trades_df, use_container_width=True)
    else:
        st.info("Noch keine Trades im Logbuch vorhanden.")

    st.markdown("---")
    st.subheader("➕ Neuen Trade manuell eintragen")
    with st.form("trade_form"):
        col_a, col_b, col_c = st.columns(3)
        trade_asset = col_a.selectbox("Asset", list(ASSET_MAP.keys()))
        trade_typ = col_b.selectbox("Typ", ["Kauf (Long)", "Verkauf (Short)"])
        trade_menge = col_c.number_input(
            "Menge", min_value=0.0001, value=1.0, step=0.01
        )

        col_d, col_e = st.columns(2)
        kaufpreis = col_d.number_input(
            f"Kaufpreis ({currency_symbol})", min_value=0.0, value=0.0
        )
        verkaufspreis = col_e.number_input(
            f"Verkaufspreis ({currency_symbol})", min_value=0.0, value=0.0
        )

        submit = st.form_submit_button("Trade Speichern")
        if submit:
            pnl = (verkaufspreis - kaufpreis) * trade_menge
            neuer_trade = {
                "Datum": datetime.now().strftime("%d.%m.%Y %H:%M"),
                "Asset": trade_asset.split(" ")[0],
                "Typ": trade_typ,
                "Kaufpreis": f"{kaufpreis:.2f} {currency_symbol}",
                "Verkaufspreis": f"{verkaufspreis:.2f} {currency_symbol}",
                "Menge": trade_menge,
                "Gewinn_Verlust": f"{pnl:+.2f} {currency_symbol}",
            }
            trades_df = pd.concat(
                [trades_df, pd.DataFrame([neuer_trade])], ignore_index=True
            )
            save_trades(trades_df)
            st.success("✅ Trade erfolgreich gespeichert!")
            st.rerun()

with tab2:
    st.subheader("🤖 RSI KI-Parameter anpassen")
    config = load_config()

    rsi_p = st.slider(
        "RSI Periode (Tage/Kerzen)",
        min_value=5,
        max_value=30,
        value=config.get("rsi_period", 14),
    )
    oversold_val = st.slider(
        "Überverkauft Signal (Kaufsignal)",
        min_value=10,
        max_value=40,
        value=config.get("oversold", 30),
    )
    overbought_val = st.slider(
        "Überkauft Signal (Verkaufsignal)",
        min_value=60,
        max_value=90,
        value=config.get("overbought", 70),
    )

    if st.button("Speichere Einstellungen"):
        neue_config = {
            "rsi_period": rsi_p,
            "overbought": overbought_val,
            "oversold": oversold_val,
            "krypto_hebel": 1.0,
        }
        save_config(neue_config)
        st.success("✅ RSI-Einstellungen erfolgreich gespeichert!")
