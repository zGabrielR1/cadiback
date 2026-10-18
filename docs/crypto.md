# Crypto deposits via NOWPayments

The operator accepts cryptocurrency as a deposit rail (decision 0057). Like
Pix/Asaas, the operator's own double-entry ledger stays the source of truth: a
crypto invoice is a *request* to move money, and a deposit reaches the books
only after NOWPayments independently confirms the payment and the amount
matches. **The IPN webhook is a hint, never proof** — every confirmation
re-reads the payment from the provider first. That matters more than with Pix:
a crypto IPN is easier to forge and to replay.

Code: `demo/crypto.py` (stdlib only, injectable transport). Routes:

| Route | Method | Role |
|-------|--------|------|
| `/api/deposit/crypto` | POST | open an invoice (`player`, `amount_minor`, `pay_currency`, `deposit_id`) |
| `/api/deposit/crypto/status` | POST | poll one invoice; confirm it if the provider now says paid |
| `/api/webhooks/crypto` | POST | NOWPayments IPN (`x-nowpayments-sig`, HMAC-SHA512); GET proves reachability |

## Credentials

Secrets live in a gitignored `.env.crypto` beside the repository (or the
environment). They are never committed and never logged:

```
CRYPTO_API_KEY=            # NOWPayments API key
CRYPTO_IPN_SECRET=         # NOWPayments IPN secret (verifies callbacks)
CRYPTO_BASE_URL=https://api.nowpayments.io/v1
CRYPTO_PRICE_CURRENCY=brl
```

`CryptoConfig.from_env()` reads the environment first, the file second. The
rail is **configured only when a key is set and the base URL is `https://`** —
an `http://` base would put the key on the wire and is treated as unconfigured.
When unconfigured, `crypto_available()` is false, the cashier hides the crypto
tab and the instant demo credit stays the fallback, exactly like Pix.

## Going live

1. Create a NOWPayments account and an API key; copy the IPN secret.
2. Put them in `.env.crypto` (or the host's environment variables).
3. Register the IPN callback URL: `https://<host>/api/webhooks/crypto`.
4. `CRYPTO_BASE_URL` stays `https://api.nowpayments.io/v1` for production.
5. Deploy — `scripts/render_deploy.py` carries `CRYPTO_*` from `.env.crypto`
   (or the environment) automatically. `render.yaml` holds `sync: false`
   placeholders for the two secrets.

## Notes

- Only **finished/confirmed** payments credit; `partially_paid` deliberately
  does not (a short payment must never look like a full one).
- The invoice is idempotent on `deposit_id`; the IPN and the poll share one
  idempotent confirm, so a replay or a double poll cannot pay twice.
- Coins offered: see `SUPPORTED_COINS` in `demo/crypto.py` (BTC, ETH, USDT
  TRC-20/ERC-20, USDC, LTC).
- A test account (`is_test`) never touches this rail — it uses the tagged test
  deposit instead (decision 0057 §7).
