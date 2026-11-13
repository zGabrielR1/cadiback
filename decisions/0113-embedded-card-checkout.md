# 0113 - Embedded Mercado Pago cards

The owner explicitly requested replacing hosted Checkout Pro with a site-styled embedded credit/debit form. New deposits use the official Card Payment Brick with the existing merchant application credentials and tokenized server-side Payments API submission. The current provider supports this Brick/Payments API pairing; no SDK dependency is vendored.

The preparation route creates a durable reference only. A restricted tokenized payload is submitted with a stable provider idempotency key and durable request digest. Amount, currency and deposit identity remain server-owned. Only a matching approved production card payment credits the wallet, atomically with receipt acknowledgement. 3DS challenges use the official embedded Status Screen Brick; browser completion is never settlement evidence. PAN/CVV are not accepted by our API; card tokens and payer details are not persisted.

Existing hosted deposits retain their original verification path. Test players remain blocked from live charges. Refund/chargeback reconciliation and webhook settlement retain the limitations in docs/card-payments.md. Crypto receiving addresses are configured separately from the owner's ignored metamask.txt, only for supported explicitly identified networks; domain verification must precede successful invoice creation.
