"use client";

/** Account-creation modal (F1 extract from page.jsx). Collects the demo
 * identity + payout details; the page owns the form state and save. */
export default function AccountModal({ open, form, onForm, onSave, onClose }) {
  return (
    <div
      className={"modal" + (open ? " open" : "")}
      role="dialog"
      aria-modal="true"
      aria-label="Sua conta demo"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="sheet">
        <h3>Sua Conta Demo</h3>
        <p className="sub">Dados de teste para simulação completa dos fluxos.</p>
        <label htmlFor="name">Nome completo</label>
        <input
          id="name"
          value={form.name}
          onChange={(e) => onForm({ ...form, name: e.target.value })}
        />
        <label htmlFor="cpf">CPF</label>
        <input
          id="cpf"
          inputMode="numeric"
          value={form.cpf}
          onChange={(e) => onForm({ ...form, cpf: e.target.value })}
        />
        <label htmlFor="pix">Chave Pix</label>
        <input
          id="pix"
          value={form.pix_key}
          onChange={(e) => onForm({ ...form, pix_key: e.target.value })}
        />
        <label htmlFor="bank">Banco / Agência / Conta</label>
        <div className="tri">
          <input
            id="bank"
            maxLength={3}
            value={form.bank_code}
            onChange={(e) => onForm({ ...form, bank_code: e.target.value })}
          />
          <input
            id="agency"
            value={form.agency}
            onChange={(e) => onForm({ ...form, agency: e.target.value })}
          />
          <input
            id="account"
            value={form.account}
            onChange={(e) => onForm({ ...form, account: e.target.value })}
          />
        </div>
        <label htmlFor="holder">Titular da Conta</label>
        <input
          id="holder"
          value={form.holder_name}
          onChange={(e) => onForm({ ...form, holder_name: e.target.value })}
        />
        <button onClick={onSave} style={{ marginTop: 14 }}>Salvar e Entrar</button>
        <button
          className="ghost"
          style={{ width: "100%", marginTop: 8 }}
          onClick={onClose}
        >
          Fechar
        </button>
      </div>
    </div>
  );
}
