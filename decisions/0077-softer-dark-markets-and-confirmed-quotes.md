# 0077 — Softer dark surfaces and a coherent sportsbook transaction

The approved redesign review called for faster market discovery and a consistent selection contract. The owner clarified that the dark-mode appearance needed improvement; the default theme remains dark, with lighter graphite layers, quieter lime and more readable secondary text. Candibet branding and actual font assets remain.

Phone discovery uses a compact event highlight, one primary market per row, a board market selector and disclosed secondary filters. Team names open the existing match research view; returning restores the list position. Long research selections put their price below the label. The corner invitation compacts after scrolling or exploring.

The board keeps one selection per fixture; the research draft still allows comparisons but never manufactures a combined same-match price. Public quote and bet routes validate fixture, market, line, selection and current price against the server feed. Rejections precede wallet mutation. Changed prices require explicit acceptance. The low-level simulation method remains available to existing internal tests.

The slip shows inline validation, price review, submission and a server-confirmed receipt. Stable request IDs recover confirmed receipts after a lost response, including when the feed subsequently moves. Reusing an ID with different details is rejected. This release does not add durable remote wallet storage; the existing Render file-backed ledger limitation remains.

Validation: frontend build, structure verifier, 15 Node tests, 50 core tests and 431 demo tests pass. Browser transaction coverage checks quote review, no premature submission, stable retry ID and visible mobile receipt. Responsive checks cover five widths. No live wagers or payment transactions were submitted during QA.

Deployment status is recorded in CURRENTTASK; local completion alone does not imply publication.
