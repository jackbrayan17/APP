from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Transaction(TimeStampedModel):
    """Paiement NotchPay (collecte client, carte ou Mobile Money) lié a une ou plusieurs commandes."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        PAID = "paid", "Payé"
        FAILED = "failed", "Échoué"
        CANCELLED = "cancelled", "Annulé"
        EXPIRED = "expired", "Expiré"

    reference = models.CharField(max_length=60, unique=True, db_index=True)
    notchpay_reference = models.CharField(max_length=80, blank=True, db_index=True)
    orders = models.ManyToManyField("orders.Order", related_name="transactions", blank=True)
    amount = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="XAF")
    channel = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    authorization_url = models.URLField(blank=True, max_length=500)
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} — {self.amount} {self.currency} ({self.status})"


class Payout(TimeStampedModel):
    """Demande de retrait (restaurant / livreur) vers un compte Mobile Money."""

    class Recipient(models.TextChoices):
        RESTAURANT = "restaurant", "Restaurant"
        DRIVER = "driver", "Livreur"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        PROCESSING = "processing", "En cours"
        PAID = "paid", "Payé"
        FAILED = "failed", "Échoué"

    recipient_type = models.CharField(max_length=10, choices=Recipient.choices)
    restaurant = models.ForeignKey("restaurants.Restaurant", null=True, blank=True,
                                   on_delete=models.CASCADE, related_name="payouts")
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                               on_delete=models.CASCADE, related_name="payouts")
    amount = models.PositiveIntegerField()
    phone = models.CharField(max_length=20)
    channel = models.CharField(max_length=20, default="cm.mtn")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    beneficiary_id = models.CharField(max_length=80, blank=True)
    notchpay_transfer_ref = models.CharField(max_length=80, blank=True, db_index=True)
    failure_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Retrait {self.amount} FCFA — {self.get_status_display()}"
