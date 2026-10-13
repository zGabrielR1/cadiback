"use client";

const STAKES = [
  [200, "R$2"],
  [500, "R$5"],
  [1000, "R$10"],
  [2500, "R$25"],
];

// European wheel red pockets (the rest of 1..36 are black).
const RED = new Set([
  1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27,
  30, 32, 34, 36,
]);

const EVEN_MONEY = [
  ["red", "Vermelho"],
  ["black", "Preto"],
  ["even", "Par"],
  ["odd", "Ímpar"],
  ["low", "1–18"],
  ["high", "19–36"],
];

const ballColor = (n) => (n === 0 ? "green" : RED.has(n) ? "red" : "black");

/** In-house original table game (decision 0021): European
 * single-zero roulette. One selection per round; the page
 * owns stake/spin and receives the drawn ball back. */
export default function RoulettePanel({
  game,
  selection,
  onSelection,
  ball,
  win,
  message,
  stake,
  busy,
  onStake,
  onSpin,
  onClose,
}) {
  if (!game) return null;
  return (
    <div id="gameview" style={{ marginTop: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>{game.title}</h2>
        <button className="ghost" style={{ width: "auto" }} onClick={onClose}>
          ✕ Fechar Roleta
        </button>
      </div>
      <div id="cert">Mesa Original · RTP {game.rtp}% · zero único (casa 2,70%)</div>

      <div className="reels" style={{ minHeight: 64 }}>
        <div
          className={"reel" + (win ? " win" : "")}
          style={{
            width: 56,
            height: 56,
            borderRadius: "50%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 24,
            fontWeight: 800,
            color: "#fff",
            background:
              ball === null ? "var(--mut)"
                : ballColor(ball) === "red" ? "#c0392b"
                : ballColor(ball) === "black" ? "#222"
                : "#2e8b57",
          }}
        >
          {ball === null ? "?" : ball}
        </div>
        <div style={{ alignSelf: "center", fontSize: 13, color: "var(--mut)" }}>
          última bola
        </div>
      </div>

      <div style={{ marginTop: 10 }}>
        <div className="gmeta" style={{ marginBottom: 6 }}>Seleção</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
          {EVEN_MONEY.map(([value, label]) => (
            <button
              key={value}
              className={"qlink" + (selection === value ? " on" : "")}
              onClick={() => onSelection(value)}
              style={{
                background:
                  value === "red" ? "#c0392b"
                    : value === "black" ? "#222"
                    : undefined,
                color:
                  value === "red" || value === "black" ? "#fff" : undefined,
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(9, 1fr)",
            gap: 4,
            maxWidth: 460,
          }}
        >
          <button
            className={"qlink" + (selection === "0" ? " on" : "")}
            onClick={() => onSelection("0")}
            style={{
              background: "#2e8b57",
              color: "#fff",
              fontWeight: 700,
            }}
            aria-label="Zero"
          >
            0
          </button>
          {Array.from({ length: 36 }, (_, i) => i + 1).map((n) => (
            <button
              key={n}
              className={"qlink" + (selection === String(n) ? " on" : "")}
              onClick={() => onSelection(String(n))}
              style={{
                background: RED.has(n) ? "#c0392b" : "#1a1a1a",
                color: "#fff",
              }}
              aria-label={`Número ${n}`}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      <div className="stakeRow">
        {STAKES.map(([value, label]) => (
          <button
            key={value}
            className={stake === value ? "on" : ""}
            onClick={() => onStake(value)}
          >
            {label}
          </button>
        ))}
      </div>
      <button id="spin" disabled={busy} onClick={onSpin}>
        Girar
      </button>
      <div id="msg" className={win ? "ok" : "err"}>
        {message}
      </div>
    </div>
  );
}
