"""Display helpers used by more than one tab: verdict card, signal list, charts and badges."""

import json

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from views.theme import C_BLUE, C_DOWN, C_GOLD, C_UP, VERDICT_CLASS, VERDICT_EMOJI


# --------------------------------------------------------------------------- #
# Shared render helpers
# --------------------------------------------------------------------------- #
def dtip(text: str) -> str:
    """Dark-icon hover tooltip span (for use on light/white cards)."""
    return (f'<span class="tip tip-d"><span class="info-i">?</span>'
            f'<span class="tip-text">{text}</span></span>')


def verdict_card(tag: str, verdict: str, headline: str, price: float,
                 score: float, confidence: int, meta_line: str = "", agreement_tip: str = ""):
    agree_info = (f'<span class="tip"><span class="info-i">?</span>'
                  f'<span class="tip-text">{agreement_tip}</span></span>') if agreement_tip else ""
    chips = (f'<span class="chip">Price <b>{price:,.2f}</b></span>'
             f'<span class="chip">Score <b>{score:+.0f}</b></span>'
             f'<span class="chip">Agreement <b>{confidence}%</b>{agree_info}</span>')
    meta = f'<div class="v-meta">{meta_line}</div>' if meta_line else ""
    icon = VERDICT_EMOJI.get(verdict, "")
    cls = VERDICT_CLASS.get(headline, "vk-" + verdict.lower())
    st.markdown(
        f'<div class="verdict {cls}">'
        f'<div class="v-icon">{icon}</div>'
        f'<div class="v-body">'
        f'<div class="v-tag">{tag}</div>'
        f'<div class="v-head">{headline}</div>'
        f'<div class="v-chips">{chips}</div>{meta}'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def render_signals(sig_list):
    """A scannable scorecard: each signal = a row with a colored status pill.
    The explanation lives behind the hover 'i' so the board stays clean."""
    rows = []
    for s in sig_list:
        d = s.direction
        if d == "neutral":
            cls, label, wt = "neu", "Neutral", ""
        elif s.weight == 0:                                  # directional context, not scored
            cls, label, wt = "info", "Info", ""
        else:
            cls = "bull" if d == "bullish" else "bear"
            label = "Bullish" if d == "bullish" else "Bearish"
            wt = f'<span class="scard-wt">×{s.weight:g}</span>'
        rows.append(
            f'<div class="scard-row">'
            f'<span class="scard-dot {cls}"></span>'
            f'<span class="scard-name">{s.name}</span>'
            f'{dtip(s.detail)}'
            f'<span class="scard-pill {cls}">{label}{wt}</span>'
            f'</div>'
        )
    st.markdown(f'<div class="scard">{"".join(rows)}</div>', unsafe_allow_html=True)


def section(title: str):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)


def _lw_time(ts, mode):
    """Time value for Lightweight Charts: 'YYYY-MM-DD' for daily, else a UNIX
    second shifted by the tz offset so the axis shows the exchange's wall clock."""
    if mode == "date":
        return ts.strftime("%Y-%m-%d")
    off = ts.utcoffset().total_seconds() if ts.utcoffset() else 0
    return int(ts.value // 10**9 + int(off))


def _lw_candles(df, mode):
    rows = []
    for ts, r in df[["Open", "High", "Low", "Close"]].dropna().iterrows():
        rows.append({"time": _lw_time(ts, mode), "open": round(float(r.Open), 4),
                     "high": round(float(r.High), 4), "low": round(float(r.Low), 4),
                     "close": round(float(r.Close), 4)})
    return rows


def _lw_line(s, mode):
    return [{"time": _lw_time(ts, mode), "value": round(float(v), 4)}
            for ts, v in s.dropna().items()]


def _lw_hist(s, mode):
    out = []
    for ts, v in s.dropna().items():
        color = "rgba(22,163,74,.55)" if v >= 0 else "rgba(220,38,38,.55)"
        out.append({"time": _lw_time(ts, mode), "value": round(float(v), 4), "color": color})
    return out


def lw_chart(df, overlays, mode, height=640):
    """Responsive TradingView Lightweight Chart (v5) with synced panes:
    pane 0 = candles + overlays, pane 1 = RSI, pane 2 = MACD. One shared time axis.

    overlays: list of (column, color, line_width, legend_title); empty title hides from legend.
    """
    has_rsi = "RSI" in df.columns
    has_macd = all(c in df.columns for c in ("MACD", "MACD_SIGNAL", "MACD_HIST"))
    lines = [{"data": _lw_line(df[col], mode), "color": color, "width": w}
             for (col, color, w, _t) in overlays if col in df.columns]

    chips = f'<span><i style="background:{C_UP}"></i>Price</span>'
    for (_c, color, _w, title) in overlays:
        if title:
            chips += f'<span><i style="background:{color}"></i>{title}</span>'
    if has_rsi:
        chips += f'<span><i style="background:{C_GOLD}"></i>RSI</span>'
    if has_macd:
        chips += f'<span><i style="background:{C_BLUE}"></i>MACD</span>'
    st.markdown(f'<div class="lw-legend">{chips}</div>', unsafe_allow_html=True)

    payload = json.dumps({
        "candles": _lw_candles(df, mode), "lines": lines,
        "rsi": _lw_line(df["RSI"], mode) if has_rsi else [],
        "macd": _lw_line(df["MACD"], mode) if has_macd else [],
        "signal": _lw_line(df["MACD_SIGNAL"], mode) if has_macd else [],
        "hist": _lw_hist(df["MACD_HIST"], mode) if has_macd else [],
        "up": C_UP, "down": C_DOWN, "blue": C_BLUE, "gold": C_GOLD,
        "intraday": mode != "date",
    })
    html = (
        "<style>@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500&display=swap');"
        "html,body{margin:0;background:transparent;}</style>"
        f'<div id="c" style="width:100%;height:{height}px;background:#fff;'
        'border:1px solid #E5E9F0;border-radius:12px;overflow:hidden;"></div>'
        '<script src="https://unpkg.com/lightweight-charts@5.2.0/dist/lightweight-charts.standalone.production.js"></script>'
        f"<script>const P={payload};const L=LightweightCharts;const el=document.getElementById('c');"
        f"const chart=L.createChart(el,{{width:el.clientWidth||700,height:{height},"
        "layout:{background:{type:'solid',color:'#FFFFFF'},textColor:'#475569',"
        "fontFamily:'Plus Jakarta Sans, sans-serif',fontSize:12,"
        "panes:{separatorColor:'#E5E9F0',separatorHoverColor:'rgba(37,99,235,.12)'}},"
        "grid:{vertLines:{color:'rgba(17,24,39,.06)'},horzLines:{color:'rgba(17,24,39,.06)'}},"
        "rightPriceScale:{borderColor:'#E5E9F0',minimumWidth:64},"
        "timeScale:{borderColor:'#E5E9F0',timeVisible:P.intraday,secondsVisible:false,rightOffset:4},"
        "crosshair:{mode:L.CrosshairMode.Normal}});"
        "const cs=chart.addSeries(L.CandlestickSeries,{upColor:P.up,downColor:P.down,borderVisible:false,"
        "wickUpColor:P.up,wickDownColor:P.down},0);cs.setData(P.candles);"
        "P.lines.forEach(function(s){var ls=chart.addSeries(L.LineSeries,{color:s.color,lineWidth:s.width,"
        "priceLineVisible:false,lastValueVisible:false},0);ls.setData(s.data);});"
        "var pi=1;"
        "if(P.rsi.length){var rsi=chart.addSeries(L.LineSeries,{color:P.gold,lineWidth:2,"
        "priceLineVisible:false,lastValueVisible:true},pi);rsi.setData(P.rsi);"
        "rsi.createPriceLine({price:70,color:'#DC2626',lineWidth:1,lineStyle:2,axisLabelVisible:true,title:'70'});"
        "rsi.createPriceLine({price:30,color:'#16A34A',lineWidth:1,lineStyle:2,axisLabelVisible:true,title:'30'});pi++;}"
        "if(P.hist.length){var h=chart.addSeries(L.HistogramSeries,{priceLineVisible:false,lastValueVisible:false},pi);"
        "h.setData(P.hist);"
        "var ml=chart.addSeries(L.LineSeries,{color:P.blue,lineWidth:1.5,priceLineVisible:false,lastValueVisible:false},pi);ml.setData(P.macd);"
        "var sl=chart.addSeries(L.LineSeries,{color:P.gold,lineWidth:1.5,priceLineVisible:false,lastValueVisible:false},pi);sl.setData(P.signal);pi++;}"
        "var pn=chart.panes();if(pn[0])pn[0].setStretchFactor(3);"
        "for(var k=1;k<pn.length;k++){pn[k].setStretchFactor(1);}"
        "chart.timeScale().fitContent();"
        "new ResizeObserver(function(){chart.applyOptions({width:el.clientWidth});"
        "chart.timeScale().fitContent();}).observe(el);</script>"
    )
    components.html(html, height=height + 6)


def live_badge(q) -> str:
    if q.state in ("PRE", "PREPRE"):
        return "🌅 PRE-MARKET"
    if q.state in ("POST", "POSTPOST"):
        return "🌙 AFTER-HOURS"
    if q.state == "CLOSED":
        return "🕒 MARKET CLOSED"
    return "🔴 LIVE" if q.realtime else "🕒 DELAYED"


def render_backtest(res: dict, rules: str = ""):
    if res["trades"] == 0:
        st.warning(f"No trades triggered on {res['interval']} bars ({res['start']}–{res['end']}).")
        return
    st.caption(f"{res['interval']} bars · {res['start']}–{res['end']} · "
               f"{res['bars']:,} bars · {res['trades']} trades")
    a = st.columns(4)
    a[0].metric("Trades", res["trades"])
    a[1].metric("Win rate", f"{res['win_rate']:.0f}%")
    a[2].metric("Total return", f"{res['total_return']:+.1f}%")
    pf = res["profit_factor"]
    a[3].metric("Profit factor", "∞" if pf == float("inf") else f"{pf:.2f}",
                help="Gross profit ÷ gross loss. Above 1.0 = profitable; 1.5+ is solid.")
    b = st.columns(4)
    b[0].metric("Expectancy", f"{res['expectancy_R']:+.2f}R",
                help="Average result per trade in units of risk (R). Positive = an edge.")
    b[1].metric("Avg win", f"{res['avg_win']:+.2f}%")
    b[2].metric("Avg loss", f"{res['avg_loss']:+.2f}%")
    b[3].metric("Max drawdown", f"{res['max_drawdown']:.1f}%",
                help="Worst peak-to-trough drop of the equity curve.")
    st.line_chart(pd.DataFrame({"Equity (×)": res["curve"]}), height=220)
    st.caption(
        f"📌 Buy-&-hold over the same window: **{res['buy_hold']:+.1f}%**. "
        + (rules or "Rules tested: long-only, enter on a BUY at the bar close; exit on a 1.5×ATR stop, "
                    "a SELL signal, or end of day (no overnight holds). ")
        + "**No fees/slippage; past ≠ future — treat this as a sanity check, not a promise.**"
    )


def clamp(x, lo=3.0, hi=97.0):
    return max(lo, min(hi, x))
