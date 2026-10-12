"""The Long-term tab: daily-bar verdict, live price, chart and backtest."""

import streamlit as st

import live
import signals

from views.api_keys import API_KEY
from views.data import cached_analyze, cached_backtest_lt
from views.shared import live_badge, lw_chart, render_backtest, render_signals, section, verdict_card
from views.theme import C_BLUE, C_PURPLE


@st.fragment(run_every="15s")
def live_price_ticker(ticker: str, api_key: str | None):
    """Last price, refreshed every 15s. Also shows pre-market and after-hours prices."""
    q = live.get_live_quote(ticker, api_key)
    if not q or q.price is None:
        st.caption("⚠️ Live price unavailable right now.")
        return
    delta = (f"{q.change:+.2f} ({q.percent:+.2f}%)"
             if (q.change is not None and q.percent is not None) else None)
    st.metric(label=f"{live_badge(q)}  ·  {q.ticker}  ·  {q.source}",
              value=f"{q.price:,.2f}", delta=delta)
    if q.state in ("PRE", "PREPRE", "POST", "POSTPOST") and q.regular_price:
        st.caption(f"Regular-session close: {q.regular_price:,.2f}")


# --------------------------------------------------------------------------- #
# Long-term (daily)
# --------------------------------------------------------------------------- #
def price_chart(a: signals.Analysis):
    lw_chart(a.df, overlays=[
        ("SMA50", C_BLUE, 2, "SMA 50"),
        ("SMA200", C_PURPLE, 2, "SMA 200"),
        ("BB_UPPER", "rgba(124,58,237,.40)", 1, ""),
        ("BB_LOWER", "rgba(124,58,237,.40)", 1, ""),
    ], mode="date", height=660)
    st.caption("Price · RSI · MACD, synced. Drag to pan, scroll to zoom, drag the dividers to resize panes.")


def show_analysis(a: signals.Analysis):
    meta = f"{a.currency} · daily bars" if a.currency else "daily bars"
    verdict_card(f"LONG-TERM · {a.ticker}", a.verdict, a.headline,
                 a.price, a.score, a.confidence, meta)

    left, right = st.columns([3, 2])
    with left:
        section("Why this verdict")
        render_signals(a.signals)
    with right:
        section("Snapshot")
        items = list(a.snapshot.items())
        for i in range(0, len(items), 2):
            cols = st.columns(2)
            for col, (k, v) in zip(cols, items[i:i + 2]):
                col.metric(k, v)

    st.divider()
    price_chart(a)


def render():
    """Render the Long-term tab and return the selected history window (the Watchlist uses it too)."""
    st.caption("Swing / long-term view — daily bars. The verdict follows the **200-day trend regime** "
               "(stay invested above it, step aside below it); RSI, MACD & Bollinger add context.")
    c1, c2 = st.columns([3, 1])
    ticker = c1.text_input("Ticker symbol", value="SOXL", label_visibility="collapsed",
                           placeholder="Enter a ticker, e.g. SOXL or NVDA").strip().upper()
    period = c2.selectbox("History window", ["6mo", "1y", "2y", "5y"], index=1,
                          key="lt_period", label_visibility="collapsed",
                          help="How much history to analyze.")
    if ticker:
        live_price_ticker(ticker, API_KEY)
        try:
            with st.spinner(f"Crunching {ticker.upper()}…"):
                analysis = cached_analyze(ticker, period)
            show_analysis(analysis)
        except Exception as e:
            st.error(f"Couldn't analyze **{ticker.upper()}**: {e}")

        with st.expander("🧪  Backtest these long-term signals",
                         expanded=st.session_state.get("lt_bt_done", False)):
            st.caption("Validate the 200-day trend-regime engine — the same one the Watchlist uses — on history.")
            lb1, lb2 = st.columns([2, 1], vertical_alignment="bottom")
            lb1.selectbox("History to test", ["2y", "5y", "max"], index=1, key="lt_bt_period")
            if lb2.button("▶  Run backtest", key="lt_bt_run", width="stretch"):
                st.session_state["lt_bt_done"] = True
            if st.session_state.get("lt_bt_done"):
                try:
                    with st.spinner("Backtesting…"):
                        res = cached_backtest_lt(ticker, st.session_state["lt_bt_period"])
                    render_backtest(res, rules="Rules tested: trend-regime, long-only — go long when price is "
                                               "ABOVE its 200-day average (BUY) and step aside when it drops BELOW "
                                               "(SELL); held across days; any still-open position is marked to the "
                                               "last close. ")
                except Exception as e:
                    st.error(f"Backtest failed: {e}")

    return period
