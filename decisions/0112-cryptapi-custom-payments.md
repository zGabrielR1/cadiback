# 0112 - CryptAPI custom payment flow

The owner requested replacing new NOWPayments invoices with CryptAPI and will
provide receiving addresses later in a configuration file. `.env.cryptapi` is
ignored, with a tracked empty example and setup guide in `docs/cryptapi.md`.
Only configured networks are offered. No API key is needed. Domain verification
uses the provider's HTTPS-file challenge; CAPTCHA approval remains with the owner.

The existing durable crypto invoice and double-entry transaction seams remain.
CryptAPI-specific details are private metadata on each invoice. Status checks
use provider logs, validate the immutable callback/address pair, sum distinct
confirmed incoming transfers and credit the original BRL quote once. Pending,
duplicate and underpaid transfers cannot generate wallet credit. POST callbacks
verify exact raw bytes with RSA-SHA256 and the invoice nonce, then independently
query the provider. The cryptography dependency implements signature verification.

Legacy NOWPayments credentials and invoice confirmation are retained to settle
already-created invoices, but new deposits use only CryptAPI. Wallet backups
already carry both invoice variants in crypto_charges. No receiving address is
invented or activated while the owner's file is blank.
