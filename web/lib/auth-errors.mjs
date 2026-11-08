/** Provider details are for diagnostics; the account dialog needs a recovery action. */
export function socialErrorMessage(value = "") {
  const reason = String(value).toLowerCase();
  if (/state|expired|sessão|session/.test(reason)) {
    return "Seu acesso social expirou. Escolha o provedor para começar novamente.";
  }
  if (/denied|cancel|access_denied/.test(reason)) {
    return "O acesso não foi autorizado. Você pode tentar novamente ou entrar com sua senha.";
  }
  return "Não foi possível concluir o login social. Tente novamente com o provedor ou entre com sua senha.";
}
