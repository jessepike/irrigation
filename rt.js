const { JSDOM, VirtualConsole } = require('jsdom');

const errors = [];
const vc = new VirtualConsole();
vc.on('jsdomError', e => errors.push(e));
vc.on('error', e => errors.push(e));

(async () => {
  const dom = await JSDOM.fromURL('http://localhost:8766/', {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    virtualConsole: vc,
    resources: 'usable',
  });
  const { window } = dom;
  window.addEventListener('error', e => errors.push(e.error || e));

  // Wait for fetches with retry
  let tries = 0;
  while (tries < 30) {
    await new Promise(r => setTimeout(r, 200));
    const events = window.document.querySelectorAll('#today-view .event');
    if (events.length > 0) break;
    tries++;
  }
  console.log(`Polled for events: ${tries} ticks`);
  if (errors.length) console.log('Errors:', errors.map(e => e.message || String(e)));

  const doc = window.document;
  console.log('Pill:', JSON.stringify(doc.querySelector('#conflictPill').textContent.trim()));
  console.log('Today events:', doc.querySelectorAll('#today-view .event').length);
  console.log('Data info:', doc.querySelector('#dataInfo')?.textContent.trim() || '(empty)');
  console.log('Today view innerHTML head:', doc.querySelector('#today-view').innerHTML.slice(0, 200));
  process.exit(0);
})();
