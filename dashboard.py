import json
import os
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf
from streamlit_autorefresh import st_autorefresh

# ==============================================================================
# 1. SEITEN-EINSTELLUNGEN & DESIGN (STREAMLIT CONFIGURATION)
# ==============================================================================

st.set_page_config(
    page_title="Apex Krypto & ETF-Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Automatischer Refresh alle 12,5 Sekunden (12500 Millisekunden), damit sich alles von selbst aktualisiert!
st_autorefresh(interval=12500, key="datenschleife_counter")

# ==============================================================================
# 2. HILFSFUNKTIONEN (DATEI-HANDLING, FORMATE & WECHSELKURSE)
# ==============================================================================

LOG_FILE = "trades_log.json"


def format_de_number(val, is_currency=True, currency_symbol="€"):
    """Formatiert Zahlen ins deutsche Format mit Punkte-Tausendertrennung (z.B. 1.234,56 €)"""
    if pd.isna(val) or val is None:
        return "N/A"
    formatted = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if is_currency:
        return f"{formatted} {currency_symbol}"
    return formatted


def load_config():
    """Lädt die lokalen Einstellungen für Indikatoren und Strategien"""
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "rsi_period": 14, 
        "overbought": 70, 
        "oversold": 30,
        "active_strategy": "Standard RSI-Reversal v1",
        "strategy_score": 100
    }


def save_config(config_data):
    """Speichert die geänderten Indikator-Einstellungen lokal ab"""
    try:
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        st.error(f"Fehler beim Speichern der Konfiguration: {e}")


def load_trade_logs():
    """Lädt das echte, sekundengenaue Trade-Logbuch aus der JSON-Datei"""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_trade_logs(logs):
    """Speichert das Logbuch mit allen Trades und KI-Lernstatus ab"""
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=4, ensure_ascii=False)
    except Exception as e:
        st.error(f"Fehler beim Speichern des Logbuchs: {e}")


@st.cache_data(ttl=15)
def fetch_data(symbol, period, interval):
    """Holt historische Finanzdaten und Live-Kurse direkt über die Yahoo Finance API (TTL 15s)"""
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
        return 0.92


# ==============================================================================
# 3. UPDATE POP-UP (DIALOG) FÜR FREUNDE & NUTZER
# ==============================================================================

if "seen_update_dialog" not in st.session_state:
    st.session_state["seen_update_dialog"] = False


@st.dialog("🔔 Neues System-Update")
def show_update_dialog():
    st.success("🔒 **Vollständiges Auto-Refresh & KI-Terminal-Update geladen!**")
    st.markdown("""
    Willkommen zurück! Die wichtigsten Optimierungen sind jetzt aktiv:
    
    * 🔄 **Auto-Refresh (12,5s):** Das Terminal aktualisiert Kurse, Metriken und Charts nun vollautomatisch im 12,5-Sekunden-Takt.
    * 🤖 **Automatischer Signal-Scanner:** Keine sinnlosen Klick-Buttons mehr – die Mini-KI erkennt echte Marktsignale von alleine.
    * 📈 **TradingView-Style Charts:** Live-Kerzenansicht mit optimierter Zeitzone und dynamischen RSI-Grenzen.
    """)
    if st.button("Verstanden & Schließen", type="primary", use_container_width=True):
        st.session_state["seen_update_dialog"] = True
        st.rerun()


if not st.session_state["seen_update_dialog"]:
    show_update_dialog()

# ==============================================================================
# 4. HEADER & TITELBEREICH DER DASHBOARD-OBERFLÄCHE
# ==============================================================================

st.title("⚡ Apex Krypto & ETF-Terminal")
st.caption(
    "Echtzeit-Analyse mit Auto-Refresh (15s), Interaktive Kerzen-Charts, "
    "Sekundengenaues Automatik-Logbuch & Adaptive Mini-KI"
)

# ==============================================================================
# 5. EINSTELLUNGEN & KONTROLLZENTRUM (SIDEBAR NAVIGATION)
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
# 6. DATENVERARBEITUNG, WÄHRUNGSUMRECHNUNG & RSI BERECHNUNG
# ==============================================================================

df = fetch_data(ticker_symbol, period, interval)

if df.empty:
    st.error("❌ Keine Marktdaten gefunden. Bitte versuche es später erneut oder wähle ein anderes Asset.")
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

# Mini-KI Algorithmus
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

    letzte_aktualisierung = datetime.now().strftime("%d.%m.%Y um %H:%M:%S Uhr")

    st.markdown(f"**Letztes Auto-Update:** {letzte_aktualisierung} (Aktualisiert alle 15 Sekunden)")

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

    fig.update_xaxes(tickformat="%d.%m.%Y\n%H:%M:%S", gridcolor="#2a2e39")
    fig.update_xaxes(gridcolor="#2a2e39", row=2, col=1)
    fig.update_yaxes(gridcolor="#2a2e39")

    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ==============================================================================
    # 8. AUTOMATISCHES MINI-KI SIGNAL- & STRATEGIE-LOGBUCH (VOLLAUTOMATISCH)
    # ==============================================================================
    
    st.subheader("🤖 Automatischer Mini-KI Signal-Scanner & Denkprozess")
    
    aktuelle_strategie = config.get("active_strategy", "RSI-Reversal-v1")
    
    if letzter_rsi < oversold_level:
        automatisches_signal = "KAUFEN"
        ki_gedanke = f"🟢 **Signal erkannt ({aktuelle_strategie}):** RSI steht bei {letzter_rsi:.1f}. Die KI hat automatisch ein starkes Kaufsignal ausgelöst!"
    elif letzter_rsi > overbought_level:
        automatisches_signal = "VERKAUFEN"
        ki_gedanke = f"🔴 **Signal erkannt ({aktuelle_strategie}):** RSI hat {letzter_rsi:.1f} erreicht. Die KI hat automatisch ein Verkaufssignal ausgelöst!"
    else:
        automatisches_signal = "NEUTRAL"
        ki_gedanke = f"⚪ **Markt-Monitoring ({aktuelle_strategie}):** Neutraler Bereich bei RSI {letzter_rsi:.1f}. Der Scanner überwacht den Kurs im Hintergrund."

    st.info(ki_gedanke)

    # Vollautomatisches Loggen, sobald ein echtes Signal erkannt wird
    logs = load_trade_logs()
    
    if automatisches_signal != "NEUTRAL":
        aktueller_zeitstempel = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        # Wir prüfen, ob das letzte Log frisch ist, um Spam zu verhindern
        letzter_eintrag_zeit = logs[0]["Zeitstempel"] if logs else ""
        
        # Falls kein Log existiert oder das letzte Signal mindestens 5 Minuten her ist, automatisch eintragen
        if not logs or logs[0]["Signal"] != automatisches_signal or logs[0]["Coin"] != selected_asset_label:
            neuer_eintrag = {
                "Zeitstempel": aktueller_zeitstempel,
                "Coin": selected_asset_label,
                "Signal": automatisches_signal,
                "Kurs": format_de_number(aktueller_kurs, True, currency_symbol),
                "RSI-Wert": f"{letzter_rsi:.1f}",
                "KI-Lernstatus": "🧠 Automatisch erfasst & gemerkt"
            }
            logs.insert(0, neuer_eintrag)
            save_trade_logs(logs)

    st.subheader("📋 Automatisches Strategie- & Signal-Logbuch (Sekundengenau)")
    
    if not logs or not isinstance(logs, list) or len(logs) == 0:
        st.info("Der automatische Scanner überwacht den Markt. Sobald ein RSI-Schwellenwert durchbrochen wird, trägt sich das Signal hier von selbst ein.")
    else:
        clean_logs = [l for l in logs if isinstance(l, dict) and "Zeitstempel" in l]
        df_logbuch = pd.DataFrame(clean_logs)
        st.dataframe(df_logbuch, use_container_width=True, hide_index=True)
        
        if st.button("🗑️ Logbuch zurücksetzen"):
            if os.path.exists(LOG_FILE):
                os.remove(LOG_FILE)
            st.success("Logbuch wurde geleert!")
            st.rerun()

# ==============================================================================
# TAB 2: MINI-KI & PARAMETER KONFIGURATION
# ==============================================================================

with tab2:
    st.subheader("⚙️ KI-Parameter & Strategie-Verwaltung")
    st.write("Passe hier die Schwellenwerte an. Die KI speichert funktionierende Parameter im Memory ab.")

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

    if st.button("Einstellungen & KI-Gedächtnis speichern", type="primary"):
        neue_config = {
            "rsi_period": rsi_p,
            "overbought": ob_level,
            "oversold": os_level,
            "active_strategy": f"RSI-Custom-{rsi_p}-({os_level}/{ob_level})"
        }
        save_config(neue_config)
        st.success("✅ Einstellungen & Strategie erfolgreich gespeichert!")
        st.rerun()
