from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel
from apps.restaurants.models import Restaurant


class DriverProfile(TimeStampedModel):
    """Profil livreur. Peut etre rattache a un restaurant par l'equipe ONE EAT."""

    class Vehicle(models.TextChoices):
        MOTO = "moto", "Moto"
        BIKE = "bike", "Velo"
        CAR = "car", "Voiture"
        FOOT = "foot", "A pied"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="driver_profile")
    # Affectation optionnelle geree par la plateforme.
    restaurant = models.ForeignKey(Restaurant, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="drivers")

    vehicle = models.CharField(max_length=6, choices=Vehicle.choices, default=Vehicle.MOTO)
    phone = models.CharField(max_length=20, blank=True)

    is_available = models.BooleanField(default=False, help_text="En ligne / disponible")
    # Position courante du livreur (geolocalisation)
    current_lat = models.FloatField(null=True, blank=True)
    current_lng = models.FloatField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)

    service_radius_km = models.PositiveSmallIntegerField(default=10)

    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0)
    deliveries_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Livreur {self.user.display_name}"

    @property
    def active_mission(self):
        from apps.orders.models import Order
        return (Order.objects.filter(driver=self.user)
                .exclude(status__in=[Order.Status.DELIVERED, Order.Status.CANCELLED])
                .select_related("restaurant", "customer").first())

    @property
    def status_key(self):
        """offline | available | on_mission (statuts du cahier des charges)."""
        if self.active_mission:
            return "on_mission"
        return "available" if self.is_available else "offline"

    def earnings_since(self, since=None):
        """Gains livreur = frais de livraison des courses livrees."""
        from django.db.models import Count, Sum
        from apps.orders.models import Order
        qs = Order.objects.filter(driver=self.user, status=Order.Status.DELIVERED)
        if since:
            qs = qs.filter(delivered_at__gte=since)
        agg = qs.aggregate(total=Sum("delivery_fee"), n=Count("id"))
        return {"amount": agg["total"] or 0, "count": agg["n"] or 0}
