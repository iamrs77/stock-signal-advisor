"""API keys and settings, read from .streamlit/secrets.toml. Keys are empty strings when not set."""

import streamlit as st


# Keys are read from .streamlit/secrets.toml. Set them there by hand, not through the UI.
try:
    API_KEY = st.secrets.get("FINNHUB_API_KEY", "")          # Finnhub: real-time price
    ALPACA_KEY = st.secrets.get("ALPACA_API_KEY", "")        # Alpaca: real-time intraday bars
    ALPACA_SECRET = st.secrets.get("ALPACA_SECRET_KEY", "")
except Exception:
    API_KEY = ALPACA_KEY = ALPACA_SECRET = ""

# Public demo: everyone shares one server, so each visitor's trade log is kept in their own
# browser session instead of the shared daily_risk.json file.
try:
    DEMO_MODE = bool(st.secrets.get("DEMO_MODE", False))
except Exception:
    DEMO_MODE = False
