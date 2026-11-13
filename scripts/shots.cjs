const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const base = process.env.SHOTS_BASE || "http://127.0.0.1:8099";
const out = path.resolve("out/shots");
const routes = [
  ["home", "#/"],
  ["enrol", "#/enrol"],
  ["capture", "#/capture"],
  ["capture-child", "#/capture/child"],
  ["review", "#/review"],
  ["cohort", "#/cohort"],
  ["about", "#/about"],
  ["p-SYN-C-0102", "#/p/SYN-C-0102"],
  ["p-SYN-C-0104", "#/p/SYN-C-0104"],
  ["p-SYN-A-0203", "#/p/SYN-A-0203"],
  ["p-SYN-A-0204", "#/p/SYN-A-0204"],
  ["p-SYN-A-0205", "#/p/SYN-A-0205"],
  ["p-SYN-A-0205-history", "#/p/SYN-A-0205/history"],
  ["p-SYN-C-0101-history", "#/p/SYN-C-0101/history"],
  ["replay-SYN-A-0204", "#/p/SYN-A-0204/replay"],
  ["replay-SYN-C-0104", "#/p/SYN-C-0104/replay"],
  ["crossover", "#/crossover"],
  ["review-SYN-C-0102", "#/review/SYN-C-0102"],
];
const widths = [
  [1440, 900],
  [390, 844],
];

(async () => {
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ channel: "chrome" });
  const errors = [];
  for (const lang of ["en", "ar"]) {
    const context = await browser.newContext();
    await context.addInitScript((value) => {
      localStorage.setItem("nodal-screen-lang", value);
    }, lang);
    const page = await context.newPage();
    page.on("pageerror", (err) => errors.push(String(err)));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    for (const [name, hash] of routes) {
      for (const [width, height] of widths) {
        errors.length = 0;
        await page.setViewportSize({ width, height });
        await page.goto(`${base}/${hash}`, { waitUntil: "networkidle" });
        await page.waitForSelector("#view h1");
        if (hash === "#/review/SYN-C-0102") {
          await page.waitForSelector("[data-decision='confirm']");
          await page.click("[data-decision='confirm']");
          await page.waitForSelector("#fhir");
          await page.reload({ waitUntil: "networkidle" });
          await page.waitForSelector("#fhir");
        }
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
        if (overflow) throw new Error(`horizontal scroll ${name} ${lang} ${width}`);
        if (errors.length) throw new Error(errors.join("\n"));
        await page.screenshot({ path: path.join(out, `${name}-${lang}-${width}.png`) });
      }
    }
    await context.close();
  }
  await browser.close();
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
