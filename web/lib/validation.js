/** Client-side account validation — mirrors demo/payments.py so the form
 * refuses the same values the server would, before any request is sent. */

export function validateEmail(value) {
  const v = String(value || "").trim().toLowerCase();
  if (!v || v.length > 254) return "email inválido";
  if (!/^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/.test(v))
    return "email inválido";
  return "";
}

export function cpfDigits(value) {
  return String(value || "").replace(/\D/g, "");
}

function checkDigit(number, weights) {
  let sum = 0;
  for (let i = 0; i < weights.length; i++) sum += Number(number[i]) * weights[i];
  const mod = sum % 11;
  return mod < 2 ? 0 : 11 - mod;
}

export function validateCPF(value) {
  if (!/^[0-9.\-\s]+$/.test(String(value || ""))) return "CPF inválido";
  const n = cpfDigits(value);
  if (n.length !== 11 || /^(\d)\1{10}$/.test(n)) return "CPF inválido";
  const d1 = checkDigit(
    n,
    [10, 9, 8, 7, 6, 5, 4, 3, 2]
  );
  const d2 = checkDigit(
    n,
    [11, 10, 9, 8, 7, 6, 5, 4, 3, 2]
  );
  if (Number(n[9]) !== d1 || Number(n[10]) !== d2)
    return "CPF inválido — dígitos verificadores não conferem";
  return "";
}

export function cnpjCharacters(value) {
  return String(value || "").replace(/[./\-\s]/g, "").toUpperCase();
}

export function validateCNPJ(value) {
  const n = cnpjCharacters(value);
  if (!/^[A-Z0-9]{12}[0-9]{2}$/.test(n) || /^(.)\1{13}$/.test(n)) return "CNPJ inválido";
  const weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  for (const [length, factors] of [[12, weights], [13, [6, ...weights]]]) {
    const sum = factors.reduce((total, weight, i) => total + (n.charCodeAt(i) - 48) * weight, 0);
    const mod = sum % 11;
    if (Number(n[length]) !== (mod < 2 ? 0 : 11 - mod))
      return "CNPJ inválido — dígitos verificadores não conferem";
  }
  return "";
}

export function formatCPF(value) {
  const n = cpfDigits(value).slice(0, 11);
  return n.replace(/^(\d{3})(\d)/, "$1.$2").replace(/^(\d{3}\.\d{3})(\d)/, "$1.$2")
    .replace(/(\.\d{3})(\d{1,2})$/, "$1-$2");
}

export function formatCNPJ(value) {
  const n = String(value || "").replace(/[^A-Za-z0-9]/g, "").toUpperCase().slice(0, 14);
  return n.replace(/^(.{2})(.)/, "$1.$2").replace(/^(.{2}\..{3})(.)/, "$1.$2")
    .replace(/^(..\....\....)(.)/, "$1/$2").replace(/(\/.{4})(.{1,2})$/, "$1-$2");
}

export function validatePassword(value) {
  const v = String(value || "");
  if (v.length < 6 || v.length > 128)
    return "a senha precisa de ao menos 6 caracteres";
  if (!/[A-Za-z]/.test(v) || !/[0-9]/.test(v))
    return "a senha precisa de letras e números";
  return "";
}

export function validateName(value) {
  if (String(value || "").trim().length < 2) return "informe seu nome completo";
  return "";
}

export function validateUsername(value) {
  const v = String(value || "").trim().toLowerCase();
  if (!/^[a-z0-9][a-z0-9._-]{2,19}$/.test(v))
    return "usuário: 3-20 caracteres (letras, números, . _ -), começando por letra ou número";
  return "";
}
