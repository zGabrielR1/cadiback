/** One availability rule for public discovery, research and the existing slip. */
export function matchState(fixture) {
  const status = fixture?.status || '';
  const unavailable = /CANCEL|POSTPON|SUSPEND|ABANDON/i.test(status);
  const ended = !unavailable && /FINAL|AET|\bFT\b/i.test(status);
  const live = !unavailable && !ended && /IN_PROGRESS|LIVE/i.test(status);
  const label = /CANCEL/i.test(status) ? 'Cancelada' : /POSTPON/i.test(status) ? 'Adiada'
    : /SUSPEND/i.test(status) ? 'Suspensa' : /ABANDON/i.test(status) ? 'Abandonada'
      : ended ? 'Encerrada' : live ? 'Ao vivo' : 'Pré-jogo';
  return { unavailable, ended, live, label, selectable: !!fixture && !unavailable && !ended };
}
const live = f => matchState(f).live;
const final = f => matchState(f).ended;
const SPORT_TERMS = {
  soccer: "futebol", basketball: "basquete basquetebol", tennis: "tênis tenis",
  hockey: "hóquei hoquei", volleyball: "vôlei voleibol", futsal: "futebol de salão",
  handball: "handebol", esports: "e-sports esportes eletrônicos",
  baseball: "beisebol", football: "futebol americano", rugby: "rúgbi", cricket: "críquete",
};
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
    const text = normalized([f.home, f.away, f.competition, f.country, f.sport, SPORT_TERMS[f.sport || "soccer"]].join(" "));
    if (!terms.every(term => text.includes(term))) return false;
    const kickoff = new Date(f.kickoff);
    if (date === "today" && !sameDay(kickoff, today)) return false;
    if (date === "tomorrow" && !sameDay(kickoff, tomorrow)) return false;
    if (date === "upcoming" && (live(f) || !matchState(f).selectable || !(kickoff.getTime() > nowMs))) return false;
    if (date === "results" && !final(f)) return false;
    return true;
  });
}
