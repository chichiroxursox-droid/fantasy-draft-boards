# Draft Day — Runbook & Strategy Brief

**Objective:** win the draft. League **"GCC YG"** — ESPN, 12-team snake, **full PPR**, **Sat Aug 9 2026 @ 1:00 PM EDT**, 90 s per pick, redraft (no keepers). Roster: QB·2RB·2WR·TE·FLEX·K·D/ST + 7 bench = **16 rounds** (the IR slot is not drafted). The board's defaults already match all of this — the only thing to enter is your slot.

## Draft-day timeline
1. **Morning:** `python3 tools/fetch_data.py` — refresh rankings/ADP/ESPN ranks (overnight news moves values)
2. `python3 tools/serve.py` — leave running, open **http://localhost:8712/draft.html**
3. `python3 tools/espn_sync.py` in a second terminal — leave running. It polls the (public) league API and prints your **real slot automatically once ESPN randomizes the order (~12:00 PM EDT)**. Enter that slot in ⚙ Setup — the only setting you need to touch.
4. Open Claude Code in this project folder and say **"start draft watch"** — Claude reads `data/state.json` live and volunteers insights; you can also just ask "who should I take?"
5. **1:00 PM:** flip **🛰 sync ON** in the board's top bar. Picks now appear on the board by themselves as they happen in ESPN — **no clicking needed**. Manual clicking still works as backup and can't create duplicates.

## Draft watch — proactive Claude insights (no asking needed)
When the draft goes live, tell Claude **"start draft watch."** Claude then re-reads `data/state.json` on a self-paced interval (~every 60–75 s) and speaks up only when there's signal:
- **≤3 picks before your turn:** a short target plan for the pick ("aim McBride; fallback Cook — Lamar if both gone")
- **You're on the clock:** the pick and a one-line why
- **A position run or a notable faller** worth reacting to
Otherwise it stays silent — no spam between picks. Say **"stop draft watch"** when the draft ends. You can still ask questions at any time; the watch doesn't replace that.

## During the draft
- With **🛰 sync ON**, picks record themselves. If ESPN's feed ever lags: type a few letters → click the row (auto-assigns to the team on the clock); sync resumes safely around your manual entries.
- **Team names don't matter — order does.** "Team 3" just means "whoever picks 3rd." The only mapping that matters is that YOUR slot is set right, and that every pick gets clicked **in the order it happened** (undo fixes any slip). Sanity check anytime: the board's pick number should match ESPN's pick number.
- **Your turn** = green pulsing banner. The rec strip shows top 5 with reasons; click a rec card (or any row) to draft.
- Misclick → **UNDO** button or Cmd+Z. Player missing → **Unlisted pick…** (records the pick, keeps the order right).
- Columns: **ECR** = expert consensus rank (value) · **ADP** = market price · **Value +N** = market lets him fall N picks past his rank · **At your pick %** = chance he's still there at your next turn.

## Strategy brief (built from live Aug-2026 data — see Value column for all of this in real time)

**Core rules**
1. Draft by **tier, not rank** — when a tier is about to die at a position ("last in T3"), that beats a slightly higher-ranked player from a fat tier.
2. **Rounds 1–3: RB/WR only** (exception below: elite TE value). This year's elite tier: Chase, Nacua, Smith-Njigba, St. Brown (WR) / Gibbs, Bijan (RB), then CMC/Lamb/Jefferson/Taylor T2.
3. **Elite TE: take at fair price, don't count on a fall.** Generic mock-ADP says McBride/Bowers slide to R3/4 — but **ESPN's own list prices them at #17/#24**, and this room drafts off ESPN's list. If one slips past ~pick 22, snap him; otherwise punt TE late (TE is deeper than usual this year).
4. **QB is the structural steal of THIS room.** ESPN's list buries the QBs casuals rely on: **Lamar is ESPN #88 vs expert #31** and **Daniels #87 vs #50**. Expect them to hang around 2–4 rounds past their real value — target Lamar ~R5–6, Daniels as the R6–7 fallback. One QB only until the final rounds. (Watch the ESPN# column: it predicts what the room does.)
5. **K + DST in the last two rounds. Never earlier.** (The app enforces this in recommendations.)
6. Rounds 9+: **upside over floor** — bench spots are lottery tickets. Byes are a tiebreaker at most; ignore before round 10.

**2026 flags** (consensus data + reported news)
- **Overpriced by the market — let someone else pay:** Achane (ECR 21 / ADP 9), Rashee Rice (20 / 11 — reported suspension risk), Saquon (25 / 19), Hubbard (86 / 75).
- **Falling values — plan to catch them:** McBride, Bowers, Lamar, Daniels, rookie WR Carnell Tate (64 / 76), Jefferson mildly (9 / 13).
- **Injury-priced-in — fine at their listed rank, don't reach:** Malik Nabers (ECR 30, 2025 ACL recovery), Kittle (105, Achilles), Charbonnet (142, reportedly out until ~Oct — skip entirely).
- **Ricky Pearsall is OFF expert boards** (injury signal) but stale market ADP ~118 remains — do not draft; if a leaguemate takes him, use Unlisted pick.

**Casual-room edges** (~half the league drafts off the site's default list ≈ ADP)
- The "falling values" above really will fall near their ADP — **don't reach for them**, schedule them.
- Position runs (QB/TE panic runs) happen — don't chase; take the best player the run is ignoring.
- Slot 1–3 or 10–12: you pick in **pairs** at the turn — plan both picks together, and a small reach beats losing both targets during the 22-pick wait.

## League-specific notes (from the GCC YG settings)
- **Scoring is standard ESPN full-PPR** (4-pt pass TD, -2 INT, 0.1/yd rush-rec, 1/reception) — the fetched PPR ranks apply as-is. Fumbles are a mild −1.5.
- **Only 4 of 12 teams make the playoffs** → draft for **ceiling**, not floor. A safe 7th-place roster is worthless; the late-round upside rule matters extra here.
- **Kicker scoring is juiced** (FG 40–49 = 4, 50–59 = 5, 60+ = 6, miss −1): still last-round only, but prefer a strong-leg kicker on a good offense when you get there.
- **D/ST gets yards-allowed bonuses** on top of points-allowed: elite defenses are worth slightly more than usual — take the best available D/ST in round 15/16 rather than fully punting quality.
- **Rosters cap QB at 4, TE at 3, K at 3, D/ST at 3** — irrelevant if drafting sanely (1 QB, 1 TE unless value, 1 K, 1 D/ST).
- **ESPN room dynamics:** casuals draft from ESPN's default rank list. Expect market behavior close to ADP — the "falling values" plan holds. With 90 s picks and half the room casual, expect a few panic reaches and autopicks late; stay patient.
- You are **"Chichi's Cool Team"**; lineup lock is per-game, waivers are 1-day — none of it matters until after the draft.

## Edge cases
- **espn_sync.py dies or feed stalls:** the board keeps working — click picks manually (the original flow). Restart the script anytime; it catches up and the dupe-guard prevents double entries.
- **Wrong click / out-of-order chaos:** undo as far back as needed; picks are a simple stack.
- **Board won't load data:** run steps 1–2 above (it needs the local server, not file://).
- **Roster boxes in ⚙ Setup** already match the league (BN 7 → 16 rounds); don't change them unless the LM changes settings.
- **Re-verify after any code change:** `NODE_PATH=$(npm root -g) node tools/test_board.cjs` (with serve.py running) — must print `ALL BOARD CHECKS PASSED`.
