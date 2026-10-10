import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# Configurazione pagina
st.set_page_config(
    page_title="Portfolio & Market Monitor", page_icon="📈", layout="wide"
)

# Stile CSS personalizzato
st.markdown(
    """
    <style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .metric-card { background-color: #161b22; padding: 20px; border-radius: 12px; border: 1px solid #30363d; margin-bottom: 20px; }
    .market-card-pos { background-color: #113822; padding: 15px; border-radius: 8px; border-left: 5px solid #238636; margin-bottom: 10px; }
    .market-card-neg { background-color: #3b171c; padding: 15px; border-radius: 8px; border-left: 5px solid #da3633; margin-bottom: 10px; }
    </style>
""",
    unsafe_allow_html=True,
)


# Funzione dati da yfinance
@st.cache_data(ttl=300)
def get_ticker_data(ticker_symbol):
  try:
    t = yf.Ticker(ticker_symbol)
    hist = t.history(period="5d")
    if not hist.empty:
      current_price = hist["Close"].iloc[-1]
      prev_price = hist["Close"].iloc[-2] if len(hist) > 1 else current_price
      change = ((current_price - prev_price) / prev_price) * 100
      return current_price, change, t
  except Exception:
    pass
  return None, None, None


# Funzione per prossimi dividendi
def get_upcoming_dividends(ticker_symbol):
  try:
    t = yf.Ticker(ticker_symbol)
    divs = t.dividends
    if not divs.empty:
      return divs.tail(4)
  except Exception:
    pass
  return pd.Series(dtype=float)


# Inizializzazione Sessione
if "portfolio" not in st.session_state:
  st.session_state.portfolio = {
      "VWCE.MI": {"qty": 22.0, "name": "Vanguard FTSE All-World"},
      "SWDA.MI": {"qty": 87.0, "name": "iShares Core MSCI World"},
      "ISP.MI": {"qty": 250.0, "name": "Intesa Sanpaolo"},
      "GOLD": {"qty": 10.0, "name": "Amundi Physical Gold"},
  }

if "watchlists" not in st.session_state:
  st.session_state.watchlists = {
      "Da seguire": ["SWDA.MI", "ISP.MI", "AAPL", "NVDA"]
  }

tab_mercati, tab_portafoglio, tab_watchlist = st.tabs(
    ["Mercati", "Portafoglio", "Watchlist"]
)

# 1. TAB MERCATI
with tab_mercati:
  st.markdown(
      """
        <div style="background: linear-gradient(135deg, #238636, #113822); padding: 25px; border-radius: 12px; margin-bottom: 20px;">
            <h1 style="color: white; margin: 0;">Mercati</h1>
            <p style="color: #c9d1d9; margin: 5px 0 0 0;">Panoramica in tempo reale dei principali indici, materie prime e crypto</p>
        </div>
    """,
      unsafe_allow_html=True,
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

  col1, col2 = st.columns(2)
  i = 0
  for name, sym in market_symbols.items():
    price, change, _ = get_ticker_data(sym)
    if price is not None:
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
  st.markdown(
      """
        <div style="background: linear-gradient(135deg, #1f6feb, #113822); padding: 25px; border-radius: 12px; margin-bottom: 20px;">
            <h3 style="color: #8b94e0; margin: 0;">Patrimonio netto</h3>
    """,
      unsafe_allow_html=True,
  )

  total_net_worth = 0
  portfolio_items = []
  for sym, data in st.session_state.portfolio.items():
    price, _, _ = get_ticker_data(sym)
    if price is None:
      price = 100.0
    valore = data["qty"] * price
    total_net_worth += valore
    portfolio_items.append({
        "ticker": sym,
        "name": data["name"],
        "qty": data["qty"],
        "price": price,
        "valore": valore,
    })

  st.markdown(
      f"""
        <h1 style="color: white; margin: 5px 0; font-size: 38px;">{total_net_worth:,.2f} €</h1>
        <p style="color: #c9d1d9; margin: 0;">{len(st.session_state.portfolio)} titoli monitorati</p>
        </div>
    """,
      unsafe_allow_html=True,
  )

  st.subheader("Posizioni in Portafoglio")

  with st.form("add_position_form"):
    col_a, col_b, col_c = st.columns([2, 2, 1])
    with col_a:
      new_ticker = st.text_input("Ticker o ISIN (es. AAPL, VWCE.MI)")
    with col_b:
      new_name = st.text_input("Nome Descrittivo")
    with col_c:
      new_qty = st.number_input("Quantità", min_value=0.0, value=1.0)
    submitted = st.form_submit_button("Aggiungi Posizione")
    if submitted and new_ticker:
      st.session_state.portfolio[new_ticker.upper()] = {
          "qty": new_qty,
          "name": new_name or new_ticker,
      }
      st.rerun()

  for item in portfolio_items:
    cols = st.columns([2, 2, 1, 1, 1])
    with cols[0]:
      st.markdown(
          f"**{item['ticker']}**<br><span style='font-size:12px;"
          f" color:#8b9499;'>{item['name']}</span>",
          unsafe_allow_html=True,
      )
    with cols[1]:
      st.markdown(f"Quantità: **{item['qty']}**")
    with cols[2]:
      st.markdown(f"Prezzo: **{item['price']:,.2f} €**")
    with cols[3]:
      st.markdown(
          f"Totale: **{item['valore']:,.0f} €**", unsafe_allow_html=True
      )
    with cols[4]:
      if st.button("❌ Rimuovi", key=f"del_{item['ticker']}"):
        del st.session_state.portfolio[item["ticker"]]
        st.rerun()

  st.divider()

  st.subheader("Cedole e dividendi, prossimi 12 mesi")
  total_dividends_est = 0
  div_records = []
  for sym, data in st.session_state.portfolio.items():
    divs = get_upcoming_dividends(sym)
    if not divs.empty:
      annual_div_per_share = divs.iloc[-1] * (4 if len(divs) >= 4 else 1)
      est_div = annual_div_per_share * data["qty"]
      total_dividends_est += est_div
      div_records.append(
          {"Titolo": sym, "Cedola/Dividendo Stimato": f"{est_div:,.2f} €"}
      )

  st.markdown(f"### Totale stimato: **{total_dividends_est:,.0f} €**")
  if div_records:
    st.dataframe(pd.DataFrame(div_records), use_container_width=True)
  else:
    st.info(
        "Nessun dividendo recente rilevato automaticamente per i ticker"
        " inseriti."
    )

  st.divider()

  st.subheader("Simulatore Monte Carlo con PAC")
  col_m1, col_m2, col_m3 = st.columns(3)
  with col_m1:
    pac_amount = st.number_input("Importo PAC (€)", value=300)
  with col_m2:
    pac_freq = st.selectbox(
        "Frequenza", ["Mensile", "Settimanale", "Trimestrale"]
    )
  with col_m3:
    years = st.number_input("Anni", min_value=1, max_value=40, value=20)

  if st.button("🚀 Simula (3.000 scenari)", type="primary"):
    np.random.seed(42)
    n_sims = 3000
    months = int(years * 12)
    monthly_contrib = (
        pac_amount
        if pac_freq == "Mensile"
        else (pac_amount * 4 if pac_freq == "Settimanale" else pac_amount / 3)
    )

    expected_return = 0.073
    volatility = 0.157
    dt = 1 / 12

    simulations = np.zeros((months, n_sims))
    simulations[0, :] = total_net_worth

    for m in range(1, months):
      rand_normals = np.
