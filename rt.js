const { JSDOM, VirtualConsole } = require('jsdom');
const fs = require('fs');

const errors = [];
const vc = new VirtualConsole();
vc.on('jsdomError', e => errors.push(e));
vc.on('error', e => errors.push(e));

(async () => {
  const html = fs.readFileSync('index.html', 'utf8');
  const dom = new JSDOM(html, {
    url: 'http://localhost:8771/',
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    virtualConsole: vc,
    resources: 'usable',
    beforeParse(window) {
      window.fetch = (url, opts) => globalThis.fetch(
        String(url).startsWith('http') ? url : 'http://localhost:8771/' + String(url).replace(/^\.?\//,''),
        opts
      );
    },
  });
  const { window } = dom;
  window.addEventListener('error', e => errors.push(e.error || e));

  let tries = 0;
  while (tries < 30) {
    await new Promise(r => setTimeout(r, 200));
    if (window.document.querySelectorAll('.row-link').length > 0) break;
    tries++;
  }
  const doc = window.document;
  const log = (s) => console.log(s);

  log('--- Boot ---');
  log(`Controllers visible: ${doc.querySelectorAll('.row-link').length}`);
  log(`Title: ${doc.querySelector('#title')?.textContent.trim()}`);
  log(`Conflict pill: ${doc.querySelector('#conflict-pill')?.style.display === 'none' ? '(hidden)' : doc.querySelector('#conflict-pill')?.textContent.trim()}`);

  const routes = [
    ['#/week', '.day-strip', 'day strips'],
    ['#/c/island', '.station-row', 'station rows'],
    ['#/c/island/s/1', '#f-zone', 'zone input'],
    ['#/conflicts', '.conflict-card', 'conflict cards'],
    ['#/settings', '#f-pat', 'PAT input'],
  ];
  for (const [hash, sel, label] of routes) {
    window.location.hash = hash;
    await new Promise(r => setTimeout(r, 150));
    const n = doc.querySelectorAll(sel).length;
    log(`${hash} → ${n} ${label}`);
  }

  if (errors.length) {
    log('--- ERRORS ---');
    for (const e of errors) log(e.message || String(e));
    process.exit(1);
  }
  log('--- No errors ---');
  process.exit(0);
})().catch(e => { console.error('rt.js failed:', e); process.exit(2); });
