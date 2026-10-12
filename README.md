# Stock Signal Advisor

A Streamlit app that gives a BUY, SELL or HOLD verdict for a stock and explains the reasons behind it. It has an intraday view for day trading and a long-term view based on daily prices, uses real-time market data where it's available, and can backtest its own rules.

**Not financial advice.** The verdicts come from fixed rules. They're a second opinion, not a prediction.

## Features

- **Intraday** (1 to 60 minute bars). VWAP, EMA 9/21, RSI and MACD add up to a score and one of six verdicts: Strong BUY, BUY, HOLD, WAIT, SELL or Strong SELL. The tab also shows ATR-based stop and target levels, position sizing from your account size and risk per trade, a daily loss limit, a log of verdict changes, and a plain-English summary of the session.
- **Long-term** (daily bars). The verdict follows the 200-day trend: stay in above it, step aside below it. RSI, MACD and Bollinger Bands add context.
- **Backtesting.** Replays history bar by bar through the same code the live views use, so the test matches the real rules.
- **Watchlist.** Scans several tickers at once and sorts them by signal.
- **Know your ticker.** A ticker's risk profile from 3 years of daily data and 15-minute bars (about a year with an Alpaca key, about 60 days without): how much of the move happens overnight versus during the day, volatility by time of day, and opening-range breaks.
- **Live prices.** Picks the best free source for the current session: Finnhub during regular hours, Yahoo before and after the market, and Alpaca's IEX feed for real-time intraday bars.

## Running it

Needs Python 3.11 or newer.

```bash
git clone https://github.com/iamrs77/stock-signal-advisor.git
cd stock-signal-advisor
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens at http://localhost:8501. On Windows, after the setup above, you can also double-click `run.bat`.

### API keys (optional)

Without keys the app uses Yahoo Finance, which is delayed by about 15 minutes during regular hours. For real-time data, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in:

| Key                                    | Used for                                   | Where to get it                                           |
| -------------------------------------- | ------------------------------------------ | --------------------------------------------------------- |
| `FINNHUB_API_KEY`                      | Real-time US prices during regular hours   | [finnhub.io](https://finnhub.io/register) (free)          |
| `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`  | Real-time intraday bars                    | [alpaca.markets](https://alpaca.markets) (free paper account) |

`secrets.toml` is ignored by git, so your keys stay on your machine.

### Background logger

`watch.py` keeps recording verdict changes even when the app is closed. The changes show up in the app's verdict history.

```bash
python watch.py SOXL              # SOXL on 5-minute bars
python watch.py SOXL TQQQ --tf 3m # two tickers on 3-minute bars
```

On Windows, `watch.bat` does the same.

## How the verdicts work

Each indicator adds or subtracts points, and the total decides the verdict.

| Intraday score            | Verdict     |
| ------------------------- | ----------- |
| +5 or more                | Strong BUY  |
| +2 or more                | BUY         |
| Between -2 and +2         | HOLD        |
| -2 or less                | SELL        |
| -5 or less                | Strong SELL |
| Choppy or conflicting     | WAIT        |

The app is long-only: SELL means exit a position or don't buy, never short. All indicators are calculated directly with pandas, with no third-party technical-analysis library.

The intraday backtest buys on a BUY verdict and exits on a 1.5x ATR stop, a SELL verdict or the end of the day, whichever comes first. The long-term backtest holds while the price is above the 200-day average, over 5 years of daily data.

## Project structure

The analysis modules have no UI code, so the same logic runs in the app, the backtests and the background logger.

| File             | What it does                                                   |
| ---------------- | -------------------------------------------------------------- |
| `app.py`         | Page setup and the five tabs                                   |
| `views/`         | One module per tab, plus shared display helpers, cached data loaders, theme and API keys |
| `signals.py`     | Daily data, indicators and the long-term verdict               |
| `intraday.py`    | Intraday data, indicators and verdicts                         |
| `backtest.py`    | Backtests for the intraday and long-term rules                 |
| `risk.py`        | Position sizing and the daily loss limit                       |
| `live.py`        | Chooses the live price source for the current market session   |
| `alpaca_data.py` | Real-time intraday bars from Alpaca                            |
| `narrator.py`    | Plain-English session summary, outlook and live commentary     |
| `history.py`     | Log of verdict changes                                         |
| `watch.py`       | Background logger that runs without Streamlit                  |

## Limitations

- Backtests don't include fees or slippage and assume every order fills at the bar's close.
- Alpaca's free feed only includes IEX volume, so VWAP is close to, but not exactly, the full-market value.
- Yahoo only keeps a few weeks of history for the shortest intervals.
- Signals describe the past and present. They can't predict the future.
