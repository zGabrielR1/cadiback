import { test } from 'node:test';
import assert from 'node:assert/strict';
import { canCalendarMatch, matchCalendar } from './match-calendar.mjs';

const now = Date.parse('2026-10-27T12:00:00Z');
const fixture = { key: 'soccer:São Paulo/1', home: 'São Paulo', away: 'Santos',
  competition: 'Liga de teste', country: 'Brasil', status: 'STATUS_SCHEDULED', kickoff: '2026-11-01T16:30:00-03:00' };
const unfold = content => content.replace(/\r\n /g, '');

test('calendar preserves the absolute kickoff and includes only a public match link', () => {
  const { content, filename } = matchCalendar(fixture, 'https://example.test/?token=secret&marketSearch=private#secret', now);
  const event = unfold(content);
  assert.match(event, /DTSTART:20261101T193000Z\r\n/);
  assert.match(event, /DTSTAMP:20261027T120000Z\r\n/);
  assert.match(event, /SUMMARY:São Paulo × Santos\r\n/);
  const link = event.match(/^URL:(.+)\r$/m)[1];
  assert.deepEqual([...new URL(link).searchParams], [['match', fixture.key]]);
  assert.equal(new URL(link).hash, '');
  assert.doesNotMatch(event, /secret|private|DTEND|DURATION|VALARM|ATTENDEE|METHOD:/);
  assert.match(event, /não sincroniza alterações/);
  assert.equal(filename, 'sao-paulo-santos.ics');
  assert.ok(content.endsWith('END:VCALENDAR\r\n'));
});

test('only future scheduled matches with explicit timezone and valid identities can export', () => {
  assert.equal(canCalendarMatch(fixture, now), true);
  assert.equal(canCalendarMatch({ ...fixture, status: 'SCHEDULED' }, now), true);
  for (const status of ['LIVE', 'IN_PROGRESS', 'FINAL', 'STATUS_FINAL', 'FT', 'AET', 'CANCELLED', 'POSTPONED', 'SUSPENDED', 'ABANDONED', '', 'UNKNOWN']) {
    assert.equal(canCalendarMatch({ ...fixture, status }, now), false, status);
  }
  for (const kickoff of [null, '', 'not-a-date', '2026-11-01', '2026-11-01T16:30:00', '2026-10-27T12:00:00Z', '2026-10-26T12:00:00Z', '2027-02-30T12:00:00Z', '2027-02-01T24:00:00Z', '2027-02-01T12:00:00+25:00']) {
    assert.equal(canCalendarMatch({ ...fixture, kickoff }, now), false, kickoff);
  }
  for (const key of ['', null, 'x'.repeat(513), 'x\nBEGIN:VEVENT']) {
    assert.equal(canCalendarMatch({ ...fixture, key }, now), false);
  }
  assert.equal(canCalendarMatch(null, now), false);
  assert.throws(() => matchCalendar({ ...fixture, status: 'LIVE' }, 'https://example.test', now), /Horário indisponível/);
});

test('UID survives updated times and labels; no URL credentials enter the calendar', () => {
  const first = unfold(matchCalendar(fixture, 'https://user:password@example.test/', now).content);
  const second = unfold(matchCalendar({ ...fixture, home: 'Renamed', kickoff: '2026-11-02T12:00:00Z' }, 'https://example.test', now + 1000).content);
  assert.equal(first.match(/^UID:.+$/m)[0], second.match(/^UID:.+$/m)[0]);
  assert.doesNotMatch(first, /user:|password/);
  assert.throws(() => matchCalendar(fixture, 'javascript:alert(1)', now), /Link da partida inválido/);
});

test('text escaping and UTF-8 folding keep hostile and long feed labels inside one event', () => {
  const home = 'É⚽'.repeat(70) + '\\,;\r\nBEGIN:VEVENT\r\nATTENDEE:evil';
  const { content, filename } = matchCalendar({ ...fixture, home }, 'https://example.test', now);
  for (const line of content.split('\r\n')) {
    assert.ok(Buffer.byteLength(line, 'utf8') <= 75, line);
    assert.doesNotMatch(line, /\uFFFD/);
  }
  const event = unfold(content);
  assert.equal(event.split('\r\n').filter(line => line === 'BEGIN:VEVENT').length, 1);
  assert.match(event, /\\\\\\,\\;\\nBEGIN:VEVENT\\nATTENDEE:evil/);
  assert.match(filename, /^[a-z0-9-]+\.ics$/);
  assert.ok(filename.length <= 104);
});
