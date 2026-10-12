"""The Watchlist tab: scan several tickers with the long-term rules."""

import pandas as pd
import streamlit as st

from views.data import cached_analyze
from views.theme import VERDICT_EMOJI


def watchlist_view(tickers: list[str], period: str):
    rows = []
    progress = st.progress(0.0, text="Scanning…")
    for i, t in enumerate(tickers, start=1):
        try:
            a = cached_analyze(t, period)
            rows.append({
                "Ticker": a.ticker,
                "Verdict": f"{VERDICT_EMOJI[a.verdict]} {a.headline}",
                "Price": round(a.price, 2),
                "Score": a.score,
                "Agreement %": a.confidence,
                "RSI": a.snapshot.get("RSI (14)", ""),
            })
        except Exception as e:
            rows.append({"Ticker": t.upper(), "Verdict": "⚠️ error",
                         "Price": None, "Score": None, "Agreement %": None, "RSI": str(e)[:40]})
        progress.progress(i / len(tickers), text=f"Scanning… {t.upper()}")
    progress.empty()

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Score", ascending=False, na_position="last")
    st.dataframe(df, width="stretch", hide_index=True)


def render(period: str):
    """Render the Watchlist tab. `period` is the history window chosen in the Long-term tab."""
    st.caption("Scan several tickers at once (long-term). Verdicts follow the **200-day trend regime** — "
               "validated to roughly track the trend at about **half the drawdown** of buy-&-hold. "
               "It still gets chopped up on very choppy names (e.g. TSLA), so confirm any ticker in the "
               "Long-term tab's 🧪 Backtest before trusting it.")
    default_list = "AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA"
    raw = st.text_area("Tickers (comma or space separated)", value=default_list, height=80)
    if st.button("Scan watchlist", type="primary"):
        tickers = [t for t in raw.replace(",", " ").split() if t]
        if tickers:
            watchlist_view(tickers, period)
        else:
            st.warning("Add at least one ticker.")
