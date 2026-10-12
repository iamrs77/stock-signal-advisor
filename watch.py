"""
watch.py — standalone 24/7 intraday verdict logger.

Runs OUTSIDE Streamlit, so it keeps logging verdict flips even when the app (or the
Intraday tab) is closed. Every POLL_SECONDS, for each watched ticker, it computes the
SAME live intraday verdict the app shows — real engine, real-time price during the
regular session, same data-staleness guard — and appends any CHANGE to
verdict_history.json. That's the same file the app's "Verdict history" panel reads, so
captures from this logger show up there automatically.

It only logs during the US REGULAR session (decided by Yahoo's market state, so holidays
and early closes are handled for free); outside the session it idles quietly.

Run it:
    .venv\\Scripts\\python.exe watch.py              # defaults: SOXL, 5m
    .venv\\Scripts\\python.exe watch.py SOXL TQQQ    # custom tickers
    .venv\\Scripts\\python.exe watch.py SOXL --tf 3m # custom timeframe
…or just double-click  watch.bat .  Leave it running (minimized is fine) during the day.
Stop it with Ctrl+C.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime

import pandas as pd

import history
import intraday
import live

POLL_SECONDS = 30          # how often to check while the market is open
IDLE_SECONDS = 300         # how often to re-check when the market is closed
DEFAULT_TICKERS = ["SOXL"]
DEFAULT_INTERVAL = "5m"


def load_keys() -> tuple[str, tuple[str, str]]:
    """Read API keys from .streamlit/secrets.toml without needing Streamlit running."""
    try:
        import tomllib
        with open(".streamlit/secrets.toml", "rb") as f:
            s = tomllib.load(f)
        return (s.get("FINNHUB_API_KEY", ""),
                (s.get("ALPACA_API_KEY", ""), s.get("ALPACA_SECRET_KEY", "")))
    except Exception:
        return "", ("", "")


def compute_verdict(ticker: str, interval: str, finnhub_key: str, alpaca: tuple[str, str]):
    """Compute the live verdict exactly like the app's intraday panel does.

    Returns (analysis, in_session). `in_session` is True only during the regular session.
    """
    q = live.get_live_quote(ticker, finnhub_key)
    in_session = bool(q) and q.state == "REGULAR"
    live_price = q.price if in_session else None

    df = intraday.fetch_intraday(ticker, interval, alpaca=(alpaca if any(alpaca) else None))
    a = intraday.evaluate_intraday(df, ticker, interval, live_price=live_price,
                                   htf_trend=intraday.daily_trend(ticker))

    # Same data-staleness guard as the app: never log a confident verdict on frozen data.
    try:
        if in_session:
            age_min = (pd.Timestamp.now(tz=a.df.index.tz) - a.df.index[-1]).total_seconds() / 60.0
            iv_min = int("".join(c for c in interval if c.isdigit()) or "5")
            if age_min > max(30, 3 * iv_min):
                a.verdict, a.strength = "WAIT", ""
    except Exception:
        pass

    return a, in_session


def main() -> None:
    # Parse args: positional tickers + optional "--tf 3m".
    args = sys.argv[1:]
    interval = DEFAULT_INTERVAL
    if "--tf" in args:
        i = args.index("--tf")
        if i + 1 < len(args):
            interval = args[i + 1]
        args = args[:i] + args[i + 2:]
    tickers = [t.upper() for t in args] or DEFAULT_TICKERS

    finnhub_key, alpaca = load_keys()
    bars_src = "Alpaca real-time" if any(alpaca) else "Yahoo (delayed ~15m)"
    print(f"[watch] logging {tickers} @ {interval} every {POLL_SECONDS}s during the US regular "
          f"session.\n[watch] bars via {bars_src}; writing changes to verdict_history.json. "
          f"Ctrl+C to stop.\n")

    while True:
        try:
            any_open = False
            for tk in tickers:
                try:
                    a, in_session = compute_verdict(tk, interval, finnhub_key, alpaca)
                    if not in_session:
                        continue                      # only log during the regular session
                    any_open = True
                    bar = a.df.iloc[-1]
                    changed = history.record_verdict(tk, interval, a.headline, a.price,
                                                     float(bar["High"]), float(bar["Low"]))
                    stamp = datetime.now().strftime("%H:%M:%S")
                    if changed:
                        print(f"[{stamp}] ▲ {tk} {interval}: {a.headline}  ${a.price:,.2f}  (logged)")
                    else:
                        print(f"[{stamp}]   {tk} {interval}: {a.headline}  ${a.price:,.2f}")
                except Exception as e:
                    print(f"[{datetime.now():%H:%M:%S}]   {tk}: {e}")
            time.sleep(POLL_SECONDS if any_open else IDLE_SECONDS)
        except KeyboardInterrupt:
            print("\n[watch] stopped.")
            break
        except Exception as e:
            print(f"[watch] loop error: {e}")
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
