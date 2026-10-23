import "./globals.css";

export const metadata = {
  title: "Candibet — Esportes e Cassino",
  description: "Esportes ao vivo, cotações em movimento e um cassino no mesmo ritmo. Candibet, 18+.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="pt-BR" data-theme="dark">
      <head>
        {/* Set before first paint so the reveal layer can hide only when
            JavaScript is actually available; no-JS readers still get the
            whole page. */}
        <script
          dangerouslySetInnerHTML={{
            __html: "document.documentElement.classList.add('js');",
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}