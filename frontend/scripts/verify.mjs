import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const OUT = new URL("../verification/", import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });

const BASE = "http://localhost:3000";

async function login(page) {
  await page.goto(BASE + "/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("Sovereign-Audit-2026!");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(BASE + "/");
}

async function run() {
  const browser = await chromium.launch();

  // --- Desktop screenshots, 1440px ---
  let ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  let page = await ctx.newPage();

  await page.goto(BASE + "/login");
  await page.screenshot({ path: OUT + "01-login-desktop.png" });

  await login(page);
  await page.screenshot({ path: OUT + "02-workbench-empty-desktop.png" });

  // Send a real chat message and capture the full round trip.
  await page.getByPlaceholder("Enter an engineering query or instruction…").fill(
    "What is the wall thickness finding for line L-204 and is it within spec?"
  );
  await page.getByRole("button", { name: "Execute" }).click();
  await page.waitForSelector("text=Autonomy hold", { timeout: 20000 }).catch(() => {});
  await page.screenshot({ path: OUT + "03-workbench-hold-desktop.png" });

  const approveBtn = page.getByRole("button", { name: "Approve action" });
  if (await approveBtn.count()) {
    await approveBtn.click();
    await page.waitForSelector("text=Evidence", { timeout: 30000 }).catch(() => {});
  }
  await page.screenshot({ path: OUT + "04-workbench-completed-desktop.png", fullPage: true });

  await page.goto(BASE + "/documents");
  await page.waitForTimeout(600);
  await page.screenshot({ path: OUT + "05-documents-desktop.png" });

  await page.goto(BASE + "/console");
  await page.waitForTimeout(600);
  await page.screenshot({ path: OUT + "06-console-memory-desktop.png" });

  await page.getByRole("button", { name: "Audit Trail" }).click();
  await page.waitForTimeout(400);
  await page.screenshot({ path: OUT + "07-console-audit-desktop.png" });

  await page.getByRole("button", { name: "Model Registry" }).click();
  await page.waitForTimeout(400);
  await page.screenshot({ path: OUT + "08-console-models-desktop.png" });

  await ctx.close();

  // --- Mobile screenshots, 375px ---
  ctx = await browser.newContext({ viewport: { width: 375, height: 812 } });
  page = await ctx.newPage();

  await page.goto(BASE + "/login");
  await page.screenshot({ path: OUT + "09-login-mobile.png" });

  await login(page);
  await page.screenshot({ path: OUT + "10-workbench-mobile.png" });
  const overflowWorkbench = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);

  await page.goto(BASE + "/documents");
  await page.waitForTimeout(500);
  await page.screenshot({ path: OUT + "11-documents-mobile.png" });
  const overflowDocs = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);

  await page.goto(BASE + "/console");
  await page.waitForTimeout(500);
  await page.screenshot({ path: OUT + "12-console-mobile.png" });
  const overflowConsole = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);

  console.log("Horizontal overflow at 375px — workbench:", overflowWorkbench, "documents:", overflowDocs, "console:", overflowConsole);

  await ctx.close();

  // --- Keyboard focus verification, desktop ---
  ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  page = await ctx.newPage();
  await login(page);
  await page.goto(BASE + "/");
  await page.waitForLoadState("networkidle");
  await page.bringToFront();
  await page.locator("body").click({ position: { x: 700, y: 10 }, force: true });
  const focusOutlines = [];
  for (let i = 0; i < 6; i++) {
    await page.keyboard.press("Tab");
    const info = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el) return null;
      const style = getComputedStyle(el);
      return { tag: el.tagName, text: el.textContent?.slice(0, 30), boxShadow: style.boxShadow };
    });
    focusOutlines.push(info);
  }
  await page.screenshot({ path: OUT + "13-keyboard-focus.png" });
  console.log("Tab sequence focus states:", JSON.stringify(focusOutlines, null, 2));

  // --- prefers-reduced-motion ---
  ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
  page = await ctx.newPage();
  await page.goto(BASE + "/login");
  await page.screenshot({ path: OUT + "14-reduced-motion-login.png" });
  await ctx.close();

  await browser.close();
  console.log("Done. Screenshots written to", OUT);
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
