from django.conf import settings
from django.db import models
from django.utils.crypto import get_random_string

from apps.core.models import TimeStampedModel
from apps.restaurants.models import Restaurant, Dish


class Order(TimeStampedModel):
    """Commande client."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        CONFIRMED = "confirmed", "Confirmée"
        PREPARING = "preparing", "En préparation"
        READY = "ready", "Prête"
        PICKED_UP = "picked_up", "Récupérée"
        ON_THE_WAY = "on_the_way", "En route"
        DELIVERED = "delivered", "Livrée"
        CANCELLED = "cancelled", "Annulée"

    class Payment(models.TextChoices):
        CASH = "cash", "Espèces à la livraison"
        MOMO = "momo", "MTN Mobile Money"
        OM = "om", "Orange Money"
        CARD = "card", "Carte bancaire"

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "En attente de paiement"
        PAID = "paid", "Payé"
        ON_DELIVERY = "on_delivery", "À payer à la livraison"
        REFUNDED = "refunded", "Remboursé"

    number = models.CharField(max_length=14, unique=True, blank=True, db_index=True)
    share_token = models.CharField(max_length=22, unique=True, blank=True, db_index=True)

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name="orders")
    restaurant = models.ForeignKey(Restaurant, on_delete=models.PROTECT, related_name="orders")
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                               null=True, blank=True, related_name="deliveries")

    status = models.CharField(max_length=14, choices=Status.choices, default=Status.PENDING)
    payment_method = models.CharField(max_length=8, choices=Payment.choices, default=Payment.CASH)
    payment_status = models.CharField(max_length=12, choices=PaymentStatus.choices,
                                      default=PaymentStatus.ON_DELIVERY)
    payment_phone = models.CharField(max_length=20, blank=True,
                                     help_text="Numero Mobile Money debite")

    # Montants (FCFA)
    items_total = models.PositiveIntegerField(default=0)
    delivery_fee = models.PositiveIntegerField(default=0)
    discount = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)

    # Livraison / geolocalisation
    delivery_address = models.CharField(max_length=255, blank=True)
    delivery_lat = models.FloatField(null=True, blank=True)
    delivery_lng = models.FloatField(null=True, blank=True)
    # Position courante du livreur (suivi temps reel simplifie)
    driver_lat = models.FloatField(null=True, blank=True)
    driver_lng = models.FloatField(null=True, blank=True)

    notes = models.TextField(blank=True)
    promo_code = models.CharField(max_length=24, blank=True)

    confirmed_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    driver_assigned_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["-created_at"])]

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = "OE" + get_random_string(8, "0123456789")
        if not self.share_token:
            self.share_token = get_random_string(16)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} — {self.restaurant.name}"

    @property
    def item_count(self):
        return sum(i.quantity for i in self.items.all())

    @property
    def status_label(self):
        return self.get_status_display()

    @property
    def is_active(self):
        return self.status not in (self.Status.DELIVERED, self.Status.CANCELLED)

    @property
    def is_awaiting_payment(self):
        return self.payment_status == self.PaymentStatus.PENDING

    @property
    def is_cancellable_by_customer(self):
        return self.status == self.Status.PENDING

    @property
    def restaurant_revenue(self):
        """Montant revenant au restaurant (articles - remise, hors livraison)."""
        return max(0, self.items_total - self.discount)

    @property
    def progress_step(self):
        """Etape 0-4 pour les barres de progression (commande -> livree)."""
        return {
            self.Status.PENDING: 0, self.Status.CONFIRMED: 1, self.Status.PREPARING: 2,
            self.Status.READY: 2, self.Status.PICKED_UP: 3, self.Status.ON_THE_WAY: 3,
            self.Status.DELIVERED: 4,
        }.get(self.status, 0)

    @property
    def customer_status_text(self):
        """Phrase claire du point de vue du client."""
        S = self.Status
        if self.is_awaiting_payment and self.status == S.PENDING:
            return "Validez le paiement Mobile Money pour transmettre la commande."
        return {
            S.PENDING: "Le restaurant examine votre commande.",
            S.CONFIRMED: "Commande acceptée, la cuisine s'organise.",
            S.PREPARING: "Vos plats sont en cours de préparation.",
            S.READY: ("Prête ! Le livreur arrive au restaurant." if self.driver_id
                      else "Prête ! Nous cherchons un livreur."),
            S.PICKED_UP: "Le livreur a récupéré votre commande.",
            S.ON_THE_WAY: "Votre livreur est en route vers vous.",
            S.DELIVERED: "Livrée. Bon appétit !",
            S.CANCELLED: "Commande annulée." + (f" {self.cancel_reason}" if self.cancel_reason else ""),
        }.get(self.status, "")

    @property
    def can_review(self):
        return self.status == self.Status.DELIVERED and not hasattr(self, "review")

    def recompute_totals(self):
        self.items_total = sum(i.line_total for i in self.items.all())
        self.total = max(0, self.items_total + self.delivery_fee - self.discount)
        self.save(update_fields=["items_total", "total"])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    dish = models.ForeignKey(Dish, on_delete=models.SET_NULL, null=True, related_name="order_items")
    name = models.CharField(max_length=140)        # snapshot
    unit_price = models.PositiveIntegerField()      # snapshot (prix paye)
    quantity = models.PositiveSmallIntegerField(default=1)

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.quantity}x {self.name}"


class Review(TimeStampedModel):
    """Note + commentaire apres une commande livree."""
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="review")
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name="reviews")
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="reviews")
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                               null=True, blank=True, related_name="driver_reviews")
    rating = models.PositiveSmallIntegerField(default=5, help_text="Note de 1 a 5")
    driver_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.rating}★ — {self.restaurant.name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.restaurant.recompute_rating()
        if self.driver_id and self.driver_rating:
            from apps.delivery.models import DriverProfile
            avg = Review.objects.filter(driver_id=self.driver_id, driver_rating__isnull=False)                 .aggregate(a=models.Avg("driver_rating"))["a"]
            DriverProfile.objects.filter(user_id=self.driver_id).update(rating=round(avg or 0, 1))
