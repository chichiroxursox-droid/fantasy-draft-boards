#!/usr/bin/env python3
"""Generate a mock-auction moderator script for practice run-throughs.
A friend reads it aloud like the auctioneer; you type everything into auction.html.
Deterministic (seeded) so the answer key always matches.

Usage: python3 tools/make_mock.py   ->  data/mock_auction_script.txt
"""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEAMS = ["Dana", "Cole", "Ari/Ivan", "Drew", "Paul", "Jack", "Sean", "P.Evan",  # placeholder names
         "Jon R.", "Perry", "Miles", "Carl", "Ellis", "Kim", "Sam/Ethan", "Ethan Z"]
ME = 14
BUDGET, SPOTS = 200, 12

rng = random.Random(830)  # seeded: script and answer key always agree

data = json.loads((ROOT / "data" / "players.json").read_text())
pool = sorted((p for p in data["players"] if p.get("auction")),
              key=lambda p: -p["auction"].get("half", 1))

spent = [0] * 16
bought = [0] * 16
sales = []          # (name, pos, price, buyer_idx or None)
used = set()


def pick_buyer(price, exclude_me=True):
    cands = [i for i in range(16)
             if (not exclude_me or i != ME)
             and bought[i] < SPOTS
             and BUDGET - spent[i] - price >= (SPOTS - bought[i] - 1)]
    return rng.choice(cands) if cands else None


def sell(p, buyer=None, mult=None):
    base = p["auction"].get("half", 1)
    price = max(1, round(base * (mult if mult else rng.uniform(0.85, 1.25))))
    if buyer is None:
        buyer = pick_buyer(price)
        if buyer is None:
            price, buyer = 1, pick_buyer(1)
    price = min(price, BUDGET - spent[buyer] - (SPOTS - bought[buyer] - 1))
    price = max(1, price)
    spent[buyer] += price
    bought[buyer] += 1
    sales.append((p["name"], p["pos"], price, buyer))
    used.add(p["name"])
    return price, buyer


def take(n, lo, hi):
    """n unsold players from value-rank window [lo, hi)."""
    window = [p for p in pool[lo:hi] if p["name"] not in used]
    return rng.sample(window, min(n, len(window)))


L = []
say = L.append
say("MOCK AUCTION RUN-THROUGH — moderator script (friend reads, you type)")
say("=" * 68)
say("")
say("Setup: open http://localhost:8712/auction.html and click 'New auction")
say("(clear all sales)'. Friend reads each line aloud AT TALKING SPEED and")
say("does not repeat unless asked once. You type every sale.")
say("Goal: under ~6 seconds per sale, zero wrong buyers.")
say("")
say("-" * 68)
say("PHASE 1 — warm-up, 8 sales (stars go first, like real life)")
say("-" * 68)
for p in take(8, 0, 18):
    price, b = sell(p)
    say(f'  "{p["name"]}... sold to {TEAMS[b]}, ${price}."')

say("")
say("-" * 68)
say("PHASE 2 — you 'arrived late': friend reads this block in ONE breath.")
say("Do NOT enter these one by one — use the ⏱ Catch up button and paste")
say("the block below it, exactly as printed:")
say("-" * 68)
catchup = []
for p in take(8, 10, 45):
    price, b = sell(p)
    say(f'  "{p["name"]} went for ${price} to {TEAMS[b]}."')
    catchup.append(f"{p['name'].lower()} {price} {b+1}")
catchup[-1] = catchup[-1].rsplit(" ", 1)[0]  # last one: buyer unknown on purpose
lastname = sales[-1][0]
say("")
say("  Paste-ready block (last line has no buyer on purpose — it should")
say("  land under '❓ Unknown'; fix it later from Last sales):")
for line in catchup:
    say("    " + line)
say(f"  (The unknown one was actually {TEAMS[sales[-1][3]]} — practice")
say(f"  clicking the {lastname} sale in the feed and assigning the buyer.)")

say("")
say("-" * 68)
say("PHASE 3 — live chaos, 10 sales: you win two, one correction, keep up")
say("-" * 68)
mine = take(2, 15, 60)
chaos = take(8, 25, 80)
order = mine[:1] + chaos[:4] + mine[1:] + chaos[4:]
correction_at = 3
for i, p in enumerate(order):
    if p in mine:
        price, b = sell(p, buyer=ME)
        say(f'  "{p["name"]}... going once... SOLD to Sam and Ethan, ${price}."   (buyer: m)')
    else:
        price, b = sell(p)
        say(f'  "{p["name"]}, ${price}, {TEAMS[b]}."')
    if i == correction_at:
        nm, pos, pr, byr = sales[-1]
        newpr = pr + 7
        spent[byr] += 7
        sales[-1] = (nm, pos, newpr, byr)
        say(f'  "Wait — correction, {nm} was ${newpr}, not ${pr}."')
        say(f"   (practice: click the {nm} sale in Last sales, fix the price)")

say("")
say("-" * 68)
say("PHASE 4 — endgame, 6 quick $1-$3 sales (watch your Nominate strip")
say("flip to '$1 wins' if your max bid drops low)")
say("-" * 68)
for p in take(6, 90, 170):
    price, b = sell(p, mult=rng.uniform(0.5, 1.0))
    say(f'  "{p["name"]}, {TEAMS[b]}, ${price}."')

say("")
say("=" * 68)
say("ANSWER KEY — after all phases, your Teams grid must show exactly:")
say("=" * 68)
for i, t in enumerate(TEAMS):
    if spent[i] or bought[i]:
        left = BUDGET - spent[i]
        mx = left - max(0, (SPOTS - bought[i]) - 1)
        say(f"  {i+1:>2}. {t:<12} spent ${spent[i]:<3} left ${left:<3} max ${mx:<3} open {SPOTS - bought[i]}")
say(f"  Total sales entered: {len(sales)}  ·  league money spent: ${sum(s[2] for s in sales)}")
say("")
say("If a row is off: 'show sold' + click the player to see who you gave him")
say("to, or click sales in the feed to audit. Then run it again for time.")

out = ROOT / "data" / "mock_auction_script.txt"
out.write_text("\n".join(L) + "\n")
print(f"wrote {out} ({len(sales)} sales)")
