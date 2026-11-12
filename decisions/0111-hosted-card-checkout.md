# 0111 - Hosted Mercado Pago card checkout

The owner selected real hosted card checkout and explicitly authorized reuse of mamyat's existing merchant credential. The operator copies only that access token into ignored .env.mercadopago; it does not change the other application's secrets or webhooks.

Card deposits use separate operator-card references and card_charges persistence. Real test-account charges are refused. The direct simulated debit path is refused whenever this provider is configured. Hosted card details never pass through our frontend/server.

Confirmation is an authenticated server operation. It retrieves matching provider records and verifies approved status, production mode, BRL, exact amount, card payment type and deposit metadata. The existing double-entry posting key and shared database transaction make a repeated confirmation idempotent. Wallet backups carry card_charges.

This initial release uses explicit customer confirmation rather than a webhook, preserving the other merchant application's webhook configuration. Refunds, chargebacks and repeated payments against one preference need merchant reconciliation; no automatic wallet reversal is claimed. See docs/card-payments.md.
