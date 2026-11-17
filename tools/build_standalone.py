#!/usr/bin/env python3
"""Bundle auction.html + its data into ONE file you can email or AirDrop.
No server, no wifi, no install — the recipient double-clicks it and it works.

Usage: python3 tools/build_standalone.py   ->  GCCFFL-auction-board.html
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "GCCFFL-auction-board.html"

html = (ROOT / "auction.html").read_text()
players = json.loads((ROOT / "data" / "players.json").read_text())
notes_path = ROOT / "data" / "notes.json"
notes = json.loads(notes_path.read_text()).get("notes", {}) if notes_path.exists() else {}

# trim to what the board actually reads — keeps the emailed file small
slim = [{k: v for k, v in p.items() if k in
         ("name", "pos", "team", "bye", "ecr", "tier", "posRank", "auction")}
        for p in players["players"]]
payload = {"fetched_at": players.get("fetched_at"), "auction": players.get("auction"), "players": slim}

inline = ("<script>window.INLINE_DATA=" + json.dumps(payload, separators=(",", ":"))
          + ";window.INLINE_NOTES=" + json.dumps(notes, separators=(",", ":")) + ";</script>\n<script>")
out = html.replace('<script>\n"use strict";', inline + '\n"use strict";', 1)
assert "INLINE_DATA" in out, "inline hook not found — did the <script> opener in auction.html change?"

OUT.write_text(out)
mb = OUT.stat().st_size / 1e6
print(f"wrote {OUT.name} — {mb:.1f} MB, {len(slim)} players, {len(notes)} news flags")
print("Double-click to open. Works offline, no server needed.")
