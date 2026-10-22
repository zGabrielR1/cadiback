"use client";

import { useEffect, useState } from "react";
import TurnstileWidget from "./TurnstileWidget";
import OAuthIcon from "./OAuthIcon";
import { formatCPF, formatCNPJ, validateCPF, validateCNPJ, cpfDigits, cnpjCharacters } from "../../lib/validation";

/** Manual PF/PJ signup and password login. Social providers sign in directly;
 * the first withdrawal collects their Pix destination. Document validation
 * checks formatting/check digits, not registration status or ownership. */
export default function AccountModal({
  open,
  mode,
  form,
  errors,
  busy,
  requireBank = false,
  testAccountsEnabled = false,
  turnstileSiteKey = "",
  turnstileReset = 0,
  oauthProviders = [],
  remember = true,
  notice = "",
  passwordResetEnabled = false,
  onForm,
  onMode,
  onRemember,
  onSubmit,
  onSocial,
  onTurnstileToken,
  onFillTest,
  onClose,
}) {
  const [secretFilled, setSecretFilled] = useState(false);

  useEffect(() => {
    if (!open) {
      setSecretFilled(false);
      return undefined;
    }
    const onKey = (event) => {
      if (!testAccountsEnabled) return;
      if (mode !== "login" && mode !== "register") return;
      if (event.ctrlKey && event.shiftKey &&
          (event.key === "T" || event.key === "t")) {
        event.preventDefault();
        onFillTest();
        setSecretFilled(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, testAccountsEnabled, onFillTest, mode]);

  if (!open) return null;
  const isLogin = mode === "login";
  const isRegister = mode === "register";
  const isForgot = mode === "forgot";
  const isReset = mode === "reset";
  const title = isLogin
      ? "Entrar"
      : isRegister
        ? "Criar sua conta"
        : isForgot
          ? "Esqueci minha senha"
          : "Criar nova senha";
  const subtitle = isLogin
      ? "Acesse com seu usuário, email, CPF ou CNPJ e sua senha."
      : isRegister
        ? "Escolha PF ou PJ. CPF e CNPJ são formatados e validados antes do cadastro."
        : isForgot
          ? "Informe o email da sua conta. Se ela existir, enviaremos um link para criar uma nova senha."
          : "Escolha uma nova senha. O link que você abriu só pode ser usado uma vez.";
  const fieldErrors = { ...errors };
  const documentKind = form.person_type === "PJ" ? "cnpj" : "cpf";
  const completeDocument = documentKind === "cnpj"
    ? cnpjCharacters(form.cnpj).length === 14 : cpfDigits(form.cpf).length === 11;
  const documentError = documentKind === "cnpj" ? validateCNPJ(form.cnpj) : validateCPF(form.cpf);
  if (isRegister && completeDocument) fieldErrors[documentKind] = documentError;
  const field = (id, label, props, hint) => (
    <>
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        value={form[props.name] || ""}
        onChange={(e) => onForm({ ...form, [props.name]: props.name === "cpf" ? formatCPF(e.target.value) : props.name === "cnpj" ? formatCNPJ(e.target.value) : e.target.value })}
        aria-invalid={fieldErrors[props.name] ? "true" : undefined}
        {...props}
      />
      {fieldErrors[props.name] ? (
        <p className="ferr" role="alert">
          {fieldErrors[props.name]}
        </p>
      ) : props.name === documentKind && completeDocument && !documentError ? (
        <p className="fok" role="status">{documentKind.toUpperCase()} válido — dígitos verificadores conferem.</p>
      ) : hint ? (
        <p className="fhint">{hint}</p>
      ) : null}
    </>
  );
  const socialRow = (isLogin || isRegister) && oauthProviders.length > 0 ? (
    <div className="oauth-row">
      <span className="oauth-note">ou continue com</span>
      {oauthProviders.map((p) => (
        <button
          key={p.id}
          type="button"
          className={"oauth-btn oauth-" + p.id}
          onClick={() => onSocial(p.id)}
          disabled={!!busy}
        >
          <OAuthIcon provider={p.id} />
          <span>Continuar com {p.label}</span>
        </button>
      ))}
    </div>
  ) : null;
  return (
    <div
      className={"modal" + (open ? " open" : "")}
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="sheet">
        <h3>{title}</h3>
        <p className="sub">{subtitle}</p>
        {isLogin ? (
          <>
            {field("identifier", "Usuário, email, CPF ou CNPJ", {
              name: "identifier",
              autoComplete: "username",
              placeholder: "Usuário, email, CPF ou CNPJ",
            })}
            {field("password", "Senha", {
              name: "password",
              type: "password",
              autoComplete: "current-password",
              placeholder: "••••••",
            })}
            {passwordResetEnabled ? (
              <button
                type="button"
                className="ghost"
                style={{ width: "100%", marginTop: 6 }}
                onClick={() => onMode("forgot")}
              >
                Esqueci minha senha
              </button>
            ) : null}
          </>
        ) : isForgot ? (
          <>
            {field("identifier", "Email da conta", {
              name: "identifier",
              autoComplete: "email",
              inputMode: "email",
              placeholder: "voce@email.com",
            })}
          </>
        ) : isReset ? (
          <>
            {field(
              "password",
              "Nova senha",
              {
                name: "password",
                type: "password",
                autoComplete: "new-password",
                placeholder: "Mínimo 6 caracteres, letras e números",
              },
              "Mínimo 6 caracteres, com letras e números."
            )}
            {field("password_confirm", "Confirme a nova senha", {
              name: "password_confirm",
              type: "password",
              autoComplete: "new-password",
              placeholder: "Repita a nova senha",
            })}
          </>
        ) : (
          <>
            <label htmlFor="person-type">Tipo de conta</label>
            <select id="person-type" value={form.person_type || "PF"}
              onChange={(e) => onForm({ ...form, person_type: e.target.value, cpf: "", cnpj: "" })}>
              <option value="PF">Pessoa física (PF)</option>
              <option value="PJ">Pessoa jurídica (PJ)</option>
            </select>
            {field("name", form.person_type === "PJ" ? "Razão social" : "Nome completo", {
              name: "name",
              autoComplete: form.person_type === "PJ" ? "organization" : "name",
              placeholder: "Como está no seu documento",
            })}
            {field(
              "username",
              "Nome de usuário",
              {
                name: "username",
                autoComplete: "username",
                autoCapitalize: "none",
                spellCheck: "false",
                placeholder: "seu.usuario",
              },
              "3-20 caracteres: letras, números, ponto, hífen ou _."
            )}
            {field("email", "Email", {
              name: "email",
              autoComplete: "email",
              inputMode: "email",
              placeholder: "voce@email.com",
            })}
            {form.person_type === "PJ" ? field("cnpj", "CNPJ", {
              name: "cnpj", inputMode: "text", autoCapitalize: "characters",
              autoComplete: "off", maxLength: 18, placeholder: "00.000.000/0000-00",
            }, "Aceita CNPJ numérico ou alfanumérico.") : field("cpf", "CPF", {
              name: "cpf", inputMode: "numeric", autoComplete: "off",
              maxLength: 14, placeholder: "000.000.000-00",
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
            <label htmlFor="bank">
              Banco / Agência / Conta{requireBank ? "" : " (opcional)"}
            </label>
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
            ) : requireBank ? null : (
              <p className="fhint">
                Opcional — o saque cai na sua chave Pix. Preencha só se
                quiser (e o titular deve ser você).
              </p>
            )}
            {field(
              "holder",
              requireBank ? "Titular da Conta" : "Titular da Conta (opcional)",
              {
                name: "holder_name",
                autoComplete: "name",
                placeholder: "Igual ao nome da conta",
              }
            )}
          </>
        )}
        {isLogin ? (
          <label className="remember">
            <input
              type="checkbox"
              checked={!!remember}
              onChange={(e) => onRemember(e.target.checked)}
            />
            <span>Lembrar de mim neste dispositivo</span>
          </label>
        ) : null}
        {notice ? (
          <p className="fok" role="status" style={{ marginTop: 10 }}>
            {notice}
          </p>
        ) : null}
        {errors._ ? (
          <p className="ferr" role="alert" style={{ marginTop: 10 }}>
            {errors._}
          </p>
        ) : null}
        {socialRow}
        {turnstileSiteKey && (isLogin || isRegister || isForgot) ? (
          <div style={{ marginTop: 12 }}>
            <TurnstileWidget
              siteKey={turnstileSiteKey}
              action={
                isLogin ? "login" : isForgot ? "password_reset" : "register"
              }
              onToken={onTurnstileToken}
              resetSignal={turnstileReset}
            />
            {errors.turnstile ? (
              <p className="ferr" role="alert">
                {errors.turnstile}
              </p>
            ) : null}
          </div>
        ) : null}
        <button
          onClick={onSubmit}
          disabled={!!busy}
          style={{ marginTop: 14 }}
        >
          {busy
            ? "Aguarde…"
            : isLogin
                ? "Entrar"
                : isRegister
                  ? "Criar conta e entrar"
                  : isForgot
                    ? "Enviar link"
                    : "Redefinir senha"}
        </button>
        {secretFilled ? (
          <p className="fhint" style={{ marginTop: 8 }} role="status">
            {isLogin
              ? "Conta de teste preenchida — envie para entrar."
              : "Conta de teste preenchida — crie a conta para entrar."}
          </p>
        ) : null}
        {(
          <button
            className="ghost"
            style={{ width: "100%", marginTop: 8 }}
            onClick={() =>
              onMode(isLogin ? "register" : isRegister ? "login" : "login")
            }
          >
            {isLogin
              ? "Ainda não tenho conta — criar"
              : isRegister
                ? "Já tenho conta — entrar"
                : "Voltar para entrar"}
          </button>
        )}
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
