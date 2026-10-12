"""
Plain-English commentary on the intraday session.

Three pure functions (no Streamlit, so they can be tested and reused for alerts or a CLI):
  - day_summary(df): recap of today (what moved, when, and where it stands).
  - day_outlook(df): a rules-based setup into tomorrow (not a prediction) plus key levels.
  - live_read(df, price, headline): a few sentences on what's happening right now.

Every number comes from the bars and indicators the app already calculates. The index is
tz-aware America/New_York, so session buckets use real market time.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _today(df: pd.DataFrame) -> pd.DataFrame | None:
    if df is None or len(df) == 0:
        return None
    last_day = df.index[-1].normalize()
    return df[df.index.normalize() == last_day]


def _fmt_t(ts) -> str:
    try:
        s = ts.strftime("%I:%M %p")
        return s[1:] if s.startswith("0") else s
    except Exception:
        return ""


_SESSIONS = [
    ("Open", "09:30", "11:00"),
    ("Midday", "11:00", "14:00"),
    ("Power hour", "14:00", "16:00"),
]


def _sessions(t: pd.DataFrame) -> list[dict]:
    out = []
    for name, a, b in _SESSIONS:
        try:
            seg = t.between_time(a, b, inclusive="left")
        except Exception:
            continue
        if len(seg) < 2:
            continue
        o = float(seg["Open"].iloc[0])
        c = float(seg["Close"].iloc[-1])
        mv = (c - o) / o * 100 if o else 0.0
        out.append({
            "name": name,
            "move_pct": mv,
            "word": "rallied" if mv > 0.25 else "sold off" if mv < -0.25 else "chopped",
        })
    return out


def day_summary(df: pd.DataFrame) -> dict | None:
    t = _today(df)
    if t is None or len(t) < 2:
        return None
    op = float(t["Open"].iloc[0])
    cur = float(t["Close"].iloc[-1])
    hi = float(t["High"].max())
    lo = float(t["Low"].min())
    hi_t = _fmt_t(t["High"].idxmax())
    lo_t = _fmt_t(t["Low"].idxmin())
    chg = (cur - op) / op * 100 if op else 0.0
    rng = (hi - lo) / op * 100 if op else 0.0
    pos = (cur - lo) / (hi - lo) if hi > lo else 0.5

    above_vwap = None
    if "VWAP" in t:
        v = t.dropna(subset=["VWAP"])
        if len(v):
            above_vwap = float((v["Close"] > v["VWAP"]).mean() * 100)

    last = t.index[-1]
    return {
        "date": last.strftime("%a, %b ") + str(last.day),
        "open": op, "current": cur, "high": hi, "low": lo,
        "high_time": hi_t, "low_time": lo_t,
        "change_pct": chg, "range_pct": rng, "pos_in_range": pos,
        "above_vwap_pct": above_vwap,
        "sessions": _sessions(t),
        "n_bars": len(t),
    }


def day_outlook(df: pd.DataFrame) -> dict | None:
    t = _today(df)
    if t is None or len(t) < 5:
        return None
    last = t.iloc[-1]
    cur = float(last["Close"])
    hi = float(t["High"].max())
    lo = float(t["Low"].min())
    pos = (cur - lo) / (hi - lo) if hi > lo else 0.5
    vwap = float(last["VWAP"]) if not np.isnan(last["VWAP"]) else None
    e9, e21 = float(last["EMA9"]), float(last["EMA21"])
    m_last = float(t["MACD"].iloc[-1])
    m_prev = float(t["MACD"].iloc[-2])

    score, reasons = 0, []
    if pos > 0.66:
        score += 1; reasons.append("closed near the day's highs")
    elif pos < 0.33:
        score -= 1; reasons.append("closed near the day's lows")
    else:
        reasons.append("closed mid-range")
    if vwap is not None:
        if cur > vwap:
            score += 1; reasons.append("finished above VWAP")
        else:
            score -= 1; reasons.append("finished below VWAP")
    if e9 > e21:
        score += 1; reasons.append("9-EMA above 21-EMA")
    else:
        score -= 1; reasons.append("9-EMA below 21-EMA")
    if m_last > m_prev:
        score += 1; reasons.append("MACD ticking up into the close")
    else:
        score -= 1; reasons.append("MACD ticking down into the close")

    bias = ("leaning bullish" if score >= 2
            else "leaning bearish" if score <= -2
            else "mixed — no clear edge")
    return {
        "bias": bias, "score": score, "reasons": reasons,
        "levels": {"Prior-day high": hi, "Prior-day low": lo,
                   "Close": cur, "VWAP": vwap},
    }


def live_read(df: pd.DataFrame, price: float | None = None, headline: str = "",
              htf_trend: str | None = None, minutes_to_close: int | None = None) -> list[tuple[str, str]]:
    """Detailed, plain-English read of the tape right now, as (label, text) pairs.
    Everything is quantified (distances, RSI direction, MACD histogram, ATR) so it actually
    informs a decision rather than just naming the indicator state."""
    t = _today(df)
    if t is None or len(t) < 3:
        t = df.tail(12) if df is not None else None
    if t is None or len(t) == 0:
        return []
    last = t.iloc[-1]
    px = float(price) if price is not None else float(last["Close"])

    op = float(t["Open"].iloc[0])
    hi = float(t["High"].max())
    lo = float(t["Low"].min())
    chg = (px - op) / op * 100 if op else 0.0
    rel = (px - lo) / (hi - lo) if hi > lo else 0.5
    where = "near the highs" if rel > 0.7 else "near the lows" if rel < 0.3 else "mid-range"

    out: list[tuple[str, str]] = []
    out.append(("Price", f"${px:,.2f}, {chg:+.2f}% today — {where} of the "
                         f"${lo:,.2f}–${hi:,.2f} day range."))

    vwap = float(last["VWAP"]) if not np.isnan(last["VWAP"]) else None
    if vwap is not None:
        d = (px - vwap) / vwap * 100
        side = "above" if px >= vwap else "below"
        who = "buyers" if px >= vwap else "sellers"
        out.append(("VWAP", f"{abs(d):.2f}% {side} VWAP (${vwap:,.2f}) — {who} in control; "
                            "that line is the intraday battle line."))

    e9, e21 = float(last["EMA9"]), float(last["EMA21"])
    if e9 >= e21:
        struct = "price holding above both" if (px >= e9 and px >= e21) else "but price has slipped under the 9-EMA"
        out.append(("Trend", f"Short-term UP — 9-EMA ${e9:,.2f} above 21-EMA ${e21:,.2f}, {struct}."))
    else:
        struct = "price below both" if (px <= e9 and px <= e21) else "though price is poking above the 9-EMA"
        out.append(("Trend", f"Short-term DOWN — 9-EMA ${e9:,.2f} below 21-EMA ${e21:,.2f}, {struct}."))

    rsi = float(last["RSI"]) if not np.isnan(last["RSI"]) else None
    if rsi is not None:
        rsi_ref = float(t["RSI"].iloc[-4]) if (len(t) >= 4 and not np.isnan(t["RSI"].iloc[-4])) else rsi
        rsi_dir = "rising" if rsi > rsi_ref + 0.5 else "falling" if rsi < rsi_ref - 0.5 else "flat"
        rsi_word = "overbought" if rsi > 70 else "oversold" if rsi < 30 else "neutral"
        m, sig = float(last["MACD"]), float(last["MACD_SIGNAL"])
        h_last = float(t["MACD_HIST"].iloc[-1])
        h_prev = float(t["MACD_HIST"].iloc[-2]) if len(t) >= 2 else h_last
        bias = "above" if m >= sig else "below"
        if m >= sig:
            mom = "momentum building" if h_last >= h_prev else "but momentum is fading"
        else:
            mom = "momentum building to the downside" if h_last <= h_prev else "but downside momentum is fading"
        out.append(("Momentum", f"RSI {rsi:.0f} ({rsi_word}) and {rsi_dir}; MACD {bias} its signal, "
                                f"histogram {'expanding' if abs(h_last) > abs(h_prev) else 'contracting'} — {mom}."))

    atr = float(last["ATR"]) if ("ATR" in t and not np.isnan(last["ATR"])) else None
    if atr is not None:
        bar_rng = float(last["High"] - last["Low"])
        pace = "fast" if bar_rng > 1.3 * atr else "quiet" if bar_rng < 0.6 * atr else "normal"
        out.append(("Volatility", f"Typical bar swings ≈ ${atr:,.2f} ({atr / px * 100:.1f}% of price); "
                                  f"the last bar moved ${bar_rng:,.2f} — {pace} pace."))

    if htf_trend:
        backs = "backs longs (intraday dips are buy-the-dip candidates)" if htf_trend == "up" \
            else "is a headwind for longs — be selective and quick" if htf_trend == "down" \
            else "is flat"
        out.append(("Bigger picture", f"Daily trend is {htf_trend.upper()} — it {backs}."))

    # Concrete trigger levels.
    res = f"${hi:,.2f} (day high)" if px < hi else "no resistance overhead (at the day's highs)"
    if vwap is not None and px >= vwap:
        sup = f"${vwap:,.2f} (VWAP)"
        flip = f"losing ${vwap:,.2f} (VWAP) would turn it cautious"
    else:
        sup = f"${lo:,.2f} (day low)"
        flip = f"a break under ${lo:,.2f} (day low) opens more downside"
    out.append(("Levels", f"Resistance {res}; support {sup}. A push above ${hi:,.2f} extends the move; {flip}."))

    if minutes_to_close is not None and minutes_to_close >= 0:
        phase = ("opening hour — expect wide swings" if minutes_to_close > 330
                 else "power hour — moves often extend into the close" if minutes_to_close <= 90
                 else "midday — often the quietest, choppiest stretch" if minutes_to_close > 120
                 else "late session")
        out.append(("Clock", f"~{minutes_to_close} min to the close — {phase}."))

    if headline:
        out.append(("Net read", headline))
    return out


def live_metrics(df: pd.DataFrame, price: float | None = None, htf_trend: str | None = None,
                 minutes_to_close: int | None = None) -> dict | None:
    """Raw numbers behind the live read, used by the visual dashboard (gauges and level ladder)."""
    t = _today(df)
    if t is None or len(t) < 3:
        t = df.tail(12) if df is not None else None
    if t is None or len(t) == 0:
        return None
    last = t.iloc[-1]
    px = float(price) if price is not None else float(last["Close"])
    op = float(t["Open"].iloc[0])
    hi = float(t["High"].max())
    lo = float(t["Low"].min())
    chg = (px - op) / op * 100 if op else 0.0
    pos = (px - lo) / (hi - lo) if hi > lo else 0.5

    vwap = float(last["VWAP"]) if not np.isnan(last["VWAP"]) else None
    vwap_dist = ((px - vwap) / vwap * 100) if vwap else None

    rsi = float(last["RSI"]) if not np.isnan(last["RSI"]) else None
    rsi_ref = float(t["RSI"].iloc[-4]) if (len(t) >= 4 and not np.isnan(t["RSI"].iloc[-4])) else rsi
    if rsi is None or rsi_ref is None:
        rsi_dir = "flat"
    else:
        rsi_dir = "rising" if rsi > rsi_ref + 0.5 else "falling" if rsi < rsi_ref - 0.5 else "flat"

    m_ = float(last["MACD"])
    sig = float(last["MACD_SIGNAL"])
    h_last = float(t["MACD_HIST"].iloc[-1])
    h_prev = float(t["MACD_HIST"].iloc[-2]) if len(t) >= 2 else h_last
    macd_above = m_ >= sig
    macd_mom = ("building" if h_last >= h_prev else "fading") if macd_above \
        else ("building" if h_last <= h_prev else "fading")

    atr = float(last["ATR"]) if ("ATR" in t and not np.isnan(last["ATR"])) else None
    atr_pct = (atr / px * 100) if (atr and px) else None
    bar_range = float(last["High"] - last["Low"])
    pace_ratio = (bar_range / atr) if atr else None
    pace = None
    if pace_ratio is not None:
        pace = "fast" if pace_ratio > 1.3 else "quiet" if pace_ratio < 0.6 else "normal"

    ema9, ema21 = float(last["EMA9"]), float(last["EMA21"])

    levels = [("Resistance", "res", hi), ("Now", "now", px), ("Support", "sup", lo)]
    if vwap is not None:
        levels.append(("VWAP", "vwap", vwap))
    levels.sort(key=lambda x: -x[2])

    phase = None
    if minutes_to_close is not None and minutes_to_close >= 0:
        phase = ("opening hour" if minutes_to_close > 330 else "power hour" if minutes_to_close <= 90
                 else "midday lull" if minutes_to_close > 120 else "late session")

    return {
        "price": px, "open": op, "high": hi, "low": lo, "chg_pct": chg, "pos_in_range": pos,
        "vwap": vwap, "vwap_dist_pct": vwap_dist,
        "rsi": rsi, "rsi_dir": rsi_dir, "macd_above": macd_above, "macd_mom": macd_mom,
        "atr": atr, "atr_pct": atr_pct, "bar_range": bar_range, "pace": pace, "pace_ratio": pace_ratio,
        "ema9": ema9, "ema21": ema21, "trend_up": ema9 >= ema21,
        "levels": levels, "htf_trend": htf_trend, "minutes_to_close": minutes_to_close, "phase": phase,
    }
