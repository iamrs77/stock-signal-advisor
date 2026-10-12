"""Cached data loaders. Each wraps the analysis modules with st.cache_data."""

import pandas as pd
import streamlit as st

import alpaca_data
import backtest
import intraday
import live
import signals

from views.api_keys import ALPACA_KEY, ALPACA_SECRET


@st.cache_data(ttl=900, show_spinner=False)
def cached_analyze(ticker: str, period: str):
    """Cache results for 15 min so flipping tabs doesn't re-hit Yahoo every time."""
    return signals.analyze(ticker, period=period)


# --------------------------------------------------------------------------- #
# Intraday
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=8, show_spinner=False)
def cached_intraday(ticker: str, interval: str):
    """Very short 8s cache (shorter than the refresh interval) so every refresh pulls fresh bars.
    The old 60s cache was the main reason the verdict lagged the live price. Uses Alpaca's
    real-time IEX feed when keys are set (falls back to Yahoo otherwise)."""
    alpaca = (ALPACA_KEY, ALPACA_SECRET) if (ALPACA_KEY and ALPACA_SECRET) else None
    return intraday.fetch_intraday(ticker, interval, alpaca=alpaca)


@st.cache_data(ttl=8, show_spinner=False)
def cached_quote(ticker: str, api_key: str | None):
    """Short 8s cache (< the refresh interval) so the live price feeding the verdict stays
    fresh, while a burst of reruns (e.g. toggling inputs) doesn't hammer the quote API."""
    return live.get_live_quote(ticker, api_key)


@st.cache_data(ttl=900, show_spinner=False)
def cached_daily_trend(ticker: str):
    return intraday.daily_trend(ticker)


@st.cache_data(ttl=600, show_spinner=False)
def cached_backtest(ticker: str, interval: str, use_htf: bool = True):
    return backtest.run_backtest(ticker, interval, use_htf=use_htf)


@st.cache_data(ttl=900, show_spinner=False)
def cached_backtest_lt(ticker: str, period: str):
    return backtest.run_backtest_lt(ticker, period)


@st.cache_data(ttl=21600, show_spinner=False)
def cached_behavior_stats(ticker: str):
    """Measured risk profile of a ticker (changes slowly, so cached for 6h). Shows where the move
    and the risk happen: overnight vs intraday split, 'straight-line' days, and
    decay risk. Daily only (~3y from Yahoo); the fine-grained intraday/15-min profile lives
    in cached_microstructure. Plain floats (cache-friendly) or None if too little history."""
    import numpy as np
    import yfinance as yf

    d = yf.download(ticker, period="3y", interval="1d", auto_adjust=True, progress=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d.dropna()
    if len(d) < 80:
        return None
    d = d.copy()
    d["prev"] = d["Close"].shift(1)
    d = d.dropna()
    gap = d["Open"] / d["prev"] - 1                 # overnight: prev 4pm close -> today 9:30 open
    intra = d["Close"] / d["Open"] - 1              # intraday : 9:30 open -> 4pm close
    total = d["Close"] / d["prev"] - 1
    ret = d["Close"].pct_change().dropna()
    vt = float(total.var()) or 1e-12
    b = {
        "n_daily": int(len(d)),
        "ann_vol": float(ret.std() * np.sqrt(252) * 100),
        "avg_range": float(((d["High"] - d["Low"]) / d["Close"]).mean() * 100),
        "pct_up": float((ret > 0).mean() * 100),
        "overnight_mean": float(gap.mean() * 100),
        "intraday_mean": float(intra.mean() * 100),
        "overnight_var_share": float(gap.var() / vt * 100),
        "gap_worst": float(gap.min() * 100),                       # worst overnight fall
        "gap_best": float(gap.max() * 100),                        # best overnight jump
        "overnight_abs_mean": float(gap.abs().mean() * 100),       # typical overnight move size
        "intraday_abs_mean": float(intra.abs().mean() * 100),      # typical daytime move size
        "gap_up_pct": float((gap > 0).mean() * 100),               # opens higher than yesterday's close
        "gap_big_pct": float((gap.abs() > 0.02).mean() * 100),     # nights that gap more than 2%
        "gap_cont_up_pct": float((intra[gap > 0.01] > 0).mean() * 100) if (gap > 0.01).any() else None,
        "flat_pct": float((intra.abs() < 0.005).mean() * 100),     # 'straight-line' days
    }

    # where is it now: position within the 52-week range + recent vs usual 'heat'
    last_close = float(d["Close"].iloc[-1])
    win = d.tail(252)
    hi52, lo52 = float(win["High"].max()), float(win["Low"].min())
    rng52 = (hi52 - lo52) or 1e-9
    recent_range = float(((d["High"] - d["Low"]) / d["Close"]).tail(10).mean() * 100)
    # best/worst day of week (avg daily return + range by weekday, Mon–Fri)
    names = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    dow_ret = ret.groupby(ret.index.dayofweek).mean() * 100
    day_rng = ((d["High"] - d["Low"]) / d["Close"])
    dow_rng = day_rng.groupby(day_rng.index.dayofweek).mean() * 100
    b.update({
        "last_close": last_close,
        "hi52": hi52, "lo52": lo52,
        "pos52": float((last_close - lo52) / rng52 * 100),
        "pct_from_high": float((last_close / hi52 - 1) * 100),
        "recent_range": recent_range,
        "heat_ratio": float(recent_range / b["avg_range"]) if b["avg_range"] else None,
        "dow": [(names[i], float(dow_ret.get(i, 0.0)), float(dow_rng.get(i, 0.0))) for i in range(5)],
    })
    return b


@st.cache_data(ttl=21600, show_spinner=False)
def cached_microstructure(ticker: str):
    """Advanced intraday profile from 15-minute bars over ~1 year (Alpaca IEX, paginated;
    falls back to Yahoo's trailing ~60 days). 26 buckets/session → fine-grained volatility
    curve, liquidity profile, best-time-to-enter, opening-range break and an intraday
    momentum-vs-mean-reversion read. Plain floats/lists (cache-friendly) or None."""
    import numpy as np

    df = src = window = None
    if ALPACA_KEY and ALPACA_SECRET:                       # full year of real 15-min IEX bars
        try:
            df = alpaca_data.fetch_bars_history(ticker, "15m", ALPACA_KEY, ALPACA_SECRET,
                                                days=365, feed="iex")
            if df is not None and len(df) >= 500:
                src, window = "Alpaca IEX 15-min", "~1 year"
            else:
                df = None
        except Exception:
            df = None
    if df is None:                                         # fallback: Yahoo's last ~60 days
        try:
            import yfinance as yf
            y = yf.download(ticker, period="60d", interval="15m", auto_adjust=True, progress=False)
            if isinstance(y.columns, pd.MultiIndex):
                y.columns = y.columns.get_level_values(0)
            y = y.dropna()
            if len(y):
                y.index = (y.index.tz_localize("America/New_York") if y.index.tz is None
                           else y.index.tz_convert("America/New_York"))
                df = y.between_time("09:30", "15:59")[["Open", "High", "Low", "Close", "Volume"]]
                src, window = "Yahoo 15-min", "~60 days"
        except Exception:
            df = None
    if df is None or len(df) < 200:
        return None

    df = df.between_time("09:30", "15:45").copy()          # 26 buckets: 09:30 … 15:45
    df["tod"] = df.index.strftime("%H:%M")
    df["date"] = df.index.date
    ORDER = [f"{9 + (30 + 15 * i) // 60:02d}:{(30 + 15 * i) % 60:02d}" for i in range(26)]
    seen = set(df["tod"])
    present = [t for t in ORDER if t in seen]

    bar = df["Close"] / df["Open"] - 1                      # move within each 15-min bar
    vol_by = bar.groupby(df["tod"]).std() * 100
    vol_curve = [(t, float(vol_by[t])) for t in present if t in vol_by.index and np.isfinite(vol_by[t])]

    dvol = df.groupby("date")["Volume"].transform("sum")
    vshare = (df["Volume"] / dvol.where(dvol > 0)).groupby(df["tod"]).mean() * 100
    vol_profile = [(t, float(vshare[t])) for t in present if t in vshare.index and np.isfinite(vshare[t])]

    gc = df.groupby("date")["Close"]
    span = gc.transform("max") - gc.transform("min")
    pos = ((df["Close"] - gc.transform("min")) / span.where(span > 0)).dropna()
    avg_pos = pos.groupby(df["tod"]).mean().reindex(present).dropna()
    path = [(t, float(avg_pos[t] * 100)) for t in avg_pos.index]
    low_freq = df.loc[gc.idxmin(), "tod"].value_counts(normalize=True)
    high_freq = df.loc[gc.idxmax(), "tod"].value_counts(normalize=True)
    entry_tod = avg_pos.idxmin() if len(avg_pos) else None
    exit_tod = avg_pos.idxmax() if len(avg_pos) else None

    open_vol = float(vol_by.get("09:30", np.nan))
    last_vol = float(vol_by.get("15:45", np.nan))
    mid_vol = float(bar[~df["tod"].isin(["09:30", "09:45", "15:30", "15:45"])].std() * 100)
    o1530 = df[df["tod"] == "15:30"].set_index("date")["Open"]
    c1545 = df[df["tod"] == "15:45"].set_index("date")["Close"]
    l30 = (c1545 / o1530 - 1).dropna()                      # the real last-30-min (3:30→4:00) move

    # opening-range break: first 30 min (9:30–10:00) high/low, broken later in the day?
    or_up = or_dn = follow = n_or = 0
    for _, g in df.groupby("date"):
        opn = g[g["tod"].isin(["09:30", "09:45"])]
        rest = g[~g["tod"].isin(["09:30", "09:45"])]
        if len(opn) == 0 or len(rest) == 0:
            continue
        n_or += 1
        orh, orl = float(opn["High"].max()), float(opn["Low"].min())
        bu, bd = bool((rest["High"] > orh).any()), bool((rest["Low"] < orl).any())
        or_up += bu
        or_dn += bd
        if bu and float(g["Close"].iloc[-1]) > orh:
            follow += 1

    # persistence: lag-1 autocorrelation of within-day 15-min returns (drop overnight-spanning bar)
    r = bar.copy()
    r[df.groupby("date").cumcount() == 0] = np.nan
    rr = r.dropna()
    persist = float(rr.autocorr(lag=1)) if len(rr) > 100 else None

    return {
        "source": src, "window": window, "n_days": int(df["date"].nunique()),
        "vol_curve": vol_curve, "vol_profile": vol_profile, "path": path,
        "entry_tod": entry_tod, "exit_tod": exit_tod,
        "entry_low_freq": float(low_freq.get(entry_tod, 0.0) * 100) if entry_tod else None,
        "exit_high_freq": float(high_freq.get(exit_tod, 0.0) * 100) if exit_tod else None,
        "open_vol": open_vol if np.isfinite(open_vol) else None,
        "mid_vol": mid_vol if np.isfinite(mid_vol) else None,
        "last_vol": last_vol if np.isfinite(last_vol) else None,
        "open_ratio": float(open_vol / mid_vol) if (np.isfinite(open_vol) and mid_vol) else None,
        "last30_big_pct": float((l30.abs() > 0.01).mean() * 100) if len(l30) else None,
        "last30_min": float(l30.min() * 100) if len(l30) else None,
        "last30_max": float(l30.max() * 100) if len(l30) else None,
        "or_up_pct": float(or_up / n_or * 100) if n_or else None,
        "or_dn_pct": float(or_dn / n_or * 100) if n_or else None,
        "or_follow_pct": float(follow / or_up * 100) if or_up else None,
        "persist": persist,
    }
