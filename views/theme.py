"""Colors, verdict icons and the page CSS."""

# --------------------------------------------------------------------------- #
# Look & feel
# --------------------------------------------------------------------------- #
VERDICT_EMOJI = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡", "WAIT": "⏸️"}


LADDER_ICON = {"res": "▲", "vwap": "·", "now": "●", "sup": "▼"}


# Banner colour by full headline, matching the "6 verdicts" key badges exactly.
VERDICT_CLASS = {"Strong BUY": "vk-sbuy", "BUY": "vk-buy", "HOLD": "vk-hold",
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
