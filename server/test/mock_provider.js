/** Fake The Odds API for local end-to-end runs: node server/test/mock_provider.js [port]
 *  Serves the sample payloads with quota headers; rejects apiKey "bad" with 401; "quota" with 429. */
'use strict';
const http = require('http');
const path = require('path');
const sports = require(path.join(__dirname, 'sample_sports.json'));
const odds = require(path.join(__dirname, 'sample_odds.json'));
const props = require(path.join(__dirname, 'sample_props.json'));
let used = 0;
const srv = http.createServer((req, res) => {
  const u = new URL(req.url, 'http://x');
  const key = u.searchParams.get('apiKey');
  const send = (status, body, cost = 0) => { used += cost; res.writeHead(status, { 'content-type': 'application/json', 'x-requests-remaining': String(500 - used), 'x-requests-used': String(used), 'x-requests-last': String(cost) }); res.end(JSON.stringify(body)); };
  if (key === 'bad') return send(401, { message: 'Invalid API key' });
  if (key === 'quota') return send(429, { message: 'quota exceeded' });
  if (u.pathname === '/v4/sports/') return send(200, sports, 0);
  const m = /^\/v4\/sports\/([^/]+)\/odds\/$/.exec(u.pathname);
  if (m) { const cost = (u.searchParams.get('markets') || 'h2h').split(',').length * (u.searchParams.get('regions') || 'us').split(',').length; return send(200, m[1] === 'soccer_mexico_ligamx' ? odds : [], cost); }
  const e = /^\/v4\/sports\/([^/]+)\/events\/([^/]+)\/odds\/$/.exec(u.pathname);
  if (e) return send(200, e[2] === 'evt1' ? props : Object.assign({}, props, { id: e[2], bookmakers: [] }), 3);
  send(404, { message: 'not found' });
});
srv.listen(Number(process.argv[2] || 9911), () => console.log('mock provider on', srv.address().port));
