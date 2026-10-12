"""API keys, read from .streamlit/secrets.toml. Empty strings when a key isn't set."""

import streamlit as st


# Keys are read from .streamlit/secrets.toml. Set them there by hand, not through the UI.
try:
    API_KEY = st.secrets.get("FINNHUB_API_KEY", "")          # Finnhub: real-time price
    ALPACA_KEY = st.secrets.get("ALPACA_API_KEY", "")        # Alpaca: real-time intraday bars
    ALPACA_SECRET = st.secrets.get("ALPACA_SECRET_KEY", "")
except Exception:
    API_KEY = ALPACA_KEY = ALPACA_SECRET = ""
