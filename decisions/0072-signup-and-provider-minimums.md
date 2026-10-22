# 0072 — PF/PJ signup, direct social login and provider deposit minimums

## Requested behavior

Manual signup offers Pessoa Física (CPF) or Pessoa Jurídica (CNPJ), masks the
document as typed and checks its check digits. Google/Facebook sign-in must
not require CPF or another signup form. Pix is collected at withdrawal.
The cashier must disclose and enforce the real payment-provider minimums.

## Identity

- PF retains the existing CPF-derived wallet identifier, preserving current
  accounts. PJ uses a separate CNPJ namespace. Canonical validation prevents
  punctuation/case from bypassing document uniqueness. Password login accepts
  username, email, CPF or CNPJ.
- Numeric and alphanumeric CNPJ are accepted. Alphanumeric check digits use
  Receita's ASCII-value-minus-48 calculation. The generic numeric foundry
  validators remain vendored and unchanged; the host adds the new format.
- CPF/CNPJ fields format while typing and show live check-digit feedback.
  Profiles redact document numbers; raw Pix keys and credential material are
  excluded from API profile responses. Check-digit validation is not proof of
  document issuance, status, or ownership.
- Signed social identities link existing accounts or create an account keyed
  by provider/subject immediately. Name/email come from the signed identity;
  there is no CPF, username, password, bank or Pix form. Facebook can omit email:
  the stable subject still identifies the account. The obsolete completion
  endpoint and frontend mode were removed. Handoffs are consumed once, and a
  device session is minted only when the browser exchanges the handoff.
- `POST /api/player/pix-key` registers the authenticated player's first payout
  destination. An existing key cannot be replaced by a withdrawal payload.
  Withdrawal remains blocked until a structurally valid key is registered.
  Format validation does not claim verification of bank-account ownership.

## Payment limits

- Configured Asaas Pix charges enforce the requested R$5.00 minimum before
  contacting Asaas. Local/demo payment flows keep their own R$0.01 floor.
- `GET /api/deposit/limits?method=...&pay_currency=...` is player-authenticated.
  NOWPayments minimums are queried per coin/network with `fiat_equivalent=brl`,
  fixed-rate and merchant-paid fee flags matching invoice creation. Leaving
  the outcome currency unset uses the merchant setting, matching payment
  creation. BRL minimums round upward to centavos.
- Display quotes cache for at most 60 seconds and report their remaining
  lifetime. The UI refreshes before expiry and discards quotes for a different
  method/network. Invoice creation forces a fresh provider lookup, enforcing
  the current minimum even if the browser is bypassed. No provider minimum is
  disabled, guessed, or replaced with a fabricated small amount.
- The input declares its minimum, clamps upward on blur, shows an explicit
  provider/network warning, offers a minimum-value shortcut and disables
  submission below the limit. Missing/failed quotes disable the input and
  submission and offer retry. Amount parsing uses exact centavos rather than
  partially accepting invalid `parseFloat` input. Charge requests have a
  30-second timeout to accommodate the minimum lookup and payment creation.
- The first social withdrawal asks only for a Pix key, then submits the
  withdrawal separately. Account changes clear payout drafts, receipts and
  pending charge UI. Deposit errors trigger a fresh limit quote.

## Verification and delivery

Backend regressions cover PF/PJ masks, invalid check digits, both CNPJ formats,
duplicate documents, document login, social signup, first withdrawal, key
replacement refusal, authenticated routes, provider minimums, rounding,
cache expiry and fail-closed behavior. Frontend checks cover formatting,
check digits, exact amounts, clamping and stale-network quotes.

The browser flow is exercised against local static output and mocked backend
responses: no real identity, invoice, deposit or withdrawal is created. A live
read-only NOWPayments minimum lookup confirmed BRL support for the configured
merchant (USDT/TRC-20 was R$99.34 rounded upward at that instant; never store
that snapshot as a fixed production minimum).

No production deployment or data import occurred. Decision 0071's identity
snapshot/import cutover still applies before deploying this combined tree.

## Primary references

- [Receita CNPJ check-digit manual](https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/documentos-tecnicos/cnpj/manual-dv-cnpj.pdf)
- [Receita first alphanumeric CNPJ](https://www.gov.br/fazenda/pt-br/assuntos/noticias/2026/julho/receita-federal-gera-o-primeiro-cnpj-em-formato-alfanumerico)
- [NOWPayments minimum amount API](https://nowpayments.zendesk.com/hc/en-us/articles/27407237685917-Minimum-payment-amount)
