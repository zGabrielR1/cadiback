import "./globals.css";

export const metadata = {
  title: "Candibet — Cassino e Esporte",
  description: "Demonstração — nenhum dinheiro real",
};

export default function RootLayout({ children }) {
  return (
    <html lang="pt-BR" data-theme="dark">
      <body>{children}</body>
    </html>
  );
}