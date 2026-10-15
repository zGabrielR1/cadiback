# 0046 — Signup without the payout account, and hidden test accounts

Date: 2026-10-15
Status: shipped

## Context

Two pieces of signup friction the owner flagged:

1. Creating an account forced bank/agência/conta (and the holder name). Every
   real betting site asks for the payout details *after* the account exists, or
   uses the Pix key alone. The owner's ideal was "fetch the account from the Pix
   key"; the fallback was an operator toggle so the requirement can be turned on
   later.
2. The site carried a visible **"Usar conta de teste"** button that prefilled a
   built-in identity. It was a development convenience leaking into the product:
   it should be invisible, reachable only through a secret, or disabled — while
   still letting the owner log in with test credentials and manage test users in
   the painel.

## Decision

### The payout account is optional, and the operator decides

- The **Pix key is the payout destination** (`process_withdrawal` pays the
  stored key). The bank fields were never consulted for a Pix payout, so they
  are records, not plumbing.
- `Demo.register_player(payload, *, is_test=False)`:
  - no account supplied → accepted (the account is empty);
  - *any* account field supplied → the whole account is validated
    (`validate_bank_account`, own-name rule included), because a half-filled
    account is worse than none;
  - no account supplied **and** the operator's `require_bank_at_signup` is on →
    refused, restoring the old strict behaviour.
- Settings live in a JSON store (`settings.json`), defaults in
  `SETTINGS_DEFAULTS`. Read path `Demo.settings_view()` fills defaults so a
  fresh install or a truncated file never crashes the server.
- **No auto-fetch from the Pix key.** Asaas exposes no DICT lookup for an
  arbitrary key, and a bank account is not derivable from an email / CPF / phone
  / EVP key. The honest resolution is that the account is optional, because the
  payout already follows the key.

### Test accounts are invisible and painel-managed

- The visible button is **gone**. Nothing on the storefront advertises test
  accounts.
- A test account is an **ordinary player row flagged `is_test`**. It logs in
  through the normal email + password door — no special endpoint.
- On the storefront the built-in identity is reachable only through
  **Ctrl+Shift+T** while the account modal is open, and only while
  `test_accounts_enabled` is on. (The hidden-shortcut idiom already exists for
  the panel: Ctrl+Shift+A.)
- `test_accounts_enabled` off → a test account **cannot log in**, with the same
  message and the same delay as a wrong password, so nothing is probeable.
- The painel gains **Contas de teste**: list, create, reset password, delete.
  Listing never exposes `pw_salt`/`pw_hash`; reset re-salts; delete drops the
  row and its Pix allowlist entry.
- Test accounts are **exempt from `require_bank_at_signup`**: the requirement is
  about public signup friction, and an account the operator mints in the painel
  should not be blocked by it.

## Surface

| Route | Access | Purpose |
|-------|--------|---------|
| `GET /api/config` | public | `require_bank_at_signup`, `test_accounts_enabled` (the storefront adapts) |
| `GET /api/admin/settings` | admin | read settings |
| `POST /api/admin/settings` | admin | flip settings |
| `GET /api/admin/test-accounts` | admin | list test accounts |
| `POST /api/admin/test-accounts` | admin | create (→ `register_player(is_test=True)`) |
| `POST /api/admin/test-accounts/reset` | admin | reset a test account's password |
| `POST /api/admin/test-accounts/delete` | admin | delete a test account |

`/api/health` also carries `config` (same shape as `/api/config`) so a single
poll exposes it. All admin doors reuse `_require_admin`, so a `viewer` is
refused with the panel's client-safe message.

## Frontend

- `useSession` fetches `/api/config` on boot (independent of a logged-in
  player) and exposes `serverConfig`.
- `AccountModal` takes `requireBank` and `testAccountsEnabled`; bank fields are
  labelled `(opcional)` and only validated when required or when partially
  filled; the secret shortcut fills the test identity and shows a quiet note.
- `AdminPanel` gains **Configurações do cadastro** (two toggles) and **Contas de
  teste** (table + create/reset), both admin-only.

## Why not per-player Asaas customers / DICT lookup

Out of scope for the same reason as 0045: one sandbox customer, sandbox only,
no real money. A production rail would resolve the holder from the key at the
*provider*, which Asaas does not offer; the key remains the payout source.

## Verification

`SignupSettingsTest` (6): defaults; optional-vs-required; a partial account
refused; settings admin-only and persistent across a restart; test accounts
flagged and listed without secrets, blocked when disabled, reset, deleted; test
accounts exempt from the signup rule; the test-account doors are admin-only.
`frame` 45/45, `demo` 258/258, `verify.py` 0. The HTTP routes were smoked live:
`/api/config`, a settings flip reflected publicly, signup with and without the
account, test-account create/list/login/reset/delete, and a `viewer` refusal.
