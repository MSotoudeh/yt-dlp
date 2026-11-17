// Real-browser end-to-end check of the Digital Concert Hall bridge (run by tests/e2e/run_dch_e2e.sh).
// Loads the real extension in Chromium, serves a fake https://www.digitalconcerthall.com page that
// holds a FAKE token in localStorage, and waits so the Python side can drive the chain.
const { chromium } = require('playwright');
const fs = require('fs');

const [extDir, profileDir, readyFile, doneFile, fakeToken] = process.argv.slice(2);
const PAGE_URL = 'https://www.digitalconcerthall.com/en/concert/56205';

(async () => {
  const context = await chromium.launchPersistentContext(profileDir, {
    headless: false,
    args: [`--disable-extensions-except=${extDir}`, `--load-extension=${extDir}`, '--no-sandbox'],
  });
  await context.route('https://www.digitalconcerthall.com/**', (route) =>
    route.fulfill({ status: 200, contentType: 'text/html', body: '<html><body>fake concert page</body></html>' }));
  const page = await context.newPage();
  await page.goto(PAGE_URL);
  await page.evaluate(([k, v]) => window.localStorage.setItem(k, v), ['access_token_production', fakeToken]);
  let worker = context.serviceWorkers()[0];
  if (!worker) worker = await context.waitForEvent('serviceworker', { timeout: 15000 });
  fs.writeFileSync(readyFile, 'ready');
  const started = Date.now();
  while (!fs.existsSync(doneFile) && Date.now() - started < 90000) await new Promise((r) => setTimeout(r, 250));
  await context.close();
})().catch((e) => { console.error('E2E_BROWSER_ERROR', e.message); process.exit(1); });
