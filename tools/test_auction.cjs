/* Auction board checks — run with serve.py up:
   NODE_PATH=$(npm root -g) node tools/test_auction.cjs */
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errs = [];
  page.on("pageerror", e => errs.push("pageerror: " + e.message));
  page.on("console", m => { if (m.type() === "error") errs.push("console: " + m.text()); });

  await page.goto("http://localhost:8712/auction.html");
  await page.evaluate(() => localStorage.removeItem("ffauction-v1"));  // repeatable run
  await page.reload();
  await page.waitForFunction(() => typeof DATA !== "undefined" && DATA && DATA.players.length > 0);

  // 1. boot: 15 preconfigured teams, $200, auction values priced for the pool
  const boot = await page.evaluate(() => ({
    teams: S.teams.length, me: S.teams[S.me], budget: S.budget, spots: spots(), fmt: S.fmt,
    priced: DATA.players.filter(p => p.auction).length,
    sumPool: DATA.players.reduce((a, p) => a + (p.auction?.gcc ?? 0), 0),
    myMax: C.teams[S.me].max,
  }));
  assert.equal(boot.teams, 15, "15 teams drafting");
  assert.equal(boot.me, "Sam/Ethan", "my team preconfigured");
  assert.equal(boot.budget, 200);
  assert.equal(boot.spots, 12, "12 roster spots");
  assert.equal(boot.fmt, "gcc", "fresh boot defaults to the league's 0.6-PPR scoring");
  assert.ok(boot.priced >= 150, "auction pool priced: " + boot.priced);
  assert.ok(Math.abs(boot.sumPool - 3000) < 60, "pool sums to room money (15 x $200): " + boot.sumPool);
  assert.equal(boot.myMax, 189, "fresh max bid 200-(12-1)");
  assert.ok((await page.locator("#teamgrid tr").count()) >= 16, "team grid renders");

  // 2. full keyboard sale: type name -> Enter -> price -> Enter -> buyer digit -> Enter
  await page.keyboard.type("jahmyr");
  await page.keyboard.press("Enter");
  assert.ok(await page.locator("#salecard:not(.hide)").count(), "sale card opens");
  assert.ok((await page.locator("#sc-head").innerText()).includes("Jahmyr Gibbs"));
  assert.ok((await page.locator("#sc-money").innerText()).includes("My max"), "card shows my max");
  await page.keyboard.type("105");
  await page.keyboard.press("Enter");            // -> buyer field
  await page.keyboard.type("2");                 // Cole
  await page.keyboard.press("Enter");            // commit
  let st = await page.evaluate(() => ({ s: S.sales.at(-1), cole: C.teams[1], gone: !availablePlayers().some(p => p.name === "Jahmyr Gibbs") }));
  assert.deepEqual([st.s.name, st.s.price, st.s.buyer], ["Jahmyr Gibbs", 105, 1], "sale recorded");
  assert.equal(st.cole.remaining, 95); assert.equal(st.cole.open, 11);
  assert.equal(st.cole.max, 85, "max = remaining - (open-1)");
  assert.ok(st.gone, "sold player leaves the pool");
  assert.ok(!(await page.evaluate(() => recommendations().buys.some(x => x.p.name === "Jahmyr Gibbs"))), "sold player leaves recs");

  // 3. leaveEmpty raises my max bid
  const le = await page.evaluate(() => { S.leaveEmpty = 2; calc(); const m = C.teams[S.me].max; S.leaveEmpty = 0; calc(); return m; });
  assert.equal(le, 200 - (12 - 1 - 2), "leaveEmpty adjusts my max");

  // 4. inflation: matches the formula exactly, and overpays deflate remaining players
  const inf = await page.evaluate(() => {
    const ref = DATA.players.find(p => p.name === "Bijan Robinson");
    const before = now$(ref);
    const chase = DATA.players.find(p => p.name === "Ja'Marr Chase");
    S.sales.push({ id: pid(chase), name: chase.name, pos: chase.pos, price: base(chase) * 2, buyer: 0 });
    calc();
    const gone = new Set(S.sales.map(s => s.id));
    let pv = 0, pc = 0;
    for (const p of DATA.players) if (p.auction && !gone.has(pid(p))) { pv += base(p); pc++; }
    const expect = (C.remainingCash - C.openLeague) / (pv - pc);
    return { before, after: now$(ref), infl: C.infl, expect };
  });
  assert.ok(Math.abs(inf.infl - inf.expect) < 1e-9, "inflation formula");
  assert.ok(inf.after < inf.before, `overpay deflates the board (${inf.before} -> ${inf.after})`);

  // 5. unknown buyer: league cash + slots move, no team budget does
  const unk = await page.evaluate(() => {
    const before = { cash: C.remainingCash, spent: C.teams.map(t => t.spent).join() };
    const p = DATA.players.find(x => x.name === "Puka Nacua");
    S.sales.push({ id: pid(p), name: p.name, pos: p.pos, price: 80, buyer: null });
    persist(); render();
    return { before, cash: C.remainingCash, spent: C.teams.map(t => t.spent).join(), unk: C.unkCount };
  });
  assert.equal(unk.cash, unk.before.cash - 80, "unknown sale drains league cash");
  assert.equal(unk.spent, unk.before.spent, "no team charged");
  assert.equal(unk.unk, 1);
  assert.ok((await page.locator("#teamgrid").innerText()).includes("Unknown"), "Unknown row shown");

  // 6. bulk catch-up import: fuzzy name, name buyer, missing buyer, duplicate skipped
  await page.click("#catchupbtn");
  await page.fill("#im-text", "tyreek hill 60 cole\ngar wilson 55\njamar chase 40 3");
  await page.waitForTimeout(100);
  const prev = await page.locator("#im-preview").innerText();
  assert.ok(prev.includes("Tyreek Hill") && prev.includes("Cole"), "fuzzy + buyer resolve in preview");
  assert.ok(prev.includes("already sold"), "duplicate flagged");
  const nBefore = await page.evaluate(() => S.sales.length);
  await page.click("#im-apply");
  st = await page.evaluate(() => ({ n: S.sales.length, tail: S.sales.slice(-2) }));
  assert.equal(st.n, nBefore + 2, "2 of 3 lines applied (dupe skipped)");
  assert.equal(st.tail[0].buyer, 1, "name buyer resolved to Cole");
  assert.equal(st.tail[1].buyer, null, "missing buyer -> Unknown");

  // 7. edit a past sale from the feed: price and buyer both recomputed
  await page.locator("#feed div", { hasText: "Tyreek" }).first().click();
  assert.ok(await page.locator("#salecard:not(.hide)").count(), "edit card opens from feed");
  await page.fill("#sc-price", "70");
  await page.fill("#sc-buyer", "4");
  await page.click("#sc-commit");
  st = await page.evaluate(() => ({ s: S.sales.find(s => s.name === "Tyreek Hill"), cole: C.teams[1].spent, drew: C.teams[3].spent }));
  assert.deepEqual([st.s.price, st.s.buyer], [70, 3], "sale edited");
  assert.equal(st.cole, 105, "Cole refunded (only Gibbs left)");
  assert.equal(st.drew, 70, "Drew charged");

  // 8. undo reverts the ACTUAL last action (not "pop the newest sale")
  const CMDZ = process.platform === "darwin" ? "Meta+z" : "Control+z";
  let n = await page.evaluate(() => S.sales.length);
  await page.click("#undobtn");                  // last action was the edit in step 7
  st = await page.evaluate(() => ({ n: S.sales.length, s: S.sales.find(s => s.name === "Tyreek Hill") }));
  assert.equal(st.n, n, "undo of an edit does not delete a sale");
  assert.deepEqual([st.s.price, st.s.buyer], [60, 1], "undo restored the pre-edit price and buyer");
  await page.keyboard.press(CMDZ);               // next: the bulk import (2 sales)
  assert.equal(await page.evaluate(() => S.sales.length), n - 2, "Cmd+Z reverts the whole import");
  await page.click("#search");
  await page.fill("#search", "chase");
  await page.keyboard.press(CMDZ);
  assert.equal(await page.evaluate(() => S.sales.length), n - 2, "Cmd+Z ignored while actually typing");
  await page.fill("#search", "");
  await page.keyboard.press("Escape");

  // 8b. delete a mid-list sale (button must be VISIBLE), then undo restores it
  await page.evaluate(() => { S.sales = [
    { id: "A|WR", name: "Alpha", pos: "WR", price: 10, buyer: 0 },
    { id: "B|WR", name: "Bravo", pos: "WR", price: 20, buyer: 1 },
    { id: "C|WR", name: "Charlie", pos: "WR", price: 30, buyer: 2 }]; persist(); render(); });
  await page.locator("#feed div", { hasText: "Bravo" }).first().click();
  assert.ok(await page.locator("#sc-delete").isVisible(), "Delete button is visible in edit mode");
  await page.click("#sc-delete");
  st = await page.evaluate(() => ({ names: S.sales.map(s => s.name), b1: C.teams[1].spent }));
  assert.deepEqual(st.names, ["Alpha", "Charlie"], "mid-list sale deleted");
  assert.equal(st.b1, 0, "deleted sale's buyer refunded");
  await page.click("#undobtn");
  assert.deepEqual(await page.evaluate(() => S.sales.map(s => s.name)), ["Alpha", "Bravo", "Charlie"], "undo restores a deleted sale");

  // 9. persistence: reload survives; server received state
  n = await page.evaluate(() => S.sales.length);
  await page.reload();
  await page.waitForFunction(() => typeof DATA !== "undefined" && DATA && DATA.players.length > 0);
  assert.equal(await page.evaluate(() => S.sales.length), n, "sales survive reload");
  const stateFile = path.join(__dirname, "..", "data", "auction_state.json");
  const posted = JSON.parse(fs.readFileSync(stateFile, "utf8"));
  assert.ok(Array.isArray(posted.sales) && Array.isArray(posted.teamsCalc), "auction_state.json written with derived fields");

  // 10. XSS: hostile name renders inert everywhere
  const xss = await page.evaluate(() => {
    S.sales.push({ id: null, name: "<img src=x onerror=window.__xss=1>", pos: "?", price: 1, buyer: null });
    persist(); render();
    return { feed: document.querySelector("#feed").innerHTML.includes("&lt;img"), pwned: window.__xss };
  });
  assert.ok(xss.feed && !xss.pwned, "XSS-inert sale names");

  // 11. mid-draft format toggle recomputes without errors
  await page.selectOption("#fmtsel", "ppr");
  await page.waitForTimeout(100);
  assert.equal(await page.evaluate(() => S.fmt), "ppr");
  await page.selectOption("#fmtsel", "gcc");     // back to the league's real scoring

  // 12. roster fill order: WR -> WR, WT1, WT2, WRT, BN; K gated until skill slots done
  const fill = await page.evaluate(() => {
    S.sales = [];
    const wrs = DATA.players.filter(p => p.pos === "WR").slice(0, 5);
    for (const p of wrs) S.sales.push({ id: pid(p), name: p.name, pos: p.pos, price: 10, buyer: S.me });
    calc();
    const labels = assignRoster().filter(s => s.p).map(s => s.lbl);
    const kEarly = needMult("K");
    for (const pos of ["QB", "RB", "TE", "WR", "TE"])  // fill remaining skill: QB,RB,TE,WRT(WR),BN? — pad with more
      { const p = DATA.players.find(x => x.pos === pos && !S.sales.some(s => s.id === pid(x))); S.sales.push({ id: pid(p), name: p.name, pos: p.pos, price: 5, buyer: S.me }); }
    calc();
    const skillDone = assignRoster().filter(s => !["K", "DST"].includes(s.pos)).every(s => s.p);
    return { labels, kEarly, kLate: needMult("K"), skillDone };
  });
  assert.deepEqual(fill.labels, ["WR", "WT1", "WT2", "WRT", "BN1"], "WR fill order: natural, WT, WRT, bench");
  assert.equal(fill.kEarly, 0, "K gated while skill slots open");
  assert.ok(fill.skillDone, "test filled all skill slots");
  assert.equal(fill.kLate, 1, "K wanted once skill slots done");

  // 13. dad-team tilt: buy scores use PHI/PIT boost + NE penalty; NE stars never crack top buys
  const pref = await page.evaluate(() => {
    S.sales = []; calc();
    const buys = recommendations().buys;
    const ajb = DATA.players.find(p => p.name === "A.J. Brown");   // NE in 2026
    return { mults: [PREF.PHI, PREF.PIT, PREF.NE], ajbTeam: ajb?.team,
             neInTop: buys.some(x => x.p.team === "NE"),
             names: buys.map(x => x.p.name) };
  });
  assert.deepEqual(pref.mults, [1.15, 1.15, 0.5], "PREF constants");
  if (pref.ajbTeam === "NE") assert.ok(!pref.neInTop, "Patriots suppressed from top buys: " + pref.names.join(", "));

  // 14. GCCFFL scoring: 0.6 PPR is the default and is fully priced
  const scoring = await page.evaluate(() => ({
    fmt: S.fmt,
    opts: [...document.querySelectorAll("#fmtsel option")].map(o => o.value),
    priced: DATA.players.filter(p => p.auction?.gcc).length,
    sum: DATA.players.reduce((a, p) => a + (p.auction?.gcc ?? 0), 0),
    ecr: DATA.players.filter(p => p.ecr?.gcc).length,
  }));
  assert.equal(scoring.fmt, "gcc", "0.6 scoring is the resting state after a format toggle");
  assert.ok(scoring.opts.includes("gcc"), "0.6 option present");
  assert.ok(scoring.priced >= 150 && Math.abs(scoring.sum - 3000) < 60, "0.6 pool priced and sums to the room: $" + scoring.sum);
  assert.ok(scoring.ecr > 500, "0.6 blended ranks exist");

  // 15. import hardening — the three ways a mistyped catch-up line used to corrupt money silently
  await page.evaluate(() => { S.sales = []; persist(); render(); });
  await page.click("#catchupbtn");
  await page.fill("#im-text", "bijan 88 17\ntyreek hill 60 cloe\njamarr chase 91 dana\njamarr chase 88\nnico collins 30 j");
  await page.waitForTimeout(150);
  const p2 = await page.locator("#im-preview").innerText();
  assert.ok(/not a team #/.test(p2), "out-of-range team # is rejected, not silently used as the price");
  assert.ok(/buyer .*no match/.test(p2), "typo'd buyer is rejected, not silently made Unknown");
  assert.ok(/already sold/.test(p2), "same player twice in ONE paste flagged as dupe");
  assert.ok(/ambiguous/.test(p2), "'j' is ambiguous between Jack and Jon R.");
  await page.click("#im-apply");
  st = await page.evaluate(() => ({ n: S.sales.length, s: S.sales[0] }));
  assert.equal(st.n, 1, "only the one clean line applied");
  assert.deepEqual([st.s.name, st.s.price, st.s.buyer], ["Ja'Marr Chase", 91, 0], "clean line correct");

  // 16. buyer resolution never silently picks the rival Ethan Z over my own team
  const rb = await page.evaluate(() => {
    const orig = S.teams.slice();
    S.teams = [...orig, "Ethan Z"];                    // if the 16th GM turns up after all
    const withRival = resolveBuyer("ethan").buyer;
    S.teams = orig;
    return { solo: resolveBuyer("ethan").buyer, withRival, sam: resolveBuyer("sam").buyer,
             me: resolveBuyer("m").buyer, bad: resolveBuyer("16").buyer, unknown: resolveBuyer("u").buyer };
  });
  assert.equal(rb.solo, 14, "'ethan' -> my team (I'm the only Ethan in a 15-team league)");
  assert.equal(rb.withRival, undefined, "'ethan' -> ambiguous if Ethan Z rejoins, never silently the rival");
  assert.equal(rb.sam, 14, "'sam' -> my team");
  assert.equal(rb.me, 14, "'m' -> me");
  assert.equal(rb.bad, undefined, "out-of-range team # rejected");
  assert.equal(rb.unknown, null, "'u' -> Unknown");

  // 17. injury/news flags load and surface on the sale card (advisory layer, must never break the board)
  const news = await page.evaluate(() => ({ count: Object.keys(NOTES).length, jeanty: NOTES["Ashton Jeanty"] }));
  assert.ok(news.count >= 40, "notes.json loaded: " + news.count);
  assert.ok(news.jeanty && news.jeanty.action, "a known flagged player has an action");
  await page.evaluate(() => { S.sales = []; persist(); render(); });
  await page.fill("#search", "jeanty");
  await page.waitForTimeout(120);
  await page.keyboard.press("Enter");
  const cardNews = await page.locator("#sc-news").innerText();
  assert.ok(/ankle/i.test(cardNews), "sale card shows the injury note: " + cardNews.slice(0, 60));
  await page.keyboard.press("Escape");

  // leave a clean board behind for draft day
  await page.evaluate(() => { S.sales = []; S.leaveEmpty = 0; persist(); render(); });

  assert.deepEqual(errs, [], "no page/console errors");
  console.log("ALL AUCTION CHECKS PASSED");
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
