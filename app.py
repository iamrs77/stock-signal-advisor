"""
Stock Signal Advisor dashboard (Streamlit).

Run it with:   run.bat        (double-click it)
or:            .venv\\Scripts\\python.exe -m streamlit run app.py

Type a ticker and the app pulls real price data, calculates common technical indicators
and gives a BUY / SELL / HOLD verdict with the reasons behind it, for both intraday and
long-term timeframes. Not a prediction, and not financial advice.
"""

import streamlit as st

from views import help_tab, intraday_tab, know_tab, longterm_tab, watchlist_tab
from views.theme import CSS

st.set_page_config(page_title="Stock Signal Advisor", page_icon="📈", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# Layout
# --------------------------------------------------------------------------- #
st.markdown(
    '<div class="hero"><div class="hero-logo">📈</div>'
    '<div><h1>Stock Signal Advisor</h1></div></div>'
    '<div class="hero-sub">A disciplined, emotion-free second opinion — '
    'not a prediction, and not financial advice.</div>',
    unsafe_allow_html=True,
)

tab_intraday, tab_analyze, tab_watchlist, tab_know, tab_help = st.tabs(
    ["⚡ Intraday", "📊 Long-term", "📋 Watchlist", "🔬 Know your ticker", "ℹ️ How it works"])

with tab_intraday:
    intraday_tab.render()

with tab_analyze:
    period = longterm_tab.render()

# The Watchlist scans with the history window picked in the Long-term tab.
with tab_watchlist:
    watchlist_tab.render(period)

with tab_know:
    know_tab.render()

with tab_help:
    help_tab.render()

st.markdown(
    "<hr><div style='text-align:center;color:#94A3B8;font-size:12px;'>"
    "Stock Signal Advisor · prices via Finnhub & Yahoo Finance · not financial advice"
    "</div>", unsafe_allow_html=True,
)
