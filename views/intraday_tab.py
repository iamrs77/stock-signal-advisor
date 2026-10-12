"""The Intraday tab: live verdict, trade plan, chart, session summary and verdict history."""

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import history
import intraday
import live
import narrator
import risk

from views.api_keys import ALPACA_KEY, ALPACA_SECRET, API_KEY, DEMO_MODE
from views.data import cached_backtest, cached_daily_trend, cached_intraday, cached_quote
from views.shared import clamp, dtip, live_badge, lw_chart, render_backtest, render_signals, section, verdict_card
from views.theme import C_BLUE, C_GOLD, C_PURPLE, LADDER_ICON


# How often the intraday verdict refreshes (seconds). Kept short on purpose, because
# intraday is time-sensitive. The heavier chart refreshes on a slower cycle (see below).
# Auto-refresh interval (seconds). Note: pass run_every to @st.fragment as a string ("10s");
# a bare int silently fails to auto-rerun in this Streamlit version (the string "30s" works).
INTRADAY_REFRESH = 10


# Description + live countdown for the intraday auto-refresh. The "__N__" nonce is
# swapped for a per-refresh counter so Streamlit re-renders (re-runs the JS) each cycle,
# which resets the countdown the instant the data actually refreshes.
INTRADAY_STATUS_HTML = """<!--r__N__-->
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600&display=swap');
html,body{margin:0;background:transparent;}
body{font-family:'Plus Jakarta Sans',sans-serif;color:#667085;font-size:15px;
     display:flex;align-items:center;justify-content:space-between;gap:12px;}
.cap{line-height:1.4;}
.cd{flex-shrink:0;display:inline-flex;align-items:center;gap:7px;background:#EFF3FA;
    border:1px solid #DCE4F2;border-radius:999px;padding:4px 12px;color:#2563EB;
    font-weight:600;font-size:13px;white-space:nowrap;}
.cd .dot{width:7px;height:7px;border-radius:50%;background:#2563EB;animation:p 1s ease-in-out infinite;}
@keyframes p{0%,100%{opacity:1}50%{opacity:.35}}
</style>
<span class="cap">Fast day-trading signals — VWAP, EMA 9/21, RSI &amp; MACD on intraday bars, plus ATR-based stops &amp; targets.</span>
<span class="cd"><span class="dot"></span><span id="t">Next refresh in __SECS__s</span></span>
<script>
var n=__SECS__,e=document.getElementById('t');
var iv=setInterval(function(){n--;if(n<=0){e.textContent='refreshing…';clearInterval(iv);}
else{e.textContent='Next Refresh in '+n+'s';}},1000);
</script>"""


VERDICT_KEY_HTML = """
<div class="vkey">
  <div class="vrow"><span class="badge b-sbuy">Strong BUY</span><span class="desc">All signals aligned bullish (score ≥ +5) — high-conviction long.</span></div>
  <div class="vrow"><span class="badge b-buy">BUY</span><span class="desc">Net bullish (score ≥ +2) — bias to the upside.</span></div>
  <div class="vrow"><span class="badge b-hold">HOLD</span><span class="desc">Mixed, no clear edge (score between −2 and +2) — no fresh entry.</span></div>
  <div class="vrow"><span class="badge b-wait">WAIT</span><span class="desc">Choppy or conflicting conditions — stand aside, no trade.</span></div>
  <div class="vrow"><span class="badge b-sell">SELL</span><span class="desc">Net bearish (score ≤ −2) — sell your long / don't buy. (You don't short.)</span></div>
  <div class="vrow"><span class="badge b-ssell">Strong SELL</span><span class="desc">All signals aligned bearish (score ≤ −5) — strong exit / stay-out signal.</span></div>
</div>
"""


def trade_store():
    """Where the daily trade log lives: this visitor's session on the public demo, else daily_risk.json."""
    return st.session_state if DEMO_MODE else None


def render_intraday_backtest(itk):
    """Rarely used validation tool, placed at the very bottom of the intraday tab."""
    with st.expander("🧪  Backtest these signals", expanded=st.session_state.get("bt_done", False)):
        st.caption("How would the BUY/SELL rules have performed on past data? The real trust check.")
        tcol, rcol = st.columns([2, 1], vertical_alignment="bottom")
        tcol.selectbox("Timeframe", ["5m", "15m", "3m", "1m"], key="bt_iv",
                       help="5m/15m cover ~60 days of history; 3m/1m only ~7 days (Yahoo's limit).")
        if rcol.button("▶  Run backtest", key="bt_run", width="stretch"):
            st.session_state["bt_done"] = True
        st.toggle("Trend filter — only buy with the daily uptrend", value=True, key="bt_htf",
                  help=(
                      "**What it is:** it only allows a long when the bigger-picture **daily** trend is up "
                      "(daily 20-day EMA above the 50-day EMA). If the daily trend is down, it blocks the "
                      "buy (turns BUY → HOLD) so you don't go long against the bigger tide.\n\n"
                      "**Why it's worth keeping on:** it's insurance. It costs a little in strong uptrends "
                      "(SOXL backtest: +57% → +40%) but protects you in downtrends — on SOXS, which fell ~89%, "
                      "it kept you **flat with 0% drawdown** instead of **−8.7% with a −37% drawdown.**\n\n"
                      "**How to read this toggle:** ON ≈ how you actually trade (the live verdict always uses "
                      "this filter). OFF shows the unfiltered strategy for comparison only — it does **not** "
                      "change your live trading.\n\n"
                      "**Trade-off in one line:** filter ON = fewer trades, smoother ride, safer in bad markets; "
                      "OFF = more trades and more upside in a raging bull, but exposed when the trend rolls over."
                  ))
        st.caption("ℹ️ Your live verdict always applies the trend filter — this toggle just lets you explore its effect.")
        if st.session_state.get("bt_done") and itk:
            try:
                with st.spinner("Backtesting… (a few seconds)"):
                    res = cached_backtest(itk, st.session_state["bt_iv"], st.session_state.get("bt_htf", True))
                render_backtest(res)
            except Exception as e:
                st.error(f"Backtest failed: {e}")


def intraday_chart(a):
    lw_chart(a.df, overlays=[
        ("VWAP", C_PURPLE, 2, "VWAP"),
        ("EMA9", C_BLUE, 2, "EMA 9"),
        ("EMA21", C_GOLD, 2, "EMA 21"),
    ], mode="datetime", height=660)
    st.caption("Price · RSI · MACD, synced. Overnight gaps collapse automatically; drag dividers to resize.")


def _vhist_color(v: str) -> str:
    if "SELL" in v:
        return "#DC2626"
    if "BUY" in v:
        return "#16A34A"
    if v == "WAIT":
        return "#64748B"
    return "#D97706"          # HOLD


def render_verdict_history(ticker: str):
    """Log of every intraday verdict flip for `ticker`, grouped by day (newest first), 60-day window."""
    section("📜 Verdict history")
    st.caption("Each time the live verdict flipped, with the **high & low the price reached "
               "afterwards** (until the next flip) so you can see if the call worked. "
               "Grouped by day, kept for 60 days.")
    rows = history.history(ticker, 60)
    if not rows:
        st.markdown('<div class="muted">— Nothing logged yet. As the verdict flips during the '
                    'session, each change is stamped here with its time, price, and the range '
                    'it reaches afterwards.</div>', unsafe_allow_html=True)
        return
    newest = rows[-1]                             # the currently-active verdict (still updating)
    groups: dict[str, list] = {}
    order: list[str] = []
    for r in reversed(rows):                      # newest first
        d = (r.get("ts") or "")[:10]
        if d not in groups:
            groups[d] = []
            order.append(d)
        groups[d].append(r)
    parts = ['<div class="vhist">']
    for d in order:
        try:
            ts = pd.Timestamp(d)
            label = ts.strftime("%a, %b ") + str(ts.day)
        except Exception:
            label = d
        parts.append(f'<div class="vh-day">{label}</div>')
        for r in groups[d]:
            v = r.get("verdict", "")
            t = (r.get("ts") or "")[11:16]
            px = r.get("price")
            pxs = f"${px:,.2f}" if isinstance(px, (int, float)) else ""
            hi, lo = r.get("hi"), r.get("lo")
            if isinstance(hi, (int, float)) and isinstance(lo, (int, float)) and isinstance(px, (int, float)) and px:
                live = ' <span class="vh-live">· so far</span>' if r is newest else ""
                after = (f'<div class="vh-after">after → '
                         f'<span class="vh-hi">▲ high {hi:,.2f} ({(hi - px) / px * 100:+.1f}%)</span>'
                         f' &nbsp; '
                         f'<span class="vh-lo">▼ low {lo:,.2f} ({(lo - px) / px * 100:+.1f}%)</span>'
                         f'{live}</div>')
            else:
                after = '<div class="vh-after vh-na">after → not tracked for this one</div>'
            parts.append(
                f'<div class="vh-item">'
                f'<div class="vh-row"><span class="vh-t">{t}</span>'
                f'<span class="vh-v" style="color:{_vhist_color(v)}">{v}</span>'
                f'<span class="vh-iv">{r.get("interval", "")}</span>'
                f'<span class="vh-px">entry {pxs}</span></div>'
                f'{after}</div>')
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


@st.fragment(run_every=f"{INTRADAY_REFRESH}s")
def intraday_panel(ticker: str, api_key: str | None):
    """The fast-refreshing half of the intraday view (verdict, signals and trade plan). It updates
    every INTRADAY_REFRESH seconds with fresh bars and the live price, so it tracks the market in
    near-real-time. The (heavier) chart + history live in intraday_chart_panel on a slower
    cycle, so speeding this up doesn't reload the chart every few seconds. The timeframe
    toolbar sits between them (in the page body) so changing it recomputes both at once."""
    st.session_state.setdefault("intraday_interval", "5m")
    interval = st.session_state["intraday_interval"]

    # Description + auto-refresh countdown (nonce forces a re-render each cycle → resets timer).
    tick = st.session_state.get("intraday_tick", 0) + 1
    st.session_state["intraday_tick"] = tick
    components.html(INTRADAY_STATUS_HTML.replace("__N__", str(tick)).replace("__SECS__", str(INTRADAY_REFRESH)), height=46)

    lq = cached_quote(ticker, api_key)
    # Use the live price in the verdict only during the regular session. Outside it (pre/post/closed),
    # an extended-hours price would be compared against indicators frozen at the regular close, which
    # is misleading. So we fall back to the last regular-session close and keep price and indicators consistent.
    in_session = bool(lq) and lq.state == "REGULAR"
    live_price = lq.price if in_session else None
    try:
        df = cached_intraday(ticker, interval)
        a = intraday.evaluate_intraday(df, ticker, interval, live_price=live_price,
                                       htf_trend=cached_daily_trend(ticker))
    except Exception as e:
        st.error(f"⚠️ Couldn't load intraday data for **{ticker.upper()}** ({e}). "
                 "Treat this as WAIT — don't trade on missing data.")
        return

    # ---- data-staleness guard: never show a confident verdict on stale/frozen data ----
    stale, stale_age = False, 0.0
    try:
        if in_session:                              # only expect fresh bars during the regular session
            stale_age = (pd.Timestamp.now(tz=a.df.index.tz) - a.df.index[-1]).total_seconds() / 60.0
            iv_min = int("".join(c for c in interval if c.isdigit()) or "5")
            if stale_age > max(30, 3 * iv_min):     # generous: allows normal feed lag, catches frozen data
                stale = True
                a.verdict, a.strength = "WAIT", ""
    except Exception:
        stale = False

    # Log the verdict + track the high/low it reaches afterwards (for the history panel below).
    try:
        _bar = a.df.iloc[-1]
        history.record_verdict(ticker, interval, a.headline, a.price,
                               float(_bar["High"]), float(_bar["Low"]))
    except Exception:
        pass

    if in_session:
        delta = (f"{lq.change:+.2f} ({lq.percent:+.2f}%)"
                 if (lq.change is not None and lq.percent is not None) else "")
        meta = f"{live_badge(lq)} · {lq.source} · {delta}"
    else:
        meta = "🕒 Outside regular hours — verdict is as of the last regular-session close"
    n = a.interval.replace("m", "")
    unit = "minute" if n == "1" else "minutes"
    tip = (f"Timeframe: each candle covers {n} {unit}. VWAP, EMA 9/21, RSI, MACD and the "
           "BUY/SELL/HOLD verdict are all computed on these bars. "
           "Switch it with the 1m/3m/5m/15m toolbar above the chart.")
    tag = (f'INTRADAY · {a.ticker} · <span class="tip">{a.interval}'
           f'<span class="info-i">?</span><span class="tip-text">{tip}</span></span>')
    agree_tip = ("How unanimous the signals are — the net directional score vs the weight of the "
                 "signals that took a side. 100% = the main signals all line up the same way. "
                 "It's a consensus measure, not the odds of being right.")
    verdict_card(tag, a.verdict, a.headline, a.price, a.score, a.confidence, meta, agreement_tip=agree_tip)
    st.markdown(
        f'<div class="muted">⏱ Latest bar: {a.last_bar_time} · bars via '
        + ("Alpaca real-time (IEX)" if (ALPACA_KEY and ALPACA_SECRET) else "Yahoo (delayed ~15m)")
        + " · "
        + ("real-time price used for VWAP/EMA checks" if a.using_live_price
           else "using last bar price") + "</div>",
        unsafe_allow_html=True,
    )
    if stale:
        st.error(f"⚠️ Data looks stale — the latest bar is {stale_age:.0f} min old during market hours "
                 "(the feed may be lagging or frozen). Showing **WAIT** — do not trade on this.")

    left, right = st.columns([3, 2], gap="large")
    with left:
        section("Why this verdict")
        render_signals(a.signals)
    with right, st.container(key="action_zone"):
        section("Your plan — long only")
        if not a.atr:
            st.caption("Not enough bars to compute levels yet.")
        else:
            st.metric("ATR — typical bar move", f"{a.atr:,.2f}",
                      delta=f"{a.atr_pct:.1f}% of price", delta_color="off",
                      help="How much the price usually moves in one candle on this timeframe. "
                           "A bigger number means bigger swings, so you need a wider stop.")

            # --- daily loss guardrail ---
            _mx = st.session_state.get("max_daily_loss")
            _realized = sum(risk.load_today(trade_store())["trades"])
            limit_hit = bool(_mx) and _mx > 0 and _realized <= -_mx
            if limit_hit:
                st.error(f"🛑 Daily loss limit hit ({_realized:+,.0f}). No new trades today — protect your capital.")

            # --- position inputs: revealed only when you own it, so the panel stays short ---
            own = st.toggle("📊 I own this — show P&L calculator", key="own_flag",
                            help="Turn on to enter your buy price & shares for live P&L.")
            if own:
                entry_in = st.number_input("Your buy price ($)", min_value=0.0, step=0.01, format="%.2f",
                                           value=None, placeholder="e.g. 245.00", key="entry_px")
                shares_in = st.number_input("Shares", min_value=0.0, step=1.0, format="%.2f",
                                            value=None, placeholder="e.g. 100", key="shares_qty")
                if st.button("⏎  Calculate P&L", key="calc_btn"):
                    st.session_state["pos_committed"] = {"entry": entry_in or 0.0, "shares": shares_in or 0.0}
            pos = st.session_state.get("pos_committed") if own else None

            entry = pos.get("entry") if pos else None
            shares = pos.get("shares", 0.0) if pos else 0.0
            holding = bool(own) and bool(entry) and entry > 0

            if stale:
                st.markdown('<div class="plan-head">⚠️ DATA STALE</div>'
                            '<div class="plan-msg">The price feed looks lagging or frozen — stand aside '
                            'until it catches up. Do not trade on stale data.</div>', unsafe_allow_html=True)
            elif own and not holding:
                st.info("Enter your buy price and shares above, then hit **Calculate** to see your live P&L.")

            elif holding:
                # You own it → focus on the exit (sell at the right time).
                per_share = a.price - entry
                pct = per_share / entry * 100
                pcol = "#16A34A" if per_share >= 0 else "#DC2626"
                sgn = "+" if per_share >= 0 else ""
                has_sh = bool(shares) and shares > 0
                pnl_txt = (f"{sgn}{per_share * shares:,.2f} ({sgn}{pct:.2f}%)" if has_sh
                           else f"{sgn}{per_share:,.2f}/share ({sgn}{pct:.2f}%)")
                if a.verdict == "SELL":
                    head, msg = "🔴 SELL / EXIT", "Momentum has turned against your long — lock in the move or cut the loss."
                elif a.verdict == "WAIT":
                    head, msg = "⏸️ TIGHTEN UP", "Choppy — consider trimming and tightening your stop."
                elif a.verdict == "HOLD":
                    head, msg = "🟡 HOLD", "Trend is unclear — hold, but tighten your stop to protect gains."
                else:
                    head, msg = "🟢 HOLD / ADD", "Trend is with you — hold and trail your stop up."
                trail = dtip("As price rises, move your stop up to about here so you lock in gains "
                             "and auto-exit if it reverses.")
                rows = f'<div class="row"><span>Your buy price</span><span>{entry:,.2f}</span></div>'
                if has_sh:
                    rows += f'<div class="row"><span>Shares</span><span>{shares:g}</span></div>'
                rows += (f'<div class="row"><span>Open P&amp;L</span>'
                         f'<span style="color:{pcol};font-weight:700">{pnl_txt}</span></div>')
                if has_sh:
                    rows += f'<div class="row"><span>Position value</span><span>{a.price * shares:,.2f}</span></div>'
                rows += f'<div class="row"><span>🛑 Move your stop up to {trail}</span><span>{a.stop:,.2f}</span></div>'
                st.markdown(f'<div class="risk-box">{rows}</div>'
                            f'<div class="plan-head">{head}</div><div class="plan-msg">{msg}</div>',
                            unsafe_allow_html=True)

            elif a.verdict == "BUY":
                if limit_hit:
                    st.markdown('<div class="plan-head">🛑 DONE FOR TODAY</div>'
                                '<div class="plan-msg">You have hit your daily loss limit — no new entries. '
                                'Protect your capital and come back tomorrow.</div>', unsafe_allow_html=True)
                else:
                    acct = st.session_state.get("acct_size")
                    rpct = st.session_state.get("risk_pct") or 1.0
                    ps = risk.position_size(acct, rpct, a.price, a.stop)
                    if ps and ps["shares"] > 0:
                        cap = " · capped by account" if ps["capped"] else ""
                        size_val = f'{ps["shares"]:g} sh · risks {ps["risk_dollars"]:,.0f}{cap}'
                    elif acct:
                        size_val = "account too small for 1 share"
                    else:
                        size_val = "set account size in 🛡️ Risk"
                    size_tip = dtip("Shares sized so that if the stop is hit you lose about your chosen "
                                    "risk-per-trade. Also capped to what your account can buy.")
                    buy_rows = (
                        f'<div class="row"><span>Buy near</span><span>{a.price:,.2f}</span></div>'
                        f'<div class="row"><span>🛑 Stop (1.5× ATR) '
                        f'{dtip("Where to sell and bail if it goes against you. Sits 1.5 ATR below entry, so normal wiggles do not stop you out.")}'
                        f'</span><span>{a.stop:,.2f}</span></div>'
                        f'<div class="row"><span>🎯 Sell target 1 (1R) '
                        f'{dtip("First place to take profit — a rise as big as what you risked (1R). A 1-to-1 reward.")}'
                        f'</span><span>{a.target1:,.2f}</span></div>'
                        f'<div class="row"><span>🎯 Sell target 2 (2R) '
                        f'{dtip("A bigger profit target — twice what you risked (2R). More reward, but price must climb further.")}'
                        f'</span><span>{a.target2:,.2f}</span></div>'
                        f'<div class="row"><span>📐 Suggested size {size_tip}</span><span>{size_val}</span></div>'
                    )
                    st.markdown('<div class="plan-head">🟢 BUY ZONE</div>'
                                '<div class="plan-msg">Signals favour a long. If you take it:</div>'
                                f'<div class="risk-box">{buy_rows}</div>', unsafe_allow_html=True)

            else:
                if a.verdict == "WAIT":
                    head, msg = "⏸️ STAY OUT", "Choppy, no clean setup — wait for clearer conditions before buying."
                elif a.verdict == "HOLD":
                    head, msg = "✋ WAIT FOR A BUY", "No clean entry yet — stay patient until the signals line up bullish."
                else:  # SELL while not holding
                    head, msg = "⛔ DON'T BUY", "It's bearish right now. You don't short, so simply stay flat and wait for a buy signal."
                st.markdown(f'<div class="plan-head">{head}</div><div class="plan-msg">{msg}</div>',
                            unsafe_allow_html=True)


@st.fragment(run_every="30s")
def intraday_chart_panel(ticker: str):
    """The chart only, on a slower 30s cycle so the fast verdict above doesn't reload
    the (heavier) TradingView iframe every few seconds. Reuses the cached bars, so it's cheap."""
    interval = st.session_state.get("intraday_interval", "5m")
    try:
        df = cached_intraday(ticker, interval)
        a = intraday.evaluate_intraday(df, ticker, interval)
    except Exception:
        st.caption("Chart unavailable right now — retrying on the next refresh.")
        return
    intraday_chart(a)


def render_day_summary(summ: dict | None, out: dict | None, in_session: bool):
    """Render the 'Summary of the day' recap + a rules-based setup into tomorrow."""
    if not summ:
        st.caption("Not enough data for a day summary yet.")
        return
    chg = summ["change_pct"]
    col = "#16A34A" if chg >= 0 else "#DC2626"
    arrow = "▲" if chg >= 0 else "▼"
    st.markdown(
        f'<div class="day-head">{summ["date"]} · '
        f'<span style="color:{col}">{arrow} {chg:+.2f}%</span> on the day · '
        f'range {summ["range_pct"]:.1f}%</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="day-stats">'
        f'<span><b>Open</b> {summ["open"]:,.2f}</span>'
        f'<span><b>High</b> {summ["high"]:,.2f} <i>{summ["high_time"]}</i></span>'
        f'<span><b>Low</b> {summ["low"]:,.2f} <i>{summ["low_time"]}</i></span>'
        f'<span><b>{"Now" if in_session else "Close"}</b> {summ["current"]:,.2f}</span>'
        '</div>', unsafe_allow_html=True)

    bits = []
    if summ.get("above_vwap_pct") is not None:
        p = summ["above_vwap_pct"]
        bits.append(f'Price spent **{p:.0f}%** of the day above VWAP — '
                    f'{"buyers" if p >= 50 else "sellers"} had the edge.')
    if summ.get("sessions"):
        seg = " · ".join(f'**{s["name"]}** {s["word"]} ({s["move_pct"]:+.1f}%)'
                         for s in summ["sessions"])
        bits.append("How it traded through the day — " + seg + ".")
    w = summ["pos_in_range"]
    wtxt = "near the highs" if w > 0.7 else "near the lows" if w < 0.3 else "mid-range"
    bits.append(f'Right now it sits **{wtxt}** of the day’s range.')
    st.markdown("\n\n".join(bits))

    if out:
        st.markdown(f'**Setup into tomorrow: {out["bias"]}.** '
                    + "; ".join(out["reasons"]).capitalize() + ".")
        lv = " · ".join(f'{k} {v:,.2f}' for k, v in out["levels"].items() if v is not None)
        st.caption(f'🎯 Key levels to watch tomorrow: {lv}. '
                   'These are reference points (today’s range, close & VWAP), **not a prediction** — '
                   'watch how price reacts around them.')


def render_live_dashboard(m: dict | None):
    """Visual gauges (vs-VWAP, Momentum, Volatility, Day-range) + a large-font level ladder."""
    if not m:
        st.caption("Live read unavailable right now.")
        return
    tiles = []

    # vs VWAP: centered gauge, where the marker shows how far price is from VWAP (±2% spans the bar).
    if m["vwap"] is not None:
        vd = m["vwap_dist_pct"]
        col = "#16A34A" if vd >= 0 else "#DC2626"
        bar = (f'<div class="lm-track"><div class="lm-center"></div>'
               f'<div class="lm-marker" style="left:{clamp(50 + vd * 25):.0f}%;background:{col}"></div></div>')
        tiles.append(
            f'<div class="lm-tile"><div class="lm-label">vs VWAP {dtip("VWAP is the volume-weighted average price — the average price everyone has paid so far today. Above it, buyers are in control; below it, sellers. The marker shows how far price sits above/below VWAP (±2% spans the bar).")}</div>'
            f'<div class="lm-val" style="color:{col}">{vd:+.2f}%</div>{bar}'
            f'<div class="lm-sub">{"Above" if vd >= 0 else "Below"} ${m["vwap"]:,.2f} — '
            f'{"buyers" if vd >= 0 else "sellers"} in control</div></div>')

    # Momentum: RSI gauge 0-100 with oversold/overbought ticks at 30 and 70.
    if m["rsi"] is not None:
        rsi = m["rsi"]
        word = "overbought" if rsi > 70 else "oversold" if rsi < 30 else "neutral"
        bar = ('<div class="lm-track"><span class="lm-tick" style="left:30%"></span>'
               '<span class="lm-tick" style="left:70%"></span>'
               f'<div class="lm-marker" style="left:{clamp(rsi):.0f}%;background:#0F172A"></div></div>')
        tiles.append(
            f'<div class="lm-tile"><div class="lm-label">Momentum · RSI {dtip("RSI measures how stretched the recent move is, on a 0–100 scale. Above 70 = overbought (stretched high), below 30 = oversold (stretched low), 30–70 = neutral. The dot is the live reading; the line below shows whether MACD momentum is building or fading.")}</div>'
            f'<div class="lm-val">{rsi:.0f}<small>{m["rsi_dir"]}</small></div>{bar}'
            f'<div class="lm-sub">{word}; MACD {"↑" if m["macd_above"] else "↓"} {m["macd_mom"]}</div></div>')

    # Volatility: ATR% fill bar (0-1.5% scale), colored by current pace.
    if m["atr_pct"] is not None:
        ap = m["atr_pct"]
        pace = m["pace"] or "normal"
        pcol = "#DC2626" if pace == "fast" else "#16A34A" if pace == "quiet" else "#F59E0B"
        bar = (f'<div class="lm-track"><div class="lm-fill" '
               f'style="left:0;width:{clamp(ap / 1.5 * 100, 0, 100):.0f}%;background:{pcol}"></div></div>')
        ratio = f' ({m["pace_ratio"]:.1f}× typical)' if m["pace_ratio"] else ""
        tiles.append(
            f'<div class="lm-tile"><div class="lm-label">Volatility · ATR {dtip("ATR (Average True Range) is how much price typically moves in one bar — your volatility gauge. Bigger = wilder swings, so you need a wider stop. The bar fills toward 1.5%; the label flags whether the latest bar moved faster or quieter than usual.")}</div>'
            f'<div class="lm-val">{ap:.2f}%<small>per bar</small></div>{bar}'
            f'<div class="lm-sub">{pace} pace{ratio}</div></div>')

    # Day range: where price sits between today's high and low.
    pos = m["pos_in_range"]
    where = "near highs" if pos > 0.7 else "near lows" if pos < 0.3 else "mid-range"
    chgcol = "#16A34A" if m["chg_pct"] >= 0 else "#DC2626"
    bar = (f'<div class="lm-track"><div class="lm-fill" style="left:0;width:{clamp(pos*100,0,100):.0f}%;'
           f'background:#2563EB"></div><div class="lm-marker" '
           f'style="left:{clamp(pos*100):.0f}%;background:#2563EB"></div></div>')
    tiles.append(
        f'<div class="lm-tile"><div class="lm-label">Day range {dtip("Shows the percent change on the day, and where the current price sits between today’s low and high. The marker near the top of the bar means it is trading near its highs; near the bottom means near its lows.")}</div>'
        f'<div class="lm-val" style="color:{chgcol}">{m["chg_pct"]:+.2f}%</div>{bar}'
        f'<div class="lm-sub">{where} of ${m["low"]:,.2f}–${m["high"]:,.2f}</div></div>')

    st.markdown(f'<div class="lm-grid">{"".join(tiles)}</div>', unsafe_allow_html=True)

    # Key-levels ladder (support / resistance), sorted high → low, current price highlighted.
    rows = []
    for role, cls, val in m["levels"]:
        if val is None:
            continue
        dist = "—" if cls == "now" else f'{(val - m["price"]) / m["price"] * 100:+.2f}%'
        rows.append(
            f'<div class="lad-row {cls}"><span class="lad-role">{LADDER_ICON[cls]} {role}</span>'
            f'<span class="lad-price">{val:,.2f}</span><span class="lad-dist">{dist}</span></div>')
    st.markdown(f'<div class="lad-head">📐 Key levels '
                f'{dtip("The prices that matter intraday: today’s High (resistance above), VWAP, the current price, and today’s Low (support below). Price often stalls or reverses at these — handy spots for entries, exits and stops. The % is how far each level is from the current price.")}'
                f'</div><div class="ladder">{"".join(rows)}</div>',
                unsafe_allow_html=True)


@st.fragment(run_every=f"{INTRADAY_REFRESH}s")
def intraday_summary_panel(ticker: str):
    """Bottom of the intraday tab (above history): the day's recap + setup into tomorrow,
    and a LIVE plain-English market read that refreshes with the verdict. Then history."""
    interval = st.session_state.get("intraday_interval", "5m")
    try:
        df = cached_intraday(ticker, interval)
        lq = cached_quote(ticker, API_KEY)
        in_session = bool(lq) and lq.state == "REGULAR"
        live_price = lq.price if in_session else None
        a = intraday.evaluate_intraday(df, ticker, interval, live_price=live_price,
                                       htf_trend=cached_daily_trend(ticker))
    except Exception:
        st.divider()
        render_verdict_history(ticker)
        return

    section("📡 Live market read")
    now_et = pd.Timestamp.now(tz="America/New_York")
    as_of = now_et.strftime("%H:%M:%S ET")
    mtc = None
    if in_session:
        close_et = now_et.normalize() + pd.Timedelta(hours=16)
        mtc = max(int((close_et - now_et).total_seconds() // 60), 0)
    htf = cached_daily_trend(ticker)
    dot = '<span class="lr-dot"></span>' if in_session else ""
    status = "LIVE" if in_session else "AS OF LAST CLOSE"
    st.markdown(f'<div class="lr-head">{dot}MARKET READ · {status} · {as_of}</div>', unsafe_allow_html=True)
    render_live_dashboard(narrator.live_metrics(a.df, a.price, htf_trend=htf, minutes_to_close=mtc))
    with st.expander("📖 Plain-English read"):
        reads = narrator.live_read(a.df, a.price, a.headline, htf_trend=htf, minutes_to_close=mtc)
        st.markdown("".join(f'<div class="lr-line"><strong>{lbl}:</strong> {body}</div>'
                            for lbl, body in reads), unsafe_allow_html=True)

    sumcol, histcol = st.columns(2, gap="large")
    with sumcol:
        section("🗒️ Summary of the day")
        with st.container(border=True):
            render_day_summary(narrator.day_summary(a.df), narrator.day_outlook(a.df), in_session)
    with histcol:
        render_verdict_history(ticker)


def render():
    """Render the Intraday tab."""
    st.markdown('<div class="search-label">⚡ Pick a ticker to day-trade</div>', unsafe_allow_html=True)
    itk = st.text_input("Intraday ticker", value="SOXL", label_visibility="collapsed",
                        key="intraday_ticker",
                        placeholder="Search a ticker…   e.g. SOXL, TQQQ, NVDA").strip().upper()
    with st.expander("ℹ️  What do the 6 verdicts mean?"):
        st.markdown(VERDICT_KEY_HTML, unsafe_allow_html=True)

    with st.expander("🛡️  Risk & money management", expanded=st.session_state.get("risk_exp", False)):
        rc1, rc2, rc3 = st.columns(3, vertical_alignment="bottom")
        rc1.number_input("Account size ($)", min_value=0.0, step=100.0, value=None,
                         placeholder="e.g. 5000", key="acct_size",
                         help="Total capital you trade with — used to size positions.")
        rc2.number_input("Risk per trade (%)", min_value=0.1, max_value=10.0, value=1.0, step=0.1,
                         key="risk_pct",
                         help="How much of your account you accept losing if a trade hits its stop. "
                              "1% is a common, safe default.")
        rc3.number_input("Max daily loss ($)", min_value=0.0, step=10.0, value=None,
                         placeholder="e.g. 150", key="max_daily_loss",
                         help="When your logged losses for the day reach this, the app tells you to stop.")

        st.divider()
        day = risk.load_today(trade_store())
        realized = sum(day["trades"])
        ntr = len(day["trades"])
        mx = st.session_state.get("max_daily_loss")
        t1, t2, t3 = st.columns(3)
        t1.metric("Trades logged today", ntr)
        t2.metric("Realized P&L today", f"{realized:+,.2f}")
        if mx and mx > 0:
            used = min(max(-realized, 0.0) / mx, 1.0)
            t3.metric("Daily loss used", f"{used * 100:.0f}%")
            st.progress(used)
            if realized <= -mx:
                st.error("🛑 DAILY LOSS LIMIT HIT — stop trading for today. Walk away.")

        st.caption("Log each closed trade so the loss limit can protect you:")
        lc1, lc2, lc3 = st.columns([2, 1, 1], vertical_alignment="bottom")
        pnl_in = lc1.number_input("Closed trade P&L ($)", value=None, step=1.0, format="%.2f",
                                  placeholder="+120 or -75", key="log_pnl", label_visibility="collapsed")
        if lc2.button("Add trade", key="log_add"):
            if pnl_in is not None:
                risk.record_trade(pnl_in, trade_store())
                st.session_state.pop("log_pnl", None)
                st.session_state["risk_exp"] = True
                st.rerun()
        if lc3.button("Reset day", key="log_reset"):
            risk.reset_today(trade_store())
            st.session_state["risk_exp"] = True
            st.rerun()

    if itk:
        st.session_state.setdefault("intraday_interval", "5m")
        intraday_panel(itk, API_KEY)              # fast: verdict + plan (every ~10s, fresh data)
        intraday_summary_panel(itk)               # fast: live read + day summary + history
        st.divider()
        tb_left, _ = st.columns([2, 3])
        with tb_left:
            st.segmented_control("Timeframe", ["1m", "3m", "5m", "15m"],
                                 key="intraday_interval", label_visibility="collapsed")
        intraday_chart_panel(itk)                 # chart at the bottom (slower 30s, no flicker)
        render_intraday_backtest(itk)             # rarely used validation tool, kept at the very bottom
