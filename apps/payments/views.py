import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.core.inputs import clean_phone
from apps.orders.models import Order
from apps.orders.workflow import confirm_mobile_money, customer_cancel

from . import services
from .models import Payout, Transaction
from .wallet import driver_available_balance, restaurant_available_balance

logger = logging.getLogger("oneeat")

CHANNELS = {"cm.mtn": "MTN Mobile Money", "cm.orange": "Orange Money"}


@csrf_exempt
@require_POST
def notchpay_webhook(request):
    """Notifications NotchPay : paiement collecte (commande) ou virement (retrait)."""
    raw = request.body
    signature = request.headers.get("X-Notch-Signature", "")
    if not services.verify_signature(raw, signature):
        logger.warning("Webhook NotchPay : signature invalide ou absente")
        return HttpResponseBadRequest("invalid signature")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return HttpResponseBadRequest("invalid json")

    event_type = payload.get("type", "")
    data = payload.get("data") or {}
    if event_type.startswith("payment."):
        _handle_payment_event(event_type, data)
    elif event_type.startswith("transfer."):
        _handle_transfer_event(event_type, data)
    return HttpResponse("ok")


def _handle_payment_event(event_type, data):
    reference = data.get("reference") or data.get("id")
    if not reference:
        return
    txn = (Transaction.objects.filter(notchpay_reference=reference).first()
           or Transaction.objects.filter(reference=reference).first())
    if not txn:
        logger.warning("Webhook NotchPay : transaction inconnue %s", reference)
        return

    if event_type == "payment.complete" and txn.status != Transaction.Status.PAID:
        txn.status = Transaction.Status.PAID
        txn.channel = data.get("channel", txn.channel)
        txn.raw_payload = data
        txn.save(update_fields=["status", "channel", "raw_payload", "updated_at"])
        with transaction.atomic():
            for order in txn.orders.select_related("restaurant"):
                confirm_mobile_money(order)
    elif event_type in ("payment.failed", "payment.canceled", "payment.expired"):
        txn.status = {
            "payment.failed": Transaction.Status.FAILED,
            "payment.canceled": Transaction.Status.CANCELLED,
            "payment.expired": Transaction.Status.EXPIRED,
        }[event_type]
        txn.raw_payload = data
        txn.save(update_fields=["status", "raw_payload", "updated_at"])
        for order in txn.orders.filter(status=Order.Status.PENDING,
                                       payment_status=Order.PaymentStatus.PENDING):
            customer_cancel(order, "Paiement NotchPay non abouti.")
    else:
        txn.raw_payload = data
        txn.save(update_fields=["raw_payload", "updated_at"])


def _handle_transfer_event(event_type, data):
    reference = data.get("reference") or data.get("id")
    if not reference:
        return
    payout = Payout.objects.filter(notchpay_transfer_ref=reference).first()
    if not payout:
        return
    if event_type == "transfer.complete":
        payout.status = Payout.Status.PAID
        payout.save(update_fields=["status", "updated_at"])
    elif event_type == "transfer.failed":
        payout.status = Payout.Status.FAILED
        payout.failure_reason = data.get("reason", "")[:255]
        payout.save(update_fields=["status", "failure_reason", "updated_at"])


@login_required
@require_POST
def request_payout(request):
    """Retrait restaurant/livreur vers Mobile Money — declenche un virement NotchPay reel."""
    user = request.user
    referer = request.META.get("HTTP_REFERER", "/")
    phone = clean_phone(request.POST.get("phone", ""))
    channel = request.POST.get("channel", "cm.mtn")
    try:
        amount = int(request.POST.get("amount", "0"))
    except ValueError:
        amount = 0

    if channel not in CHANNELS:
        messages.error(request, "Opérateur Mobile Money invalide.")
        return redirect(referer)
    if not phone or len(phone.lstrip("+")) < 9:
        messages.error(request, "Numéro Mobile Money invalide.")
        return redirect(referer)
    if amount <= 0:
        messages.error(request, "Montant de retrait invalide.")
        return redirect(referer)

    if user.is_restaurant:
        restaurant = user.restaurants.first()
        if not restaurant:
            messages.error(request, "Aucun restaurant associé à ce compte.")
            return redirect(referer)
        available = restaurant_available_balance(restaurant)
        recipient_type, kwargs = Payout.Recipient.RESTAURANT, {"restaurant": restaurant}
        display_name = restaurant.name
    elif user.is_driver:
        available = driver_available_balance(user)
        recipient_type, kwargs = Payout.Recipient.DRIVER, {"driver": user}
        display_name = user.display_name
    else:
        messages.error(request, "Fonction réservée aux restaurants et livreurs.")
        return redirect(referer)

    if amount > available:
        messages.error(request, f"Montant supérieur à votre solde disponible ({available} FCFA).")
        return redirect(referer)

    intl_phone = services.to_international_cm(phone)
    payout = Payout.objects.create(recipient_type=recipient_type, amount=amount, phone=phone,
                                   channel=channel, **kwargs)
    try:
        ben = services.create_beneficiary(name=display_name, phone=intl_phone, channel=channel,
                                          reference=f"ben_{payout.id}")
        payout.beneficiary_id = services.extract_reference(ben.get("beneficiary")) or str(
            ben.get("beneficiary", ""))
        transfer = services.create_transfer(
            amount=amount, currency="XAF", beneficiary_id=payout.beneficiary_id,
            description=f"Retrait ONE EAT — {display_name}", reference=f"payout_{payout.id}")
        payout.notchpay_transfer_ref = services.extract_reference(transfer.get("transfer"))
        payout.status = Payout.Status.PROCESSING
        payout.save(update_fields=["beneficiary_id", "notchpay_transfer_ref", "status",
                                   "updated_at"])
        messages.success(request, f"Retrait de {amount} FCFA vers {phone} en cours de traitement.")
    except services.NotchPayError as exc:
        payout.status = Payout.Status.FAILED
        payout.failure_reason = str(exc)[:255]
        payout.save(update_fields=["status", "failure_reason", "updated_at"])
        logger.exception("Echec du virement NotchPay pour le retrait #%s", payout.id)
        messages.error(request, "Le virement n'a pas pu être initié. Réessayez plus tard.")
    return redirect(referer)


# --- Diagnostic temporaire (reserve admin) : verifier depuis l'IP serveur reelle que
# /transfers passe la liste blanche NotchPay. A retirer apres verification. ---
@login_required
def diagnostic_transfer(request):
    if not request.user.is_staff:
        messages.error(request, "Réservé aux administrateurs.")
        return redirect("core:home")
    result = None
    if request.method == "POST":
        try:
            ben = services.create_beneficiary(name="Diag ONE EAT", phone="237694103585",
                                              channel="cm.orange", reference="diag_ben")
            ben_id = services.extract_reference(ben.get("beneficiary")) or str(
                ben.get("beneficiary"))
            transfer = services.create_transfer(amount=100, currency="XAF", beneficiary_id=ben_id,
                                                description="Diag transfer ONE EAT",
                                                reference="diag_transfer_1")
            result = {"ok": True, "beneficiary": ben, "transfer": transfer}
        except services.NotchPayError as exc:
            result = {"ok": False, "error": str(exc)}
    return render(request, "payments/diagnostic.html", {"result": result})
