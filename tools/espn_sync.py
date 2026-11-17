#!/usr/bin/env python3
"""Live ESPN draft sync for league GCC YG (public league — no auth needed).

Polls ESPN's draft feed and writes data/espn_picks.json with picks already
matched to our players.json names; the board (with its "ESPN sync" toggle ON)
ingests them automatically, so nobody has to click picks in by hand.

Also prints the draft order / your slot once ESPN randomizes it (~1 hr before).

Usage:
  python3 tools/espn_sync.py          # run during the draft (Ctrl-C to stop)
  python3 tools/espn_sync.py --once   # single status check (e.g. at noon for your slot)
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from fetch_data import norm_name, norm_dst  # single source of truth for name matching

ROOT = Path(__file__).resolve().parent.parent
LEAGUE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/segments/0/leagues/" + os.environ.get("ESPN_LEAGUE_ID", "")
PLAYERS_URL = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/players?view=players_wl&scoringPeriodId=0"
MY_TEAM_ID = 11  # Chichi's Cool Team
POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DST"}
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36", "Accept": "application/json"}


def get(url, extra=None):
    req = urllib.request.Request(url, headers={**UA, **(extra or {})})
    return json.loads(urllib.request.urlopen(req, timeout=20).read())


def atomic_write(path, obj):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1))
    tmp.replace(path)


def local_player_index():
    """(normalized name, pos) -> canonical players.json identity."""
    data = json.loads((ROOT / "data" / "players.json").read_text())
    idx = {}
    for p in data["players"]:
        k = ("dst-" + norm_dst(p["name"])) if p["pos"] == "DST" else (norm_name(p["name"]), p["pos"])
        idx[k] = (p["name"], p["pos"])
    return idx


def espn_player_map():
    """ESPN playerId -> (fullName, pos). Cached; refetched if an id is missing."""
    cache_path = ROOT / "data" / "espn_players.json"
    filt = {"filterActive": {"value": True}}
    rows = get(PLAYERS_URL, {"x-fantasy-filter": json.dumps(filt)})
    m = {str(r["id"]): (r.get("fullName", "?"), POS.get(r.get("defaultPositionId"), "?")) for r in rows}
    atomic_write(cache_path, m)
    return m


def draft_order(picks):
    r1 = sorted((p for p in picks if p.get("roundId") == 1), key=lambda p: p.get("roundPickNumber", 0))
    return [p.get("teamId") for p in r1]


def main():
    once = "--once" in sys.argv
    local = local_player_index()
    espn = espn_player_map()
    print(f"matched sources: {len(local)} local players, {len(espn)} ESPN players")
    out_path = ROOT / "data" / "espn_picks.json"
    last_count = -1

    while True:
        dd = {}
        try:
            dd = get(LEAGUE + "?view=mDraftDetail").get("draftDetail", {})
            picks_raw = dd.get("picks") or []
            order = draft_order(picks_raw)
            my_slot = order.index(MY_TEAM_ID) + 1 if MY_TEAM_ID in order else None
            made = sorted((p for p in picks_raw if (p.get("playerId") or 0) > 0),  # empty slots carry playerId -1
                          key=lambda p: p.get("overallPickNumber", 0))
            feed = []
            for p in made:
                pid = str(p["playerId"])
                name, pos = espn.get(pid, (None, None))
                if name is None:                       # id not in cache -> refresh once
                    espn = espn_player_map()
                    name, pos = espn.get(pid, (f"ESPN id {pid}", "?"))
                k = ("dst-" + norm_dst(name)) if pos == "DST" else (norm_name(name), pos)
                hit = local.get(k)
                feed.append({
                    "n": p.get("overallPickNumber"), "espnTeamId": p.get("teamId"),
                    "name": hit[0] if hit else name, "pos": hit[1] if hit else pos,
                    "pid": f"{hit[0]}|{hit[1]}" if hit else None, "matched": bool(hit),
                })
            atomic_write(out_path, {
                "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "inProgress": dd.get("inProgress", False), "drafted": dd.get("drafted", False),
                "mySlot": my_slot, "draftOrder": order, "picks": feed,
            })
            if len(feed) != last_count:
                for p in feed[max(0, last_count):]:
                    print(f"  pick {p['n']}: {p['name']} ({p['pos']})" + ("" if p["matched"] else "  [UNMATCHED]"))
                last_count = len(feed)
            status = "LIVE" if dd.get("inProgress") else ("done" if dd.get("drafted") else "not started")
            slot_note = f"my slot: {my_slot or '?'}" + ("" if dd.get("inProgress") or dd.get("drafted")
                        else " (PROVISIONAL — ESPN randomizes the real order ~1 hr before draft)")
            print(f"[{time.strftime('%H:%M:%S')}] draft {status} · {len(feed)} picks · {slot_note}")
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] poll error (will retry): {type(e).__name__}: {e}")
        if once:
            return
        time.sleep(3 if dd.get("inProgress") else 15)


if __name__ == "__main__":
    main()
