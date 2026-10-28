/** Public fixture links contain a fixture identity and optional public market filters, never session state. */
export function matchKeyFromUrl(value) {
  const key = new URL(value, 'https://local.invalid').searchParams.get('match');
  return key && key.length <= 512 && !/[\u0000-\u001f\u007f]/.test(key) ? key : null;
}

const MARKET_CATEGORIES = new Set(['all', 'result', 'totals', 'discipline', 'corners', 'players', 'other']);
const MARKET_PARAMS = ['marketCategory', 'marketSearch'];

export function matchFiltersFromUrl(value) {
  const url = new URL(value, 'https://local.invalid');
  if (!matchKeyFromUrl(value)) return { category: 'all', query: '' };
  const category = url.searchParams.get('marketCategory');
  const query = url.searchParams.get('marketSearch') || '';
  return {
    category: MARKET_CATEGORIES.has(category) ? category : 'all',
    query: query.length <= 200 && !/[\u0000-\u001f\u007f]/.test(query) ? query : '',
  };
}

export function matchLink(value, key, filters = {}) {
  const url = new URL(value);
  url.search = '';
  url.hash = '';
  url.searchParams.set('match', key);
  if (MARKET_CATEGORIES.has(filters.category) && filters.category !== 'all') url.searchParams.set('marketCategory', filters.category);
  const query = typeof filters.query === 'string' ? filters.query.trim().slice(0, 200) : '';
  if (query && !/[\u0000-\u001f\u007f]/.test(query)) url.searchParams.set('marketSearch', query);
  return url.href;
}

export function navigateMatch(key, { replace = false } = {}) {
  const url = new URL(window.location.href);
  MARKET_PARAMS.forEach(param => url.searchParams.delete(param));
  if (key === null) url.searchParams.delete('match');
  else url.searchParams.set('match', key);
  // Section anchors belong to the previous detail view.
  if (/^#detail-/.test(url.hash)) url.hash = '';
  const next = url.pathname + url.search + url.hash;
  const current = window.location.pathname + window.location.search + window.location.hash;
  if (next !== current) window.history[replace ? 'replaceState' : 'pushState'](null, '', next);
  window.dispatchEvent(new Event('operator-match-change'));
}
