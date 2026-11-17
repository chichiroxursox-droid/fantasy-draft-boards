#!/usr/bin/env python3
"""Fetch live draft data and merge into data/players.json. No API keys needed.
Re-run the morning of the draft.

Sources:
- FantasyPros embedded ECR JSON (value): name/team/pos/bye + expert tier,
  overall rank, position rank — per scoring format. ~515 players, updated daily.
- FantasyFootballCalculator ADP API (market price): adp + stdev per format.

Usage: python3 tools/fetch_data.py
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "players.json"

FFC = "https://fantasyfootballcalculator.com/api/v1/adp/{slug}?teams=12&year=2026"
FP = "https://www.fantasypros.com/nfl/rankings/{slug}.php"
ESPN_KONA = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/segments/0/leagues/" + os.environ.get("ESPN_LEAGUE_ID", "") + "?view=kona_player_info"
ESPN_POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DST"}

FORMATS = {  # key -> (ffc slug, fantasypros slug)
    "ppr": ("ppr", "ppr-cheatsheets"),
    "half": ("half-ppr", "half-point-ppr-cheatsheets"),
    "std": ("standard", "consensus-cheatsheets"),
}
SUFFIX_TOKENS = {"jr", "sr", "ii", "iii", "iv", "v"}
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def get(url, timeout=30):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def norm_name(name):
    s = re.sub(r"[^a-z ]", "", name.lower().replace(".", "").replace("'", ""))
    return " ".join(t for t in s.split() if t not in SUFFIX_TOKENS)


def norm_dst(name):
    # "Patriots Defense" / "New England Patriots" -> "patriots"
    toks = [t for t in norm_name(name).split() if t not in {"defense", "dst", "d", "st"}]
    return toks[-1] if toks else ""


def key_for(name, pos, team=None):
    if pos == "DST":  # city vs nickname naming differs by source; team code is stable
        return (team or norm_dst(name), pos)
    return (norm_name(name), pos)


def fetch_fp(fmt_key):
    html = get(FP.format(slug=FORMATS[fmt_key][1])).decode(errors="replace")
    m = re.search(r"var ecrData\s*=\s*(\{.*?\});", html, re.S)
    if not m:
        raise RuntimeError(f"no ecrData found on FantasyPros {fmt_key} page")
    return json.loads(m.group(1))


def fetch_ffc(fmt_key):
    data = json.loads(get(FFC.format(slug=FORMATS[fmt_key][0])))
    out = {}
    for p in data.get("players", []):
        pos = {"PK": "K", "DEF": "DST"}.get(p["position"], p["position"])
        out[key_for(p["name"], pos, p.get("team"))] = (p.get("adp"), p.get("stdev"))
    return out


def fetch_espn_ranks():
    """ESPN's default draft ranks + market auction values (10-team $200 scale)."""
    filt = {"players": {"limit": 500, "sortDraftRanks": {"sortPriority": 100, "sortAsc": True, "value": "PPR"}}}
    req = urllib.request.Request(ESPN_KONA, headers={**UA, "x-fantasy-filter": json.dumps(filt), "Accept": "application/json"})
    data = json.loads(urllib.request.urlopen(req, timeout=30).read())
    ranks = {}
    for row in data.get("players", []):
        pl = row.get("player") or {}
        pos = ESPN_POS.get(pl.get("defaultPositionId"))
        dr = (pl.get("draftRanksByRankType") or {}).get("PPR") or {}
        rk, av = dr.get("rank"), dr.get("auctionValue")
        if not pos or not rk:
            continue
        name = pl.get("fullName", "")
        key = ("dst-" + norm_dst(name)) if pos == "DST" else (norm_name(name), pos)
        ranks[key] = (rk, av)
    return ranks


# ---- GCCFFL auction valuation (16 teams x $200, 12 spots) ----
# 192 league slots: 16 x (QB,RB,WR,TE,K,DST) mandatory + 32 W/T flex (75/25 WR/TE)
# + 16 W/R/T flex (45/35/20 WR/RB/TE) + 48 bench (40/40/10/10 RB/WR/TE/QB).
# Only 1 mandatory RB start makes this pool RB-light / WR-heavy vs standard sheets.
AUCTION = {"teams": 15, "budget": 200, "spots": 12}   # 15 GMs confirmed for draft day; --teams N to change
# per-team draftable demand: 1 each mandatory + flex/bench share. x teams -> pool sizes.
PER_TEAM = {"QB": 21 / 16, "RB": 41 / 16, "WR": 66 / 16, "TE": 32 / 16, "K": 1, "DST": 1}
POOL = {}


def set_teams(n):
    """Team count drives everything: money in the room and how deep each position is drafted."""
    AUCTION["teams"] = n
    POOL.clear()
    POOL.update({pos: max(1, round(v * n)) for pos, v in PER_TEAM.items()})


set_teams(AUCTION["teams"])

# GCCFFL scores 0.6 per reception (Yahoo settings export) — 20% of the
# way from half-PPR to full PPR. Blend the two expert rank sets instead of pretending
# it's either one; "gcc" then behaves like any other format everywhere downstream.
PPR_WEIGHT = 0.2
FMT_KEYS = list(FORMATS) + ["gcc"]


def blend_gcc(out):
    scored = []
    for r in out:
        h, p = r["ecr"].get("half"), r["ecr"].get("ppr")
        blended = (1 - PPR_WEIGHT) * h + PPR_WEIGHT * p if (h and p) else (h or p)
        if blended is not None:
            scored.append((blended, r))
        if r["tier"].get("half") is not None:      # 0.6 sits much closer to half — take its tiers
            r["tier"]["gcc"] = r["tier"]["half"]
        for fld in ("adp", "stdev"):
            hv, pv = r[fld].get("half"), r[fld].get("ppr")
            if hv and pv:
                r[fld]["gcc"] = round((1 - PPR_WEIGHT) * hv + PPR_WEIGHT * pv, 1)
            elif hv or pv:
                r[fld]["gcc"] = hv or pv
    scored.sort(key=lambda x: x[0])
    pos_n = {}
    for i, (_, r) in enumerate(scored, 1):        # re-rank to clean integers for display
        r["ecr"]["gcc"] = i
        pos_n[r["pos"]] = pos_n.get(r["pos"], 0) + 1
        r["posRank"]["gcc"] = pos_n[r["pos"]]
    print(f"gcc blend: {len(scored)} players ranked at 0.6 PPR ({int(PPR_WEIGHT*100)}% toward full PPR)")


def compute_auction(out):
    """Per-format dollar values: ESPN's market curve per position (price *shape*),
    reassigned in each format's ECR order, rescaled so the whole draftable pool
    sums to the room's money. $1 floor everywhere; tail/K/DST land at $1 naturally."""
    slots = sum(POOL.values())
    disc = AUCTION["teams"] * AUCTION["budget"] - slots  # $ above the $1 floors
    for fmt in FMT_KEYS:
        weights = []  # (row, curve weight)
        for pos, n in POOL.items():
            at_pos = [r for r in out if r["pos"] == pos]
            ladder = sorted((r.get("espnAV") or 0 for r in at_pos), reverse=True)[:n]
            ladder += [0] * (n - len(ladder))
            ranked = sorted(at_pos, key=lambda r: r["ecr"].get(fmt) or 9999)[:n]
            # elite-TE damp: ESPN's market premium prices top TEs ~40% above projection-VORP;
            # independent 16-team sheets have Bowers/McBride ~$20 lower. Our extra TE slots
            # (2 W/T + flex) justify staying above VORP, so split the difference on the top rungs.
            weights += [(row, max(av - 1, 0) * (0.8 if pos == "TE" and av >= 25 else 1))
                        for row, av in zip(ranked, ladder)]
        wsum = sum(w for _, w in weights) or 1
        for row, w in weights:
            row.setdefault("auction", {})[fmt] = max(1, round(1 + w * disc / wsum))
        total = sum(r["auction"][fmt] for r in out if fmt in r.get("auction", {}))
        gt1 = sum(1 for r in out if r.get("auction", {}).get(fmt, 1) > 1)
        print(f"auction {fmt}: pool Σ ${total} (target {AUCTION['teams']*AUCTION['budget']}), {gt1} players above $1")
        # draft-morning guard: if ESPN's auction feed is down, every weight is 0 and the whole
        # board silently becomes $1. Refuse to produce that rather than overwrite good data.
        assert gt1 >= 100, f"{fmt}: only {gt1} players above $1 — ESPN auction values missing, refusing to write"
    print("\nTop 8 per position (GCCFFL 0.6-PPR $):")
    for pos in POOL:
        top = sorted((r for r in out if r["pos"] == pos and "gcc" in r.get("auction", {})),
                     key=lambda r: -r["auction"]["gcc"])[:8]
        print(f"  {pos:<3} " + " | ".join(f"{r['name'].split()[-1]} ${r['auction']['gcc']}" for r in top))


def write_sheet():
    """--sheet: printable per-position auction $ tables from existing players.json (offline paper fallback)."""
    data = json.loads(OUT.read_text())
    rows_html = []
    for pos in ["QB", "RB", "WR", "TE", "K", "DST"]:
        rows = sorted((p for p in data["players"] if p["pos"] == pos and p.get("auction")),
                      key=lambda p: -p["auction"].get("gcc", 0))
        body = "".join(
            f"<tr><td>{i+1}</td><td>{p['name']}</td><td>{p.get('team') or ''}</td><td>{p.get('bye') or ''}</td>"
            f"<td class=m>${p['auction'].get('gcc',1)}</td><td>${p['auction'].get('half',1)}</td><td>${p['auction'].get('ppr',1)}</td></tr>"
            for i, p in enumerate(rows))
        rows_html.append(f"<table><caption>{pos}</caption><tr><th></th><th>Player</th><th>Tm</th><th>Bye</th>"
                         f"<th>0.6</th><th>Half</th><th>PPR</th></tr>{body}</table>")
    sheet = ROOT / "data" / "auction_sheet.html"
    sheet.write_text(
        "<!DOCTYPE html><meta charset='utf-8'><title>GCCFFL auction values</title><style>"
        "body{font:9.5px/1.3 -apple-system,sans-serif;columns:3;column-gap:14px;margin:10px}"
        "table{border-collapse:collapse;width:100%;break-inside:avoid;margin-bottom:10px}"
        "caption{font-weight:700;text-align:left;padding:2px 0}"
        "td,th{border-bottom:1px solid #ccc;padding:1px 4px;text-align:left}.m{font-weight:700}"
        "</style><h3 style='column-span:all;margin:0 0 6px'>GCCFFL 16-team $200 auction values — "
        f"{data.get('fetched_at','')[:10]} · 0.6 PPR column is the live one</h3>" + "".join(rows_html))
    print(f"wrote {sheet} — print it as the paper fallback")


def main():
    if "--teams" in sys.argv:      # e.g. --teams 15 if someone drops out before draft day
        set_teams(int(sys.argv[sys.argv.index("--teams") + 1]))
        print(f"teams={AUCTION['teams']} -> ${AUCTION['teams']*AUCTION['budget']} in the room, pool {POOL}")
    if "--sheet" in sys.argv:
        return write_sheet()
    players = {}
    fp_meta = {}
    for fmt in FORMATS:
        data = fetch_fp(fmt)
        fp_meta[fmt] = data.get("last_updated")
        rows = data.get("players", [])
        print(f"FP {fmt}: {len(rows)} players (updated {fp_meta[fmt]})")
        for p in rows:
            pos = re.sub(r"\d+$", "", p["player_position_id"]).upper()
            if pos not in {"QB", "RB", "WR", "TE", "K", "DST"}:
                continue
            k = key_for(p["player_name"], pos, p.get("player_team_id"))
            row = players.setdefault(k, {
                "name": p["player_name"], "pos": pos,
                "team": p.get("player_team_id"), "bye": None,
                "ecr": {}, "tier": {}, "posRank": {}, "adp": {}, "stdev": {},
            })
            bye = p.get("player_bye_week")
            row["bye"] = row["bye"] or (int(bye) if bye and str(bye).isdigit() else None)
            row["ecr"][fmt] = p.get("rank_ecr")
            row["tier"][fmt] = p.get("tier")
            pr = re.sub(r"\D", "", str(p.get("pos_rank", "")))
            row["posRank"][fmt] = int(pr) if pr else None

    unmatched_adp = []
    for fmt in FORMATS:
        table = fetch_ffc(fmt)
        print(f"FFC {fmt}: {len(table)} players")
        matched = 0
        for k, (adp, stdev) in table.items():
            if k in players:
                players[k]["adp"][fmt] = adp
                players[k]["stdev"][fmt] = stdev
                matched += 1
            elif fmt == "ppr" and adp and adp <= 150:
                unmatched_adp.append(f"{k[1]} {k[0]} (adp {adp})")
        if matched < len(table) * 0.8:
            print(f"WARN: only {matched}/{len(table)} FFC {fmt} names matched FantasyPros")

    try:
        espn = fetch_espn_ranks()
        hit = av_hit = 0
        for k, row in players.items():
            ek = ("dst-" + norm_dst(row["name"])) if row["pos"] == "DST" else k
            if ek in espn:
                rk, av = espn[ek]
                row["espnRank"] = rk
                hit += 1
                if av:
                    row["espnAV"] = int(av)
                    av_hit += 1
        print(f"ESPN ranks: {len(espn)} fetched, {hit} matched ({av_hit} with auction value)")
    except Exception as e:
        print(f"WARN: ESPN ranks unavailable ({type(e).__name__}: {e}) — continuing without")

    out = sorted(players.values(), key=lambda r: r["ecr"].get("ppr") or 9999)
    blend_gcc(out)
    compute_auction(out)

    # ---- sanity checks ----
    assert len(out) >= 400, f"only {len(out)} players from FantasyPros"
    top100 = out[:100]
    no_adp = [r["name"] for r in top100 if not r["adp"].get("ppr")]
    no_bye = [r["name"] for r in top100 if r["pos"] != "DST" and not r["bye"]]
    missing_fmt = [r["name"] for r in top100 if not (r["ecr"].get("half") and r["ecr"].get("std"))]
    if no_adp:
        print(f"note: top-100 ECR without market ADP ({len(no_adp)}): {no_adp[:8]}")
    if no_bye:
        print(f"WARN: top-100 missing bye: {no_bye[:8]}")
    if missing_fmt:
        print(f"WARN: top-100 missing half/std ranks: {missing_fmt[:8]}")
    if unmatched_adp:
        print(f"WARN: FFC top-150 ADP names with no FantasyPros match: {unmatched_adp[:8]}")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fp_updated": fp_meta, "teams": 12, "year": 2026, "auction": AUCTION,
        "players": out,
    }, indent=1))
    with_adp = sum(1 for r in out if r["adp"].get("ppr"))
    print(f"\nwrote {OUT} — {len(out)} players ({with_adp} with ADP)")
    print("\nTop 15 by PPR ECR (rank | tier | adp):")
    for r in out[:15]:
        print(f"  {r['ecr']['ppr']:>3} | T{r['tier'].get('ppr','?')} | adp {str(r['adp'].get('ppr','—')):>5} | {r['pos']:<3} {r['name']} ({r['team']}, bye {r['bye']})")


if __name__ == "__main__":
    sys.exit(main())
