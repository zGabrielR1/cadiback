"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, BRL, newDepositId, getAdminSession, setAdminSession, getPlayerSession, setPlayerSession } from "../lib/api";
import { validateCPF, validateCNPJ, validateEmail, validateName, validatePassword, validateUsername } from "../lib/validation";
import { amountMinor, depositAllowed, matchingDepositLimit } from "../lib/money.mjs";
import { rememberGame } from "../lib/localCache";
import { useSession } from "../lib/useSession";
import { useSportsFeed } from "../lib/useSportsFeed";
import CasinoHome from "./components/CasinoHome";
import SportsHome from "./components/SportsHome";
import { betIdentity } from "../lib/sports.mjs";
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
import WheelPanel from "./components/WheelPanel";

/** Page shell (F1): owns view routing, view-local UI state and the wallet
 * action handlers; every visual block lives in components/ and shared
 * player-session state lives in useSession(). */
export default function Page() {
  const session = useSession();
  const {
    player, setPlayer, profile, setProfile,
    history, setHistory, health, asaasAvailable,
    cryptoAvailable, cryptoCoins, serverConfig,
    refreshError, busy, setBusy, refresh,
  } = session;

  const [theme, setTheme] = useState("dark");
  const [view, setView] = useState("sport");
  const authenticated = !!(player && profile?.player_id === player);
  const [pendingCasino, setPendingCasino] = useState(null);
  const [guestPromptDismissed, setGuestPromptDismissed] = useState(false);
  const [guestPromptNearTop, setGuestPromptNearTop] = useState(true);
  const [admin, setAdmin] = useState(null);
  const [casinoCat, setCasinoCat] = useState("Todos");
  const [liveOnly, setLiveOnly] = useState(false);
  const [catalog, setCatalog] = useState(null);
  const [query, setQuery] = useState("");
  const sportsFeed = useSportsFeed(view === "sport");
  const { sports } = sportsFeed;
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
  // Password reset (decision 0068): the raw token arrives in the URL hash and
  // is handed straight to the reset form. It is cleared from the address bar
  // on boot so a reload or a shared screenshot cannot replay it.
  const [authNotice, setAuthNotice] = useState("");
  const [resetToken, setResetToken] = useState("");
  // Cloudflare Turnstile (foundry.turnstile): the widget hands us a token, we
  // send it with the login/signup POST, and the server checks it at siteverify.
  // `authAttempt` is bumped after every submit so the widget is reset — a token
  // is single-use and a retry must mint a fresh one.
  const [turnstileToken, setTurnstileToken] = useState("");
  const [authAttempt, setAuthAttempt] = useState(0);
  // "Lembrar de mim" only affects the login path: checked persists the
  // player id in localStorage, unchecked keeps it in sessionStorage so it
  // dies with the tab. Signup and social login keep the default.
  const [rememberMe, setRememberMe] = useState(true);
  const onTurnstileToken = useCallback((token) => {
    setTurnstileToken(token || "");
  }, []);
  const [form, setForm] = useState({
    identifier: "",
    name: "",
    username: "",
    email: "",
    person_type: "PF",
    cpf: "",
    cnpj: "",
    password: "",
    password_confirm: "",
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
  const [cashError, setCashError] = useState("");
  const [withdrawPixKey, setWithdrawPixKey] = useState("");
  const [depositLimit, setDepositLimit] = useState(null);
  const [limitError, setLimitError] = useState("");
  const [limitRetry, setLimitRetry] = useState(0);
  // The open Asaas Pix charge, if any: the cashier shows its QR and polls
  // until the provider confirms, then credits through the books.
  const [pixCharge, setPixCharge] = useState(null);
  // The open NOWPayments invoice, if any: the cashier shows the pay address
  // and polls until the provider confirms, then credits through the books.
  const [cryptoCharge, setCryptoCharge] = useState(null);
  const [cryptoCoin, setCryptoCoin] = useState("");

  const anyModal = cashOpen || acctOpen || !!activeOfficialGame || !!detailGame;
  // The invitation belongs to the opening view. Once the reader scrolls into
  // the board it slides away instead of sitting on top of a match row.
  useEffect(() => {
    const sync = () => setGuestPromptNearTop(window.scrollY < 560);
    sync();
    window.addEventListener("scroll", sync, { passive: true });
    return () => window.removeEventListener("scroll", sync);
  }, []);
  useEffect(() => {
    if (!anyModal) return undefined;
    const previousFocus = document.activeElement;
    const dialog = document.querySelector(".game-modal, .modal.open");
    const focusable = () => [...(dialog?.querySelectorAll(
      'a[href], button, input:not([type="hidden"]), select, textarea, iframe, [tabindex]'
    ) || [])].filter((el) => !el.disabled && el.tabIndex >= 0 && el.getClientRects().length);
    const focusFirst = () => (focusable()[0] || dialog)?.focus({ preventScroll: true });
    const frame = requestAnimationFrame(() => {
      const input = dialog?.querySelector('input:not([type="hidden"]):not(:disabled)');
      if (input) input.focus({ preventScroll: true });
      else focusFirst();
    });
    const onFocus = (event) => {
      if (dialog && !dialog.contains(event.target)) focusFirst();
    };
    const onKey = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        if (activeOfficialGame) setActiveOfficialGame(null);
        else if (cashOpen) setCashOpen(false);
        else if (acctOpen) setAcctOpen(false);
        else setDetailGame(null);
      }
      if (e.key === "Tab") {
        const items = focusable();
        if (!items.length) { e.preventDefault(); dialog?.focus(); return; }
        if (e.shiftKey && document.activeElement === items[0]) {
          e.preventDefault(); items.at(-1).focus();
        } else if (!e.shiftKey && document.activeElement === items.at(-1)) {
          e.preventDefault(); items[0].focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("focusin", onFocus);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("focusin", onFocus);
      document.body.style.overflow = previous;
      if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true });
    };
  }, [anyModal, cashOpen, acctOpen, activeOfficialGame, detailGame]);

  // Poll the open Pix charge until Asaas confirms it — the webhook may not
  // reach a local instance, and the server settles idempotently, so a poll
  // that races the webhook cannot credit twice.
  useEffect(() => {
    if (!pixCharge || pixCharge.posted || !cashOpen || !player) return undefined;
    let stop = false;
    const check = async () => {
      try {
        const row = await api("POST", "/api/deposit/pix/status", {
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

  // Poll the open crypto invoice until NOWPayments confirms it. Crypto
  // confirmations are slow (a block or two), so the interval is longer; the
  // server settles idempotently, so the poll cannot credit twice.
  useEffect(() => {
    if (!cryptoCharge || cryptoCharge.posted || !cashOpen || !player) return undefined;
    let stop = false;
    const check = async () => {
      try {
        const row = await api("POST", "/api/deposit/crypto/status", {
          deposit_id: cryptoCharge.deposit_id,
        });
        if (stop) return;
        setCryptoCharge(row);
        if (row.posted) {
          setReceipt("Depósito confirmado: " + BRL(row.amount_minor));
          await refresh();
        }
      } catch (e) {
        /* transient: the next tick tries again */
      }
    };
    const timer = setInterval(check, 10000);
    check();
    return () => {
      stop = true;
      clearInterval(timer);
    };
  }, [cryptoCharge && cryptoCharge.deposit_id, cryptoCharge && cryptoCharge.posted,
      cashOpen, player, refresh]);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem("casa-theme");
      if (stored) setTheme(stored);
    } catch (e) {}
    setAdmin(getAdminSession());
    // a stored player session logs the visitor back in without the form;
    // /api/player derives the account from the token (decision 0069)
    const saved = getPlayerSession();
    // refresh() verifies the credential; a network outage must not erase it.
    if (saved) setPlayer(saved.player_id);
    api("GET", "/api/catalog").then(setCatalog).catch(() => {});
  }, []);

  const applyAdminSession = useCallback((next) => {
    setAdminSession(next); // write first: later api() calls read it
    setAdmin(next);
  }, []);

  // The OAuth callback returns the browser to "/#social=<token>" (or
  // "#social_error=<msg>"). A hash never reaches the server, so the one-time
  // token stays out of request logs and referrers; we exchange it here, then
  // clear it so a reload cannot replay it. New and returning accounts both
  // sign in directly; Pix is requested only when needed for a withdrawal.
  useEffect(() => {
    const raw = String(window.location.hash || "");
    if (!raw.startsWith("#social")) return;
    const params = new URLSearchParams(raw.slice(1));
    const token = params.get("social");
    const err = params.get("social_error");
    window.history.replaceState(
      null, "", window.location.pathname + window.location.search);
    if (err) {
      setMessage("Login social: " + err);
      return;
    }
    if (!token) return;
    setBusy(true);
    api("POST", "/api/auth/oauth/session", { token })
      .then((row) => {
        setPlayerSession({ player_id: row.player_id, token: row.player_token });
        setProfile(row);
        setPlayer(row.player_id);
        setAcctOpen(false);
      })
      .catch((e) => setMessage("Login social: " + e.message))
      .finally(() => setBusy(false));
  }, [setPlayer]);

  // The reset email returns the browser to "/#reset=<token>" (decision 0068).
  // A hash never reaches the server, so the one-time token stays out of
  // request logs and referrers; it is removed from the address bar
  // immediately and held only in component state until the form is sent.
  useEffect(() => {
    const raw = String(window.location.hash || "");
    if (!raw.startsWith("#reset")) return;
    const params = new URLSearchParams(raw.slice(1));
    const token = params.get("reset");
    window.history.replaceState(
      null, "", window.location.pathname + window.location.search);
    if (!token) return;
    setResetToken(token);
    setAuthMode("reset");
    setAuthErrors({});
    setAuthNotice("");
    setForm((f) => ({ ...f, password: "", password_confirm: "" }));
    setAcctOpen(true);
  }, []);

  const startSocial = useCallback(async (provider) => {
    // Better Auth (decision 0066): ask the same-origin auth server for the
    // provider URL, then navigate. The call must be same-origin so the OAuth
    // state cookie lands on this host; the bridge route finishes the flow.
    setBusy(true);
    try {
      const callbackURL = "/api/betterauth/bridge?return=" +
        encodeURIComponent(window.location.origin);
      const res = await fetch("/api/betterauth/sign-in/social", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, callbackURL }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.url) {
        throw new Error(data.error || data.message || "login indisponível");
      }
      window.location.href = data.url;
    } catch (e) {
      setMessage("Login social: " + e.message);
      setBusy(false);
    }
  }, [setBusy]);

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
    if (authenticated && pendingCasino) {
      setCasinoCat(pendingCasino);
      setPendingCasino(null);
      setView("casino");
    }
    if (!authenticated) {
      setActiveOfficialGame(null);
      setOfficialToken(null);
      setDetailGame(null);
      setCurrent(null);
      setView((value) => value === "casino" ? "sport" : value);
    }
  }, [authenticated, pendingCasino]);

  const go = (next) => {
    if (next !== view) setQuery("");
    setView(next);
    if (next === "account" || next === "promos") refresh();
    window.scrollTo(0, 0);
  };

  const goSport = (live) => {
    setLiveOnly(!!live);
    go("sport");
  };

  const goCasino = (cat) => {
    if (!authenticated) {
      setPendingCasino(cat || "Todos");
      setAuthMode("login");
      setAuthNotice("Entre na sua conta para acessar o cassino.");
      setAcctOpen(true);
      return;
    }
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

  const logout = async () => {
    // decision 0070: end this device on the server too. The local clear runs
    // even if the call fails — a dead token still ends the local session.
    const request = api("POST", "/api/player/logout").catch(() => {});
    setPlayerSession(null);
    setPlayer(null);
    setProfile(null);
    setHistory(null);
    setAuthErrors({});
    setAuthMode("login");
    setCashOpen(false);
    setAcctOpen(false);
    setPendingCasino(null);
    setView("sport");
    window.scrollTo(0, 0);
    await request;
  };

  const onQuery = (value) => {
    setQuery(value);
    // Search stays within the current public sports or signed-in casino view.
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
    if (!authenticated) { goCasino("Todos"); return; }
    // the game itself is cached on this machine, not just its id: Recentes
    // then has something to show before (or without) /api/catalog
    rememberGame(game);
    api("POST", "/api/play", { game_id: game.game_id }).catch(() => {});
    setBall(null);
    setLastRow(null);
    setMinesPicks([]);
    if (game.demo_url) {
      const launchSession = getPlayerSession()?.token;
      const open = async () => {
        let src = game.demo_url;
        let token = null;
        if (player) {
          try {
            const w = await api("POST", "/api/wallet/launch", {
              game_id: game.game_id,
            });
            token = w.token || null;
            src = w.interposed_url || `/g/${encodeURIComponent(game.game_id)}?token=${encodeURIComponent(w.token)}`;
          } catch (e) {
            /* session refused: fall back to the publisher's own page */
          }
        }
        if (getPlayerSession()?.token !== launchSession) return;
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
      const r = await api("POST", "/api/chat", { message: text });
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
        person_type: "PF",
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
    const forgot = authMode === "forgot";
    const reset = authMode === "reset";
    if (authMode === "login") {
      const id = String(form.identifier || "").trim();
      if (!id) errs.identifier = "informe seu usuário, email, CPF ou CNPJ";
      if (!String(form.password || "")) errs.password = "informe sua senha";
    } else if (forgot) {
      const e = validateEmail(String(form.identifier || "").trim());
      if (e) errs.identifier = e;
    } else if (reset) {
      const p = validatePassword(form.password);
      if (p) errs.password = p;
      if (form.password !== form.password_confirm)
        errs.password_confirm = "as senhas não coincidem";
      if (!resetToken)
        errs._ = "link expirado — peça um novo email";
    } else {
      const n = validateName(form.name);
      if (n) errs.name = n;
      const u = validateUsername(form.username);
      if (u) errs.username = u;
      const e = validateEmail(form.email);
      if (e) errs.email = e;
      const documentKind = form.person_type === "PJ" ? "cnpj" : "cpf";
      const c = documentKind === "cnpj" ? validateCNPJ(form.cnpj) : validateCPF(form.cpf);
      if (c) errs[documentKind] = c;
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
    if ((authMode === "login" || authMode === "register" || forgot) &&
        serverConfig.turnstile_enabled &&
        serverConfig.turnstile_site_key && !turnstileToken) {
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
      let profileRow;
      if (authMode === "login") {
        profileRow = await api("POST", "/api/player/login", {
          identifier: String(form.identifier || "").trim(),
          password: form.password,
          remember: rememberMe,
          ...turnstile,
        });
      } else if (forgot) {
        await api("POST", "/api/player/password/request", {
          identifier: String(form.identifier || "").trim(),
          ...turnstile,
        });
        setAuthErrors({});
        setAuthNotice(
          "Se houver uma conta com esse email, enviamos um link. " +
          "Confira a caixa de entrada e o spam."
        );
        return;
      } else if (reset) {
        const row = await api("POST", "/api/player/password/reset", {
          token: resetToken,
          password: form.password,
        });
        setResetToken("");
      setAuthMode("login");
        setAuthErrors({});
        setAuthNotice("Senha redefinida. Entre com a nova senha.");
        setForm((f) => ({
          ...f,
          identifier: row.username || f.identifier,
          password: "",
          password_confirm: "",
        }));
        return;
      } else {
        profileRow = await api("POST", "/api/player", {
          name: String(form.name || "").trim(),
          username: String(form.username || "").trim(),
          email: String(form.email || "").trim(),
          person_type: form.person_type || "PF",
          cpf: form.person_type === "PJ" ? "" : String(form.cpf || "").trim(),
          cnpj: form.person_type === "PJ" ? String(form.cnpj || "").trim() : "",
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
      }
      setPlayerSession(
        { player_id: profileRow.player_id, token: profileRow.player_token },
        { remember: authMode === "login" ? rememberMe : true },
      );
      setPlayer(profileRow.player_id);
      setAuthErrors({});
        setAuthMode("login");
      setAcctOpen(false);
    } catch (e) {
      setAuthErrors({ _: e.message });
    } finally {
      setBusy(false);
      // a token is single-use: reset the widget so a retry mints a new one
      setAuthAttempt((n) => n + 1);
    }
  };

  const activeDepositLimit = matchingDepositLimit(depositLimit, method,
    cryptoCoin || cryptoCoins[0]?.code || "usdttrc20");

  useEffect(() => {
    setWithdrawPixKey("");
    setPixCharge(null);
    setCryptoCharge(null);
    setReceipt("");
    setCashError("");
    setDepositLimit(null);
  }, [player]);

  useEffect(() => {
    if (!cashOpen || cashTab !== "dep" || !player || pixCharge || cryptoCharge) return;
    let active = true;
    let timer;
    const load = async () => {
      setDepositLimit(null);
      setLimitError("");
      try {
        const coin = cryptoCoin || cryptoCoins[0]?.code || "usdttrc20";
        const quote = await api("GET", `/api/deposit/limits?method=${encodeURIComponent(method)}&pay_currency=${encodeURIComponent(coin)}`);
        if (active) {
          setDepositLimit(quote);
          timer = setTimeout(load, Math.max(1000, ((quote.valid_for_seconds || 60) - 1) * 1000));
        }
      } catch (e) {
        if (active) setLimitError(e.message);
      }
    };
    load();
    return () => { active = false; clearTimeout(timer); };
  }, [cashOpen, cashTab, player, method, cryptoCoin, cryptoCoins, !!profile?.is_test,
      !!pixCharge, !!cryptoCharge, limitRetry]);

  const deposit = async () => {
    setCashError("");
    if (!depositAllowed(depositAmount, activeDepositLimit)) {
      setCashError(activeDepositLimit ? "O mínimo para este depósito é " + BRL(activeDepositLimit.min_minor) + "." : "Aguarde a consulta do mínimo de depósito.");
      return;
    }
    setBusy(true);
    try {
      const amount = amountMinor(depositAmount);
      // A test account never touches the real rail: its deposits are the
      // instant, tagged test credit even when Asaas is configured.
      const realPix = asaasAvailable && method === "pix"
        && !(profile && profile.is_test);
      const realCrypto = cryptoAvailable && method === "crypto"
        && !(profile && profile.is_test);
      if (realPix) {
        // Real Pix: open the charge and let the poll effect confirm it. The
        // modal stays open showing the QR instead of crediting instantly.
        const charge = await api("POST", "/api/deposit/pix", {
          amount_minor: amount,
          method: "pix",
          deposit_id: newDepositId(),
        });
        setReceipt("");
        setPixCharge(charge);
      } else if (realCrypto) {
        // Real crypto: open a NOWPayments invoice, show the pay address, and
        // poll until the provider confirms.
        const charge = await api("POST", "/api/deposit/crypto", {
          amount_minor: amount,
          method: "crypto",
          pay_currency: cryptoCoin || (cryptoCoins[0] && cryptoCoins[0].code) || "usdttrc20",
          deposit_id: newDepositId(),
        });
        setReceipt("");
        setCryptoCharge(charge);
      } else {
        await api("POST", "/api/deposit", {
          amount_minor: amount,
          method,
          deposit_id: newDepositId(),
        });
        setCashOpen(false);
        await refresh();
      }
    } catch (e) {
      setCashError("Depósito: " + e.message);
      setDepositLimit(null);
      setLimitRetry((value) => value + 1);
    } finally {
      setBusy(false);
    }
  };

  const withdraw = async () => {
    setCashError("");
    if (!amountMinor(withdrawAmount)) { setCashError("Informe um valor de saque válido."); return; }
    if (!profile?.pix_registered && !withdrawPixKey.trim()) {
      setCashError("Cadastre uma chave Pix para receber o saque."); return;
    }
    setBusy(true);
    try {
      const amount = amountMinor(withdrawAmount);
      if (!profile?.pix_registered) {
        const updated = await api("POST", "/api/player/pix-key", { pix_key: withdrawPixKey.trim() });
        setProfile(updated);
        setWithdrawPixKey("");
      }
      const row = await api("POST", "/api/withdraw", {
        amount_minor: amount,
        payout_id: newDepositId(),
      });
      setReceipt(
        "Saque " + BRL(amount) + " → Pix " + row.pix_masked + " · " + row.status
      );
      await refresh();
    } catch (e) {
      setCashError("Saque: " + e.message);
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
      const r = await api("POST", "/api/bonus", { kind });
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
      prev.filter((x) => !(betIdentity(x) === betIdentity(b)))
    );

  const selectBet = (b) =>
    setSelectedBets((prev) => {
      const idx = prev.findIndex(
        (x) => betIdentity(x) === betIdentity(b)
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
        player={authenticated}
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
        {view === "casino" && authenticated ? (
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
              ) : currentGame.game_id === "demo:roda-da-sorte" ? (
                <WheelPanel
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
            query={query}
            sports={sports}
            loading={sportsFeed.loading}
            error={sportsFeed.error}
            updatedAt={sportsFeed.updatedAt}
            onRetry={sportsFeed.retry}
            liveOnly={liveOnly}
            onSelectBet={selectBet}
            selectedBets={selectedBets}
            onLive={setLiveOnly}
            authenticated={authenticated}
            onCasino={goCasino}
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
            onLogout={logout}
          />
        ) : null}

        <footer className="site-footer">
          <div className="footer-mark" aria-hidden="true">CANDIBET<span>.</span></div>
          <div className="footer-bottom">
            <p>Candibet · Esportes e entretenimento em um só lugar. · 18+ · Jogue com responsabilidade.</p>
            <nav aria-label="Navegação do rodapé">
              <button type="button" onClick={() => goSport(false)}>Esportes</button>
              <button type="button" onClick={() => goCasino("Todos")}>Cassino</button>
              <button type="button" onClick={() => go("promos")}>Promoções</button>
              <button type="button" onClick={openCash}>Caixa</button>
            </nav>
          </div>
        </footer>
      </div>

      <GameTheater
        game={authenticated ? activeOfficialGame : null}
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
        game={authenticated ? detailGame : null}
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
        onDepositAmount={(value) => { setDepositAmount(value); setCashError(""); }}
        withdrawAmount={withdrawAmount}
        onWithdrawAmount={setWithdrawAmount}
        receipt={receipt}
        error={cashError}
        depositLimit={activeDepositLimit}
        limitError={limitError}
        onRetryLimit={() => setLimitRetry((value) => value + 1)}
        pixRegistered={!!profile?.pix_registered}
        pixMasked={profile?.pix_masked || ""}
        withdrawPixKey={withdrawPixKey}
        onWithdrawPixKey={(value) => { setWithdrawPixKey(value); setCashError(""); }}
        busy={busy}
        onDeposit={deposit}
        onWithdraw={withdraw}
        asaasAvailable={asaasAvailable && !(profile && profile.is_test)}
        pixCharge={pixCharge}
        onResetPix={() => setPixCharge(null)}
        cryptoAvailable={cryptoAvailable && !(profile && profile.is_test)}
        cryptoCharge={cryptoCharge}
        onResetCrypto={() => setCryptoCharge(null)}
        cryptoCoins={cryptoCoins}
        cryptoCoin={cryptoCoin}
        onCryptoCoin={setCryptoCoin}
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
        oauthProviders={
          serverConfig.oauth_enabled ? serverConfig.oauth_providers || [] : []
        }
        remember={rememberMe}
        notice={authNotice}
        passwordResetEnabled={!!serverConfig.password_reset_enabled}
        onRemember={setRememberMe}
        onForm={(next) => {
          setForm(next);
          setAuthErrors({});
          setAuthNotice("");
        }}
        onMode={(next) => {
          setAuthMode(next);
          setAuthErrors({});
          setAuthNotice("");
        }}
        onSubmit={submitAuth}
        onSocial={startSocial}
        onTurnstileToken={onTurnstileToken}
        onFillTest={fillTestAccount}
        onClose={() => {
          setAcctOpen(false);
          setAuthMode("login");
          setAuthErrors({});
          setAuthNotice("");
          setResetToken("");
          setPendingCasino(null);
        }}
      />

      <BottomNav
        view={view}
        liveOnly={liveOnly}
        onCasino={goCasino}
        onSport={goSport}
        onAccount={openAccount}
        onCash={openCash}
      />

      {!authenticated && view === "sport" && !guestPromptDismissed && !acctOpen && !cashOpen ? (
        <aside
          className={"guest-login-card" + (guestPromptNearTop ? "" : " is-away")}
          aria-label="Acesse sua conta"
          aria-hidden={!guestPromptNearTop}
          inert={guestPromptNearTop ? undefined : true}
        >
          <button className="guest-login-dismiss" aria-label="Fechar convite para entrar" onClick={() => setGuestPromptDismissed(true)}>×</button>
          <span className="guest-login-eyebrow">SUA PRÓXIMA JOGADA</span>
          <strong>O esporte é para todos.<br />Sua conta abre mais possibilidades.</strong>
          <p>Continue acompanhando os jogos ou entre para apostar e acessar o cassino.</p>
          <button onClick={() => { setPendingCasino(null); setAuthMode("login"); setAcctOpen(true); }}>Entrar na minha conta <span aria-hidden="true">↗</span></button>
        </aside>
      ) : null}

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
