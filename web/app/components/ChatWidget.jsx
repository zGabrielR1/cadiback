"use client";

/** Live-chat triage widget over POST /api/chat (F1 extract from page.jsx).
 * The bot is canned-intent triage, labelled "simulada" in the header. */
export default function ChatWidget({ open, log, input, onInput, onSend, onToggle }) {
  return (
    <>
      {open ? (
        <div
          role="region"
          aria-labelledby="help-chat-title"
          onKeyDown={(event) => {
            if (event.key === "Escape" && !event.nativeEvent.isComposing) {
              event.stopPropagation();
              onToggle();
            }
          }}
          style={{
            position: "fixed",
            right: 16,
            bottom: 132,
            zIndex: 40,
            width: 320,
            maxWidth: "calc(100vw - 32px)",
            background: "var(--card)",
            color: "var(--ink)",
            border: "1px solid var(--line)",
            borderRadius: 12,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          <div id="help-chat-title" style={{ padding: "10px 14px", borderBottom: "1px solid var(--line)", fontWeight: 600 }}>
            Central de Ajuda (simulada)
          </div>
          <div role="log" aria-label="Mensagens da central de ajuda" aria-live="polite" aria-relevant="additions text" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 8, maxHeight: 280, overflowY: "auto" }}>
            {log.map((m, i) => (
              <div
                key={i}
                style={{
                  alignSelf: m.who === "me" ? "flex-end" : "flex-start",
                  background: m.who === "me" ? "var(--acc)" : "var(--field)",
                  color: m.who === "me" ? "var(--on-acc)" : "var(--ink)",
                  padding: "8px 11px",
                  borderRadius: 10,
                  maxWidth: "80%",
                  overflowWrap: "anywhere",
                  whiteSpace: "pre-wrap",
                  fontSize: 13,
                }}
              >
                {m.text}
              </div>
            ))}
          </div>
          <form onSubmit={(event) => { event.preventDefault(); if (String(input || "").trim()) onSend(); }} style={{ display: "flex", gap: 8, padding: 10, borderTop: "1px solid var(--line)" }}>
            <input
              type="text"
              aria-label="Mensagem para a central de ajuda"
              value={input}
              onChange={(e) => onInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.nativeEvent.isComposing || e.keyCode === 229)) e.preventDefault();
              }}
              placeholder="Escreva sua dúvida…"
              style={{ flex: 1, minWidth: 0, background: "var(--field)", color: "var(--ink)", border: "1px solid var(--line)", borderRadius: 8, padding: "8px 10px" }}
            />
            <button type="submit" disabled={!String(input || "").trim()} style={{ width: "auto", padding: "8px 14px" }}>
              Enviar
            </button>
          </form>
        </div>
      ) : null}
      {open ? <button
        onClick={onToggle}
        style={{ position: "fixed", right: 16, bottom: 76, zIndex: 40, width: "auto", padding: "10px 16px", borderRadius: 999 }}
      >
        Fechar Chat
      </button> : null}
    </>
  );
}
