"""
Stock Signal Advisor dashboard (Streamlit).

Run it with:   run.bat        (double-click it)
or:            .venv\\Scripts\\python.exe -m streamlit run app.py

Type a ticker and the app pulls real price data, calculates common technical indicators
and gives a BUY / SELL / HOLD verdict with the reasons behind it, for both intraday and
long-term timeframes. Not a prediction, and not financial advice.
"""

import contextlib
import json

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import alpaca_data
import backtest
import history
import intraday
import live
import narrator
import risk
import signals

st.set_page_config(page_title="Stock Signal Advisor", page_icon="📈", layout="wide")

# --------------------------------------------------------------------------- #
# Look & feel
# --------------------------------------------------------------------------- #
VERDICT_EMOJI = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡", "WAIT": "⏸️"}
LADDER_ICON = {"res": "▲", "vwap": "·", "now": "●", "sup": "▼"}
# Banner colour by full headline, matching the "6 verdicts" key badges exactly.
_VK_CLASS = {"Strong BUY": "vk-sbuy", "BUY": "vk-buy", "HOLD": "vk-hold",
             "WAIT": "vk-wait", "SELL": "vk-sell", "Strong SELL": "vk-ssell"}

# Chart palette (readable on a light canvas)
C_UP, C_DOWN = "#16A34A", "#DC2626"
C_BLUE, C_GOLD, C_PURPLE = "#2563EB", "#EA580C", "#7C3AED"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html { font-size: 18px; }
html, body, .stApp, [data-testid="stAppViewContainer"], [class*="css"] {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
.stApp { background: radial-gradient(1100px 560px at 18% -8%, #EEF2F9 0%, #F6F8FB 55%); }
.block-container { max-width: 1220px; padding-top: 2.2rem; padding-bottom: 3rem; }
[data-testid="stHeader"] { background: transparent; }

/* readable body text */
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li { font-size: 1.05rem; line-height: 1.62; color:#2B3445; }
[data-testid="stCaptionContainer"] p, [data-testid="stCaptionContainer"] { font-size: 0.95rem; color:#667085; }

/* numbers align cleanly */
.verdict, .chip, .risk-box, [data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }

/* sidebar */
[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #E5E9F0; }
[data-testid="stSidebar"] .block-container { padding-top: 1.5rem; }

/* headings */
h1, h2, h3, h4 { font-weight: 700; letter-spacing: -0.01em; color: #111827; }
hr { border-color: #E5E9F0; }

/* metric cards */
[data-testid="stMetric"] {
    background: #FFFFFF; border: 1px solid #E5E9F0; border-radius: 14px; padding: 16px 18px;
    box-shadow: 0 1px 2px rgba(16,24,40,.04);
}
[data-testid="stMetricValue"] { font-weight: 700; font-size: 1.75rem; color:#111827; }
[data-testid="stMetricLabel"] p { color: #667085; font-weight: 500; font-size: 0.95rem; }

/* tabs */
[data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid #E5E9F0; }
[data-testid="stTabs"] button[data-baseweb="tab"] { font-weight: 600; font-size: 1.08rem; padding: 10px 18px; }

/* primary buttons: white text on blue (override the global paragraph color) */
button[kind="primary"], [data-testid="stBaseButton-primary"] {
    background-color: #2563EB !important; border-color: #2563EB !important; font-weight: 600;
}
button[kind="primary"] *, [data-testid="stBaseButton-primary"] * { color: #FFFFFF !important; }
button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {
    background-color: #1D4ED8 !important; border-color: #1D4ED8 !important;
}

/* green Calculate button (targeted by its widget key) */
.st-key-calc_btn button:not(:disabled) { background-color:#16A34A !important; border-color:#16A34A !important; }
.st-key-calc_btn button:not(:disabled):hover { background-color:#15803D !important; border-color:#15803D !important; }
.st-key-calc_btn button:not(:disabled) * { color:#FFFFFF !important; }

/* Intraday ticker — styled as a real search bar (magnifier icon + rounded field) */
.search-label { font-size:.82rem; font-weight:700; letter-spacing:.05em; text-transform:uppercase;
    color:#64748B; margin:4px 0 8px; }
.st-key-intraday_ticker { max-width:560px; }
.st-key-intraday_ticker [data-baseweb="input"] {
    position:relative; border:1.5px solid #DCE4F2 !important; border-radius:14px !important;
    background:#FFFFFF !important; box-shadow:0 2px 10px rgba(16,24,40,.06) !important;
    transition:border-color .15s, box-shadow .15s; }
.st-key-intraday_ticker [data-baseweb="input"]::before {
    content:"🔍"; position:absolute; left:15px; top:50%; transform:translateY(-50%);
    font-size:15px; opacity:.55; pointer-events:none; z-index:2; }
.st-key-intraday_ticker [data-baseweb="input"]:focus-within {
    border-color:#2563EB !important; box-shadow:0 0 0 4px rgba(37,99,235,.14) !important; }
.st-key-intraday_ticker input {
    padding-left:42px !important; font-size:1.15rem !important; font-weight:700 !important;
    color:#0F172A !important; background:transparent !important; }
.st-key-intraday_ticker input::placeholder {
    font-weight:500 !important; letter-spacing:normal !important; color:#9AA5B5 !important; }

/* Hide the "Press Enter to apply" hint under every input site-wide */
[data-testid="InputInstructions"] { display:none !important; }

/* ticker inputs show uppercase as you type (placeholder stays normal case) */
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea { text-transform: uppercase; }
[data-testid="stTextInput"] input::placeholder, [data-testid="stTextArea"] textarea::placeholder { text-transform: none; }

[data-testid="stDataFrame"] { border: 1px solid #E5E9F0; border-radius: 12px; }

/* ---------- custom components ---------- */
.hero { display:flex; align-items:center; gap:15px; margin: 0 0 2px; }
.hero-logo {
    font-size: 1.7rem; width:52px; height:52px; display:flex; align-items:center; justify-content:center;
    background: linear-gradient(135deg,#2563EB,#16C784); border-radius:15px; box-shadow:0 8px 22px rgba(37,99,235,.22);
}
.hero h1 { font-size: 2.15rem; margin: 0; color:#0F172A; }
.hero-sub { color:#667085; font-size: 1.02rem; margin: 5px 0 6px; }

.verdict { display:flex; align-items:center; gap:26px; border-radius: 18px; padding: 22px 30px; margin: 10px 0 8px;
    color:#fff; box-shadow: 0 14px 34px rgba(16,24,40,.18); }
.v-icon { font-size:3.7rem; line-height:1; flex-shrink:0; filter:drop-shadow(0 2px 6px rgba(0,0,0,.18)); }
.v-body { flex:1; min-width:0; }
/* Banner colours mirror the "6 verdicts" key badges exactly */
.verdict.vk-sbuy  { background: linear-gradient(135deg,#0E9F6E,#16C784); }
.verdict.vk-buy   { background:#16A34A; }
.verdict.vk-hold  { background:#F59E0B; }
.verdict.vk-wait  { background:#64748B; }
.verdict.vk-sell  { background:#DC2626; }
.verdict.vk-ssell { background: linear-gradient(135deg,#C81E2B,#EF4444); }
.v-tag  { font-size:.84rem; letter-spacing:2px; text-transform:uppercase; color:rgba(255,255,255,.92); }
.v-head { font-size:3.1rem; font-weight:800; line-height:1.04; margin:5px 0 14px; }
.v-chips { display:flex; flex-wrap:wrap; gap:9px; }
.chip { background: rgba(255,255,255,.20); border:1px solid rgba(255,255,255,.32);
    border-radius:999px; padding:7px 16px; font-size:.98rem; }
.chip b { font-weight:700; }
.v-meta { font-size:.88rem; opacity:.92; margin-top:14px; }
/* Action zone — the "Your plan" sidebar: tinted box with even padding on all 4 sides */
.st-key-action_zone { background:#F6F9FF !important; border:1px solid #D8E3F6 !important;
    border-radius:14px !important; padding:18px 20px !important; }
.st-key-action_zone .section-title { margin-top:2px; }   /* container padding handles the top gap */

/* "Why this verdict" scorecard — one scannable status row per signal */
.scard { display:flex; flex-direction:column; gap:8px; }
.scard-row { display:flex; align-items:center; gap:11px; background:#FFFFFF; border:1px solid #E8ECF3;
    border-radius:10px; padding:11px 15px; box-shadow:0 1px 2px rgba(16,24,40,.03); }
.scard-dot { width:9px; height:9px; border-radius:50%; flex-shrink:0; }
.scard-dot.bull { background:#16A34A; }
.scard-dot.bear { background:#DC2626; }
.scard-dot.neu  { background:#CBD2DE; }
.scard-dot.info { background:#3B82F6; }
.scard-name { font-weight:600; font-size:1.02rem; color:#1F2937; }
.scard-pill { margin-left:auto; font-weight:700; font-size:.76rem; letter-spacing:.04em;
    text-transform:uppercase; border-radius:999px; padding:5px 12px; white-space:nowrap; flex-shrink:0; }
.scard-pill.bull { background:#DCFCE7; color:#15803D; border:1px solid #BBF7D0; }
.scard-pill.bear { background:#FEE2E2; color:#B91C1C; border:1px solid #FECACA; }
.scard-pill.neu  { background:#F1F5F9; color:#64748B; border:1px solid #E2E8F0; }
.scard-pill.info { background:#EFF6FF; color:#2563EB; border:1px solid #DBEAFE; }
.scard-wt { opacity:.7; margin-left:3px; }

.section-title { font-size:1.2rem; font-weight:700; color:#0F172A; margin: 34px 0 14px;
    padding-left:12px; border-left:4px solid #2563EB; line-height:1.25; }
.risk-box { background:#FFFFFF; border:1px solid #E5E9F0; border-radius:12px; padding:16px 18px; margin:10px 0 14px; box-shadow: 0 1px 2px rgba(16,24,40,.04); }
.risk-box .row { display:flex; justify-content:space-between; padding:7px 0; font-size:1.05rem; color:#4B5563; }
.risk-box .row > span:last-child { font-weight:700; color:#111827; }
.plan-head { font-weight:700; font-size:1.08rem; margin:12px 0 4px; color:#111827; }
.plan-msg { color:#4B5563; font-size:.98rem; line-height:1.5; }
.muted { color:#667085; font-size:.92rem; }
.vhist { background:#FFFFFF; border:1px solid #E5E9F0; border-radius:12px; padding:6px 16px 12px;
    margin:8px 0 16px; max-height:340px; overflow-y:auto; box-shadow:0 1px 2px rgba(16,24,40,.04); }
.vh-day { position:sticky; top:0; background:#FFFFFF; font-weight:700; color:#0F172A; font-size:.92rem;
    padding:10px 0 6px; border-bottom:1px solid #EEF1F6; }
.vh-item { padding:7px 2px; border-bottom:1px dashed #F1F3F8; }
.vh-item:last-child { border-bottom:none; }
.vh-row { display:flex; align-items:center; gap:12px; font-size:1rem; }
.vh-t { color:#475569; font-variant-numeric:tabular-nums; min-width:48px; }
.vh-v { font-weight:700; min-width:96px; }
.vh-iv { font-size:.72rem; color:#64748B; background:#F1F5F9; border-radius:6px; padding:1px 7px; }
.vh-px { margin-left:auto; color:#334155; font-variant-numeric:tabular-nums; }
.vh-after { font-size:.82rem; color:#94A3B8; margin:3px 0 0 60px; font-variant-numeric:tabular-nums; }
.vh-after .vh-hi { color:#16A34A; font-weight:600; }
.vh-after .vh-lo { color:#DC2626; font-weight:600; }
.vh-after .vh-live { color:#64748B; font-style:italic; }
.vh-after.vh-na { color:#CBD5E1; }
.live-read { background:#F8FAFF; border:1px solid #DCE4F2; border-left:4px solid #2563EB;
    border-radius:12px; padding:14px 16px; margin:8px 0 26px; }
.lr-head { display:flex; align-items:center; gap:8px; color:#2563EB; font-weight:700;
    font-size:.8rem; letter-spacing:.05em; margin-bottom:8px; }
.lr-dot { width:8px; height:8px; border-radius:50%; background:#22C55E; animation:lrpulse 1.1s infinite; }
@keyframes lrpulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.lr-line { color:#334155; font-size:1.02rem; line-height:1.55; margin:4px 0; padding-left:18px; position:relative; }
.lr-line::before { content:"›"; position:absolute; left:3px; color:#94A3B8; font-weight:700; }
.day-head { font-size:1.05rem; font-weight:600; color:#0F172A; margin-bottom:2px; }
.day-stats { display:flex; flex-wrap:wrap; gap:7px 18px; margin:7px 0 10px; font-size:1.02rem;
    color:#475569; font-variant-numeric:tabular-nums; }
.day-stats b { color:#0F172A; font-weight:700; margin-right:4px; }
.day-stats i { color:#94A3B8; font-style:normal; font-size:.8rem; }

/* Live market read — visual dashboard (gauge tiles + level ladder) */
.lm-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:12px; margin-bottom:14px; }
.lm-tile { background:#FFFFFF; border:1px solid #E8ECF3; border-radius:12px; padding:13px 16px;
    box-shadow:0 1px 2px rgba(16,24,40,.03); }
.lm-label { font-size:.7rem; font-weight:700; letter-spacing:.06em; text-transform:uppercase; color:#94A3B8; }
.lm-val { font-size:1.55rem; font-weight:800; color:#0F172A; margin:3px 0 11px; line-height:1; }
.lm-val small { font-size:.8rem; font-weight:600; color:#64748B; margin-left:6px; text-transform:capitalize; }
.lm-track { position:relative; height:8px; border-radius:999px; background:#EEF2F7; }
.lm-fill { position:absolute; top:0; bottom:0; border-radius:999px; }
.lm-marker { position:absolute; top:50%; width:14px; height:14px; border-radius:50%;
    border:2px solid #fff; transform:translate(-50%,-50%); box-shadow:0 1px 3px rgba(0,0,0,.28); z-index:2; }
.lm-center { position:absolute; left:50%; top:-3px; bottom:-3px; width:2px; background:#CBD5E1; transform:translateX(-50%); }
.lm-tick { position:absolute; top:-3px; bottom:-3px; width:2px; background:#CBD5E1; }
.lm-sub { font-size:.82rem; color:#64748B; margin-top:9px; line-height:1.35; }

.lad-head { font-size:.82rem; font-weight:700; letter-spacing:.05em; text-transform:uppercase;
    color:#64748B; margin:2px 0 8px; }
.ladder { display:flex; flex-direction:column; border:1px solid #E8ECF3; border-radius:12px; overflow:hidden; }
.lad-row { display:flex; align-items:baseline; gap:12px; padding:11px 16px; border-bottom:1px solid #F1F4F9; }
.lad-row:last-child { border-bottom:none; }
.lad-role { font-size:.9rem; font-weight:700; width:138px; flex-shrink:0; }
.lad-price { font-size:1.4rem; font-weight:800; font-variant-numeric:tabular-nums; }
.lad-dist { margin-left:auto; font-size:.92rem; font-variant-numeric:tabular-nums; color:#64748B; }
.lad-row.res .lad-role, .lad-row.res .lad-price { color:#B91C1C; }
.lad-row.sup .lad-role, .lad-row.sup .lad-price { color:#15803D; }
.lad-row.vwap .lad-role, .lad-row.vwap .lad-price { color:#64748B; }
.lad-row.now { background:#EFF6FF; }
.lad-row.now .lad-role, .lad-row.now .lad-price { color:#2563EB; }
.lw-legend { display:flex; gap:16px; flex-wrap:wrap; margin:6px 2px 8px; font-size:.92rem; color:#475569; font-weight:500; }
.lw-legend i { display:inline-block; width:11px; height:11px; border-radius:3px; margin-right:7px; vertical-align:middle; }
.tip { position:relative; cursor:help; white-space:nowrap; display:inline-flex; align-items:center; vertical-align:middle; }
.tip .info-i { display:inline-flex; align-items:center; justify-content:center; box-sizing:border-box;
    width:16px; height:16px; flex-shrink:0; border-radius:50%; border:1px solid rgba(255,255,255,.7);
    font-size:10px; line-height:1; font-weight:700; font-style:normal; text-transform:none;
    letter-spacing:normal; margin-left:6px; vertical-align:middle; }
.tip-d .info-i { border-color:#9AA5B5; color:#667085; }   /* dark icon for light backgrounds */
.tip .tip-text { visibility:hidden; opacity:0; transition:opacity .15s ease; position:absolute;
    left:0; top:calc(100% + 8px); z-index:9999; width:250px; white-space:normal; text-transform:none; letter-spacing:normal;
    font-size:.8rem; font-weight:500; line-height:1.45; color:#fff; background:#0F172A;
    padding:9px 12px; border-radius:9px; box-shadow:0 12px 28px rgba(0,0,0,.35); }
.tip:hover .tip-text { visibility:visible; opacity:1; }
.vkey { display:flex; flex-direction:column; gap:9px; }
.vkey .vrow { display:flex; align-items:center; gap:13px; }
.vkey .badge { flex-shrink:0; width:112px; text-align:center; color:#fff; font-weight:700;
    font-size:.82rem; padding:6px 8px; border-radius:8px; letter-spacing:.3px; }
.vkey .desc { color:#4B5563; font-size:.98rem; line-height:1.4; }
.vkey .b-sbuy  { background:linear-gradient(135deg,#0E9F6E,#16C784); }
.vkey .b-buy   { background:#16A34A; }
.vkey .b-hold  { background:#F59E0B; }
.vkey .b-wait  { background:#64748B; }
.vkey .b-sell  { background:#DC2626; }
.vkey .b-ssell { background:linear-gradient(135deg,#C81E2B,#EF4444); }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

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
    cls = _VK_CLASS.get(headline, "vk-" + verdict.lower())
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


@st.cache_data(ttl=900, show_spinner=False)
def cached_analyze(ticker: str, period: str):
    """Cache results for 15 min so flipping tabs doesn't re-hit Yahoo every time."""
    return signals.analyze(ticker, period=period)


def _live_badge(q) -> str:
    if q.state in ("PRE", "PREPRE"):
        return "🌅 PRE-MARKET"
    if q.state in ("POST", "POSTPOST"):
        return "🌙 AFTER-HOURS"
    if q.state == "CLOSED":
        return "🕒 MARKET CLOSED"
    return "🔴 LIVE" if q.realtime else "🕒 DELAYED"


@st.fragment(run_every="15s")
def live_price_ticker(ticker: str, api_key: str | None):
    """Last price, refreshed every 15s. Also shows pre-market and after-hours prices."""
    q = live.get_live_quote(ticker, api_key)
    if not q or q.price is None:
        st.caption("⚠️ Live price unavailable right now.")
        return
    delta = (f"{q.change:+.2f} ({q.percent:+.2f}%)"
             if (q.change is not None and q.percent is not None) else None)
    st.metric(label=f"{_live_badge(q)}  ·  {q.ticker}  ·  {q.source}",
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


def _hm(tod: str) -> str:
    """'09:30' -> '9:30', '15:45' -> '3:45' (12-hour without am/pm, for axis labels)."""
    hh, mm = tod.split(":")
    return f"{int(hh) % 12 or 12}:{mm}"


def _microbars(series, color_fn, label_every: int = 4) -> str:
    """A compact 26-bar intraday strip (one bar per 15-min bucket). Heights scale to the
    series max; `color_fn(tod, value)` picks each bar's colour. Returns inline-styled HTML."""
    if not series:
        return ""
    mx = max((v for _, v in series), default=0) or 1.0
    cells = []
    for i, (t, v) in enumerate(series):
        hpx = 6 + max(v, 0) / mx * 60
        lab = _hm(t) if i % label_every == 0 else ""
        cells.append(
            '<div style="display:flex;flex-direction:column;align-items:center;flex:1;gap:3px;justify-content:flex-end;">'
            f'<div style="width:74%;height:{hpx:.0f}px;background:{color_fn(t, v)};border-radius:3px 3px 0 0;"></div>'
            f'<div style="font-size:.56rem;color:#94A3B8;height:11px;white-space:nowrap;">{lab}</div></div>')
    return ('<div style="display:flex;align-items:flex-end;gap:2px;height:94px;padding:8px 6px 2px;'
            f'background:#fff;border:1px solid #E8ECF3;border-radius:12px;overflow:hidden;margin-bottom:4px;">'
            f'{"".join(cells)}</div>')


def _legend(items) -> str:
    """A row of little colour-chip + label pairs, so a chart explains itself in plain words."""
    chips = "".join(
        '<span style="display:inline-flex;align-items:center;gap:5px;margin-right:14px;font-size:.78rem;color:#64748B;">'
        f'<span style="width:11px;height:11px;border-radius:3px;background:{c};"></span>{lab}</span>'
        for c, lab in items)
    return f'<div style="margin:-2px 0 8px;">{chips}</div>'


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


def render_behavior_panel(ticker: str, wrap: bool = True):
    """'Know your ticker': a measured risk profile (not a prediction). Covers the daily
    character (volatility, overnight split, decay) plus the intraday microstructure from
    15-minute bars over about a year: volatility curve, liquidity, best time to enter,
    opening-range breaks, and whether the ticker tends to trend or mean-revert intraday.

    wrap=True nests it in an expander (inline use); wrap=False renders it bare for the
    dedicated 🔬 Know your ticker tab, which brings its own search box."""
    ctx = (st.expander(f"📊  Know your ticker — {ticker}’s risk & microstructure", expanded=True)
           if wrap else contextlib.nullcontext())
    with ctx:
        try:
            with st.spinner(f"Profiling {ticker} — ~3y daily + ~1y of 15-min bars…"):
                b = cached_behavior_stats(ticker)
                m = cached_microstructure(ticker)
        except Exception as e:
            st.caption(f"⚠️ Couldn’t profile {ticker}: {e}")
            return
        if not b:
            st.caption(f"Not enough history to profile {ticker} yet.")
            return

        spice = "🌶️🌶️🌶️" if b["ann_vol"] >= 80 else "🌶️🌶️" if b["ann_vol"] >= 40 else "🌶️"
        word = ("Wild ride" if b["ann_vol"] >= 80 else
                "Lively mover" if b["ann_vol"] >= 40 else "Fairly calm")
        hold = ("🚫 Too risky to hold for weeks — it slowly loses value over time."
                if b["ann_vol"] >= 60 else "")
        st.markdown(
            '<div class="lm-tile" style="padding:16px 18px;">'
            '<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">'
            f'<div style="font-size:2rem;line-height:1;">{spice}</div>'
            f'<div><div style="font-weight:800;font-size:1.35rem;color:#0F172A;">{ticker} — {word}</div>'
            f'<div style="color:#475569;font-size:1.02rem;">On a normal day it moves about '
            f'<b>{b["avg_range"]:.0f}%</b> up or down. {hold}</div></div></div></div>',
            unsafe_allow_html=True)

        # ---------- where is it right now? ----------
        if b.get("pos52") is not None:
            posm = _clamp(b["pos52"], 2, 98)
            hr = b.get("heat_ratio")
            heat = ("🔥 hotter than usual" if hr and hr >= 1.2 else
                    "❄️ calmer than usual" if hr and hr <= 0.8 else "≈ about its usual pace")
            near = ("near its highs" if b["pos52"] >= 70 else
                    "near its lows" if b["pos52"] <= 30 else "around the middle")
            st.markdown('<div class="section-title">📍 Where is it right now?</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="lm-track" style="height:11px;margin:4px 0 5px;">'
                f'<div class="lm-fill" style="left:0;width:{posm:.0f}%;background:#2563EB;"></div>'
                f'<div class="lm-marker" style="left:{posm:.0f}%;background:#0F172A;"></div></div>'
                '<div style="display:flex;justify-content:space-between;font-size:.76rem;color:#94A3B8;font-weight:600;">'
                f'<span>52-wk low ${b["lo52"]:,.2f}</span><span style="color:#0F172A;">now ${b["last_close"]:,.2f}</span>'
                f'<span>52-wk high ${b["hi52"]:,.2f}</span></div>',
                unsafe_allow_html=True)
            st.caption(f"Latest price is **{b['pos52']:.0f}%** of the way up its past-year range ({near}), about "
                       f"**{abs(b['pct_from_high']):.0f}% below** the 1-year high. Lately it’s trading **{heat}** "
                       "(last 2 weeks vs its normal daily swing).")

        tiles = []
        if m and m.get("open_ratio"):
            w = _clamp(m["open_ratio"] / 3 * 100, 0, 100)
            tiles.append(
                '<div class="lm-tile"><div class="lm-label">🕘 First 15 minutes</div>'
                '<div class="lm-val" style="color:#DC2626">Wildest</div>'
                f'<div class="lm-track"><div class="lm-fill" style="left:0;width:{w:.0f}%;background:#DC2626"></div></div>'
                f'<div class="lm-sub">Jumps around about <b>{m["open_ratio"]:.0f}×</b> more than midday. Trade small here.</div></div>')
        if m and m.get("last30_big_pct") is not None:
            tiles.append(
                '<div class="lm-tile"><div class="lm-label">🔔 Last 30 minutes</div>'
                '<div class="lm-val" style="color:#16A34A">Usually calm</div>'
                '<div class="lm-track"><div class="lm-fill" style="left:0;width:30%;background:#F59E0B"></div></div>'
                f'<div class="lm-sub">…but it can flip fast — on about <b>{m["last30_big_pct"]:.0f}%</b> of days it makes a big move right into the close.</div></div>')
        tiles.append(
            '<div class="lm-tile"><div class="lm-label">🌙 Overnight</div>'
            '<div class="lm-val" style="color:#DC2626">Biggest risk</div>'
            f'<div class="lm-track"><div class="lm-fill" style="left:0;width:{_clamp(b["overnight_var_share"], 0, 100):.0f}%;background:#7C3AED"></div></div>'
            f'<div class="lm-sub">Lots happens while the market is shut. A bad night can drop it <b>{b["gap_worst"]:.0f}%</b> before you can react.</div></div>')
        flat_one_in = max(1, round(100 / b["flat_pct"])) if b["flat_pct"] else 0
        tiles.append(
            '<div class="lm-tile"><div class="lm-label">➖ Quiet days</div>'
            f'<div class="lm-val">1 in {flat_one_in}</div>'
            f'<div class="lm-track"><div class="lm-fill" style="left:0;width:{_clamp(b["flat_pct"] * 3, 0, 100):.0f}%;background:#2563EB"></div></div>'
            '<div class="lm-sub">Some days barely move — the action already happened overnight.</div></div>')
        st.markdown(f'<div class="lm-grid">{"".join(tiles)}</div>', unsafe_allow_html=True)

        # --- overnight deep-dive ---
        on, dy = b.get("overnight_abs_mean"), b.get("intraday_abs_mean")
        if on is not None and dy is not None and (on + dy) > 0:
            on_share = on / (on + dy) * 100
            day_share = 100 - on_share
            st.markdown('<div class="section-title">🌙 What happens overnight?</div>', unsafe_allow_html=True)
            st.markdown(
                '<div style="display:flex;height:38px;border-radius:9px;overflow:hidden;border:1px solid #E8ECF3;'
                'font-weight:700;font-size:.9rem;color:#fff;">'
                f'<div style="width:{on_share:.0f}%;background:#7C3AED;display:flex;align-items:center;'
                f'justify-content:center;min-width:58px;">🌙 {on_share:.0f}%</div>'
                f'<div style="width:{day_share:.0f}%;background:#F59E0B;display:flex;align-items:center;'
                f'justify-content:center;min-width:58px;">☀️ {day_share:.0f}%</div></div>',
                unsafe_allow_html=True)
            st.caption(f"About **{on_share:.0f}%** of a typical day’s movement happens **overnight** (🌙) — while the "
                       "market is shut and you can’t trade or set a safety net. The rest happens during the day (☀️).")

            ocards = [
                ("Typical overnight move", f'±{b["overnight_abs_mean"]:.1f}%', "how far it usually jumps from yesterday’s close", ""),
                ("Opens higher", f'{b["gap_up_pct"]:.0f}%', "of mornings (it opens lower the rest)", ""),
                ("Biggest jump up", f'+{b["gap_best"]:.0f}%', "best overnight jump in 3 years", "#16A34A"),
                ("Biggest drop", f'{b["gap_worst"]:.0f}%', "worst overnight fall in 3 years", "#DC2626"),
            ]
            cells = []
            for lab, val, sub, col in ocards:
                style = f' style="color:{col}"' if col else ""
                cells.append(f'<div class="lm-tile"><div class="lm-label">{lab}</div>'
                             f'<div class="lm-val"{style}>{val}</div><div class="lm-sub">{sub}</div></div>')
            st.markdown(f'<div class="lm-grid">{"".join(cells)}</div>', unsafe_allow_html=True)

            extra = ""
            cu = b.get("gap_cont_up_pct")
            if cu is not None:
                extra = (" After a big jump up, the morning usually **keeps going** up." if cu >= 55 else
                         " After a big jump up, the morning often **gives some back**." if cu <= 45 else
                         " After a big jump up, the next move is roughly a coin-flip.")
            st.caption(f"It makes a **big** overnight move (more than 2%) on about **{b['gap_big_pct']:.0f}%** of "
                       f"nights.{extra} That’s why holding overnight is the riskiest bet — a surprise can hit before "
                       "the market reopens.")

        # --- the day, in 15-minute pictures ---
        if m and m.get("vol_curve"):
            vmax = max(v for _, v in m["vol_curve"])
            st.markdown('<div class="section-title">🌡️ How wild is each part of the day?</div>', unsafe_allow_html=True)
            st.markdown(_legend([("#DC2626", "wild"), ("#F59E0B", "medium"), ("#FCD34D", "calm")]),
                        unsafe_allow_html=True)
            st.markdown(_microbars(m["vol_curve"],
                        lambda t, v: "#DC2626" if v >= 0.9 * vmax else "#F59E0B" if v >= 0.55 * vmax else "#FCD34D"),
                        unsafe_allow_html=True)
            pk = max(m["vol_curve"], key=lambda x: x[1])
            cm = min(m["vol_curve"], key=lambda x: x[1])
            st.caption(f"Wildest right at the open (**{_hm(pk[0])}**), calmest around **{_hm(cm[0])}**. "
                       "Taller bar = bigger swings, so trade smaller then.")

            if m.get("vol_profile"):
                vpmax = max(v for _, v in m["vol_profile"])
                st.markdown('<div class="section-title">👥 When is it busiest?</div>', unsafe_allow_html=True)
                st.markdown(_legend([("#2563EB", "busy — easy to buy/sell"), ("#93C5FD", "quiet")]),
                            unsafe_allow_html=True)
                st.markdown(_microbars(m["vol_profile"], lambda t, v: "#2563EB" if v >= 0.9 * vpmax else "#93C5FD"),
                            unsafe_allow_html=True)
                top2 = sorted(m["vol_profile"], key=lambda x: x[1], reverse=True)[:2]
                st.caption(f"Busiest at the open and the close (around **{'** & **'.join(_hm(t) for t, _ in top2)}**). "
                           "More people trading = easier to get a fair price; quiet midday can mean a worse one.")

            if m.get("path") and m.get("entry_tod") and m.get("exit_tod"):
                ent, ex = m["entry_tod"], m["exit_tod"]
                st.markdown('<div class="section-title">💲 When is it usually cheapest to buy?</div>',
                            unsafe_allow_html=True)
                st.markdown(_legend([("#16A34A", "cheapest"), ("#CBD5E1", "in between"), ("#DC2626", "priciest")]),
                            unsafe_allow_html=True)
                st.markdown(_microbars(m["path"],
                            lambda t, v: "#16A34A" if t == ent else "#DC2626" if t == ex else "#CBD5E1"),
                            unsafe_allow_html=True)
                st.caption(f"Usually cheapest just after the open (**{_hm(ent)}**) and priciest near the close "
                           f"(**{_hm(ex)}**). So on a typical day: buy the morning dip, sell into the afternoon.")

        # --- two simple personality cards ---
        cards = []
        if m and m.get("or_up_pct") is not None:
            cards.append(
                '<div class="lm-tile"><div class="lm-label">📈 After the first 30 minutes</div>'
                '<div class="lm-val" style="color:#16A34A">Usually pushes up</div>'
                f'<div class="lm-sub">On <b>{m["or_up_pct"]:.0f}%</b> of days it breaks past the early-morning high — '
                f'and when it does, it keeps going about <b>{m["or_follow_pct"]:.0f}%</b> of the time.</div></div>')
        if m and m.get("persist") is not None:
            p = m["persist"]
            if p < -0.03:
                pic, head, sub = "🔄", "Bounces back", "When it jumps, it often gives some back — take profits a little early."
            elif p > 0.03:
                pic, head, sub = "📈", "Keeps trending", "Moves tend to keep going — let your winners run a bit longer."
            else:
                pic, head, sub = "🎲", "No clear habit", "One move doesn’t really predict the next."
            cards.append(
                f'<div class="lm-tile"><div class="lm-label">{pic} Its personality</div>'
                f'<div class="lm-val">{head}</div><div class="lm-sub">{sub}</div></div>')
        if cards:
            st.markdown(f'<div class="lm-grid">{"".join(cards)}</div>', unsafe_allow_html=True)

        # --- best & worst days of the week ---
        if b.get("dow"):
            dow = b["dow"]
            st.markdown('<div class="section-title">📅 Best &amp; worst days of the week</div>', unsafe_allow_html=True)
            mx = max((abs(r) for _, r, _ in dow), default=0) or 1.0
            dcells = []
            for name, r, _rng in dow:
                col = "#16A34A" if r >= 0 else "#DC2626"
                h = 4 + abs(r) / mx * 44
                dcells.append(
                    '<div style="display:flex;flex-direction:column;align-items:center;flex:1;gap:4px;'
                    'justify-content:flex-end;height:78px;">'
                    f'<div style="font-size:.7rem;color:{col};font-weight:700;">{r:+.2f}%</div>'
                    f'<div style="width:52%;height:{h:.0f}px;background:{col};border-radius:4px 4px 0 0;"></div>'
                    f'<div style="font-size:.8rem;color:#475569;font-weight:600;">{name}</div></div>')
            st.markdown('<div style="display:flex;align-items:flex-end;gap:10px;padding:10px 10px 8px;background:#fff;'
                        f'border:1px solid #E8ECF3;border-radius:12px;">{"".join(dcells)}</div>', unsafe_allow_html=True)
            best = max(dow, key=lambda x: x[1])
            worst = min(dow, key=lambda x: x[1])
            wild = max(dow, key=lambda x: x[2])
            st.caption(f"On average, **{best[0]}** has been its strongest day and **{worst[0]}** its weakest; "
                       f"**{wild[0]}** swings the most. A weak, average-over-a-year tendency — any single week can flip it.")

        # --- does the app's own signal work on this ticker? ---
        st.markdown('<div class="section-title">🧪 Does the app’s signal work on this ticker?</div>',
                    unsafe_allow_html=True)
        try:
            with st.spinner("Backtesting the intraday BUY/SELL rules on the last ~60 days…"):
                res = cached_backtest(ticker, "15m", True)
        except Exception:
            res = None
        if res and res.get("trades"):
            sc = st.columns(4)
            sc[0].metric("Strategy", f'{res["total_return"]:+.1f}%')
            sc[1].metric("Buy & hold", f'{res["buy_hold"]:+.1f}%')
            sc[2].metric("Win rate", f'{res["win_rate"]:.0f}%')
            sc[3].metric("Worst drop", f'{res["max_drawdown"]:.1f}%')
            beat = res["total_return"] - res["buy_hold"]
            verdict = (f"✅ Beat buy-&-hold by **{beat:.1f}%**" if beat > 0
                       else f"⚠️ Buy-&-hold did better (by **{-beat:.1f}%**)")
            st.caption(f"{verdict} over ~60 days on 15-min bars · {res['trades']} trades · {res['start']}–{res['end']}. "
                       "No fees included, and past results don’t guarantee future ones — it's a sanity check, not a promise.")
        else:
            st.caption("Not enough recent intraday data to backtest this ticker right now.")

        # --- cheat sheet (replaces the paragraphs) ---
        rules = [("🕘", "The first 15 minutes are wild — trade small."),
                 ("🌙", "Holding overnight is a gamble — most surprises happen then.")]
        if m and m.get("entry_tod") and m.get("exit_tod"):
            rules.append(("💲", f"Usually cheapest around {_hm(m['entry_tod'])}, priciest around {_hm(m['exit_tod'])}."))
        if m and m.get("persist") is not None:
            rules.append(("🔄" if m["persist"] < -0.03 else "📈" if m["persist"] > 0.03 else "🎲",
                          "Tends to bounce back — bank profits early." if m["persist"] < -0.03
                          else "Tends to keep trending — let winners run." if m["persist"] > 0.03
                          else "No clear bar-to-bar habit."))
        if b["ann_vol"] >= 60:
            rules.append(("🚫", "Don’t hold it for weeks — it slowly loses value."))
        rows = "".join(
            '<div style="display:flex;gap:10px;align-items:flex-start;padding:7px 0;border-top:1px solid #F1F5F9;">'
            f'<span style="font-size:1.1rem;line-height:1.4;">{ic}</span>'
            f'<span style="color:#334155;font-size:1.02rem;">{tx}</span></div>'
            for ic, tx in rules)
        st.markdown('<div class="lm-tile" style="padding:8px 16px 12px;">'
                    '<div class="lm-label" style="padding-top:6px;">✅ Cheat sheet</div>'
                    f'{rows}</div>', unsafe_allow_html=True)

        st.caption("📅 Based on the last year of trading. Markets change, so treat this as a helpful guide — not a promise.")


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
        meta = f"{_live_badge(lq)} · {lq.source} · {delta}"
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
            _realized = sum(risk.load_today()["trades"])
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


def _clamp(x, lo=3.0, hi=97.0):
    return max(lo, min(hi, x))


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
               f'<div class="lm-marker" style="left:{_clamp(50 + vd * 25):.0f}%;background:{col}"></div></div>')
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
               f'<div class="lm-marker" style="left:{_clamp(rsi):.0f}%;background:#0F172A"></div></div>')
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
               f'style="left:0;width:{_clamp(ap / 1.5 * 100, 0, 100):.0f}%;background:{pcol}"></div></div>')
        ratio = f' ({m["pace_ratio"]:.1f}× typical)' if m["pace_ratio"] else ""
        tiles.append(
            f'<div class="lm-tile"><div class="lm-label">Volatility · ATR {dtip("ATR (Average True Range) is how much price typically moves in one bar — your volatility gauge. Bigger = wilder swings, so you need a wider stop. The bar fills toward 1.5%; the label flags whether the latest bar moved faster or quieter than usual.")}</div>'
            f'<div class="lm-val">{ap:.2f}%<small>per bar</small></div>{bar}'
            f'<div class="lm-sub">{pace} pace{ratio}</div></div>')

    # Day range: where price sits between today's high and low.
    pos = m["pos_in_range"]
    where = "near highs" if pos > 0.7 else "near lows" if pos < 0.3 else "mid-range"
    chgcol = "#16A34A" if m["chg_pct"] >= 0 else "#DC2626"
    bar = (f'<div class="lm-track"><div class="lm-fill" style="left:0;width:{_clamp(pos*100,0,100):.0f}%;'
           f'background:#2563EB"></div><div class="lm-marker" '
           f'style="left:{_clamp(pos*100):.0f}%;background:#2563EB"></div></div>')
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


# --------------------------------------------------------------------------- #
# Layout
# --------------------------------------------------------------------------- #
st.markdown(
    '<div class="hero"><div class="hero-logo">📈</div>'
    '<div><h1>Stock Signal Advisor</h1></div></div>'
    '<div class="hero-sub">A disciplined, emotion-free second opinion — '
    'not a prediction, and not financial advice.</div>',
    unsafe_allow_html=True,
)

# Keys are read from .streamlit/secrets.toml. Set them there by hand, not through the UI.
try:
    API_KEY = st.secrets.get("FINNHUB_API_KEY", "")          # Finnhub: real-time price
    ALPACA_KEY = st.secrets.get("ALPACA_API_KEY", "")        # Alpaca: real-time intraday bars
    ALPACA_SECRET = st.secrets.get("ALPACA_SECRET_KEY", "")
except Exception:
    API_KEY = ALPACA_KEY = ALPACA_SECRET = ""

tab_intraday, tab_analyze, tab_watchlist, tab_know, tab_help = st.tabs(
    ["⚡ Intraday", "📊 Long-term", "📋 Watchlist", "🔬 Know your ticker", "ℹ️ How it works"])

with tab_intraday:
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
        day = risk.load_today()
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
                risk.record_trade(pnl_in)
                st.session_state.pop("log_pnl", None)
                st.session_state["risk_exp"] = True
                st.rerun()
        if lc3.button("Reset day", key="log_reset"):
            risk.reset_today()
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

with tab_analyze:
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

with tab_watchlist:
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

with tab_know:
    st.caption("Profile **any** stock's *risk character* before you trade it — measured from real history, "
               "not a forecast. It shows where the move actually happens (open / midday / close / overnight), "
               "how violent the stock is, and how often a day is just a straight line. Works for US tickers "
               "(`NVDA`, `TQQQ`) and Canadian/TSX names with a `.TO` suffix (`SHOP.TO`).")
    kt = st.text_input("Stock to profile", value="SOXL", label_visibility="collapsed",
                       key="know_ticker",
                       placeholder="Search any ticker…   e.g. NVDA, TQQQ, AAPL, SHOP.TO").strip().upper()
    if kt:
        render_behavior_panel(kt, wrap=False)
    else:
        st.info("Type a ticker above to see its volatility & overnight behaviour.")

with tab_help:
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

st.markdown(
    "<hr><div style='text-align:center;color:#94A3B8;font-size:12px;'>"
    "Stock Signal Advisor · prices via Finnhub & Yahoo Finance · not financial advice"
    "</div>", unsafe_allow_html=True,
)
