/* Keyboard navigation, history, short viewports and native feature fallbacks. */
const { chromium, webkit, firefox } = require(
  process.env.PLAYWRIGHT_MODULE || "playwright",
);
const assert = require("node:assert/strict"),
  fs = require("fs");
const chrome = process.env.CHROMIUM_EXECUTABLE;
const baseUrl = process.env.SITE_URL || "http://127.0.0.1:4173";
assert(
  ["127.0.0.1", "localhost", "[::1]"].includes(new URL(baseUrl).hostname),
  "Use a local preview",
);
const reportDir =
  process.env.REPORT_DIR ||
  fs.mkdtempSync(
    require("path").join(require("os").tmpdir(), "homepage-compat-"),
  );
fs.mkdirSync(reportDir, { recursive: true });
const results = [];
async function run(name) {
  const browser = await { chromium, webkit, firefox }[name].launch(
    name === "chromium" && chrome ? { executablePath: chrome } : {},
  );
  try {
    for (const route of ["/", "/zh_cn/"])
      for (const size of [
        { width: 390, height: 844 },
        { width: 1440, height: 900 },
        { width: 1366, height: 640 },
        { width: 844, height: 390 },
      ]) {
        const context = await browser.newContext({
          viewport: size,
          reducedMotion: "reduce",
        });
        const p = await context.newPage(),
          errors = [];
        p.on("pageerror", (e) => errors.push(e.message));
        await p.goto(baseUrl + route);
        await p.evaluate(() => document.fonts.ready);
        await p.keyboard.press("Tab");
        assert.equal(
          await p
            .locator(".skip-link")
            .evaluate((e) => e === document.activeElement),
          true,
        );
        await p.keyboard.press("Enter");
        await p.waitForURL("**#main-content");
        assert.equal(new URL(p.url()).pathname, route);
        assert.equal(
          await p
            .locator("#main-content")
            .evaluate((e) => e === document.activeElement),
          true,
        );
        const menu = p.locator(".greedy-nav__toggle"),
          lang = p.locator(".lang-menu__trigger");
        if (await menu.isVisible()) {
          await menu.focus();
          await p.keyboard.press("ArrowDown");
          assert.equal(await menu.getAttribute("aria-expanded"), "true");
          assert.equal(
            await p
              .locator(".hidden-links a")
              .first()
              .evaluate((e) => e === document.activeElement),
            true,
          );
          await p.keyboard.press("End");
          assert.equal(
            await p
              .locator(".hidden-links a")
              .last()
              .evaluate((e) => e === document.activeElement),
            true,
          );
          await p.keyboard.press("Escape");
          assert.equal(await menu.getAttribute("aria-expanded"), "false");
          await menu.click();
          await lang.click();
          assert.equal(await menu.getAttribute("aria-expanded"), "false");
          assert.equal(await lang.getAttribute("aria-expanded"), "true");
          await menu.click();
          assert.equal(await lang.getAttribute("aria-expanded"), "false");
          await p.keyboard.press("Escape");
        }
        for (const section of ["publications", "media-mentions"]) {
          const link = p.locator(
            '.masthead__menu-item:not(.masthead__menu-home-item) a[href$="#' +
              section +
              '"]',
          );
          if (!(await link.isVisible())) await menu.click();
          await link.click();
          await p.waitForURL("**#" + section);
          await p.waitForFunction(
            (id) =>
              document.querySelector(
                '.masthead__menu-item a[aria-current="location"]',
              )?.hash ===
              "#" + id,
            section,
          );
          const geometry = await p.locator("#" + section).evaluate((e) => ({
            heading: e.nextElementSibling.getBoundingClientRect().top,
            header: document.querySelector(".masthead").getBoundingClientRect()
              .bottom,
          }));
          assert(
            geometry.heading >= geometry.header - 2,
            JSON.stringify(geometry),
          );
          assert.equal(new URL(p.url()).pathname, route);
        }
        await p.goBack();
        await p.waitForURL("**#publications");
        assert.equal(new URL(p.url()).pathname, route);
        const picture = p.locator(
          '.paper-image-link[href="/images/paper/t2mem.webp"]',
        );
        await picture.click();
        await p.waitForFunction(
          () =>
            document.querySelector(".lightbox-img").complete &&
            document.querySelector(".lightbox-img").naturalWidth > 0,
        );
        // Decoded pixels alone do not prove the dialog has painted in WebKit.
        const previewGeometry = await p
          .locator("dialog")
          .evaluate(async (dialog) => {
            await dialog.querySelector("img").decode();
            await Promise.all(dialog.getAnimations().map((a) => a.finished));
            await new Promise((resolve) =>
              requestAnimationFrame(() => requestAnimationFrame(resolve)),
            );
            return [
              ...dialog.querySelectorAll(
                ".lightbox-img, .lightbox-close, .lightbox-caption",
              ),
            ].map((e) => {
              const r = e.getBoundingClientRect();
              return {
                className: e.className,
                visible:
                  r.width > 0 &&
                  r.height > 0 &&
                  r.top >= 0 &&
                  r.left >= 0 &&
                  r.bottom <= innerHeight + 1 &&
                  r.right <= innerWidth + 1,
              };
            });
          });
        assert(
          previewGeometry.every((e) => e.visible),
          JSON.stringify(previewGeometry),
        );
        if (size.width === 390)
          await p.screenshot({
            path: `${reportDir}/preview-${name}-${route === "/" ? "en" : "zh"}.png`,
          });
        assert.equal(
          await p.locator(".lightbox-caption a").getAttribute("href"),
          baseUrl + "/images/paper/t2mem.webp",
        );
        assert.equal(await p.locator(".lightbox-status").isVisible(), false);
        await p.keyboard.press("Escape");
        await p.waitForFunction(() => !document.querySelector("dialog").open);
        assert.equal(
          await picture.evaluate((e) => e === document.activeElement),
          true,
        );
        if (size.height < 761 && size.width >= 925)
          assert.equal(
            await p
              .locator(".sidebar")
              .evaluate((e) => getComputedStyle(e).position),
            "static",
          );
        assert.equal(
          await p.evaluate(
            () => document.documentElement.scrollWidth > innerWidth,
          ),
          false,
        );
        assert.deepEqual(errors, []);
        results.push({ engine: name, route, viewport: size, status: "pass" });
        await context.close();
      }
    // Explicit feature fallback: a full-size link works when dialog is unavailable.
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      reducedMotion: "reduce",
    });
    await context.addInitScript(() => {
      HTMLDialogElement.prototype.showModal = undefined;
      window.IntersectionObserver = undefined;
      window.ResizeObserver = undefined;
    });
    const p = await context.newPage();
    await p.goto(baseUrl + "/zh_cn/");
    const link = p.locator(
      '.paper-image-link[href="/images/paper/t2mem.webp"]',
    );
    assert.equal(await link.getAttribute("role"), null);
    await link.click();
    await p.waitForURL("**/images/paper/t2mem.webp");
    await p.goBack();
    await p.waitForURL("**/zh_cn/");
    results.push({
      engine: name,
      scenario: "dialog and observer unavailable",
      status: "pass",
    });
    await context.close();
  } finally {
    await browser.close();
  }
}
(async () => {
  for (const name of process.argv.slice(2).length
    ? process.argv.slice(2)
    : ["chromium", "webkit", "firefox"]) {
    await run(name);
    console.log(name, "compatibility passed");
  }
  fs.writeFileSync(
    require("path").join(reportDir, "compat-results.json"),
    JSON.stringify(results, null, 2),
  );
})().catch((e) => {
  console.error(e);
  fs.writeFileSync(
    require("path").join(reportDir, "compat-results.json"),
    JSON.stringify({ completed: results, error: String(e) }, null, 2),
  );
  process.exit(1);
});
