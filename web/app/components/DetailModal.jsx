"use client";

/** Game detail modal shown before launch (F1 extract from page.jsx). */
export default function DetailModal({ game, isFav, onPlay, onToggleFav, onClose }) {
  return (
    <div
      className={"modal" + (game ? " open" : "")}
      tabIndex={-1}
      role="dialog"
      aria-modal="true"
      aria-label="Detalhes do jogo"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {game ? (
        <div className="sheet">
          <h3>{game.title}</h3>
          <p className="sub">
            {(game.provider || "").replace(/_/g, " ")} · {game.category || "Slots"}
            {game.rtp ? ` · RTP ${game.rtp}%` : ""}
          </p>
          <p className="sub" style={{ marginTop: 8 }}>
            {game.demo_url
              ? "Demo gratuita hospedada pelo provedor geral com saldo isolado."
              : "Rodadas simuladas com saldo virtual — nenhuma aposta real."}
          </p>
          <button
            style={{ marginTop: 14 }}
            onClick={() => {
              onPlay(game);
              onClose();
            }}
          >
            ▶ Jogar Agora
          </button>
          <button className="ghost" style={{ marginTop: 8, width: "100%" }} onClick={onToggleFav}>
            {isFav ? "★ Favoritado" : "☆ Adicionar aos Favoritos"}
          </button>
          <button className="ghost" style={{ marginTop: 8, width: "100%" }} onClick={onClose}>
            Fechar
          </button>
        </div>
      ) : null}
    </div>
  );
}
