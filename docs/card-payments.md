# Mercado Pago hosted cards

Uses the merchant access token explicitly authorized from mamyat, stored only in ignored .env.mercadopago and Render environment. No Mamy Ateliê notification registration or secret is changed.

The authenticated card endpoints create hosted preferences with isolated operator-card references and persist them in card_charges. The browser opens Mercado Pago in another tab and offers explicit payment verification; per-account session storage retains a checkout across refreshes. Returning from checkout is never proof of payment. The status endpoint retrieves provider records and checks approved status, exact BRL amount, production mode, card type and isolated metadata before an idempotent wallet posting. Test player accounts cannot create live charges.

This initial integration uses authenticated verification rather than background webhook settlement. A player must use Verificar pagamento to refresh the wallet after paying. Refunds/chargebacks require merchant reconciliation; the implementation does not automatically reverse a wallet that may already be spent. Additional payments against the same deposit never generate additional wallet credit.

Official API references: https://www.mercadopago.com.br/developers/en/reference/online-payments/checkout-pro-preferences/create-preference/post and https://www.mercadopago.com.br/developers/en/reference/payments/_payments_id/get
