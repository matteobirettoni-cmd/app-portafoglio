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
      "Suggerimento: puoi anche modificare i singoli prezzi o quantità usando"
      " l'icona della matita ✏️ nella tabella del portafoglio."
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


# Inizializzazione Sessione con il tuo portafoglio esatto
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
    price, change = get_ticker_data(sym)
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
    portfolio_items.append({
        "ticker": sym,
        "name": data["name"],
        "qty": data["qty"],
        "price": price,
        "valore": valore,
        "is_bond": is_bond,
        "manual_price": manual_p,
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
    col_a, col_b, col_c, col_d, col_e = st.columns([2, 2, 1, 1, 1])
    with col_a:
      new_ticker = st.text_input("Ticker / ISIN (es. BTP-2067, AAPL)")
    with col_b:
      new_name = st.text_input("Nome Descrittivo")
    with col_c:
      new_qty = st.number_input(
          "Quantità / Lotti", min_value=0.0, value=1.0, step=1.0
      )
    with col_d:
      new_is_bond = st.checkbox("È Obbligazione/BTP?")
    with col_e:
      new_manual_price = st.number_input(
          "Prezzo Manuale (€ o %)",
          min_value=0.0,
          value=0.0,
          step=0.01,
          help="Se inserito (>0), usa questo prezzo fisso",
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

  # Visualizzazione e modifica rapida compatta con icona matita
  for item in portfolio_items:
    sym = item["ticker"]
    edit_key = f"editing_{sym}"
    if edit_key not in st.session_state:
      st.session_state[edit_key] = False

    cols = st.columns([2, 2, 1.3, 1, 0.7])
    with cols[0]:
      badge = (
          " <span style='color:#3fb950; font-size:10px;'>(Bond/BTP)</span>"
          if item["is_bond"]
          else ""
      )
      st.markdown(
          f"**{sym}**{badge}<br><span style='font-size:12px;"
          f" color:#8b9499;'>{item['name']}</span>",
          unsafe_allow_html=True,
      )
    with cols[1]:
      q_label = (
          f"Lotti: {item['qty']} (Nom. {item['qty']*1000:,.0f}€)"
          if item["is_bond"]
          else f"Quantità: {item['qty']}"
      )
      st.markdown(q_label)
    with cols[2]:
      p_label = (
          f"Prezzo: {item['price']:.2f}%"
          if item["is_bond"]
          else f"Prezzo: {item['price']:,.2f} €"
      )
      sub_c1, sub_c2 = st.columns([3, 1])
      with sub_c1:
        st.markdown(p_label, unsafe_allow_html=True)
      with sub_c2:
        if st.button("✏️", key=f"edit_btn_{sym}", help="Modifica prezzo/quantità"):
          st.session_state[edit_key] = not st.session_state[edit_key]
          st.rerun()
    with cols[3]:
      st.markdown(
          f"Tot: **{item['valore']:,.0f} €**", unsafe_allow_html=True
      )
    with cols[4]:
      if st.button("❌", key=f"del_{sym}", help="Rimuovi"):
        del st.session_state.portfolio[sym]
        st.rerun()

    # Box di modifica rapida a comparsa compatta
    if st.session_state[edit_key]:
      st.markdown(
          f"<div style='background-color: #161b22; padding: 12px; border-radius: 8px; border: 1px solid #30363d; margin-bottom: 10px;'>"
          f"<p style='margin:0 0 8px 0; font-size:13px; color:#8b94e0; font-weight:bold;'>Modifica rapida: {sym}</p>"
          f"</div>",
          unsafe_allow_html=True,
      )
      ecols = st.columns([2, 2, 1])
      with ecols[0]:
        up_qty = st.number_input(
            "Quantità / Lotti",
            value=float(item["qty"]),
            key=f"up_q_{sym}",
            step=1.0,
        )
      with ecols[1]:
        up_price = st.number_input(
            "Prezzo manuale (€ o %)",
            value=float(item["manual_price"])
            if item["manual_price"] > 0
            else float(item["price"]),
            key=f"up_p_{sym}",
            step=0.01,
        )
      with ecols[2]:
        st.write("")
        st.write("")
        if st.button("💾 Salva", key=f"save_{sym}"):
          st.session_state.portfolio[sym]["qty"] = up_qty
          st.session_state.portfolio[sym]["manual_price"] = up_price
          st.session_state[edit_key] = False
          st.rerun()

    st.divider()

  st.subheader("Cedole e dividendi, prossimi 12 mesi")
  total_dividends_est = 0
  div_records = []
  for sym, data in st.session_state.portfolio.items():
    is_bond = data.get("is_bond", False)
    if is_bond:
      nominale = data["qty"] * 1000.0
      est_div = nominale * 0.028
    else:
      last_div = get_upcoming_dividends(sym)
      est_div = last_div * 4 * data["qty"] if last_div > 0 else 0.0

    if est_div > 0:
      total_dividends_est += est_div
      div_records.append(
          {"Titolo": sym, "Cedola/Dividendo Stimato": f"{est_div:,.2f} €"}
      )

  st.markdown(f"### Totale stimato: **{total_dividends_est:,.0f} €**")
  if div_records:
    st.dataframe(pd.DataFrame(div_records), use_container_width=True)
  else:
    st.info("Nessun dividendo o cedola rilevata per i titoli inseriti.")

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
      rand_normals = np.random.normal(0, 1, n_sims)
      growth = (
          simulations[m - 1, :]
          * (
              1
              + expected_return * dt
              + volatility * np.sqrt(dt) * rand_normals
          )
          + monthly_contrib
      )
      simulations[m, :] = growth

    pessimistic = np.percentile(simulations, 10, axis=1)
    neutral = np.percentile(simulations, 50, axis=1)
    optimistic = np.percentile(simulations, 90, axis=1)
    invested_capital = [
        total_net_worth + (monthly_contrib * m) for m in range(months)
    ]

    col_res1, col_res2, col_res3 = st.columns(3)
    col_res1.metric(
        "Pessimista (10° perc.)", f"{pessimistic[-1]:,.0f} €".replace(",", ".")
    )
    col_res2.metric(
        "Neutro (Mediana)", f"{neutral[-1]:,.0f} €".replace(",", ".")
    )
    col_res3.metric(
        "Ottimista (90° perc.)", f"{optimistic[-1]:,.0f} €".replace(",", ".")
    )

    fig = go.Figure()
    x_axis = np.arange(months) / 12
    fig.add_trace(
        go.Scatter(
            x=x_axis,
            y=optimistic,
            mode="lines",
            name="Ottimista (90°)",
            line=dict(color="#238636"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_axis,
            y=neutral,
            mode="lines",
            name="Neutro (50°)",
            line=dict(color="#1f6feb", width=3),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_axis,
            y=pessimistic,
            mode="lines",
            name="Pessimista (10°)",
            line=dict(color="#da3633"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_axis,
            y=invested_capital,
            mode="lines",
            name="Capitale Versato",
            line=dict(dash="dash", color="#8b9499"),
        )
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#161b22",
        plot_bgcolor="#161b22",
        xaxis_title="Anni",
        yaxis_title="Valore (€)",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
        ),
    )
    st.plotly_chart(fig, use_container_width=True)

# 3. TAB WATCHLIST
with tab_watchlist:
  st.markdown(
      """
        <div style="background: linear-gradient(135deg, #d97706, #78350f); padding: 25px; border-radius: 12px; margin-bottom: 20px;">
            <h1 style="color: white; margin: 0;">Watchlist</h1>
            <p style="color: #fef3c7; margin: 5px 0 0 0;">Monitora i titoli di tuo interesse con prezzi in tempo reale</p>
        </div>
    """,
      unsafe_allow_html=True,
  )

  selected_wl = st.selectbox(
      "Seleziona Lista", list(st.session_state.watchlists.keys())
  )

  with st.form("add_wl_form"):
    col_w1, col_w2 = st.columns([3, 1])
    with col_w1:
      new_wl_ticker = st.text_input("Aggiungi Ticker (es. BTP-2067, TSLA)")
    with col_w2:
      submitted_wl = st.form_submit_button("Aggiungi")
      if submitted_wl and new_wl_ticker:
        if (
            new_wl_ticker.upper()
            not in st.session_state.watchlists[selected_wl]
        ):
          st.session_state.watchlists[selected_wl].append(
              new_wl_ticker.upper()
          )
          st.rerun()

  for sym in st.session_state.watchlists[selected_wl]:
    price, change = get_ticker_data(sym)
    price_str = f"{price:,.2f} €" if price else "n.d."
    change_str = f"{change:+.2f}%" if change is not None else ""

    cols = st.columns([3, 2, 1])
    with cols[0]:
      st.markdown(f"**{sym}**")
    with cols[1]:
      st.markdown(f"{price_str} ({change_str})")
    with cols[2]:
      if st.button("❌", key=f"del_wl_{sym}"):
        st.session_state.watchlists[selected_wl].remove(sym)
        st.rerun()
