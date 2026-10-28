# Data portal code

Updated 2026-10-25 (decision0092).

Signed-in players can open **Cassino** and **Criar Aposta** directly. They do not need the data-portal code. Guests still see the sports/research surface without private financial or game navigation.

The optional Dados portal currently compares one shared code, not a registry of individually enrolled codes. Its built-in default is `feed-seguro`.

To replace that shared code:

1. Open the `cadiback-web` project in Vercel.
2. In Settings → Environment Variables, add or update `NEXT_PUBLIC_DATA_ACCESS_CODE` for Production.
3. Set the desired code and redeploy the frontend. The value is compiled at build time; changing the environment alone does not change an already-built deployment.
4. For a local build, set the same environment variable before `npm run build`.

Comparison ignores letter case, extra whitespace and accents. The portal keeps an unlock marker in the current browser session. It is a frontend display gate whose comparison is in the bundle, not an authentication secret. The server's signed player sessions remain the actual authenticated-player boundary.

There is no code-registration screen or multiple-code list in the current implementation. This pass does not invent a new code or change the configured code; it removes the unwanted second gate for members.
