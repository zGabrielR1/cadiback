"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api, BRL } from "../../lib/api";
import { readRecent } from "../../lib/localCache";

const QUICK_LINKS = [
  { label: "Todos", icon: "◆", category: "Todos" },
  { label: "Slots", icon: "▦", category: "Slots" },
  { label: "Crash", icon: "🚀", category: "Crash" },
  { label: "Mesa", icon: "▣", category: "Mesa" },
  { label: "Ao vivo", icon: "●", category: "Ao vivo" },
  { label: "Jackpots", icon: "★", category: "Jackpots" },
  { label: "Originais", icon: "✦", category: "Originais" },
  { label: "Promoções", icon: "%", category: "Promoções" },
  { label: "Recentes", icon: "↻", category: "Recentes" },
  { label: "Favoritos", icon: "★", category: "Favoritos" },
];

const CATEGORIES = [
  "Todos",
  "Slots",
  "Crash",
  "Mesa",
  "Ao vivo",
  "Jackpots",
  "Originais",
  "Promoções",
];

function gameIcon(gameId) {
  if (gameId.includes("olympus")) return "⚡";
  if (gameId.includes("bonanza")) return "🍬";
  if (gameId.includes("sugar")) return "🍭";
  if (gameId.includes("bass")) return "🎣";
  if (gameId.includes("starlight")) return "👑";
  if (gameId.includes("dog")) return "🐶";
  if (gameId.includes("wolf")) return "🐺";
  if (gameId.includes("fruit")) return "🍓";
  if (gameId.includes("aviator")) return "✈️";
  if (gameId.includes("space")) return "🚀";
  if (gameId.includes("city")) return "🎲";
  if (gameId.includes("dead")) return "📜";
  if (gameId.includes("roulette")) return "🎯";
  if (gameId.includes("blackjack")) return "🃏";
  if (gameId.includes("baccarat")) return "🂡";
  if (gameId.includes("tiger")) return "🐯";
  if (gameId.includes("mahjong")) return "🀄";
  if (gameId.includes("neon")) return "💎";
  if (gameId.includes("fortune")) return "🪙";
  return "🎰";
}

function tone(gameId) {
  if (gameId.includes("olympus") || gameId.includes("starlight")) return "t-fort";
  if (gameId.includes("aviator") || gameId.includes("space")) return "t-neon";
  if (gameId.includes("bonanza") || gameId.includes("sugar") || gameId.includes("fruit")) return "t-fort";
  if (gameId.includes("roulette") || gameId.includes("blackjack") || gameId.includes("baccarat")) return "t-roy";
  if (gameId.includes("city") || gameId.includes("dead")) return "t-roy";
  if (gameId.includes("dados") || gameId.includes("dice")) return "t-roy";
  return "t-neon";
}

function Section({ title, note, action, onAction, children }) {
  return (
    <section className="panel" style={{ marginTop: 14 }}>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          marginBottom: 10,
        }}
      >
        <h2 style={{ margin: 0 }}>{title}</h2>
        {action ? (
          <button
            className="ghost"
            style={{ width: "auto", margin: 0, padding: "6px 12px", fontSize: 12 }}
            onClick={onAction}
          >
            {action}
          </button>
        ) : null}
      </div>
      {note ? <p className="sub">{note}</p> : null}
      {children}
    </section>
  );
}

function Empty({ children }) {
  return <p style={{ color: "var(--mut)", fontSize: 13 }}>{children}</p>;
}

function CoverArt({ game }) {
  const [stage, setStage] = useState(0);
  const slug = (game.game_id || "").replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "");
  if (stage === 2) return <span style={{ fontSize: 44 }}>{gameIcon(game.game_id)}</span>;
  const src = stage === 1 ? `/games/${slug}.svg` : game.cover || `/games/${slug}.svg`;
  return (
    <img
      src={src}
      alt={game.title || "game"}
      onError={() => setStage((s) => s + 1)}
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
    />
  );
}

/** Unified catalog card for both official provider games and in-house slots */
function GameCard({ game, onPlay, onDetails }) {
  const providerLabel = (game.provider || "").replace(/_/g, " ").toUpperCase();

  return (
    <div className="gcard" onClick={() => (onDetails ? onDetails(game) : onPlay(game))} style={{ cursor: "pointer" }}>
      <div className={"tile " + tone(game.game_id)}>
        <CoverArt game={game} />
        <span
          className="badge"
          style={{
            position: "absolute",
            top: 8,
            left: 8,
            background: "rgba(0,0,0,0.65)",
            color: "var(--acc)",
            border: "1px solid var(--acc)",
            fontSize: 10.5,
          }}
        >
          {game.category || "Slots"}
        </span>
        <div className="play-hover-btn">
          <div className="play-circle">▶</div>
        </div>
      </div>
      <div className="gbody">
        <b style={{ display: "block", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {game.title}
        </b>
        <div className="gmeta" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>{providerLabel}</span>
          {game.rtp ? <span style={{ color: "var(--gold)" }}>RTP {game.rtp}%</span> : null}
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onPlay(game);
          }}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            boxShadow: "var(--glow)",
          }}
        >
          <span style={{ fontSize: 12 }}>▶</span> Jogar Agora
        </button>
      </div>
    </div>
  );
}

export default function CasinoHome({
  catalog,
  onPlay,
  onDetails,
  history,
  onCash,
  onAccount,
  player,
  query,
  onQuery,
  initialCategory,
}) {
  const [category, setCategory] = useState("Todos");
  const [provider, setProvider] = useState("Todos");
  const [banner, setBanner] = useState(0);
  const [sports, setSports] = useState(null);
  const [jackpot, setJackpot] = useState(null);
  const touch = useRef(null);

  useEffect(() => {
    if (initialCategory) setCategory(initialCategory);
  }, [initialCategory]);

  // The jackpot pool now ticks only when real rounds land
  useEffect(() => {
    const load = () => api("GET", "/api/jackpot").then(setJackpot).catch(() => {});
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, []);

  const banners = useMemo(
    () => [
      {
        title: "Gates of Olympus & Aviator",
        sub: "Jogue os maiores sucessos mundiais incorporados com 100% de fidelidade diretamente no site.",
        cta: "Jogar Agora",
        go: "lobby",
      },
      {
        title: "Cassino & Apostas 1:1",
        sub: "Réplica de alta fidelidade para uso pessoal e hobby: saldo virtual, slots, crash e ao vivo.",
        cta: "Explorar Jogos",
        go: "lobby",
      },
      {
        title: "Depósito e Saque Instantâneos",
        sub: "Simulação de pagamentos Pix em tempo real para testar fluxos completos da plataforma.",
        cta: player ? "Ir para o Caixa" : "Entrar / Cadastrar",
        go: "cash",
      },
      {
        title: "Super Odds & Principais Mercados",
        sub: "Cotações reais atualizadas para os principais campeonatos do Brasil e do mundo.",
        cta: "Ver Apostas",
        go: "sports",
      },
    ],
    [player]
  );

  useEffect(() => {
    const id = setInterval(() => setBanner((b) => (b + 1) % banners.length), 6000);
    return () => clearInterval(id);
  }, [banners.length]);

  useEffect(() => {
    const load = () => api("GET", "/api/sports").then(setSports).catch(() => {});
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, []);

  const [trending, setTrending] = useState(null);

  useEffect(() => {
    const load = () => api("GET", "/api/trending").then(setTrending).catch(() => {});
    load();
    const id = setInterval(load, 60000);
    return () => clearInterval(id);
  }, []);

  const [torneios, setTorneios] = useState(null);

  useEffect(() => {
    const load = () => api("GET", "/api/tournaments").then(setTorneios).catch(() => {});
    load();
    const id = setInterval(load, 60000);
    return () => clearInterval(id);
  }, []);

  const [news, setNews] = useState(null);

  useEffect(() => {
    const load = () => api("GET", "/api/news").then(setNews).catch(() => {});
    load();
    const id = setInterval(load, 60000);
    return () => clearInterval(id);
  }, []);

  const [live, setLive] = useState(null);

  useEffect(() => {
    const load = () => api("GET", "/api/live").then(setLive).catch(() => {});
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, []);

  const providerDemos = useMemo(() => {
    return catalog && catalog.provider_demos ? catalog.provider_demos.demos : [];
  }, [catalog]);

  const registry = useMemo(() => {
    return catalog ? catalog.games : [];
  }, [catalog]);

  // Put official provider demos first, followed by original demo slots
  const all = useMemo(() => {
    return [...providerDemos, ...registry];
  }, [providerDemos, registry]);

  const byId = useMemo(() => new Map(all.map((g) => [g.game_id, g])), [all]);

  const providers = useMemo(() => {
    const seen = [];
    for (const g of all) {
      const p = g.provider || "—";
      if (!seen.includes(p)) seen.push(p);
    }
    return ["Todos", ...seen];
  }, [all]);

  const lsRecents = useMemo(() => {
    // re-read on every category switch: picking the Recentes tab re-renders,
    // so plays from another view (or tab) surface without a full reload
    return readRecent();
  }, [category]);

  // The catalog is the truth about a game, but it arrives over the network
  // and may not have arrived at all (cold instance, one bar of signal). A
  // game opened earlier is already on this machine, so the Recentes tab is
  // built from the catalog where they overlap and from the local cache
  // where the catalog is silent — the tab you open in order to play
  // something never being the tab that is still loading.
  const recentGames = useMemo(() => {
    const seen = new Set();
    const out = [];
    for (const r of lsRecents) {
      if (seen.has(r.game_id)) continue;
      seen.add(r.game_id);
      const live = byId.get(r.game_id);
      if (live) out.push(live);
      else if (r.game) out.push({ ...r.game, from_local_cache: true });
    }
    const rounds = history && history.rounds ? history.rounds : [];
    for (let i = rounds.length - 1; i >= 0; i--) {
      const id = rounds[i] && rounds[i].game_id;
      const live = id && byId.get(id);
      if (live && !seen.has(id)) {
        seen.add(id);
        out.push(live);
      }
    }
    return out;
  }, [lsRecents, byId, history]);

  // the cached rows have to be playable too, and a cached row is played by
  // the same handler as any other — it only lacks a few catalog fields, so
  // they are filled in from the cache rather than guarded against
  const playableRecent = useMemo(() => {
    const out = [];
    for (const g of recentGames) {
      if (!g.demo_url && !byId.has(g.game_id)) continue; // in-house rows need the catalog
      out.push(g);
    }
    return out;
  }, [recentGames, byId]);

  const recentOrder = useMemo(
    () => recentGames.map((g) => g.game_id),
    [recentGames]
  );

  // how many of the recents are being served from this machine rather than
  // from the catalog that just arrived
  const cachedCount = useMemo(
    () => recentGames.filter((g) => g.from_local_cache).length,
    [recentGames]
  );

  const favIds = useMemo(() => {
    // same re-read discipline as lsRecents: switching the tab re-reads
    // storage, so a star toggled in the detail modal shows up
    try {
      return new Set(JSON.parse(window.localStorage.getItem("casa-favs") || "[]"));
    } catch (e) {
      return new Set();
    }
  }, [category]);

  const recentIds = useMemo(() => new Set(recentOrder), [recentOrder]);

  // The search box and the provider chip apply to every tab, including the
  // one served from the local cache — so they are separated from the
  // category switch, which is what decides the pool in the first place.
  const matchesScope = (game) => {
    if (query) {
      const q = query.toLowerCase();
      const matchTitle = (game.title || "").toLowerCase().includes(q);
      const matchProvider = (game.provider || "").toLowerCase().includes(q);
      if (!matchTitle && !matchProvider) return false;
    }
    if (provider && provider !== "Todos" && game.provider !== provider) return false;
    return true;
  };

  const matchesCategory = (game) => {
    switch (category) {
      case "Todos":
        return true;
      case "Slots":
        return game.category === "Slots";
      case "Crash":
        return game.category === "Crash";
      case "Mesa":
        return game.category === "Mesa";
      case "Ao vivo":
        return game.category === "Ao vivo";
      case "Jackpots":
        return (
          game.category === "Slots" ||
          game.game_id.includes("olympus") ||
          game.game_id.includes("bonanza") ||
          game.game_id.includes("wolf")
        );
      case "Originais":
        return game.provider === "demo_studio" || game.category === "Originais";
      case "Promoções":
        return game.game_id.includes("olympus") || game.game_id.includes("aviator") || game.game_id.includes("bonanza");
      case "Recentes":
        return recentIds.has(game.game_id);
      case "Favoritos":
        return favIds.has(game.game_id);
      default:
        return game.category === category;
    }
  };

  const matches = (game) => matchesScope(game) && matchesCategory(game);

  const filtered =
    // Recentes is served from the cache-merged list, so it is the only tab
    // that can show a game the catalog has not delivered yet
    category === "Recentes"
      ? playableRecent.filter(matchesScope)
      : all.filter(matches);
  const visible =
    category === "Recentes"
      ? [...filtered].sort(
          (a, b) => recentOrder.indexOf(a.game_id) - recentOrder.indexOf(b.game_id)
        )
      : filtered;
  const featured = all.filter((g) =>
    ["pp:gates-of-olympus", "spribe:aviator", "pp:sweet-bonanza", "pp:spaceman", "pp:sugar-rush", "pp:big-bass-bonanza"].includes(g.game_id)
  );

  const priced = sports
    ? sports.fixtures.filter((f) => f.markets.length > 0).slice(0, 3)
    : [];

  const act = (target) => {
    if (target === "cash") onCash();
    else if (target === "account") onAccount();
    else {
      const el = document.getElementById("lobby");
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  return (
    <>
      <div
        className="hero carousel"
        onTouchStart={(e) => {
          touch.current = e.touches[0].clientX;
        }}
        onTouchEnd={(e) => {
          if (touch.current === null) return;
          const dx = e.changedTouches[0].clientX - touch.current;
          touch.current = null;
          if (Math.abs(dx) < 40) return;
          setBanner((b) => (b + (dx < 0 ? 1 : banners.length - 1)) % banners.length);
        }}
      >
        <div style={{ padding: "34px 28px", width: "100%" }}>
          <h1>{banners[banner].title}</h1>
          <p>{banners[banner].sub}</p>
          <div className="cta">
            <button onClick={() => act(banners[banner].go)}>{banners[banner].cta}</button>
          </div>
          <div className="dots" role="tablist" aria-label="Banners">
            {banners.map((b, i) => (
              <button
                key={b.title}
                role="tab"
                aria-selected={i === banner}
                aria-label={b.title}
                className={i === banner ? "on" : ""}
                onClick={() => setBanner(i)}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="chips" style={{ marginTop: 14 }}>
        {QUICK_LINKS.map((q) => (
          <button
            key={q.label}
            className={"qlink" + (category === q.category ? " on" : "")}
            onClick={() => setCategory(q.category)}
          >
            <span aria-hidden>{q.icon}</span> {q.label}
          </button>
        ))}
      </div>
      <div className="chips" style={{ marginTop: 8 }}>
        {providers.map((p) => (
          <button
            key={p}
            className={"qlink" + (provider === p ? " on" : "")}
            onClick={() => setProvider(p)}
            style={{ fontSize: 11.5, textTransform: "capitalize" }}
          >
            {p === "Todos" ? "Todos os Provedores" : p.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      <div className="layout">
        <aside className="sidebar">
          <div className="side-title">Categorias</div>
          {CATEGORIES.map((c) => (
            <button
              key={c}
              className={"side-item" + (category === c ? " on" : "")}
              onClick={() => setCategory(c)}
              style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
            >
              <span>{c}</span>
              <span style={{ color: "var(--mut)", fontSize: 11 }}>
                {all.filter((g) => {
                  if (provider && provider !== "Todos" && g.provider !== provider) return false;
                  switch (c) {
                    case "Todos":
                      return true;
                    case "Slots":
                      return g.category === "Slots";
                    case "Crash":
                      return g.category === "Crash";
                    case "Mesa":
                      return g.category === "Mesa";
                    case "Ao vivo":
                      return g.category === "Ao vivo";
                    case "Jackpots":
                      return (
                        g.category === "Slots" ||
                        g.game_id.includes("olympus") ||
                        g.game_id.includes("bonanza") ||
                        g.game_id.includes("wolf")
                      );
                    case "Originais":
                      return g.provider === "demo_studio" || g.category === "Originais";
                    case "Promoções":
                      return (
                        g.game_id.includes("olympus") ||
                        g.game_id.includes("aviator") ||
                        g.game_id.includes("bonanza")
                      );
                    default:
                      return g.category === c;
                  }
                }).length}
              </span>
            </button>
          ))}
          <div className="side-title" style={{ marginTop: 18 }}>Buscar Jogo</div>
          <input
            placeholder="Nome do jogo ou provedor…"
            value={query}
            onChange={(e) => onQuery(e.target.value)}
          />
        </aside>

        <div className="main">
          {category === "Todos" && !query && featured.length > 0 ? (
            <Section title="Destaques & Mais Jogados" note="Os títulos mais populares integrados diretamente no site.">
              <div className="rowscroll">
                {featured.map((g) => (
                  <GameCard key={g.game_id} game={g} onPlay={onPlay} onDetails={onDetails} />
                ))}
              </div>
            </Section>
          ) : null}

          <Section
            title={category === "Todos" ? "Todos os Jogos" : category}
            note={`${visible.length} jogo(s) disponível(is) para jogar diretamente`}
            action="Ver Todos"
            onAction={() => {
              setCategory("Todos");
              onQuery("");
            }}
          >
            <div id="lobby">
              {visible.length === 0 ? (
                <Empty>
                  {category === "Recentes"
                    ? "Você ainda não abriu nenhum jogo neste dispositivo — jogue um e ele fica aqui."
                    : `Nenhum jogo encontrado para “${query || category}”.`}
                </Empty>
              ) : (
                <>
                  {/* say where the list came from: a row served from this
                      machine's cache is not a fresh catalog row, and the
                      player should not have to guess which one they got */}
                  {category === "Recentes" && cachedCount > 0 ? (
                    <div className="gmeta" style={{ marginBottom: 10 }}>
                      {cachedCount} deste(s) veio do cache deste dispositivo
                      {catalog ? "" : " — o catálogo ainda não respondeu"}.
                    </div>
                  ) : null}
                  {visible.map((g) => (
                    <GameCard key={g.game_id} game={g} onPlay={onPlay} onDetails={onDetails} />
                  ))}
                </>
              )}
            </div>
          </Section>

          <Section
            title="Ao Vivo Agora"
            note="Quem está jogando e os últimos ganhadores — dados reais do servidor, janela de 15 minutos."
          >
            {live === null ? (
              <Empty>Carregando atividade ao vivo…</Empty>
            ) : (
              <>
                <div className="gmeta" style={{ marginBottom: 8 }}>
                  <span className="badge b-ok">
                    ● {live.active_players}{" "}
                    {live.active_players === 1 ? "jogador" : "jogadores"} ativo
                    {" "}agora
                  </span>
                  {live.active_games.length > 0 ? (
                    <span style={{ color: "var(--mut)", fontSize: 12.5 }}>
                      {" "}· em jogo:{" "}
                      {live.active_games
                        .slice(0, 4)
                        .map((g) => `${g.title} (${g.opens})`)
                        .join(" · ")}
                    </span>
                  ) : null}
                </div>
                {live.latest_wins.length === 0 ? (
                  <Empty>
                    Nenhum ganhador registrado ainda — os prêmios aparecem
                    aqui assim que saírem.
                  </Empty>
                ) : (
                  <div className="news">
                    {live.latest_wins.map((w) => (
                      <div className="news-item" key={`${w.ts}-${w.label}-${w.payout_minor}`}>
                        <span className="badge" style={{ background: "var(--gold)", color: "#1a1a1a" }}>
                          PRÊMIO
                        </span>
                        <div>
                          <b>{w.label}</b> ganhou{" "}
                          <b style={{ color: "var(--gold)" }}>
                            {BRL(w.payout_minor)}
                          </b>{" "}
                          em {w.title}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </Section>

          <Section
            title="Quentes e Frios"
            note="Mais abre e rodada nas últimas 24h, em tempo real."
          >
            {trending === null ? (
              <Empty>Carregando atividade…</Empty>
            ) : trending.hot.length === 0 ? (
              <Empty>Nenhuma atividade nas últimas 24h — seja o primeiro a jogar.</Empty>
            ) : (
              <div className="rowscroll">
                {trending.hot.map((h) => {
                  const g = byId.get(h.game_id);
                  if (!g) return null;
                  return (
                    <div key={h.game_id} style={{ flex: "0 0 auto", width: 190 }}>
                      <GameCard game={g} onPlay={onPlay} onDetails={onDetails} />
                      <div className="sub" style={{ marginTop: 4, fontSize: 12 }}>
                        {h.opens} abre(s) · {h.rounds} rodada(s) em 24h
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            {trending && trending.cold && trending.cold.length > 0 ? (
              <div className="sub" style={{ marginTop: 10, fontSize: 12.5 }}>
                Frios (sem atividade em 24h):{" "}
                {trending.cold
                  .map((id) => (byId.get(id) || {}).title || id)
                  .join(" · ")}
              </div>
            ) : null}
          </Section>

          <Section title="Jackpot Progressivo" note="Prêmio acumulado simulado — cresce com as apostas reais do dia.">
            <div className="jackpot">
              <div>
                <div className="jackpot-label">Mega Jackpot da Casa</div>
                <div className="jackpot-ticker">
                  {jackpot ? BRL(jackpot.pool_minor) : "Carregando…"}
                </div>
                <div style={{ fontSize: 12.5, color: "var(--mut)", marginTop: 4 }}>
                  {jackpot ? jackpot.note : "1% das apostas do dia alimenta o pote progressivo simulado."}
                </div>
              </div>
            </div>
          </Section>

          <Section
            title="Super Odds em Destaque"
            note="Principais partidas com cotações turbinadas da rodada."
          >
            {sports === null ? (
              <Empty>Carregando partidas…</Empty>
            ) : priced.length === 0 ? (
              <Empty>Nenhuma partida com preço disponível no momento.</Empty>
            ) : (
              <div className="rowscroll">
                {priced.map((f) => (
                  <div className="boost" key={f.key}>
                    <div className="boost-kind">{f.competition}</div>
                    <div className="boost-name">
                      {f.home} × {f.away}
                    </div>
                    {f.markets[0].selections.map((sel, i) => (
                      <div className="boost-odd" key={sel}>
                        {sel} {(f.markets[0].prices[i] * 1.1).toFixed(2)}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </Section>

          <Section title="Torneios em Andamento" note={torneios ? torneios.note : "Calculado das rodadas reais de hoje."}>
            <div className="tournaments">
              {torneios === null ? (
                <div className="tournament">
                  <div className="gmeta">Carregando…</div>
                </div>
              ) : torneios.boards.every((b) => b.rows.length === 0) ? (
                <div className="tournament">
                  <div className="gmeta">Nenhuma rodada hoje — o placar aparece assim que sair a 1ª.</div>
                </div>
              ) : (
                torneios.boards.map((b) => (
                  <div className="tournament" key={b.key}>
                    <div>
                      <b>{b.title}</b>
                      <div className="gmeta">
                        {b.rows.length === 0
                          ? "Sem resultados ainda"
                          : b.rows
                              .map((r, i) =>
                                b.key === "biggest_win"
                                  ? `${i + 1}º ${r.label} — ${BRL(r.value_minor)}`
                                  : `${i + 1}º ${r.label} — ${r.value} rodada(s)`
                              )
                              .join(" · ")}
                      </div>
                    </div>
                    <div className="tournament-prize">Hoje</div>
                  </div>
                ))
              )}
            </div>
          </Section>

          <Section title="Notícias da Plataforma">
            <div className="news">
              {news === null ? (
                <Empty>Carregando notícias…</Empty>
              ) : (
                news.items.map((n) => (
                  <div className="news-item" key={n.title}>
                    <span className="badge b-ok">{n.tag}</span>
                    <div>{n.title}</div>
                  </div>
                ))
              )}
            </div>
          </Section>
        </div>
      </div>
    </>
  );
}