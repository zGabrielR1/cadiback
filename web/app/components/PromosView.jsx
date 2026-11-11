"use client";

import { useRef, useState } from "react";
import { BRL } from "../../lib/api";

/** Promotions view: welcome bonus + daily cashback (F1 extract from
 * page.jsx). Real mechanics over the double-entry wallet; the page owns
 * the claim() handler, this view renders progress + claim buttons. */
export default function PromosView({ profile, player, busy, onClaim, onOptOut }) {
  const [pending, setPending] = useState("");
  const [actionError, setActionError] = useState("");
  const actionLock = useRef(false);
  const run = async (kind, action) => {
    if (busy || actionLock.current || !action) return;
    actionLock.current = true;
    setPending(kind);
    setActionError("");
    try { await action(); }
    catch { setActionError("Não foi possível concluir a ação. Atualize a conta antes de tentar novamente."); }
    finally { actionLock.current = false; setPending(""); }
  };
  const disabled = busy || !!pending;
  const optedOut = !!profile?.bonus?.opt_out;
  const event = profile?.bonus?.event;
  const percent = event && event.target_minor > 0 && Number.isFinite(event.wagered_minor)
    ? Math.min(100, Math.max(0, Math.floor(event.wagered_minor / event.target_minor * 100))) : 0;
  const remaining = event ? Math.max(0, event.target_minor - event.wagered_minor) : 0;
  return (
    <>
      <section className="panel">
        <h2>Promoções & Bônus</h2>
        <p className="sub" style={{ fontSize: 12.5 }}>
          Mecânicas reais sobre a carteira demo: cada resgate é um
          lançamento de bônus nos livros e o valor só vira saldo
          retirável quando a meta de giro é atingida.
        </p>
        {actionError ? <p className="account-notice err" role="alert">{actionError}</p> : null}
        {pending ? <p className="account-notice" role="status">{pending === "preference" ? "Salvando preferência…" : "Processando resgate…"}</p> : null}
        {profile && profile.bonus && profile.bonus.active && profile.bonus.event ? (
          <div className="promo" style={{ marginTop: 14, display: "block" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <b>
                {profile.bonus.event.kind === "welcome"
                  ? "Bônus de Boas-Vindas em andamento"
                  : "Cashback em andamento"}
              </b>
              <span style={{ color: "var(--acc)", fontWeight: 700 }}>
                {BRL(profile.bonus.event.granted_minor)} em bônus
              </span>
            </div>
            <div
              role="progressbar"
              aria-label="Giro do bônus"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={percent}
              aria-valuetext={`${percent}% concluído; faltam ${BRL(remaining)} em giro`}
              style={{
                height: 8,
                background: "var(--chip)",
                borderRadius: 6,
                overflow: "hidden",
                marginTop: 10,
                border: "1px solid var(--line)",
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: percent + "%",
                  background: "var(--acc)",
                  transition: "width .4s",
                }}
              />
            </div>
            <div
              className="gmeta"
              style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}
            >
              <span>
                Giro: {BRL(profile.bonus.event.wagered_minor)} de{" "}
                {BRL(profile.bonus.event.target_minor)}
                {remaining > 0 ? ` · faltam ${BRL(remaining)}` : " · meta atingida"}
              </span>
              <span style={{ color: "var(--acc)" }}>
                {percent}%
              </span>
            </div>
          </div>
        ) : null}
        <div className="promos" style={{ marginTop: 16 }}>
          <div className="promo">
            <b>Bônus de Boas-Vindas 100%</b>
            <span>
              100% do primeiro depósito até R$ 500, com giro de 20x
              sobre o valor do bônus antes de virar saldo retirável.
            </span>
            {profile && profile.bonus ? (
              profile.bonus.welcome_claimed ? (
                <span className="badge b-ok" style={{ marginTop: 8 }}>
                  ✓ resgatado
                </span>
              ) : optedOut ? <span className="gmeta" style={{ display: "block", marginTop: 8 }}>Promoções desativadas para esta conta.</span> : profile.bonus.can_claim_welcome ? (
                <button
                  disabled={disabled || !onClaim}
                  onClick={() => run("welcome", () => onClaim("welcome"))}
                  style={{ marginTop: 8 }}
                >
                  Resgatar Bônus
                </button>
              ) : (
                <span className="gmeta" style={{ display: "block", marginTop: 8 }}>
                  {!player
                    ? "Entre para resgatar."
                    : profile.bonus.first_deposit_minor === 0
                    ? "Faça um primeiro depósito de ao menos R$20."
                    : "Primeiro depósito abaixo do mínimo de R$20."}
                </span>
              )
            ) : (
              <span className="gmeta" style={{ display: "block", marginTop: 8 }}>
                {player ? "Carregando promoções…" : "Entre para consultar seus bônus."}
              </span>
            )}
          </div>
          <div className="promo">
            <b>Cashback Diário de 10%</b>
            <span>
              10% das perdas líquidas de hoje (máx. R$ 200), com giro
              1x. Um resgate por dia.
            </span>
            {profile && profile.bonus ? (
              profile.bonus.cashback_claimed_today ? (
                <span className="badge b-ok" style={{ marginTop: 8 }}>
                  ✓ resgatado hoje
                </span>
              ) : optedOut ? <span className="gmeta" style={{ display: "block", marginTop: 8 }}>Promoções desativadas para esta conta.</span> : profile.bonus.can_claim_cashback ? (
                <button
                  disabled={disabled || !onClaim}
                  onClick={() => run("cashback", () => onClaim("cashback"))}
                  style={{ marginTop: 8 }}
                >
                  Resgatar {BRL(profile.bonus.cashback_available_minor)}
                </button>
              ) : (
                <span className="gmeta" style={{ display: "block", marginTop: 8 }}>
                  {!player
                    ? "Entre para ver seu cashback."
                    : "Sem perdas líquidas hoje."}
                </span>
              )
            ) : (
              <span className="gmeta" style={{ display: "block", marginTop: 8 }}>
                {player ? "Carregando promoções…" : "Entre para consultar seu cashback."}
              </span>
            )}
          </div>
          <div className="promo">
            <b>Promoções para esta conta</b>
            <span>
              {profile?.bonus?.opt_out
                ? "Você desativou promoções. Bônus ativos continuam valendo até vencerem, mas nada novo será oferecido."
                : "Ative ou desative promoções quando quiser. Desativar não apaga o saldo de bônus atual."}
            </span>
            <button className="ghost" style={{ marginTop: 8 }} disabled={disabled || !profile?.bonus || !onOptOut} onClick={() => run("preference", () => onOptOut(!optedOut))}>
              {profile?.bonus?.opt_out ? "Reativar promoções" : "Desativar promoções"}
            </button>
          </div>
          <div className="promo">
            <b>Super Odds em Destaque</b>
            <span>
              Cotações turbinadas em +10% nos destaques do lobby,
              sobre o feed público de partidas.
            </span>
          </div>
        </div>
      </section>
      <section className="panel">
        <h2>Dúvidas Frequentes</h2>
        <details className="faq" open>
          <summary>Como funcionam as cotações?</summary>
          <p>
            As cotações são geradas pelo modelo da casa sobre o feed público de
            partidas. Cada mercado é reprecificado a cada 30 segundos, e a
            cotação exibida no boletim é conferida novamente antes do envio.
          </p>
        </details>
        <details className="faq">
          <summary>Quais esportes estão disponíveis?</summary>
          <p>
            Futebol, tênis, basquete, hóquei, beisebol, handebol, rugby, vôlei,
            e-sports e futsal, com mercados de resultado, totais, dupla chance e
            handicap conforme as regras de cada esporte.
          </p>
        </details>
        <details className="faq">
          <summary>Como funciona o saldo e pagamentos?</summary>
          <p>
            Esta é uma plataforma de demonstração desenvolvida para fins de hobby e uso pessoal. Todos os depósitos e saques utilizam saldo virtual demonstrativo com liquidação instantânea via simulação Pix.
          </p>
        </details>
        <details className="faq">
          <summary>A plataforma funciona no celular?</summary>
          <p>
            Sim! Toda a interface, menus, boletim de apostas e mercados são totalmente responsivos para computadores, tablets e smartphones.
          </p>
        </details>
      </section>
    </>
  );
}
