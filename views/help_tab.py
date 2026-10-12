"""The How it works tab."""

import streamlit as st


def render():
    """Render the How it works tab."""
    st.markdown(
        """
        ### 👋 New here? Start with this
        This app is a **second opinion**, not a robot that trades for you. It reads the price
        chart using a handful of well-known math tools (called **indicators**), and boils them
        down into one plain word — **BUY, SELL, or HOLD** — plus the reasons behind it.
        You stay in control: it tells you what the signals say; **you** decide.

        Think of it like a **weather forecast for a stock**. A forecast can't promise rain, but
        it tells you when to grab an umbrella. Same here: it tilts the odds and flags risk — it
        does **not** predict the future.

        ### What the verdict means
        The app scores several signals and adds them into one number:
        **positive → BUY, strongly negative → SELL, in-between → HOLD**. The **Intraday** tab
        also uses **WAIT** (too choppy — stand aside) and **Strong** versions when the signals
        really pile up. **"Agreement %"** is just how unanimous the signals are — *not* the
        chance of being right.

        ### ⚡ Intraday vs 📊 Long-term — which tab do I use?
        | | **📊 Long-term** | **⚡ Intraday** |
        |---|---|---|
        | Best for | Holding days/weeks/months | Day trading (minutes/hours) |
        | Chart bars | 1 per **day** | 1 every **1 / 3 / 5 / 15 min** |
        | The verdict follows | The **200-day trend regime** | VWAP, EMA 9/21, RSI, MACD + a chop gate |
        | Extras | — | Stop & profit targets, ~10s auto-refresh, verdict history |

        > 💡 **The golden rule:** the **Long-term** tab tells you *whether to be in a stock at all*;
        > the **Intraday** tab tells you *when to enter/exit on the day*. They answer different questions.

        ---
        ### 📖 Plain-English glossary — tap any term
        Each one explains **what it is**, **what it tells you**, and **how to read it in the app.**
        """
    )

    with st.expander("📈  MACD — is momentum speeding up or slowing down?"):
        st.markdown(
            """
            **What it is:** MACD compares a *fast* average of the price to a *slower* one. When the
            fast one pulls away from the slow one, the move is gaining steam. It draws two wiggly
            lines — the **MACD line** and a smoother **signal line** — plus **histogram bars** for
            the gap between them.

            **What it tells you (the accelerator pedal):** it measures *momentum*, not price.
            - **MACD line crosses ABOVE the signal line → momentum turning up** (bullish).
            - **MACD line crosses BELOW the signal line → momentum turning down** (bearish).
            - **Histogram bars growing** → the move is strengthening; **shrinking** → it's fading.

            **How to read it here:** it's the **bottom pane** of the intraday chart. In *"Why this
            verdict,"* a **fresh** cross (just happened) counts **double (weight 2)** because it's
            news; an **older** cross that's still in place counts **once (weight 1)** — confirmation,
            not news. (That's why you'll see MACD flip between weight 2 and 1.)

            **Watch out:** MACD *lags* — it confirms a move after it starts. On fast timeframes
            (1m/3m) and leveraged ETFs like SOXL it flips back and forth a lot (false signals).
            """
        )

    with st.expander("🌡️  RSI — is the stock overbought or oversold?"):
        st.markdown(
            """
            **What it is:** a single number from **0 to 100** measuring how hard and fast price has
            moved recently.

            **What it tells you (the speedometer):**
            - **Above 70 = "overbought"** — it's run up a lot and may need to cool off.
            - **Below 30 = "oversold"** — it's dropped a lot and may be due for a bounce.
            - **30–70 = normal**, no extreme.

            **How to read it here:** the **middle pane** of the chart, with dashed lines at 30 and 70.

            **Watch out:** in a *strong* trend RSI can sit above 70 (or below 30) for a long time and
            keep going. Overbought ≠ "sell now" — it's a caution flag, not a stop sign.
            """
        )

    with st.expander("➿  EMA 9 / EMA 21 — the trend lines that hug the price (intraday)"):
        st.markdown(
            """
            **What it is:** an **EMA (Exponential Moving Average)** is a running average of recent
            prices that leans on the *most recent* prices, so it reacts quickly. The intraday chart
            draws a **fast EMA 9** and a **slower EMA 21**.

            **What it tells you (the smoothed direction):**
            - **Price above both EMAs** → short-term uptrend (buyers in control).
            - **EMA 9 crossing above EMA 21** → momentum turning up; **below** → turning down.

            **How to read it here:** the two lines drawn over the candles. The verdict also checks
            **"Price vs EMA 9"** as one of its signals.
            """
        )

    with st.expander("📊  50-day / 200-day average & the 200-day trend regime (long-term)"):
        st.markdown(
            """
            **What it is:** a **moving average (SMA)** is the plain average of the last N daily closes.
            The **200-day average** is the single most-watched long-term trend line on Wall Street;
            the **50-day** is a medium-term one.

            **What it tells you (the tide):**
            - **50-day above 200-day = "golden cross"** → healthy long-term uptrend.
            - **50-day below 200-day = "death cross"** → downtrend.

            **The 200-day trend regime (this is how the Long-term tab decides):**
            - **Price ABOVE its 200-day average → BUY / stay invested** (the long-term trend is up).
            - **Price BELOW its 200-day average → SELL / step aside to cash** (trend is down).

            Why this simple rule? It keeps you riding big uptrends and **out of big crashes**. In our
            backtests it captured most of the trend (e.g. SOXL, QQQ near buy-&-hold) at **roughly half
            the drawdown**. The other indicators (RSI, MACD, Bollinger) ride along as context but don't
            override the trend.
            """
        )

    with st.expander("⚖️  VWAP — the day's \"fair price\" (intraday)"):
        st.markdown(
            """
            **What it is:** **Volume-Weighted Average Price** — the average price everyone paid so far
            *today*, weighted by how much traded at each price. It **resets every morning**.

            **What it tells you (the day's center of gravity):** big institutions use VWAP as their
            benchmark. **Price above VWAP → buyers in control today** (favours longs); **below VWAP →
            sellers in control.** Price snapping back toward VWAP is common.

            **How to read it here:** the line drawn over the intraday candles; it's one of the heavier
            signals in the intraday verdict.
            """
        )

    with st.expander("🎈  Bollinger Bands — how stretched is the price?"):
        st.markdown(
            """
            **What it is:** a middle line (a 20-period average) with an **upper and lower band** drawn
            a set distance away. The bands **widen when the stock is volatile** and **narrow when calm**.

            **What it tells you (the rubber band):**
            - **Price riding the upper band** → stretched high, may snap back / cool off.
            - **Price riding the lower band** → stretched low, may bounce.

            **Watch out:** "touching the band" isn't an automatic reversal — in strong moves price can
            walk along a band for a while.
            """
        )

    with st.expander("📏  ATR — how much does it normally move? (sets your stop & targets)"):
        st.markdown(
            """
            **What it is:** **Average True Range** — the typical size of one price bar's move. It's a
            **volatility** measure: a bigger ATR means bigger swings.

            **What it's used for here:** your safety levels are built from it, so they fit the stock's
            real volatility instead of a random guess:
            - **Stop** = about **1.5 × ATR below your entry** — far enough that normal wiggles don't
              stop you out, close enough to cap the loss.
            - **Targets** at **1R and 2R** (see "R" below).
            """
        )

    with st.expander("🎯  Stop, targets, and \"R\" — the risk vocabulary"):
        st.markdown(
            """
            - **Stop (stop-loss):** the price where you bail out to cap a loss. Decide it *before* you
              buy, not in the heat of the moment.
            - **R = your risk per trade** = entry price − stop price. It's your "1 unit of risk."
            - **1R target** = a gain as big as what you risked (a 1-to-1 reward). **2R target** = twice
              your risk. Thinking in R keeps **reward-vs-risk** honest: risking $1 to make $2 is a 2R trade.
            - **Position size:** the app can suggest how many shares so that *if your stop is hit*, you
              only lose the % of your account you chose in **🛡️ Risk** (e.g. 1%).
            """
        )

    with st.expander("🧪  Backtest words — profit factor, expectancy, drawdown, agreement %"):
        st.markdown(
            """
            - **Profit factor** = total $ won ÷ total $ lost. **Above 1.0 = profitable**, 1.5+ is solid.
            - **Expectancy (in R)** = the average result per trade in units of risk. **Positive = an
              edge** over many trades.
            - **Win rate** = % of trades that made money. (A low win rate can still be profitable if
              the wins are much bigger than the losses.)
            - **Max drawdown** = the worst peak-to-valley drop of the account — *how much pain* you'd
              have had to sit through. Smaller is calmer.
            - **Buy-&-hold** = what you'd have made just buying and never selling — the bar to beat.
            - **Agreement %** = how unanimously the live signals point one way. It's a *consensus*
              measure, **not** the probability of being right.
            """
        )

    with st.expander("📜  How to read the Verdict history (grading the calls)"):
        st.markdown(
            """
            At the bottom of the **Intraday** tab, every time the verdict flips it's logged with the
            **time, the price, and the high & low the price reached afterwards** (until the next flip).
            Use it to see whether a call actually worked:

            - **BUY** with a big green **▲ high** and a small red **▼ low** → it worked, and your stop
              likely wasn't threatened.
            - **BUY** where the **▼ low** went deeper than the **▲ high** → the entry was early/wrong
              (or a stop would've been hit first).
            - **SELL / WAIT** followed by a falling **▼ low** → it correctly kept you out of a drop.
            - The newest row says **"· so far"** because its range is still updating live.

            Tip: leave **`watch.bat`** running during the day so the ranges are captured even when the
            app/browser is closed.
            """
        )

    st.markdown(
        """
        ---
        ### ⚠️ Honest limitations — please read
        - These are **lagging, rule-based** signals, **not predictions** — they describe what *has*
          happened, not what *will*. No indicator works in every market.
        - Use this as **one input** alongside your own judgement, never the only reason to trade.
        - **Prices can lag** (Yahoo up to ~15 min; the "latest bar" time is always shown), and exact
          values may differ a few cents from your broker — confirm in Wealthsimple before you click.
        - **Leveraged ETFs (SOXL/TQQQ)** move ~3× and decay over time, so keep intraday holds short
          and **never skip the stop**.

        > **Not financial advice.** For education and personal decision-support only.
        > You are responsible for your own trades.
        """
    )
