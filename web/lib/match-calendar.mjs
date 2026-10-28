import { matchLink } from './match-link.mjs';

const utc = value => new Date(value).toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
const text = value => String(value ?? '').replace(/\\/g, '\\\\')
  .replace(/\r\n|\r|\n/g, '\\n').replace(/;/g, '\\;').replace(/,/g, '\\,')
  .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, '');

function kickoffTime(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d+)?)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$/i.test(value)) return NaN;
  // Date.parse normalizes impossible dates such as February 30; don't export them.
  const day = new Date(value.slice(0, 10) + 'T00:00:00Z');
  if (!Number.isFinite(day.getTime()) || day.toISOString().slice(0, 10) !== value.slice(0, 10)) return NaN;
  return Date.parse(value);
}

// Fold at UTF-8 boundaries; the continuation space counts toward 75 octets.
function fold(line) {
  const encoder = new TextEncoder();
  let output = '', length = 0;
  for (const character of line) {
    const size = encoder.encode(character).length;
    if (length + size > 75) { output += '\r\n '; length = 1; }
    output += character;
    length += size;
  }
  return output;
}

export function canCalendarMatch(fixture, nowMs = Date.now()) {
  const start = kickoffTime(fixture?.kickoff);
  return !!(fixture && typeof fixture.key === 'string' && fixture.key.length > 0 &&
    fixture.key.length <= 512 && !/[\u0000-\u001f\u007f]/.test(fixture.key) &&
    /^(STATUS_)?SCHEDULED$/i.test(fixture.status || '') &&
    Number.isFinite(start) && start > nowMs &&
    new Date(start).getUTCFullYear() >= 1000 && new Date(start).getUTCFullYear() <= 9999);
}

/** A one-time public event export. No inferred end time or calendar subscription. */
export function matchCalendar(fixture, pageUrl, nowMs = Date.now()) {
  if (!canCalendarMatch(fixture, nowMs)) throw new Error('Horário indisponível para exportar.');
  const url = new URL(matchLink(pageUrl, fixture.key));
  if (!['https:', 'http:'].includes(url.protocol)) throw new Error('Link da partida inválido.');
  url.username = '';
  url.password = '';
  const identity = Array.from(new TextEncoder().encode(fixture.key), byte => byte.toString(16).padStart(2, '0')).join('');
  const summary = `${fixture.home} × ${fixture.away}`;
  const description = [[fixture.competition, fixture.country].filter(Boolean).join(' · '),
    'Horário informado pela fonte. Este arquivo não sincroniza alterações de horário.', url.href].filter(Boolean).join('\n');
  const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Operator//Match Calendar//PT-BR',
    'CALSCALE:GREGORIAN', 'BEGIN:VEVENT', `UID:${identity}@${url.host}`,
    `DTSTAMP:${utc(nowMs)}`, `DTSTART:${utc(fixture.kickoff)}`,
    `SUMMARY:${text(summary)}`, `DESCRIPTION:${text(description)}`, `URL:${url.href}`,
    'TRANSP:TRANSPARENT', 'END:VEVENT', 'END:VCALENDAR'];
  const filename = `${fixture.home}-${fixture.away}`.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 100) || 'partida';
  return { content: lines.map(fold).join('\r\n') + '\r\n', filename: filename + '.ics' };
}
