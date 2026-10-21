const live = f => /IN_PROGRESS|LIVE/i.test(f.status || "");
const final = f => /FINAL|AET|\bFT\b/i.test(f.status || "");
const normalized = value => String(value ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

export function betIdentity(bet) {
  return JSON.stringify([bet.fixtureKey, bet.marketKind, bet.line == null ? null : String(bet.line), bet.selection]);
}

export function validMarkets(fixture) {
  return (fixture.markets || []).filter(m =>
    Array.isArray(m.selections) && m.selections.length > 0 &&
    Array.isArray(m.prices) && m.prices.length === m.selections.length &&
    m.prices.every(p => typeof p === "number" && Number.isFinite(p) && p > 1)
  );
}

export function filterFixtures(fixtures, { liveOnly = false, sport, query = "", date = "all", league = "", favoritesOnly = false, favorites = [], nowMs = Date.now() } = {}) {
  const today = new Date(nowMs);
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const sameDay = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  const terms = normalized(query).trim().split(/\s+/).filter(Boolean);
  return fixtures.filter(f => {
    if (liveOnly && !live(f)) return false;
    if (sport && (f.sport || "soccer") !== sport) return false;
    if (league && f.competition !== league) return false;
    if (favoritesOnly && !favorites.includes(f.key)) return false;
    const text = normalized([f.home, f.away, f.competition, f.country, f.sport].join(" "));
    if (!terms.every(term => text.includes(term))) return false;
    const kickoff = new Date(f.kickoff);
    if (date === "today" && !sameDay(kickoff, today)) return false;
    if (date === "tomorrow" && !sameDay(kickoff, tomorrow)) return false;
    if (date === "upcoming" && (live(f) || final(f) || !(kickoff.getTime() > nowMs))) return false;
    if (date === "results" && !final(f)) return false;
    return true;
  });
}
