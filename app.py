import json
import os
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

# Stile CSS personalizzato per ottimizzazione mobile estrema
st.markdown(
    """
    <style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .market-card-pos { background-color: #113822; padding: 12px; border-radius: 8px; border-left: 4px solid #238636; margin-bottom: 8px; }
    .market-card-neg { background-color: #3b171c; padding: 12px; border-radius: 8px; border-left: 4px solid #da3633; margin-bottom: 8px; }
    
    /* Stile per i mini-pulsanti d'azione */
    div.stButton > button {
        padding: 2px 5px !important;
        font-size: 11px !important;
        min-height: 24px !important;
        max-height: 28px !important;
        line-height: 1 !important;
        border-radius: 4px !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Gestione persistenza dati su file JSON locale
PORTFOLIO_FILE = "portfolio.json"


def load_portfolio():
  if os.path.exists(PORTFOLIO_FILE):
    try:
      with open(PORTFOLIO_FILE, "r") as f:
        return json.load(f)
    except Exception:
      pass
  return {
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


def save_portfolio(port):
  try:
    with open(PORTFOLIO_FILE, "w") as f:
      json.dump(port, f)
  except Exception:
    pass


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
  st.info(
      "💡 Clicca sulla matita ✏️ a fianco di ogni titolo per aprirne la gestione"
      " e le opzioni."
  )


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


# Inizializzazione Sessione con caricamento persistente
if "portfolio" not in st.session_state:
  st.session_state.portfolio = load_portfolio()

if "watchlists" not in st.session_state:
  st.session_state.watchlists = {
      "Da seguire": ["SWDA.MI", "ISP.MI", "BTP-2067", "AAPL"]
  }

if "show_pac" not in st.session_state:
  st.session_state.show_pac = False

if "show_fire" not in st.session_state:
  st.session_state.show_fire = False

if "show_add_form" not in st.session_state:
  st.session_state.show_add_form = False

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
        <div style="background: {header_bg}; padding: 20px; border-radius: 10px; margin-bottom: 15px;">
            <h1 style="color: white; margin: 0; font-size: 24px;">Mercati</h1>
            <p style="color: #c9d1d9; margin: 5px 0 0 0; font-size: 13px;">Panoramica in tempo reale</p>
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
                <h4 style="margin:0; color: white; font-size: 14px;">{name}</h4>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px;">
                    <span style="font-size: 16px; font-weight: bold; color: white;">{price:,.2f}</span>
                    <span style="font-size: 13px; font-weight: bold; color: {color};">{sign}{change:.2f}%</span>
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
      (total_daily_change_eur / prev_net_worth) * 100
      if prev_net_worth > 0
      else 0.0
  )

  chg_sign = "+" if total_daily_change_eur >= 0 else ""
  chg_color = "#3fb950" if total_daily_change_eur >= 0 else "#f85149"

  st.markdown(
      f"""
        <div style="background: linear-gradient(135deg, #1f6feb, #113822); padding: 20px; border-radius: 10px; margin-bottom: 15px;">
            <h3 style="color: #8b94e0; margin: 0; font-size: 14px;">Patrimonio netto</h3>
            <h1 style="color: white; margin: 4px 0; font-size: 32px;">{total_net_worth:,.2f} €</h1>
            <p style="color: {chg_color}; margin: 0; font-size: 14px; font-weight: bold;">
                Oggi: {chg_sign}{total_daily_change_eur:,.2f} € ({chg_sign}{portfolio_daily_pct:.2f}%)
            </p>
        </div>
    """,
      unsafe_allow_html=True,
  )

  # Pulsante a scomparsa per aggiungere una nuova posizione
  btn_label = (
      "❌ Chiudi Modulo Aggiunta"
      if st.session_state.show_add_form
      else "➕ Aggiungi Posizione"
  )
  if st.button(btn_label, type="primary", use_container_width=True):
    st.session_state.show_add_form = not st.session_state.show_add_form
    st.rerun()

  if st.session_state.show_add_form:
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Nuova Posizione")
    with st.form("add_position_form"):
      col_a, col_b = st.columns(2)
      with col_a:
        new_ticker = st.text_input("Ticker / ISIN")
        new_qty = st.number_input(
            "Quantità / Lotti", min_value=0.0, value=1.0, step=1.0
        )
      with col_b:
        new_name = st.text_input("Nome")
        new_manual_price = st.number_input(
            "Prezzo Man. (€ o %)", min_value=0.0, value=0.0, step=0.01
        )

      new_is_bond = st.checkbox("Obbligazione/BTP?")
      submitted = st.form_submit_button("Conferma e Salva Posizione")
      if submitted and new_ticker:
        st.session_state.portfolio[new_ticker.upper()] = {
            "qty": new_qty,
            "name": new_name or new_ticker,
            "is_bond": new_is_bond,
            "manual_price": new_manual_price,
        }
        save_portfolio(st.session_state.portfolio)
        st.session_state.show_add_form = False
        st.rerun()

  st.markdown(
      "<hr style='margin: 12px 0; border-color: #30363d;'>",
      unsafe_allow_html=True,
  )
  st.subheader("Posizioni")

  # Layout ottimizzato: Spazi spostati più a sinistra e font percentuale ingrandito
  for item in portfolio_items:
    sym = item["ticker"]
    chg = item["change"]
    c_sign = "+" if chg >= 0 else ""
    c_col = "#3fb950" if chg >= 0 else "#f85149"
    badge = " (BTP)" if item["is_bond"] else ""
    p_display = (
        f"{item['price']:.2f}%" if item["is_bond"] else f"{item['price']:,.2f} €"
    )

    edit_key = f"edit_active_{sym}"
    if edit_key not in st.session_state:
      st.session_state[edit_key] = False

    cols = st.columns([4.8, 1.5, 0.7], gap="small")
    with cols[0]:
      st.markdown(
          f"""
            <div style="font-size: 13px; line-height: 1.3;">
                <b>{sym}{badge}</b> <span style="color: #8b9499; font-size: 11px; margin-left: 4px;">{p_display}</span><br>
                <span style="font-size: 11px; color: #c9d1d9;">Qt: {item['qty']} | Tot: <b>{item['valore']:,.0f} €</b></span>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with cols[1]:
      st.markdown(
          f"""
            <div style="text-align: center; font-size: 16px; font-weight: bold; color: {c_col}; padding-top: 4px;">
                {c_sign}{chg:.2f}%
            </div>
            """,
          unsafe_allow_html=True,
      )
    with cols[2]:
      if st.button("✏️", key=f"btn_edit_{sym}", help="Gestisci / Modifica"):
        st.session_state[edit_key] = not st.session_state[edit_key]
        st.rerun()

    # Pannello a comparsa con Modifica e Pulsante X di eliminazione
    if st.session_state[edit_key]:
      with st.container():
        st.markdown(
            f"<div style='background-color: #161b22; padding: 10px; border-radius: 6px; border: 1px solid #30363d; margin: 4px 0;'>"
            f"<span style='font-size:12px; color:#8b94e0; font-weight:bold;'>Gestione {sym}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        ec1, ec2 = st.columns(2)
        with ec1:
          up_q = st.number_input(
              "Qt / Lotti",
              value=float(item["qty"]),
              key=f"q_{sym}",
              step=1.0,
          )
        with ec2:
          default_p = (
              float(item["manual_price"])
              if item["manual_price"] > 0
              else float(item["price"])
          )
          up_p = st.number_input(
              "Prezzo (€ o %)", value=default_p, key=f"p_{sym}", step=0.01
          )

        sub_c1, sub_c2 = st.columns(2)
        with sub_c1:
          if st.button("💾 Salva", key=f"save_{sym}", use_container_width=True):
            st.session_state.portfolio[sym]["qty"] = up_q
            st.session_state.portfolio[sym]["manual_price"] = up_p
            save_portfolio(st.session_state.portfolio)
            st.session_state[edit_key] = False
            st.rerun()
        with sub_c2:
          if st.button(
              "❌ Elimina Titolo", key=f"del_{sym}", use_container_width=True
          ):
            del st.session_state.portfolio[sym]
            save_portfolio(st.session_state.portfolio)
            st.rerun()

    st.markdown(
        "<hr style='margin: 4px 0; border-color: #21262d;'>",
        unsafe_allow_html=True,
    )

  st.divider()

  # Pulsante per aprire/chiudere il Simulatore PAC
  if st.button(
      "📊 Simulazione Rendimento PAC", type="primary", use_container_width=True
  ):
    st.session_state.show_pac = not st.session_state.show_pac
    st.rerun()

  if st.session_state.show_pac:
    st.markdown("### Simulatore Monte Carlo con PAC")
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
      pac_amount = st.number_input("Importo PAC (€)", value=300)
    with col_m2:
      pac_freq = st.selectbox(
          "Frequenza", ["Mensile", "Settimanale", "Trimestrale"]
      )
    with col_m3:
      years = st.number_input("Anni", min_value=1, max_value=40, value=20)

    st.markdown("##### 📊 Ripartizione Asset per il PAC (%)")

    active_pac_items = [
        item
        for item in portfolio_items
        if item["ticker"] not in st.session_state.pac_excluded
    ]

    if not active_pac_items:
      st.warning(
          "Tutti i titoli sono stati esclusi dal PAC. Ripristina almeno un"
          " titolo."
      )
    else:
      raw_weights = {}
      for item in active_pac_items:
        sym = item["ticker"]
        val = item["valore"]
        default_pct = (
            float((val / total_net_worth) * 100)
            if total_net_worth > 0
            else 0.0
        )

        cols_pw = st.columns([3.5, 0.5])
        with cols_pw[0]:
          raw_weights[sym] = st.number_input(
              f"{sym} ({item['name'][:18]}...)",
              min_value=0.0,
              max_value=100.0,
              value=default_pct,
              step=1.0,
              key=f"pac_w_{sym}",
          )
        with cols_pw[1]:
          st.write("")
          if st.button("❌", key=f"exc_pac_{sym}", help=f"Escludi {sym} dal PAC"):
            st.session_state.pac_excluded.append(sym)
            st.rerun()

      if st.session_state.pac_excluded:
        st.info(
            f"Titoli esclusi dal PAC: {', '.join(st.session_state.pac_excluded)}"
        )
        if st.button("🔄 Ripristina tutti i titoli esclusi"):
          st.session_state.pac_excluded = []
