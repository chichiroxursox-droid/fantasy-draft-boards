#!/usr/bin/env python3
"""Build the illustrated how-to guide as ONE self-contained HTML file (screenshots embedded).
Run tools/make_guide.cjs first to capture the shots.

Usage: python3 tools/build_guide.py  ->  GCCFFL-how-to-use.html
"""
import base64
import io
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / ".tmp" / "guide"
OUT = ROOT / "GCCFFL-how-to-use.html"
MAXW = 1500  # plenty for a full-width figure, keeps the file emailable


def img(name, width=None):
    src = SHOTS / f"{name}.png"
    if not src.exists():
        return f"<p style='color:#b00'>[missing screenshot: {name}]</p>"
    im = Image.open(src).convert("RGB")
    w = width or MAXW
    if im.width > w:
        im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82, optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f'<img src="data:image/jpeg;base64,{b64}" alt="{name}">'


STEPS = f"""
<h2 id="what">What this is</h2>
<p>A scoreboard for the auction. It knows what every player is worth <em>in our league</em> (15 teams,
$200 each, our exact roster), tracks what all 15 teams have spent and how many slots they have left, and
re-prices everyone live as money leaves the room. You type in each sale as the auctioneer calls it; it does the rest.</p>
<p class="callout"><b>It needs no internet.</b> Everything is already inside the file. Open it on a plane, in a
basement, on airport wifi — identical behavior.</p>

<h2 id="open">1. Open it</h2>
<p>Double-click <code>GCCFFL-auction-board.html</code>. That's the whole install. It opens in your normal browser.</p>
<p class="note">Your progress is saved in <em>your</em> browser automatically. If you close the tab by accident,
reopen the same file and everything is still there.</p>
{img("01-board")}

<h2 id="dashboard">2. The five numbers across the top</h2>
{img("02-topbar")}
<table>
<tr><th>Room +8% 🔥</th><td><b>How hot the room is.</b> What everyone has actually paid versus what those players
are worth on the sheet. Positive means the room is overpaying — you'll have to pay up to win anyone, but that money
is leaving for good. Negative (🧊) means bargains are being had and you should be patient.</td></tr>
<tr><th>Ahead ×0.98</th><td><b>What's still to come.</b> Remaining cash divided by remaining player value.
Below 1.00 means everything left is about to get cheaper than the sheet says. This is the number that scales
every price you see.</td></tr>
<tr><th>ME: $200 left · max bid $189</th><td>Your money, and the most you can bid right now while still
leaving $1 for each empty roster spot. <b>Never bid above your max</b> — the app won't let you strand yourself.</td></tr>
<tr><th>7 can outbid · 0 broke</th><td>How many rivals can still beat your best bid, and how many are out of money.
When "can outbid" hits 0, everyone left is yours at a dollar over.</td></tr>
<tr><th>🎤 Nominate: …</th><td>Who to put up when it's your turn. Covered below.</td></tr>
</table>

<h2 id="sale">3. Recording a sale (the thing you do 180 times)</h2>
<p>Player gets nominated → <b>type 3–4 letters of the name</b> → press <b>Enter</b>. The card opens:</p>
{img("03-salecard")}
<p>Read the four money numbers left to right:</p>
<ul>
<li><b>Base</b> — what he's worth on our sheet.</li>
<li><b>Now</b> — what he's worth <em>right now</em>, adjusted for how the room's money has drained.</li>
<li><b>Bid to</b> — <b>the number to actually follow.</b> Now-price, adjusted for the teams we like and don't,
and capped by what you can afford. Bid to this. Stop above it.</li>
<li><b>My max</b> — the absolute ceiling.</li>
</ul>
<p>It also tells you which teams can still outbid you, which roster slot he'd fill, and whether he's the last
good one at his position tier.</p>
<p>When the hammer falls: <b>type the price → Enter → the buyer → Enter</b>. Done, about five keystrokes.</p>
{img("04-buyer")}
<p>For the buyer you can type the <b>team number</b> (1–15), enough of their <b>name</b> to be unique,
<b>m</b> for us, or <b>u</b> if you didn't catch who won. Or just click their button. If a name is ambiguous
it says so instead of guessing.</p>
<p class="note">Not sold / nomination withdrawn? Press <b>Esc</b>.</p>

<h2 id="news">4. Injury and news flags</h2>
<p>Players with something going on show a colored note right on the card — researched the day before the draft,
with sources. 💡 green means the room is likely to overreact and you can buy the dip; ⚠ red means real missed
games; • yellow is minor, just be aware.</p>
{img("11-news")}

<h2 id="nominate">5. When it's YOUR turn to nominate</h2>
<p>The gold button always shows the top target. Click it for the full list and the reasoning:</p>
{img("07-nominate")}
<p><b>The strategy:</b> nominate players <em>you don't want</em> while everyone still has money, so their cash
gets spent on someone else's roster. Cowboys and Patriots are at the top of that list because we won't own
them at any price. Our own targets (Eagles, Steelers) are deliberately kept <em>off</em> the list — never put
your own guy up while the room is rich.</p>
<p>Late in the draft, when your max bid gets small, the button flips to <b>$1 target</b> and starts naming
players you can actually win for a dollar.</p>

<h2 id="fix">6. Fixing a mistake</h2>
<p>Wrong price? Wrong buyer? <b>Click that sale in "Last sales"</b> on the right. Change it and Save, or
Delete it entirely. All 15 budgets recalculate instantly.</p>
{img("09-fix")}
<p><b>Cmd+Z</b> (Ctrl+Z on Windows) undoes whatever you last did — a sale, an edit, a delete, even a whole
bulk import.</p>

<h2 id="catchup">7. Showing up late, or missing a run of sales</h2>
<p>Click <b>⏱ Catch up</b> and type one line per sale: <code>player price buyer</code>. Buyer can be a number,
a name, or left off entirely if you don't know it.</p>
{img("08-catchup")}
<p>It shows you exactly what it will do before you commit. Green ✓ lines get added; anything ambiguous or
misspelled is flagged and skipped rather than guessed at. <b>In an auction the order doesn't matter</b>, so
once these are in, every recommendation is fully accurate again.</p>

<h2 id="panel">8. The right-hand panel</h2>
{img("06-rightpanel", 620)}
<p><b>My roster</b> fills in automatically — a receiver goes to WR, then W/T, then the flex, then the bench,
in the order that keeps the most options open. <b>Teams</b> shows every rival's money left, max bid, and open
slots — that's how you know who can actually fight you. <b>Last sales</b> is your click-to-fix history.</p>

<h2 id="setup">9. Settings (rarely needed)</h2>
{img("10-setup")}
<p>Team names are pre-loaded from the league email. If someone is missing, click <b>✕</b>; if someone new turns up,
click <b>+ Add team</b>. Money in the room recalculates immediately. <b>"Slots I'll leave empty"</b> raises your
max bid if you plan to fill spots later with free-agency money instead.</p>

<h2 id="cheat">Cheat sheet</h2>
<table class="keys">
<tr><th>type a name → Enter</th><td>open the player</td></tr>
<tr><th>price → Enter → buyer → Enter</th><td>record the sale</td></tr>
<tr><th>Esc</th><td>close / not sold</td></tr>
<tr><th>Cmd+Z</th><td>undo the last thing</td></tr>
<tr><th>click a sale in Last sales</th><td>fix or delete it</td></tr>
<tr><th>m / u / 1–15</th><td>buyer = us / unknown / team number</td></tr>
</table>

<h2 id="rules">The rules that shaped the numbers</h2>
<p>From the official Yahoo settings export:</p>
<ul>
<li><b>0.6 points per reception</b> — not the standard 0.5 or 1.0, so the values use a custom blend.</li>
<li><b>Only one required RB but up to four receivers</b> — this makes running backs cheaper and receivers
dearer here than on any off-the-shelf sheet. That gap is our edge.</li>
<li><b>Return yards score</b> (1 point per 25) — a full-time kick returner quietly adds 2–3 points a game and
no ranking accounts for it. Good tiebreaker on $1 bench guys.</li>
<li><b>Kickers are nerfed and 5-point passing TDs</b> — $1 kicker at the very end, always; elite QBs are worth
a bit more than usual, sack-prone ones less.</li>
</ul>
"""

HTML = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GCCFFL Auction Board — how to use it</title>
<style>
 :root {{ --ink:#12161c; --dim:#5d6673; --line:#e2e6ec; --accent:#1f6feb; --gold:#8a6d1f; --bg:#fff; }}
 * {{ box-sizing:border-box; }}
 body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.65 -apple-system,"SF Pro Text",Segoe UI,Roboto,sans-serif; }}
 .wrap {{ max-width:900px; margin:0 auto; padding:38px 22px 90px; }}
 h1 {{ font-size:30px; line-height:1.2; margin:0 0 6px; letter-spacing:-.02em; }}
 .sub {{ color:var(--dim); margin:0 0 26px; font-size:15px; }}
 h2 {{ font-size:20px; margin:40px 0 12px; padding-top:14px; border-top:1px solid var(--line); letter-spacing:-.01em; }}
 p {{ margin:10px 0; }}
 ul {{ margin:10px 0; padding-left:22px; }} li {{ margin:5px 0; }}
 img {{ width:100%; border:1px solid var(--line); border-radius:9px; margin:14px 0; display:block; }}
 code {{ background:#f2f4f7; padding:1.5px 5px; border-radius:4px; font:13.5px ui-monospace,Menlo,monospace; }}
 table {{ border-collapse:collapse; width:100%; margin:14px 0; }}
 th,td {{ text-align:left; vertical-align:top; padding:9px 12px; border-bottom:1px solid var(--line); font-size:14.5px; }}
 th {{ width:220px; font-weight:600; white-space:nowrap; }}
 table.keys th {{ font:13.5px ui-monospace,Menlo,monospace; font-weight:600; width:250px; }}
 .callout {{ background:#eef5ff; border-left:3px solid var(--accent); padding:11px 14px; border-radius:0 7px 7px 0; }}
 .note {{ color:var(--dim); font-size:14.5px; }}
 .toc {{ background:#f7f9fb; border:1px solid var(--line); border-radius:9px; padding:14px 18px; }}
 .toc a {{ color:var(--accent); text-decoration:none; }} .toc a:hover {{ text-decoration:underline; }}
 .toc ol {{ margin:6px 0 0; padding-left:20px; }} .toc li {{ margin:3px 0; }}
 @media (prefers-color-scheme:dark) {{
   :root {{ --ink:#e6ebf2; --dim:#95a0af; --line:#2a3341; --bg:#11151b; --accent:#5aa2e8; }}
   code {{ background:#1c232e; }} .callout {{ background:#16202e; }} .toc {{ background:#161b23; }}
 }}
 @media print {{ h2 {{ page-break-after:avoid; }} img {{ page-break-inside:avoid; }} }}
</style></head><body><div class="wrap">
<h1>GCCFFL Auction Board</h1>
<p class="sub">How to use it — Sunday Aug 30, 2026 · 15 teams · $200 each · live auction, entered by hand</p>
<div class="toc"><b>Contents</b><ol>
<li><a href="#open">Open it</a></li><li><a href="#dashboard">The numbers up top</a></li>
<li><a href="#sale">Recording a sale</a></li><li><a href="#news">Injury flags</a></li>
<li><a href="#nominate">Your turn to nominate</a></li><li><a href="#fix">Fixing mistakes</a></li>
<li><a href="#catchup">Catching up</a></li><li><a href="#panel">The right panel</a></li>
<li><a href="#setup">Settings</a></li><li><a href="#cheat">Cheat sheet</a></li>
</ol></div>
{STEPS}
</div></body></html>"""

OUT.write_text(HTML)
print(f"wrote {OUT.name} — {OUT.stat().st_size/1e6:.1f} MB")
