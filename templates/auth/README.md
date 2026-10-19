# Auth module — the reusable half

`foundry.auth` is the plumbing, not the product. It provides:

| Piece | What it owns | What the host still owns |
|---|---|---|
| `PasswordHasher` | PBKDF2-HMAC-SHA256, fresh salt, versioned record, constant-time verify, rehash advice | the password policy, the error copy, when to rehash |
| `issue_session` / `Session` | a `secrets` token, an absolute expiry, a test-injectable clock | where sessions live, revocation, cookies, "remember me" duration |
| `validate_cpf` / `validate_cnpj` | normalisation, check digits, masking | whether a document is required and what it unlocks |
| `resolve_*` | one environment read with safe defaults | the deploy values |

Authentication *policy* (who may register, what a login error says, the
required fields, the CPF-to-wallet rule) stays in the host. That boundary is
what lets the same module run in a stdlib-only container and in a FastAPI
service.

## Server use

```python
from foundry.auth import (PasswordHasher, PasswordPolicy, issue_session,
                          token_fingerprint)

hasher = PasswordHasher(
    policy=PasswordPolicy(min_length=8, require_letter=True, require_digit=True),
)
stored = hasher.hash(password)          # put `stored` in the user row
if hasher.verify(password, row["password"]):
    if hasher.needs_rehash(row["password"]):
        row["password"] = hasher.hash(password)
    session = issue_session(remember=remember)
    sessions[token_fingerprint(session.token)] = session.expires_at
```

The raw token goes to the client; only its fingerprint is stored. A read-only
leak of the session table then does not hand over live sessions.

## Frontend use

`session.js` is a dependency-free browser helper for the "Lembrar de mim"
choice: checked writes `localStorage` (survives a browser restart), unchecked
writes `sessionStorage` (dies with the tab). Both stores are read on boot,
session storage first, so a deliberate non-remembered login wins over an older
remembered one. Copy it into the host's client code; it is a template, not a
package.

## Environment

Copy `env.example` into the service's `.env` and fill only what the host uses.
A missing value is a normal state: the hash uses its safe default, and the
session policy falls back to 12 hours / 30 days. Nothing here reads a secret
at import time.

For OAuth (Google/Facebook through Authgear), use `foundry.oauth` — it owns
discovery, PKCE, `state`, the code exchange and userinfo; this module does not
duplicate it.
