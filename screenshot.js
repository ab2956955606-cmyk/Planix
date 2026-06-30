const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 800, height: 700 } });
  await page.goto('file:///C:/Users/86183/Desktop/Claude_Demo/note/MyNote.html', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: 'C:/Users/86183/Desktop/Claude_Demo/note/screenshot.png', fullPage: true });
  await browser.close();
  console.log('Screenshot saved!');
})();
