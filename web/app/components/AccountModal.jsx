"use client";

import { useEffect, useState } from "react";
import TurnstileWidget from "./TurnstileWidget";

/** Player login, registration and social completion (Entrar / Criar conta /
 * Complete seu cadastro). Real-site shape: login takes username, email or CPF
 * plus password; registration takes name, username, email, CPF, password, the
 * Pix key and — only when the operator requires it — the payout account;
 * "complete" is the social path, where the name/email come from the provider
 * and the player still supplies the CPF that keys the wallet (plus a username
 * and Pix key). Every field is validated here and again on the server
 * (demo/payments.py + Demo.register_player); the page owns the form state and
 * the submit, this modal only renders.
 *
 * Test accounts are invisible: there is no button. Ctrl+Shift+T while the
 * modal is open fills the built-in test identity, and only while the
 * operator's test_accounts_enabled setting is on. */
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
  social = null,
  onForm,
  onMode,
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
      if (event.ctrlKey && event.shiftKey &&
          (event.key === "T" || event.key === "t")) {
        event.preventDefault();
        onFillTest();
        setSecretFilled(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, testAccountsEnabled, onFillTest]);

  if (!open) return null;
  const isComplete = mode === "complete";
  const isLogin = mode !== "register" && !isComplete;
  const title = isComplete
    ? "Complete seu cadastro"
    : isLogin
      ? "Entrar"
      : "Criar sua conta";
  const subtitle = isComplete
    ? "Você entrou com " + (social?.provider || "sua conta social") +
      ". Falta o CPF para abrir sua carteira (uma conta por CPF) e escolher um usuário."
    : isLogin
      ? "Acesse com seu usuário, email ou CPF e sua senha."
      : "Uma conta por CPF. Validação de usuário, email e CPF no navegador e no servidor.";
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
  const socialRow = !isComplete && oauthProviders.length > 0 ? (
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
          {p.label}
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
        {isComplete ? (
          <>
            <label>Nome</label>
            <input value={social?.name || ""} readOnly disabled />
            <label>Email</label>
            <input value={social?.email || ""} readOnly disabled />
            {field(
              "cpf",
              "CPF",
              {
                name: "cpf",
                inputMode: "numeric",
                autoComplete: "off",
                placeholder: "000.000.000-00",
              },
              "Obrigatório e único: é a chave da sua carteira."
            )}
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
            {field("pix", "Chave Pix", {
              name: "pix_key",
              autoComplete: "off",
              placeholder: "CPF, email, telefone ou EVP",
            })}
            {field(
              "password",
              "Senha (opcional)",
              {
                name: "password",
                type: "password",
                autoComplete: "new-password",
                placeholder: "Defina se quiser entrar sem a conta social",
              },
              "Sem senha, você entra apenas com " +
                (social?.provider || "sua conta social") + "."
            )}
          </>
        ) : isLogin ? (
          <>
            {field("identifier", "Usuário, email ou CPF", {
              name: "identifier",
              autoComplete: "username",
              placeholder: "seu.usuario, voce@email.com ou 000.000.000-00",
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
        {errors._ ? (
          <p className="ferr" role="alert" style={{ marginTop: 10 }}>
            {errors._}
          </p>
        ) : null}
        {socialRow}
        {turnstileSiteKey && !isComplete ? (
          <div style={{ marginTop: 12 }}>
            <TurnstileWidget
              siteKey={turnstileSiteKey}
              action={isLogin ? "login" : "register"}
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
            : isComplete
              ? "Verificar CPF e entrar"
              : isLogin
                ? "Entrar"
                : "Criar conta e entrar"}
        </button>
        {secretFilled ? (
          <p className="fhint" style={{ marginTop: 8 }} role="status">
            {isLogin
              ? "Conta de teste preenchida — envie para entrar."
              : "Conta de teste preenchida — crie a conta para entrar."}
          </p>
        ) : null}
        {isComplete ? null : (
          <button
            className="ghost"
            style={{ width: "100%", marginTop: 8 }}
            onClick={() => onMode(isLogin ? "register" : "login")}
          >
            {isLogin ? "Ainda não tenho conta — criar" : "Já tenho conta — entrar"}
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
