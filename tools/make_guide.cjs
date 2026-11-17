/* Capture the screenshots used by the how-to guide.
   Needs serve.py running:  NODE_PATH=$(npm root -g) node tools/make_guide.cjs  */
const { chromium } = require("playwright");
const path = require("path");
const SHOT = path.join(__dirname, "..", ".tmp", "guide");
require("fs").mkdirSync(SHOT, { recursive: true });

const shot = (p, name, clip) => p.screenshot({ path: path.join(SHOT, name + ".png"), ...(clip ? { clip } : {}) });

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1400, height: 880 }, deviceScaleFactor: 2 });
  const errs = [];
  page.on("pageerror", e => errs.push("" + e.message));
  await page.goto("http://localhost:8712/auction.html");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.waitForFunction(() => typeof DATA !== "undefined" && DATA && DATA.players.length > 0);
  await page.waitForTimeout(500);

  // 1. empty board
  await shot(page, "01-board");
  // top bar alone (the dashboard strip)
  await shot(page, "02-topbar", { x: 0, y: 34, width: 1400, height: 56 });

  // 2. sale card
  await page.fill("#search", "bijan");
  await page.waitForTimeout(200);
  await page.keyboard.press("Enter");
  await page.waitForTimeout(300);
  await shot(page, "03-salecard");

  // 3. record it, then a few more so the board has life
  await page.fill("#sc-price", "92");
  await page.fill("#sc-buyer", "3");
  await page.waitForTimeout(120);
  await shot(page, "04-buyer", { x: 490, y: 150, width: 470, height: 300 });
  await page.click("#sc-commit");
  await page.waitForTimeout(300);

  await page.evaluate(() => {
    const sell = (q, price, buyer) => {
      const p = DATA.players.find(x => x.name.toLowerCase().includes(q));
      if (p) S.sales.push({ id: pid(p), name: p.name, pos: p.pos, price, buyer });
    };
    sell("jahmyr", 96, 0); sell("ja'marr", 99, 1); sell("nacua", 88, 4);
    sell("smith-njigba", 84, 5); sell("bowers", 52, 6); sell("amon-ra", 80, 7);
    persist(); render();
  });
  await page.waitForTimeout(400);
  await shot(page, "05-live");
  await shot(page, "06-rightpanel", { x: 1090, y: 90, width: 310, height: 700 });

  // 4. nominate modal
  await page.click("#nomsbtn");
  await page.waitForTimeout(400);
  await shot(page, "07-nominate");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);

  // 5. catch up
  await page.click("#catchupbtn");
  await page.fill("#im-text", "kenneth walker 44 paul\nbrock bowers 50 9\nmalik nabers 47");
  await page.waitForTimeout(300);
  await shot(page, "08-catchup");
  await page.click("#im-cancel");
  await page.waitForTimeout(200);

  // 6. fix a sale
  await page.locator("#feed div").first().click();
  await page.waitForTimeout(350);
  await shot(page, "09-fix");
  await page.click("#sc-cancel");
  await page.waitForTimeout(200);

  // 7. setup
  await page.click("#setupbtn");
  await page.waitForTimeout(400);
  await shot(page, "10-setup");
  await page.keyboard.press("Escape");

  // 8. a news-flagged player card
  await page.waitForTimeout(200);
  await page.fill("#search", "jeanty");
  await page.waitForTimeout(250);
  await page.keyboard.press("Enter");
  await page.waitForTimeout(350);
  await shot(page, "11-news", { x: 490, y: 120, width: 470, height: 330 });

  console.log("shots ->", SHOT, errs.length ? "ERRORS: " + errs.join("; ") : "(no errors)");
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
