"use client";

/** Player login + registration (Entrar / Criar conta). Real-site shape:
 * login takes email-or-CPF plus password; registration takes name, email,
 * CPF, password and the payout details. Every field is validated here and
 * again on the server (demo/payments.py + Demo.register_player); the page
 * owns the form state and the submit, this modal only renders. */
export default function AccountModal({
  open,
  mode,
  form,
  errors,
  busy,
  onForm,
  onMode,
  onSubmit,
  onFillTest,
  onClose,
}) {
  if (!open) return null;
  const isLogin = mode !== "register";
  const field = (id, label, props, hint) => (
    <>
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        value={form[props.name] || ""}
        onChange={(e) => onForm({ ...form, [props.name]: e.target.value })}
        aria-invalid={errors[props.name] ? "true" : undefined}
        {...props}
      />
      {errors[props.name] ? (
        <p className="ferr" role="alert">
          {errors[props.name]}
        </p>
      ) : hint ? (
        <p className="fhint">{hint}</p>
      ) : null}
    </>
  );
  return (
    <div
      className={"modal" + (open ? " open" : "")}
      role="dialog"
      aria-modal="true"
      aria-label={isLogin ? "Entrar na sua conta" : "Criar sua conta"}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="sheet">
        <h3>{isLogin ? "Entrar" : "Criar sua conta"}</h3>
        <p className="sub">
          {isLogin
            ? "Acesse com seu email ou CPF e sua senha."
            : "Uma conta por CPF. Validação de email e CPF no navegador e no servidor."}
        </p>
        {isLogin ? (
          <>
            {field("identifier", "Email ou CPF", {
              name: "identifier",
              autoComplete: "username",
              inputMode: "email",
              placeholder: "voce@email.com ou 000.000.000-00",
            })}
            {field("password", "Senha", {
              name: "password",
              type: "password",
              autoComplete: "current-password",
              placeholder: "••••••",
            })}
          </>
        ) : (
          <>
            {field("name", "Nome completo", {
              name: "name",
              autoComplete: "name",
              placeholder: "Como está no seu documento",
            })}
            {field("email", "Email", {
              name: "email",
              autoComplete: "email",
              inputMode: "email",
              placeholder: "voce@email.com",
            })}
            {field("cpf", "CPF", {
              name: "cpf",
              inputMode: "numeric",
              autoComplete: "off",
              placeholder: "000.000.000-00",
            })}
            {field(
              "password",
              "Senha",
              {
                name: "password",
                type: "password",
                autoComplete: "new-password",
                placeholder: "Mínimo 6 caracteres, letras e números",
              },
              "Mínimo 6 caracteres, com letras e números."
            )}
            {field("pix", "Chave Pix", {
              name: "pix_key",
              autoComplete: "off",
              placeholder: "CPF, email, telefone ou EVP",
            })}
            <label htmlFor="bank">Banco / Agência / Conta</label>
            <div className="tri">
              <input
                id="bank"
                maxLength={3}
                inputMode="numeric"
                placeholder="001"
                value={form.bank_code || ""}
                onChange={(e) => onForm({ ...form, bank_code: e.target.value })}
              />
              <input
                id="agency"
                inputMode="numeric"
                placeholder="1234"
                value={form.agency || ""}
                onChange={(e) => onForm({ ...form, agency: e.target.value })}
              />
              <input
                id="account"
                placeholder="56789-0"
                value={form.account || ""}
                onChange={(e) => onForm({ ...form, account: e.target.value })}
              />
            </div>
            {errors.bank ? (
              <p className="ferr" role="alert">
                {errors.bank}
              </p>
            ) : null}
            {field("holder", "Titular da Conta", {
              name: "holder_name",
              autoComplete: "name",
              placeholder: "Igual ao nome da conta",
            })}
          </>
        )}
        {errors._ ? (
          <p className="ferr" role="alert" style={{ marginTop: 10 }}>
            {errors._}
          </p>
        ) : null}
        <button
          onClick={onSubmit}
          disabled={!!busy}
          style={{ marginTop: 14 }}
        >
          {busy ? "Aguarde…" : isLogin ? "Entrar" : "Criar conta e entrar"}
        </button>
        <button
          className="ghost"
          style={{ width: "100%", marginTop: 8 }}
          onClick={() => onMode(isLogin ? "register" : "login")}
        >
          {isLogin ? "Ainda não tenho conta — criar" : "Já tenho conta — entrar"}
        </button>
        <button
          className="ghost"
          style={{ width: "100%", marginTop: 8 }}
          onClick={onFillTest}
          title="Preenche a conta de teste (Ana) para desenvolvimento"
        >
          Usar conta de teste
        </button>
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
