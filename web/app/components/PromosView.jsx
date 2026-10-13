"use client";

import { BRL } from "../../lib/api";

/** Promotions view: welcome bonus + daily cashback (F1 extract from
 * page.jsx). Real mechanics over the double-entry wallet; the page owns
 * the claim() handler, this view renders progress + claim buttons. */
export default function PromosView({ profile, player, busy, onClaim }) {
  return (
    <>
      <section className="panel">
        <h2>Promoções & Bônus</h2>
        <p className="sub" style={{ fontSize: 12.5 }}>
          Mecânicas reais sobre a carteira demo: cada resgate é um
          lançamento de bônus nos livros e o valor só vira saldo
          retirável quando a meta de giro é atingida.
        </p>
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
                  width: profile.bonus.event.percent + "%",
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
              </span>
              <span style={{ color: "var(--acc)" }}>
                {profile.bonus.event.percent}%
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
              ) : profile.bonus.can_claim_welcome ? (
                <button
                  disabled={busy}
                  onClick={() => onClaim("welcome")}
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
                Carregando…
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
              ) : profile.bonus.can_claim_cashback ? (
                <button
                  disabled={busy}
                  onClick={() => onClaim("cashback")}
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
                Carregando…
              </span>
            )}
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
          <summary>Como funcionam os jogos oficiais?</summary>
          <p>
            Todos os jogos oficiais de provedores líderes mundiais (Pragmatic Play, Spribe Aviator, Hacksaw Gaming, Play'n GO, Evolution) estão incorporados diretamente no site. Você joga diretamente em tela cheia com alta fidelidade sem necessidade de sair da plataforma.
          </p>
        </details>
        <details className="faq">
          <summary>Quais jogos estão disponíveis?</summary>
          <p>
            Você pode jogar Gates of Olympus, Aviator, Sweet Bonanza, Sugar Rush, Spaceman, Big Bass Bonanza, Roleta Europeia, Blackjack, Baccarat, além dos slots originais da casa.
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
            Sim! Toda a interface, menus, boletim de apostas e os jogos oficiais são totalmente responsivos para computadores, tablets e smartphones.
          </p>
        </details>
      </section>
    </>
  );
}
