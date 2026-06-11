from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel
from apps.restaurants.models import Restaurant


class DriverProfile(TimeStampedModel):
    """Profil livreur. Peut etre rattache a un restaurant (employe) ou freelance."""

    class Vehicle(models.TextChoices):
        MOTO = "moto", "Moto"
        BIKE = "bike", "Velo"
        CAR = "car", "Voiture"
        FOOT = "foot", "A pied"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="driver_profile")
    # Livreur enregistre sous un restaurant (gestion par le resto)
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
