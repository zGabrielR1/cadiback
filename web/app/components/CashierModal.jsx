"use client";

import { useState } from "react";
import { BRL } from "../../lib/api";
import { amountMinor, depositAllowed, clampDeposit } from "../../lib/money.mjs";

/** Cashier modal: deposit / Pix-withdraw tabs (F1 extract from page.jsx).
 * Money movement stays in the page handlers; this component is pure UI.
 *
 * When the server has an Asaas Pix rail, a deposit opens a real charge and
 * this modal shows the QR + copy-paste string and waits for confirmation
 * (`pixCharge`). Without the rail it keeps the instant demo credit. */
export default function CashierModal({
  open,
  tab,
  onTab,
  method,
  onMethod,
  depositAmount,
  onDepositAmount,
  withdrawAmount,
  onWithdrawAmount,
  receipt,
  error = "",
  depositLimit = null,
  limitError = "",
  onRetryLimit,
  pixRegistered = false,
  pixMasked = "",
  withdrawPixKey = "",
  onWithdrawPixKey,
  busy,
  onDeposit,
  onWithdraw,
  asaasAvailable,
  pixCharge,
  onResetPix,
  cryptoAvailable,
  cryptoCharge,
  onResetCrypto,
  cryptoCoins,
  cryptoCoin,
  onCryptoCoin,
  onClose,
}) {
  const [copied, setCopied] = useState(false);
  const realPix = asaasAvailable && method === "pix";
  const realCrypto = cryptoAvailable && method === "crypto";
  const canDeposit = depositAllowed(depositAmount, depositLimit);

  const copyPix = async () => {
    try {
      await navigator.clipboard.writeText(pixCharge.copy_paste);
      setCopied(true);
    } catch (e) {
      /* clipboard blocked: the textarea below is selectable by hand */
    }
  };

  const copyAddress = async () => {
    try {
      await navigator.clipboard.writeText(cryptoCharge.pay_address);
      setCopied(true);
    } catch (e) {
      /* clipboard blocked: the field below is selectable by hand */
    }
  };

  return (
    <div
      className={"modal" + (open ? " open" : "")}
      tabIndex={-1}
      role="dialog"
      aria-modal="true"
      aria-label="Caixa"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="sheet">
        <h3>Caixa da Conta</h3>
        <div className="tabs">
          <button className={tab === "dep" ? "on" : ""} onClick={() => onTab("dep")}>
            Depositar
          </button>
          <button className={tab === "wd" ? "on" : ""} onClick={() => onTab("wd")}>
            Sacar via Pix
          </button>
        </div>
        {tab === "dep" ? (
          pixCharge ? (
            <div>
              <p className="sub" style={{ marginTop: 4 }}>
                Pague <b>{BRL(pixCharge.amount_minor)}</b> via Pix para o saldo cair
                na hora.
              </p>
              {pixCharge.qr_base64 ? (
                <img
                  alt="QR Code Pix"
                  width={220}
                  height={220}
                  src={"data:image/png;base64," + pixCharge.qr_base64}
                  style={{
                    display: "block",
                    margin: "12px auto",
                    background: "#fff",
                    padding: 8,
                    borderRadius: 8,
                  }}
                />
              ) : null}
              {pixCharge.copy_paste ? (
                <div>
                  <label htmlFor="pixcode">Pix copia e cola</label>
                  <textarea
                    id="pixcode"
                    readOnly
                    rows={3}
                    value={pixCharge.copy_paste}
                    onFocus={(e) => e.target.select()}
                    style={{ width: "100%", fontFamily: "monospace", fontSize: 11.5 }}
                  />
                  <button className="ghost" style={{ width: "100%" }} onClick={copyPix}>
                    {copied ? "Código copiado ✓" : "Copiar código Pix"}
                  </button>
                </div>
              ) : null}
              <p className="sub" style={{ marginTop: 8 }}>
                {pixCharge.posted
                  ? "Pagamento confirmado — saldo creditado."
                  : "Aguardando a confirmação do pagamento…"}
              </p>
              <button
                className="ghost"
                style={{ width: "100%", marginTop: 8 }}
                onClick={onResetPix}
              >
                Gerar outro código
              </button>
            </div>
          ) : cryptoCharge ? (
            <div>
              <p className="sub" style={{ marginTop: 4 }}>
                Envie <b>{cryptoCharge.pay_amount} {(cryptoCharge.pay_currency || "").toUpperCase()}</b>{" "}
                (≈ {BRL(cryptoCharge.amount_minor)}) para o endereço abaixo. O saldo
                cai quando a rede confirmar.
              </p>
              <label htmlFor="cryptoaddr">Endereço de depósito</label>
              <textarea
                id="cryptoaddr"
                readOnly
                rows={2}
                value={cryptoCharge.pay_address}
                onFocus={(e) => e.target.select()}
                style={{ width: "100%", fontFamily: "monospace", fontSize: 11.5 }}
              />
              <button className="ghost" style={{ width: "100%" }} onClick={copyAddress}>
                {copied ? "Endereço copiado ✓" : "Copiar endereço"}
              </button>
              <p className="sub" style={{ marginTop: 8 }}>
                {cryptoCharge.posted
                  ? "Pagamento confirmado — saldo creditado."
                  : "Aguardando a confirmação da rede (leva alguns minutos)…"}
              </p>
              <button
                className="ghost"
                style={{ width: "100%", marginTop: 8 }}
                onClick={onResetCrypto}
              >
                Gerar outra cobrança
              </button>
            </div>
          ) : (
            <div>
              <label htmlFor="method">Método de Depósito</label>
              <select id="method" value={method} onChange={(e) => onMethod(e.target.value)}>
                <option value="pix">Pix Instantâneo</option>
                <option value="ted">TED</option>
                <option value="debit">Cartão de Débito</option>
                <option value="crypto">Criptomoeda</option>
              </select>
              {realCrypto ? (
                <>
                  <label htmlFor="coin">Moeda</label>
                  <select id="coin" value={cryptoCoin || ((cryptoCoins[0] || {}).code || "")}
                    onChange={(e) => onCryptoCoin(e.target.value)}>
                    {cryptoCoins.map((c) => (
                      <option key={c.code} value={c.code}>{c.label}</option>
                    ))}
                  </select>
                </>
              ) : null}
              <label htmlFor="dep">Valor (R$)</label>
              <input
                id="dep"
                type="number"
                inputMode="decimal"
                min={depositLimit ? depositLimit.min_minor / 100 : undefined}
                step="0.01"
                disabled={!depositLimit || !!busy}
                value={depositAmount}
                onChange={(e) => onDepositAmount(e.target.value)}
                onBlur={() => onDepositAmount(clampDeposit(depositAmount, depositLimit))}
                aria-describedby="deposit-minimum"
                aria-invalid={depositLimit && !canDeposit ? "true" : undefined}
              />
              <p id="deposit-minimum" className={depositLimit && !canDeposit ? "ferr" : "fhint"} role="status">
                {limitError ? "Não foi possível consultar o mínimo. O depósito está indisponível até atualizar."
                  : !depositLimit ? "Consultando o mínimo de depósito…"
                    : `Depósito mínimo: ${BRL(depositLimit.min_minor)}${depositLimit.provider === "demo" ? " (demonstração)" : " — " + depositLimit.provider + (realCrypto ? " nesta moeda/rede" : " via Pix")}. Valores menores não são aceitos.`}
              </p>
              {limitError ? <button className="ghost" onClick={onRetryLimit} disabled={busy}>Consultar novamente</button> : null}
              {depositLimit && !canDeposit ? (
                <button className="ghost" onClick={() => onDepositAmount((depositLimit.min_minor / 100).toFixed(2))}>
                  Usar o mínimo de {BRL(depositLimit.min_minor)}
                </button>
              ) : null}
              <button disabled={busy || !canDeposit} onClick={onDeposit} style={{ marginTop: 12 }}>
                {realPix ? "Gerar Pix para pagar"
                  : realCrypto ? "Gerar cobrança cripto"
                  : "Confirmar Depósito Demo"}
              </button>
              {realPix ? (
                <p className="sub" style={{ marginTop: 8 }}>
                  O Pix é gerado pelo Asaas; o saldo cai quando o pagamento é
                  confirmado.
                </p>
              ) : null}
              {realCrypto ? (
                <p className="sub" style={{ marginTop: 8 }}>
                  A cobrança é gerada pela NOWPayments; envie a moeda para o
                  endereço e o saldo cai quando a rede confirmar.
                </p>
              ) : null}
            </div>
          )
        ) : (
          <div>
            {!pixRegistered ? (
              <>
                <label htmlFor="withdraw-pix-key">Chave Pix para receber saques</label>
                <input id="withdraw-pix-key" value={withdrawPixKey} autoComplete="off"
                  onChange={(e) => onWithdrawPixKey(e.target.value)}
                  placeholder="Email, telefone com +55, chave aleatória, CPF ou CNPJ" />
                <p className="fhint">Use uma chave de sua titularidade. Confira antes de confirmar: ela será cadastrada para os próximos saques.</p>
              </>
            ) : <p className="fhint">Destino Pix cadastrado: {pixMasked}</p>}
            <label htmlFor="wd">Valor (R$)</label>
            <input
              id="wd"
              inputMode="decimal"
              value={withdrawAmount}
              onChange={(e) => onWithdrawAmount(e.target.value)}
            />
            <p className="sub" style={{ marginTop: 6 }}>
              O saque demo sai imediatamente para a chave Pix cadastrada em sua conta.
            </p>
            <button disabled={busy || !amountMinor(withdrawAmount) || (!pixRegistered && !withdrawPixKey.trim())} onClick={onWithdraw} style={{ marginTop: 12 }}>
              Sacar agora via Pix
            </button>
            {receipt ? (
              <div style={{ fontSize: 12.5, color: "var(--acc)", marginTop: 8 }}>{receipt}</div>
            ) : null}
          </div>
        )}
        {error ? <p className="ferr" role="alert">{error}</p> : null}
        <button className="ghost" style={{ width: "100%", marginTop: 12 }} onClick={onClose}>
          Fechar
        </button>
      </div>
    </div>
  );
}
