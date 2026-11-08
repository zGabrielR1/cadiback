const record = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const optionalText = value => value == null || typeof value === 'string';
const fixtureText = ['sport', 'competition', 'country', 'status', 'progress', 'kickoff'];

/** Reject an invalid refresh as a whole so existing prices cannot appear fresh.
 * Optional data stays optional. Markets have their own validMarkets boundary.
 * Return the original payload: never coerce identities, labels, dates or prices.
 */
export function readSportsFeed(value) {
  if (!record(value) || !Array.isArray(value.fixtures) ||
      !optionalText(value.source) || !optionalText(value.note)) throw new Error('invalid sports feed');
  const keys = new Set();
  for (const fixture of value.fixtures) {
    if (!record(fixture) || typeof fixture.key !== 'string' || !fixture.key.trim() || keys.has(fixture.key) ||
        typeof fixture.home !== 'string' || typeof fixture.away !== 'string' ||
        !fixtureText.every(key => optionalText(fixture[key])) ||
        !['home_score', 'away_score'].every(key => fixture[key] == null ||
          (typeof fixture[key] === 'number' && Number.isFinite(fixture[key])))) {
      throw new Error('invalid sports feed');
    }
    keys.add(fixture.key);
  }
  return value;
}
