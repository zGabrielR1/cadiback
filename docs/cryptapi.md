# CryptAPI custom payment flow

Edit the ignored `.env.cryptapi` in the repository root. The tracked
`.env.cryptapi.example` has the same fields. No API key or account is needed.
Set only public receiving addresses; never enter a private key or seed phrase.

| Variable | Asset and network |
| --- | --- |
| CRYPTAPI_WALLET_BTC | Bitcoin |
| CRYPTAPI_WALLET_ETH | Ethereum mainnet |
| CRYPTAPI_WALLET_LTC | Litecoin |
| CRYPTAPI_WALLET_USDTTRC20 | USDT on TRON |
| CRYPTAPI_WALLET_USDTERC20 | USDT on Ethereum mainnet |
| CRYPTAPI_WALLET_USDC | USDC on Ethereum mainnet |

Blank networks are hidden from checkout. If all receiving addresses are blank,
the live crypto rail is disabled. A receiving address also waits for a configured domain-verification value before the live rail is offered. Existing dashboard values are preserved when
the local file does not supply a nonempty value. Restart the local Python
server after editing; use the normal verified Render deploy to update the live
environment. Addresses for existing invoices are immutable; changing a receiving
address affects only new invoices.

## Verify the callback domain

The default callback host is `cadiback.onrender.com`. At
<https://cryptapi.io/verify_domain/>, enter that exact host and complete the
provider's CAPTCHA. Copy its full `cryptapi-verification=...` value into
`CRYPTAPI_VERIFICATION_TOKEN` in `.env.cryptapi`. Deploy, then confirm
`https://cadiback.onrender.com/.well-known/cryptapi-verification.txt` serves that
exact text. Back on CryptAPI's page, verify with its HTTPS-file method. The
server serves this file without compression or redirects. No file is served
until the value is configured. Change `CRYPTAPI_CALLBACK_BASE` only if using
another verified HTTPS backend host.

## Payment behavior

The backend fetches each network's current minimum and BRL exchange rate. It
refuses below-minimum invoices and rounds requested crypto upward to that
network's base unit. Checkout displays both the exact requested crypto amount
and the minimum per transaction. Below-minimum transfers may be ignored by
CryptAPI; users must send only the asset/network shown.

Each generated address uses a random callback nonce. Callback URLs and nonces
remain in the private durable invoice, not in browser responses. POST callbacks
require RSA-SHA256 verification against CryptAPI's published key and a matching
invoice nonce. Callback bodies alone never credit money: the server fetches
provider logs and validates incoming address, receiving address, callback URL,
forwarded status and confirmed logs. Distinct confirmed incoming transactions
can accumulate toward an invoice; duplicates do not count twice. The existing
wallet journal posts only the requested BRL amount once. Overpayments require
manual reconciliation; this release does not create a second wallet credit.

The existing cashier polls status. A callback may arrive before its provider log
has been recorded, in which case that poll completes confirmation later. No
automated reconciliation worker is introduced. The endpoint acknowledges valid
callbacks with `*ok*`; malformed signatures and unknown nonces are refused.

The old NOWPayments credentials/client are retained solely for confirmation of
existing invoices. New invoices use CryptAPI; provider changes never reinterpret
an old reference as a new-provider payment. Backups already include the durable
`crypto_charges` document, including private CryptAPI invoice metadata.

References: [custom flow](https://docs.cryptapi.io/get-started/custom-payment-flow),
[domain verification](https://docs.cryptapi.io/kb/developers/how-to-verify-your-callback-domain),
[address logs](https://docs.cryptapi.io/api/tickerlogs),
[signature verification](https://docs.cryptapi.io/webhooks/verify-webhook-signature).

Owner wallet import (2026-11-12): `metamask.txt` is ignored. Only its explicitly labeled BTC and Ethereum-mainnet addresses were copied into the ignored environment file. Solana, Linea, Base, Arbitrum, BNB Chain and Monad entries are not mapped to another chain. No token network was inferred from the Ethereum address.
