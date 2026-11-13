let loading;

export function loadMercadoPago() {
  if (window.MercadoPago) return Promise.resolve(window.MercadoPago);
  if (loading) return loading;
  loading = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://sdk.mercadopago.com/js/v2";
    script.async = true;
    const failed = () => {
      clearTimeout(timer);
      script.remove();
      loading = null;
      reject(new Error("Não foi possível carregar o formulário seguro. Tente novamente."));
    };
    const timer = setTimeout(failed, 20000);
    script.onload = () => {
      clearTimeout(timer);
      if (window.MercadoPago) resolve(window.MercadoPago);
      else failed();
    };
    script.onerror = failed;
    document.head.appendChild(script);
  });
  return loading;
}

// Never persist the Brick's token or payer data in browser storage.
export function cardSnapshot(charge) {
  return { deposit_id: charge.deposit_id, amount_minor: charge.amount_minor,
    status: charge.status, checkout_mode: charge.checkout_mode,
    ...(charge.checkout_url ? { checkout_url: charge.checkout_url } : {}) };
}

export function cardMessage(status) {
  if (status === "paid") return "Pagamento confirmado. Saldo atualizado.";
  if (status === "rejected") return "Pagamento recusado. Confira os dados e o limite com o banco antes de iniciar outro depósito.";
  if (["cancelled", "refunded", "charged_back"].includes(status)) return "Pagamento cancelado ou estornado. Consulte o suporte se já houve crédito na carteira.";
  if (status === "submitting") return "Pagamento enviado. Consulte a confirmação antes de iniciar outro depósito.";
  return "Aguardando confirmação do pagamento. O saldo só muda após aprovação.";
}
