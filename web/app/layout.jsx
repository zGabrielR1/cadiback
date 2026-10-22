import "./globals.css";

export const metadata = {
  title: "Candibet — Esportes e Cassino",
  description: "Acompanhe esportes, placares ao vivo e suas partidas favoritas.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="pt-BR" data-theme="dark">
      <body>{children}</body>
    </html>
  );
}