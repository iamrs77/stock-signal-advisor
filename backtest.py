"""
backtest.py — does the intraday BUY/SELL logic actually make money on SOXL?

It replays history bar-by-bar using the SAME engine the live tab uses
(intraday.evaluate_intraday), so the test reflects the real rules — not a copy
that could drift. Long-only, one position at a time:

  • ENTER on a BUY verdict, at that bar's close.
  • EXIT on whichever comes first: a 1.5×ATR stop, a SELL verdict, or end of day
    (no overnight holds — this is an intraday strategy).

Honest caveats (shown in the UI too): no fees/slippage, assumes clean fills, runs
on Yahoo bars (which can lag), and PAST PERFORMANCE IS NOT FUTURE PERFORMANCE.
It's a sanity check on the rules, not a promise.
"""

from __future__ import annotations

import pandas as pd

import intraday
import signals

# Yahoo history limits per interval (how far back intraday bars go).
_BT_PERIOD = {"1m": "7d", "2m": "60d", "3m": "7d", "5m": "60d", "15m": "60d", "30m": "60d", "60m": "730d"}


def run_backtest(ticker: str, interval: str = "5m", stop_atr: float = 1.5, use_htf: bool = True) -> dict:
    df = intraday.fetch_intraday(ticker, interval, period=_BT_PERIOD.get(interval, "60d"))
    n = len(df)
    if n < 50:
        raise ValueError("Not enough history to backtest this timeframe.")

    days = df.index.normalize()
    dates = df.index.date
    htf = intraday.daily_trend_series(ticker) if use_htf else {}
    close = df["Close"].to_numpy()
    low = df["Low"].to_numpy()
    atr = df["ATR"].to_numpy()

    # Verdict at each bar, from the real engine — fed a tiny trailing window so it's O(n)
    # (evaluate only looks at the last row + last 4 bars, so a 5-row window is identical).
    verdicts: list[str | None] = [None] * n
    for i in range(n):
        if pd.isna(atr[i]):
            continue
        htf_t = htf.get(dates[i]) if use_htf else None
        verdicts[i] = intraday.evaluate_intraday(
            df.iloc[max(0, i - 4):i + 1], ticker, interval, htf_trend=htf_t).verdict

    trades: list[dict] = []
    in_pos = False
    entry = stop = 0.0
    entry_i = 0
    for i in range(n):
        eod = (i == n - 1) or (days[i + 1] != days[i])
        if in_pos:
            exit_price = reason = None
            if low[i] <= stop:                       # stop hit (assume worst case within the bar)
                exit_price, reason = stop, "stop"
            elif verdicts[i] == "SELL":              # signal flipped bearish
                exit_price, reason = float(close[i]), "signal"
            elif eod:                                # never hold overnight
                exit_price, reason = float(close[i]), "end of day"
            if exit_price is not None:
                risk_ps = entry - stop
                trades.append({
                    "entry": entry, "exit": exit_price,
                    "ret": (exit_price - entry) / entry,
                    "R": (exit_price - entry) / risk_ps if risk_ps > 0 else 0.0,
                    "reason": reason, "bars": i - entry_i,
                })
                in_pos = False
        if (not in_pos) and (not eod) and (not pd.isna(atr[i])) and verdicts[i] == "BUY":
            entry, stop, entry_i, in_pos = float(close[i]), float(close[i] - stop_atr * atr[i]), i, True

    return _stats(trades, df, interval)


def run_backtest_lt(ticker: str, period: str = "5y") -> dict:
    """Backtest the LONG-TERM (daily) engine in signals.py — the same one the Long-term
    tab and the Watchlist use. It's a trend-regime strategy: go long when price is above
    its 200-day average (a BUY verdict), step aside when it drops below (a SELL verdict).
    Long-only, held across days; the 200-day line itself is the exit. Reuses the real
    `signals.evaluate` on a trailing window so it tests the actual rules. 'Risk' (for the
    R multiple) is the distance from the entry price down to the 200-day at entry — i.e.
    how far price would have to fall to trigger the trend exit."""
    df = signals.get_data(ticker, period=period)
    n = len(df)
    if n < 250:
        raise ValueError("Not enough daily history to backtest (need ~1 year+).")

    close = df["Close"].to_numpy()
    sma200 = df["SMA200"].to_numpy()

    verdicts: list[str | None] = [None] * n
    for i in range(n):
        if pd.isna(sma200[i]):
            continue
        verdicts[i] = signals.evaluate(df.iloc[max(0, i - 4):i + 1], ticker).verdict

    trades: list[dict] = []
    in_pos = False
    entry = entry_sma = 0.0
    entry_i = 0
    for i in range(n):
        if in_pos and verdicts[i] == "SELL":            # price broke below the 200-day → exit
            risk_ps = entry - entry_sma
            trades.append({
                "entry": entry, "exit": float(close[i]),
                "ret": (close[i] - entry) / entry,
                "R": (close[i] - entry) / risk_ps if risk_ps > 0 else 0.0,
                "reason": "trend exit", "bars": i - entry_i,
            })
            in_pos = False
        if (not in_pos) and (not pd.isna(sma200[i])) and verdicts[i] == "BUY":
            entry, entry_sma, entry_i, in_pos = float(close[i]), float(sma200[i]), i, True

    # Still holding at the end? Mark it to the last close so the total return reflects the
    # position you'd actually be in right now (otherwise a big open winner is ignored).
    if in_pos:
        last = float(close[-1])
        risk_ps = entry - entry_sma
        trades.append({
            "entry": entry, "exit": last,
            "ret": (last - entry) / entry,
            "R": (last - entry) / risk_ps if risk_ps > 0 else 0.0,
            "reason": "open (marked to last close)", "bars": (n - 1) - entry_i,
        })

    return _stats(trades, df, "daily")


def _stats(trades: list[dict], df: pd.DataFrame, interval: str) -> dict:
    rets = [t["ret"] for t in trades]
    Rs = [t["R"] for t in trades]
    nt = len(trades)
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]

    equity, peak, mdd = 1.0, 1.0, 0.0
    curve = [1.0]
    for r in rets:
        equity *= (1 + r)
        curve.append(equity)
        peak = max(peak, equity)
        mdd = min(mdd, equity / peak - 1)

    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    close = df["Close"].to_numpy()
    dfmt = "%b %Y" if (df.index[-1] - df.index[0]).days > 200 else "%b %d"
    return {
        "interval": interval,
        "bars": len(df),
        "start": df.index[0].strftime(dfmt),
        "end": df.index[-1].strftime(dfmt),
        "trades": nt,
        "win_rate": (len(wins) / nt * 100) if nt else 0.0,
        "total_return": (equity - 1) * 100,
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win else 0.0),
        "expectancy_R": (sum(Rs) / nt) if nt else 0.0,
        "avg_win": (sum(wins) / len(wins) * 100) if wins else 0.0,
        "avg_loss": (sum(losses) / len(losses) * 100) if losses else 0.0,
        "max_drawdown": mdd * 100,
        "buy_hold": (close[-1] / close[0] - 1) * 100 if len(close) else 0.0,
        "curve": curve,
        "trade_list": trades,
    }
