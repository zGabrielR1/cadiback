"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, BRL, newDepositId, getAdminSession, setAdminSession, getPlayerSession, setPlayerSession } from "../lib/api";
import { validateCPF, validateEmail, validateName, validatePassword, validateUsername } from "../lib/validation";
import { rememberGame } from "../lib/localCache";
import { useSession } from "../lib/useSession";
import CasinoHome from "./components/CasinoHome";
import SportsHome from "./components/SportsHome";
import AdminPanel from "./components/AdminPanel";
import Header from "./components/Header";
import BottomNav from "./components/BottomNav";
import CashierModal from "./components/CashierModal";
import AccountModal from "./components/AccountModal";
import DetailModal from "./components/DetailModal";
import GameTheater from "./components/GameTheater";
import BetslipTray from "./components/BetslipTray";
import ChatWidget from "./components/ChatWidget";
import PromosView from "./components/PromosView";
import AccountView from "./components/AccountView";
import SlotPanel from "./components/SlotPanel";
import RoulettePanel from "./components/RoulettePanel";
import CrashPanel from "./components/CrashPanel";
import PlinkoPanel from "./components/PlinkoPanel";
import MinesPanel from "./components/MinesPanel";
import DicePanel from "./components/DicePanel";
import KenoPanel from "./components/KenoPanel";

/** Page shell (F1): owns view routing, view-local UI state and the wallet
 * action handlers; every visual block lives in components/ and shared
 * player-session state lives in useSession(). */
export default function Page() {
  const session = useSession();
  const {
    player, setPlayer, profile,
    history, health, asaasAvailable, serverConfig,
    refreshError, busy, setBusy, refresh,
  } = session;

  const [theme, setTheme] = useState("dark");
  const [view, setView] = useState("casino");
  const [admin, setAdmin] = useState(null);
  const [casinoCat, setCasinoCat] = useState("Todos");
  const [liveOnly, setLiveOnly] = useState(false);
  const [catalog, setCatalog] = useState(null);
  const [query, setQuery] = useState("");
  const [sports, setSports] = useState(null);
  const [current, setCurrent] = useState(null);
  const [activeOfficialGame, setActiveOfficialGame] = useState(null);
  const [officialToken, setOfficialToken] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [iframeKey, setIframeKey] = useState(1);
  const [selectedBets, setSelectedBets] = useState([]);
  const [betAmount, setBetAmount] = useState("10");
  const [stake, setStake] = useState(500);
  const [reels, setReels] = useState(["—", "—", "—"]);
  const [selection, setSelection] = useState("red");
  const [ball, setBall] = useState(null);
  const [crashTarget, setCrashTarget] = useState("2.00");
  const [lastRow, setLastRow] = useState(null);
  const [minesCount, setMinesCount] = useState(3);
  const [minesPicks, setMinesPicks] = useState([]);
  const [diceTarget, setDiceTarget] = useState("50");
  const [diceOver, setDiceOver] = useState(false);
  const [kenoSpots, setKenoSpots] = useState(5);
  const [kenoPicks, setKenoPicks] = useState([]);
  const [detailGame, setDetailGame] = useState(null);
  const [favTick, setFavTick] = useState(0);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatLog, setChatLog] = useState([
    { who: "bot", text: "Olá! Pergunte sobre depósitos, saques, bônus, limites ou jogos." },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [win, setWin] = useState(false);
  const [message, setMessage] = useState("");
  const [cashOpen, setCashOpen] = useState(false);
  const [cashTab, setCashTab] = useState("dep");
  const [acctOpen, setAcctOpen] = useState(false);
  // No pre-filled credentials: the form starts empty and both sides
  // validate. The built-in test identity is invisible on the storefront
  // and reachable only through the Ctrl+Shift+T shortcut in the modal.
  const [authMode, setAuthMode] = useState("login");
  const [authErrors, setAuthErrors] = useState({});
  // Cloudflare Turnstile (foundry.turnstile): the widget hands us a token, we
  // send it with the login/signup POST, and the server checks it at siteverify.
  // `authAttempt` is bumped after every submit so the widget is reset — a token
  // is single-use and a retry must mint a fresh one.
  const [turnstileToken, setTurnstileToken] = useState("");
  const [authAttempt, setAuthAttempt] = useState(0);
  const onTurnstileToken = useCallback((token) => {
    setTurnstileToken(token || "");
  }, []);
  const [form, setForm] = useState({
    identifier: "",
    name: "",
    username: "",
    email: "",
    cpf: "",
    password: "",
    pix_key: "",
    bank_code: "",
    agency: "",
    account: "",
    holder_name: "",
  });
  const [depositAmount, setDepositAmount] = useState("100.00");
  const [method, setMethod] = useState("pix");
  const [withdrawAmount, setWithdrawAmount] = useState("20.00");
  const [receipt, setReceipt] = useState("");
  // The open Asaas Pix charge, if any: the cashier shows its QR and polls
  // until the provider confirms, then credits through the books.
  const [pixCharge, setPixCharge] = useState(null);

  const anyModal = cashOpen || acctOpen || !!activeOfficialGame;
  useEffect(() => {
    if (!anyModal) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") {
        if (activeOfficialGame) setActiveOfficialGame(null);
        else if (cashOpen) setCashOpen(false);
        else setAcctOpen(false);
      }
    };
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [anyModal, cashOpen, activeOfficialGame]);

  // Poll the open Pix charge until Asaas confirms it — the webhook may not
  // reach a local instance, and the server settles idempotently, so a poll
  // that races the webhook cannot credit twice.
  useEffect(() => {
    if (!pixCharge || pixCharge.posted || !cashOpen || !player) return undefined;
    let stop = false;
    const check = async () => {
      try {
        const row = await api("POST", "/api/deposit/pix/status", {
          player,
          deposit_id: pixCharge.deposit_id,
        });
        if (stop) return;
        setPixCharge(row);
        if (row.posted) {
          setReceipt("Depósito confirmado: " + BRL(row.amount_minor));
          await refresh();
        }
      } catch (e) {
        /* transient: the next tick tries again */
      }
    };
    const timer = setInterval(check, 5000);
    check();
    return () => {
      stop = true;
      clearInterval(timer);
    };
  }, [pixCharge && pixCharge.deposit_id, pixCharge && pixCharge.posted,
      cashOpen, player, refresh]);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem("casa-theme");
      if (stored) setTheme(stored);
    } catch (e) {}
    setAdmin(getAdminSession());
    // a stored player id logs the visitor back in without the form
    const saved = getPlayerSession();
    if (saved) {
      api("GET", "/api/player?id=" + encodeURIComponent(saved.player_id))
        .then((p) => setPlayer(p.player_id))
        .catch(() => setPlayerSession(null));
    }
    api("GET", "/api/catalog").then(setCatalog).catch(() => {});
  }, []);

  const applyAdminSession = useCallback((next) => {
    setAdminSession(next); // write first: later api() calls read it
    setAdmin(next);
  }, []);

  // The Painel button only renders for a logged-in admin, so the owner
  // reaches the login form through this hidden shortcut (Ctrl+Shift+A).
  useEffect(() => {
    const onKey = (e) => {
      if (e.ctrlKey && e.shiftKey && (e.key === "A" || e.key === "a")) {
        e.preventDefault();
        setView("admin");
        window.scrollTo(0, 0);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      window.localStorage.setItem("casa-theme", theme);
    } catch (e) {}
  }, [theme]);

  useEffect(() => {
    if (!player) return undefined;
    const id = setInterval(() => {
      api("POST", "/api/settle")
        .then((r) => {
          if (r && r.settled > 0) refresh();
        })
        .catch(() => {});
    }, 10000);
    return () => clearInterval(id);
  }, [player, refresh]);

  useEffect(() => {
    if (view !== "sport") return undefined;
    const load = () => api("GET", "/api/sports").then(setSports).catch(() => {});
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [view]);

  const go = (next) => {
    setView(next);
    if (next === "sport" && !sports) {
      api("GET", "/api/sports").then(setSports).catch((e) => setMessage(e.message));
    }
    if (next === "account" || next === "promos") refresh();
    window.scrollTo(0, 0);
  };

  const goSport = (live) => {
    setLiveOnly(!!live);
    go("sport");
  };

  const goCasino = (cat) => {
    setCasinoCat(cat || "Todos");
    go("casino");
  };

  const openCash = () => {
    if (!player) {
      setAcctOpen(true);
      return;
    }
    setAcctOpen(false);
    setCashOpen(true);
  };

  const openAccount = () => (player ? go("account") : setAcctOpen(true));

  const onQuery = (value) => {
    setQuery(value);
    if (view !== "casino") go("casino");
  };

  const allOfficialGames = useMemo(() => {
    return catalog?.provider_demos?.demos || [];
  }, [catalog]);

  const allGames = useMemo(() => {
    const demos = catalog?.provider_demos?.demos || [];
    const reg = catalog?.games || [];
    return [...demos, ...reg];
  }, [catalog]);

  const play = (game) => {
    // the game itself is cached on this machine, not just its id: Recentes
    // then has something to show before (or without) /api/catalog
    rememberGame(game);
    api("POST", "/api/play", { player: player || "", game_id: game.game_id }).catch(() => {});
    setBall(null);
    setLastRow(null);
    setMinesPicks([]);
    if (game.demo_url) {
      const open = async () => {
        let src = game.demo_url;
        let token = null;
        if (player) {
          try {
            const w = await api("POST", "/api/wallet/launch", {
              player,
              game_id: game.game_id,
            });
            token = w.token || null;
            src = w.interposed_url || `/g/${encodeURIComponent(game.game_id)}?token=${encodeURIComponent(w.token)}`;
          } catch (e) {
            /* session refused: fall back to the publisher's own page */
          }
        }
        setOfficialToken(token);
        setActiveOfficialGame({ ...game, launch_url: src });
        setIframeKey((k) => k + 1);
      };
      open();
    } else {
      setCurrent(game.game_id);
      requestAnimationFrame(() => {
        const el = document.getElementById("gameview");
        if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  };

  const readFavs = () => {
    try {
      return JSON.parse(window.localStorage.getItem("casa-favs") || "[]");
    } catch (e) {
      return [];
    }
  };

  const toggleFav = () => {
    if (!detailGame) return;
    const favs = readFavs();
    const next = favs.includes(detailGame.game_id)
      ? favs.filter((id) => id !== detailGame.game_id)
      : [...favs, detailGame.game_id];
    try {
      window.localStorage.setItem("casa-favs", JSON.stringify(next));
    } catch (e) {}
    setFavTick((t) => t + 1);
  };

  const isFav = detailGame ? readFavs().includes(detailGame.game_id) : false;
  void favTick;

  const sendChat = async () => {
    const text = chatInput.trim();
    if (!text) return;
    setChatLog((log) => [...log, { who: "me", text }]);
    setChatInput("");
    try {
      const r = await api("POST", "/api/chat", { player: player || "", message: text });
      setChatLog((log) => [...log, { who: "bot", text: r.reply }]);
    } catch (e) {
      setChatLog((log) => [...log, { who: "bot", text: "central offline — tente de novo" }]);
    }
  };

  // the profile follows the player id: login, register and the
  // boot restore all land here instead of threading refresh() calls
  useEffect(() => {
    if (player) refresh();
  }, [player, refresh]);

  // Test identity for development, behind the Ctrl+Shift+T shortcut in
  // the account modal (invisible to normal users). One press fills the Ana
  // account (email ana.souza@example.com, CPF 529.982.247-25, senha
  // ana1234). Register it once and it persists in the players store; the
  // painel can also create and reset test accounts.
  const fillTestAccount = () => {
    setAuthErrors({});
    if (authMode === "login") {
      setForm((f) => ({
        ...f,
        identifier: "ana.souza@example.com",
        password: "ana1234",
      }));
    } else {
      setForm((f) => ({
        ...f,
        name: "Ana Souza",
        username: "ana.souza",
        email: "ana.souza@example.com",
        cpf: "529.982.247-25",
        password: "ana1234",
        pix_key: "ana.souza@example.com",
        bank_code: "001",
        agency: "1234",
        account: "56789-0",
        holder_name: "Ana Souza",
      }));
    }
  };

  const submitAuth = async () => {
    const errs = {};
    if (authMode === "login") {
      const id = String(form.identifier || "").trim();
      if (!id) errs.identifier = "informe seu usuário, email ou CPF";
      else if (id.includes("@")) {
        const e = validateEmail(id);
        if (e) errs.identifier = e;
      } else if (/^[\d.\-\s]+$/.test(id)) {
        const c = validateCPF(id);
        if (c) errs.identifier = c;
      } else {
        const u = validateUsername(id);
        if (u) errs.identifier = u;
      }
      if (!String(form.password || "")) errs.password = "informe sua senha";
    } else {
      const n = validateName(form.name);
      if (n) errs.name = n;
      const u = validateUsername(form.username);
      if (u) errs.username = u;
      const e = validateEmail(form.email);
      if (e) errs.email = e;
      const c = validateCPF(form.cpf);
      if (c) errs.cpf = c;
      const p = validatePassword(form.password);
      if (p) errs.password = p;
      if (!String(form.pix_key || "").trim())
        errs.pix_key = "informe sua chave Pix";
      // the payout account is optional unless the operator demands it, but
      // a half-filled account is worse than none: validate it as a whole
      // the moment any field is touched
      const bankFields = ["bank_code", "agency", "account", "holder_name"];
      const anyBank = bankFields.some((k) => String(form[k] || "").trim());
      if (serverConfig.require_bank_at_signup || anyBank) {
        if (
          !String(form.bank_code || "").trim() ||
          !String(form.agency || "").trim() ||
          !String(form.account || "").trim()
        )
          errs.bank = "informe banco, agência e conta";
        if (!String(form.holder_name || "").trim())
          errs.holder_name = "informe o titular da conta";
      }
    }
    if (serverConfig.turnstile_enabled && serverConfig.turnstile_site_key &&
        !turnstileToken) {
      errs.turnstile = "confirme que você não é um robô";
    }
    setAuthErrors(errs);
    if (Object.keys(errs).length > 0) return;
    setBusy(true);
    try {
      const turnstile =
        serverConfig.turnstile_enabled && serverConfig.turnstile_site_key
          ? { "cf-turnstile-response": turnstileToken }
          : {};
      const profileRow =
        authMode === "login"
          ? await api("POST", "/api/player/login", {
              identifier: String(form.identifier || "").trim(),
              password: form.password,
              ...turnstile,
            })
          : await api("POST", "/api/player", {
              name: String(form.name || "").trim(),
              username: String(form.username || "").trim(),
              email: String(form.email || "").trim(),
              cpf: String(form.cpf || "").trim(),
              password: form.password,
              pix_key: String(form.pix_key || "").trim(),
              bank: {
                bank_code: String(form.bank_code || "").trim(),
                agency: String(form.agency || "").trim(),
                account: String(form.account || "").trim(),
                holder_name: String(form.holder_name || "").trim(),
              },
              ...turnstile,
            });
      setPlayerSession({ player_id: profileRow.player_id });
      setPlayer(profileRow.player_id);
      setAuthErrors({});
      setAcctOpen(false);
    } catch (e) {
      setAuthErrors({ _: e.message });
    } finally {
      setBusy(false);
      // a token is single-use: reset the widget so a retry mints a new one
      setAuthAttempt((n) => n + 1);
    }
  };

  const deposit = async () => {
    setBusy(true);
    try {
      const amount = Math.round(parseFloat(depositAmount.replace(",", ".")) * 100);
      if (asaasAvailable && method === "pix") {
        // Real Pix: open the charge and let the poll effect confirm it. The
        // modal stays open showing the QR instead of crediting instantly.
        const charge = await api("POST", "/api/deposit/pix", {
          player,
          amount_minor: amount,
          method: "pix",
          deposit_id: newDepositId(),
        });
        setReceipt("");
        setPixCharge(charge);
      } else {
        await api("POST", "/api/deposit", {
          player,
          amount_minor: amount,
          method,
          deposit_id: newDepositId(),
        });
        setCashOpen(false);
        await refresh();
      }
    } catch (e) {
      window.alert("Depósito: " + e.message);
    } finally {
      setBusy(false);
    }
  };

  const withdraw = async () => {
    setBusy(true);
    try {
      const amount = Math.round(parseFloat(withdrawAmount.replace(",", ".")) * 100);
      const row = await api("POST", "/api/withdraw", {
        player,
        amount_minor: amount,
        payout_id: newDepositId(),
      });
      setReceipt(
        "Saque " + BRL(amount) + " → Pix " + row.pix_masked + " · " + row.status
      );
      await refresh();
    } catch (e) {
      window.alert("Saque: " + e.message);
    } finally {
      setBusy(false);
    }
  };

  const spin = async () => {
    setBusy(true);
    try {
      if (!player) {
        setAcctOpen(true);
        throw new Error("entre ou crie sua conta primeiro");
      }
      if (!current) throw new Error("escolha um jogo no lobby");
      const sel = current === "demo:crash-nitro"
        ? crashTarget
        : current === "demo:minas"
          ? `m=${minesCount}:cells=${minesPicks.join(",")}`
          : current === "demo:dados"
            ? `${diceOver ? "over" : "under"}:${diceTarget}`
            : current === "demo:keno"
              ? `${kenoSpots}:${kenoPicks.join(",")}`
              : selection;
      const row = await api("POST", "/api/spin", {
        player,
        game_id: current,
        stake_minor: stake,
        selection: sel,
      });
      setLastRow(row);
      setBall(current === "demo:roulette-europeia"
        ? Number(row.symbols[0]) : null);
      setReels(row.symbols);
      setWin(row.payout_minor > 0);
      setMessage(
        row.payout_minor > 0
          ? "Prêmio " + BRL(row.payout_minor) + " · " + row.tier + " " + row.multiplier + "x"
          : "Sem prêmio · " + row.tier
      );
      await refresh();
    } catch (e) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  };

  const placeBet = async () => {
    if (!player) {
      setAcctOpen(true);
      return;
    }
    if (selectedBets.length === 0) return;
    const totalOdds = selectedBets.reduce((acc, b) => acc * b.price, 1);
    const val = parseFloat(betAmount.replace(",", "."));
    if (isNaN(val) || val <= 0) {
      window.alert("Informe um valor válido.");
      return;
    }
    const stakeMinor = Math.round(val * 100);
    if (
      profile &&
      profile.available_minor + (profile.bonus_minor || 0) < stakeMinor
    ) {
      window.alert("Saldo insuficiente para esta aposta demo.");
      return;
    }
    setBusy(true);
    try {
      const row = await api("POST", "/api/bet", {
        player,
        legs: selectedBets.map((b) => ({
          fixture_key: b.fixtureKey,
          home: b.home,
          away: b.away,
          competition: b.competition,
          market_kind: b.marketKind,
          selection: b.selection,
          price: b.price,
          line: b.line == null ? null : b.line,
        })),
        stake_minor: stakeMinor,
        bet_id: newDepositId(),
      });
      window.alert(
        `✓ Aposta registrada!\n${totalOdds.toFixed(2)} @ combinada\n${selectedBets.map(b => `${b.selection} @ ${b.price.toFixed(2)}`).join("\n")}\nValor: ${BRL(stakeMinor)}\nConsolidação automática pelo resultado real ao fim das partidas — acompanhe no Histórico.`
      );
      setSelectedBets([]);
      refresh();
    } catch (e) {
      window.alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  const claim = async (kind) => {
    if (!player) {
      setAcctOpen(true);
      return;
    }
    setBusy(true);
    try {
      const r = await api("POST", "/api/bonus", { player, kind });
      window.alert(
        (kind === "welcome"
          ? "✓ Bônus de Boas-Vindas creditado: "
          : "✓ Cashback creditado: ") +
          BRL(r.granted_minor) +
          " em bônus. Meta de giro: " +
          BRL(r.target_minor) +
          " — ao atingir, o valor vira saldo retirável automaticamente."
      );
      await refresh();
    } catch (e) {
      window.alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  const removeBet = (b) =>
    setSelectedBets((prev) =>
      prev.filter((x) => !(x.fixtureKey === b.fixtureKey && x.selection === b.selection))
    );

  const selectBet = (b) =>
    setSelectedBets((prev) => {
      const idx = prev.findIndex(
        (x) => x.fixtureKey === b.fixtureKey && x.selection === b.selection
      );
      return idx >= 0 ? prev.filter((_, i) => i !== idx) : [...prev, b];
    });

  const currentGame = allGames.find((g) => g.game_id === current) || null;

  return (
    <>
      <Header
        view={view}
        casinoCat={casinoCat}
        liveOnly={liveOnly}
        query={query}
        profile={profile}
        player={player}
        admin={admin}
        theme={theme}
        onCasino={goCasino}
        onSport={goSport}
        onQuery={onQuery}
        onPromos={() => go("promos")}
        onAdmin={() => go("admin")}
        onTheme={() => setTheme(theme === "light" ? "dark" : "light")}
        onCash={openCash}
        onAccount={openAccount}
      />

      <div className="wrap">
        {view === "casino" ? (
          <>
            <CasinoHome
              catalog={catalog}
              onPlay={play}
              onDetails={setDetailGame}
              history={history}
              onCash={openCash}
              onAccount={openAccount}
              player={!!player}
              query={query}
              onQuery={setQuery}
              initialCategory={casinoCat}
            />
            {currentGame && !currentGame.demo_url ? (
              currentGame.game_id === "demo:roulette-europeia" ? (
                <RoulettePanel
                  game={currentGame}
                  selection={selection}
                  onSelection={setSelection}
                  ball={ball}
                  win={win}
                  message={message}
                  stake={stake}
                  busy={busy}
                  onStake={setStake}
                  onSpin={spin}
                  onClose={() => setCurrent(null)}
                />
              ) : currentGame.game_id === "demo:crash-nitro" ? (
                <CrashPanel
                  game={currentGame}
                  target={crashTarget}
                  onTarget={setCrashTarget}
                  lastRow={lastRow}
                  win={win}
                  message={message}
                  stake={stake}
                  busy={busy}
                  onStake={setStake}
                  onSpin={spin}
                  player={player}
                  onRefresh={refresh}
                  onNeedAccount={() => setAcctOpen(true)}
                  onClose={() => setCurrent(null)}
                />
              ) : currentGame.game_id === "demo:plinko-drops" ? (
                <PlinkoPanel
                  game={currentGame}
                  lastRow={lastRow}
                  win={win}
                  message={message}
                  stake={stake}
                  busy={busy}
                  onStake={setStake}
                  onSpin={spin}
                  onClose={() => setCurrent(null)}
                />
              ) : currentGame.game_id === "demo:minas" ? (
                <MinesPanel
                  game={currentGame}
                  mines={minesCount}
                  onMines={setMinesCount}
                  picks={minesPicks}
                  onPicks={setMinesPicks}
                  lastRow={lastRow}
                  win={win}
                  message={message}
                  stake={stake}
                  busy={busy}
                  onStake={setStake}
                  onSpin={spin}
                  onClose={() => setCurrent(null)}
                />
              ) : currentGame.game_id === "demo:dados" ? (
                <DicePanel
                  game={currentGame}
                  target={diceTarget}
                  onTarget={setDiceTarget}
                  over={diceOver}
                  onOver={setDiceOver}
                  lastRow={lastRow}
                  win={win}
                  message={message}
                  stake={stake}
                  busy={busy}
                  onStake={setStake}
                  onSpin={spin}
                  onClose={() => setCurrent(null)}
                />
              ) : currentGame.game_id === "demo:keno" ? (
                <KenoPanel
                  game={currentGame}
                  spots={kenoSpots}
                  onSpots={setKenoSpots}
                  picks={kenoPicks}
                  onPicks={setKenoPicks}
                  lastRow={lastRow}
                  win={win}
                  message={message}
                  stake={stake}
                  busy={busy}
                  onStake={setStake}
                  onSpin={spin}
                  onClose={() => setCurrent(null)}
                />
              ) : (
                <SlotPanel
                  game={currentGame}
                  reels={reels}
                  win={win}
                  message={message}
                  stake={stake}
                  busy={busy}
                  onStake={setStake}
                  onSpin={spin}
                  onClose={() => setCurrent(null)}
                />
              )
            ) : null}
          </>
        ) : null}

        {view === "sport" ? (
          <SportsHome
            sports={sports}
            liveOnly={liveOnly}
            onSelectBet={selectBet}
            selectedBets={selectedBets}
            onLive={setLiveOnly}
          />
        ) : null}

        {view === "promos" ? (
          <PromosView profile={profile} player={player} busy={busy} onClaim={claim} />
        ) : null}

        {view === "admin" ? (
          <AdminPanel session={admin} onSession={applyAdminSession} />
        ) : null}

        {view === "account" ? (
          <AccountView
            profile={profile}
            player={player}
            health={health}
            history={history}
            refreshError={refreshError}
            onChanged={refresh}
          />
        ) : null}

        <footer>
          Candibet · Plataforma de demonstração e réplica 1:1 de alta fidelidade para uso pessoal e hobby · Nenhum dinheiro real envolvido · Jogos oficiais incorporados diretamente dos provedores · 18+.
        </footer>
      </div>

      <GameTheater
        game={activeOfficialGame}
        allGames={allOfficialGames}
        profile={profile}
        walletToken={officialToken}
        onWallet={() => refresh()}
        isFullscreen={isFullscreen}
        iframeKey={iframeKey}
        onBack={() => { setActiveOfficialGame(null); setOfficialToken(null); }}
        onReload={() => setIframeKey((k) => k + 1)}
        onToggleFullscreen={() => setIsFullscreen(!isFullscreen)}
        onSelect={(g) => {
          play(g);
        }}
      />

      <BetslipTray
        bets={selectedBets}
        profile={profile}
        betAmount={betAmount}
        onBetAmount={setBetAmount}
        busy={busy}
        onRemove={removeBet}
        onClear={() => setSelectedBets([])}
        onPlace={placeBet}
      />

      <DetailModal
        game={detailGame}
        isFav={isFav}
        onPlay={play}
        onToggleFav={toggleFav}
        onClose={() => setDetailGame(null)}
      />

      <CashierModal
        open={cashOpen}
        tab={cashTab}
        onTab={setCashTab}
        method={method}
        onMethod={setMethod}
        depositAmount={depositAmount}
        onDepositAmount={setDepositAmount}
        withdrawAmount={withdrawAmount}
        onWithdrawAmount={setWithdrawAmount}
        receipt={receipt}
        busy={busy}
        onDeposit={deposit}
        onWithdraw={withdraw}
        asaasAvailable={asaasAvailable}
        pixCharge={pixCharge}
        onResetPix={() => setPixCharge(null)}
        onClose={() => setCashOpen(false)}
      />

      <AccountModal
        open={acctOpen}
        mode={authMode}
        form={form}
        errors={authErrors}
        busy={busy}
        requireBank={!!serverConfig.require_bank_at_signup}
        testAccountsEnabled={!!serverConfig.test_accounts_enabled}
        turnstileSiteKey={
          serverConfig.turnstile_enabled
            ? serverConfig.turnstile_site_key || ""
            : ""
        }
        turnstileReset={authAttempt}
        onForm={(next) => {
          setForm(next);
          setAuthErrors({});
        }}
        onMode={setAuthMode}
        onSubmit={submitAuth}
        onTurnstileToken={onTurnstileToken}
        onFillTest={fillTestAccount}
        onClose={() => setAcctOpen(false)}
      />

      <BottomNav
        view={view}
        liveOnly={liveOnly}
        onCasino={goCasino}
        onSport={goSport}
        onAccount={() => go("account")}
        onCash={openCash}
      />

      <ChatWidget
        open={chatOpen}
        log={chatLog}
        input={chatInput}
        onInput={setChatInput}
        onSend={sendChat}
        onToggle={() => setChatOpen((o) => !o)}
      />
    </>
  );
}
