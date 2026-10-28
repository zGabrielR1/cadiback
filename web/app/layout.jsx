import "./globals.css";
import "./workspace.css";
import "./apex.css";
import "./variants.css";
import "./auteur.css";

export const metadata = {
  title: "Candibet — Cotações Esportivas",
  description: "Cotações esportivas ao vivo, mercados e análise de partidas. Candibet, 18+.",
};

const design = process.env.NEXT_PUBLIC_LOCAL_BLUE === "1" ? "blue" : "auteur";

export default function RootLayout({ children }) {
  return (
    <html lang="pt-BR" data-theme={design === "auteur" ? "light" : "dark"} data-design={design} suppressHydrationWarning>
      <head>
        <link rel="preload" href="/fonts/SourceSans3.woff2" as="font" type="font/woff2" crossOrigin="anonymous" />
        <link rel="preload" href="/fonts/Archivo.woff2" as="font" type="font/woff2" crossOrigin="anonymous" />
        {/* Set before first paint so the reveal layer can hide only when
            JavaScript is actually available; no-JS readers still get the
            whole page. */}
        <script
          dangerouslySetInnerHTML={{
            __html: "document.documentElement.classList.add('js');try{const t=localStorage.getItem('casa-theme');if(t==='dark'||t==='light')document.documentElement.dataset.theme=t}catch{}document.documentElement.dataset.design='" + design + "'",
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
