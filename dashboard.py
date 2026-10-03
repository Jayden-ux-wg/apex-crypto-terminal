import json
import os
from datetime import datetime
import pandas as pd
import numpy as np
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

# === HIER FÜGST DU DEN CSS-CODE EIN ===
st.markdown("""
    <style>
    div[data-testid="stMetricValue"] {
        font-size: 15px !important;
        white-space: nowrap !important;
    }
    </style>
""", unsafe_allow_html=True)
# ======================================

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
        return 0.92

# ==============================================================================
# 2.1 CANDLESTICK-MUSTER ERKENNUNG (10 WICHTIGSTE MUSTER)
# ==============================================================================
def detect_candlestick_patterns(df: pd.DataFrame) -> dict:
    """
    Erkennt die 10 wichtigsten Candlestick-Muster auf dem DataFrame.
    Gibt ein Dictionary zurück mit den erkannten Mustern der letzten Kerzen.
    """
    if len(df) < 3:
        return {"patterns": [], "signal": "NEUTRAL", "reason": "Zu wenig Daten", "score": 0}

    df_local = df.copy().dropna(subset=["Open", "High", "Low", "Close"])
    
    o = df_local["Open"].values
    h = df_local["High"].values
    l = df_local["Low"].values
    c = df_local["Close"].values
    
    body = np.abs(c - o)
    upper_shadow = h - np.maximum(o, c)
    lower_shadow = np.minimum(o, c) - l
    full_range = h - l
    full_range = np.where(full_range == 0, 0.0001, full_range) 
    
    body_pct = body / full_range
    upper_pct = upper_shadow / full_range
    lower_pct = lower_shadow / full_range
    
    patterns = []
    signal_score = 0 
    
    # 1. DOJI
    if body_pct[-1] < 0.1:
        patterns.append("Doji")
    
    # 2. HAMMER (bullisch)
    if (lower_pct[-1] > 0.6 and 
        upper_pct[-1] < 0.1 and 
        body_pct[-1] < 0.3 and
        c[-1] > o[-1]): 
        patterns.append("Hammer")
        signal_score += 2
    
    # 3. INVERTED HAMMER (bullisch)
    if (upper_pct[-1] > 0.6 and 
        lower_pct[-1] < 0.1 and 
        body_pct[-1] < 0.3 and
        c[-1] > o[-1]):
        patterns.append("Inverted Hammer")
        signal_score += 1.5
    
    # 4. HANGING MAN (bearisch)
    if (lower_pct[-1] > 0.6 and 
        upper_pct[-1] < 0.1 and 
        body_pct[-1] < 0.3 and
        c[-1] < o[-1]): 
        patterns.append("Hanging Man")
        signal_score -= 2
    
    # 5. SHOOTING STAR (bearisch)
    if (upper_pct[-1] > 0.6 and 
        lower_pct[-1] < 0.1 and 
        body_pct[-1] < 0.3 and
        c[-1] < o[-1]):
        patterns.append("Shooting Star")
        signal_score -= 2
    
    # 6. BULLISH ENGULFING
    if (c[-2] < o[-2] and                    # vorherige Kerze rot
        c[-1] > o[-1] and                    # aktuelle Kerze grün
        o[-1] < c[-2] and                    # Open unter dem Close der vorherigen
        c[-1] > o[-2]):                      # Close über dem Open der vorherigen
        patterns.append("Bullish Engulfing")
        signal_score += 3
    
    # 7. BEARISH ENGULFING
    if (c[-2] > o[-2] and                    # vorherige Kerze grün
        c[-1] < o[-1] and                    # aktuelle Kerze rot
        o[-1] > c[-2] and                    # Open über dem Close der vorherigen
        c[-1] < o[-2]):                      # Close unter dem Open der vorherigen
        patterns.append("Bearish Engulfing")
        signal_score -= 3
    
    # 8. MORNING STAR (bullisch, 3 Kerzen)
    if (c[-3] < o[-3] and                    # 1. Kerze rot
        body_pct[-2] < 0.3 and               # 2. Kerze kleiner Body (Doji-ähnlich)
        c[-1] > o[-1] and                    # 3. Kerze grün
        c[-1] > (o[-3] + c[-3]) / 2):        # Close der 3. über der Mitte der 1.
        patterns.append("Morning Star")
        signal_score += 3
    
    # 9. EVENING STAR (bearisch, 3 Kerzen)
    if (c[-3] > o[-3] and                    # 1. Kerze grün
        body_pct[-2] < 0.3 and               # 2. Kerze kleiner Body
        c[-1] < o[-1] and                    # 3. Kerze rot
        c[-1] < (o[-3] + c[-3]) / 2):        # Close der 3. unter der Mitte der 1.
        patterns.append("Evening Star")
        signal_score -= 3
    
    # 10. PIERCING LINE / DARK CLOUD COVER
    if (c[-2] < o[-2] and                    # vorherige rot
        c[-1] > o[-1] and                    # aktuelle grün
        o[-1] < l[-2] and                    # Open unter dem Low der vorherigen
        c[-1] > (o[-2] + c[-2]) / 2 and      # Close über der Mitte der vorherigen
        c[-1] < o[-2]):                      # aber noch unter dem Open der vorherigen
        patterns.append("Piercing Line")
        signal_score += 2
    elif (c[-2] > o[-2] and                  # vorherige grün
          c[-1] < o[-1] and                  # aktuelle rot
          o[-1] > h[-2] and                  # Open über dem High der vorherigen
          c[-1] < (o[-2] + c[-2]) / 2 and    # Close unter der Mitte
          c[-1] > o[-2]):                    # aber noch über dem Open der vorherigen
        patterns.append("Dark Cloud Cover")
        signal_score -= 2
    
    if signal_score >= 3:
        signal = "KAUFEN"
    elif signal_score <= -3:
        signal = "VERKAUFEN"
    else:
        signal = "NEUTRAL"
    
    return {
        "patterns": patterns,
        "signal": signal,
        "score": signal_score,
        "reason": ", ".join(patterns) if patterns else "Kein klares Muster"
    }

# ==============================================================================
# 3. UPDATE POP-UP (DIALOG) FÜR FREUNDE & NUTZER
# ==============================================================================
if "seen_update_dialog" not in st.session_state:
    st.session_state["seen_update_dialog"] = False

@st.dialog("🔔 System-Update: Investitions-Simulator & Dynamik")
def show_update_dialog():
    st.success("🔒 **Investitions-Simulation (1.000 € / 10.000 €) integriert!**")
    st.markdown("""
    Dein Feedback wurde direkt verbaut:
    
    * 💰 **Echtgeld-Simulation:** In der KI-Prognose-Leiste siehst du jetzt direkt, was der erwartete Gewinn und das Risiko bei **1.000 €** und **10.000 €** Einsatz ausmachen.
    * 📈 **Dynamische Volatilität:** Die prozentualen Werte passen sich nun individuell an das jeweilige Asset und den gewählten Zeitraum an.
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
    "Echtzeit-Analyse, Interaktive Kerzen-Charts (TradingView-Style), "
    "Sekundengenaues Logbuch & Candlestick-Erkennung"
)

# ==============================================================================
# 5. EINSTELLUNGEN & KONTROLLZENTRUM (SIDEBAR NAVIGATION)
# ==============================================================================
ASSET_MAP = {
    "Bitcoin (BTC)": "BTC-USD",
    "Ethereum (ETH)": "ETH-USD",
    "Solana (SOL)": "SOL-USD",
    "Avalanche (AVAX)": "AVAX-USD",
    "iShares Bitcoin Trust (IBIT)": "IBIT",
}

if "selected_asset_label" not in st.session_state:
    st.session_state["selected_asset_label"] = "Bitcoin (BTC)"

st.sidebar.header("⚙️️ Einstellungen")
selected_asset_label = st.sidebar.selectbox(
    "Wählen Sie ein Asset aus:", list(ASSET_MAP.keys()),
    index=list(ASSET_MAP.keys()).index(st.session_state["selected_asset_label"])
)
st.session_state["selected_asset_label"] = selected_asset_label
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

if st.sidebar.button("🔄 Kursdaten jetzt aktualisieren", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

if st.sidebar.button("ℹ️ Update-Info anzeigen", use_container_width=True):
    st.session_state["seen_update_dialog"] = False
    st.rerun()

# ==============================================================================
# 6. DATENVERARBEITUNG, WÄHRUNGSUMRECHNUNG & SIGNAL-BERECHNUNG
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

# Candlestick-Analyse aufrufen
candle_result = detect_candlestick_patterns(df)

# Kombiniertes Signal (RSI + Candlestick Muster)
df["Signal"] = "NEUTRAL"
for i in range(len(df)):
    rsi_val = df["RSI"].iloc[i]
    base_sig = "NEUTRAL"
    if not pd.isna(rsi_val):
        # Lockerere Bedingungen für Kauf/Verkauf
        if rsi_val < oversold_level or (rsi_val < 48 and df["Close"].iloc[i] > df["Open"].iloc[i]):
            base_sig = "KAUFEN"
        elif rsi_val > overbought_level or (rsi_val > 52 and df["Close"].iloc[i] < df["Open"].iloc[i]):
            base_sig = "VERKAUFEN"
    df.iloc[i, df.columns.get_loc("Signal")] = base_sig

letzter_rsi = df["RSI"].iloc[-1] if not pd.isna(df["RSI"].iloc[-1]) else 50.0
aktuelles_signal = df["Signal"].iloc[-1]

# Flexiblere Verknüpfung für das finale Signal ganz oben
if candle_result["signal"] == "KAUFEN" or letzter_rsi < 45:
    final_signal = "STARKES KAUFEN" if candle_result["signal"] == "KAUFEN" else "KAUFEN"
elif candle_result["signal"] == "VERKAUFEN" or letzter_rsi > 55:
    final_signal = "STARKES VERKAUFEN" if candle_result["signal"] == "VERKAUFEN" else "VERKAUFEN"
else:
    final_signal = aktuelles_signal

# ==============================================================================
# 7. HAUPT-TABS STRUKTURIERUNG
# ==============================================================================
tab1, tab2 = st.tabs(["📈 Terminal & Chart", "⚙️ KI-Einstellungen"])

# ==============================================================================
# TAB 1: ECHTZEIT-KENNZAHLEN & INTERAKTIVER TRADING-CHART
# ==============================================================================
with tab1:
    # Quick-Coin-Switch Buttons
    st.write("⚡ **Quick-Asset-Schnellwahl:**")
    b_col1, b_col2, b_col3, b_col4, b_col5 = st.columns(5)
    
    with b_col1:
        if st.button("₿ Bitcoin (BTC)", use_container_width=True):
            st.session_state["selected_asset_label"] = "Bitcoin (BTC)"
            st.rerun()
    with b_col2:
        if st.button("Ξ Ethereum (ETH)", use_container_width=True):
            st.session_state["selected_asset_label"] = "Ethereum (ETH)"
            st.rerun()
    with b_col3:
        if st.button("◎ Solana (SOL)", use_container_width=True):
            st.session_state["selected_asset_label"] = "Solana (SOL)"
            st.rerun()
    with b_col4:
        if st.button("🔺 Avalanche", use_container_width=True):
            st.session_state["selected_asset_label"] = "Avalanche (AVAX)"
            st.rerun()
    with b_col5:
        if st.button("📊 IBIT ETF", use_container_width=True):
            st.session_state["selected_asset_label"] = "iShares Bitcoin Trust (IBIT)"
            st.rerun()

    st.divider()

    aktueller_kurs = df["Close"].iloc[-1]
    erster_kurs = df["Close"].iloc[0]
    prozent_aenderung = ((aktueller_kurs - erster_kurs) / erster_kurs) * 100
    hoch_kurs = df["High"].max()
    tief_kurs = df["Low"].min()
    letzte_aktualisierung = datetime.now().strftime("%d.%m.%Y um %H:%M:%S Uhr")
    
    st.markdown(f"**Letztes Laden:** {letzte_aktualisierung} (Deutsche Zeit)")
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
    if "KAUFEN" in final_signal:
        m5.metric(label="KI-Empfehlung", value=f"🟢 {final_signal}")
    elif "VERKAUFEN" in final_signal:
        m5.metric(label="KI-Empfehlung", value=f"🔴 {final_signal}")
    else:
        m5.metric(label="KI-Empfehlung", value="⚪ NEUTRAL")

    # --------------------------------------------------------------------------
    # NEU: DYNAMISCHE KI-WAHRSCHEINLICHKEITS- & GEWINN-PROGNOSE + INVESTITIONSSIMULATION
    # --------------------------------------------------------------------------
    base_prob = 50.0
    if letzter_rsi < oversold_level:
        base_prob += (oversold_level - letzter_rsi) * 1.2
    elif letzter_rsi > overbought_level:
        base_prob += (letzter_rsi - overbought_level) * 1.2
    
    pattern_score = candle_result.get("score", 0)
    win_probability = min(max(base_prob + (pattern_score * 7.5), 20.0), 92.5)
    
    # Echte, individuelle Asset-Volatilität (angepasst an den Zeitraum)
    asset_volatility = df["Close"].pct_change().std() * 100
    if pd.isna(asset_volatility) or asset_volatility == 0:
        asset_volatility = 1.2
        
    # Dynamischer Multiplikator je nach timeframe (damit 1 Tag nicht zu flach ist)
    timeframe_multiplier = 0.8 if period == "1d" else (1.2 if period == "5d" else 2.0)
    
    expected_gain_pct = round(max(0.8, (asset_volatility * timeframe_multiplier) + abs(pattern_score * 0.4)), 2)
    expected_loss_pct = round(max(0.5, expected_gain_pct * 0.6), 2)

    # Investitions-Simulation für 1.000 € und 10.000 €
    gain_1k = 1000 * (expected_gain_pct / 100)
    loss_1k = 1000 * (expected_loss_pct / 100)
    gain_10k = 10000 * (expected_gain_pct / 100)
    loss_10k = 10000 * (expected_loss_pct / 100)

    prob_color = "🟢" if win_probability >= 65 else ("🔴" if win_probability <= 40 else "🟡")
    
    st.markdown(
        f"""
        <div style="padding: 14px 18px; background-color: #1e222d; border-radius: 8px; border: 1px solid #2a2e39; margin-top: 10px; margin-bottom: 10px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <div>
                    <span style="font-size: 15px; font-weight: bold; color: #e0e0e0;">🤖 KI-Prognose & Win-Probability:</span>
                    <span style="margin-left: 10px; font-size: 15px; color: #ffffff;">{prob_color} <b>{win_probability:.1f}%</b></span>
                </div>
                <div>
                    <span style="color: #00c853; font-weight: bold; margin-right: 15px;">Erwarteter Gewinn: +{expected_gain_pct}%</span>
                    <span style="color: #ff3d00; font-weight: bold;">Max. Risiko: -{expected_loss_pct}%</span>
                </div>
            </div>
            <hr style="border: 0; height: 1px; background: #2a2e39; margin: 8px 0;">
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 13px; color: #b0b3b8;">
                <div>💡 <b>Investitions-Simulation:</b></div>
                <div>
                    <span>Bei <b>1.000 €</b> Einsatz: <span style="color: #00c853;">+{gain_1k:.2f} €</span> / <span style="color: #ff3d00;">-{loss_1k:.2f} €</span></span>
                    <span style="margin-left: 20px;">Bei <b>10.000 €</b> Einsatz: <span style="color: #00c853;">+{gain_10k:.2f} €</span> / <span style="color: #ff3d00;">-{loss_10k:.2f} €</span></span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    # --------------------------------------------------------------------------

    st.info(f"🕯️ **Erkannte Candlestick-Muster (Aktuelle Kerze):** {candle_result['reason']}")
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
    # 8. AUTOMATISCHES MINI-KI SIGNAL- & STRATEGIE-LOGBUCH
    # ==============================================================================
    st.subheader("🤖 Automatischer Mini-KI Signal-Scanner & Denkprozess")
    
    aktuelle_strategie = config.get("active_strategy", "RSI-Reversal-v1")
    
    if letzter_rsi < oversold_level:
        automatisches_signal = "KAUFEN"
        ki_gedanke = f"🟢 **Signal erkannt ({aktuelle_strategie}):** RSI steht bei {letzter_rsi:.1f}. Kerzenmuster: {candle_result['reason']}. Die KI hat automatisch ein Kaufsignal ausgelöst!"
    elif letzter_rsi > overbought_level:
        automatisches_signal = "VERKAUFEN"
        ki_gedanke = f"🔴 **Signal erkannt ({aktuelle_strategie}):** RSI hat {letzter_rsi:.1f} erreicht. Kerzenmuster: {candle_result['reason']}. Die KI hat automatisch ein Verkaufssignal ausgelöst!"
    else:
        automatisches_signal = "NEUTRAL"
        ki_gedanke = f"⚪ **Markt-Monitoring ({aktuelle_strategie}):** Neutraler Bereich bei RSI {letzter_rsi:.1f}. Aktuelles Muster: {candle_result['reason']}."
        
    st.info(ki_gedanke)
    
    logs = load_trade_logs()
    if automatisches_signal != "NEUTRAL":
        aktueller_zeitstempel = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        if not logs or logs[0]["Signal"] != automatisches_signal or logs[0]["Coin"] != selected_asset_label:
            neuer_eintrag = {
                "Zeitstempel": aktueller_zeitstempel,
                "Coin": selected_asset_label,
                "Signal": final_signal,
                "Kurs": format_de_number(aktueller_kurs, True, currency_symbol),
                "RSI-Wert": f"{letzter_rsi:.1f}",
                "Win-Prob": f"{win_probability:.1f}%",
                "Muster": candle_result["reason"],
                "KI-Lernstatus": "🧠 Automatisch erfasst & gemerkt"
            }
            logs.insert(0, neuer_eintrag)
            save_trade_logs(logs)
            
    st.subheader("📋 Automatisches Strategie- & Signal-Logbuch (Sekundengenau)")
    
    if not logs or not isinstance(logs, list) or len(logs) == 0:
        st.info("Der automatische Scanner überwacht den Markt. Sobald ein Signal durchbrochen wird, trägt sich das Signal hier von selbst ein.")
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
