/* Run against a production build served locally. Optional dependency: playwright. */
const { chromium, webkit, firefox } = require(
  process.env.PLAYWRIGHT_MODULE || "playwright",
);
const fs = require("fs");
const assert = require("node:assert/strict");
const engines = { chromium, webkit, firefox },
  results = [];
const baseUrl = process.env.SITE_URL || "http://127.0.0.1:4173";
assert(
  ["127.0.0.1", "localhost", "[::1]"].includes(new URL(baseUrl).hostname),
  "Use a local preview",
);
const reportDir =
  process.env.REPORT_DIR ||
  fs.mkdtempSync(
    require("path").join(require("os").tmpdir(), "homepage-smoke-"),
  );
fs.mkdirSync(reportDir, { recursive: true });
const chrome = process.env.CHROMIUM_EXECUTABLE;
async function testEngine(name) {
  const browser = await engines[name].launch(
    name === "chromium" && chrome ? { executablePath: chrome } : {},
  );
  try {
    for (const route of ["/", "/zh_cn/"])
      for (const width of [320, 390, 768, 924, 925, 1024, 1440, 1920]) {
        const context = await browser.newContext({
          viewport: { width, height: 900 },
          reducedMotion: "reduce",
          deviceScaleFactor: width === 390 ? 2 : 1,
        });
        // Exercise the entire first-party experience with every third-party request unavailable.
        await context.route("**/*", (r) =>
          new URL(r.request().url()).hostname === new URL(baseUrl).hostname
            ? r.continue()
            : r.abort(),
        );
        const page = await context.newPage(),
          errors = [];
        page.on("pageerror", (e) => errors.push(e.message));
        await page.goto(baseUrl + route, { waitUntil: "load" });
        await page.evaluate(() => document.fonts.ready);
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth > innerWidth,
          ),
          false,
          `${name} ${route} ${width} overflow`,
        );
        assert.equal(await page.locator("#MathJax-script").count(), 0);
        assert.equal(
          await page
            .locator(
              '.paper-box-text a[href="https://arxiv.org/abs/2610.13348"]',
            )
            .count(),
          1,
        );
        assert.equal(
          await page
            .locator(".resource-badge")
            .evaluateAll((els) => els.some((e) => !e.textContent.trim())),
          false,
        );
        assert.equal(
          await page
            .locator(".resource-badge")
            .first()
            .evaluate((e) => getComputedStyle(e).color),
          "rgb(255, 255, 255)",
        );
        assert.equal(
          await page
            .locator(".author__avatar img")
            .evaluate((i) => i.complete && i.naturalWidth > 0),
          true,
        );
        const menu = page.locator(".greedy-nav__toggle");
        if (await menu.isVisible()) {
          await menu.click();
          assert.equal(await menu.getAttribute("aria-expanded"), "true");
          await page.keyboard.press("Escape");
          assert.equal(await menu.getAttribute("aria-expanded"), "false");
        }
        let publications = page
          .locator("#site-nav a")
          .filter({ hasText: route === "/" ? "Publications" : "论文" });
        if (!(await publications.isVisible())) await menu.click();
        await publications.click();
        assert.equal(new URL(page.url()).hash, "#publications");
        assert.equal(new URL(page.url()).pathname, route);
        const lang = page.locator(".lang-menu__trigger");
        await lang.focus();
        await page.keyboard.press("ArrowDown");
        await page.waitForTimeout(50);
        assert.equal(await lang.getAttribute("aria-expanded"), "true");
        assert.equal(
          await page.locator(".lang-menu__option[href]").getAttribute("href"),
          (route === "/" ? "/zh_cn/" : "/") + "#publications",
        );
        await page.keyboard.press("Escape");
        assert.equal(await lang.getAttribute("aria-expanded"), "false");
        assert.equal(
          await lang.evaluate((e) => e === document.activeElement),
          true,
        );
        const image = page.locator(
          '.paper-image-link[href="/images/paper/t2mem.webp"]',
        );
        await image.focus();
        await page.keyboard.press("Enter");
        assert.equal(
          await page.locator("dialog").evaluate((e) => e.open),
          true,
        );
        assert.equal(
          await page.locator("dialog img").evaluate((i) => i.alt.length > 0),
          true,
        );
        await page.keyboard.press("Escape");
        await page.waitForFunction(
          () => !document.querySelector("dialog").open,
        );
        assert.equal(
          await page.locator("dialog").evaluate((e) => e.open),
          false,
        );
        assert.equal(
          await image.evaluate((e) => e === document.activeElement),
          true,
        );
        await image.press("Space");
        assert.equal(
          await page.locator("dialog").evaluate((e) => e.open),
          true,
        );
        await page.locator(".lightbox-close").click();
        await page.waitForFunction(
          () => !document.querySelector("dialog").open,
        );
        // Scroll through all deferred sections and check every local image after decoding.
        await page.evaluate(async () => {
          for (const i of document.images) {
            if (i.closest("dialog")) continue;
            i.loading = "eager";
            await i.decode().catch(() => {});
          }
        });
        assert.equal(
          await page
            .locator("img[src]")
            .evaluateAll((els) =>
              els
                .filter((i) => !i.closest("dialog"))
                .some((i) => !i.complete || !i.naturalWidth),
            ),
          false,
        );
        await page.evaluate(() =>
          window.scrollTo(0, document.body.scrollHeight),
        );
        await page.waitForTimeout(100);
        await page.locator("#back-to-top").click();
        await page.waitForTimeout(50);
        await page.waitForFunction(() => scrollY === 0);
        assert.equal(new URL(page.url()).pathname, route);
        assert.equal(new URL(page.url()).hash, "#top");
        assert.deepEqual(errors, []);
        results.push({ engine: name, route, width, checks: "pass" });
        if (name === "chromium" && (width === 390 || width === 1440)) {
          await page.screenshot({
            path: `${reportDir}/final-${route === "/" ? "en" : "zh"}-${width}.png`,
          });
          await image.scrollIntoViewIfNeeded();
          await page.screenshot({
            path: `${reportDir}/final-paper-${route === "/" ? "en" : "zh"}-${width}.png`,
          });
        }
        if (width === 390 || width === 1440) {
          await lang.click();
          await page.locator(".lang-menu__option[href]").click();
          await page.waitForURL(
            (url) => url.pathname === (route === "/" ? "/zh_cn/" : "/"),
          );
          assert.equal(
            new URL(page.url()).pathname,
            route === "/" ? "/zh_cn/" : "/",
          );
          await page.waitForFunction(
            (expected) => document.documentElement.lang === expected,
            route === "/" ? "zh-CN" : "en",
          );
          assert.equal(
            await page.locator("html").getAttribute("lang"),
            route === "/" ? "zh-CN" : "en",
          );
        }
        await context.close();
      }
    // Progressive enhancement: no JavaScript, both languages and all section links remain available.
    for (const route of ["/", "/zh_cn/"]) {
      const context = await browser.newContext({
        javaScriptEnabled: false,
        viewport: { width: 320, height: 900 },
      });
      const p = await context.newPage();
      await p.goto(baseUrl + route);
      assert.equal(
        await p.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        false,
      );
      assert.equal(
        await p.locator(".lang-menu__option[href]").isVisible(),
        true,
      );
      assert.equal(await p.locator('img[src*="t2mem"]').count(), 1);
      assert.equal(
        await p.locator('.visible-links a[href$="#publications"]').isVisible(),
        true,
      );
      assert.equal(
        await p
          .locator('.paper-image-link[href="/images/paper/t2mem.webp"]')
          .count(),
        1,
      );
      await context.close();
      results.push({ engine: name, route, javascript: false, checks: "pass" });
    }
  } finally {
    await browser.close();
  }
}
(async () => {
  for (const name of process.argv.slice(2).length
    ? process.argv.slice(2)
    : ["chromium", "webkit", "firefox"]) {
    await testEngine(name);
    console.log(name, "passed");
  }
  fs.writeFileSync(
    require("path").join(reportDir, "browser-results.json"),
    JSON.stringify(results, null, 2),
  );
})().catch((e) => {
  console.error(e);
  fs.writeFileSync(
    require("path").join(reportDir, "browser-results.json"),
    JSON.stringify({ completed: results, error: String(e) }, null, 2),
  );
  process.exit(1);
});
