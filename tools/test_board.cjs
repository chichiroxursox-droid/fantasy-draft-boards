/* Headless check of draft.html: setup, 19 picks at slot 5, snake math,
 * recommendations, undo, reload persistence, state.json push.
 * Run: NODE_PATH=$(npm root -g) node tools/test_board.cjs  (serve.py must be running)
 */
const { chromium } = require("playwright");
const assert = require("assert");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", e => errors.push("pageerror: " + e.message));
  page.on("console", m => { if (m.type() === "error") errors.push("console: " + m.text()); });

  await page.goto("http://localhost:8712/draft.html");
  await page.waitForSelector("#setup:not(.hide)", { timeout: 8000 });

  // fresh state for a repeatable test
  await page.evaluate(() => localStorage.removeItem("ffdraft-v2"));
  await page.reload();
  await page.waitForSelector("#setup:not(.hide)");

  // setup: 12 teams, my slot 5, PPR
  await page.selectOption("#s-slot", "5");
  await page.click("#startbtn");
  assert.equal(await page.textContent("#pickinfo"), "Rd 1/16 · Pick 1 (1.01)", "initial pick label (16 rounds: 9 starters + 7 bench)");
  assert.equal(await page.evaluate(() => DATA.players.length > 400), true, "data loaded");

  // recommendations present with reasons
  const recCount = await page.evaluate(() => document.querySelectorAll(".rec").length);
  assert.equal(recCount, 5, "5 recommendations");

  // simulate picks 1..19 by always taking best available (first row)
  const names = [];
  for (let n = 1; n <= 19; n++) {
    const onClock = await page.textContent("#onclock");
    if (n === 5) assert.ok(onClock.includes("YOU"), `pick ${n} should be mine, got: ${onClock}`);
    else assert.ok(!onClock.includes("YOU"), `pick ${n} not mine, got: ${onClock}`);
    names.push(await page.evaluate(() => document.querySelector("tbody tr.p b").textContent));
    await page.click("tbody tr.p"); // first available row
  }
  // snake reversal: pick 13 belongs to slot 12, pick 20 is mine (12*2-5+1)
  assert.equal(await page.evaluate(() => slotForPick(13)), 12, "round 2 starts at slot 12");
  assert.equal(await page.evaluate(() => slotForPick(20)), 5, "pick 20 is slot 5");
  assert.ok((await page.textContent("#onclock")).includes("YOU"), "pick 20 on the clock = me");

  // drafted players are out of the pool and appear in feed
  const stillThere = await page.evaluate(ns => {
    const gone = new Set(S.picks.map(x => x.name));
    return ns.filter(n => !gone.has(n));
  }, names);
  assert.equal(stillThere.length, 0, "all clicked players recorded");
  assert.equal(await page.evaluate(() => document.querySelectorAll("tbody tr.p.gone").length), 0, "drafted hidden by default");

  // my roster: slot-5 picks assigned (pick 5 and none else yet -> 1 player)
  const myCount = await page.evaluate(() => S.picks.filter(x => x.slot === 5).length);
  assert.equal(myCount, 1, "one of first 19 picks is mine");
  const rosterFilled = await page.evaluate(() => assignRoster().filter(s => s.p).length);
  assert.equal(rosterFilled, 1, "roster shows my player");

  // "picks until you" text correctness right after my pick 5 was made is hard to
  // rewind; verify current: at pick 20 it's my turn so untilme is empty
  assert.equal((await page.textContent("#untilme")).trim(), "", "untilme empty on my turn");

  // undo
  await page.click("#undobtn");
  assert.equal(await page.evaluate(() => S.picks.length), 18, "undo removed last pick");
  assert.equal(await page.textContent("#pickinfo"), "Rd 2/16 · Pick 19 (2.07)", "pick label after undo");

  // reload persistence
  await page.reload();
  await page.waitForSelector("tbody tr.p");
  assert.equal(await page.evaluate(() => S.picks.length), 18, "picks survive reload");
  assert.equal(await page.evaluate(() => S.mySlot), 5, "slot survives reload");

  // format switch re-sorts without errors
  await page.selectOption("#fmtsel", "half");
  assert.equal(await page.evaluate(() => S.fmt), "half", "format switched");
  await page.selectOption("#fmtsel", "ppr");

  // search filter
  const target = await page.evaluate(() => availablePlayers().find(p => p.ecr?.ppr)?.name);
  await page.fill("#search", target.slice(0, 6));
  const found = await page.evaluate(() => document.querySelector("tbody tr.p b")?.textContent || "");
  assert.ok(found.toLowerCase().includes((await page.evaluate(t => t, target)).slice(0, 4).toLowerCase()), "search finds player");
  await page.fill("#search", "");

  // K/DST gate: no K/DST in recs this early
  const recPos = await page.evaluate(() => recommendations().map(r => r.p.pos));
  assert.ok(recPos.every(p => !["K", "DST"].includes(p)), "K/DST suppressed early, got " + recPos);

  // --- regression checks for the four review fixes ---

  // fix 1: Cmd+Z while typing in an input must NOT undo a pick
  const mod = process.platform === "darwin" ? "Meta" : "Control";
  await page.focus("#search");
  await page.keyboard.type("abc");
  await page.keyboard.press(`${mod}+z`);
  assert.equal(await page.evaluate(() => S.picks.length), 18, "Cmd+Z in search box does not undo picks");
  await page.fill("#search", "");
  await page.click("#pickinfo"); // blur inputs
  await page.keyboard.press(`${mod}+z`);
  assert.equal(await page.evaluate(() => S.picks.length), 17, "Cmd+Z outside inputs still undoes");

  // fix 4: unlisted names render inert (no HTML injection)
  const xss = await page.evaluate(async () => {
    window.__pwned = 0;
    draftPlayer(null, '<img src=x onerror="window.__pwned=1">');
    await new Promise(r => setTimeout(r, 300));
    const feedSafe = document.querySelector("#feed").innerHTML.includes("&lt;img");
    undo();
    return { pwned: window.__pwned, feedSafe };
  });
  assert.equal(xss.pwned, 0, "injected markup does not execute");
  assert.ok(xss.feedSafe, "unlisted name shown as literal text");

  // fix 3: K/DST need gate — 0 early, 0 when roster has no slot, 1 in last 2 rounds
  const gate = await page.evaluate(() => {
    const savedRoster = { ...S.roster }, savedPicks = S.picks;
    const out = { early: needMult("K") };
    S.roster = { ...S.roster, K: 0 };
    out.noSlot = needMult("K");
    S.roster = savedRoster;
    S.picks = Array.from({ length: totalRounds() - 2 }, (_, i) =>
      ({ n: i + 1, slot: S.mySlot, id: null, name: "F" + i, pos: "RB" }));
    out.late = needMult("K"); out.lateD = needMult("DST");
    S.picks = savedPicks;
    return out;
  });
  assert.deepEqual(gate, { early: 0, noSlot: 0, late: 1, lateD: 1 }, "K/DST gate honors slots and final-2-rounds rule");

  // ESPN sync: fake feed file -> board auto-ingests picks in order
  const fs = require("fs");
  const feedPath = __dirname + "/../data/espn_picks.json";
  const nextTwo = await page.evaluate(() =>
    availablePlayers().filter(p => p.ecr?.ppr).slice(0, 2).map(p => ({ name: p.name, pos: p.pos, pid: p.name + "|" + p.pos })));
  const cur = await page.evaluate(() => S.picks.length);
  fs.writeFileSync(feedPath, JSON.stringify({ picks: [
    { n: cur + 1, name: nextTwo[0].name, pos: nextTwo[0].pos, pid: nextTwo[0].pid, matched: true },
    { n: cur + 2, name: "Practice Squad Guy", pos: "RB", pid: null, matched: false },
  ]}));
  await page.evaluate(() => { S.espnSync = true; pollEspn(); });
  await page.waitForFunction(c => S.picks.length === c + 2, cur, { timeout: 12000 });
  const synced = await page.evaluate(() => S.picks.slice(-2).map(x => ({ name: x.name, pos: x.pos, hasId: !!x.id })));
  assert.equal(synced[0].hasId, true, "matched feed pick ingested with player id");
  assert.equal(synced[1].name, "Practice Squad Guy", "unmatched feed pick ingested as unlisted");
  assert.equal(synced[1].pos, "RB", "position hint preserved for unmatched pick");
  await page.evaluate(() => { S.espnSync = false; persist(); });
  fs.unlinkSync(feedPath);

  // fix 2: changing team count preserves my slot (run last — it changes snake math)
  await page.click("#setupbtn");
  await page.fill("#s-teams", "10");
  await page.click("#startbtn");
  assert.equal(await page.evaluate(() => S.mySlot), 5, "slot preserved after team-count change");

  await browser.close();
  assert.deepEqual(errors, [], "no page/console errors");
  console.log("ALL BOARD CHECKS PASSED");
})().catch(e => { console.error("FAIL:", e.message); process.exit(1); });
