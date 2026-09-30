const { chromium } = require('playwright-core');
/**
 * Site audit: loads each page at desktop and phone widths and reports console errors, failed requests,
 * 4xx/5xx responses, broken links and anchors, buttons that do nothing when clicked, empty panels or
 * canvases, and horizontal overflow.
 *
 *   npm i playwright-core            (once; uses a locally installed Chrome/Chromium)
 *   node tools/site-audit.js https://athlemix.com / /scout /markets /inbox /profile
 *   CHROME=/path/to/chrome node tools/site-audit.js http://localhost:8080
 *
 * Pages default to the After Hours set when none are given.
 */
const BASE = (process.argv[2] || 'http://127.0.0.1:8080').replace(/\/$/, '');
const PAGES = process.argv.length > 3 ? process.argv.slice(3) : ['/', '/after-hours.html?code=4090', '/premium/index.html?tier=plus', '/altitude_fc/altitude_fc_cards.html', '/enter.html'];
const EXEC = process.env.CHROME || ['/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell', '/usr/bin/google-chrome', '/usr/bin/chromium', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'].find(p => { try { return require('fs').existsSync(p); } catch { return false; } });
(async () => {
  const browser = await chromium.launch({ executablePath: EXEC, args: ['--no-sandbox'] });
  const report = [];
  for (const path of PAGES) {
    for (const vp of [{ w: 1400, h: 900 }, { w: 390, h: 844 }]) {
      const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h } });
      const page = await ctx.newPage();
      const issues = [];
      page.on('console', m => { if (['error', 'warning'].includes(m.type())) issues.push(`console.${m.type()}: ${m.text().slice(0, 160)}`); });
      page.on('pageerror', e => issues.push(`pageerror: ${e.message.slice(0, 160)}`));
      page.on('requestfailed', r => issues.push(`requestfailed: ${r.url().replace(BASE, '')} ${r.failure() && r.failure().errorText}`));
      page.on('response', r => { if (r.status() >= 400) issues.push(`http ${r.status()}: ${r.url().replace(BASE, '')}`); });
      try { await page.goto(BASE + path, { waitUntil: 'networkidle', timeout: 20000 }); } catch (e) { issues.push('goto: ' + e.message.slice(0, 120)); }
      await page.waitForTimeout(800);
      // links
      const links = await page.$$eval('a[href]', as => as.map(a => ({ href: a.getAttribute('href'), text: (a.textContent || '').trim().slice(0, 40), hidden: a.hidden || getComputedStyle(a).display === 'none' })));
      for (const l of links) {
        if (l.hidden) continue;
        if (!l.href || l.href === '#' || l.href.startsWith('javascript')) { issues.push(`dead link: "${l.text}" href=${l.href}`); continue; }
        if (l.href.startsWith('#')) { const ok = await page.$(l.href.replace(/[^#\w-]/g, '')); if (!ok) issues.push(`anchor missing: ${l.href} ("${l.text}")`); continue; }
        if (/^https?:/.test(l.href)) continue;
        const u = new URL(l.href, BASE + path).toString();
        try { const r = await ctx.request.get(u); if (r.status() >= 400) issues.push(`link ${r.status()}: ${l.href} ("${l.text}")`); } catch (e) { issues.push(`link err: ${l.href}`); }
      }
      // buttons: click each visible one and see if anything changes
      const btns = await page.$$('button, .btn, [role=button]');
      for (let i = 0; i < btns.length; i++) {
        const b = btns[i]; if (!(await b.isVisible())) continue;
        const tag = await b.evaluate(e => e.tagName), text = (await b.textContent() || '').trim().slice(0, 40);
        if (tag === 'A' || tag === 'LABEL' || (await b.evaluate(e => e.closest('form') && e.type === 'submit')) || (await b.evaluate(e => e.querySelector('input[type=file]')))) continue;
        if (/^(Reload lines|Clear added lines)$/.test(text)) continue; // After Hours no-ops by design when nothing was added or changed
        const snap = () => page.evaluate(() => document.body.innerHTML.length + '|' + location.href + '|' + document.body.className + '|' + [...document.querySelectorAll('textarea,input,select')].map(e => e.value).join(',') + '|' + [...document.querySelectorAll('button')].map(e => e.textContent.trim() + e.disabled).join(','));
        const before = await snap();
        try { await b.click({ timeout: 1500, force: true }); } catch (e) { continue; }
        await page.waitForTimeout(350);
        const after = await snap();
        if (before === after) issues.push(`dead button: "${text}"`);
        await page.evaluate(() => document.querySelectorAll('.sheet').forEach(x => x.remove()));
      }
      // empty panels: visible elements with class containing panel/card and no text
      const empties = await page.$$eval('.panel, .card, canvas, table tbody', els => els.filter(e => { const r = e.getBoundingClientRect(); if (r.width < 40 || r.height < 30) return false; if (e.tagName === 'CANVAS') { const c = e.getContext('2d'); try { const d = c.getImageData(0, 0, e.width, e.height).data; let n = 0; for (let i = 3; i < d.length; i += 4 * 97) if (d[i]) n++; return n === 0; } catch { return false; } } return (e.innerText || '').trim().length === 0; }).map(e => `${e.tagName}${e.id ? '#' + e.id : ''}${e.className ? '.' + String(e.className).split(' ')[0] : ''}`));
      for (const e of empties) issues.push(`empty: ${e}`);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2);
      if (overflow) issues.push('horizontal overflow');
      report.push({ path, vp: `${vp.w}x${vp.h}`, issues: [...new Set(issues)] });
      await ctx.close();
    }
  }
  await browser.close();
  for (const r of report) { console.log(`\n== ${r.path} @ ${r.vp}: ${r.issues.length} issue(s)`); r.issues.forEach(i => console.log('  - ' + i)); }
})();

