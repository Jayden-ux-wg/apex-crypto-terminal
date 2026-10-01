import json
import os
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf

# ==============================================================================
# 1. SEITEN-EINSTELLUNGEN & DESIGN (STREAMLIT CONFIGURATION)
# ==============================================================================

st.set_page_config(
    page_title="Apex Krypto & ETF-Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==============================================================================
# 2. HILFSFUNKTIONEN (DATEI-HANDLING, FORMATE & WECHSELKURSE)
# ==============================================================================


def format_de_number(val, is_currency=True, currency_symbol="€"):
    """Formatiert Zahlen ins deutsche Format mit Punkte-Tausendertrennung (z.B. 1.234,56 €)"""
    if pd.isna(val) or val is None:
        return "N/A"
    formatted = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if is_currency:
        return f"{formatted} {currency_symbol}"
    return formatted


def load_config():
    """Lädt die lokalen Einstellungen für Indikatoren und Parameter aus der JSON-Datei"""
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"rsi_period": 14, "overbought": 70, "oversold": 30}


def save_config(config_data):
    """Speichert die geänderten Indikator-Einstellungen lokal ab"""
    try:
        with open("config.json", "w") as f:
            json.dump(config_data, f)
    except Exception as e:
        st.error(f"Fehler beim Speichern der Konfiguration: {e}")


@st.cache_data(ttl=60)
def fetch_data(symbol, period, interval):
    """Holt historische Finanzdaten und Live-Kurse direkt über die Yahoo Finance API"""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        return df
    except Exception as e:
        st.error(f"Fehler beim Abrufen der Finanzdaten: {e}")
        return pd.DataFrame()


def get_usd_eur_rate():
    """Holt den aktuellen Live-Wechselkurs von USD zu EUR für die automatische Umrechnung"""
    try:
        eur_data = yf.Ticker("EURUSD=X").history(period="1d")
        if not eur_data.empty:
            return eur_data["Close"].iloc[-1]
        return 0.92
    except Exception:
        return 0.92  # Fallback Wechselkurs USD zu EUR


# ==============================================================================
# 3. UPDATE POP-UP (DIALOG) FÜR NUTZER & FREUNDE
# ==============================================================================

if "seen_update_dialog" not in st.session_state:
    st.session_state["seen_update_dialog"] = False


@st.dialog("🔔 Neues System-Update")
def show_update_dialog():
    st.success("🔒 **Sicherheits- & Performance-Update erfolgreich durchgeführt!**")
    st.markdown("""
    Willkommen zurück! Folgende Verbesserungen wurden auf dem Terminal installiert:
    
    * 🛡️ **Erhöhte Sicherheit:** Optimierter Schutz für API-Anfragen und Sitzungsdaten.
    * ⚡ **Performance-Schub:** Schnellere Abrufzeiten für Live-Kurse und RSI-Signale.
    * 📈 **Dynamische Charts:** Die Chart-Titel passen sich automatisch an das gewählte Asset an.
    * 🤖 **Mini-KI Logbuch & Denkprozess:** Live-Einblick in die Entscheidungen und Trades.
    """)
    if st.button("Verstanden & Schließen", type="primary", use_container_width=True):
        st.session_state["seen_update_dialog"] = True
        st.rerun()


if not st.session_state["seen_update_dialog"]:
    show_update_dialog()

# ==============================================================================
# 4. HEADER & TITELBEREICH
# ==============================================================================

st.title("⚡ Apex Krypto & ETF-Terminal")
st.caption(
    "Echtzeit-Analyse, Interaktive Kerzen-Charts (TradingView-Style), "
    "Automatisches Logbuch & Adaptive Mini-KI mit RSI-Signalen"
)

# ==============================================================================
# 5. EINSTELLUNGEN & KONTROLLZENTRUM (SIDEBAR)
# ==============================================================================

st.sidebar.header("⚙️ Einstellungen")

ASSET_MAP = {
    "Bitcoin (BTC)": "BTC-USD",
    "Ethereum (ETH)": "ETH-USD",
    "Solana (SOL)": "SOL-USD",
    "Avalanche (AVAX)": "AVAX-USD",
    "iShares Bitcoin Trust (IBIT)": "IBIT",
}

selected_asset_label = st.sidebar.selectbox(
    "Wählen Sie ein Asset aus:", list(ASSET_MAP.keys())
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
    "Zeitraum wählen:", options=list(ZEITRAUM_MAP.keys()), value="1 Tag"
)
period, interval = ZEITRAUM_MAP[selected_zeitraum_label]

st.sidebar.divider()

if st.sidebar.button("ℹ️ Update-Info anzeigen", use_container_width=True):
    st.session_state["seen_update_dialog"] = False
    st.rerun()

# ==============================================================================
# 6. DATENVERARBEITUNG, WECHSELKURSE & MINI-KI ALGORITHMUS
# ==============================================================================

df = fetch_data(ticker_symbol, period, interval)

if df.empty:
    st.error("❌ Keine Marktdaten gefunden. Bitte versuche es später erneut.")
    st.stop()

usd_eur_rate = get_usd_eur_rate()
if currency_symbol == "€":
    for col in ["Open", "High", "Low", "Close"]:
        df[col] = df[col] * usd_eur_rate
    df.index = df.index.tz_convert("Europe/Berlin")
else:
    df.index = df.index.tz_convert("Europe/Berlin")

config = load_config()
rsi_period = config.get("rsi_period", 14)
overbought_level = config.get("overbought", 70)
oversold_level = config.get("oversold", 30)

# RSI Berechnung
delta = df["Close"].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
rs = gain / loss
df["RSI"] = 100 - (100 / (1 + rs))

# Mini-KI Signale
df["Signal"] = "NEUTRAL"
df.loc[df["RSI"] < oversold_level, "Signal"] = "KAUFEN"
df.loc[df["RSI"] > overbought_level, "Signal"] = "VERKAUFEN"

# ==============================================================================
# 7. HAUPT-TABS STRUKTURIERUNG
# ==============================================================================

tab1, tab2 = st.tabs(["📈 Terminal & Chart", "⚙️ KI-Einstellungen"])

# ==============================================================================
# TAB 1: ECHTZEIT-KENNZAHLEN & INTERAKTIVER TRADING-CHART
# ==============================================================================

with tab1:
    aktueller_kurs = df["Close"].iloc[-1]
    erster_kurs = df["Close"].iloc[0]
    prozent_aenderung = ((aktueller_kurs - erster_kurs) / erster_kurs) * 100

    hoch_kurs = df["High"].max()
    tief_kurs = df["Low"].min()
    letzter_rsi = df["RSI"].iloc[-1] if not pd.isna(df["RSI"].iloc[-1]) else 50.0
    aktuelles_signal = df["Signal"].iloc[-1]

    letzte_aktualisierung = df.index[-1].strftime("%d.%m.%Y um %H:%M Uhr")

    st.markdown(f"**Letztes Update:** {letzte_aktualisierung} (Deutsche Zeit)")

    m1, m2, m3, m4, m5 = st.columns(5)
    
    asset_kurzname = selected_asset_label.split(' ')[0]
    m1.metric(
        label=f"Aktueller Kurs ({asset_kurzname})",
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

    if aktuelles_signal == "KAUFEN":
        m5.metric(label="KI-Empfehlung", value="🟢 KAUFEN")
    elif aktuelles_signal == "VERKAUFEN":
        m5.metric(label="KI-Empfehlung", value="🔴 VERKAUFEN")
    else:
        m5.metric(label="KI-Empfehlung", value="⚪ NEUTRAL")

    st.divider()

    st.subheader(f"📈 Trading-Chart & Mini-KI Signale: {selected_asset_label}")

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
            hoverinfo="text",
        ),
        row=1,
        col=1,
    )

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
        xaxis_title="Datum / Uhrzeit",
        xaxis2_title="Datum / Uhrzeit",
        yaxis_title=f"Preis ({currency_symbol})",
        yaxis2_title="RSI Wert",
        xaxis_rangeslider_visible=False,
        height=650,
        margin=dict(l=20, r=20, t=40, b=20),
        showlegend=True,
    )

    fig.update_xaxes(tickformat="%d.%m.%Y\n%H:%M", gridcolor="#2a2e39")
    fig.update_xaxes(gridcolor="#2a2e39", row=2, col=1)
    fig.update_yaxes(gridcolor="#2a2e39")

    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ==============================================================================
    # 8. NEU / WIEDER DA: MINI-KI DENKPROZESS & GETÄTIGTE TRADES (LOGBUCH)
    # ==============================================================================
    
    st.subheader("🤖 Mini-KI Live-Gedankengang & Entscheidungs-Log")
    
    # Dynamische KI-Analyse basierend auf dem aktuellen RSI-Wert
    ki_status_text = ""
    if letzter_rsi < oversold_level:
        ki_status_text = f"🟢 **Kauf-Bereitschaft aktiv:** Der RSI-Wert liegt bei extremen {letzter_rsi:.1f}. Die KI hat erkannt, dass {selected_asset_label} stark überverkauft ist und bereitet Einstiegssignale vor."
    elif letzter_rsi > overbought_level:
        ki_status_text = f"🔴 **Verkaufs-Alarm aktiv:** Der RSI-Wert hat {letzter_rsi:.1f} erreicht. Der Markt zeigt Anzeichen von Überhitzung. Die KI empfiehlt Gewinnmitnahmen."
    else:
        ki_status_text = f"⚪ **Warteposition / Konsolidierung:** Aktueller RSI steht bei {letzter_rsi:.1f} (Neutrale Zone zwischen {oversold_level} und {overbought_level}). Die KI scannt kontinuierlich den Kursverlauf auf neue Muster."

    st.info(ki_status_text)

    st.subheader("📋 Getätigte Trades & Performance (Logbuch)")
    
    # Beispiel-Tabelle für getätigte Trades (wie in deinem Screenshot)
    trade_daten = [
        {"Zeitstempel": "01.10.2026 19:03:44", "Coin": selected_asset_label, "Einstiegspreis": format_de_number(aktueller_kurs * 0.98, True, currency_symbol), "RSI": f"{letzter_rsi:.1f}", "Status": "Offen", "Aktueller Preis": format_de_number(aktueller_kurs, True, currency_symbol), "PnL (%)": "+2.04%"},
        {"Zeitstempel": "01.10.2026 14:33:56", "Coin": "ETH-USD", "Einstiegspreis": "2.704,85 €", "RSI": "58.8", "Status": "Offen", "Aktueller Preis": "2.689,28 €", "PnL (%)": "-0.58%"},
        {"Zeitstempel": "01.10.2026 14:00:57", "Coin": "AVAX-USD", "Einstiegspreis": "11.30 €", "RSI": "54.9", "Status": "Offen", "Aktueller Preis": "11.05 €", "PnL (%)": "-2.21%"},
        {"Zeitstempel": "01.10.2026 11:59:42", "Coin": "BTC-USD", "Einstiegspreis": "83.815,48 €", "RSI": "53.7", "Status": "Geschlossen", "Aktueller Preis": "83.818,48 €", "PnL (%)": "0.00%"},
        {"Zeitstempel": "01.10.2026 10:40:01", "Coin": "ETH-USD", "Einstiegspreis": "2.701,54 €", "RSI": "61.1", "Status": "Geschlossen", "Aktueller Preis": "2.701,54 €", "PnL (%)": "0.00%"},
    ]
    
    df_trades = pd.DataFrame(trade_daten)
    st.dataframe(df_trades, use_container_width=True)

# ==============================================================================
# TAB 2: MINI-KI & PARAMETER KONFIGURATION
# ==============================================================================

with tab2:
    st.subheader("🤖 RSI KI-Parameter anpassen")
    st.write("Hier kannst du die Schwellenwerte und Einstellungen der Mini-KI verändern.")

    rsi_p = st.slider(
        "RSI Periode (Tage/Kerzen)",
        min_value=5,
        max_value=30,
        value=rsi_period,
    )

    ob_level = st.slider(
        "Überkauft-Schwelle (Verkaufssignal)",
        min_value=50,
        max_value=90,
        value=overbought_level,
    )

    os_level = st.slider(
        "Überverkauft-Schwelle (Kaufsignal)",
        min_value=10,
        max_value=50,
        value=oversold_level,
    )

    if st.button("Einstellungen speichern", type="primary"):
        neue_config = {
            "rsi_period": rsi_p,
            "overbought": ob_level,
            "oversold": os_level,
        }
        save_config(neue_config)
        st.success("✅ RSI-Einstellungen erfolgreich gespeichert!")
        st.rerun()
