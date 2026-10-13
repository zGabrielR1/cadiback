"use client";

/** Renders when any client render throws, instead of unmounting to a blank page. */
export default function Error({ error, reset }) {
  return (
    <html lang="pt-BR" data-theme="dark">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0a0e0c",
          color: "#f2f5f1",
          fontFamily:
            '-apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif',
        }}
      >
        <main style={{ maxWidth: 460, padding: 24 }}>
          <h1 style={{ fontSize: 22, margin: "0 0 10px" }}>
            A tela quebrou — nenhum dinheiro foi movido
          </h1>
          <p style={{ color: "#9aa79e", fontSize: 14, lineHeight: 1.6 }}>
            {error && error.message ? error.message : "erro desconhecido"}
          </p>
          <p style={{ color: "#9aa79e", fontSize: 13 }}>
            A carteira é append-only: cada jogada e saque já registrados permanecem.
          </p>
          <button
            onClick={reset}
            style={{
              marginTop: 16,
              padding: "11px 18px",
              borderRadius: 9,
              border: "none",
              background: "#2bff88",
              color: "#052012",
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            Tentar de novo
          </button>
        </main>
      </body>
    </html>
  );
}