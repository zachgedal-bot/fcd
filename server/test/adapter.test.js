'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const A = require('../adapter');
const odds = require('./sample_odds.json');
const props = require('./sample_props.json');
const sports = require('./sample_sports.json');

test('selects soccer leagues the desks care about, skipping outrights and other sports', () => {
  const keys = A.selectSoccerSports(sports).map(s => s.key);
  assert.deepEqual(keys, ['soccer_mexico_ligamx', 'soccer_conmebol_copa_libertadores', 'soccer_usa_mls']);
  assert.deepEqual(A.selectSoccerSports(sports, undefined, ['soccer_epl']).map(s => s.key), ['soccer_epl']);
});

test('prefers Pinnacle h2h over a US book when both post the market', () => {
  const row = A.normaliseEvent(odds[0]);
  assert.equal(row.home, 'Cruz Azul'); assert.equal(row.away, 'Toluca');
  assert.equal(row.odds_h, 1.98); assert.equal(row.odds_d, 3.55); assert.equal(row.odds_a, 3.85);
  assert.match(row.note, /^pinnacle/);
  assert.equal(row.odds_over25, 1.87); assert.equal(row.odds_under25, 1.95); // totals only at DraftKings
  assert.equal(row.date, '2026-09-27'); assert.equal(row.days_since_arrival, '');
});

test('falls back to the first preferred book, then consensus median', () => {
  const row = A.normaliseEvent(odds[1]);
  assert.equal(row.odds_h, 1.4); // fanduel is ahead of betmgm in preference
  const cons = A.consensusH2h(odds[1].bookmakers, 'Tigres UANL', 'Puebla');
  assert.equal(cons.odds_a, 7.25); assert.match(cons.book, /consensus\(2\)/);
});

test('event with no bookmakers yields an honest needs-odds row, not fabricated prices', () => {
  const row = A.normaliseEvent(odds[2]);
  assert.equal(row.odds_h, ''); assert.equal(row.odds_a, ''); assert.equal(row.note, 'no h2h market posted');
});

test('draw is required: a two-way h2h is rejected for that book', () => {
  const book = { key: 'x', markets: [{ key: 'h2h', outcomes: [{ name: 'A', price: 1.5 }, { name: 'B', price: 2.5 }] }] };
  assert.equal(A.h2hFromBook(book, 'A', 'B'), null);
});

test('player props: shots line, shots on target, anytime scorer per player', () => {
  const p = A.normalisePlayerProps(props);
  const paulinho = p.players.find(x => x.name === 'Paulinho');
  assert.equal(paulinho.line, 2.5); assert.equal(paulinho.o_over, 1.9); assert.equal(paulinho.o_under, 1.85);
  assert.equal(paulinho.sot.line, 1.5); assert.equal(paulinho.scorer, 2.75);
  const sep = p.players.find(x => x.name === 'Angel Sepulveda');
  assert.equal(sep.line, 1.5); assert.equal(sep.scorer, 2.4); assert.equal(sep.sot, undefined);
});

test('quota headers parse from a Headers-like object', () => {
  const q = A.quotaFromHeaders(new Map([['x-requests-remaining', '480'], ['x-requests-used', '20'], ['x-requests-last', '2']]));
  assert.deepEqual(q, { remaining: 480, used: 20, last_cost: 2 });
});

test('totals: a preferred book without the 2.5 line does not hide another book that posts it', () => {
  const books = [
    { key: 'pinnacle', markets: [{ key: 'totals', outcomes: [{ name: 'Over', price: 1.8, point: 2.75 }, { name: 'Under', price: 2.0, point: 2.75 }] }] },
    { key: 'draftkings', markets: [{ key: 'totals', outcomes: [{ name: 'Over', price: 1.9, point: 2.5 }, { name: 'Under', price: 1.9, point: 2.5 }] }] },
    { key: 'nopoint', markets: [{ key: 'totals', outcomes: [{ name: 'Over', price: 1.5 }, { name: 'Under', price: 2.5 }] }] },
  ];
  assert.deepEqual(A.pickTotals(books), { odds_over25: 1.9, odds_under25: 1.9, book: 'draftkings' });
  assert.equal(A.totalsFromBook(books[2]), null);   // a missing point is never treated as the 2.5 line
});

test('normaliseEvents drops events that have already kicked off', () => {
  const now = Date.parse('2026-09-27T02:00:00Z');
  const rows = A.normaliseEvents(odds, now);
  assert.deepEqual(rows.map(r => r.id), ['evt2', 'evt3']);
  assert.equal(A.normaliseEvents([{ id: 'x', home_team: 'A', away_team: 'B', bookmakers: [] }], now).length, 1); // unparseable time is kept
});

test('player props never pair an Over from one line with an Under from another', () => {
  const ev = { id: 'e', home_team: 'H', away_team: 'A', bookmakers: [
    { key: 'draftkings', markets: [{ key: 'player_shots', outcomes: [{ name: 'Over', description: 'P', price: 1.9, point: 2.5 }] }] },
    { key: 'fanduel', markets: [{ key: 'player_shots', outcomes: [{ name: 'Over', description: 'P', price: 1.7, point: 1.5 }, { name: 'Under', description: 'P', price: 2.1, point: 1.5 }] }] },
  ] };
  const p = A.normalisePlayerProps(ev).players.find(x => x.name === 'P');
  assert.deepEqual({ line: p.line, o_over: p.o_over, o_under: p.o_under, book: p.book }, { line: 1.5, o_over: 1.7, o_under: 2.1, book: 'fanduel' });
});
