import hashlib
import hmac
import json

from django.test import TestCase, override_settings

from . import services
from .models import Transaction


@override_settings(NOTCHPAY_HASH_KEY="hsk_test_dummy")
class WebhookSignatureTests(TestCase):
    def _sign(self, body: bytes) -> str:
        return hmac.new(b"hsk_test_dummy", body, hashlib.sha256).hexdigest()

    def test_valid_signature_accepted(self):
        body = json.dumps({"type": "payment.complete", "data": {"reference": "x"}}).encode()
        self.assertTrue(services.verify_signature(body, self._sign(body)))

    def test_tampered_body_rejected(self):
        body = json.dumps({"type": "payment.complete", "data": {"reference": "x"}}).encode()
        sig = self._sign(body)
        tampered = json.dumps({"type": "payment.complete", "data": {"reference": "y"}}).encode()
        self.assertFalse(services.verify_signature(tampered, sig))

    def test_missing_signature_rejected(self):
        self.assertFalse(services.verify_signature(b"{}", ""))


class WebhookEndpointTests(TestCase):
    def _sign(self, body: bytes) -> str:
        from django.conf import settings
        return hmac.new(settings.NOTCHPAY_HASH_KEY.encode(), body, hashlib.sha256).hexdigest()

    def test_payment_complete_marks_transaction_paid(self):
        txn = Transaction.objects.create(reference="pay_test_1", amount=1000, currency="XAF")
        body = json.dumps({
            "type": "payment.complete",
            "data": {"reference": txn.reference, "channel": "cm.mtn"},
        }).encode()
        resp = self.client.post("/webhooks/notchpay/", data=body,
                                content_type="application/json",
                                HTTP_X_NOTCH_SIGNATURE=self._sign(body))
        self.assertEqual(resp.status_code, 200)
        txn.refresh_from_db()
        self.assertEqual(txn.status, Transaction.Status.PAID)

    def test_invalid_signature_rejected(self):
        resp = self.client.post("/webhooks/notchpay/", data=b"{}",
                                content_type="application/json",
                                HTTP_X_NOTCH_SIGNATURE="bad")
        self.assertEqual(resp.status_code, 400)
