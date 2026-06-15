"""
Build a teaching PDF: "How We Built an Intraday Options Strategy (and What Went Wrong)"
A classroom companion documenting the real journey — design, build, and every issue faced.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    HRFlowable, ListFlowable, ListItem
)

# ── palette ────────────────────────────────────────────────────────────────
NAVY   = colors.HexColor("#1a2744")
BLUE   = colors.HexColor("#2c5aa0")
GREEN  = colors.HexColor("#1e7a4d")
RED    = colors.HexColor("#b3382c")
AMBER  = colors.HexColor("#b8860b")
GREY   = colors.HexColor("#555555")
LIGHT  = colors.HexColor("#eef2f8")
LIGHTA = colors.HexColor("#fff6e6")
LIGHTR = colors.HexColor("#fdecea")
LIGHTG = colors.HexColor("#e9f5ee")

styles = getSampleStyleSheet()
def S(name, **kw):
    styles.add(ParagraphStyle(name, parent=styles["Normal"], **kw))

S("Title2", fontName="Helvetica-Bold", fontSize=26, leading=31, textColor=NAVY, alignment=TA_CENTER, spaceAfter=6)
S("Sub", fontName="Helvetica", fontSize=13, leading=17, textColor=GREY, alignment=TA_CENTER, spaceAfter=4)
S("H1", fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=NAVY, spaceBefore=16, spaceAfter=7)
S("H2", fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=BLUE, spaceBefore=11, spaceAfter=5)
S("Body", fontName="Helvetica", fontSize=10.5, leading=15.5, textColor=colors.HexColor("#1a1a1a"), alignment=TA_JUSTIFY, spaceAfter=7)
S("BodyL", fontName="Helvetica", fontSize=10.5, leading=15.5, textColor=colors.HexColor("#1a1a1a"), spaceAfter=7)
S("BulletX", fontName="Helvetica", fontSize=10.5, leading=15, textColor=colors.HexColor("#1a1a1a"))
S("Mono", fontName="Courier", fontSize=9, leading=13, textColor=colors.HexColor("#222222"))
S("Caption", fontName="Helvetica-Oblique", fontSize=9, leading=12, textColor=GREY, spaceAfter=8)
S("CalloutH", fontName="Helvetica-Bold", fontSize=11, leading=14, spaceAfter=3)
S("CalloutB", fontName="Helvetica", fontSize=10, leading=14, textColor=colors.HexColor("#1a1a1a"))

def para(t, s="Body"): return Paragraph(t, styles[s])
def h1(t): return Paragraph(t, styles["H1"])
def h2(t): return Paragraph(t, styles["H2"])
def sp(h=6): return Spacer(1, h)

def bullets(items, style="BulletX"):
    return ListFlowable(
        [ListItem(Paragraph(i, styles[style]), leftIndent=8, value="•") for i in items],
        bulletType="bullet", start="•", leftIndent=14, spaceAfter=7)

def callout(title, body, bg, bar):
    inner = [Paragraph(title, styles["CalloutH"])]
    if body:
        inner.append(Paragraph(body, styles["CalloutB"]))
    t = Table([[inner]], colWidths=[165*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),bg),
        ("LINEBEFORE",(0,0),(0,-1),3,bar),
        ("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),
        ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),
    ]))
    return t

def issue(title, body):  return callout('<font color="#b3382c">ISSUE</font> &nbsp; ' + title, body, LIGHTR, RED)
def lesson(title, body): return callout('<font color="#1e7a4d">LESSON</font> &nbsp; ' + title, body, LIGHTG, GREEN)
def note(title, body):   return callout('<font color="#b8860b">NOTE</font> &nbsp; ' + title, body, LIGHTA, AMBER)

def dtable(data, colw, header=True):
    t = Table(data, colWidths=colw, repeatRows=1 if header else 0)
    st = [
        ("FONTNAME",(0,0),(-1,-1),"Helvetica"),
        ("FONTSIZE",(0,0),(-1,-1),9),
        ("TEXTCOLOR",(0,0),(-1,-1),colors.HexColor("#1a1a1a")),
        ("ALIGN",(1,0),(-1,-1),"CENTER"),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),
        ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#cfd8e6")),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, LIGHT]),
    ]
    if header:
        st += [("BACKGROUND",(0,0),(-1,0),NAVY),("TEXTCOLOR",(0,0),(-1,0),colors.white),
               ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("ALIGN",(0,0),(-1,0),"CENTER")]
    t.setStyle(TableStyle(st))
    return t

# ── header/footer ──────────────────────────────────────────────────────────
def deco(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8); canvas.setFillColor(GREY)
    canvas.drawString(20*mm, 12*mm, "Institutional Trader — Strategy Build Casebook")
    canvas.drawRightString(190*mm, 12*mm, f"Page {doc.page}")
    canvas.setStrokeColor(colors.HexColor("#cfd8e6")); canvas.setLineWidth(0.5)
    canvas.line(20*mm, 15*mm, 190*mm, 15*mm)
    canvas.restoreState()

story = []

# ── COVER ──────────────────────────────────────────────────────────────────
story += [sp(70)]
story.append(Paragraph("Building an Intraday Options Strategy", styles["Title2"]))
story.append(Paragraph("…and Everything That Went Wrong Along the Way", styles["Title2"]))
story += [sp(10)]
story.append(Paragraph("A teaching casebook on systematic trading: design, data, backtesting,<br/>and the hard, honest lessons of quant research.", styles["Sub"]))
story += [sp(24)]
story.append(HRFlowable(width="60%", thickness=1.2, color=BLUE, hAlign="CENTER"))
story += [sp(24)]
story.append(note("How to use this document",
    "This is the real story of building one NSE intraday options strategy end-to-end. "
    "Each chapter pairs <b>what we did</b> with the <b>issues we hit</b> and the <b>lesson</b> learned. "
    "The mistakes are the most valuable part — most quant courses only show the polished result. "
    "Educational use only. Nothing here is financial advice."))
story.append(PageBreak())

# ── 1. THE GOAL ────────────────────────────────────────────────────────────
story.append(h1("1.  The Goal — What We Set Out to Build"))
story.append(para(
    "We wanted a <b>systematic intraday strategy</b> for Indian markets (NSE) that a retail trader could "
    "run from a laptop. The brief: scan a universe of liquid stocks and the two big indices "
    "(NIFTY, BANKNIFTY) all day, score each one objectively, and only flag a trade when strict, "
    "pre-defined conditions are met — removing emotion and guesswork. Orders are placed "
    "<b>manually</b> in the broker app; the software only generates and tracks signals."))
story.append(para(
    "The design principle from day one was <b>discipline over prediction</b>: we cannot forecast the market, "
    "but we can control which setups we take, how much we risk, and when we exit. The whole project "
    "became an exercise in honestly testing whether the chosen setups actually have an edge."))
story.append(lesson("Define success before you build",
    "We fixed a 'go-live bar' upfront: a strategy must show a win rate and profit factor above a set "
    "threshold across a minimum number of trades before any real money is risked. Without a pre-committed "
    "bar, you will always find a story to justify trading."))

# ── 2. THE STRATEGY ────────────────────────────────────────────────────────
story.append(h1("2.  The Strategy — 3-Family Alpha Scoring"))
story.append(para(
    "Every stock is judged by seven small checks, grouped into <b>three independent families</b>. Each "
    "family votes LONG, SHORT, or NEUTRAL. We group rather than count seven separate votes because "
    "several checks (momentum, trend strength, volume-break) all move together in a real trend — counting "
    "them separately would fake 'breadth'."))
story.append(dtable([
    ["Family","What it measures","Weight"],
    ["TREND","Momentum + trend quality + opening-range breakout","0.65"],
    ["FLOW","Options positioning (PCR) + market regime (Nifty, VIX)","0.17"],
    ["EVENT","News headlines + corporate filings (experimental)","0.18"],
], [32*mm, 105*mm, 22*mm]))
story.append(sp(8))
story.append(para(
    "Each family produces a <b>z-score</b> (how unusual today's reading is). We blend them into one number, "
    "the <b>alpha-z</b>, as a weighted average. The sign is the direction; the size is the conviction."))
story.append(h2("The two gates"))
story.append(para("A stock becomes a trade only if it clears BOTH gates — two independent methods agreeing:"))
story.append(bullets([
    "<b>Gate 1 — Alpha:</b> |alpha-z| above 0.55 AND at least 2 of 3 families agree on direction.",
    "<b>Gate 2 — Confirmation:</b> a 5-minute opening-range breakout with a volume surge, same direction.",
]))
story.append(note("Why a 4th family was deleted",
    "We originally had a mean-reversion family. A 30-day backtest showed it won only 47.6% of the time — "
    "no edge. We removed it. A factor that does not win has no place in the system, no matter how clever it sounds."))
story.append(PageBreak())

# ── 3. ARCHITECTURE ────────────────────────────────────────────────────────
story.append(h1("3.  How the System Is Built"))
story.append(para("The software is organised into small, single-purpose modules so each piece can be tested alone:"))
story.append(dtable([
    ["Module","Job"],
    ["config.py","All tunable parameters in one place"],
    ["instruments.py","Map stock symbols to the broker's instrument keys"],
    ["data_fetcher.py","Live prices + historical candles from the broker API"],
    ["signals.py","The 3-family scoring and alpha-z maths"],
    ["options.py","Resolve the exact option contract (strike, expiry, premium)"],
    ["portfolio.py","Position sizing and instrument choice"],
    ["agent.py","The orchestrator — scans every 5 minutes"],
    ["trade_log.py","Records every signal and its outcome"],
    ["ui_terminal.py","The dashboard you watch"],
], [42*mm, 119*mm]))
story.append(sp(8))
story.append(para(
    "The app runs <b>locally</b> and is fully autonomous: the Mac wakes itself at 8:55 AM, the app launches "
    "at 9:00, scans during market hours, and force-closes any position at 3:10 PM. A separate copy of the "
    "code lives on GitHub purely as a backup."))
story.append(lesson("Separate the parts that can break",
    "Keeping data, signals, sizing, and UI in separate modules meant that when something failed — and it "
    "did, repeatedly — we could isolate and fix one piece without touching the rest."))

# ── 4. THE DATA JOURNEY ────────────────────────────────────────────────────
story.append(h1("4.  The Data Layer — Harder Than the Strategy"))
story.append(para(
    "Most beginners assume the 'strategy' is the hard part. In reality, <b>getting clean, fast, correctly-"
    "identified data</b> consumed more effort than the trading logic. We switched the data source from "
    "Yahoo Finance to the broker's API (Upstox) specifically to remove latency."))
story.append(issue("The API spoke a different language than we expected",
    "Our first attempts to fetch candles returned 404 and 400 errors. The broker had moved to a new API "
    "version (V3) with a completely different URL structure, AND it required <b>ISIN-based instrument keys</b> "
    "(e.g. NSE_EQ|INE467B01029) instead of human symbols (NSE_EQ|TCS). Three mismatches at once — endpoint, "
    "key format, and response parsing — all had to be fixed before a single price came through."))
story.append(lesson("Read the current API docs, don't assume",
    "We solved it by reading the live API documentation, then auto-downloading the broker's full instrument "
    "master (96,000+ instruments) and building a symbol-to-key lookup that refreshes weekly. Never assume the "
    "API behaves the way a tutorial from last year says it does."))
story.append(issue("Real-time streaming was not available",
    "We wanted WebSocket tick streaming for zero latency. The read-only data token returns HTTP 410 — that "
    "feature needs a paid trading token. We could not have it."))
story.append(lesson("Engineer within your real constraints",
    "Instead of streaming, we made REST polling fast: fetch all prices in ONE batched call (0.2s for 100 names "
    "instead of 18s one-by-one), cache daily history so it is fetched once per day, and run the scan on 12 "
    "parallel threads. Result: a full 97-instrument scan in a few seconds — fast enough that prices don't drift."))
story.append(PageBreak())

# ── 5. THE BIGGEST BUG ─────────────────────────────────────────────────────
story.append(h1("5.  The Bug That Made the Strategy Invisible"))
story.append(para(
    "This is the single most important lesson in the entire project. When we first ran a proper backtest to "
    "answer 'how many signals does this generate per day?', the answer was <b>zero — every day, forever.</b> "
    "The strategy looked alive on the dashboard but would never have fired a single trade."))
story.append(para("The cause was one line of maths. To turn a raw reading into a z-score, the code did:"))
story.append(callout("", "<font name='Courier'>momentum_z = stats.zscore([momentum_value])</font>", LIGHT, GREY))
story.append(para(
    "A z-score measures how far a value sits from the average of <b>a distribution</b>. But we passed it a "
    "<b>single number</b>. The z-score of one number is mathematically undefined — the function returned "
    "<font name='Courier'>nan</font> ('not a number') every time. That nan poisoned the whole calculation, "
    "so the alpha-z was always nan, so no stock ever passed Gate 1."))
story.append(issue("A silent failure that looked like success",
    "Nothing crashed. No error appeared. The dashboard scanned, the lights blinked, everything 'worked' — "
    "it just silently produced no trades. Had we trusted the polished UI, we'd have paper-traded a dead "
    "system for a month and concluded 'the market gave no signals'."))
story.append(lesson("Test the OUTPUT, not the appearance",
    "We only caught it because we asked a blunt quantitative question ('how many signals in 30 days?') and "
    "got a suspicious answer (zero). The fix was to z-score each factor against its own ROLLING HISTORY "
    "(a real distribution), not a single point. Always verify a system produces the outputs you expect — "
    "a clean interface proves nothing."))

# ── 6. THE WIN-RATE ILLUSION ───────────────────────────────────────────────
story.append(h1("6.  The Win-Rate Illusion"))
story.append(para(
    "Once signals fired, an early backtest showed a tempting <b>45% win rate</b>... that LOST money. Later we "
    "found a setting that showed <b>80%+</b> — also a trap. Understanding why is the heart of trading maths."))
story.append(para(
    "Win rate alone is meaningless without the <b>reward-to-risk ratio</b>. You can manufacture almost any "
    "win rate by choosing how far apart the target and stop sit:"))
story.append(dtable([
    ["Setup","Win rate","Reality"],
    ["Tiny target, huge stop","80–90%","Each rare loss erases ~10 wins — loses money"],
    ["Huge target, tiny stop","20–30%","Wins are big but rare — can still make money"],
    ["Balanced 2:1","~33% breakeven","Needs a genuine edge to profit"],
], [50*mm, 28*mm, 83*mm]))
story.append(sp(8))
story.append(note("The breakeven formula every student must know",
    "With a reward-to-risk of R:1, you break even at a win rate of 1 / (1 + R). At 2:1, that's 33%. So a "
    "'34% win rate' at 2:1 is NOT skill — it is exactly what random entries produce. A high win rate with a "
    "bad reward-to-risk is the most common way beginners fool themselves."))
story.append(lesson("Judge a system by EXPECTANCY, not win rate",
    "Expectancy = (Win% × average win) − (Loss% × average loss). A 45% system with 2.5:1 reward beats a 60% "
    "system with 1:1. We learned to always report win rate, reward-to-risk, AND expectancy together."))
story.append(PageBreak())

# ── 7. OPTIONS ─────────────────────────────────────────────────────────────
story.append(h1("7.  Why We Moved to Buying Options"))
story.append(para(
    "Testing on the underlying stock showed almost no directional edge at a sane 2:1 reward-to-risk — about a "
    "30% win rate, which is the random baseline. A 5% intraday move in a stock is rare, so targets were hard "
    "to reach. We switched to <b>buying options</b> (CALL for bullish, PUT for bearish — never selling)."))
story.append(para(
    "The key insight: with an option you exit on the <b>option premium</b>, not the stock price. Because of "
    "leverage, a small move in the stock can swing the premium 10%+, so a modest, achievable target becomes "
    "meaningful. Indices (NIFTY, BANKNIFTY) were added because their options need little capital "
    "(~Rs 12,000 and ~Rs 28,000 per lot)."))
story.append(issue("We could only backtest options on recent data",
    "Historical option backtesting needs the premium history of the exact contract that was at-the-money on "
    "each past day. Expired contracts are removed from the free instrument master, and the broker's "
    "expired-data API requires a paid plan (our token got a 401). So we could only test the most recent "
    "~30 days of option premium — a real, unavoidable limit on how far back the options study could go."))
story.append(h2("Tuning the option trade — every lever tested"))
story.append(para("We then methodically swept every parameter on the recent option data:"))
story.append(dtable([
    ["Lever","What we tested","Best choice"],
    ["Exit","Premium target/stop combos","+10% target / −20% stop"],
    ["Strike","ITM-2 to OTM+2","OTM+1 (one strike out)"],
    ["Cutoff","1:00 / 1:30 / 2:00 / 3:00 PM","1:00 PM"],
    ["Time window","9:45 AM to 1:00 PM buckets","12:30–1:00 PM strongest"],
], [26*mm, 70*mm, 65*mm]))
story.append(sp(8))
story.append(note("A counter-intuitive finding on stops",
    "A WIDER stop gave a HIGHER win rate. Option premiums are noisy; a tight 5% stop gets hit by random "
    "wiggles before the +10% target is reached. The 20% stop let trades breathe — 88% win in one sample vs "
    "50% with a 5% stop. The 'safe-sounding' tight stop was actually worse."))

# ── 8. THE OVERFITTING TRAP ────────────────────────────────────────────────
story.append(h1("8.  The Overfitting Trap"))
story.append(para(
    "At one point the request was: 'take all the winning trades and design signals that match them, to get "
    "a 70%+ win rate.' This is the single most dangerous idea in quant trading, and worth dwelling on."))
story.append(issue("Fitting rules to past winners is cheating yourself",
    "If you look at which trades won and then write rules that select exactly those, you can show ANY win "
    "rate on history — 90%, even 100%. But you have fitted to noise, not signal. Live, it collapses, because "
    "the future's winners are different from the past's."))
story.append(lesson("Always validate out-of-sample",
    "We split the data: find the pattern on the first 60% of days (the 'learn' set), then test it on the last "
    "40% it had never seen (the 'prove' set). If a high win rate survives on unseen data, it might be real. "
    "If it collapses, it was overfitting. This train/test discipline is non-negotiable."))
story.append(note("The student who chose wisely",
    "Late in the project, a backtest suggested a narrow 12:30–1:00 PM window hit 77% vs 72% for the wider "
    "window. The right call was made: KEEP the wider window, because the 5-point gain rested on only 13 "
    "trades — well inside the noise band. Resisting a tempting-but-fragile number is exactly the discipline "
    "this whole project teaches."))
story.append(PageBreak())

# ── 9. SAMPLE SIZE ─────────────────────────────────────────────────────────
story.append(h1("9.  The Sample-Size Problem That Never Went Away"))
story.append(para(
    "Across dozens of backtests, one issue dominated every conclusion: <b>too few trades.</b> A selective "
    "intraday strategy with a 1 PM cutoff produces only about 14 signals a month, clustered on ~8 of 22 "
    "trading days. Most days are blank."))
story.append(para(
    "This means every shiny number — 72%, 77%, 88% — rested on 13 to 34 trades. At those sizes, a couple of "
    "different outcomes flips the win rate by 10+ points. We watched the 'same' setup read 77% on 13 trades "
    "and 50% on 14 trades from an overlapping window. Both were 'true'; both were noise."))
story.append(dtable([
    ["Backtest","Trades","Reported win rate","Trustworthy?"],
    ["20-day options","13","77%","No — too few"],
    ["30-day options","14","50–64%","No — too few"],
    ["120-day underlying","379","~30% at 2:1","Yes — but no edge"],
], [55*mm, 22*mm, 45*mm, 39*mm]))
story.append(sp(8))
story.append(lesson("A number from 15 trades is a guess, not a result",
    "Statistical confidence needs samples — ideally 100+ trades. Below that, treat every win rate as a "
    "hypothesis. The honest response to a thin sample is not to pick the prettiest number, but to say "
    "'we don't know yet' and go collect more data."))

# ── 10. THE COSTS REALITY ──────────────────────────────────────────────────
story.append(h1("10.  Costs — The Silent Edge-Killer"))
story.append(para(
    "Several setups showed a small positive 'gross' expectancy of about +0.06% per trade. Then we modelled "
    "real costs: brokerage, STT, exchange fees, GST, and stamp duty total roughly 0.10% round-trip for "
    "intraday equity."))
story.append(callout("The maths that ends many strategies",
    "Gross edge per trade: +0.06%  &nbsp;&nbsp;|&nbsp;&nbsp;  Round-trip cost: −0.10%  &nbsp;&nbsp;gives&nbsp;&nbsp;  "
    "<b>Net: −0.04% — a loss.</b>", LIGHTR, RED))
story.append(para(
    "To get a high win rate you needed a tiny target (0.2–0.3%), but a tiny target is smaller than the cost "
    "of trading. The edge existed on paper and was eaten entirely by friction. This is why options, with "
    "their larger percentage moves, were the only place the maths could even potentially work."))
story.append(lesson("Always subtract costs BEFORE celebrating",
    "A backtest that ignores brokerage and taxes is a fantasy. The first thing to do with any positive result "
    "is subtract realistic round-trip costs. Many 'profitable' retail strategies are break-even or losing once "
    "friction is honest."))

# ── 11. HONEST VERDICT ─────────────────────────────────────────────────────
story.append(h1("11.  The Honest Verdict"))
story.append(para(
    "After testing every lever — strike, target, stop, cutoff, entry-time, instrument — on real Upstox data, "
    "the conclusion was disciplined and unglamorous:"))
story.append(bullets([
    "The entry signals show <b>no proven directional edge</b> at a sane reward-to-risk.",
    "High win rates appeared only on samples too small to trust, or vanished after costs.",
    "The buy-option version (OTM+1, +10%/−20%, 1 PM) looked promising (~72%) but on just 18 trades.",
    "Nothing here is yet a proven money-maker — and we wrote that plainly into the dashboard itself.",
]))
story.append(note("The only honest next step",
    "No backtest can settle it, because of the sample-size and cost limits. The real test is FORWARD: run the "
    "system live in paper mode, let it record 30+ real option outcomes with real fills and costs over the "
    "coming weeks, and only then judge whether the edge is real. Forward evidence cannot be curve-fitted."))
story.append(lesson("The most professional outcome is sometimes 'not proven'",
    "It would have been easy to tune numbers until a backtest sparkled and call it a winner. Refusing to do "
    "that — and saying clearly 'the edge is unproven, here is exactly why' — is the real mark of quantitative "
    "maturity. Protecting capital from a false positive is worth more than any backtest."))
story.append(PageBreak())

# ── 12. PERFORMANCE / SPEED ────────────────────────────────────────────────
story.append(h1("12.  Performance — How Fast Is a Scan?"))
story.append(para(
    "A common student question: if the system scans 95 stocks every five minutes, is it fast enough that "
    "prices don't move before you act? We measured every step. The answer reveals where the real cost lies — "
    "and it is NOT the strategy maths."))
story.append(h2("Per-stock timings (measured)"))
story.append(dtable([
    ["Step","What happens","Time","Type"],
    ["2","Fetch the stock's 5-min candles","~440 ms","Network"],
    ["-","Daily history (cached after 1st fetch)","~0 ms","Memory"],
    ["3-4","Score 3 families + compute alpha-z","1.4 ms","CPU"],
    ["5","Gate 1 (alpha check)","~0 ms","CPU"],
    ["6","Gate 2 (opening-range breakout + volume)","0.2 ms","CPU"],
    ["7","Choose instrument (CALL / PUT)","~0 ms","CPU"],
], [14*mm, 75*mm, 26*mm, 24*mm]))
story.append(sp(6))
story.append(callout("The decision is instant; the data is the cost",
    "Steps 3-7 — the entire 'brain' of the strategy (scoring, both gates, instrument choice) — take about "
    "<b>1.6 milliseconds</b> per stock. More than 99% of the time is just the network waiting for the broker "
    "to return candles (~440 ms). The maths is effectively free.", LIGHTA, AMBER))
story.append(h2("Scanning all 95 stocks + 2 indices"))
story.append(dtable([
    ["Approach","Time taken"],
    ["One stock at a time (naive)","~43 seconds"],
    ["12 parallel threads + daily cache + batched prices","~3-4 seconds"],
    ["First scan of the day (one-time cache warm-up)","~6-7 seconds"],
], [105*mm, 50*mm]))
story.append(sp(8))
story.append(lesson("Optimise the bottleneck, not the obvious part",
    "A beginner might try to speed up the 'algorithm'. But the algorithm was already 1.6 ms — invisible. All "
    "the engineering effort went into the NETWORK: running fetches in parallel, caching data that does not "
    "change during the day, and asking for all live prices in a single batched request. A 3-4 second scan "
    "inside a 5-minute window means a signal is seen almost the instant a candle closes, so prices barely "
    "drift before the order appears. Lesson: profile first, then optimise what actually dominates."))
story.append(note("A note on breakeven and the go-live bar",
    "Because the option exit is +10% target / -20% stop, you risk 20% to make 10%. The breakeven win rate is "
    "therefore 20 / (10 + 20) = about 67%. That is why the go-live bar is set to 70% (a margin above "
    "breakeven), not the generic 52% you might see elsewhere — at 52% with this payoff you would steadily "
    "lose money. Always derive your required win rate from your actual reward-to-risk."))
story.append(PageBreak())

# ── 13. LESSONS SUMMARY ────────────────────────────────────────────────────
story.append(h1("13.  Ten Lessons to Take Away"))
lessons = [
    ("Version-control everything from day one.", "The original code was lost because it lived untracked inside another project's folder. We rebuilt it and gave it its own git repository plus an off-site backup. Never trust a single copy."),
    ("A clean dashboard proves nothing.", "The biggest bug produced zero trades while looking perfectly alive. Test outputs, not appearances."),
    ("Win rate without reward-to-risk is meaningless.", "Judge by expectancy. Know that 1/(1+R) is your breakeven win rate."),
    ("A wide stop can beat a tight stop.", "In noisy instruments, tight stops get shaken out. Test, don't assume."),
    ("Never fit rules to past winners.", "Always validate on out-of-sample data you have not looked at."),
    ("Small samples lie.", "Below ~100 trades, a win rate is a hypothesis, not a result."),
    ("Subtract costs before celebrating.", "Brokerage and taxes kill thin edges. Model them first."),
    ("Know your data's limits.", "We could not backtest expired options or stream ticks — and we said so, rather than pretending."),
    ("Engineer within real constraints.", "Batching, caching, and parallelism gave near-real-time speed on a read-only token."),
    ("'Not proven' is a valid, professional answer.", "The forward paper-test is the only honest judge. Protect capital first."),
]
rows = [["#","Lesson","Why it matters"]]
for i,(a,b) in enumerate(lessons,1):
    rows.append([str(i), Paragraph("<b>"+a+"</b>", styles["BulletX"]), Paragraph(b, styles["BulletX"])])
t = Table(rows, colWidths=[8*mm, 58*mm, 95*mm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,0),NAVY),("TEXTCOLOR",(0,0),(-1,0),colors.white),
    ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,0),10),
    ("ALIGN",(0,0),(0,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"TOP"),
    ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#cfd8e6")),
    ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, LIGHT]),
    ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
    ("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),
]))
story.append(t)

# ── APPENDIX: BACKTEST RESULT TABLES ───────────────────────────────────────
story.append(PageBreak())
story.append(h1("Appendix — The Backtest Result Tables"))
story.append(para(
    "These are the actual numbers behind the lessons, on real Upstox data. Read them with the "
    "sample-size warning from Chapter 9 in mind: most rows rest on 13–34 trades and exclude transaction "
    "costs, so they show <b>direction and relative differences</b>, not bankable absolute returns."))

story.append(h2("A1.  Underlying direction at 2:1 reward-to-risk (120 days, 379 trades)"))
story.append(para(
    "The largest, most trustworthy sample. At a sane 2:1 reward-to-risk, the best win rate was only 34% — "
    "and breakeven for 2:1 is 33%. Conclusion: <b>no directional edge.</b>"))
story.append(dtable([
    ["Conviction / cutoff","Target / stop","Trades","Win rate","Verdict"],
    ["alpha >= 0.75, 1 PM","1% / 0.5%","59","34%","~breakeven"],
    ["alpha >= 0.55, 1 PM","1% / 0.5%","75","31%","below breakeven"],
    ["alpha >= 0.55, 3 PM","0.5% / 0.25%","379","28%","random baseline"],
], [50*mm, 30*mm, 20*mm, 24*mm, 37*mm]))

story.append(h2("A2.  Buying options — premium exit sweep (recent 20 days)"))
story.append(para(
    "Switching to options changes the picture: a small target with a wide stop wins often because premiums "
    "are volatile. Note how a tighter stop LOWERS the win rate."))
story.append(dtable([
    ["Premium target","Premium stop","Trades","Win rate","Expectancy"],
    ["+10%","-20%","13","77%","+3.74%/trade"],
    ["+10%","-10%","8","75%","+4.62%/trade"],
    ["+10%","-5%","8","50%","+2.12%/trade"],
    ["+15%","-20%","13","69%","+2.21%/trade"],
    ["+20%","-20%","13","62%","-0.10%/trade"],
], [30*mm, 28*mm, 20*mm, 24*mm, 36*mm]))

story.append(PageBreak())
story.append(h2("A3.  Strike comparison — ITM vs ATM vs OTM (30 days, +10% / -20%)"))
story.append(para(
    "Why we chose OTM+1 over the at-the-money default. Note the jagged, non-monotonic win column — a "
    "fingerprint of small-sample noise, which is why this was treated as suggestive, not conclusive."))
story.append(dtable([
    ["Strike","Trades","Win rate","Expectancy","Net"],
    ["ITM-2 (deep in-money)","16","81%","+3.81%","+61.0%"],
    ["ITM-1","19","63%","+2.68%","+51.0%"],
    ["ATM (old default)","14","71%","+3.47%","+48.6%"],
    ["OTM+1  (chosen)","18","72%","+4.51%","+81.2%"],
    ["OTM+2","15","73%","+2.83%","+42.4%"],
], [48*mm, 22*mm, 24*mm, 28*mm, 28*mm]))

story.append(h2("A4.  Entry cutoff — frequency vs quality (30 days, OTM+1)"))
story.append(para(
    "Trading later in the day gives MORE signals but WORSE ones. The win rate falls off a cliff right after "
    "1 PM, so 1 PM was kept despite the lower signal count."))
story.append(dtable([
    ["Cutoff","Signals","Signals/day","Win rate","Expectancy"],
    ["1:00 PM","18","0.8","72%","+4.51%"],
    ["1:30 PM","30","1.4","60%","+1.63%"],
    ["2:00 PM","34","1.5","62%","+1.88%"],
    ["3:00 PM","65","3.0","58%","+1.59%"],
], [30*mm, 24*mm, 28*mm, 24*mm, 30*mm]))

story.append(h2("A5.  Entry-time window — when do the winners happen?"))
story.append(para(
    "A surprise: the strategy produces NOTHING before 11:30 AM (the scores need an hour of intraday data). "
    "Signals cluster 12:30-1 PM, which is also the strongest window."))
story.append(dtable([
    ["Window","Trades","Win rate (+10%/-20%)"],
    ["09:45 - 10:30","0","no signals"],
    ["10:30 - 11:30","0","no signals"],
    ["11:30 - 12:30","5","60%"],
    ["12:30 - 1:00 PM","13","77%  (strongest)"],
], [50*mm, 26*mm, 60*mm]))
story.append(sp(8))
story.append(note("How to read these tables in class",
    "Every table tells a real story, but the absolute win rates are fragile (small samples, no costs). The "
    "durable lessons are the RELATIVE patterns: wider stops beat tighter ones, OTM beats ATM here, earlier "
    "cutoffs beat later ones, and a bigger sample (A1) erased the edge that small samples (A2-A5) suggested. "
    "That tension between small-sample hope and large-sample reality is the lesson."))

story.append(sp(14))
story.append(HRFlowable(width="100%", thickness=0.8, color=BLUE))
story.append(sp(6))
story.append(Paragraph(
    "Institutional Trader — Strategy Build Casebook &nbsp;|&nbsp; For classroom and educational use only. "
    "Not investment advice. Markets carry risk of loss.", styles["Caption"]))

# ── build ──────────────────────────────────────────────────────────────────
out = "/Users/sayali/files/institutional-trader/How_We_Built_The_Strategy.pdf"
doc = SimpleDocTemplate(out, pagesize=A4,
    leftMargin=20*mm, rightMargin=20*mm, topMargin=18*mm, bottomMargin=18*mm,
    title="How We Built an Intraday Options Strategy", author="Institutional Trader")
doc.build(story, onFirstPage=lambda c,d: None, onLaterPages=deco)
print("PDF written:", out)
