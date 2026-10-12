"""The Know your ticker tab: a measured risk profile from daily and 15-minute bars."""

import contextlib

import streamlit as st

from views.data import cached_backtest, cached_behavior_stats, cached_microstructure
from views.shared import clamp


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
            posm = clamp(b["pos52"], 2, 98)
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
            w = clamp(m["open_ratio"] / 3 * 100, 0, 100)
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
            f'<div class="lm-track"><div class="lm-fill" style="left:0;width:{clamp(b["overnight_var_share"], 0, 100):.0f}%;background:#7C3AED"></div></div>'
            f'<div class="lm-sub">Lots happens while the market is shut. A bad night can drop it <b>{b["gap_worst"]:.0f}%</b> before you can react.</div></div>')
        flat_one_in = max(1, round(100 / b["flat_pct"])) if b["flat_pct"] else 0
        tiles.append(
            '<div class="lm-tile"><div class="lm-label">➖ Quiet days</div>'
            f'<div class="lm-val">1 in {flat_one_in}</div>'
            f'<div class="lm-track"><div class="lm-fill" style="left:0;width:{clamp(b["flat_pct"] * 3, 0, 100):.0f}%;background:#2563EB"></div></div>'
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


def render():
    """Render the Know your ticker tab."""
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
