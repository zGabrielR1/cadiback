"use client";

/** Cashier modal: deposit / Pix-withdraw tabs (F1 extract from page.jsx).
 * Money movement stays in the page handlers; this component is pure UI. */
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
  busy,
  onDeposit,
  onWithdraw,
  onClose,
}) {
  return (
    <div
      className={"modal" + (open ? " open" : "")}
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
          <div>
            <label htmlFor="method">Método de Depósito</label>
            <select id="method" value={method} onChange={(e) => onMethod(e.target.value)}>
              <option value="pix">Pix Instantâneo</option>
              <option value="ted">TED</option>
              <option value="debit">Cartão de Débito</option>
            </select>
            <label htmlFor="dep">Valor (R$)</label>
            <input
              id="dep"
              inputMode="decimal"
              value={depositAmount}
              onChange={(e) => onDepositAmount(e.target.value)}
            />
            <button disabled={busy} onClick={onDeposit} style={{ marginTop: 12 }}>
              Confirmar Depósito Demo
            </button>
          </div>
        ) : (
          <div>
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
            <button disabled={busy} onClick={onWithdraw} style={{ marginTop: 12 }}>
              Sacar agora via Pix
            </button>
            {receipt ? (
              <div style={{ fontSize: 12.5, color: "var(--acc)", marginTop: 8 }}>{receipt}</div>
            ) : null}
          </div>
        )}
        <button className="ghost" style={{ width: "100%", marginTop: 12 }} onClick={onClose}>
          Fechar
        </button>
      </div>
    </div>
  );
}
