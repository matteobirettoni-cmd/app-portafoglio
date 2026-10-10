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

  st.subheader("Posizioni in Portafoglio")

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

    cols = st.columns([2.4, 1.8, 0.4, 0.4])
    with cols[0]:
      st.markdown(
          f"""
            <div style="font-size: 13px;">
                <b>{sym}</b>{badge}<br>
                <span style="font-size: 11px; color: #8b9499;">{item['name']}</span><br>
                <span style="font-size: 11px; color: #c9d1d9;">Qt: {item['qty']} | Tot: <b>{item['valore']:,.0f} €</b></span>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with cols[1]:
      st.markdown(
          f"""
            <div style="text-align: right; font-size: 13px;">
                <span style="color: {c_col}; font-weight: bold;">{c_sign}{chg:.2f}%</span><br>
                <b>{p_display}</b>
            </div>
            """,
          unsafe_allow_html=True,
      )
    with cols[2]:
      if st.button("✏️", key=f"btn_edit_{sym}", help="Modifica"):
        st.session_state[edit_key] = not st.session_state[edit_key]
        st.rerun()
    with cols[3]:
      if st.button("❌", key=f"btn_del_{sym}", help="Rimuovi"):
        del st.session_state.portfolio[sym]
        st.rerun()

    if st.session_state[edit_key]:
      with st.container():
        st.markdown(
            f"<div style='background-color: #161b22; padding: 10px; border-radius: 6px; border: 1px solid #30363d; margin-bottom: 6px;'>"
            f"<span style='font-size:12px; color:#8b94e0; font-weight:bold;'>Modifica {sym}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        ec1, ec2, ec3 = st.columns([2, 2, 1])
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
        with ec3:
          st.write("")
          if st.button("💾", key=f"save_{sym}", use_container_width=True):
            st.session_state.portfolio[sym]["qty"] = up_q
            st.session_state.portfolio[sym]["manual_price"] = up_p
            st.session_state[edit_key] = False
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
          st.rerun()

      sum_raw = sum(raw_weights.values())
      if sum_raw > 0:
        pac_weights = {k: v / sum_raw for k, v in raw_weights.items()}
      else:
        pac_weights = {}

      weighted_return = 0.0
      weighted_vol = 0.0
      for sym, w in pac_weights.items():
        data = st.session_state.portfolio[sym]
        is_bond = data.get("is_bond", False)
        if is_bond:
          name_str = data.get("name", "")
          match = re.search(r"(\d+[\.,]?\d*)\s*%", name_str)
          gross_coupon = (
              float(match.group(1).replace(",", ".")) if match else 2.5
          )
          net_coupon = gross_coupon * 0.875
          cur_price = data.get("manual_price", 0.0)
          if cur_price <= 0:
            cur_price = 100.0
          r = (net_coupon / cur_price) if cur_price > 0 else 0.035
          r = max(r, 0.02)
          v = 0.06
        elif "GOLD" in sym.upper():
          r, v = 0.06, 0.15
        else:
          r, v = 0.08, 0.16
        weighted_return += w * r
        weighted_vol += w * v

      monthly_contrib = (
          pac_amount
          if pac_freq == "Mensile"
          else (pac_amount * 4 if pac_freq == "Settimanale" else pac_amount / 3)
      )

      if st.button("🚀 Avvia Simulazione (3.000 scenari)", type="secondary"):
        if not pac_weights:
          st.warning("Seleziona una percentuale valida per i titoli del PAC.")
        else:
          np.random.seed(42)
          n_sims = 3000
          months = int(years * 12)
          dt = 1 / 12
          simulations = np.zeros((months, n_sims))
          simulations[0, :] = total_net_worth

          for m in range(1, months):
            rand_normals = np.random.normal(0, 1, n_sims)
            growth = (
                simulations[m - 1, :]
                * (
                    1
                    + weighted_return * dt
                    + weighted_vol * np.sqrt(dt) * rand_normals
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
              "Pessimista (10° perc.)",
              f"{pessimistic[-1]:,.0f} €".replace(",", "."),
          )
          col_res2.metric(
              "Neutro (Mediana)", f"{neutral[-1]:,.0f} €".replace(",", ".")
          )
          col_res3.metric(
              "Ottimista (90° perc.)",
              f"{optimistic[-1]:,.0f} €".replace(",", "."),
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
                  orientation="h",
                  yanchor="bottom",
                  y=1.02,
                  xanchor="right",
                  x=1,
              ),
          )
          st.plotly_chart(fig, use_container_width=True)

      st.markdown("<br>", unsafe_allow_html=True)

      # Pulsante per visibilità Simulatore FIRE
      if st.button(
          "🔥 Mostra/Nascondi Simulatore FIRE",
          type="secondary",
          use_container_width=True,
      ):
        st.session_state.show_fire = not st.session_state.show_fire
        st.rerun()

      if st.session_state.show_fire:
        st.markdown(
            "### 🔥 Simulatore FIRE (Financial Independence, Retire Early)"
        )
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
          fire_monthly_exp = st.number_input(
              "Spesa mensile des. (€)",
              value=1150.0,
              step=50.0,
              key="fire_exp",
          )
        with f_col2:
          current_age = st.number_input(
              "Età attuale", min_value=18, max_value=90, value=30, key="fire_age"
          )
        with f_col3:
          swr = (
              st.selectbox(
                  "Prelievo sicuro (SWR)", ["4%", "3.5%", "3%"], key="fire_swr"
              )
              .replace("%", "")
              .strip()
          )
          swr_val = float(swr) / 100.0

        fc_inf1, fc_inf2, fc_scen = st.columns(3)
        with fc_inf1:
          use_inflation = st.checkbox(
              "Includi inflazione stimata", value=True, key="fire_use_inf"
          )
        with fc_inf2:
          inflation_rate = (
              st.number_input(
                  "Inflazione annua (%)",
                  min_value=0.0,
                  max_value=10.0,
                  value=2.0,
                  step=0.1,
                  key="fire_inf_rate",
              )
              if use_inflation
              else 0.0
          )
        with fc_scen:
          scenario_choice = st.selectbox(
              "Scenario Rendimento",
              ["Neutro (Mediana)", "Pessimista (10°)", "Ottimista (90°)"],
              key="fire_scenario",
          )

        # Pulsante dedicato al calcolo/aggiornamento del FIRE
        if st.button("🔥 Calcola Obiettivo FIRE", type="primary"):
          if "Pessimista" in scenario_choice:
            eff_return = weighted_return - weighted_vol
          elif "Ottimista" in scenario_choice:
            eff_return = weighted_return + weighted_vol
          else:
            eff_return = weighted_return

          inf_val = (inflation_rate / 100.0) if use_inflation else 0.0
          base_fire_target = fire_monthly_exp * 12 * (1.0 / swr_val)

          val = total_net_worth
          months_needed = 0
          reached = False
          target_at_reach = base_fire_target

          if val >= base_fire_target:
            reached = True
            months_needed = 0
          else:
            for m in range(1, 12 * 70):
              cur_target = base_fire_target * ((1 + inf_val) ** (m / 12.0))
              val = val * (1 + (eff_return / 12.0)) + monthly_contrib
              if val >= cur_target:
                months_needed = m
                target_at_reach = cur_target
                reached = True
                break

          if use_inflation:
            st.markdown(
                f"#### 🎯 Tuo FIRE Number target (in valuta futura):"
                f" **{target_at_reach:,.0f} €**"
            )
            st.caption(
                f"Capitale in valuta attuale (senza inflazione):"
                f" {base_fire_target:,.0f} €"
            )
          else:
            st.markdown(
                f"#### 🎯 Tuo FIRE Number target: **{base_fire_target:,.0f} €**"
            )

          if reached:
            years_needed = months_needed / 12.0
            retire_age = current_age + years_needed
            success_msg = (
                f"🎉 [{scenario_choice}] Raggiungeresti il traguardo FIRE tra"
                f" **{years_needed:.1f} anni** (all'età di **{retire_age:.1f}"
                " anni**)!"
            )
            st.success(success_msg)

            progress_pct = min(1.0, total_net_worth / target_at_reach)
            st.progress(
                progress_pct,
                text=(
                    f"Progresso attuale: {total_net_worth:,.0f} € /"
                    f" {target_at_reach:,.0f} € ({progress_pct*100:.1f}%)"
                ),
            )
          else:
            st.warning(
                f"Con lo scenario [{scenario_choice}] e il PAC impostato, il"
                " traguardo FIRE richiede più di 70 anni. Prova ad aumentare"
                " l'importo del PAC."
            )

# 3. TAB WATCHLIST
with tab_watchlist:
  st.markdown(
      '<div style="background: linear-gradient(135deg, #d97706, #78350f);'
      ' padding: 25px; border-radius: 12px; margin-bottom: 20px;"><h1'
      ' style="color: white; margin: 0;">Watchlist</h1><p style="color:'
      ' #fef3c7; margin: 5px 0 0 0;">Monitora i titoli di tuo interesse con'
      ' prezzi in tempo reale</p></div>',
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
    p_str = f"{price:,.2f} €" if price else "n.d."
    c_val = change if change is not None else 0.0
    c_sign = "+" if c_val >= 0 else ""
    c_col = "#3fb950" if c_val >= 0 else "#f85149"

    cols_w = st.columns([3.4, 0.6])
    with cols_w[0]:
      st.markdown(
          f'<div style="background-color: #161b22; padding: 10px 12px;'
          ' border-radius: 8px; border: 1px solid #30363d; display: flex;'
          f' justify-content: space-between; align-items: center;"><div><b>{sym}</b></div><div'
          f' style="text-align: right;"><b>{p_str}</b><br><span'
          f' style="color: {c_col}; font-weight: bold; font-size:'
          f' 11px;">{c_sign}{c_val:.2f}%</span></div></div>',
          unsafe_allow_html=True,
      )
    with cols_w[1]:
      if st.button("❌", key=f"del_wl_{sym}", help="Rimuovi"):
        st.session_state.watchlists[selected_wl].remove(sym)
        st.rerun()
