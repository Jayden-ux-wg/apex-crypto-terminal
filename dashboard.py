import json
import os
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
    "Automatisches Logbuch & Adaptive Mini-KI mit RSI-Signalen"
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

currency_choice = st.sidebar.radio(
    "Anzeigewährung:", ["EUR (€)", "USD ($)"], index=0
)
currency_symbol = "€" if "EUR" in currency_choice else "$"

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
# 4. DATEN HOLEN, UMRECHNEN & RSI ALGORITHMUS (MINI-KI)
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
        return 0.92


df = fetch_data(ticker_symbol, period, interval)

if df.empty:
    st.error("❌ Keine Daten gefunden. Bitte versuche es später erneut.")
    st.stop()

# EUR-Umrechnung
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

# Config laden für KI / RSI Algorithmus
config = load_config()
rsi_period = config.get("rsi_period", 14)
overbought_level = config.get("overbought", 70)
oversold_level = config.get("oversold", 30)

# ------------------------------------------
# MATHE: RSI BERECHNUNG & KI-SIGNALE
# ------------------------------------------
delta = df["Close"].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
rs = gain / loss
df["RSI"] = 100 - (100 / (1 + rs))

# KI Signal-Generierung (Kauf/Verkauf)
df["Signal"] = "NEUTRAL"
df.loc[df["RSI"] < oversold_level, "Signal"] = "KAUFEN"
df.loc[df["RSI"] > overbought_level, "Signal"] = "VERKAUFEN"

# ==========================================
# 5. KENNZAHLEN / METRIKEN
# ==========================================
aktueller_kurs = df["Close"].iloc[-1]
erster_kurs = df["Close"].iloc[0]
kurs_aenderung = aktueller_kurs - erster_kurs
prozent_aenderung = (kurs_aenderung / erster_kurs) * 100

hoch_kurs = df["High"].max()
tief_kurs = df["Low"].min()
letzter_rsi = (
    df["RSI"].iloc[-1] if not pd.isna(df["RSI"].iloc[-1]) else 50.0
)
aktuelles_signal = df["Signal"].iloc[-1]

letzte_aktualisierung = df.index[-1].strftime("%d.%m.%Y um %H:%M Uhr")

st.markdown(f"**Letztes Update:** {letzte_aktualisierung} (Deutsche Zeit)")

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric(
    label=f"Aktueller Kurs ({selected_asset_label.split(' ')[0]})",
    value=format_de_number(aktueller_kurs, True, currency_symbol),
    delta=f"{prozent_aenderung:+.2f}%",
)
m2.metric(
    label="Höchstkurs",
    value=format_de_number(hoch_kurs, True, currency_symbol),
)
m3.metric(
    label="Tiefstkurs",
    value=format_de_number(tief_kurs, True, currency_symbol),
)
m4.metric(
    label="RSI Wert",
    value=f"{letzter_rsi:.1f}",
)

# Signal Status mit Symbol & Farbe
if aktuelles_signal == "KAUFEN":
    m5.metric(label="KI-Empfehlung", value="🟢 KAUFEN")
elif aktuelles_signal == "VERKAUFEN":
    m5.metric(label="KI-Empfehlung", value="🔴 VERKAUFEN")
else:
    m5.metric(label="KI-Empfehlung", value="⚪ NEUTRAL")

st.divider()

# ==========================================
# 6. CHART MIT SUBPLOT (KERZEN + RSI + SIGNALE)
# ==========================================
st.subheader(
    f"📈 Trading-Chart & Mini-KI Signale: {selected_asset_label}"
)

# Subplot: Oben Kerzen (70% Höhe), Unben RSI (30% Höhe)
fig = make_subplots(
    rows=2,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.05,
    row_heights=[0.7, 0.3],
    subplot_titles=(
        "Kursverlauf & KI-Kauf/Verkaufssignale",
        f"RSI Indikator ({rsi_period})",
    ),
)

# 1. Kerzenchart
fig.add_trace(
    go.Candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name="Kurs",
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
    ),
    row=1,
    col=1,
)

# Kaufsignale (Grüne Dreiecke) im Chart
kauf_df = df[df["Signal"] == "KAUFEN"]
if not kauf_df.empty:
    fig.add_trace(
        go.Scatter(
            x=kauf_df.index,
            y=kauf_df["Low"] * 0.99,
            mode="markers",
            marker=dict(symbol="triangle-up", size=11, color="#00c853"),
            name="KI Kaufsignal",
            text="🟢 KI Kaufsignal (RSI Überverkauft)",
            hoverinfo="text",
        ),
        row=1,
        col=1,
    )

# Verkaufssignale (Rote Dreiecke) im Chart
verkauf_df = df[df["Signal"] == "VERKAUFEN"]
if not verkauf_df.empty:
    fig.add_trace(
        go.Scatter(
            x=verkauf_df.index,
            y=verkauf_df["High"] * 1.01,
            mode="markers",
            marker=dict(symbol="triangle-down", size=11, color="#ff3d00"),
            name="KI Verkaufssignal",
            text="🔴 KI Verkaufssignal (RSI Überkauft)",
            hoverinfo="text",
        ),
        row=1,
        col=1,
    )

# 2. RSI Verlauf im unteren Subplot
fig.add_trace(
    go.Scatter(
        x=df.index,
        y=df["RSI"],
        mode="lines",
        name="RSI",
        line=dict(color="#29b6f6", width=1.5),
    ),
    row=2,
    col=1,
)

# RSI Schwellenlinien
fig.add_hline(
    y=overbought_level,
    line_dash="dash",
    line_color="#ff3d00",
    row=2,
    col=1,
    annotation_text="Überkauft",
)
fig.add_hline(
    y=oversold_level,
    line_dash="dash",
    line_color="#00c853",
    row=2,
    col=1,
    annotation_text="Überverkauft",
)

fig.update_layout(
    template="plotly_dark",
    xaxis2_title="Datum / Uhrzeit",
    yaxis_title=f"Preis ({currency_symbol})",
    yaxis2_title="RSI Wert",
    xaxis_rangeslider_visible=False,
    height=650,
    margin=dict(l=20, r=20, t=40, b=20),
    showlegend=True,
)

fig.update_xaxes(gridcolor="#2a2e39")
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
        st.rerun()
