"use client";

/** App Router error boundary: keep the shared shell and offer recovery. */
export default function Error({ reset }) {
  return <main className="club-error" role="alert">
    <h1>Não foi possível abrir a página</h1>
    <p>Ocorreu um problema ao exibir este conteúdo. Tente carregar a página novamente.</p>
    <button onClick={reset}>Tentar novamente</button>
  </main>;
}
