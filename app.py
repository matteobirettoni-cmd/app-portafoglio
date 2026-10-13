import html
import json
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Il Mio Portafoglio", page_icon="📈", layout="wide")

# Compatibilità: width="stretch" dalla 1.50, use_container_width prima
STRETCH = (
    {"width": "stretch"}
    if tuple(int(x) for x in re.findall(r"\d+", st.__version__)[:2]) >= (1, 50)
    else {"use_container_width": True}
)

st.markdown(
    """
    <style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .market-card-pos { background-color: #113822; padding: 12px; border-radius: 8px; border-left: 4px solid #238636; margin-bottom: 8px; }
    .market-card-neg { background-color: #3b171c; padding: 12px; border-radius: 8px; border-left: 4px solid #da3633; margin-bottom: 8px; }
    div.stButton > button {
        padding: 2px 5px !important; font-size: 11px !important;
        min-height: 24px !important; max-height: 28px !important;
        line-height: 1 !important; border-radius: 4px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# COSTANTI E IPOTESI (modificabili)
# ----------------------------------------------------------------------------
PORTFOLIO_FILE = "portfolio.json"
WATCHLIST_FILE = "watchlists.json"

BOND = "Obbligazioni / BTP"
CASH = "Liquidità"
ASSET_CLASSES = [
    "Azionario Globale",
    "Azionario USA",
    "Azionario Emergenti",
    "Azionario Italia/Altro",
    "Materie Prime (Oro)",
    BOND,
    CASH,
]
# (rendimento atteso annuo, volatilità annua). Sono IPOTESI, non previsioni.
# Per le obbligazioni il rendimento viene calcolato da cedola/prezzo/scadenza.
# Un BTP 2067 ha duration molto alta, quindi volatilità ben sopra il 6%.
ASSUMPTIONS = {
    "Azionario Globale": (0.07, 0.16),
    "Azionario USA": (0.075, 0.17),
    "Azionario Emergenti": (0.08, 0.20),
    "Azionario Italia/Altro": (0.07, 0.20),
    "Materie Prime (Oro)": (0.04, 0.15),
    BOND: (None, 0.12),
    CASH: (0.02, 0.005),
}
BOND_TAX = 0.125  # tassazione agevolata titoli di Stato
CCY_SYMBOL = {"EUR": "€", "USD": "$", "GBP": "£", "GBp": "p"}
GREEN, RED, GREY = "#3fb950", "#f85149", "#8b9499"

NC, NA = "Non classificato", "Non applicabile"
REGIONS = ["USA", "Europa (ex Italia)", "Italia", "Giappone", "Altri sviluppati", "Mercati emergenti", NC, NA]
SECTORS = [
    "Tecnologia", "Finanza", "Industria", "Beni ciclici", "Sanità", "Comunicazione",
    "Beni difensivi", "Energia", "Materiali", "Utility", "Immobiliare", NC, NA,
]
SECTOR_WARN = 30.0  # soglia di allerta per un singolo settore (% dell'azionario)


def _sec(tec, fin, ind, cic, san, com, dif, ene, mat, uti, imm):
    return {"Tecnologia": tec, "Finanza": fin, "Industria": ind, "Beni ciclici": cic,
            "Sanità": san, "Comunicazione": com, "Beni difensivi": dif, "Energia": ene,
            "Materiali": mat, "Utility": uti, "Immobiliare": imm}


def _reg(usa, eu, it, jp, oth, em):
    return {"USA": usa, "Europa (ex Italia)": eu, "Italia": it, "Giappone": jp,
            "Altri sviluppati": oth, "Mercati emergenti": em}


# Valori APPROSSIMATI (da verificare sulle schede dei fornitori: cambiano ogni anno).
# Chiave = ticker senza suffisso di borsa.
EXPOSURE_DB = {
    "SWDA": {"regions": _reg(71, 14.5, 0.5, 6, 8, 0), "sectors": _sec(26, 16, 11, 10, 10, 9, 6, 4, 3.5, 2.5, 2)},
    "XWLD": {"regions": _reg(60, 21, 1, 8, 10, 0), "sectors": _sec(12, 22, 11, 6, 13, 7, 8, 7, 5, 4.5, 4.5)},
    "XACT": {"regions": _reg(63, 13.5, 0.5, 5.5, 7.5, 10), "sectors": _sec(26, 16, 11, 11, 9, 8, 5.5, 4, 4, 2.5, 3)},
    "XMME": {"regions": _reg(0, 0, 0, 0, 0, 100), "sectors": _sec(26, 22, 7, 12, 3.5, 9, 5, 5, 6, 2.5, 2)},
    "XNDX": {"regions": _reg(100, 0, 0, 0, 0, 0), "sectors": _sec(55, 0.5, 4, 13, 5, 15, 5, 0.5, 0.5, 1.5, 0)},
    "XUSE": {"regions": _reg(100, 0, 0, 0, 0, 0), "sectors": _sec(33, 13, 8.5, 10.5, 10, 10, 5, 3, 2.5, 2.5, 2)},
    "XR2K": {"regions": _reg(100, 0, 0, 0, 0, 0), "sectors": _sec(14, 18, 18, 10, 16, 3, 3, 5, 4, 3, 6)},
    "ISP": {"regions": _reg(0, 0, 100, 0, 0, 0), "sectors": _sec(0, 100, 0, 0, 0, 0, 0, 0, 0, 0, 0)},
}


def default_exposure(sym, name, asset_class):
    key = sym.upper().split(".")[0]
    if key in EXPOSURE_DB:
        return dict(EXPOSURE_DB[key]["regions"]), dict(EXPOSURE_DB[key]["sectors"])
    if asset_class == BOND:
        italy = "BTP" in f"{sym} {name}".upper()
        return ({"Italia": 100.0} if italy else {NC: 100.0}), {NA: 100.0}
    if asset_class in (CASH, "Materie Prime (Oro)"):
        return {NA: 100.0}, {NA: 100.0}
    return {NC: 100.0}, {NC: 100.0}


def df_to_exposure(df, col):
    vals = {r[col]: float(r["%"]) for _, r in df.iterrows() if float(r["%"]) > 0}
    tot = sum(vals.values())
    return {k: v / tot * 100 for k, v in vals.items()} if tot > 0 else {NC: 100.0}


# ----------------------------------------------------------------------------
# UTILITY
# ----------------------------------------------------------------------------
def esc(x):
    return html.escape(str(x))


def eur(x, decimals=0):
    s = f"{x:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"


def guess_class(sym, name, is_bond):
    s = f"{sym} {name}".upper()
    if sym.upper() == "CASH" or "LIQUIDIT" in s:
        return CASH
    if is_bond or "BTP" in s or "BOND" in s:
        return BOND
    if "GOLD" in s or "ORO" in s:
        return "Materie Prime (Oro)"
    if any(k in s for k in ("EMERGING", "XMME")):
        return "Azionario Emergenti"
    if any(k in s for k in ("NASDAQ", "NDX", "RUSSELL", "S&P", "MSCI USA", "XUSE", "SP500")):
        return "Azionario USA"
    if any(k in s for k in ("WORLD", "SWDA", "XACT", "XWLD", "ACWI")):
        return "Azionario Globale"
    return "Azionario Italia/Altro"


# ----------------------------------------------------------------------------
# PERSISTENZA
# ----------------------------------------------------------------------------
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f), None
        except Exception as e:
            try:
                shutil.copy(path, path + ".bak")
            except Exception:
                pass
            return default, (
                f"Il file {path} non era leggibile ({e}). Ne ho salvato una copia"
                f" in {path}.bak; sto usando i dati di default."
            )
    return default, None


def save_json(path, data):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except Exception as e:
        st.warning(f"Salvataggio non riuscito: {e}")


def default_portfolio():
    def p(qty, name, price, is_bond=False):
        return {"qty": qty, "name": name, "is_bond": is_bond, "manual_price": price}

    return {
        "ISP.MI": p(250.0, "Intesa Sanpaolo", 6.116),
        "GOLD": p(10.0, "Amundi Physical Gold ETC", 148.21),
        "SWDA.MI": p(87.0, "iShares Core MSCI World UCITS ETF", 131.67),
        "XMME.MI": p(15.0, "Xtrackers MSCI Emerging Markets", 82.998),
        "XNDX.MI": p(10.0, "Xtrackers NASDAQ 100", 63.88),
        "XACT.MI": p(101.0, "Xtrackers FTSE All-World", 9.644),
        "XUSE.MI": p(16.0, "Xtrackers MSCI USA", 206.2),
        "XWLD.MI": p(21.0, "Xtrackers MSCI World Value", 74.09),
        "XR2K.MI": p(1.0, "Xtrackers Russell 2000", 371.82),
        "BTP-2067": p(14.0, "BTP Tf 2.8% Mz67", 63.85, True),
    }


def normalize_portfolio(port):
    """Aggiunge i campi nuovi ai dati vecchi senza perdere nulla."""
    for sym, d in port.items():
        d.setdefault("name", sym)
        d.setdefault("qty", 0.0)
        d.setdefault("is_bond", False)
        d.setdefault("manual_price", 0.0)
        d.setdefault("avg_cost", 0.0)  # prezzo medio di carico (PMC)
        d.setdefault("force_manual", bool(d["is_bond"]))
        if sym.upper() == "CASH":
            d["force_manual"], d["manual_price"], d["is_bond"] = True, 1.0, False
        d.setdefault("coupon", None)
        d.setdefault("maturity_year", None)
        if d.get("asset_class") not in ASSET_CLASSES:
            d["asset_class"] = guess_class(sym, d["name"], d["is_bond"])
        if not d.get("regions") or not d.get("sectors"):
            reg, sec = default_exposure(sym, d["name"], d["asset_class"])
            if not d.get("regions"):
                d["regions"] = reg
            if not d.get("sectors"):
                d["sectors"] = sec
    return port


# ----------------------------------------------------------------------------
# DATI DA YAHOO FINANCE (chiamate in parallelo, cache 5 minuti)
# ----------------------------------------------------------------------------
def _fetch_one(sym):
    try:
        t = yf.Ticker(sym)
        closes = t.history(period="5d")["Close"].dropna()
        if len(closes) == 0:
            return sym, None
        cur = float(closes.iloc[-1])
        prev = float(closes.iloc[-2]) if len(closes) > 1 else cur
        chg = (cur - prev) / prev * 100 if prev else 0.0
        try:
            ccy = t.fast_info.get("currency")
        except Exception:
            ccy = None
        return sym, {"price": cur, "change": chg, "currency": ccy}
    except Exception:
        return sym, None


@st.cache_data(ttl=300, show_spinner="Scarico i prezzi da Yahoo Finance...")
def fetch_quotes(symbols):
    syms = sorted({s.upper().strip() for s in symbols if s})
    if not syms:
        return {}, datetime.now().strftime("%d/%m/%Y %H:%M")
    with ThreadPoolExecutor(max_workers=8) as ex:
        res = dict(ex.map(_fetch_one, syms))
    return res, datetime.now().strftime("%d/%m/%Y %H:%M")


def fx_factor(ccy, quotes):
    """Moltiplicatore per convertire un prezzo nella valuta `ccy` in euro."""
    if not ccy or ccy == "EUR":
        return 1.0
    pairs = {"USD": ("EURUSD=X", 1.0), "GBP": ("EURGBP=X", 1.0), "GBp": ("EURGBP=X", 100.0)}
    if ccy not in pairs:
        return None
    pair, div = pairs[ccy]
    q = quotes.get(pair)
    if not q or not q["price"]:
        return None
    return 1.0 / (q["price"] * div)


def build_positions(portfolio):
    fx_syms = ("EURUSD=X", "EURGBP=X")
    to_fetch = tuple(s for s, d in portfolio.items() if not d["force_manual"]) + fx_syms
    quotes, ts = fetch_quotes(to_fetch)
    items, warns = [], []

    for sym, d in portfolio.items():
        q = None if d["force_manual"] else quotes.get(sym.upper())
        price, change, source, ccy, fx = None, None, "n/d", "EUR", 1.0

        if q:
            price, change, source = q["price"], q["change"], "Yahoo"
            ccy = q.get("currency") or "EUR"
            f = fx_factor(ccy, quotes)
            if f is None:
                warns.append(f"{sym}: valuta {ccy} non convertibile, valore non affidabile.")
                f = 1.0
            fx = f
        elif d["manual_price"] > 0:
            price, change = d["manual_price"], None
            source = "liquidità" if d["asset_class"] == CASH else "manuale"
            if not d["force_manual"]:
                warns.append(f"{sym}: Yahoo non risponde, uso il prezzo manuale.")
        else:
            warns.append(f"{sym}: prezzo non disponibile (valore escluso dal totale).")

        if price is None:
            valore = 0.0
        elif d["is_bond"]:
            valore = d["qty"] * 1000.0 * price / 100.0
        else:
            valore = d["qty"] * price * fx

        cost = 0.0
        if d["avg_cost"] > 0:
            cost = d["qty"] * 1000.0 * d["avg_cost"] / 100.0 if d["is_bond"] else d["qty"] * d["avg_cost"]
        pnl = (valore - cost) if (cost > 0 and price is not None) else None

        items.append({
            "ticker": sym, "name": d["name"], "qty": d["qty"], "price": price,
            "change": change, "valore": valore, "is_bond": d["is_bond"],
            "source": source, "ccy": ccy, "cost": cost, "pnl": pnl,
            "asset_class": d["asset_class"],
        })
    return items, warns, ts


# ----------------------------------------------------------------------------
# MODELLI: PAC (Monte Carlo log-normale) e FIRE
# ----------------------------------------------------------------------------
def bond_net_return(sym, d, price_pct):
    """Rendimento netto approssimato a scadenza (cedola + pull-to-par)."""
    coupon = d.get("coupon")
    if not coupon:
        m = re.search(r"(\d+[.,]?\d*)\s*%", d.get("name", ""))
        coupon = float(m.group(1).replace(",", ".")) if m else None
    year = d.get("maturity_year")
    if not year:
        m = re.search(r"(20\d{2})", sym) or re.search(r"[A-Za-z]{2}(\d{2})\b", d.get("name", ""))
        if m:
            y = int(m.group(1))
            year = y if y > 100 else 2000 + y
    if coupon is None:
        return 0.03
    price = price_pct if price_pct and price_pct > 0 else 100.0
    n = max(int(year) - datetime.now().year, 1) if year else None
    gross = (coupon + (100.0 - price) / n) / ((100.0 + price) / 2.0) if n else coupon / price
    return max(gross * (1 - BOND_TAX), 0.0)


def portfolio_stats(weights, items_by_sym, portfolio, rho):
    """Rendimento e volatilità del portafoglio con correlazione media rho."""
    mu = a = b = 0.0
    for sym, w in weights.items():
        d = portfolio[sym]
        r, v = ASSUMPTIONS[d["asset_class"]]
        if r is None:
            r = bond_net_return(sym, d, items_by_sym[sym]["price"])
        mu += w * r
        a += w * v
        b += (w * v) ** 2
    var = (1 - rho) * b + rho * a ** 2
    return mu, float(np.sqrt(var))


def run_monte_carlo(start, contrib, mu, sigma, years, n=3000, seed=42):
    months = int(years * 12)
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((months, n))
    factors = np.exp((mu - 0.5 * sigma ** 2) / 12 + sigma / np.sqrt(12) * z)
    paths = np.empty((months + 1, n))
    paths[0] = start
    for m in range(1, months + 1):
        paths[m] = (paths[m - 1] + contrib) * factors[m - 1]
    return paths


def aggregate_exposure(items, portfolio, field, only_equity):
    """Somma in euro l'esposizione di ogni posizione (look-through)."""
    tot = {}
    for it in items:
        if it["valore"] <= 0:
            continue
        if only_equity and not it["asset_class"].startswith("Azionario"):
            continue
        exp = portfolio[it["ticker"]].get(field) or {NC: 100.0}
        s = sum(exp.values()) or 1.0
        for k, v in exp.items():
            tot[k] = tot.get(k, 0.0) + it["valore"] * v / s
    return tot


def render_exposure(label, data, bench, palette, max_weight=None):
    total = sum(data.values())
    if total <= 0:
        st.info("Nessun dato disponibile.")
        return
    pct = {k: v / total * 100 for k, v in data.items() if v > 0}

    df = pd.DataFrame({label: list(pct.keys()), "valore": list(pct.values())})
    fig = px.pie(df, names=label, values="valore", hole=0.4, color_discrete_sequence=palette)
    fig.update_layout(template="plotly_dark", paper_bgcolor="#161b22", plot_bgcolor="#161b22", margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, **STRETCH)

    known = {k: v for k, v in pct.items() if k not in (NC, NA)}
    kt = sum(known.values())
    if kt > 0:
        eff = 1.0 / sum((v / kt) ** 2 for v in known.values())
        st.metric(f"Diversificazione effettiva ({label.lower()})", f"{eff:.1f}")
        st.caption(f"Numero di {label.lower()} \"equivalenti\" se il peso fosse uguale: 1 = tutto in una voce, più è alto meglio.")
        if max_weight:
            big_k, big_v = max(known.items(), key=lambda kv: kv[1])
            if big_v > max_weight:
                st.warning(f"⚠️ **{big_k}** pesa il **{big_v:.1f}%** dell'azionario (soglia {max_weight:.0f}%).")
    if pct.get(NC, 0) > 5:
        st.warning(f"{pct[NC]:.1f}% del patrimonio è \"non classificato\": completa i dati dalla matita ✏️ di ogni titolo.")

    if bench:
        bt = sum(bench.values())
        bpct = {k: v / bt * 100 for k, v in bench.items()}
        cats = sorted(set(pct) | set(bpct), key=lambda k: -pct.get(k, 0))
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(y=cats, x=[pct.get(k, 0) for k in cats], name="Tu", orientation="h", marker_color="#1f6feb"))
        fig2.add_trace(go.Bar(y=cats, x=[bpct.get(k, 0) for k in cats], name="MSCI World", orientation="h", marker_color=GREY))
        fig2.update_layout(
            barmode="group", template="plotly_dark", paper_bgcolor="#161b22", plot_bgcolor="#161b22",
            yaxis=dict(autorange="reversed"), xaxis_title="% dell'azionario",
            height=max(300, 55 * len(cats)), margin=dict(t=30, b=10, l=10, r=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig2, **STRETCH)
        diffs = [(pct.get(k, 0) - bpct.get(k, 0), k) for k in cats if k not in (NC, NA)]
        over = [f"{k} {d:+.0f} pt" for d, k in sorted(diffs, reverse=True) if d >= 5]
        under = [f"{k} {d:+.0f} pt" for d, k in sorted(diffs) if d <= -5]
        if over:
            st.info("📈 Sovrappeso rispetto al benchmark: " + ", ".join(over))
        if under:
            st.info("📉 Sottopeso rispetto al benchmark: " + ", ".join(under))
        st.caption("Benchmark: MSCI World (valori approssimativi). Non è un obiettivo: è solo un punto di riferimento.")


# ----------------------------------------------------------------------------
# STATO SESSIONE
# ----------------------------------------------------------------------------
if "portfolio" not in st.session_state:
    port, warn = load_json(PORTFOLIO_FILE, default_portfolio())
    st.session_state.portfolio = normalize_portfolio(port)
    st.session_state.load_warning = warn
if "watchlists" not in st.session_state:
    wl, warn = load_json(WATCHLIST_FILE, {"Da seguire": ["SWDA.MI", "ISP.MI", "AAPL"]})
    st.session_state.watchlists = wl
    st.session_state.wl_warning = warn

portfolio = st.session_state.portfolio

# ----------------------------------------------------------------------------
# SIDEBAR
# ----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ Pannello di Controllo")
    st.write("Svuota la cache e scarica prezzi freschi da Yahoo Finance.")
    if st.button("🔄 Aggiorna da Yahoo Finance", type="primary"):
        st.cache_data.clear()
        st.rerun()
    ts_box = st.empty()
    st.divider()
    st.info("💡 Clicca sulla matita ✏️ accanto a ogni titolo per modificarlo.")
    st.caption(
        "Su Streamlit Cloud i file JSON si cancellano a ogni riavvio: per"
        " pubblicare l'app serve un database esterno."
    )

tab_mercati, tab_portafoglio, tab_analisi, tab_watchlist = st.tabs(
    ["Mercati", "Portafoglio", "Analisi", "Watchlist"]
)

# ----------------------------------------------------------------------------
# 1. MERCATI
# ----------------------------------------------------------------------------
market_symbols = {
    "FTSE MIB": "^FTSEMIB", "Euro Stoxx 50": "^STOXX50E", "DAX": "^GDAXI",
    "S&P 500": "^GSPC", "Nasdaq 100": "^NDX", "Oro (USD/oz)": "GC=F",
    "Petrolio Brent": "BZ=F",
}

with tab_mercati:
    mq, _ = fetch_quotes(tuple(market_symbols.values()))
    evaluated = [(n, mq[s.upper()]) for n, s in market_symbols.items() if mq.get(s.upper())]
    missing = [n for n, s in market_symbols.items() if not mq.get(s.upper())]

    pos = sum(1 for _, q in evaluated if q["change"] >= 0)
    bullish = pos >= len(evaluated) / 2 if evaluated else True
    header_bg = (
        "linear-gradient(135deg, #238636, #113822)" if bullish
        else "linear-gradient(135deg, #da3633, #3b171c)"
    )
    st.markdown(
        f"""<div style="background: {header_bg}; padding: 20px; border-radius: 10px; margin-bottom: 15px;">
        <h1 style="color: white; margin: 0; font-size: 24px;">Mercati</h1>
        <p style="color: #c9d1d9; margin: 5px 0 0 0; font-size: 13px;">Ultima chiusura / prezzo disponibile</p></div>""",
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns(2)
    for i, (name, q) in enumerate(evaluated):
        is_pos = q["change"] >= 0
        cls = "market-card-pos" if is_pos else "market-card-neg"
        color = GREEN if is_pos else RED
        sign = "+" if is_pos else ""
        with (col1 if i % 2 == 0 else col2):
            st.markdown(
                f"""<div class="{cls}"><h4 style="margin:0; color: white; font-size: 14px;">{esc(name)}</h4>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px;">
                <span style="font-size: 16px; font-weight: bold; color: white;">{q['price']:,.2f}</span>
                <span style="font-size: 13px; font-weight: bold; color: {color};">{sign}{q['change']:.2f}%</span>
                </div></div>""",
                unsafe_allow_html=True,
            )
    if missing:
        st.caption(f"Dati non disponibili: {', '.join(missing)}")

# ----------------------------------------------------------------------------
# 2. PORTAFOGLIO
# ----------------------------------------------------------------------------
items, warns, ts = build_positions(portfolio)
ts_box.caption(f"Ultimo aggiornamento prezzi: {ts}")
items_by_sym = {it["ticker"]: it for it in items}

total_net_worth = sum(it["valore"] for it in items)
daily_eur = sum(it["valore"] * (it["change"] or 0.0) / 100.0 for it in items)
prev_nw = total_net_worth - daily_eur
daily_pct = daily_eur / prev_nw * 100 if prev_nw > 0 else 0.0
total_cost = sum(it["cost"] for it in items if it["pnl"] is not None)
total_pnl = sum(it["pnl"] for it in items if it["pnl"] is not None)

with tab_portafoglio:
    if st.session_state.get("load_warning"):
        st.warning(st.session_state.load_warning)
    if warns:
        st.warning("\n\n".join(f"⚠️ {w}" for w in warns))

    chg_color = GREEN if daily_eur >= 0 else RED
    sign = "+" if daily_eur >= 0 else ""
    pnl_line = ""
    if total_cost > 0:
        ps = "+" if total_pnl >= 0 else ""
        pc = GREEN if total_pnl >= 0 else RED
        pnl_line = (
            f'<p style="color:{pc}; margin:2px 0 0 0; font-size:13px;">P&L totale: {ps}{eur(total_pnl)}'
            f" ({ps}{total_pnl / total_cost * 100:.2f}%)</p>"
        )
    st.markdown(
        f"""<div style="background: linear-gradient(135deg, #1f6feb, #113822); padding: 20px; border-radius: 10px; margin-bottom: 15px;">
        <h3 style="color: #8b94e0; margin: 0; font-size: 14px;">Patrimonio netto</h3>
        <h1 style="color: white; margin: 4px 0; font-size: 32px;">{eur(total_net_worth, 2)}</h1>
        <p style="color: {chg_color}; margin: 0; font-size: 14px; font-weight: bold;">
        Oggi: {sign}{eur(daily_eur, 2)} ({sign}{daily_pct:.2f}%)</p>{pnl_line}</div>""",
        unsafe_allow_html=True,
    )

    # --- Aggiunta posizione ---
    with st.expander("➕ Aggiungi posizione"):
        with st.form("add_position_form", clear_on_submit=True):
            ca, cb = st.columns(2)
            new_ticker = ca.text_input("Ticker (Yahoo) / codice", help="Per la liquidità scrivi CASH e usa la quantità come importo in €.")
            new_name = cb.text_input("Nome")
            new_qty = ca.number_input("Quantità / Lotti", min_value=0.0, value=1.0, step=1.0)
            new_price = cb.number_input("Prezzo manuale (€ o %; 0 = Yahoo)", min_value=0.0, value=0.0, step=0.01)
            new_cost = ca.number_input("Prezzo medio di carico (0 = n/d)", min_value=0.0, value=0.0, step=0.01)
            new_cls = cb.selectbox("Asset class", ["Auto"] + ASSET_CLASSES)
            new_is_bond = st.checkbox("Obbligazione/BTP? (prezzo in %, lotti da 1.000 €)")
            cc1, cc2 = st.columns(2)
            new_coupon = cc1.number_input("Cedola % (solo obbligazioni)", min_value=0.0, value=0.0, step=0.05)
            new_mat = cc2.number_input("Anno scadenza (solo obbligazioni)", min_value=0, max_value=2100, value=0, step=1)
            if st.form_submit_button("Conferma e salva"):
                t = new_ticker.upper().strip()
                if not t:
                    st.error("Inserisci un ticker.")
                elif t in portfolio:
                    st.error(f"{t} è già presente: modificalo con la matita.")
                else:
                    is_cash = t == "CASH"
                    name = new_name.strip() or ("Liquidità" if is_cash else t)
                    portfolio[t] = {
                        "qty": new_qty, "name": name, "is_bond": new_is_bond and not is_cash,
                        "manual_price": 1.0 if is_cash else new_price, "avg_cost": 0.0 if is_cash else new_cost,
                        "force_manual": new_is_bond or is_cash,
                        "coupon": new_coupon or None, "maturity_year": int(new_mat) or None,
                        "asset_class": CASH if is_cash else (guess_class(t, name, new_is_bond) if new_cls == "Auto" else new_cls),
                    }
                    normalize_portfolio({t: portfolio[t]})  # regioni/settori di default
                    save_json(PORTFOLIO_FILE, portfolio)
                    st.rerun()

    st.markdown("<hr style='margin: 12px 0; border-color: #30363d;'>", unsafe_allow_html=True)
    st.subheader("Posizioni")

    for it in items:
        sym = it["ticker"]
        key_edit = f"edit_active_{sym}"
        st.session_state.setdefault(key_edit, False)

        csym = CCY_SYMBOL.get(it["ccy"], it["ccy"])
        if it["asset_class"] == CASH:
            p_disp = "liquidità"
        elif it["price"] is None:
            p_disp = "n/d"
        elif it["is_bond"]:
            p_disp = f"{it['price']:.2f}%"
        else:
            p_disp = f"{it['price']:,.2f} {csym}"
        badge = " (BTP)" if it["is_bond"] else ""
        src = f"<span style='color:{GREY}; font-size:10px;'> · {esc(it['source'])}</span>"
        pnl_html = ""
        if it["pnl"] is not None:
            ps = "+" if it["pnl"] >= 0 else ""
            pc = GREEN if it["pnl"] >= 0 else RED
            pnl_html = f" | <span style='color:{pc};'>P&L {ps}{eur(it['pnl'])}</span>"

        if it["change"] is None:
            chg_html = f"<span style='color:{GREY};'>—</span>"
        else:
            cs = "+" if it["change"] >= 0 else ""
            cc = GREEN if it["change"] >= 0 else RED
            chg_html = f"<span style='color:{cc};'>{cs}{it['change']:.2f}%</span>"

        cols = st.columns([4.8, 1.5, 0.7], gap="small")
        with cols[0]:
            st.markdown(
                f"""<div style="font-size: 13px; line-height: 1.3;">
                <b>{esc(sym)}{badge}</b> <span style="color: {GREY}; font-size: 11px; margin-left: 4px;">{p_disp}</span>{src}<br>
                <span style="font-size: 11px; color: #c9d1d9;">Qt: {it['qty']:g} | Tot: <b>{eur(it['valore'])}</b>{pnl_html}</span></div>""",
                unsafe_allow_html=True,
            )
        with cols[1]:
            st.markdown(
                f"<div style='text-align:center; font-size:16px; font-weight:bold; padding-top:4px;'>{chg_html}</div>",
                unsafe_allow_html=True,
            )
        with cols[2]:
            if st.button("✏️", key=f"btn_edit_{sym}", help="Gestisci / Modifica"):
                st.session_state[key_edit] = not st.session_state[key_edit]
                st.rerun()

        if st.session_state[key_edit]:
            d = portfolio[sym]
            e1, e2 = st.columns(2)
            up_q = e1.number_input("Importo (€)" if sym.upper() == "CASH" else "Quantità / Lotti", value=float(d["qty"]), step=1.0, key=f"q_{sym}")
            up_p = e2.number_input("Prezzo manuale (€ o %)", min_value=0.0, value=float(d["manual_price"]), step=0.01, key=f"p_{sym}")
            e3, e4 = st.columns(2)
            up_cost = e3.number_input("Prezzo medio carico (0 = n/d)", min_value=0.0, value=float(d["avg_cost"]), step=0.01, key=f"c_{sym}")
            up_cls = e4.selectbox("Asset class", ASSET_CLASSES, index=ASSET_CLASSES.index(d["asset_class"]), key=f"k_{sym}")
            up_force = st.checkbox("Usa sempre il prezzo manuale (ignora Yahoo)", value=d["force_manual"], key=f"f_{sym}")
            up_coupon, up_mat = d.get("coupon"), d.get("maturity_year")
            if d["is_bond"]:
                b1, b2 = st.columns(2)
                up_coupon = b1.number_input("Cedola %", min_value=0.0, value=float(d.get("coupon") or 0.0), step=0.05, key=f"cp_{sym}") or None
                up_mat = int(b2.number_input("Anno scadenza", min_value=0, max_value=2100, value=int(d.get("maturity_year") or 0), step=1, key=f"mt_{sym}")) or None
            with st.expander("🌍 Regioni e settori (% del titolo)"):
                st.caption("Valori da verificare sulla scheda del fornitore. Vengono normalizzati a 100%.")
                col_cfg = {"%": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=0.5)}
                reg_df = pd.DataFrame({"Regione": REGIONS, "%": [float(d["regions"].get(r, 0.0)) for r in REGIONS]})
                up_reg = st.data_editor(reg_df, hide_index=True, disabled=["Regione"], column_config=col_cfg, key=f"reg_{sym}", **STRETCH)
                st.caption(f"Somma regioni: {up_reg['%'].sum():.1f}%")
                up_sec = None
                if d["asset_class"].startswith("Azionario"):
                    sec_df = pd.DataFrame({"Settore": SECTORS, "%": [float(d["sectors"].get(x, 0.0)) for x in SECTORS]})
                    up_sec = st.data_editor(sec_df, hide_index=True, disabled=["Settore"], column_config=col_cfg, key=f"sec_{sym}", **STRETCH)
                    st.caption(f"Somma settori: {up_sec['%'].sum():.1f}%")
            s1, s2 = st.columns(2)
            if s1.button("💾 Salva", key=f"save_{sym}", **STRETCH):
                d.update({
                    "qty": up_q, "manual_price": up_p, "avg_cost": up_cost,
                    "asset_class": up_cls, "force_manual": up_force,
                    "coupon": up_coupon, "maturity_year": up_mat,
                    "regions": df_to_exposure(up_reg, "Regione"),
                    "sectors": df_to_exposure(up_sec, "Settore") if up_sec is not None else d["sectors"],
                })
                save_json(PORTFOLIO_FILE, portfolio)
                st.session_state[key_edit] = False
                st.rerun()
            if s2.button("🗑️ Elimina titolo", key=f"del_{sym}", **STRETCH):
                del portfolio[sym]
                for k in list(st.session_state.keys()):
                    if k.endswith(f"_{sym}"):
                        del st.session_state[k]
                save_json(PORTFOLIO_FILE, portfolio)
                st.rerun()

        st.markdown("<hr style='margin: 4px 0; border-color: #21262d;'>", unsafe_allow_html=True)

    st.divider()

    # Variabili condivise tra PAC e FIRE
    mu = sigma = monthly_contrib = 0.0
    model_ok = False

    if not items:
        st.info("Aggiungi almeno una posizione per usare i simulatori.")
    else:
        # --- Simulatore PAC ---
        with st.expander("📊 Simulazione PAC (Monte Carlo)"):
            m1, m2, m3 = st.columns(3)
            pac_amount = m1.number_input("Importo PAC (€)", min_value=0.0, value=300.0, step=50.0)
            pac_freq = m2.selectbox("Frequenza", ["Mensile", "Settimanale", "Trimestrale"])
            years = m3.number_input("Anni", min_value=1, max_value=40, value=20)
            rho = st.slider(
                "Correlazione media tra asset", 0.0, 1.0, 0.7, 0.05,
                help="1 = si muovono tutti insieme (nessuna diversificazione); 0 = indipendenti.",
            )
            monthly_contrib = {
                "Mensile": pac_amount,
                "Settimanale": pac_amount * 52 / 12,
                "Trimestrale": pac_amount / 3,
            }[pac_freq]

            st.markdown("##### Ripartizione del PAC")
            st.caption("Spunta/deseleziona i titoli e modifica i pesi: vengono normalizzati a 100%.")
            tickers = list(portfolio.keys())
            base = pd.DataFrame({
                "Ticker": tickers,
                "Incluso": True,
                "Peso %": [
                    round(items_by_sym[t]["valore"] / total_net_worth * 100, 1) if total_net_worth > 0 else 0.0
                    for t in tickers
                ],
            })
            edited = st.data_editor(
                base, hide_index=True, disabled=["Ticker"],
                column_config={"Peso %": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=1.0)},
                key=f"pac_editor_{abs(hash(tuple(tickers)))}", **STRETCH,
            )
            sel = edited[edited["Incluso"] & (edited["Peso %"] > 0)]
            total_w = float(sel["Peso %"].sum())

            if total_w <= 0:
                st.warning("Seleziona almeno un titolo con peso maggiore di zero.")
            else:
                weights = {r["Ticker"]: r["Peso %"] / total_w for _, r in sel.iterrows()}
                mu, sigma = portfolio_stats(weights, items_by_sym, portfolio, rho)
                model_ok = True
                st.caption(
                    f"Ipotesi del modello: rendimento atteso {mu * 100:.1f}% annuo,"
                    f" volatilità {sigma * 100:.1f}% annua. Sono ipotesi, non previsioni."
                    " (Rendimenti per asset class in cima al codice.)"
                )

                paths = run_monte_carlo(total_net_worth, monthly_contrib, mu, sigma, years)
                p10, p50, p90 = (np.percentile(paths, q, axis=1) for q in (10, 50, 90))
                months = paths.shape[0] - 1
                invested = total_net_worth + monthly_contrib * np.arange(months + 1)

                r1, r2, r3 = st.columns(3)
                r1.metric("Pessimista (10° perc.)", eur(p10[-1]))
                r2.metric("Neutro (mediana)", eur(p50[-1]))
                r3.metric("Ottimista (90° perc.)", eur(p90[-1]))

                x = np.arange(months + 1) / 12
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=x, y=p90, name="Ottimista (90°)", line=dict(color="#238636")))
                fig.add_trace(go.Scatter(x=x, y=p50, name="Neutro (50°)", line=dict(color="#1f6feb", width=3)))
                fig.add_trace(go.Scatter(x=x, y=p10, name="Pessimista (10°)", line=dict(color="#da3633")))
                fig.add_trace(go.Scatter(x=x, y=invested, name="Capitale versato", line=dict(dash="dash", color=GREY)))
                fig.update_layout(
                    template="plotly_dark", paper_bgcolor="#161b22", plot_bgcolor="#161b22",
                    xaxis_title="Anni", yaxis_title="Valore (€)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(t=30, b=10, l=10, r=10),
                )
                st.plotly_chart(fig, **STRETCH)
                st.caption("3.000 scenari, rendimenti log-normali, versamento a inizio mese, valori nominali (non corretti per inflazione).")

        # --- Simulatore FIRE ---
        with st.expander("🔥 Simulatore FIRE"):
            if not model_ok:
                st.info("Imposta prima una ripartizione valida nel simulatore PAC (qui sopra).")
            else:
                f1, f2, f3 = st.columns(3)
                fire_exp = f1.number_input("Spesa mensile desiderata (€)", min_value=0.0, value=1150.0, step=50.0, key="fire_exp")
                age = f2.number_input("Età attuale", min_value=18, max_value=90, value=30, key="fire_age")
                swr = float(f3.selectbox("Prelievo sicuro (SWR)", ["4%", "3.5%", "3%"], key="fire_swr").rstrip("%")) / 100.0

                i1, i2, i3 = st.columns(3)
                use_inf = i1.checkbox("Includi inflazione", value=True, key="fire_use_inf")
                inf_rate = i2.number_input("Inflazione annua (%)", min_value=0.0, max_value=10.0, value=2.0, step=0.1, key="fire_inf", disabled=not use_inf)
                scen = i3.selectbox("Scenario", ["Neutro (Mediana)", "Pessimista (10°)", "Ottimista (90°)"], key="fire_scen")

                z = {"Pessimista (10°)": -1.2816, "Neutro (Mediana)": 0.0, "Ottimista (90°)": 1.2816}[scen]
                # Rendimento geometrico atteso, spostato di z deviazioni standard
                # su un orizzonte di riferimento di 20 anni (coerente con la mediana del PAC).
                eff = (mu - 0.5 * sigma ** 2) + z * sigma / np.sqrt(20)

                inf = inf_rate / 100.0 if use_inf else 0.0
                base_target = fire_exp * 12 / swr
                val, reached, months_needed, target_at = total_net_worth, False, 0, base_target

                if val >= base_target:
                    reached = True
                else:
                    for m in range(1, 12 * 70 + 1):
                        val = (val + monthly_contrib) * (1 + eff / 12.0)
                        tgt = base_target * (1 + inf) ** (m / 12.0)
                        if val >= tgt:
                            reached, months_needed, target_at = True, m, tgt
                            break

                if use_inf and reached and months_needed > 0:
                    st.markdown(f"#### 🎯 FIRE Number a quella data: **{eur(target_at)}**")
                    st.caption(f"In euro di oggi: {eur(base_target)}. Rendimento ipotizzato: {eff * 100:.1f}% annuo.")
                else:
                    st.markdown(f"#### 🎯 FIRE Number: **{eur(base_target)}**")
                    st.caption(f"Rendimento ipotizzato: {eff * 100:.1f}% annuo.")

                if reached:
                    yrs = months_needed / 12.0
                    st.success(f"🎉 [{scen}] Traguardo FIRE tra **{yrs:.1f} anni** (a **{age + yrs:.1f} anni**).")
                    prog = min(1.0, total_net_worth / target_at) if target_at > 0 else 1.0
                    st.progress(prog, text=f"Progresso attuale: {eur(total_net_worth)} / {eur(target_at)} ({prog * 100:.1f}%)")
                else:
                    st.warning(f"Con lo scenario [{scen}] e il PAC impostato servono più di 70 anni. Prova ad aumentare il PAC.")

# ----------------------------------------------------------------------------
# 3. ANALISI
# ----------------------------------------------------------------------------
with tab_analisi:
    st.markdown(
        '<div style="background: linear-gradient(135deg, #7c3aed, #4c1d95); padding: 20px; border-radius: 10px; margin-bottom: 15px;">'
        '<h1 style="color: white; margin: 0; font-size: 24px;">Analisi Portafoglio</h1>'
        '<p style="color: #ede9fe; margin: 5px 0 0 0; font-size: 13px;">Suddivisione e bilanciamento</p></div>',
        unsafe_allow_html=True,
    )
    if total_net_worth > 0:
        df = pd.DataFrame(items)
        df = df[df["valore"] > 0]

        def pie(names, values_df, palette):
            fig = px.pie(values_df, names=names, values="valore", hole=0.4, color_discrete_sequence=palette)
            fig.update_layout(template="plotly_dark", paper_bgcolor="#161b22", plot_bgcolor="#161b22", margin=dict(t=10, b=10, l=10, r=10))
            return fig

        st.subheader("📊 Ripartizione per ticker")
        st.plotly_chart(pie("ticker", df, px.colors.qualitative.Prism), **STRETCH)

        st.subheader("🌍 Ripartizione per asset class")
        grouped = df.groupby("asset_class", as_index=False)["valore"].sum()
        st.plotly_chart(pie("asset_class", grouped, px.colors.qualitative.Safe), **STRETCH)

        st.markdown("---")
        st.subheader("🗺️ Aree geografiche")
        scope = st.radio("Perimetro", ["Solo azionario", "Tutto il patrimonio"], horizontal=True, key="geo_scope")
        only_eq = scope == "Solo azionario"
        reg_data = aggregate_exposure(items, portfolio, "regions", only_eq)
        render_exposure("Regione", reg_data, EXPOSURE_DB["SWDA"]["regions"] if only_eq else None, px.colors.qualitative.Vivid)

        us_heavy = [
            it["ticker"] for it in items
            if it["valore"] > 0 and it["asset_class"].startswith("Azionario")
            and portfolio[it["ticker"]]["regions"].get("USA", 0) >= 50
        ]
        if len(us_heavy) >= 3:
            st.info(
                f"🔁 **Sovrapposizione:** {len(us_heavy)} titoli ({', '.join(us_heavy)}) hanno oltre il 50% in USA."
                " Le stesse grandi società compaiono in più fondi, quindi il numero di ETF sovrastima la diversificazione reale."
            )

        st.markdown("---")
        st.subheader("🏭 Settori (solo azionario)")
        sec_data = aggregate_exposure(items, portfolio, "sectors", True)
        render_exposure("Settore", sec_data, EXPOSURE_DB["SWDA"]["sectors"], px.colors.qualitative.Prism, max_weight=SECTOR_WARN)
        st.caption("Regioni e settori sono valori approssimativi dei fondi: verificali sulle schede dei fornitori e modificali dalla matita ✏️ di ogni titolo.")

        st.markdown("---")
        st.subheader("⚖️ Bilanciamento")
        df_inv = df[df["asset_class"] != CASH]
        top = df_inv.loc[df_inv["valore"].idxmax()] if len(df_inv) else df.loc[df["valore"].idxmax()]
        top_pct = top["valore"] / total_net_worth * 100
        if top_pct > 35:
            st.warning(f"⚠️ **{top['ticker']}** pesa il **{top_pct:.1f}%** del portafoglio: concentrazione sopra la soglia del 35%.")
        else:
            st.success("✅ Nessun singolo titolo supera il 35% del patrimonio.")

        eq = grouped[grouped["asset_class"].str.startswith("Azionario")]["valore"].sum()
        bd = grouped[grouped["asset_class"] == BOND]["valore"].sum()
        cm = grouped[grouped["asset_class"] == "Materie Prime (Oro)"]["valore"].sum()
        lq = grouped[grouped["asset_class"] == CASH]["valore"].sum()
        st.info(
            f"💡 Azionario ~{eq / total_net_worth * 100:.1f}% | Obbligazionario"
            f" ~{bd / total_net_worth * 100:.1f}% | Materie prime ~{cm / total_net_worth * 100:.1f}% | Liquidità ~{lq / total_net_worth * 100:.1f}%"
        )
    else:
        st.info("Aggiungi almeno una posizione con un prezzo valido per vedere l'analisi.")

# ----------------------------------------------------------------------------
# 4. WATCHLIST
# ----------------------------------------------------------------------------
with tab_watchlist:
    st.markdown(
        '<div style="background: linear-gradient(135deg, #d97706, #78350f); padding: 20px; border-radius: 10px; margin-bottom: 15px;">'
        '<h1 style="color: white; margin: 0; font-size: 24px;">Watchlist</h1>'
        '<p style="color: #fef3c7; margin: 5px 0 0 0; font-size: 13px;">Monitora i titoli di tuo interesse</p></div>',
        unsafe_allow_html=True,
    )
    wls = st.session_state.watchlists
    if st.session_state.get("wl_warning"):
        st.warning(st.session_state.wl_warning)

    selected = st.selectbox("Seleziona lista", list(wls.keys()))

    with st.expander("Nuova lista"):
        with st.form("new_list_form", clear_on_submit=True):
            nl = st.text_input("Nome lista")
            if st.form_submit_button("Crea") and nl.strip() and nl.strip() not in wls:
                wls[nl.strip()] = []
                save_json(WATCHLIST_FILE, wls)
                st.rerun()

    with st.form("add_wl_form", clear_on_submit=True):
        cw1, cw2 = st.columns([3, 1])
        t_new = cw1.text_input("Aggiungi ticker Yahoo (es. TSLA, SWDA.MI)")
        if cw2.form_submit_button("Aggiungi") and t_new.strip():
            t = t_new.upper().strip()
            if t not in wls[selected]:
                wls[selected].append(t)
                save_json(WATCHLIST_FILE, wls)
                st.rerun()

    wq, _ = fetch_quotes(tuple(wls[selected]))
    for sym in list(wls[selected]):
        q = wq.get(sym.upper())
        if q:
            csym = CCY_SYMBOL.get(q.get("currency"), q.get("currency") or "")
            p_str = f"{q['price']:,.2f} {csym}".strip()
            c = q["change"]
            c_col = GREEN if c >= 0 else RED
            c_html = f"{'+' if c >= 0 else ''}{c:.2f}%"
        else:
            p_str, c_col, c_html = "n.d.", GREY, "—"
        cw = st.columns([3.4, 0.6])
        with cw[0]:
            st.markdown(
                f'<div style="background-color: #161b22; padding: 10px 12px; border-radius: 8px; border: 1px solid #30363d;'
                f' display: flex; justify-content: space-between; align-items: center;"><div><b>{esc(sym)}</b></div>'
                f'<div style="text-align: right;"><b>{esc(p_str)}</b><br>'
                f'<span style="color: {c_col}; font-weight: bold; font-size: 11px;">{c_html}</span></div></div>',
                unsafe_allow_html=True,
            )
        with cw[1]:
            if st.button("❌", key=f"del_wl_{selected}_{sym}", help="Rimuovi"):
                wls[selected].remove(sym)
                save_json(WATCHLIST_FILE, wls)
                st.rerun()
