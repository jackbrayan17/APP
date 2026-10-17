"""Client HTTP pour l'API NotchPay : collecte (carte + Mobile Money) et virements.

Doc : https://developer.notchpay.co/api-reference/index
- Initialisation paiement : POST /payments, header Authorization = cle publique.
- Operations sensibles (transferts, beneficiaires, solde) : header X-Grant = cle privee,
  en plus de Authorization.
- Signature webhook : HMAC-SHA256(corps brut, hash key) comparee au header
  X-Notch-Signature.
"""
import hashlib
import hmac
import logging

import requests
from django.conf import settings

logger = logging.getLogger("oneeat")


class NotchPayError(Exception):
    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response


def _headers(with_grant=False):
    headers = {
        "Authorization": settings.NOTCHPAY_PUBLIC_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if with_grant:
        headers["X-Grant"] = settings.NOTCHPAY_SECRET_KEY
    return headers


def _request(method, path, with_grant=False, **kwargs):
    url = f"{settings.NOTCHPAY_BASE_URL}{path}"
    try:
        resp = requests.request(method, url, headers=_headers(with_grant), timeout=20, **kwargs)
    except requests.RequestException as exc:
        logger.exception("NotchPay %s %s a échoué", method, path)
        raise NotchPayError(f"Connexion à NotchPay impossible : {exc}") from exc
    if resp.status_code >= 400:
        detail = resp.text[:500]
        logger.error("NotchPay %s %s -> %s: %s", method, path, resp.status_code, detail)
        raise NotchPayError(f"NotchPay a refusé la requête ({resp.status_code}) : {detail}",
                            response=resp)
    return resp.json()


def create_payment(*, amount, currency, reference, callback_url, email=None, phone=None,
                   description=""):
    """Initie un paiement hosted-checkout. Reponse : transaction (ref) + authorization_url."""
    body = {
        "amount": int(amount), "currency": currency, "reference": reference,
        "description": description, "callback": callback_url,
    }
    if email:
        body["email"] = email
    if phone:
        body["phone"] = phone
    return _request("POST", "/payments", json=body)


def get_payment(reference):
    return _request("GET", f"/payments/{reference}", with_grant=True)


def create_beneficiary(*, name, phone, channel, country="CM", reference=""):
    body = {
        "name": name, "channel": channel, "account_number": phone, "phone": phone,
        "country": country, "reference": reference,
    }
    return _request("POST", "/beneficiaries", with_grant=True, json=body)


def create_transfer(*, amount, currency, beneficiary_id, description, reference=""):
    body = {
        "amount": int(amount), "currency": currency, "beneficiary": beneficiary_id,
        "description": description, "reference": reference,
    }
    return _request("POST", "/transfers", with_grant=True, json=body)


def extract_reference(value):
    """La reponse NotchPay imbrique parfois la reference dans un objet
    ({"transaction": {"reference": "trx.xxx", ...}}) plutot que de la renvoyer nue,
    malgre ce que suggere la doc. On gere les deux formes."""
    if isinstance(value, dict):
        return str(value.get("reference") or value.get("id") or "")
    return str(value or "")


def to_international_cm(phone):
    """Normalise un numero camerounais vers le format attendu par NotchPay (237XXXXXXXXX)."""
    digits = (phone or "").lstrip("+")
    if not digits:
        return ""
    if not digits.startswith("237"):
        digits = "237" + digits
    return digits


def verify_signature(raw_body: bytes, signature: str) -> bool:
    if not signature or not settings.NOTCHPAY_HASH_KEY:
        return False
    computed = hmac.new(settings.NOTCHPAY_HASH_KEY.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)
