import re
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# Configurazione pagina
st.set_page_config(
    page_title="Portfolio & Market Monitor", page_icon="📈", layout="wide"
)

# Stile CSS personalizzato per ottimizzazione mobile
st.markdown(
    """
    <style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .market-card-pos { background-color: #113822; padding: 15px; border-radius: 8px; border-left: 5px solid #238636; margin-bottom: 10px; }
    .market-card-neg { background-color: #3b171c; padding: 15px; border-radius: 8px; border-left: 5px solid #da3633; margin-bottom: 10px; }
    .asset-row { background-color: #161b22; padding: 10px 12px; border-radius: 8px; border: 1px solid #30363d; margin-bottom: 6px; }
    </style>
""",
    unsafe_allow_html=True,
)

# Sidebar globale con pulsante di aggiornamento
with st.sidebar:
  st.markdown("### ⚙️ Pannello di Controllo")
  st.write(
      "Usa il pulsante sottostante per svuotare la cache e forzare lo scaricamento"
      " dei prezzi freschi da Yahoo Finance."
  )
  if st.button("🔄 Aggiorna da Yahoo Finance", type="primary"):
    st.cache_data.clear()
    st.success("Dati aggiornati con successo!")
    st.rerun()
  st.divider()
  st.info("💡 Usa le icone ✏️ e ❌ a fianco di ogni titolo per gestirlo.")


# Funzione dati da yfinance
@st.cache_data(ttl=300)
def get_ticker_data(ticker_symbol):
  clean_sym = ticker_symbol.upper().strip()
  try:
    t = yf.Ticker(clean_sym)
    hist = t.history(period="5d")
    if not hist.empty and "Close" in hist.columns:
      current_price = float(hist["Close"].iloc[-1])
      prev_price = (
          float(hist["Close"].iloc[-2]) if len(hist) > 1 else current_price
      )
      change = float(((current_price - prev_price) / prev_price) * 100)
      if not np.isnan(current_price):
        return current_price, change

    price = t.fast_info.get("lastPrice", None)
    if price is not None and not np.isnan(price):
      return float(price), 0.0
  except Exception:
    pass

  return 100.0, 0.0


# Inizializzazione Sessione con il tuo portafoglio
if "portfolio" not in st.session_state:
  st.session_state.portfolio = {
      "ISP.MI": {
          "qty": 250.0,
          "name": "Intesa Sanpaolo",
          "is_bond": False,
          "manual_price": 6.116,
      },
      "GOLD": {
          "qty": 10.0,
          "name": "Amundi Physical Gold ETC",
          "is_bond": False,
          "manual_price": 148.21,
      },
      "SWDA.MI": {
          "qty": 87.0,
          "name": "iShares Core MSCI World UCITS ETF",
          "is_bond": False,
          "manual_price": 131.67,
      },
      "XMME.MI": {
          "qty": 15.0,
          "name": "Xtrackers MSCI Emerging Markets",
          "is_bond": False,
          "manual_price": 82.998,
      },
      "XNDX.MI": {
          "qty": 10.0,
          "name": "Xtrackers NASDAQ 100",
          "is_bond": False,
          "manual_price": 63.88,
      },
      "XACT.MI": {
          "qty": 101.0,
          "name": "Xtrackers FTSE All-World",
          "is_bond": False,
          "manual_price": 9.644,
      },
      "XUSE.MI": {
          "qty": 16.0,
          "name": "Xtrackers MSCI USA",
          "is_bond": False,
          "manual_price": 206.2,
      },
      "XWLD.MI": {
          "qty": 21.0,
          "name": "Xtrackers MSCI World Value",
          "is_bond": False,
          "manual_price": 74.09,
      },
      "XR2K.MI": {
          "qty": 1.0,
          "name": "Xtrackers Russell 2000",
          "is_bond": False,
          "manual_price": 371.82,
      },
      "BTP-2067": {
          "qty": 14.0,
          "name": "BTP Tf 2.8% Mz67",
          "is_bond": True,
          "manual_price": 63.85,
      },
  }

if "watchlists" not in st.session_state:
  st.session_state.watchlists = {
      "Da seguire": ["SWDA.MI", "ISP.MI", "BTP-2067", "AAPL"]
  }

if "show_pac" not in st.session_state:
  st.session_state.show_pac = False

if "show_fire" not in st.session_state:
  st.session_state.show_fire = False

if "pac_excluded" not in st.session_state:
  st.session_state.pac_excluded = []

tab_mercati, tab_portafoglio, tab_watchlist = st.tabs(
    ["Mercati", "Portafoglio", "Watchlist"]
)

market_symbols = {
    "FTSE MIB": "^FTSEMIB",
    "Euro Stoxx 50": "^STOXX50E",
    "DAX": "^GDAXI",
    "S&P 500": "^GSPC",
    "Nasdaq 100": "^NDX",
    "Oro (USD/oz)": "GC=F",
    "Petrolio Brent": "BZ=F",
}

# 1. TAB MERCATI
with tab_mercati:
  pos_count = 0
  tot_count = 0
  evaluated_markets = []

  for name, sym in market_symbols.items():
    p, c = get_ticker_data(sym)
    if c is not None:
      tot_count += 1
      if c >= 0:
        pos_count += 1
      evaluated_markets.append((name, p, c))

  is_market_bullish = (
      pos_count >= (tot_count / 2) if tot_count > 0 else True
  )
  header_bg = (
      "linear-gradient(135deg, #238636, #113822)"
      if is_market_bullish
      else "linear-gradient(135deg, #da3633, #3b171c)"
  )

  st.markdown(
      f"""
        <div style="background: {header_bg}; padding: 25px; border-radius: 12px; margin-bottom: 20px;">
            <h1 style="color: white; margin: 0;">Mercati</h1>
            <p style="color: #c9d1d9; margin: 5px 0 0 0;">Panoramica in tempo reale dei principali indici, materie prime e crypto</p>
        </div>
    """,
      unsafe_allow_html=True,
  )

  col1, col2 = st.columns(2)
  i = 0
  for name, price, change in evaluated_markets:
    is_pos = change >= 0
    card_class = "market-card-pos" if is_pos else "market-card-neg"
    sign = "+" if is_pos else ""
    color = "#3fb950" if is_pos else "#f85149"

    with col1 if i % 2 == 0 else col2:
      st.markdown(
          f"""
            <div class="{card_class}">
                <h3 style="margin:0; color: white;">{name}</h3>
                <p style="margin:2px 0; color: #8b94e0; font-size: 12px;">Indice / Materia Prima</p>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
                    <span style="font-size: 20px; font-weight: bold; color: white;">{price:,.2f}</span>
                    <span style="font-size: 16px; font-weight: bold; color: {color};">{sign}{change:.2f}%</span>
                </div>
            </div>
        """,
          unsafe_allow_html=True,
      )
    i += 1

# 2. TAB PORTAFOGLIO
with tab_portafoglio:
  total_net_worth = 0
  total_daily_change_eur = 0
  portfolio_items = []

  for sym, data in st.session_state.portfolio.items():
    manual_p = data.get("manual_price", 0.0)
    if manual_p > 0:
      price = manual_p
      change = 0.0
    else:
      price, change = get_ticker_data(sym)
      if price is None or np.isnan(price):
        price = 100.0

    is_bond = data.get("is_bond", False)
    if is_bond:
      nominale = data["qty"] * 1000.0
      valore = nominale * (price / 100.0)
    else:
      valore = data["qty"] * price

    total_net_worth += valore
    item_daily_eur = valore * (change / 100.0)
    total_daily_change_eur += item_daily_eur

    portfolio_items.append({
        "ticker": sym,
        "name": data["name"],
        "qty": data["qty"],
        "price": price,
        "change": change,
        "valore": valore,
        "is_bond": is_bond,
        "manual_price": manual_p,
    })

  prev_net_worth = total_net_worth - total_daily_change_eur
  portfolio_daily_pct = (
      (total_daily_change_eur / prev_net_
