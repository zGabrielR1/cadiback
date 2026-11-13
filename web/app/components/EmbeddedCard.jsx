"use client";

import { useEffect, useId, useRef, useState } from "react";
import { loadMercadoPago } from "../../lib/mercadopago.mjs";

export default function EmbeddedCard({ charge, onSubmit, theme = "light" }) {
  const id = "mp-card-" + useId().replace(/[^a-zA-Z0-9]/g, "");
  const submit = useRef(onSubmit);
  submit.current = onSubmit;
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const challengeUrl = charge.three_ds_info?.external_resource_url;
  const creq = charge.three_ds_info?.creq;
  useEffect(() => {
    let active = true;
    let controller;
    let submitting = false;
    setReady(false);
    setError("");
    const fail = () => { if (active) setError("Não foi possível abrir o formulário seguro. Confira a conexão e tente novamente."); };
    const mount = async () => {
      try {
        const MercadoPago = await loadMercadoPago();
        if (!active) return;
        const mp = new MercadoPago(charge.public_key, { locale: "pt-BR" });
        // Resolve the cashier's actual tokens, including brand/theme overrides.
        // CSS variables cannot cross the provider's secure iframe boundary.
        const host = document.getElementById(id);
        const tokens = getComputedStyle(host);
        const color = name => tokens.getPropertyValue(name).trim();
        const style = { theme: "flat", customVariables: {
          baseColor: color("--acc"), baseColorFirstVariant: color("--acc"),
          baseColorSecondVariant: color("--acc-soft"),
          textPrimaryColor: color("--ink"), textSecondaryColor: color("--mut"),
          formBackgroundColor: color("--card"), inputBackgroundColor: color("--field"),
          outlinePrimaryColor: color("--line"), outlineSecondaryColor: color("--acc"),
          buttonTextColor: color("--on-acc"), errorColor: color("--bad"),
          fontSizeMedium: "16px", fontSizeSmall: "14px", fontSizeExtraSmall: "14px",
          fontWeightNormal: "400", fontWeightSemiBold: "600", formInputsTextTransform: "none",
          borderRadiusSmall: "4px", borderRadiusMedium: "4px", borderRadiusLarge: "4px",
          inputVerticalPadding: "12px", inputHorizontalPadding: "12px", formPadding: "0px",
        } };
        const visual = { style, font: new URL("/fonts/card-fields.css", location.origin).href };
        const settings = {
          initialization: challengeUrl ? { paymentId: charge.payment_id,
            additionalInfo: { externalResourceURL: challengeUrl, creq } } : { amount: charge.amount_minor / 100 },
          customization: challengeUrl ? { visual: { style } } : {
            paymentMethods: { minInstallments: 1, maxInstallments: 1,
              types: { included: ["credit_card", "debit_card"] } },
            visual: { ...visual, hideFormTitle: true, texts: { emailSectionTitle: "Dados de contato", formSubmit: "Pagar depósito" } },
          },
          callbacks: {
            onReady: () => { if (active) setReady(true); },
            onError: fail,
            onSubmit: async (form) => {
              if (!active || submitting) throw new Error("Pagamento em andamento.");
              submitting = true;
              try { return await submit.current(form); }
              finally { submitting = false; }
            },
          },
        };
        controller = await mp.bricks().create(challengeUrl ? "statusScreen" : "cardPayment", id, settings);
        if (!active) controller.unmount();
      } catch { fail(); }
    };
    mount();
    return () => { active = false; controller?.unmount(); };
  }, [id, charge.public_key, charge.amount_minor, charge.payment_id, challengeUrl, creq, theme, retry]);
  return <div className="embedded-card">
    {!ready && !error && <p role="status">Carregando formulário seguro…</p>}
    {error && <div role="alert"><p>{error}</p><button className="ghost" onClick={() => setRetry(n => n + 1)}>Tentar novamente</button></div>}
    <div id={id} />
    <p className="sub">Os dados do cartão são protegidos pelo Mercado Pago. Seu banco pode solicitar uma confirmação de identidade.</p>
  </div>;
}
