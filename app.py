import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# Configurazione pagina
st.set_page_config(
    page_title="Portfolio & Market Monitor", page_icon="📈", layout="wide"
)

# Stile CSS personalizzato per ottimizzazione mobile e tabelle scrollabili
st.markdown(
    """
    <style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .metric-card { background-color: #161b22; padding: 20px; border-radius: 12px; border: 1px solid #30363d; margin-bottom: 20px; }
    .market-card-pos { background-color: #113822; padding: 15px; border-radius: 8px; border-left: 5px solid #238636; margin-bottom: 10px; }
    .market-card-neg { background-color: #3b171c; padding: 15px; border-radius: 8px; border-left: 5px solid #da3633; margin-bottom: 10px; }
    .table-container { width: 100%; overflow-x: auto; margin-bottom: 20px; }
    .custom-table { width: 100%; border-collapse: collapse; background-color: #161b22; border-radius: 8px; overflow: hidden; }
    .custom-table th { background-color: #21262d; color: #c9d1d9; padding: 12px; text-align: left; font-size: 14px; border-bottom: 1px solid #30363d; white-space: nowrap; }
    .custom-table td { padding: 12px; color: #ffffff; font-size: 14px; border-bottom: 1px solid #30363d; white-space: nowrap; }
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
  st.info(
      "💡 Suggerimento: scorri la tabella del portafoglio verso destra per"
      " vedere quantità e totali da smartphone."
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


# Funzione per prossimi dividendi/cedole
@st.cache_data(ttl=3600)
def get_upcoming_dividends(ticker_symbol):
  clean_sym = ticker_symbol.upper().strip()
  if "BTP" in clean_sym or "IT000" in clean_sym:
    return 1.4
  try:
    t = yf.Ticker(clean_sym)
    divs = t.dividends
    if not divs.empty:
      return float(divs.iloc[-1])
  except Exception:
    pass
  return 0.0


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
      (total_daily_change_eur / prev_net_worth) * 100
      if prev_net_worth > 0
      else 0.0
  )

  chg_sign = "+" if total_daily_change_eur >= 0 else ""
  chg_color = "#3fb950" if total_daily_change_eur >= 0 else "#f85149"

  st.markdown(
      f"""
        <div style="background: linear-gradient(135deg, #1f6feb, #113822); padding: 25px; border-radius: 12px; margin-bottom: 20px;">
            <h3 style="color: #8b94e0; margin: 0;">Patrimonio netto</h3>
            <h1 style="color: white; margin: 5px 0; font-size: 38px;">{total_net_worth:,.2f} €</h1>
            <p style="color: {chg_color}; margin: 0; font-size: 16px; font-weight: bold;">
                Variazione odierna: {chg_sign}{total_daily_change_eur:,.2f} € ({chg_sign}{portfolio_daily_pct:.2f}%)
            </p>
            <p style="color: #c9d1d9; margin: 5px 0 0 0; font-size: 13px;">{len(st.session_state.portfolio)} titoli monitorati</p>
        </div>
    """,
      unsafe_allow_html=True,
  )

  st.subheader("Posizioni in Portafoglio (Scorri a destra ➡️)")

  with st.form("add_position_form"):
    col_a, col_b, col_c, col_d, col_e = st.columns([2, 2, 1, 1, 1])
    with col_a:
      new_ticker = st.text_input("Ticker / ISIN")
    with col_b:
      new_name = st.text_input("Nome")
    with col_c:
      new_qty = st.number_input(
          "Quantità / Lotti", min_value=0.0, value=1.0, step=1.0
      )
    with col_d:
      new_is_bond = st.checkbox("Obbligazione/BTP?")
    with col_e:
      new_manual_price = st.number_input(
          "Prezzo Man. (€ o %)", min_value=0.0, value=0.0, step=0.01
      )

    submitted = st.form_submit_button("Aggiungi Posizione")
    if submitted and new_ticker:
      st.session_state.portfolio[new_ticker.upper()] = {
          "qty": new_qty,
          "name": new_name or new_ticker,
          "is_bond": new_is_bond,
          "manual_price": new_manual_price,
      }
      st.rerun()

  table_html = """
    <div class="table-container">
        <table class="custom-table">
            <thead>
                <tr>
                    <th>Titolo / Nome</th>
                    <th>Var. Oggi</th>
                    <th>Prezzo</th>
                    <th>Quantità / Lotti</th>
                    <th>Totale (€)</th>
                </tr>
            </thead>
            <tbody>
    """

  for item in portfolio_items:
    sym = item["ticker"]
    chg = item["change"]
    c_sign = "+" if chg >= 0 else ""
    c_col = "#3fb950" if chg >= 0 else "#f85149"
    badge = " (BTP/Bond)" if item["is_bond"] else ""
    p_display = (
        f"{item['price']:.2f}%" if item["is_bond"] else f"{item['price']:,.2f} €"
    )
    q_display = (
        f"Lotti: {item['qty']} (Nom. {item['qty']*1000:,.0f}€)"
        if item["is_bond"]
        else f"Qt: {item['qty']}"
    )

    table_html += f"""
        <tr>
            <td><b>{sym}</b>{badge}<br><span style="font-size:11px; color:#8b9499;">{item['name']}</span></td>
            <td><span style="color: {c_col}; font-weight:bold;">{c_sign}{chg:.2f}%</span></td>
            <td><b>{p_display}</b></td>
            <td>{q_display}</td>
            <td><b>{item['valore']:,.2f} €</b></td>
        </tr>
    """

  table_html += """
            </tbody>
        </table>
    </div>
    """
  st.markdown(table_html, unsafe_allow_html=True)

  st.markdown("##### ✏️ Gestisci / Modifica singoli titoli")
  for item in portfolio_items:
    sym = item["ticker"]
    with st.expander(f"Modifica {sym} - {item['name']}"):
      ecols = st.columns([2, 2, 1, 1])
      with ecols[0]:
        up_qty = st.number_input(
            "Quantità / Lotti",
            value=float(item["qty"]),
            key=f"up_q_{sym}",
            step=1.0,
        )
      with ecols[1]:
        up_price = st.
