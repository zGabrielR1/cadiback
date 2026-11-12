"""CryptAPI custom checkout. Stored invoice details, never callbacks, prove credit."""
import base64
import hmac
import json
import os
import secrets
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .crypto import CryptoCharge, CryptoError, read_env_pairs, SUPPORTED_COINS

ROOT = os.path.dirname(os.path.dirname(__file__))
TICKERS = {"btc": "btc", "eth": "eth", "ltc": "ltc", "usdttrc20": "trc20/usdt",
           "usdterc20": "erc20/usdt", "usdc": "erc20/usdc"}
PUBLIC_KEY = b"""-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC3FT0Ym8b3myVxhQW7ESuuu6lo
dGAsUJs4fq+Ey//jm27jQ7HHHDmP1YJO7XE7Jf/0DTEJgcw4EZhJFVwsk6d3+4fy
Bsn0tKeyGMiaE6cVkX0cy6Y85o8zgc/CwZKc0uw6d5siAo++xl2zl+RGMXCELQVE
ox7pp208zTvown577wIDAQAB
-----END PUBLIC KEY-----"""


@dataclass
class CryptapiConfig:
    wallets: dict = field(default_factory=dict)
    callback_base: str = "https://cadiback.onrender.com"
    env_name: str = "production"
    verification_token: str = ""

    @classmethod
    def from_env(cls, env=None, env_file=None):
        values = dict(env) if env is not None else {**read_env_pairs(env_file or os.path.join(ROOT, '.env.cryptapi')), **os.environ}
        wallets = {code: values.get('CRYPTAPI_WALLET_' + code.upper(), '').strip() for code in TICKERS}
        wallets = {k: v for k, v in wallets.items() if v}
        if any(any(c.isspace() for c in v) or any(c in v for c in '|@?&#') for v in wallets.values()):
            raise CryptoError('Endereço de recebimento CryptAPI inválido')
        base = values.get('CRYPTAPI_CALLBACK_BASE', 'https://cadiback.onrender.com').rstrip('/')
        if urlparse(base).scheme != 'https' or not urlparse(base).hostname:
            raise CryptoError('CryptAPI exige um domínio HTTPS de callback')
        return cls(wallets, base, verification_token=values.get('CRYPTAPI_VERIFICATION_TOKEN', '').strip())

    @property
    def configured(self):
        return bool(self.wallets)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise CryptoError('CryptAPI redirect refused')


def positive(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number <= 0:
            raise ValueError()
        return number
    except (InvalidOperation, TypeError, ValueError):
        raise CryptoError('CryptAPI devolveu um valor inválido') from None


@dataclass(frozen=True)
class CryptapiCharge(CryptoCharge):
    private: dict = field(default_factory=dict)


class CryptapiClient:
    def __init__(self, config, transport=None):
        self.config = config
        self.transport = transport

    def _call(self, ticker, endpoint, params=None):
        if ticker not in TICKERS.values():
            raise CryptoError('Rede CryptAPI não suportada')
        url = 'https://api.cryptapi.io/' + ticker + '/' + endpoint + '/'
        if params:
            url += '?' + urlencode(params)
        try:
            if self.transport:
                raw = self.transport(url)
            else:
                with build_opener(NoRedirect()).open(Request(url, headers={'User-Agent': 'Candibet/1.0'}), timeout=15) as response:
                    raw = json.load(response, parse_float=Decimal)
            if not isinstance(raw, dict) or raw.get('status') != 'success':
                raise ValueError()
            return raw
        except Exception:
            raise CryptoError('CryptAPI indisponível. Verifique a rede, o endereço e a verificação do domínio.') from None

    def coins(self):
        return [{'code': code, 'label': label} for code, label in SUPPORTED_COINS if code in self.config.wallets]

    def minimum_payment(self, coin, refresh=False):
        if coin not in self.config.wallets:
            raise CryptoError('Configure o endereço de recebimento desta rede no servidor.')
        raw = self._call(TICKERS[coin], 'info', {'prices': 1})
        minimum = positive(raw.get('minimum_transaction_coin'))
        price = positive((raw.get('prices') or {}).get('BRL'))
        return {'min_minor': int((minimum * price * 100).to_integral_value(rounding=ROUND_CEILING)),
                'min_crypto': str(minimum), 'currency': 'brl', 'pay_currency': coin,
                'provider': 'CryptAPI', 'valid_for_seconds': 60}

    def create_payment(self, *, txid, amount_cents, pay_currency, ipn_url='', **kwargs):
        minimum = self.minimum_payment(pay_currency, refresh=True)
        if amount_cents < minimum['min_minor']:
            raise CryptoError('Valor abaixo do mínimo desta rede CryptAPI.')
        ticker = TICKERS[pay_currency]
        amount = positive(self._call(ticker, 'convert', {'value': str(Decimal(amount_cents) / 100), 'from': 'BRL'}).get('value_coin'))
        amount = amount.quantize(Decimal(1).scaleb(-({'eth': 18, 'usdttrc20': 6, 'usdterc20': 6, 'usdc': 6}.get(pay_currency, 8))), rounding=ROUND_CEILING)
        if amount < positive(minimum['min_crypto']):
            raise CryptoError('A cotação mudou; aumente o valor e tente novamente.')
        nonce = secrets.token_urlsafe(32)
        callback = self.config.callback_base + '/api/webhooks/cryptapi?' + urlencode({'deposit_id': txid, 'nonce': nonce})
        address = self.config.wallets[pay_currency]
        raw = self._call(ticker, 'create', {'callback': callback, 'address': address, 'pending': 1,
                                         'post': 1, 'json': 1, 'multi_token': 0})
        if raw.get('callback_url') != callback or raw.get('address_out') != address or not raw.get('address_in'):
            raise CryptoError('Endereço CryptAPI divergente')
        provider_min = positive(raw.get('minimum_transaction_coin'))
        if amount < provider_min:
            raise CryptoError('O mínimo desta rede mudou; aumente o valor e tente novamente.')
        private = {'callback': callback, 'nonce': nonce, 'ticker': ticker, 'destination': address,
                   'expected_coin': str(amount), 'minimum_coin': str(provider_min)}
        return CryptapiCharge(txid, 'PENDING', amount_cents, str(raw['address_in']), pay_currency,
                              float(amount), 'brl', private)

    def get_invoice(self, row):
        details = row['cryptapi']
        raw = self._call(details['ticker'], 'logs', {'callback': details['callback']})
        if (raw.get('callback_url') != details['callback'] or raw.get('address_in') != row['pay_address']
                or raw.get('address_out') != details['destination']):
            raise CryptoError('Confirmação CryptAPI não corresponde ao depósito')
        total, seen = Decimal(0), set()
        for payment in raw.get('callbacks', []):
            txid = payment.get('txid_in')
            if not txid or txid in seen:
                continue
            seen.add(txid)
            confirmed = any(str(log.get('pending')) == '0' and str(log.get('confirmed')) == '1'
                            for log in payment.get('logs', []))
            if confirmed and payment.get('result') in ('sent', 'done') and payment.get('txid_out'):
                total += positive(payment.get('value_coin'))
        paid = total >= positive(details['expected_coin'])
        return CryptoCharge(row['provider_ref'], 'PAID' if paid else 'PENDING', int(row['amount_minor']),
                            row['pay_address'], row['pay_currency'], float(details['expected_coin']))


def verify_signature(raw, signature):
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        key = serialization.load_pem_public_key(PUBLIC_KEY)
        key.verify(base64.b64decode(signature, validate=True), raw, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def webhook(demo, raw, signature, query):
    if not verify_signature(raw, signature):
        raise PermissionError('Assinatura CryptAPI inválida')
    deposit_id = query.get('deposit_id', '')
    row = demo._get_crypto_charge(deposit_id)
    if not row or not row.get('cryptapi') or not hmac.compare_digest(query.get('nonce', ''), row['cryptapi']['nonce']):
        raise PermissionError('Callback CryptAPI desconhecido')
    demo.crypto_deposit_status({'player': row['player'], 'deposit_id': deposit_id})
